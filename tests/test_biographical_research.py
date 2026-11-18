import json
from copy import deepcopy

import pytest

from which_candidate import biographical_acquisition as acquisition
from which_candidate.biographical_research import (
    BASELINE,
    FAMILIES,
    JOURNAL,
    SCIENTIFIC_TRAITS,
    TRAITS,
    build,
    frozen_support,
    load_journals,
    research_states,
    validated_documents,
)
from which_candidate.storage import fingerprint, read_rows, write_json, write_rows


@pytest.fixture
def candidate():
    return {
        "candidate_id": "test-1",
        "contest_id": "2026:house:XX:01",
        "name": "Example Candidate",
        "state": "XX",
        "district": "01",
        "party": "Democratic",
        "campaign_websites": ["https://example.org"],
    }


@pytest.fixture
def document(candidate):
    return {
        **{
            k: candidate[k]
            for k in ("candidate_id", "name", "state", "district", "party", "contest_id")
        },
        "id": "test-bio",
        "url": "https://example.org/about",
        "family": "campaign",
        "identity_status": "verified",
        "identity_qualification": "Same candidate and campaign office, not a name-only join.",
        "identity_fragments": ["Example Candidate", "District 01"],
        "source_excerpts": ["Example Candidate. District 01. Born in 1976."],
        "traits_reviewed": list(TRAITS),
        "publication_date": None,
        "accessed_at": "2026-11-18",
        "original_bytes_acquired": False,
        "claims": [
            {
                "trait": "age",
                "value": {"birth_year": 1976},
                "factual_status": "partial",
                "precision": "birth_year_only",
                "source_fragment": "Born in 1976",
                "factual_reference_date": None,
            }
        ],
    }


def test_partial_facts_survive_without_invented_precision(candidate, document):
    _, claims = validated_documents({"documents": [document]}, {"test-1": candidate})
    claim = claims[("test-1", "age")][0]
    assert claim["value"] == {"birth_year": 1976}
    assert claim["factual_status"] == "partial"
    assert claim["analytical_eligibility"] == "not_promoted_to_frozen_scientific_models"
    assert claim["prediction_time_availability"] == "not_established_by_retrieval_date"
    assert not claim["original_bytes_acquired"]


def test_literal_identity_and_claim_validation(candidate, document):
    document["claims"][0]["supporting_fragments"] = ["Completed a master's degree"]
    with pytest.raises(ValueError, match="literal claim"):
        validated_documents({"documents": [document]}, {"test-1": candidate})
    document["claims"][0].pop("supporting_fragments")
    document["claims"][0]["source_fragment"] = "Age 50"
    with pytest.raises(ValueError, match="literal claim"):
        validated_documents({"documents": [document]}, {"test-1": candidate})
    document["claims"] = []
    document["identity_fragments"] = ["Different Person"]
    with pytest.raises(ValueError, match="literal identity"):
        validated_documents({"documents": [document]}, {"test-1": candidate})


def test_access_failure_does_not_complete_person_research(candidate):
    journal = {
        "searches": [
            {
                "candidate_id": "test-1",
                "family": "campaign",
                "query": "Example Candidate bio",
                "searched_at": "2026-11-18",
                "outcome": "access_failure",
                "underlying_urls": ["https://example.org/about"],
            }
        ],
        "completed_candidates": [
            {
                "candidate_id": "test-1",
                "actionable_leads_remaining": False,
                "extraction_review": "Campaign biography blocked.",
            }
        ],
    }
    with pytest.raises(ValueError, match="Unfinished research"):
        research_states(journal, {"test-1": candidate}, {})


def test_unreviewed_leads_prevent_completion(candidate, document):
    journal = {
        "searches": [
            {
                "candidate_id": "test-1",
                "family": family,
                "query": f"Example {family}",
                "searched_at": "2026-11-18",
                "outcome": "leads_found",
                "underlying_urls": ["https://example.org/unreviewed"],
            }
            for family in FAMILIES
        ],
        "completed_candidates": [
            {
                "candidate_id": "test-1",
                "actionable_leads_remaining": False,
                "extraction_review": "Reviewed source.",
            }
        ],
    }
    with pytest.raises(ValueError, match="Unreviewed underlying"):
        research_states(journal, {"test-1": candidate}, {"test-bio": document})
    for search in journal["searches"]:
        search["lead_dispositions"] = {
            "https://example.org/unreviewed": "Not yet opened; follow this lead next."
        }
    with pytest.raises(ValueError, match="Unreviewed underlying"):
        research_states(journal, {"test-1": candidate}, {"test-bio": document})


