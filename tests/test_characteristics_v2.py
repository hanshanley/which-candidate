import copy
import json
from pathlib import Path

import numpy as np
import pytest

from which_candidate import characteristics_v2 as v2
from which_candidate import house_characteristics as v1
from which_candidate.storage import read_rows

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("interval", "expected"),
    [
        ([38, 39], "under_40"),
        ([39, 40], None),
        ([40, 41], "40_to_59"),
        ([59, 60], None),
        ([60, 61], "60_or_older"),
        (None, None),
    ],
)
def test_interval_band_never_invents_a_birthday_or_crosses_a_boundary(interval, expected):
    assert v2.age_band(interval) == expected


def sample():
    rng = np.random.default_rng(814)
    rows = []
    for state in range(12):
        for candidate in range(8):
            lean = float(rng.uniform(25, 75))
            rows.append(
                {
                    "state": f"S{state}",
                    "D_incumbent": True,
                    "R_incumbent": False,
                    "D_candidate_election_id": f"{state}:{candidate}",
                    "contest_id": f"contest:{state}:{candidate}",
                    "D_name": "Candidate",
                    "presidential_D_two_party_share_pct": lean,
                    "descriptive_gap_share_pp": float(rng.normal()),
                    "_value": float(rng.uniform(35, 75)),
                }
            )
    return rows


def test_training_only_constant_nuisance_is_not_an_unseen_stratum_prediction():
    rows = sample()
    rows[-1]["D_incumbent"] = False
    predictions, folds = v2.paired(rows, "age", None)
    failed = next(f for f in folds if f["held_out_state"] == "S11")
    assert failed["failure_reason"] == "unseen_test_incumbency_stratum"
    assert not any(r["state"] == "S11" for r in predictions)
    assert all(not set(f["training_people"]) & set(f["test_people"]) for f in folds)
    retained = v2.common_support(rows, "age")
    assert len(retained) == len(rows) - 1
    predictions, folds = v2.paired(retained, "age", None)
    assert len(predictions) == len(retained)
    assert all(f["status"] == "estimated" for f in folds)
    for state in {r["state"] for r in retained}:
        reduced = [r for r in retained if r["state"] != state]
        assert len(v2.paired(reduced, "age", None)[0]) == len(reduced)


def test_three_state_support_is_covariate_only_and_preserves_people_separation():
    rows = sample()
    for state in ("S0", "S1"):
        row = next(r for r in rows if r["state"] == state)
        row["D_incumbent"] = False
    selected = v2.common_support(rows, "age")
    changed = copy.deepcopy(rows)
    for row in changed:
        row["descriptive_gap_share_pp"] = 1e9
    assert [r["contest_id"] for r in selected] == [
        r["contest_id"] for r in v2.common_support(changed, "age")
    ]
    assert all(r["D_incumbent"] for r in selected)
    selected[0]["person_group"] = selected[10]["person_group"] = "same-person"
    _, folds = v2.paired(selected, "age", None)
    assert all(not set(f["training_people"]) & set(f["test_people"]) for f in folds)


def test_rank_deficient_focal_is_not_dropped():
    rows = sample()
    for row in rows:
        row["_value"] = 60.0
    predictions, folds = v2.paired(rows, "age", None)
    assert not predictions
    assert all(f["status"] == "failed" for f in folds)


def test_complementary_incumbent_nuisance_is_reparameterized_without_dropping_focal():
    rows = sample()
    for i, row in enumerate(rows):
        row["D_incumbent"] = bool(i % 2)
        row["R_incumbent"] = not row["D_incumbent"]
    predictions, folds = v2.paired(rows, "age", None)
    assert len(predictions) == len(rows)
    assert all(
        f["baseline_terms"] == ["intercept", "lean_10pp", "lean_squared", "D_incumbent"]
        for f in folds
    )
    assert all(f["augmented_terms"][-1] == "age" for f in folds)


@pytest.fixture(scope="module")
def reviewed():
    return v2.reviewed_rows(ROOT)


def test_fact_qualification_does_not_invent_identity_reference_or_service_negatives(reviewed):
    rows, _, _, _ = reviewed
    identity = [
        r for r in rows if r["party"] == "Democratic" and r["trait"] in {"race", "ethnicity"}
    ]
    assert any(r["factual_qualified"] for r in identity)
    assert all(not r["analysis_eligible"] for r in identity)
    assert all(
        r["value"] is not False
        for r in rows
        if r["trait"] in {"military", "prior_elected_office", "other_government"}
    )
    assert all(not r["prospective_model_eligible"] for r in rows)


def test_degree_conflict_attendance_and_historical_refusal_are_not_promoted(reviewed):
    rows = {(r["candidate_id"], r["trait"]): r for r in reviewed[0]}
    assert rows[("220698", "education")]["status"] == "uncertain"
    assert not rows[("220698", "education")]["analysis_eligible"]
    assert rows[("220448", "education")]["value"]["documented_completed_attainment"] is None
    assert not rows[("220448", "education")]["analysis_eligible"]
    assert rows[("220950", "education")]["analysis_value"] == "masters"
    assert rows[("220950", "education")]["analysis_eligible"]
    assert (
        sum(
            r["trait"] == "religion"
            and r["party"] == "Democratic"
            and "Questionnaire nonresponse" in r["eligibility_reason"]
            for r in reviewed[0]
        )
        == 15
    )


def test_service_bridges_are_v2_only_and_unknown_opponent_remains_held(reviewed):
    rows, _, panel, _ = reviewed
    values = {(r["candidate_id"], r["trait"]): r for r in rows}
    for cid in ("220756", "220835"):
        assert values[(cid, "incumbency")]["value"] is True
        assert values[(cid, "house_service")]["analysis_eligible"]
    keating = next(r for r in panel if r["D_name"] == "Bill Keating")
    assert keating["D_incumbent"] is True and keating["R_incumbent"] is None
    original = read_rows(ROOT / "results/house-study/candidate-comparisons.jsonl.gz")
    assert next(r for r in original if r["D_name"] == "Bill Keating")["D_incumbent"] is None
    assert (
        sum(
            r["trait"] == "incumbency" and r["party"] == "Democratic" and r["status"] == "unknown"
            for r in rows
        )
        == 37
    )


def test_frozen_hashes_and_relational_evidence_references(reviewed):
    assert v2.verify_frozen(ROOT) > 154
    rows, _, _, baseline = reviewed
    assert len(rows) == len(baseline) == 1284 * 15
    for row in rows:
        old = baseline[row["baseline_trait_row"] - 1]
        assert v1.key(row) == v1.key(old) and row["trait"] == old["trait"]
    seal = json.loads((ROOT / v2.SEAL).read_text())
    assert len(seal["profiles"]) > 40
