import csv
import json
from copy import deepcopy
from pathlib import Path

import pytest

from which_candidate.house_members import (
    build,
    incoming_profiles,
    incoming_service,
    qualified_infobox,
    wiki_new_members,
)
from which_candidate.storage import fingerprint

ROOT = Path(__file__).resolve().parents[1]


def candidate(name="Bob Example", district="02", winner=True):
    return {
        "candidate_id": "candidate-1",
        "contest_id": "contest-1",
        "state": "CA",
        "district": district,
        "name": name,
        "party": "Republican",
        "identity": {"fec_id": None},
        "legislative": {"bioguide_id": None, "house_incumbent": False},
        "native_flags_unverified": {"winner": winner},
        "source": {"id": "test-provider"},
        "source_updated_at_values": ["2026-11-13"],
        "background": {
            "official_candidate_profiles": [],
            "official_member_profiles": [],
            "dated_religion_observations": [],
            "member_authorized_biographies": [],
            "official_historian_observations": [],
        },
    }


def person():
    return {
        "id": {"bioguide": "E000001", "wikipedia": "Bob Example"},
        "name": {"first": "Robert", "last": "Example"},
        "terms": [
            {
                "type": "rep",
                "state": "CA",
                "party": "Republican",
                "start": "2025-01-03",
                "end": "2027-01-03",
            }
        ],
        "evidence": {"id": "test-service"},
    }


def test_wikipedia_roster_uses_qualified_article_link_and_preserves_uncertain_year():
    html = (
        "<table><tr><th>District</th><th>Representative</th>"
        "<th>Birth year</th><th>Prior background</th></tr>"
        "<tr><td>Alaska at-large</td><td><a href='https://en.wikipedia.org/wiki/"
        "Mark_Example_(politician)'>Mark Example</a> (R)<sup>[1]</sup></td>"
        "<td>1977/1978</td><td>City council</td></tr></table>"
    )
    row = wiki_new_members(html)[0]
    assert row["district"] == "AL" and row["state"] == "AK"
    assert row["wikipedia_url"].endswith("/Mark_Example_(politician)")
    assert row["birth_year_literal"] == "1977/1978"
    assert row["name"] == "Mark Example"
    with pytest.raises(ValueError, match="duplicate"):
        wiki_new_members(html.replace("</table>", html[html.index("<tr><td>") :]))


def test_wrong_person_birth_year_is_held_and_sensitive_infobox_labels_are_not_inferred():
    html = (
        "<table class='infobox biography'><tr><th>Born</th><td>1964-01-01</td></tr>"
        "<tr><th>Education</th><td>Example College<sup>2</sup></td></tr>"
        "<tr><th>Religion</th><td>Example religion</td></tr>"
        "<tr><th>Ethnicity</th><td>Example group</td></tr></table>"
    )
    fields, status = qualified_infobox({"birth_year_literal": "1972"}, html)
    assert fields == {} and "held" in status
    fields, status = qualified_infobox({"birth_year_literal": "1963/1964"}, html)
    assert fields == {"birth_literal": "1964-01-01", "education": "Example College"}
    assert "not_self_description" in status


def test_service_crosswalk_recovers_recorded_alias_but_requires_state_party_and_house():
    c, p = candidate(), person()
    links, people = incoming_service([c], [p], [])
    assert links[0]["bioguide_id"] == p["id"]["bioguide"]
    assert people == [p]
    for field, value in (("state", "NY"), ("party", "Democrat"), ("type", "sen")):
        changed = deepcopy(p)
        changed["terms"][0][field] = value
        assert incoming_service([c], [changed], []) == ([], [])
    changed = deepcopy(p)
    changed["id"]["wikipedia"] = "Unrelated Example"
    assert incoming_service([c], [changed], []) == ([], [])
    with pytest.raises(ValueError, match="Ambiguous"):
        incoming_service([c], [p, p], [])


def test_former_service_requires_fec_or_district_qualified_article_not_only_name():
    c, p = candidate(), person()
    p["terms"][0]["end"] = "2021-01-03"
    assert incoming_service([c], [p], []) == ([], [])
    roster = {
        "name": c["name"],
        "state": "CA",
        "district": "02",
        "party": c["party"],
        "wikipedia_url": "https://en.wikipedia.org/wiki/Bob_Example",
    }
    assert incoming_service([c], [p], [roster])[0][0]["bioguide_id"] == "E000001"
    roster["party"] = "Democratic"
    assert incoming_service([c], [p], [roster]) == ([], [])