def test_later_followup_resolves_same_candidates_discovery_lead(candidate, document):
    url = "https://example.org/blocked"
    searches = [
        {
            "candidate_id": "test-1",
            "family": family,
            "query": f"Search {family}",
            "searched_at": "2026-11-18",
            "outcome": "no_qualifying_results",
        }
        for family in FAMILIES
    ]
    searches[0].update(outcome="leads_found", underlying_urls=[url])
    followup = searches[0] | {
        "candidate_id": "test-2",
        "query": "Follow selected original",
        "query_kind": "source_followup",
        "outcome": "access_failure",
        "lead_dispositions": {url: {"status": "access_failure", "reason": "HTTP 403"}},
    }
    journal = {
        "searches": [*searches, followup],
        "completed_candidates": [
            {
                "candidate_id": "test-1",
                "actionable_leads_remaining": False,
                "extraction_review": "Reviewed source; other originals checked or blocked.",
            }
        ],
    }
    candidates = {"test-1": candidate, "test-2": candidate | {"candidate_id": "test-2"}}
    with pytest.raises(ValueError, match="Unreviewed underlying"):
        research_states(journal, candidates, {"test-bio": document})
    followup["candidate_id"] = "test-1"
    assert research_states(journal, candidates, {"test-bio": document})[2] == {"test-1"}
    followup["underlying_urls"] = ["https://example.org/different"]
    with pytest.raises(ValueError, match="Unreviewed underlying"):
        research_states(journal, candidates, {"test-bio": document})


@pytest.mark.parametrize("unverified", ["query_text", "result_mapping"])
def test_unverified_queries_cannot_establish_searched_families(candidate, document, unverified):
    journal = {
        "searches": [
            {
                "candidate_id": "test-1",
                "family": family,
                "query": f"Historical description for {family}",
                "query_kind": (
                    "reconstructed_historical_description"
                    if unverified == "query_text"
                    else "search_query"
                ),
                "searched_at": "2026-11-18",
                "outcome": (
                    "no_qualifying_results"
                    if unverified == "query_text"
                    else "result_mapping_not_retained"
                ),
                "underlying_urls": [],
            }
            for family in FAMILIES
        ],
        "completed_candidates": [
            {
                "candidate_id": "test-1",
                "actionable_leads_remaining": False,
                "extraction_review": "Reviewed source.",
            }
        ],
    }
    with pytest.raises(ValueError, match="Unfinished research"):
        research_states(journal, {"test-1": candidate}, {"test-bio": document})


def test_unsearched_roster_and_partial_first_evidence(tmp_path, candidate, document):
    for folder in ("data", "results/house", "results/house-characteristics-v9"):
        (tmp_path / folder).mkdir(parents=True, exist_ok=True)
    second = {**candidate, "candidate_id": "test-2", "name": "Unsearched Candidate"}
    write_rows(tmp_path / "results/house/candidates.jsonl.gz", [candidate, second])
    baseline = []
    for person in (candidate, second):
        for trait in SCIENTIFIC_TRAITS:
            baseline.append(
                {
                    **person,
                    "trait": trait,
                    "status": "unknown",
                    "value": None,
                    "analysis_value": False if trait == "incumbency" else None,
                    "analysis_eligible": trait == "incumbency",
                    "factual_qualified": False,
                    "source_recorded_value": {},
                    "evidence": [],
                    "uncertainty": [],
                    "timing_status": "unresolved",
                    "coding_status": "unresolved",
                    "eligibility_reason": "No qualified value.",
                }
            )
    write_rows(tmp_path / "results/house-characteristics-v9/candidate-traits.jsonl.gz", baseline)
    write_json(tmp_path / BASELINE, {"protected_sha256": {}})
    retrievals = {"sources": {"https://example.org/about": {"status": "acquired"}}}
    write_json(tmp_path / "data/biographical-retrievals.json", retrievals)
    write_json(
        tmp_path / JOURNAL,
        {
            "documents": [document],
            "searches": [],
            "completed_candidates": [],
            "withheld_documents": [
                {
                    "id": "unverified-second-person",
                    "candidate_id": "test-2",
                    "url": "https://example.org/unverified",
                    "status": "identity_hold",
                    "reason": "A same-name source is not an identity bridge.",
                    "traits_pending_verification": ["age"],
                }
            ],
        },
    )
    summary = build(tmp_path)
    assert summary["research_status"] == {"in_progress": 1, "not_yet_researched": 1}
    assert summary["first_evidence_fields"] == 1
    assert summary["first_qualified_fields"] == 0
    assert summary["withheld_source_records"] == 1
    assert summary["trait_cells"] == 2 * len(SCIENTIFIC_TRAITS)
    assert not summary["acquisition_complete"]
    rows = read_rows(tmp_path / "results/biographical-research/candidate-trait-ledger.jsonl.gz")
    assert all(
        r["factual_status"] == "not_yet_researched" for r in rows if r["candidate_id"] == "test-2"
    )
    age = next(r for r in rows if r["candidate_id"] == "test-1" and r["trait"] == "age")
    assert age["factual_status"] == "partial_or_imprecise_evidence"
    held_age = next(r for r in rows if r["candidate_id"] == "test-2" and r["trait"] == "age")
    assert not held_age["new_claims"] and not held_age["new_first_evidence"]
    assert held_age["held_source_leads"][0]["status"] == "identity_hold"
    html = (tmp_path / "publication/biographical-research/report.html").read_text()
    assert "A same-name source is not an identity bridge." in html
    before = fingerprint(tmp_path / "publication/biographical-research/report.html")
    manifest_path = tmp_path / "results/biographical-research/manifest.json"
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    assert "data/biographical-retrievals.json" in manifest["inputs"]
    leads = tmp_path / "results/biographical-research/unreviewed-campaign-reading-leads.json"
    assert json.loads(leads.read_text()) == retrievals
    for name in manifest["files"]:
        (tmp_path / name).unlink()
    manifest_path.unlink()
    build(tmp_path)
    assert fingerprint(tmp_path / "publication/biographical-research/report.html") == before
    assert manifest_path.read_bytes() == manifest_bytes


