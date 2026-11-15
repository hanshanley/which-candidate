import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from which_candidate.house_report import render
from which_candidate.house_study import (
    acquired_evidence,
    build,
    csv_rows,
    held_out_diagnostics,
    trait_comparisons,
)
from which_candidate.house_validation import paired_predictions, predictive_comparisons
from which_candidate.models import available, matrix
from which_candidate.storage import fingerprint, read_rows

ROOT = Path(__file__).resolve().parents[1]


def panel():
    rng = np.random.default_rng(42)
    rows = []
    for state in range(12):
        for district in range(8):
            lean = float(rng.uniform(20, 80))
            age = float(rng.uniform(30, 80))
            unity = float(rng.uniform(0.85, 0.99))
            gap = 2 + 0.1 * (lean - 50) + 10 * (1 - unity) + float(rng.normal())
            identifier = f"candidate-{state}-{district}"
            rows.append(
                {
                    "year": 2026,
                    "state": f"S{state:02}",
                    "district": f"{district:02}",
                    "contest_id": identifier,
                    "D_candidate_election_id": identifier,
                    "person_group": identifier,
                    "D_name": identifier,
                    "eligible": True,
                    "D_incumbent": district % 2 == 0,
                    "R_incumbent": district % 3 == 0,
                    "service_verified_incumbent": district % 2 == 0,
                    "age_years": age,
                    "chamber_tenure_years": float(rng.uniform(0, 30)),
                    "nokken_poole_dim1": float(rng.uniform(-0.7, -0.1)),
                    "party_unity_score": unity,
                    "source_recorded_gender": "F" if district % 3 == 1 else "M",
                    "presidential_D_two_party_share_pct": lean,
                    "D_two_party_share_pct": lean + gap,
                    "descriptive_gap_share_pp": gap,
                    "previous_presidential_share": lean - 2,
                }
            )
    return rows


def test_held_out_predictions_exclude_both_state_and_shared_people():
    rows = panel()
    rows[0]["person_group"] = rows[8]["person_group"] = "shared-person"
    predictions, folds, metrics = held_out_diagnostics(rows)
    for fold in folds:
        assert fold["held_out_state"] not in fold["training_states"]
        assert not set(fold["test_people"]) & set(fold["training_people"])
        assert not set(fold["test_candidate_ids"]) & set(fold["training_candidate_ids"])
    changed = deepcopy(rows)
    for row in changed:
        if row["state"] == "S00" or row["person_group"] == "shared-person":
            row["descriptive_gap_share_pp"] += 30
            row["D_two_party_share_pct"] += 30
        row["D_incumbent"] = not row["D_incumbent"]
    new, _, _ = held_out_diagnostics(changed)
    expected = [r["expected_D_share_pct"] for r in predictions if r["state"] == "S00"]
    observed = [r["expected_D_share_pct"] for r in new if r["state"] == "S00"]
    assert observed == pytest.approx(expected)
    residual = np.array([r["held_out_residual_margin_pp"] / 2 for r in predictions])
    assert metrics["held_out_MAE_share_pp"] == pytest.approx(np.mean(np.abs(residual)))
    assert metrics["n"] == len(rows)


def test_defection_increment_margin_intervals_and_fixed_six_test_correction():
    rows = panel()
    fits = trait_comparisons(rows)
    primary = [r for r in fits if r["variant"] == "primary"]
    fit = next(r for r in primary if r["model"] == "defection")
    sample = [r for r in rows if available(r, "defection")]
    x, terms = matrix(sample, "defection", [2026])
    coefficients = np.linalg.lstsq(x, [r["descriptive_gap_share_pp"] for r in sample], rcond=None)[
        0
    ]
    changed = deepcopy(sample)
    for row in changed:
        row["party_unity_score"] -= 0.01
    changed_x, _ = matrix(changed, "defection", [2026])
    contrast = (changed_x - x) @ coefficients
    assert fit["estimate_share_pp"] == pytest.approx(float(contrast[0]))
    assert fit["ci_low_margin_pp"] == 2 * fit["ci_low"]
    assert fit["ci_high_margin_pp"] == 2 * fit["ci_high"]
    common = {r["variant"]: r for r in fits if r["model"] == "ideology"}
    assert (
        common["common_sample_2020"]["candidate_election_ids"]
        == common["common_sample_2024"]["candidate_election_ids"]
    )
    ordered = sorted(primary, key=lambda r: r["pvalue"])
    maximum = 0
    for rank, row in enumerate(ordered):
        maximum = max(maximum, min(1, (6 - rank) * row["pvalue"]))
        assert row["holm_pvalue"] == pytest.approx(maximum)
    assert terms[-1] == "defection_5pp"


