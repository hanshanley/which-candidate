import csv
import json

import pytest

from which_candidate.candidate_acquisition import biography_links
from which_candidate.candidate_discovery import (
    assess_results,
    attach_repair,
    capture_extraction,
    directory_profile,
    finalize_repair,
    record_gap_review,
    record_roster_identity_review,
    record_search,
    review_directory_snapshot,
)
from which_candidate.candidate_research import background_field_coverage
from which_candidate.storage import fingerprint, write_json, write_rows


@pytest.mark.parametrize(
    "provider,method",
    [
        ("search", "public_search_provider_page_extraction"),
        ("web_fetch", "public_web_fetch_page_extraction"),
    ],
)
def test_extracted_pages_preserve_provider_provenance_without_coverage_credit(
    tmp_path, provider, method
):
    candidate = {
        "candidate_id": "1",
        "contest_id": "2026:house:KY:02:general",
        "name": "Test Candidate",
        "state": "KY",
        "district": "02",
        "party": "Independent",
    }
    manifest_path = tmp_path / "data/candidate-acquisition.json"
    manifest_path.parent.mkdir()
    write_json(manifest_path, {"sources": [], "candidates": []})
    sid = capture_extraction(
        tmp_path,
        candidate,
        url="https://guide.example/candidate",
        text="Test Candidate reports some college study, not a degree.",
        provider_reference="actual public-page extraction receipt",
        source_kind="public_voter_directory_biography",
        provider=provider,
    )
    manifest = json.loads(manifest_path.read_text())
    source = manifest["sources"][0]
    assert source["id"] == sid
    assert source["retrieval_method"] == method
    assert fingerprint(tmp_path / source["path"]) == {
        key: source[key] for key in ("bytes", "sha256")
    }
    assert not manifest["candidates"][0]["counted_as_background_coverage"]
    assert not manifest["candidates"][0]["facts_reviewed"]


@pytest.mark.parametrize(
    "name,url,title",
    [
        ("Aaron Gies", "https://www.aarons.com/", "Aaron's Furniture"),
        ("Dave Dawson", "https://dave.com/", "Dave Banking App"),
        ("James Pericola", "https://bible.example/james", "James in the Bible"),
    ],
)
def test_first_name_results_are_failed_discovery(name, url, title):
    result = assess_results({"name": name, "state": "NY"}, [{"url": url, "title": title}])
    assert result["status"] == "failed_irrelevant_or_empty_results"
    assert not result["relevant_results"]


def test_relevant_institution_result_is_only_a_lead():
    result = assess_results(
        {"name": "Aaron Gies", "state": "NY"},
        [{"url": "https://sbu.edu/academics/faculty/gies-aaron-m", "title": "Gies, Aaron M."}],
    )
    assert result["status"] == "contextual_leads_found"
    assert "factual identity and source review required" in result["qualification"]


def test_manually_rejected_identity_result_never_becomes_a_relevant_lead():
    rejected = {
        "url": "https://university.edu/faculty/gies-aaron",
        "title": "Aaron Gies faculty biography",
        "identity_review": "rejected",
        "rejection_reason": "Reviewed namesake, not the candidate.",
    }
    result = assess_results({"name": "Aaron Gies", "state": "NY"}, [rejected])
    assert result["status"] == "failed_irrelevant_or_empty_results"
    assert result["relevant_results"] == []
    assert result["rejected_results"] == [rejected]