def test_prior_nested_documents_and_failed_attempts_are_reused(tmp_path):
    cache = tmp_path / "artifacts/characteristics-v9/worker"
    cache.mkdir(parents=True)
    (tmp_path / "data").mkdir()
    original = cache / "old"
    original.write_bytes(b"<h1>Retained original</h1>")
    write_json(
        cache / "retrievals.json",
        [
            {
                "id": "old",
                "url": "https://example.org/about",
                "status": "acquired",
                "retrieved_at": "2026-11-17",
                **fingerprint(original),
            },
            {
                "id": "blocked",
                "url": "https://blocked.example.org",
                "retrieved_at": "2026-11-17",
                "status": "failed_attempt_not_evidence",
                "error": "HTTP 403",
            },
        ],
    )
    index = acquisition.prior_index(tmp_path)
    assert index["https://example.org/about"]["status"] == "retained_original"
    assert index["https://example.org/about"]["network_attempts"] == 0
    assert index["https://blocked.example.org"]["status"] == "retained_access_failure"
    assert list(
        acquisition.source_records(
            {
                "documents": [
                    {
                        "url": "https://example.org/about",
                        **fingerprint(original),
                    }
                ]
            }
        )
    )


def test_duplicate_factual_claims_within_document_are_rejected(candidate, document):
    document["claims"].append(dict(document["claims"][0]))
    with pytest.raises(ValueError, match="literal claim"):
        validated_documents({"documents": [document]}, {"test-1": candidate})


def test_batch_journals_merge_without_loading_baseline_as_evidence(tmp_path, document):
    (tmp_path / "data").mkdir()
    empty = {"documents": [], "searches": [], "completed_candidates": []}
    write_json(tmp_path / JOURNAL, empty)
    write_json(tmp_path / BASELINE, {"protected_sha256": {}})
    path = "data/biographical-research-batch.json"
    write_json(tmp_path / path, {**empty, "documents": [document]})
    journal, inputs = load_journals(tmp_path)
    assert journal["documents"] == [document]
    assert inputs == [JOURNAL, path]
    write_json(tmp_path / path, {"documents": []})
    with pytest.raises(ValueError, match="Missing research journal sections"):
        load_journals(tmp_path)


def test_duplicate_original_is_rejected_across_batch_reviews(candidate, document):
    second = deepcopy(document)
    second["id"] = "different-review-id"
    second["url"] = "http://www.example.org/about/#biography"
    with pytest.raises(ValueError, match="Duplicate document review"):
        validated_documents(
            {"documents": [document, second]},
            {"test-1": candidate},
        )


def test_retained_excerpt_budget_is_per_reviewed_original(candidate, document):
    document["source_excerpts"].append(" ".join(["extra"] * 26))
    with pytest.raises(ValueError, match="Excessive retained source quotation"):
        validated_documents({"documents": [document]}, {"test-1": candidate})


def test_detail_conflict_preserves_supported_narrow_fact(candidate, document):
    document["source_excerpts"] = ["Example Candidate. District 01. Served in the Navy."]
    document["claims"] = [
        {
            "trait": "military",
            "value": {"served": True},
            "factual_status": "qualified",
            "precision": "service affirmative, unresolved start year",
            "source_fragment": "Served in the Navy",
            "factual_reference_date": None,
            "unresolved_details": ["Sources disagree about the start year."],
        }
    ]
    _, claims = validated_documents({"documents": [document]}, {"test-1": candidate})
    claim = claims[("test-1", "military")][0]
    assert claim["factual_status"] == "qualified"
    assert claim["unresolved_details"] == ["Sources disagree about the start year."]


def test_frozen_support_sums_disjoint_performance_groups(tmp_path):
    folder = tmp_path / "results/house-characteristics-v9"
    folder.mkdir(parents=True)
    (folder / "coverage-by-party-and-incumbency.csv").write_text(
        "trait,party,baseline_incumbency_group,performance_eligible,"
        "fitted_after,full_fit_prediction_supported\n"
        "religion,Democratic,incumbent,True,100,99\n"
        "religion,Democratic,nonincumbent,True,23,23\n"
        "religion,Democratic,unknown_incumbency,False,0,0\n"
    )
    support = frozen_support(tmp_path)
    assert support[("religion", "Democratic", "all")] == {
        "fitted_unchanged": 123,
        "prediction_supported_unchanged": 122,
    }
    assert support[("religion", "all", "nonincumbent")]["fitted_unchanged"] == 23
