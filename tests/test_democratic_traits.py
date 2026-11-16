import json
import shutil
from pathlib import Path

from which_candidate import house_study
from which_candidate.democratic_traits import democratic_trait_rows, standardize_observation
from which_candidate.storage import fingerprint, read_rows

ROOT = Path(__file__).resolve().parents[1]


def observation(field, value, **extra):
    return {
        "field": field,
        "value": value,
        "source_kind": "candidate_campaign_self_report",
        "source_year": "2026",
        "observation_date": "2026-10-01",
        "qualification": "review_required",
        "evidence": {"url": "https://example.test/source", **extra.pop("evidence", {})},
        "model_ready": False,
        **extra,
    }


def profile(observations):
    return {
        "candidate_id": "candidate-1",
        "contest_id": "contest-1",
        "name": "Candidate One",
        "state": "AA",
        "district": "01",
        "party": "Democratic",
        "acquired_background_observations": observations,
        "campaign_websites": [],
    }


def test_standardization_does_not_infer_completion_pay_office_or_service_from_prose():
    attendance = standardize_observation(observation("education", "Attended Example University"))
    campaign = standardize_observation(
        observation("occupation", "Volunteered on a presidential campaign")
    )
    public_service = standardize_observation(
        observation("public_service_experience", "Worked on veterans policy")
    )
    military_family = standardize_observation(
        observation("local_roots", "Grew up in a military family and traveled overseas")
    )
    assert attendance["completion_status"] == "completion_unknown"
    assert campaign["relationship_status"] == "relationship_unknown"
    assert public_service["office_status"] == "elected_or_employment_status_unknown"
    assert military_family["trait"] == "other_background_evidence"
    appointed = standardize_observation(observation("prior_office", "Secretary of Labor"))
    assert appointed["trait"] == "government_or_public_service"
    assert appointed["office_status"] == "elected_or_employment_status_unknown"
    unknown_service = standardize_observation(observation("military_service", "Unknown"))
    assert unknown_service["service_status"] == "service_unknown"


def test_manual_field_reviews_preserve_degree_attendance_conflict_without_leaking_fields():
    degree = standardize_observation(
        observation(
            "education",
            "Bachelor's degree",
            evidence={
                "field_review": {
                    "completion_status": "degree_earned",
                    "claim_status": "supported",
                }
            },
        )
    )
    attendance = standardize_observation(
        observation(
            "education",
            "Attended Example University",
            evidence={
                "field_review": {
                    "completion_status": "attendance_only",
                    "claim_status": "supported",
                }
            },
        )
    )
    conflict = standardize_observation(
        observation(
            "education",
            "Sources report different graduation years",
            evidence={
                "field_review": {
                    "completion_status": "conflicting",
                    "claim_status": "conflicting",
                }
            },
        )
    )
    professional = standardize_observation(
        observation("professional_history", "Worked at Example Corp.")
    )
    assert degree["completion_status"] == "degree_earned"
    assert degree["claim_status"] == "supported"
    assert attendance["completion_status"] == "attendance_only"
    assert conflict["completion_status"] == conflict["claim_status"] == "conflicting"
    assert professional["relationship_status"] == "relationship_unknown"
    assert professional["claim_status"] == "reported"


def test_trait_rows_preserve_identity_unknown_conflict_and_source_lineage():
    rows = democratic_trait_rows(
        [
            profile(
                [
                    observation("education", "Unknown"),
                    observation(
                        "professional_history",
                        {"literal": "Two sources disagree", "claim_status": "conflicting"},
                        evidence={"source_id": "source-2"},
                    ),
                ]
            )
        ],
        expected_population=1,
    )
    assert len(rows) == 1
    row = rows[0]
    assert (row["candidate_id"], row["contest_id"], row["name"]) == (
        "candidate-1",
        "contest-1",
        "Candidate One",
    )
    assert row["unknown_claim_count"] == 1
    assert row["conflicting_claim_count"] == 1
    assert row["review_status"] == "contains_explicit_conflict"
    assert row["source_urls"] == ["https://example.test/source"]
    assert row["standardized_claims"][1]["evidence"]["source_id"] == "source-2"
    assert row["model_ready"] is False


def test_real_trait_population_matches_every_democratic_candidate_once():
    profiles = read_rows(ROOT / "results/house-study/candidate-profiles.jsonl.gz")
    candidates = read_rows(ROOT / "results/house/candidates.jsonl.gz")
    rows = democratic_trait_rows(profiles)
    expected = {
        (row["candidate_id"], row["contest_id"])
        for row in candidates
        if row["party"] == "Democratic"
    }
    assert len(rows) == len(expected) == 449
    assert {(row["candidate_id"], row["contest_id"]) for row in rows} == expected
    assert all(row["party"] == "Democratic" and row["model_ready"] is False for row in rows)


def test_evidence_refresh_reuses_frozen_outputs_and_replays_without_fitting(tmp_path, monkeypatch):
    output = tmp_path / "house-study"
    shutil.copytree(ROOT / "results/house-study", output)
    baseline = json.loads((ROOT / "data/democratic-background-gap-baseline.json").read_text())
    protected = {
        name: fingerprint(ROOT / name)["sha256"] for name in baseline["protected_analysis_sha256"]
    }

    def forbidden(*args, **kwargs):
        raise AssertionError("Evidence-only refresh attempted model fitting")

    monkeypatch.setattr(house_study, "trait_comparisons", forbidden)
    monkeypatch.setattr(house_study, "held_out_diagnostics", forbidden)
    monkeypatch.setattr(house_study, "predictive_comparisons", forbidden)
    summary = house_study.refresh_evidence(ROOT, output)

    assert summary["frozen_analysis_outputs_changed"] is False
    assert summary["new_background_fields_used_in_models"] is False
    traits = read_rows(output / "democratic-candidate-traits.jsonl.gz")
    assert len(traits) == 449
    assert len(house_study.csv_rows(output / "background-field-coverage.csv")) == 1284
    assert protected == {name: fingerprint(ROOT / name)["sha256"] for name in protected}


def test_frozen_local_cache_is_optional_but_existing_bytes_are_protected(tmp_path):
    baseline = {
        "protected_analysis_sha256": {},
        "additional_local_snapshot_sha256": {"artifacts/old-snapshot.csv": "held-sha256"},
    }
    house_study._verify_protected(tmp_path, baseline)
    held = tmp_path / "artifacts/old-snapshot.csv"
    held.parent.mkdir()
    held.write_text("changed")
    import pytest

    with pytest.raises(ValueError, match="Frozen local snapshot changed"):
        house_study._verify_protected(tmp_path, baseline)
