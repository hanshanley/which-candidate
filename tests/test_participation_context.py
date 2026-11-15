import json
import shutil
from copy import deepcopy
from pathlib import Path

import pytest

from which_candidate import rebuild_package
from which_candidate.house_report import render
from which_candidate.participation_context import (
    OUTPUT,
    PACKET,
    aggregate_rows,
    attach,
    build,
    house_rows,
    result_matches,
    validate_packet,
)
from which_candidate.storage import fingerprint, read_rows, write_json

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def packet():
    return json.loads((ROOT / PACKET).read_bytes())


def test_native_counts_preserve_zero_unknown_scope_dates_and_source_receipts(packet):
    data = validate_packet(packet)
    sample = deepcopy(data)
    sample["counts"]["snapshot"]["early_voting"][0]["ballots"] = 0
    sample["counts"]["snapshot"]["early_voting"][1]["ballots"] = None
    rows = aggregate_rows(packet, sample)
    assert rows[0]["reported_count"] == 0
    assert rows[1]["reported_count"] is None
    assert rows[0]["original_source_receipts"][0]["sha256"]
    assert rows[0]["source_retrieved_at"] != packet["imported_at"]
    assert rows[0]["evidence"]["replay_scope"].startswith("pinned_normalized")
    assert any(r["geography_level"] == "source_region" for r in rows)
    assert any(r["source_section"] == "demographics" for r in rows)
    assert all(r["analytical_turnout_pct"] is None for r in rows)
    assert all(r["model_ready"] is False and not r["district_join_qualified"] for r in rows)


def test_maine_snapshots_are_separate_and_missing_final_categories_are_not_zero(packet):
    rows = house_rows(packet, validate_packet(packet))
    final = [r for r in rows if r["snapshot_id"] == "native_reported_final_major_party_counts"]
    assert {r["category"]: r["reported_count"] for r in final} == {
        "D": 165432,
        "R": 170890,
        "O": None,
        "blank": None,
    }
    assert all(r["source_update_label"] is None for r in final)
    assert all(r["publication_date"] == "2026-11-12" for r in final)
    assert len({r["snapshot_id"] for r in rows if r["state_code"] == "ME"}) == 3
    assert next(r for r in rows if r["category"] == "unassigned_write_ins")["party"] == ""


def test_matches_require_unique_election_district_party_name_and_candidate_context(packet):
    rows = house_rows(packet, validate_packet(packet))
    original = next(r for r in rows if r["source_name"] == "(D) CASE, Ed")
    candidate = {
        "candidate_id": "test-case",
        "contest_id": "2026:house:HI:01:general:source_general",
        "name": "Ed Case",
        "state": "HI",
        "district": "01",
        "party": "Democratic",
        "votes": 126337,
    }
    assert result_matches([deepcopy(original)], [candidate])[0]["candidate_id"] == "test-case"
    for changed in (
        {"state": "NY"},
        {"district": "02"},
        {"party": "Republican"},
        {"name": "Ed Other"},
        {"contest_id": "2024:house:HI:01:general:source_general"},
    ):
        assert (
            result_matches([deepcopy(original)], [{**candidate, **changed}])[0]["candidate_id"]
            is None
        )
    ambiguous = [candidate, {**candidate, "candidate_id": "other-case"}]
    assert (
        result_matches([deepcopy(original)], ambiguous)[0]["identity_status"] == "ambiguous_match"
    )
    duplicate_rows = result_matches([deepcopy(original), deepcopy(original)], [candidate])
    assert all(r["candidate_id"] is None for r in duplicate_rows)
    wrong_year = {**original, "election_date": "2024-11-05"}
    assert (
        result_matches([wrong_year], [candidate])[0]["identity_status"] == "held_different_election"
    )