def test_incoming_does_not_invent_winner_or_votes_and_joins_continuing_member_across_seats():
    a = candidate(district="01", winner=False)
    a["candidate_id"] = "candidate-unresolved"
    b = candidate()
    seats = [
        {
            "seat_id": "CA:01",
            "state": "CA",
            "district": "01",
            "bioguide_id": "E000001",
            "education": "Example College",
            "cast_yea_nay_votes": 123,
        },
        {"seat_id": "CA:02", "state": "CA", "district": "02", "bioguide_id": "O000001"},
    ]
    additions = {
        "incoming_service_crosswalks": [
            {"candidate_id": b["candidate_id"], "bioguide_id": "E000001"}
        ]
    }
    rows, _ = incoming_profiles([a, b], [], seats, additions, {"people": []})
    assert rows[0]["name"] is None and "unresolved" in rows[0]["status"]
    assert rows[1]["current_seat_id"] == "CA:01"
    assert rows[1]["education"] == "Example College"
    assert rows[1]["cast_yea_nay_votes"] == 123
    rows, _ = incoming_profiles([a, b], [], seats, {}, {"people": []})
    assert "cast_yea_nay_votes" not in rows[1]
    assert "not_zero" in rows[1]["current_federal_voting_applicability"]
    another = deepcopy(b)
    another["candidate_id"] = "candidate-conflicting-winner"
    rows, _ = incoming_profiles([a, b, another], [], seats, {}, {"people": []})
    assert rows[1]["name"] is None


def test_actual_member_build_preserves_all_seats_vacancies_provenance_and_historical_vintage(
    tmp_path,
):
    report = build(ROOT, tmp_path)
    assert report["voting_seats"] == 435
    assert report["occupied_members"] + report["vacant_seats"] == 435
    with (tmp_path / "house-119-seats.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    occupied = [r for r in rows if r["bioguide_id"]]
    vacant = [r for r in rows if not r["bioguide_id"]]
    assert len({r["member_id"] for r in occupied}) == 433
    assert {r["seat_id"] for r in vacant} == {"FL:20", "TX:23"}
    assert all(r["predecessor_bioguide_id"] and not r["name"] for r in vacant)
    assert all(
        all(
            r[k]
            for k in (
                "birth_clause",
                "education",
                "professional_history",
                "service_evidence",
                "biography_evidence",
                "cast_yea_nay_votes",
            )
        )
        for r in occupied
    )
    with (tmp_path / "missing-fields.csv").open() as stream:
        gaps = list(csv.DictReader(stream))
    assert all(r["member_id"] and r["seat_id"] for r in gaps)
    assert "historical_donor_score" not in {r["field"] for r in gaps}
    with (tmp_path / "house-120-seats.csv").open() as stream:
        incoming = list(csv.DictReader(stream))
    assert len(incoming) == 435
    assert all(
        r.get("education") or r.get("reported_prior_background") for r in incoming if r["name"]
    )
    assert all(not r.get("cast_yea_nay_votes") for r in incoming if not r.get("current_seat_id"))
    with (tmp_path / "incoming-missing-fields.csv").open() as stream:
        incoming_gaps = list(csv.DictReader(stream))
    assert {r["seat_id"] for r in incoming_gaps if r["field"] == "member_identity"} == {
        r["seat_id"] for r in incoming if not r["name"]
    }
    assert {r["seat_id"] for r in incoming_gaps if r["field"] == "current_119th_voting_record"} == {
        r["seat_id"] for r in incoming if r["name"] and not r["current_seat_id"]
    }
    assert sorted(
        r["name"] for r in incoming if r["entry_classification"] == "returning_former_House_member"
    ) == sorted(
        ["Jerry Carl", "Hilda Solis", "Melissa Bean", "Colin Allred", "Ben McAdams", "Elaine Luria"]
    )
    historical = json.loads((ROOT / "data/congressdata-members.json").read_text())
    with (tmp_path / "congressdata-latest.csv").open() as stream:
        reader = csv.DictReader(stream)
        assert set(historical["columns"]).issubset(reader.fieldnames)
        records = list(reader)
    assert all(float(r["year"]) <= 2024 and r["historical_model_ready"] == "False" for r in records)
    manifest = json.loads((ROOT / "results/members/manifest.json").read_text())
    for name, receipt in manifest["files"].items():
        assert fingerprint(tmp_path / name) == receipt, name