@pytest.mark.parametrize("invalid", [None, "party", "fec_id", "website", "bytes", "context"])
def test_roster_identity_hold_does_not_invent_biography_or_hide_discovery_gaps(tmp_path, invalid):
    candidate = {
        "candidate_id": "1",
        "contest_id": "2026:house:NJ:01:general",
        "name": "No One",
        "state": "NJ",
        "district": "01",
        "party": "Write-In",
        "identity": {"fec_id": None},
        "campaign_websites": [],
        "votes": 1,
        "source": {"url": "https://election.example/returns", "sha256": "native-hash"},
    }
    if invalid == "party":
        candidate["party"] = "Independent"
    if invalid == "fec_id":
        candidate["identity"]["fec_id"] = "H123"
    if invalid == "website":
        candidate["campaign_websites"] = ["https://campaign.example/"]
    held = tmp_path / "results/house"
    held.mkdir(parents=True)
    roster = held / "candidates.jsonl.gz"
    write_rows(roster, [candidate])
    write_json(held / "manifest.json", {"files": {"candidates.jsonl.gz": fingerprint(roster)}})
    decision = {**candidate, "discovery_status": "retry_required", "attempts": []}
    if invalid == "context":
        decision["district"] = "02"
    path = tmp_path / "data/candidate-discovery-repair.json"
    path.parent.mkdir(parents=True)
    write_json(path, {"candidates": [decision]})
    if invalid == "bytes":
        write_rows(roster, [{**candidate, "votes": 2}])
    if invalid:
        with pytest.raises(ValueError):
            record_roster_identity_review(tmp_path, "1", disposition="Unidentified vote label.")
        assert "roster_identity_review" not in json.loads(path.read_text())["candidates"][0]
    else:
        result = record_roster_identity_review(
            tmp_path, "1", disposition="Unidentified vote label, not evidence about a person."
        )
        assert result["native_source"] == candidate["source"]
        assert result["votes"] == 1
        recorded = json.loads(path.read_text())["candidates"][0]
        assert recorded["discovery_status"] == "retry_required"
        assert not recorded["attempts"]
        assert "fields" not in result
        assert "No background observations" in result["qualification"]


def test_search_retry_preserves_irrelevant_attempt_then_records_contextual_lead(tmp_path):
    path = tmp_path / "data/candidate-discovery-repair.json"
    path.parent.mkdir()
    write_json(
        path,
        {
            "candidates": [
                {"candidate_id": "1", "name": "Aaron Gies", "state": "NY", "attempts": []}
            ]
        },
    )
    for title, url in (
        ("Aaron Furniture", "https://furniture.example/"),
        ("Aaron Gies faculty", "https://university.edu/faculty/gies"),
    ):
        record_search(
            tmp_path,
            "1",
            query="full name context",
            provider="test",
            results=[{"url": url, "title": title}],
        )
    person = json.loads(path.read_text())["candidates"][0]
    assert len(person["attempts"]) == 2
    assert person["attempts"][0]["status"] == "failed_irrelevant_or_empty_results"
    assert person["discovery_status"] == "leads_pending_source_review"


@pytest.mark.parametrize(
    "state,district,year", [("Virginia", 8, 2026), ("Maryland", 7, 2026), ("Maryland", 8, 2024)]
)
def test_public_directory_rejects_wrong_contest_even_when_name_matches(state, district, year):
    raw = (
        "Candidate Profile Cheryl Riley Candidate for U.S. House of Representatives - "
        f"{state} {district}th Congressional District in {year} General Election"
    ).encode()
    assert not directory_profile(raw, {"name": "Cheryl Riley", "state": "MD", "district": "08"})[
        "fields"
    ]


def test_public_directory_retains_school_listing_without_inventing_degree():
    raw = b"""
    Candidate Profile Cheryl Riley Candidate for U.S. House of Representatives -
    Maryland 8th Congressional District in 2026 General Election
    <section><h2>About Cheryl Riley</h2>
    <div>Professional Experience</div>
    <div class="mb-2 rounded-md">PR Firm, Founder (2001 - Present)</div>
    <div>Degrees</div><div class="mb-2 rounded-md">University of Maryland</div></section>
    <section>Policy support for universities</section>
    """
    result = directory_profile(raw, {"name": "Cheryl Riley", "state": "MD", "district": "08"})
    assert result["fields"] == {
        "education": ["University of Maryland"],
        "professional_history": ["PR Firm, Founder (2001 - Present)"],
    }
    assert "not graduation" in result["qualification"]


@pytest.mark.parametrize(
    "url",
    [
        "https://www.ballotready.org/people/cheryl-riley",
        "https://www.branch.vote/candidates/example",
        "https://www.wfyi.org/news/articles/example",
        "https://news.wttw.com/elections/2026/example",
    ],
)
def test_directory_organization_about_page_is_not_a_candidate_biography(url):
    assert biography_links(b'<a href="/about">About</a>', url) == []


