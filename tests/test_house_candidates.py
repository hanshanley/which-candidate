import csv
import json
import socket
from copy import deepcopy
from pathlib import Path

import pytest

from which_candidate import house_candidates as house
from which_candidate import rebuild_publication
from which_candidate.house_backgrounds import (
    background_profile,
    parse_oregon_page,
    parse_utah_certification,
    parse_utah_profile,
)
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
        if fact.get("historical"):
            assert candidate["identity"]["fec_id"]
            assert fact["record_id"] in candidate["historical_campaign_record_ids"]
            assert fact["source_year"] < 2026
        else:
            assert fact["candidate_cycle_id"] == candidate["website"]["candidate_cycle_id"]
        assert not fact["model_ready"]
        assert fact["captured_before_election"] == house.capture_before_cutoff(
            fact["first_capture_timestamp"]
        )
        assert "evidence" not in fact
        assert "require_review" in fact["review_status"]
    assert all(r["verified_religion"] is None for r in candidates)
    assert all(r["verified_race_ethnicity"] is None for r in candidates)


def test_missing_ids_cannot_inherit_any_historical_person_evidence():
    candidates = read_rows(ROOT / "results/house/candidates.jsonl.gz")
    for row in candidates:
        if not row["identity"]["fec_id"]:
            assert not row["historical_biography"]["historical_biography_available"]
            assert not row["historical_campaign_record_ids"]
            assert not row["background"]["dated_religion_observations"]
            assert not row["background"]["member_authorized_biographies"]


def test_write_in_ballot_label_needs_exact_district_and_preserves_affiliation():
    candidate, fec, website = identity_fixture()
    candidate["party"] = "Write-In"
    result = house.resolve_identity(candidate, [fec], [website])
    assert result["fec_id"] == fec["fec_id"]
    assert "write_in_is_ballot_label" in result["status"]
    assert candidate["party"] == "Write-In"
    assert house.resolve_identity(candidate, [{**fec, "district": "03"}], [])["fec_id"] is None


def test_documented_congressional_title_alias_requires_the_same_fec_id():
    candidate, fec, _ = identity_fixture()
    candidate["name"], fec["name"], fec["first"] = "Jo Smith", "SMITH, JOSEPHINE", "Josephine"
    person = {
        "id": {"fec": [fec["fec_id"]], "wikipedia": "Jo Smith (politician)"},
        "name": {"first": "Josephine", "last": "Smith"},
    }
    assert house.resolve_identity(candidate, [fec], [], [person])["fec_id"] == fec["fec_id"]
    person["id"]["fec"] = ["H6CA02002"]
    assert house.resolve_identity(candidate, [fec], [], [person])["fec_id"] is None


def test_official_profile_link_requires_office_cycle_party_and_district():
    candidate = {
        **identity_fixture()[0],
        "identity": {"fec_id": None},
    }
    profile = {
        "name": candidate["name"],
        "state": "CA",
        "district": "02",
        "party": "Republican",
        "election_year": 2026,
        "fields": {"occupation": "Teacher"},
        "chamber": "house",
    }
    inputs = {"people": [], "official_profiles": [profile]}
    assert background_profile(candidate, inputs)["official_candidate_profiles"] == [profile]
    for key, value in (
        ("district", "03"),
        ("party", "Democratic"),
        ("election_year", 2024),
        ("chamber", "senate"),
        ("fields", {}),
    ):
        changed = {**inputs, "official_profiles": [{**profile, key: value}]}
        assert not background_profile(candidate, changed)["official_candidate_profiles"]


def test_pamphlet_parser_excludes_statements_and_state_house_candidates():
    text = (
        "US Representative, 4th District\nJane Smith\nPacific Green\n"
        "Occupation: Statistician\nOccupational Background: Teacher\n"
        "Educational Background: Example College, BS\n"
        "Prior Governmental Experience: Council member\nMy campaign promises..."
    )
    profile = parse_oregon_page(text)[0]
    assert profile["party"] == "Pacific Green"
    assert profile["fields"] == {
        "occupation": "Statistician",
        "occupational_background": "Teacher",
        "education": "Example College, BS",
    }
    assert "promises" not in json.dumps(profile)
    assert not parse_oregon_page(text.replace("US Representative", "State Representative"))


