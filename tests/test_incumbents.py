import csv
import json
from copy import deepcopy
from pathlib import Path

import pytest

from which_candidate.house_backgrounds import background_profile
from which_candidate.incumbents import (
    clerk_person,
    directory_profiles,
    historian_profile,
    incumbent_tables,
    veteran_profiles,
)
from which_candidate.storage import read_rows

ROOT = Path(__file__).resolve().parents[1]


def service_fixture():
    candidate = {"name": "Jane Smith", "state": "CA", "party": "Republican", "district": "02"}
    person = {
        "id": {"bioguide": "S000001", "fec": ["H6CA02001", "H4CA04001"]},
        "name": {"first": "Jane", "last": "Smith"},
        "terms": [{"type": "rep", "state": "CA", "start": "2025-01-03", "end": "2027-01-03"}],
    }
    record = {
        "publication_date": "2026-11-03",
        "native_xml": (
            '<member><member-info><state postal-code="CA">California</state>'
            "<official-name>Jane Smith</official-name><party>R</party>"
            "<district>04</district><bioguideID>S000001</bioguideID>"
            '<sworn-date date="20250103"/></member-info></member>'
        ),
    }
    return candidate, person, record


def test_directory_cross_page_labels_do_not_absorb_headers_staff_or_family():
    pages = [
        "25 119th CongressCALIFORNIA\n"
        "JANE SMITH, M.D., Republican of Example City, CA; born in Example, CA, "
        "January 1, 1970; edu-\ncation: B.S., Example College; professional",
        "26 Congressional Directory CALIFORNIA\n"
        "history: physician; military service: Army; married: private name; "
        "election history: elected in 2024.\nCongressional Office\n"
        "https://smith.house.gov\nChief of Staff: private name\n",
    ]
    profile = directory_profiles(pages)[0]
    assert profile["source_page"] == 1
    assert profile["fields"] == {
        "birth_clause": "born in Example, CA, January 1, 1970",
        "education": "B.S., Example College",
        "professional_history": "physician",
        "military_service": "Army",
        "election_history": "elected in 2024",
    }
    assert "private" not in json.dumps(profile)
    assert directory_profiles([pages[0]]) == []


def test_historian_attendance_and_ab_degree_are_education_not_career():
    html = (
        "<h1>SMITH, Jane (S000001)</h1><p>SMITH, Jane, a Representative from "
        "California; born in Example, Calif., January 1, 1970; attended Example "
        "College, 1988-1989; A.B., Another College, 1992; lawyer; "
        "U.S. Army Reserve, 1993-1995; elected as a Republican to Congress.</p>"
    )
    fields = historian_profile(html, "S000001")["fields"]
    assert fields["education"] == (
        "attended Example College, 1988-1989; A.B., Another College, 1992"
    )
    assert "graduated" not in fields["education"]
    assert fields["professional_history"] == "lawyer"
    assert fields["military_service"] == "U.S. Army Reserve, 1993-1995"
    with pytest.raises(ValueError, match="does not identify"):
        historian_profile(html, "S000002")
    with pytest.raises(ValueError, match="Ambiguous"):
        historian_profile(html.replace("; elected ", "; appointed "), "S000001")


def test_clerk_identity_does_not_choose_between_campaign_ids_or_require_old_district():
    candidate, person, record = service_fixture()
    linked, evidence = clerk_person(candidate, [person], [record])
    assert linked == person
    assert evidence == record
    assert len(linked["id"]["fec"]) == 2
    assert candidate["district"] == "02"


@pytest.mark.parametrize(
    ("before", "after"),
    [
        ('postal-code="CA"', 'postal-code="NY"'),
        ("<party>R</party>", "<party>D</party>"),
        ("Jane Smith", "John Smith"),
        ("S000001", "S000002"),
        ('date="20250103"', 'date="20261104"'),
        ('date="20250103"', ""),
    ],
)
def test_clerk_identity_requires_qualified_name_state_party_id_and_sworn_date(before, after):
    candidate, person, record = service_fixture()
    record["native_xml"] = record["native_xml"].replace(before, after)
    assert clerk_person(candidate, [person], [record]) == (None, None)


def test_clerk_identity_requires_independent_active_service_and_preserves_write_in_hold():
    candidate, person, record = service_fixture()
    for key, value in (("state", "NY"), ("type", "sen"), ("start", "2026-11-04")):
        changed = deepcopy(person)
        changed["terms"][0][key] = value
        assert clerk_person(candidate, [changed], [record]) == (None, None)
    assert clerk_person({**candidate, "party": "Write-In"}, [person], [record]) == (None, None)
    assert clerk_person(candidate, [person], [record, record]) == (None, None)
    with pytest.raises(ValueError, match="Election Day"):
        clerk_person(candidate, [person], [{**record, "publication_date": "2026-11-04"}])


