import copy
import csv
import hashlib
import json
from pathlib import Path

import pytest

from which_candidate import characteristics_v2 as v2
from which_candidate import house_characteristics as v1
from which_candidate.characteristics_research import reviewed_claims, source_text
from which_candidate.characteristics_v4 import (
    birth_interval,
    held_fec_review,
    new_rows,
    office_category_support,
)
from which_candidate.characteristics_v4_acquisition import BASELINE, QUEUE, freeze
from which_candidate.storage import fingerprint, json_bytes, read_rows

ROOT = Path(__file__).resolve().parents[1]


def test_subject_scope_rejects_another_person_degree_or_service():
    body = b"<p>Jane Doe</p><p>Teacher</p><p>John Doe</p><p>JD and Navy veteran</p>"
    source = {
        "id": "test-subject",
        "text_scope": {"start": "Jane Doe", "end": "John Doe"},
        "identity_fragment": "Jane Doe",
        "claims": [{"fragment": "Navy veteran"}],
    }
    scoped = source_text(body, source)
    assert "teacher" in scoped
    with pytest.raises(ValueError, match="Unsupported research fragment"):
        reviewed_claims(source, {}, scoped)
    source["text_scope"]["end"] = "Not in document"
    with pytest.raises(ValueError, match="Missing research subject boundary"):
        source_text(body, source)


def test_v4_intervals_do_not_require_or_invent_a_birthday():
    assert birth_interval({"birth_year": 1978}) == [47, 48]
    assert birth_interval({"birth_year": 1971, "birth_month": 9}) == [55, 55]
    assert birth_interval({"birth_year": 1971, "birth_month": 11}) == [54, 55]
    assert birth_interval("1971-09-21") == [55, 55]


def test_v4_actual_acquisition_qualifies_challengers_without_manufacturing_references():
    rows, _, panel, previous, observations, conflicts, held = new_rows(ROOT)
    assert len(observations) == 91
    assert len({o["candidate_id"] for o in observations}) == 27
    assert not conflicts
    assert sum(r["party"] == "Democratic" for r in held) == 7
    assert sum(r["party"] == "Republican" for r in held) == 3
    index = {(r["candidate_id"], r["trait"]): r for r in rows}
    assert index[("220347", "religion")]["analysis_value"] == "protestant"
    assert index[("220351", "age")]["uncertainty"]["age_years_interval"] == [47, 48]
    assert not index[("220351", "age")]["analysis_eligible"]
    assert not index[("220502", "profession")]["analysis_eligible"]
    assert index[("220519", "education")]["analysis_value"] == "doctoral_or_professional"
    assert all(
        not r["analysis_eligible"]
        for r in rows
        if r["trait"] in {"prior_elected_office", "other_government", "ethnicity"}
    )
    before = {
        r["contest_id"]: r
        for r in read_rows(ROOT / "results/house-characteristics-v3/panel-overlay.jsonl.gz")
    }
    assert all(
        r["service_verified_incumbent"] == before[r["contest_id"]]["service_verified_incumbent"]
        for r in panel
    )
    assert len(previous) == len(rows)


def test_held_fec_review_rejects_multiple_ids_and_first_name_only():
    _, candidates, panel, previous, _, _, _ = new_rows(ROOT)
    candidate = next(c for c in candidates if c["name"] == "Eric Jones")
    inputs = copy.deepcopy(read_rows(ROOT / "results/house/source-inputs.jsonl.gz")[0])
    match = next(r for r in inputs["fec"] if r["fec_id"] == "H6CA04222")
    assert len(held_fec_review([candidate], previous, panel, inputs)) == 1
    inputs["fec"].append({**match, "fec_id": "different-person"})
    assert not held_fec_review([candidate], previous, panel, inputs)
    inputs["fec"] = [{**match, "last": "Different"}]
    assert not held_fec_review([candidate], previous, panel, inputs)