def directory_review_fixture(root):
    candidate = {
        "candidate_id": "220409",
        "contest_id": "race",
        "name": "Test Candidate",
        "state": "IL",
        "district": "01",
        "party": "Independent",
        "baseline_has_observations": False,
        "baseline_missing_fields": ["education", "professional_history"],
        "reviewed_source_ids": [],
        "public_directory_lookup": {
            "extracted_profiles": [
                {
                    "source_id": "profile",
                    "identity_status": "name_and_2026_house_context_matched",
                    "fields": {
                        "education": ["Uncorroborated college credential"],
                        "professional_history": ["OBGYN", "Design business owner"],
                    },
                    "review_excluded_values": {"professional_history": ["OBGYN"]},
                }
            ]
        },
    }
    (root / "data").mkdir()
    write_json(root / "data/candidate-discovery-repair.json", {"candidates": [candidate]})
    write_json(root / "data/candidate-reviewed-backgrounds.json", {"profiles": []})
    return candidate


def test_snapshot_review_holds_questionable_claims_and_preserves_manual_review_markers(tmp_path):
    directory_review_fixture(tmp_path)
    path = tmp_path / "data/candidate-discovery-repair.json"
    review = tmp_path / "data/candidate-reviewed-backgrounds.json"
    assert review_directory_snapshot(tmp_path, fingerprint(path)["sha256"]) == {
        "new_reviewed_source_profiles": 1
    }
    accepted = json.loads(review.read_text())["profiles"][0]
    assert accepted["support"] == {"professional_history": ["Design business owner"]}
    assert not accepted["model_ready"]
    before = fingerprint(review)
    review_directory_snapshot(tmp_path, fingerprint(path)["sha256"])
    assert fingerprint(review) == before
    extracted = json.loads(path.read_text())["candidates"][0]["public_directory_lookup"][
        "extracted_profiles"
    ][0]
    assert extracted["reviewed_fields"] == ["professional_history"]
    assert extracted["fields"]["professional_history"] == ["OBGYN", "Design business owner"]


@pytest.mark.parametrize("change", ["hash", "identity", "exclusion"])
def test_snapshot_review_rejects_changed_or_unqualified_claims(tmp_path, change):
    candidate = directory_review_fixture(tmp_path)
    path = tmp_path / "data/candidate-discovery-repair.json"
    digest = fingerprint(path)["sha256"]
    profile = candidate["public_directory_lookup"]["extracted_profiles"][0]
    if change == "identity":
        profile["identity_status"] = "contest_not_qualified"
    elif change == "exclusion":
        profile["review_excluded_values"]["professional_history"] = ["Not in source"]
    else:
        candidate["name"] = "Changed Candidate"
    write_json(path, {"candidates": [candidate]})
    with pytest.raises(ValueError):
        review_directory_snapshot(
            tmp_path, digest if change == "hash" else fingerprint(path)["sha256"]
        )
    assert json.loads((tmp_path / "data/candidate-reviewed-backgrounds.json").read_text()) == {
        "profiles": []
    }


def test_repair_counts_people_separately_from_field_gains_and_rejects_stale_inputs(tmp_path):
    candidate = directory_review_fixture(tmp_path)
    candidate.pop("public_directory_lookup")
    candidate.update(baseline_has_observations=True, attempts=[])
    uncovered = {**candidate, "candidate_id": "2", "baseline_has_observations": False}
    path = tmp_path / "data/candidate-discovery-repair.json"
    write_json(
        path,
        {"baseline_profiles": {"sha256": "frozen"}, "candidates": [candidate, uncovered]},
    )
    write_json(
        tmp_path / "data/candidate-discovery-baseline.json",
        {
            "profile_fingerprint": {"sha256": "frozen"},
            "candidates": [
                {
                    "candidate_id": row["candidate_id"],
                    "has_observations": row["baseline_has_observations"],
                    **background_field_coverage(
                        [{"field": "prior_office", "value": "School board"}]
                        if row["baseline_has_observations"]
                        else []
                    ),
                }
                for row in [candidate, uncovered]
            ],
        },
    )
    held = tmp_path / "results/house"
    held.mkdir(parents=True)
    write_rows(held / "candidates.jsonl.gz", [candidate, uncovered])
    with (held / "background-observations.csv").open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=["candidate_id", "field", "value", "evidence"])
        writer.writeheader()
        for field in ("education", "professional_history", "prior_office"):
            writer.writerow(
                {"candidate_id": candidate["candidate_id"], "field": field, "value": '"Fact"'}
            )
    write_json(
        held / "manifest.json",
        {
            "files": {
                name: fingerprint(held / name)
                for name in ("candidates.jsonl.gz", "background-observations.csv")
            }
        },
    )
    result = finalize_repair(tmp_path)
    assert result["newly_covered_people"] == 0
    assert result["baseline_covered_people_with_new_fields"] == 1
    assert result["newly_filled_fields"]["education"] == 1
    assert result["newly_filled_fields"]["professional_history"] == 1
    assert result["remaining_uncovered_people"] == 1
    assert result["inadequate_discovery_still_requiring_retry"] == 1
    profiles = [
        {
            **row,
            "acquired_background_observations": (
                [
                    {"field": field, "value": "Fact"}
                    for field in ("education", "professional_history", "prior_office")
                ]
                if row["baseline_has_observations"]
                else []
            ),
        }
        for row in (candidate, uncovered)
    ]
    assert attach_repair(tmp_path, profiles) == result
    assert profiles[0]["background_discovery_repair"]["newly_covered"] is False
    assert profiles[1]["background_discovery_repair"]["discovery_status"] == "retry_required"
    profiles[1]["name"] = "Different Candidate"
    with pytest.raises(ValueError, match="identity or coverage"):
        attach_repair(tmp_path, profiles)
    profiles[1]["acquired_background_observations"] = [{"field": "education", "value": "New"}]
    with pytest.raises(ValueError, match="current coverage"):
        attach_repair(tmp_path, profiles)
    (held / "background-observations.csv").write_text("changed")
    with pytest.raises(ValueError, match="unchanged normalized"):
        finalize_repair(tmp_path)


