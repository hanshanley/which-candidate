import zipfile
from pathlib import Path

import pytest

from which_candidate import characteristics_v2 as v2
from which_candidate import characteristics_v3 as v3
from which_candidate.characteristics_acquisition import BASELINE
from which_candidate.storage import read_rows

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def overlay():
    return v3.new_rows(ROOT)


def test_new_source_literals_are_lossless_and_old_rows_unchanged(overlay):
    rows, _, _, previous, observations, _, _ = overlay
    old = {(r["candidate_id"], r["trait"]): r for r in previous}
    keyed = {(r["candidate_id"], r["trait"]): r for r in rows}
    for observation in observations:
        row = keyed[(observation["candidate_id"], observation["trait"])]
        assert observation in row["source_recorded_value"]["reviewed_facts"]
        assert observation in row["evidence"]
    for row in rows:
        before = old[(row["candidate_id"], row["trait"])]
        assert row["baseline_trait_row"] == before["baseline_trait_row"]
        assert all(e in row["evidence"] for e in before["evidence"])
        assert not row["prospective_model_eligible"]
    assert previous == read_rows(ROOT / v2.OUT / "candidate-traits.jsonl.gz")
    assert v2.verify_frozen(ROOT, BASELINE) > 200


def test_official_birthday_and_completed_credential_not_blank_identity(overlay):
    rows = {r["trait"]: r for r in overlay[0] if r["name"] == "Matt Little"}
    assert rows["age"]["analysis_value"] == 41
    assert rows["age"]["uncertainty"]["age_years_interval"] == [41, 41]
    assert rows["education"]["analysis_value"] == "doctoral_or_professional"
    assert rows["profession"]["analysis_value"] == "legal"
    assert rows["gender"]["analysis_value"] == "M"
    assert not rows["race"]["analysis_eligible"]
    assert not rows["ethnicity"]["analysis_eligible"]
    assert not rows["religion"]["analysis_eligible"]


def test_post_election_religion_and_positive_service_do_not_create_model_inputs(overlay):
    rows = {(r["name"], r["trait"]): r for r in overlay[0]}
    for name in ("Eric Yonce", "Kelly Esti", "Kristi Burke"):
        row = rows[(name, "religion")]
        assert row["factual_qualified"]
        assert not row["analysis_eligible"]
    assert rows[("Gay Valimont", "religion")]["value"]["explicit_source_observations"] == [
        "Methodist"
    ]
    for row in overlay[0]:
        if row["trait"] in {"military", "prior_elected_office", "other_government"}:
            assert row["value"] is not False
            assert not row["analysis_eligible"] or row["trait"] == "military"


def test_race_reference_requires_positive_historical_identification(overlay):
    for row in overlay[0]:
        if row["trait"] != "race" or not row["analysis_eligible"]:
            continue
        identities = set().union(
            *(
                set(o["value"])
                for o in row["evidence"]
                if o.get("source_id", "").startswith("v3-cawp-history-")
            )
        )
        assert ("Black" in identities) != ("White" in identities)
        assert row["analysis_value"] in identities
        assert "historical_2024" in row["timing_status"]
    assert all(not r["analysis_eligible"] for r in overlay[0] if r["trait"] == "ethnicity")


def test_election_control_resolution_never_changes_outcomes_or_service_verification(overlay):
    panel = overlay[2]
    before = read_rows(ROOT / v2.OUT / "panel-overlay.jsonl.gz")
    resolved = []
    for old, new in zip(before, panel):
        for key in old:
            if key not in {"D_incumbent", "R_incumbent"}:
                assert old[key] == new[key], key
        for party in ("D", "R"):
            key = f"{party}_incumbent"
            if old[key] != new[key]:
                assert old[key] is None
                assert isinstance(new[key], bool)
                assert new[f"v3_{party}_incumbency_evidence"]
                resolved.append(new["contest_id"])
    assert resolved
    for row in overlay[0]:
        if row["coding_status"] == "resolved_not_current_federal_incumbent":
            assert row["status"] == "inapplicable"
            assert row["analysis_value"] is None
            assert not row["analysis_eligible"]