def test_utah_profiles_join_certified_party_and_preserve_multiline_occupation():
    certified = parse_utah_certification(
        "U.S. House of Representatives District 1. First district\nCandidate Party\n"
        "JANE M. SMITH Libertarian\nADONIS HOOSL YN Unaffiliated\n"
        "U.S. House of Representatives District 2. Second district\nCandidate Party\n"
        "JANE SMITH Republican\n"
    )
    text = (
        "Congressional District 1\n\nJane Smith\n\n"
        "CONTACT EMAIL    private@example.org\n\n"
        "WEBSITE    example.org\nCITY OF RESIDENCE    Example City\n\n"
        "YEARS OF RESIDENCE    12\n\nAGE    39\n"
        "OCCUPATION    Physical Education Teacher & Direct Care\n"
        "             Provider\n\nA campaign promise, not a biography field."
    )
    profile = parse_utah_profile(text, certified)
    assert profile["party"] == "Libertarian"
    assert profile["fields"] == {
        "residence_city": "Example City",
        "reported_years_of_residence": "12",
        "reported_age": "39",
        "occupation": "Physical Education Teacher & Direct Care Provider",
        "campaign_website": "example.org",
    }
    assert not profile["model_ready"]
    assert "private@" not in json.dumps(profile)
    assert "campaign promise" not in json.dumps(profile)
    assert parse_utah_profile(text.replace("Congressional", "State House"), certified) is None
    assert certified[1]["name"] == "ADONIS HOOSL YN"
    assert (
        parse_utah_profile(text.replace("Jane Smith", "Adonis Hooslyn"), certified)["party"]
        == "Unaffiliated"
    )


def test_utah_empty_fields_and_nonresponses_do_not_inherit_campaign_prose():
    certified = [{"name": "JANE SMITH", "district": "01", "party": "Democratic"}]
    text = "Congressional District 1\n\nJane Smith\n\n"
    for ending, status in (
        ("NO PROFILE SUBMITTED", "no_profile_submitted"),
        ("NO  PROFILE  SUBMITTED", "no_profile_submitted"),
        ("WEBSITE    example.org\n\nOCCUPATION\n\nI will cut taxes.", "no_structured_fields"),
    ):
        profile = parse_utah_profile(text + ending, certified)
        assert profile["fields"] == {}
        assert profile["response_status"] == status
    for alternatives in (
        [],
        [*certified, *certified],
        [{**certified[0], "district": "02"}],
        [{**certified[0], "name": "JANES MITH"}],
    ):
        profile = parse_utah_profile(text + "OCCUPATION    Teacher", alternatives)
        assert profile["fields"] == {}
        assert profile["response_status"] == "certification_identity_unresolved"


def test_dated_backgrounds_keep_unknowns_and_changes_without_current_labels():
    candidate, fec, _ = identity_fixture()
    candidate["identity"] = {"fec_id": fec["fec_id"]}
    person = {
        "id": {"fec": [fec["fec_id"]], "bioguide": "S000001"},
        "name": {"first": "Jane", "last": "Smith"},
        "terms": [{"state": "CA"}],
    }
    record = {
        "name": "Jane Smith",
        "state": "CA",
        "chamber": "house",
        "publication_date": "2023-01-03",
        "religion_literal": "Unknown",
    }
    inputs = {
        "people": [person],
        "religion_observations": [
            record,
            {
                **record,
                "religion_literal": "Unspecified Protestant",
                "publication_date": "2025-01-02",
            },
            {**record, "publication_date": "2026-11-04"},
            {**record, "state": "NY"},
            {**record, "name": "Jane Jones"},
        ],
    }
    result = background_profile(candidate, inputs)["dated_religion_observations"]
    assert [r["religion_literal"] for r in result] == ["Unknown", "Unspecified Protestant"]
    assert all(not r["current_identity_label"] and not r["model_ready"] for r in result)


def test_background_csv_coverage_counts_people_not_repeated_observations():
    candidates = read_rows(ROOT / "results/house/candidates.jsonl.gz")
    with (ROOT / "results/house/background-observations.csv").open() as stream:
        observations = list(csv.DictReader(stream))
    ids = {r["candidate_id"] for r in observations}
    assert len(ids) == house.coverage(candidates)[0]["factual_background"]
    assert all(r["model_ready"] == "False" for r in observations)
    assert all(r["field"] and r["value"] and r["evidence"] for r in observations)


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