def test_real_study_retains_all_candidates_contests_holds_and_exact_replay(tmp_path):
    summary = build(ROOT, tmp_path)
    profiles = read_rows(tmp_path / "candidate-profiles.jsonl.gz")
    comparisons = read_rows(tmp_path / "candidate-comparisons.jsonl.gz")
    assert len(comparisons) == 435
    assert len(profiles) == len(read_rows(ROOT / "results/house/candidates.jsonl.gz"))
    assert {r["contest_id"] for r in comparisons} == {r["contest_id"] for r in profiles}
    assert summary["eligible_comparisons"] + summary["held_comparisons"] == 435
    assert sum(r["comparison_eligible"] for r in profiles) == summary["eligible_comparisons"]
    observations = csv_rows(ROOT / "results/house/background-observations.csv")
    expected = Counter((r["candidate_id"], r["contest_id"]) for r in observations)
    assert sum(len(r["acquired_background_observations"]) for r in profiles) == len(observations)
    assert summary["candidates_with_acquired_observations"] == len(expected)
    research = summary["candidate_background_research"]
    assert research["documented_dispositions"] == research["initially_uncovered"] == 601
    assert research["baseline_with_observations"] + research["newly_covered_people"] == len(
        expected
    )
    assert len(csv_rows(tmp_path / "research-dispositions.csv")) == 601
    assert len(csv_rows(tmp_path / "background-field-coverage.csv")) == len(profiles)
    assert sum(row["in_initial_research_queue"] for row in profiles) == 601
    for row in profiles:
        assert (
            len(row["acquired_background_observations"])
            == expected[(row["candidate_id"], row["contest_id"])]
        )
        assert row["background_model_ready"] is False
        if not row["comparison_eligible"]:
            assert row["held_out_residual_margin_pp"] is None
            assert row["presidential_gap_margin_pp"] is None
    losing = next(r for r in profiles if r["candidate_id"] == "219731")
    assert losing["provider_winner_flag"] is False
    assert any(
        r["field"] == "education"
        and "Associate Degree in Nursing" in r["value"]
        and r["model_ready"] is False
        for r in losing["acquired_background_observations"]
    )
    for name, receipt in json.loads((ROOT / "results/house-study/manifest.json").read_text())[
        "files"
    ].items():
        assert fingerprint(tmp_path / name) == receipt, name


def test_local_report_escapes_embedded_records_and_uses_only_relative_figures():
    name = '</script><img src="https://attacker.test">'
    document = render("## Findings\n\nEvidence.", [{"name": name}], [])
    assert name not in document
    payload = document.split('<script id="candidate-data" type="application/json">')[1].split(
        "</script>"
    )[0]
    assert json.loads(payload) == [{"name": name}]
    assert "https://fonts." not in document
    assert 'id="download"' in document