def test_acquisition_is_not_a_held_source_or_corroboration_count(tmp_path, overlay):
    rows, _, _, previous, observations, conflicts, _ = overlay
    (tmp_path / "data").mkdir()
    from which_candidate.characteristics_acquisition import ACQUISITIONS

    (tmp_path / ACQUISITIONS).write_bytes((ROOT / ACQUISITIONS).read_bytes())
    counts = v3.progress(tmp_path, rows, previous, observations, conflicts)
    assert counts["newly_acquired_observations"] == counts["acquisition"]["new_acquired_claims"]
    assert counts["new_source_candidate_trait_fields"] <= counts["newly_acquired_observations"]
    assert (
        counts["newly_informed_candidate_trait_fields"]
        < counts["new_source_candidate_trait_fields"]
    )
    assert counts["newly_informed_candidates"] <= counts["newly_informed_candidate_trait_fields"]
    assert counts["D_unknown_incumbency_after"] < counts["D_unknown_incumbency_before"]


def test_historical_research_ledger_remains_strict_with_incremental_evidence():
    from which_candidate.house_study import attach_research_history

    profiles = read_rows(ROOT / "results/house-study/candidate-profiles.jsonl.gz")
    evidence = [p["acquired_background_observations"][:] for p in profiles]
    research, repair = attach_research_history(ROOT, profiles)
    assert research["supplemental_v3_observations"] > 0
    assert repair["historical_milestone_not_new_acquisition"]
    assert evidence == [p["acquired_background_observations"] for p in profiles]
    queued = next(
        p
        for p in profiles
        if p["in_initial_research_queue"]
        and any(
            not isinstance(o["evidence"], dict) or not o["evidence"].get("id", "").startswith("v3-")
            for o in p["acquired_background_observations"]
        )
    )
    queued["acquired_background_observations"] = []
    with pytest.raises(ValueError, match="stale|coverage|unsupported"):
        attach_research_history(ROOT, profiles)


def test_complete_zip_lzma_retains_exact_files_with_standard_library(tmp_path):
    from which_candidate.publication import write_zip

    source = tmp_path / "report.html"
    source.write_bytes(b"<p>Complete evidence and report</p>\n" * 100)
    code = tmp_path / "replay.py"
    code.write_text("print('complete replay')\n")
    archive_path = tmp_path / "complete.zip"
    write_zip(archive_path, {"report.html": source, "replay.py": code}, lzma_text_threshold=1000)
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.getinfo("report.html").compress_type == zipfile.ZIP_LZMA
        assert archive.getinfo("replay.py").compress_type == zipfile.ZIP_DEFLATED
        archive.extractall(tmp_path / "extracted")
    for path in (source, code):
        assert (tmp_path / "extracted" / path.name).read_bytes() == path.read_bytes()


def test_v3_keeps_full_family_and_reports_actual_complete_matched_predictions():
    fits = read_rows(ROOT / v3.OUT / "fits.jsonl.gz")
    predictions = read_rows(ROOT / v3.OUT / "predictions.jsonl.gz")
    folds = read_rows(ROOT / v3.OUT / "folds.jsonl.gz")
    deletions = read_rows(ROOT / v3.OUT / "state-deletions.jsonl.gz")
    assert {f["trait"] for f in fits} == set(v3.v1.TRAITS)
    assert next(f for f in fits if f["trait"] == "race")["status"] == "estimated"
    for fit in fits:
        if fit["status"] != "estimated":
            assert fit["holm_pvalue"] == 1
            continue
        p = fit["prediction"]
        rows = [r for r in predictions if r["trait"] == fit["trait"]]
        assert p["complete"] and len(rows) == p["population_candidates"]
        assert len({r["candidate_election_id"] for r in rows}) == len(rows)
        assert all(r["complete"] for r in deletions if r["trait"] == fit["trait"])
        for fold in [r for r in folds if r["trait"] == fit["trait"]]:
            assert fold["status"] == "estimated"
            assert not set(fold["training_people"]) & set(fold["test_people"])
