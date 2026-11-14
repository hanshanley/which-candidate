import json
import socket
from copy import deepcopy
from pathlib import Path

import pytest

from which_candidate import house_candidates as house
from which_candidate import rebuild_publication
from which_candidate.storage import fingerprint, read_rows

ROOT = Path(__file__).resolve().parents[1]


def identity_fixture():
    candidate = {"name": "Jane Smith", "state": "CA", "district": "02", "party": "Republican"}
    fec = {
        "name": "SMITH, JANE",
        "first": "Jane",
        "last": "Smith",
        "fec_id": "H6CA02001",
        "state": "CA",
        "district": "02",
        "party": "REP",
        "chamber": "house",
        "election_year": 2026,
    }
    website = {
        "candidate": "Jane Smith",
        "cand_id": fec["fec_id"],
        "candidate_cycle_id": "H6CA02001-2026",
        "state": "CA",
        "district": "2.0",
        "party": "R",
        "office": "house",
        "year": "2026",
    }
    return candidate, fec, website


@pytest.mark.parametrize(
    "change",
    [
        {"state": "NY"},
        {"party": "DEM"},
        {"chamber": "senate"},
        {"election_year": 2024},
        {"name": "JONES, JANE", "last": "Jones"},
    ],
)
def test_official_link_cannot_cross_identity_context(change):
    candidate, fec, _ = identity_fixture()
    result = house.resolve_identity(candidate, [{**fec, **change}], [])
    assert result["fec_id"] is None


def test_district_change_does_not_destroy_a_unique_stable_person_id():
    candidate, fec, website = identity_fixture()
    fec["district"], website["district"] = "04", "4"
    result = house.resolve_identity(candidate, [fec], [website])
    assert result["fec_id"] == fec["fec_id"]
    assert "registration_district_differs" in result["status"]
    assert result["website"] == website
    result = house.resolve_identity(candidate, [], [website])
    assert result["fec_id"] is None


def test_conflicting_ids_are_held_and_retained_not_silently_selected():
    candidate, fec, website = identity_fixture()
    alternative = {**fec, "fec_id": "H6CA02002"}
    result = house.resolve_identity(candidate, [fec, alternative], [])
    assert result["fec_id"] is None
    assert len(result["official_alternatives"]) == 2
    website["cand_id"] = "H6CA02003"
    result = house.resolve_identity(candidate, [fec], [website])
    assert result["fec_id"] is None
    assert result["status"] == "ambiguous_or_conflicting"


def test_all_house_choices_reconcile_to_the_native_roster():
    panel = [
        r
        for r in read_rows(ROOT / "results/2026-v4/candidate-queries.jsonl.gz")
        if r["chamber"] == "house"
    ]
    choices = read_rows(ROOT / "results/house/all-choices.jsonl.gz")
    candidates = read_rows(ROOT / "results/house/candidates.jsonl.gz")
    expected = {
        (r["contest_id"], str(c["candidate_id"])): c
        for r in panel
        for c in r["native_evidence"]["native"]["candidates"]
    }
    assert len(choices) == len(expected)
    assert len({r["contest_id"] for r in choices}) == len(panel) == 435
    assert {(r["contest_id"], r["candidate_id"]) for r in choices} == set(expected)
    for row in choices:
        native = expected[(row["contest_id"], row["candidate_id"])]
        assert all(row[k] == native[k] for k in ("name", "party", "votes"))
    assert {(r["contest_id"], r["candidate_id"]) for r in candidates} == {
        key for key, row in expected.items() if house.is_person(row["name"])
    }
    assert house.is_person("Wendell Blankenship")
    assert house.is_person("Jane Write")
    assert not house.is_person("Write-in")
    assert not house.is_person("None of the Above")
    for row in candidates:
        assert row["native_flags_unverified"] is not None
        assert row["legislative"]["house_incumbent"] is None or (
            row["legislative"]["status"] == "exact_fec_service_crosswalk"
        )


def test_biography_records_preserve_subject_review_and_pre_election_cutoff():
    candidates = read_rows(ROOT / "results/house/candidates.jsonl.gz")
    facts = read_rows(ROOT / "results/house/biography-facts.jsonl.gz")
    by_id = {r["candidate_id"]: r for r in candidates}
    for fact in facts:
        candidate = by_id[fact["candidate_id"]]
        assert fact["candidate_cycle_id"] == candidate["website"]["candidate_cycle_id"]
        assert not fact["model_ready"]
        assert fact["captured_before_election"] == house.capture_before_cutoff(
            fact["first_capture_timestamp"]
        )
        assert "evidence" not in fact
        assert "require_review" in fact["review_status"]
    assert all(r["verified_religion"] is None for r in candidates)
    assert all(r["verified_race_ethnicity"] is None for r in candidates)


def test_house_inventory_replays_offline_without_mutating_sources(tmp_path, monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("Unexpected network access")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket, "getaddrinfo", denied)
    source = ROOT / "results/house"
    expected = json.loads((source / "manifest.json").read_text())
    assert house.build(ROOT, tmp_path / "replay") == expected
    for name, receipt in expected["files"].items():
        assert fingerprint(tmp_path / "replay" / name) == receipt


def test_current_figures_are_house_only_and_coverage_denominators_reconcile():
    panel = read_rows(ROOT / "results/2026-v4/candidate-queries.jsonl.gz")
    original = deepcopy(panel)
    fig, rows, caption = rebuild_publication.geography({"panel": panel})
    try:
        assert all(r["chamber"] == "house" for r in rows)
        assert len(fig.axes) == 1
        assert fig.axes[0].get_xlim() == (0, 100)
        assert "435 House" in caption
        assert panel == original
    finally:
        rebuild_publication.plt.close(fig)
    rows = json.loads((ROOT / "results/house/coverage.json").read_text())
    assert rows[0]["candidates"] == sum(r["candidates"] for r in rows[1:])
    for row in rows:
        for key in ("fec_id", "pre_election_biography", "donor_score", "campaign_website"):
            assert 0 <= row[key] <= row["candidates"]


@pytest.mark.parametrize(("score", "expected"), [(0, 1), (None, 0)])
def test_voting_coverage_distinguishes_a_zero_score_from_missing(score, expected):
    candidate = read_rows(ROOT / "results/house/candidates.jsonl.gz")[0]
    candidate["legislative"]["prior_voting_record"] = {"nokken_poole_dim1": score}
    assert house.coverage([candidate])[0]["prior_federal_voting_score"] == expected
