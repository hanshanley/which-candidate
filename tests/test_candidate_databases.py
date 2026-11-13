import csv
import gzip
import json

import pytest

from which_candidate.candidate_databases import (
    _read_receipts,
    build,
    cawp_winner_classifications,
    cross_office_leads,
    religion_observations,
    reviewed_descriptions,
    select_campaignview,
    select_cawp,
    select_dime,
    snapshot,
)
from which_candidate.storage import fingerprint, write_json


def query(**changes):
    return {
        "D_fec_id": "H4CA01001",
        "state": "CA",
        "year": 2026,
        "chamber": "house",
        "contest_id": "2026:house:CA:01",
        "D_candidate_election_id": "candidate-1",
        "D_name": "A Candidate",
        "eligible": True,
        "D_incumbent": False,
        "won_two_party_comparison": False,
        "nokken_poole_dim1": None,
        **changes,
    }


def dime(**changes):
    return {
        "Cand.ID": "H4CA01001",
        "state": "CA",
        "party": "100",
        "recipient.type": "cand",
        "cycle": "2024",
        "bonica.rid": "cand1",
        "recipient.cfscore.dyn": "-0.75",
        "num.givers": "80",
        "seat": "federal:house",
        "ffname": "A",
        "lname": "Candidate",
        "source_row": 1,
        **changes,
    }


def test_donation_ideology_covers_losing_nonincumbent_without_vote_score():
    selected = select_dime(query(), [dime()])
    assert selected["score"] == -0.75
    assert selected["cycle"] == 2024
    assert selected["source_rows"] == [1]


@pytest.mark.parametrize(
    "change,status",
    [
        ({"party": "200"}, "state_party_type_or_vintage_conflict"),
        ({"state": "NY"}, "state_party_type_or_vintage_conflict"),
        ({"cycle": "2026"}, "state_party_type_or_vintage_conflict"),
        ({"recipient.type": "comm"}, "state_party_type_or_vintage_conflict"),
        ({"recipient.cfscore.dyn": "NA"}, "latest_cycle_score_missing"),
        ({"recipient.cfscore.dyn": "nan"}, "latest_cycle_score_missing"),
        ({"recipient.cfscore.dyn": "inf"}, "latest_cycle_score_missing"),
        ({"cycle": "2024.5"}, "state_party_type_or_vintage_conflict"),
        ({"Cand.ID": "H4NY01001"}, "state_party_type_or_vintage_conflict"),
    ],
)
def test_dime_fails_closed(change, status):
    result = select_dime(query(), [dime(**change)])
    assert result["status"] == status
    assert result["score"] is None


def test_latest_missing_or_conflicting_score_never_falls_back_to_old_score():
    old = dime(cycle="2022")
    assert select_dime(query(), [old, dime(**{"recipient.cfscore.dyn": ""})])["score"] is None
    assert (
        select_dime(query(), [dime(), dime(**{"recipient.cfscore.dyn": "-0.2"})])["status"]
        == "conflicting_latest_cycle_scores"
    )
    assert (
        select_dime(query(), [dime(), dime(**{"bonica.rid": "other-person"})])["status"]
        == "conflicting_source_person_ids"
    )
    assert select_dime(query(), [dime(), dime(cycle="2026")])["cycle"] == 2024


def test_missing_fec_is_not_replaced_with_name_matching():
    assert select_dime(query(D_fec_id=None), [dime()])["status"] == "missing_target_fec_id"


def test_old_office_name_match_is_only_a_review_lead(tmp_path):
    rows = [
        dime(**{"Cand.ID": "CA-state123", "seat": "state:lower"}),
        dime(**{"Cand.ID": "CA-state124", "state": "NY"}),
        dime(**{"Cand.ID": "CA-state125", "party": "200"}),
        dime(**{"Cand.ID": "CA-state126", "cycle": "2026"}),
        dime(),
    ]
    path = tmp_path / "recipients.csv.gz"
    with gzip.open(path, "wt") as handle:
        writer = csv.DictWriter(handle, rows[0])
        writer.writeheader()
        writer.writerows(rows)
    leads = cross_office_leads(path, [query()])
    records = leads[query()["contest_id"]]
    assert len(records) == 1
    assert records[0]["source_candidate_id"] == "CA-state123"
    assert not records[0]["model_ready"]
    assert select_dime(query(), rows[:1])["score"] is None


def test_cawp_contextual_match_is_not_an_inferred_gender_or_race_label():
    record = {
        "State": "CA",
        "Party": "D",
        "Office": "U.S. Rep.",
        "Dist.": "AL",
        "First Name": "A",
        "Last Name": "Candidate",
    }
    target = query(district="00")
    matched = select_cawp(target, [record])
    assert len(matched["records"]) == 1
    assert not matched["identity_label_promoted"]
    assert not matched["race_field_available"]
    assert select_cawp(target, [])["absence_is_not_male"]
    assert select_cawp(target, [{**record, "Dist.": "2"}])["records"] == []
    assert select_cawp(target, [{**record, "Party": "R"}])["records"] == []
    assert select_cawp(target, [record, record])["status"] == "ambiguous_contextual_matches"