@pytest.mark.parametrize(
    "invalid",
    [None, "owner", "fragment", "bytes", "pdf-valid", "pdf-missing", "pdf-range", "pdf-wrong"],
)
def test_reviewed_gap_pins_context_and_source_without_adding_facts(tmp_path, monkeypatch, invalid):
    candidate = directory_review_fixture(tmp_path)
    candidate["attempts"] = []
    repair = tmp_path / "data/candidate-discovery-repair.json"
    write_json(repair, {"candidates": [candidate]})
    ledger = tmp_path / "data/candidate-research-dispositions.json"
    write_json(ledger, {"candidates": [candidate]})
    original = tmp_path / "data/raw/candidate-backgrounds-20261115/gap.html"
    original.parent.mkdir(parents=True)
    original.write_text("<h1>Test Candidate</h1><p>Campaign priorities.</p>")
    source = {
        "id": "test-source",
        "path": str(original.relative_to(tmp_path)),
        "url": "https://campaign.example/about",
        "retrieved_at": "2026-11-15",
        **fingerprint(original),
    }
    if invalid and invalid.startswith("pdf-"):
        from types import SimpleNamespace

        source["media_type"] = "application/pdf"
        monkeypatch.setattr(
            "which_candidate.candidate_discovery.PdfReader",
            lambda path: SimpleNamespace(
                pages=[
                    SimpleNamespace(extract_text=lambda: "Test Candidate No response"),
                    SimpleNamespace(extract_text=lambda: "Another Candidate No response"),
                ]
            ),
        )
    write_json(
        tmp_path / "data/candidate-acquisition.json",
        {
            "candidates": [
                {**candidate, "source_ids": [] if invalid == "owner" else ["test-source"]}
            ],
            "sources": [source],
        },
    )
    if invalid == "bytes":
        original.write_text("changed")
    support = {"test-source": ["Absent"] if invalid == "fragment" else ["Test Candidate"]}
    if invalid and invalid.startswith("pdf-"):
        support = {
            "test-source": {
                "support": ["Test Candidate No response"],
                "pdf_pages": {
                    "pdf-valid": [1],
                    "pdf-missing": None,
                    "pdf-range": [0],
                    "pdf-wrong": [2],
                }[invalid],
            }
        }
    if invalid and invalid != "pdf-valid":
        with pytest.raises(ValueError):
            record_gap_review(
                tmp_path,
                candidate["candidate_id"],
                disposition="No requested fields on this page.",
                source_support=support,
            )
        assert "gap_review" not in json.loads(repair.read_text())["candidates"][0]
    else:
        result = record_gap_review(
            tmp_path,
            candidate["candidate_id"],
            disposition="No requested fields on this page.",
            source_support=support,
        )
        assert result["sources"][0]["sha256"] == source["sha256"]
        if invalid == "pdf-valid":
            assert result["sources"][0]["pdf_pages"] == [1]
        decision = json.loads(ledger.read_text())["candidates"][0]
        assert decision["reviewed_source_ids"] == ["test-source"]
        assert "fields" not in decision