def test_positive_office_support_preserves_overlap_and_time_reference():
    observation = {
        "candidate_id": "test",
        "observation_id": "test-office",
        "trait": "prior_elected_office",
        "value": {
            "history": "Michigan House; city council",
            "time_reference": "before_2026-11-03",
        },
    }
    support = office_category_support([observation])
    assert support["overlapping_counts"] == {"state": 1, "local": 1, "federal": 0}
    assert not any(support["single_recorded_category_counts"].values())
    assert not support["contrast_fitted"]
    observation["value"]["time_reference"] = "before_first_House_entry"
    with pytest.raises(ValueError, match="Incompatible V4 office-history"):
        office_category_support([observation])


def test_reuse_signature_covers_values_people_states_controls_and_outcomes():
    row = {
        "trait": "age",
        "contest_id": "test",
        "performance_eligible": True,
        "field_eligible": True,
        "value": 40,
    }
    panel = [
        {
            "contest_id": "test",
            "D_candidate_election_id": "D:test",
            "eligible": True,
            "D_incumbent": False,
            "R_incumbent": True,
            "state": "CA",
            "D_person_id": "person-a",
            "raw_gap_share_pp": 1.5,
        }
    ]
    original = v2.numerical_input_signature([row], panel, "age")
    for key, value in {
        "D_incumbent": True,
        "R_incumbent": False,
        "state": "NY",
        "D_person_id": "person-b",
        "raw_gap_share_pp": 2.5,
    }.items():
        assert v2.numerical_input_signature([row], [{**panel[0], key: value}], "age") != original
    assert v2.numerical_input_signature([{**row, "value": 41}], panel, "age") != original
    assert (
        v2.numerical_input_signature([{**row, "evidence": "new corroboration"}], panel, "age")
        == original
    )


def test_reused_results_refresh_selection_and_holm_without_mutating_cache():
    cached_fit = {"trait": "age", "omnibus_pvalue": 0.001, "holm_pvalue": 1.0}
    obsolete_selection = {"trait": "age", "reason": "old_reason"}
    cache = {"age": ([cached_fit], [], [], [], [], [obsolete_selection], [])}
    panel = [
        {
            "D_candidate_election_id": "D:test",
            "contest_id": "test",
            "eligible": False,
            "state": "CA",
            "D_name": "Example Candidate",
            "D_incumbent": False,
            "R_incumbent": True,
        }
    ]
    fits, _, _, _, _, selections, _ = v1.analyze([], panel, reuse_results=cache)
    assert len(fits) == 15
    assert next(f for f in fits if f["trait"] == "age")["holm_pvalue"] == pytest.approx(0.015)
    assert next(s for s in selections if s["trait"] == "age")["reason"] == "outcome_hold"
    assert cached_fit["holm_pvalue"] == 1.0
    assert obsolete_selection["reason"] == "old_reason"


def test_v4_queue_retains_every_democrat_trait_and_incumbency_stratum():
    baseline = freeze(ROOT)
    with (ROOT / QUEUE).open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == baseline["trait_cells"] == 6735
    assert len({r["candidate_id"] for r in rows}) == 449
    assert baseline["eligible_democrats"] == 405
    assert baseline["incumbency_groups"] == {
        "incumbent": 183,
        "nonincumbent": 242,
        "unknown_incumbency": 24,
    }
    assert len({(r["candidate_id"], r["trait"]) for r in rows}) == len(rows)
    assert sum(r["opponent_incumbency_unresolved"] == "True" for r in rows) > 0


def test_v4_freeze_preserves_v3_bytes_identities_and_all_705_prior_claims():
    baseline = json.loads((ROOT / BASELINE).read_text())
    for path, digest in baseline["protected_sha256"].items():
        assert fingerprint(ROOT / path)["sha256"] == digest
    inputs = read_rows(ROOT / "results/house/source-inputs.jsonl.gz")[0]
    claims = {r["observation_id"]: r for r in inputs["reviewed_characteristic_observations"]}
    assert len(baseline["historical_reviewed_observations"]) == 705
    for key, digest in baseline["historical_reviewed_observations"].items():
        assert hashlib.sha256(json_bytes(claims[key])).hexdigest() == digest
    candidates = read_rows(ROOT / "results/house/candidates.jsonl.gz")
    identities = [
        {k: c[k] for k in ("candidate_id", "contest_id", "name", "state", "district", "party")}
        for c in candidates
    ]
    assert (
        hashlib.sha256(json_bytes(identities)).hexdigest() == baseline["candidate_identity_sha256"]
    )