def test_dated_religion_survives_office_change_without_imputing_current_affiliation(
    tmp_path, monkeypatch
):
    person = {
        "id": {"bioguide": "A000001", "fec": ["H4CA01001"]},
        "name": {"first": "Alice", "last": "Candidate"},
        "terms": [{"type": "rep", "state": "CA", "start": "2020-01-03", "end": "2025-01-03"}],
    }
    people = tmp_path / "people.json"
    write_json(people, [person])
    pew = tmp_path / "pew.pdf"
    pew.write_bytes(b"fixture; parser stubbed")
    manifest = tmp_path / "research.json"
    write_json(
        manifest,
        {
            "sources": [
                {"id": "people", "path": people.name, "kind": "legislators", **fingerprint(people)},
                {"id": "pew", "path": pew.name, "kind": "pew_member_religion", **fingerprint(pew)},
            ]
        },
    )
    observations = [
        {
            "name": "Alice Candidate",
            "state": "CA",
            "chamber": "house",
            "publication_date": year + "-01-03",
            "source_id": year,
            "religion_category": religion,
        }
        for year, religion in [
            ("2023", "catholic"),
            ("2025", "unknown"),
            ("2027", "protestant"),
        ]
    ]
    monkeypatch.setattr(
        "which_candidate.candidate_databases.read_pew", lambda path, spec: observations
    )
    target = query(
        D_name="Alice Candidate",
        bioguide_id="A000001",
        chamber="senate",
        election_date="2026-11-03",
        religion_category="unknown",
    )
    result, _ = religion_observations([target], manifest)
    records = result[target["contest_id"]]
    assert [r["religion_category"] for r in records] == ["catholic", "unknown"]
    assert target["religion_category"] == "unknown"
    assert all(r["chamber"] == "house" for r in records)
    unmatched, _ = religion_observations([{**target, "bioguide_id": None}], manifest)
    assert unmatched[target["contest_id"]] == []


def campaign():
    index = {
        "uid": "a-candidate-ca-democrat",
        "FECCandID": "H4CA01001",
        "cand_party": "Democrat",
        "state_postal": "CA",
        "years": [2022],
    }
    detail = {
        "uid": index["uid"],
        "FECCandID": {"1": index["FECCandID"]},
        "issues": {
            "-2022": {
                "header": "Candidate Biography",
                "year": 2022,
                "text": "Opposes the Muslim ban and supports Jewish neighbors.",
            }
        },
    }
    return index, detail


def test_campaign_issue_references_are_not_sensitive_identity_labels():
    index, detail = campaign()
    result = select_campaignview(query(), [index], {index["uid"]: detail})
    assert result["historical_biography_available"]
    assert not result["current_2026_biography"]
    assert "religion" not in result
    assert "text" not in result["records"][0]["issues"][0]
    detail["FECCandID"] = {"1": "H4NY01001"}
    result = select_campaignview(query(), [index], {index["uid"]: detail})
    assert result["held"][0]["reason"] == "detail_identity_conflict"
    assert not result["historical_biography_available"]


def test_reviewed_description_requires_pinned_quote_and_identity(tmp_path):
    source = tmp_path / "campaignview.json"
    _, detail = campaign()
    detail["issues"]["-2022"]["text"] = "I am a Christian. My grandparents were Baptist."
    write_json(source, detail)
    receipts = {
        "sources": [
            {
                "id": "profile",
                "file": source.name,
                "acquired_at": "2026-11-13",
                **fingerprint(source),
            }
        ]
    }
    annotation = {
        "name": "A Candidate",
        "fec_id": "H4CA01001",
        "state": "CA",
        "chamber": "house",
        "source_id": "profile",
        "campaignview_issue_key": "-2022",
        "quote": "I am a Christian.",
        "source_year_label": 2022,
        "religion_category": "christian_unspecified",
    }
    annotations = tmp_path / "annotations.json"
    write_json(annotations, {"observations": [annotation]})
    result = reviewed_descriptions([query()], annotations, receipts, tmp_path)[0]
    assert result["status"] == "verified_subject_and_pinned_self_description"
    assert result["religion_category"] == "christian_unspecified"
    assert result["eligible_pre_election_predictor"] is False
    held = reviewed_descriptions([query(D_fec_id="H4NY01001")], annotations, receipts, tmp_path)[0]
    assert held["status"] == "unmatched_subject_identity"
    annotation["quote"] = "I am an atheist."
    write_json(annotations, {"observations": [annotation]})
    with pytest.raises(ValueError, match="not found"):
        reviewed_descriptions([query()], annotations, receipts, tmp_path)