def test_changed_normalized_source_and_incomplete_official_inventory_fail_closed(packet):
    changed = deepcopy(packet)
    changed["inputs"]["house"]["data"][0]["votes"] = "0"
    with pytest.raises(ValueError, match="Changed normalized"):
        validate_packet(changed)
    data = deepcopy(validate_packet(packet))
    official = data["official"]["sources"][0]["url"]
    index = next(i for i, row in enumerate(data["house"]) if row["source_url"] == official)
    data["house"].pop(index)
    with pytest.raises(ValueError, match="Incomplete official"):
        house_rows(packet, data)
    data = deepcopy(validate_packet(packet))
    data["official"]["sources"][0]["year"] = "2024"
    with pytest.raises(ValueError, match="official House source context"):
        house_rows(packet, data)
    data = deepcopy(validate_packet(packet))
    data["counts"]["snapshot"]["early_voting"][0]["ballots"] = True
    with pytest.raises(ValueError, match="nonnegative integers"):
        aggregate_rows(packet, data)


def test_complete_real_context_replays_without_sibling_repository_and_detects_staleness(
    tmp_path, packet
):
    (tmp_path / "data").mkdir()
    (tmp_path / "results/house").mkdir(parents=True)
    write_json(tmp_path / PACKET, packet)
    shutil.copyfile(
        ROOT / "results/house/candidates.jsonl.gz",
        tmp_path / "results/house/candidates.jsonl.gz",
    )
    before = fingerprint(tmp_path / "results/house/candidates.jsonl.gz")
    summary = build(tmp_path)
    assert summary["aggregate_observations"] == 6596
    assert summary["state_coverage_decisions"] == 51
    assert summary["candidate_records_with_supplementary_results"] == 12
    profiles = read_rows(tmp_path / "results/house/candidates.jsonl.gz")
    assert attach(tmp_path, profiles) == summary
    assert all("participation_source_context" in profile for profile in profiles)
    historical = {
        **profiles[0],
        "contest_id": profiles[0]["contest_id"].replace("2026:", "2024:", 1),
    }
    historical.pop("participation_source_context")
    attach(tmp_path, [historical])
    assert "participation_source_context" not in historical
    lepage = next(p for p in profiles if p["candidate_id"] == "220469")
    assert lepage["votes"] == 170360
    source_results = lepage["participation_source_context"]["house_source_results"]
    assert {r["reported_count"] for r in source_results} == {170263, 170360, 170890}
    assert fingerprint(tmp_path / "results/house/candidates.jsonl.gz") == before
    manifest = json.loads((tmp_path / OUTPUT / "manifest.json").read_bytes())
    assert build(tmp_path) == summary
    for name, receipt in manifest["files"].items():
        assert fingerprint(tmp_path / OUTPUT / name) == receipt
    (tmp_path / OUTPUT / "summary.json").write_text("{}")
    with pytest.raises(ValueError, match="Changed participation output"):
        attach(tmp_path, profiles)
    build(tmp_path)
    changed = deepcopy(packet)
    changed["imported_at"] = "another-import"
    write_json(tmp_path / PACKET, changed)
    with pytest.raises(ValueError, match="Stale participation inputs"):
        attach(tmp_path, profiles)


def test_packaging_rejects_a_changed_packet_even_if_context_outputs_are_unchanged(
    tmp_path, monkeypatch
):
    original = rebuild_package.fingerprint

    def fingerprint_with_changed_packet(path):
        return {"sha256": "stale", "bytes": 0} if path == ROOT / PACKET else original(path)

    monkeypatch.setattr(rebuild_package, "fingerprint", fingerprint_with_changed_packet)
    with pytest.raises(ValueError, match="Stale participation package input"):
        rebuild_package.build(ROOT, tmp_path)


def test_report_embeds_context_safely_and_exports_it_without_external_requests():
    context = [{"state_context_id": "2026:HI", "value": "</script><img src=x>"}]
    document = render("## Findings\n\nEvidence.", [], [], participation=context)
    payload = document.split('<script id="participation-data" type="application/json">')[1].split(
        "</script>"
    )[0]
    assert json.loads(payload) == context
    assert "</script><img src=x>" not in document
    assert "Statewide count values, definitions and source receipts" in document
    assert "'participation_source_context'" in document
    assert "fetch(" not in document
