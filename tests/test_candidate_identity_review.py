import pytest

from which_candidate import candidate_identity_review
from which_candidate.candidate_identity_review import anchor, review_alias, review_lead
from which_candidate.features import FeatureSources
from which_candidate.storage import write_json, write_rows


@pytest.fixture
def crosswalk():
    sources = FeatureSources({"sources": []}, None)
    person = {
        "id": {"bioguide": "A1", "fec": ["S6AA00001", "H2AA00001"]},
        "name": {"first": "Henry", "last": "Example", "nickname": "Hank"},
        "terms": [{"state": "AA"}],
        "evidence": {"source_id": "legislators", "json_pointer": "/0"},
    }
    sources.people["A1"] = person
    sources.fec["S6AA00001"].add("A1")
    sources.fec["H2AA00001"].add("A1")
    return sources


@pytest.fixture
def query():
    return {
        "contest_id": "2026:senate:AA",
        "D_name": "Hank Example",
        "D_fec_id": "S6AA00001",
        "state": "AA",
        "bioguide_id": "A1",
    }


def test_anchor_requires_unique_stable_id_and_consistent_frozen_identity(crosswalk, query):
    assert anchor(query, crosswalk)[0]["id"]["bioguide"] == "A1"
    assert anchor({**query, "bioguide_id": "B2"}, crosswalk)[0] is None
    assert anchor({**query, "state": "BB"}, crosswalk)[0] is None
    crosswalk.fec["S6AA00001"].add("B2")
    assert anchor(query, crosswalk)[0] is None


def test_alias_review_uses_literal_crosswalk_not_assumed_nicknames(crosswalk, query):
    donor = {
        "name_screen": "manual_alias_review_required; exact_FEC_match_not_discarded",
        "source_rows": [2],
        "bonica_rid": "person1",
        "cycle": 2024,
    }
    row = {
        "Cand.ID": query["D_fec_id"],
        "state": "AA",
        "party": "100",
        "recipient.type": "cand",
        "bonica.rid": "person1",
        "cycle": "2024",
        "ffname": "henry",
        "lname": "example",
    }
    person = crosswalk.people["A1"]
    assert (
        review_alias(query, donor, {2: row}, person, crosswalk)["status"]
        == "independently_corroborated_alias"
    )
    held = review_alias(query, donor, {2: {**row, "ffname": "harry"}}, person, crosswalk)
    assert held["status"].startswith("unresolved")
    assert not held["model_ready"]
    with pytest.raises(ValueError, match="selected source identity"):
        review_alias(query, donor, {2: {**row, "Cand.ID": "wrong"}}, person, crosswalk)


def test_cross_office_bridge_requires_two_unique_fec_links(crosswalk, query):
    lead = {
        "contest_id": query["contest_id"],
        "target_fec_id": query["D_fec_id"],
        "target_name": query["D_name"],
        "state": "AA",
        "source_candidate_id": "H2AA00001",
        "source_name": "example, henry",
        "model_ready": False,
    }
    person = crosswalk.people["A1"]
    result = review_lead(query, lead, person, crosswalk)
    assert result["identity_review_status"] == "independent_FEC_Bioguide_FEC_bridge"
    assert not result["model_ready"]
    assert review_lead(query, lead, None, crosswalk)["identity_review_status"].startswith("held")
    crosswalk.fec["H2AA00001"].add("B2")
    assert review_lead(query, lead, person, crosswalk)["identity_review_status"].startswith("held")
    with pytest.raises(ValueError, match="target candidate"):
        review_lead(query, {**lead, "state": "BB"}, person, crosswalk)


def test_complete_build_retains_unknowns_and_rejects_missing_or_misattributed_contests(
    tmp_path, monkeypatch, crosswalk, query
):
    frozen = [
        {
            "contest_id": f"2026:house:AA:{number:02}",
            "year": 2026,
            "chamber": "house",
            "state": "AA",
            "D_name": None,
            "D_fec_id": None,
        }
        for number in range(470)
    ]
    frozen[0] = {**frozen[0], **query}
    expanded = [
        {
            "contest_id": row["contest_id"],
            "name": row["D_name"],
            "fec_id": row["D_fec_id"],
            "state": "AA",
            "dime": {},
            "dime_cross_office_leads": [],
        }
        for row in frozen
    ]
    paths = [tmp_path / name for name in ("frozen.gz", "expanded.gz", "donors.gz")]
    manifest = tmp_path / "manifest.json"
    write_json(manifest, {"sources": []})
    write_rows(paths[0], frozen)
    write_rows(paths[1], expanded)
    write_rows(paths[2], [])
    monkeypatch.setattr(candidate_identity_review, "load_crosswalk", lambda path: (crosswalk, []))
    output = tmp_path / "output"
    summary = candidate_identity_review.build(*paths, manifest, output)
    assert summary["contests"] == 470
    result = candidate_identity_review.read_queries(output / "candidate-identity-queries.jsonl.gz")
    assert len(result) == 470
    assert sum(row["name"] is None for row in result) == 469
    before = {path.name: path.read_bytes() for path in output.iterdir()}
    candidate_identity_review.build(*paths, manifest, output)
    assert before == {path.name: path.read_bytes() for path in output.iterdir()}
    write_rows(paths[1], expanded[:-1])
    with pytest.raises(ValueError, match="exactly the frozen"):
        candidate_identity_review.build(*paths, manifest, output)
    write_rows(paths[1], [{**expanded[0], "name": "Another Person"}, *expanded[1:]])
    with pytest.raises(ValueError, match="conflicts with frozen identity"):
        candidate_identity_review.build(*paths, manifest, output)