def test_optional_source_denial_does_not_stop_independent_acquisitions(tmp_path, monkeypatch):
    import urllib.error

    monkeypatch.setattr(
        "which_candidate.candidate_databases.ROOT_SOURCES",
        (
            ("denied", "https://example.org/denied", "denied.html"),
            ("campaignview-candidates", "https://example.org/index", "index.json"),
            ("other", "https://example.org/other", "other.html"),
        ),
    )

    def fetch(url):
        if url.endswith("/denied"):
            raise urllib.error.HTTPError(url, 403, "Forbidden", {}, None)
        return (b"[]" if url.endswith("/index") else b"public document"), url

    monkeypatch.setattr("which_candidate.candidate_databases._fetch", fetch)
    receipts = snapshot(tmp_path / "cache", tmp_path / "sources.json", [])
    assert {row["id"] for row in receipts["sources"]} == {"campaignview-candidates", "other"}
    assert receipts["failures"][0]["id"] == "denied"
    assert receipts["failures"][0]["http_status"] == 403
    assert receipts["failures"][0]["disposition"] == "not_bypassed"


def test_cawp_individual_race_requires_person_rows_and_preserves_multiple_identities(tmp_path):
    path = tmp_path / "public-embed.html"
    data = {
        "elements": {
            "content": {
                "content": {
                    "entities": {
                        "person-table": {
                            "props": {
                                "chartData": {
                                    "data": [
                                        [
                                            [
                                                "First Name",
                                                "Last Name",
                                                "State",
                                                "Party",
                                                "District",
                                                "Racial Identification",
                                            ],
                                            [
                                                {"value": "A"},
                                                {"value": "Candidate"},
                                                "CA",
                                                "D",
                                                "1",
                                                "Black, Latina",
                                            ],
                                        ]
                                    ]
                                }
                            }
                        },
                        "aggregate": {
                            "props": {"chartData": {"data": [[["Race", "Count"], ["White", 20]]]}}
                        },
                    }
                }
            }
        }
    }
    path.write_text("window.infographicData = " + json.dumps(data) + "; neverExecute();")
    rows = cawp_winner_classifications(path, "public-embed", "house")
    assert len(rows) == 1
    assert rows[0]["Racial Identification"] == "Black, Latina"
    assert rows[0]["source_scope"] == "women_nonincumbent_winners_only"
    assert rows[0]["eligible_pre_election_predictor"] is False
    assert rows[0]["identity_label_promoted"] is False
    assert len(select_cawp(query(district="01"), rows)["records"]) == 1
    assert not select_cawp(query(district="02"), rows)["records"]
    path.write_text("<html>No dataset</html>")
    with pytest.raises(ValueError, match="embedded data not found"):
        cawp_winner_classifications(path, "public-embed", "house")


def test_complete_offline_build_retains_unmatched_contests_and_detects_tampering(
    tmp_path, monkeypatch
):
    def no_network(*args, **kwargs):
        raise AssertionError("Replay attempted network access")

    monkeypatch.setattr("socket.socket.connect", no_network)
    cache, out = tmp_path / "cache", tmp_path / "out"
    cache.mkdir()
    source = dime()
    with gzip.open(cache / "dime-recipients.csv.gz", "wt") as handle:
        writer = csv.DictWriter(handle, source)
        writer.writeheader()
        writer.writerow(source)
    index, detail = campaign()
    write_json(cache / "campaignview-candidates.json", [index])
    write_json(cache / f"campaignview-{index['uid']}.json", detail)
    (cache / "hilbig-release-roster.csv").write_text(
        "cand_id,state,party,captured,website_url\nH4CA01001,CA,D,True,https://example.org\n"
    )
    manifest = tmp_path / "manifest.json"
    write_json(
        manifest,
        {
            "sources": [
                {
                    "id": "hilbig-roster"
                    if path.name == "hilbig-release-roster.csv"
                    else path.name.split(".")[0],
                    "file": path.name,
                    **fingerprint(path),
                }
                for path in sorted(cache.iterdir())
            ]
        },
    )
    targets = [
        query(),
        query(
            D_fec_id=None,
            D_name=None,
            contest_id="other",
            eligible=False,
            won_two_party_comparison=True,
        ),
    ]
    summary = build(cache, manifest, targets, out)
    assert summary["coverage"]["all"]["contests"] == 2
    assert summary["coverage"]["nonincumbent"]["dime_score"] == 1
    assert summary["coverage"]["lost_two_party"]["historical_campaign_bio"] == 1
    assert "won_two_party" not in summary["coverage"]
    assert summary["coverage"]["outcome_unavailable"]["contests"] == 1
    assert summary["coverage"]["eligible"]["contests"] == 1
    rows = [json.loads(line) for line in gzip.open(out / "candidate-queries.jsonl.gz", "rt")]
    assert len(rows) == 2
    assert rows[1]["dime"]["status"] == "no_named_nominee"
    before = {path.name: path.read_bytes() for path in out.iterdir()}
    build(cache, manifest, targets, out)
    assert before == {path.name: path.read_bytes() for path in out.iterdir()}
    (cache / "campaignview-candidates.json").write_text("[]")
    with pytest.raises(ValueError, match="Cached source changed"):
        _read_receipts(manifest, cache)