def test_unparsed_veteran_row_cannot_leak_into_previous_members_branch():
    _, person, _ = service_fixture()
    pages = [
        "1. Smith, Jane Republican California 04 Army Reserve\n"
        "2. Example, Other Republican Guam Delegate Navy\n"
        "Military Veterans\n3 of 6\n"
        "3. Smith, Jane Republican California 04 Marine Corps\n"
    ]
    profiles = veteran_profiles(pages, [person])
    assert [p["fields"]["military_service"] for p in profiles] == [
        "Army Reserve",
        "Marine Corps",
    ]


def test_reviewed_alias_and_member_profile_require_same_stable_id_and_state():
    candidate, person, _ = service_fixture()
    candidate["identity"] = {"fec_id": None}
    candidate["legislative"] = {
        "status": "official_clerk_and_service_crosswalk",
        "bioguide_id": "S000001",
        "house_incumbent": True,
    }
    profile = {
        "bioguide_id": "S000001",
        "state": "CA",
        "chamber": "house",
        "fields": {"education": "Example College"},
    }
    observation = {
        "name": "Jo Smith",
        "state": "CA",
        "chamber": "house",
        "publication_date": "2025-01-02",
        "religion_literal": "Unknown",
    }
    alias = {"bioguide_id": "S000001", "state": "CA", "name": "Jo Smith"}
    inputs = {
        "people": [person],
        "religion_observations": [observation],
        "incumbent_backgrounds": {"profiles": [profile], "aliases": [alias]},
    }
    result = background_profile(candidate, inputs)
    assert result["official_member_profiles"] == [profile]
    assert len(result["dated_religion_observations"]) == 1
    for key, value in (("bioguide_id", "S000002"), ("state", "NY")):
        changed = deepcopy(inputs)
        changed["incumbent_backgrounds"]["profiles"][0][key] = value
        changed["incumbent_backgrounds"]["aliases"][0][key] = value
        result = background_profile(candidate, changed)
        assert not result["official_member_profiles"]
        assert not result["dated_religion_observations"]
    candidate["legislative"] = {"status": "no_unique_fec_service_crosswalk"}
    result = background_profile(candidate, inputs)
    assert not result["official_member_profiles"]
    assert not result["dated_religion_observations"]


def test_latest_religion_refusal_is_not_replaced_by_older_positive_and_zero_is_observed():
    inputs = read_rows(ROOT / "results/house/source-inputs.jsonl.gz")[0]
    candidate = next(
        r
        for r in read_rows(ROOT / "results/house/candidates.jsonl.gz")
        if r["legislative"]["house_incumbent"] is True
    )
    candidate["background"]["dated_religion_observations"] = [
        {"religion_literal": "Catholic", "publication_date": "2023-01-03"},
        {"religion_literal": "Refused", "publication_date": "2025-01-02"},
    ]
    bioguide = candidate["legislative"]["bioguide_id"]
    inputs["current_voting_records"] = [
        {"bioguide_id": bioguide, "chamber": "house", "unity_score": 0, "cast_votes": 0}
    ]
    rows, gaps, report = incumbent_tables([candidate], inputs)
    assert rows[0]["religion_literal"] == "Refused"
    assert rows[0]["religion_status"] == "explicit_unknown_or_refused"
    assert report["coverage"]["party_unity_score"] == 1
    assert not [r for r in gaps if r["field"] == "party_unity_score"]
    assert next(r for r in gaps if r["field"] == "religion_literal")["status"] == (
        "explicit_unknown_or_refused"
    )


def test_real_incumbent_export_covers_every_qualified_incumbent_and_keeps_voting_vintages():
    candidates = read_rows(ROOT / "results/house/candidates.jsonl.gz")
    with (ROOT / "results/house/incumbents.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    expected = {
        r["candidate_id"] for r in candidates if r["legislative"]["house_incumbent"] is True
    }
    assert {r["candidate_id"] for r in rows} == expected
    assert all(
        all(r[k] for k in ("birth_clause", "education", "professional_history", "voting_evidence"))
        for r in rows
    )
    for row in rows:
        vote = json.loads(row["voting_evidence"])
        assert vote["last_unity_vote"] < row["voting_cutoff_exclusive"]
        if vote["unity_votes"] < 50:
            assert not row["party_unity_score"]
        assert row["current_congress"] == "119" and row["prior_congress"] == "118"
        if not row["military_service"]:
            assert "not_a_negative" in row["military_status"]
    kiley = next(r for r in rows if r["name"] == "Kevin Kiley")
    assert kiley["voting_source_party_code"] == "200"
    assert "not necessarily native ballot affiliation" in kiley["voting_record_scope"]
    ledger = json.loads((ROOT / "data/incumbent-disclosure-search.json").read_text())
    assert {(r["bioguide_id"], r["name"]) for r in ledger["unresolved"]} == {
        (r["bioguide_id"], r["name"])
        for r in rows
        if r["religion_status"] == "no_qualified_disclosure"
    }