def test_paired_trait_predictions_purge_people_and_detect_transferable_signal():
    rows = panel()
    for row in rows:
        row["D_incumbent"] = row["service_verified_incumbent"] = True
        row["descriptive_gap_share_pp"] = (
            12 * (row["source_recorded_gender"] == "F") + row["age_years"] / 100
        )
        row["D_two_party_share_pct"] = (
            row["presidential_D_two_party_share_pct"] + row["descriptive_gap_share_pp"]
        )
    rows[0]["person_group"] = rows[8]["person_group"] = "shared-person"
    predictions, folds = paired_predictions(rows, "gender")
    for fold in folds:
        assert fold["held_out_state"] not in fold["training_states"]
        assert not set(fold["test_people"]) & set(fold["training_people"])
        assert not set(fold["test_candidate_ids"]) & set(fold["training_candidate_ids"])
    changed = deepcopy(rows)
    for row in changed:
        if row["state"] == "S00" or row["person_group"] == "shared-person":
            row["descriptive_gap_share_pp"] += 40
            row["D_two_party_share_pct"] += 40
    modified, _ = paired_predictions(changed, "gender")
    for key in ("baseline_expected_D_share_pct", "augmented_expected_D_share_pct"):
        assert [r[key] for r in predictions if r["state"] == "S00"] == pytest.approx(
            [r[key] for r in modified if r["state"] == "S00"]
        )
    summaries, all_predictions, _, deletions = predictive_comparisons(rows)
    gender = next(r for r in summaries if r["model"] == "gender")
    paired = [r for r in all_predictions if r["model"] == "gender"]
    assert gender["augmented_MAE_share_pp"] < gender["baseline_MAE_share_pp"] / 4
    assert gender["MAE_gain_share_pp"] == pytest.approx(
        np.mean([r["absolute_error_gain_share_pp"] for r in paired])
    )
    assert gender["gain_ci_low_share_pp"] > 0
    deleted = next(r for r in deletions if r["model"] == "gender" and r["deleted_state"] == "S00")
    independent, _ = paired_predictions([r for r in rows if r["state"] != "S00"], "gender")
    assert deleted["MAE_gain_share_pp"] == pytest.approx(
        np.mean([r["absolute_error_gain_share_pp"] for r in independent])
    )


def test_missing_fold_support_suppresses_predictive_interval_not_zero_imputation():
    rows = panel()
    for row in rows:
        row["D_incumbent"] = row["service_verified_incumbent"] = True
        row["source_recorded_gender"] = "F" if row["state"] == "S00" else "M"
    summaries, _, folds, _ = predictive_comparisons(rows)
    gender = next(r for r in summaries if r["model"] == "gender")
    assert gender["paired_predictions"] < gender["qualified_candidates"]
    assert gender["complete_paired_predictions"] is False
    assert gender["gain_ci_low_share_pp"] is None
    assert gender["gain_ci_high_share_pp"] is None
    assert (
        next(r for r in folds if r["model"] == "gender" and r["held_out_state"] == "S00")["status"]
        == "insufficient_training_support"
    )


def test_acquired_profile_values_retain_qualifications_and_reject_wrong_subjects():
    candidate = {
        "candidate_id": "1",
        "contest_id": "contest",
        "name": "Jane Doe",
        "state": "AL",
        "district": "04",
        "party": "Democratic",
    }
    observation = {
        **candidate,
        "field": "education",
        "value": json.dumps("Associate degree"),
        "source_kind": "campaign_extraction",
        "source_year": "2026",
        "observation_date": "20260924030253",
        "model_ready": "False",
        "qualification": "machine_extracted; subject_and_field_require_review",
        "evidence": json.dumps({"record_id": "fact", "parent_document_id": "document"}),
    }
    fact = {
        "candidate_id": "1",
        "record_id": "fact",
        "state": "AL",
        "field": "education",
        "original_urls": ["https://example.test/biography"],
        "captured_before_election": True,
    }
    result = acquired_evidence([candidate], [observation], [fact])[("1", "contest")][0]
    assert result["value"] == "Associate degree"
    assert result["model_ready"] is False
    assert result["qualification"] == observation["qualification"]
    assert result["evidence"]["original_urls"] == fact["original_urls"]
    with pytest.raises(ValueError, match="identity"):
        acquired_evidence([candidate], [{**observation, "party": "Republican"}], [fact])
