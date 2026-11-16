import hashlib
import json

import pytest
from pypdf import PdfWriter

from which_candidate.democratic_research import ingest, validate
from which_candidate.house_backgrounds import background_observations
from which_candidate.reviewed_backgrounds import reviewed_inputs
from which_candidate.storage import fingerprint, write_json


def context():
    return {
        "candidate_id": "1",
        "contest_id": "2026:house:AA:01:general",
        "name": "Test Candidate",
        "state": "AA",
        "district": "01",
        "party": "Democratic",
    }


def setup_root(tmp_path, *, source_text=None, inline=False):
    candidate = context()
    data = tmp_path / "data"
    artifacts = tmp_path / "artifacts/democratic-background-research"
    data.mkdir()
    artifacts.mkdir(parents=True)
    write_json(
        data / "democratic-background-gap-baseline.json",
        {
            "candidates": [{**candidate, "target_fields": ["professional_history"]}],
        },
    )
    write_json(
        data / "candidate-discovery-repair.json",
        {"candidates": [{**candidate, "attempts": [], "discovery_status": "retry_required"}]},
    )
    write_json(data / "candidate-acquisition.json", {"candidates": [], "sources": []})
    write_json(
        data / "candidate-research-dispositions.json",
        {"candidates": [{**candidate, "reviewed_source_ids": []}]},
    )
    write_json(
        data / "candidate-reviewed-backgrounds.json",
        {"qualification": "Reviewed source.", "profiles": []},
    )
    source_text = source_text or (
        "Test Candidate biography for AA district 01. Worked as an engineer at Example Corp."
    )
    held = artifacts / "candidate.html"
    held.write_text(f"<html><body>{source_text}</body></html>")
    source = {
        "url": "https://example.test/candidate",
        "source_kind": "official campaign biography",
        "retrieved_at": "2026-11-15T20:00:00-05:00",
        "publication_date": None,
        "provider_reference": "provider:result-1",
        "retrieval_method": "held_public_original",
        "text_or_local_path": (
            "proposal paraphrase, not provider text"
            if inline
            else "artifacts/democratic-background-research/candidate.html"
        ),
        "fields": {"professional_history": ["Engineer, Example Corp."]},
        "support": {"professional_history": ["Worked as an engineer at Example Corp."]},
        "identity_support": ["Test Candidate", "AA district 01"],
        "qualification": "Campaign self-report; compensation not established.",
        "identity_match_status": "matched_exact_candidate",
    }
    proposal = {
        "candidates": [
            {
                **candidate,
                "target_fields": ["professional_history"],
                "searches": [
                    {
                        "query": '"Test Candidate" AA biography',
                        "provider": "test search",
                        "provider_reference": "search:1",
                        "results": [
                            {
                                "url": "https://university.test/test-candidate",
                                "title": "Test Candidate faculty biography",
                                "rejection_reason": "Reviewed namesake, not this candidate.",
                            }
                        ],
                    }
                ],
                "sources": [source],
                "remaining_fields": [],
                "limitations": ["Employer dates were not established."],
                "rejected_matches": [
                    {
                        "url": "https://university.test/test-candidate",
                        "reason": "Reviewed namesake.",
                    }
                ],
            }
        ]
    }
    proposal_path = artifacts / "professional-proposals.json"
    write_json(proposal_path, proposal)
    return proposal_path, held


def test_validate_only_requires_actual_source_and_does_not_mutate_shared_data(tmp_path):
    proposal, _ = setup_root(tmp_path, inline=True)
    before = {path: path.read_bytes() for path in (tmp_path / "data").iterdir() if path.is_file()}
    with pytest.raises(ValueError, match="proposal paraphrases cannot become evidence"):
        ingest(tmp_path, [proposal.relative_to(tmp_path)], validate_only=True)
    assert before == {path: path.read_bytes() for path in before}
    assert not (tmp_path / "data/democratic-background-research.json").exists()
    assert not (tmp_path / "data/raw").exists()


def test_long_proposal_prose_is_rejected_as_evidence_not_a_filesystem_error(tmp_path):
    proposal, _ = setup_root(tmp_path)
    data = json.loads(proposal.read_text())
    data["candidates"][0]["sources"][0]["text_or_local_path"] = "Unheld prose\n" * 100
    write_json(proposal, data)
    with pytest.raises(ValueError, match="proposal paraphrases cannot become evidence"):
        validate(tmp_path, [proposal.relative_to(tmp_path)])


def test_research_must_account_for_every_pinned_target(tmp_path):
    proposal, _ = setup_root(tmp_path)
    write_json(proposal, {"candidates": []})
    with pytest.raises(ValueError, match="omit pinned candidates"):
        validate(tmp_path, [proposal.relative_to(tmp_path)])


def test_validation_rejects_missing_support_identity_and_non_target_fields(tmp_path):
    proposal, held = setup_root(tmp_path)
    held.write_text("<html><body>Unrelated person.</body></html>")
    with pytest.raises(ValueError, match="Identity anchor absent"):
        validate(tmp_path, [proposal.relative_to(tmp_path)])
    proposal_data = json.loads(proposal.read_text())
    proposal_data["candidates"][0]["sources"][0]["fields"] = {"education": ["Unrelated degree"]}
    proposal_data["candidates"][0]["sources"][0]["support"] = {"education": ["Unrelated degree"]}
    write_json(proposal, proposal_data)
    with pytest.raises(ValueError, match="non-target field"):
        validate(tmp_path, [proposal.relative_to(tmp_path)])


def test_ingest_pins_original_registers_rejected_search_and_merges_annotations(tmp_path):
    proposal, held = setup_root(tmp_path)
    digest = hashlib.sha256(held.read_bytes()).hexdigest()
    source_id = f"candidate-bio-1-{digest[:20]}"
    review_path = tmp_path / "data/candidate-reviewed-backgrounds.json"
    write_json(
        review_path,
        {
            "qualification": "Reviewed source.",
            "profiles": [
                {
                    **context(),
                    "source_id": source_id,
                    "fields": {"prior_office": ["School board member"]},
                    "support": {"prior_office": ["School board"]},
                    "source_kind": "official_previous_office_biography",
                    "qualification": "Earlier review.",
                    "model_ready": False,
                }
            ],
        },
    )
    result = ingest(tmp_path, [proposal.relative_to(tmp_path)], validate_only=False)
    assert result["status"] == "ingested"
    manifest = json.loads((tmp_path / "data/candidate-acquisition.json").read_text())
    source = next(row for row in manifest["sources"] if row["id"] == source_id)
    assert fingerprint(tmp_path / source["path"]) == {
        key: source[key] for key in ("bytes", "sha256")
    }
    annotation = json.loads(review_path.read_text())["profiles"][0]
    assert annotation["fields"]["prior_office"] == ["School board member"]
    assert annotation["fields"]["professional_history"] == ["Engineer, Example Corp."]
    assert annotation["model_ready"] is False
    repair = json.loads((tmp_path / "data/candidate-discovery-repair.json").read_text())
    attempt = repair["candidates"][0]["attempts"][0]
    assert attempt["relevant_results"] == []
    assert attempt["rejected_results"][0]["identity_review"] == "rejected"
    registry = json.loads((tmp_path / "data/democratic-background-research.json").read_text())
    assert registry["candidates"][0]["rejected_matches"]
    assert registry["accounting"]["unique_change"]["acquisition_sources"] == 1
    assert registry["accounting"]["unique_change"]["reviewed_candidate_sources"] == 0
    second = ingest(tmp_path, [proposal.relative_to(tmp_path)], validate_only=False)
    assert second["accounting"]["unique_change"]["acquisition_sources"] == 0
    assert second["accounting"]["unique_change"]["reviewed_candidate_sources"] == 0
    registry = json.loads((tmp_path / "data/democratic-background-research.json").read_text())
    assert registry["accounting"]["unique_change"]["acquisition_sources"] == 1
    review = json.loads(review_path.read_text())
    assert "Earlier review." in review["profiles"][0]["qualification"]
    assert review["profiles"][0]["qualification"].count("Campaign self-report") == 1
    repair = json.loads((tmp_path / "data/candidate-discovery-repair.json").read_text())
    assert len(repair["candidates"][0]["attempts"]) == 1


def test_intake_preserves_field_specific_manual_review_metadata(tmp_path):
    proposal, _ = setup_root(tmp_path)
    data = json.loads(proposal.read_text())
    source = data["candidates"][0]["sources"][0]
    source["field_reviews"] = {
        "professional_history": {
            "relationship_status": "paid_employment",
            "claim_status": "supported",
            "qualification": "Employer explicitly identifies this as paid employment.",
        }
    }
    data["candidates"][0]["remaining_fields"] = ["professional_history"]
    data["candidates"][0]["retrieval_attempts"] = [
        {"url": "https://blocked.test/candidate", "status": "failed_not_absence_evidence"}
    ]
    write_json(proposal, data)
    ingest(tmp_path, [proposal.relative_to(tmp_path)], validate_only=False)
    annotation = json.loads((tmp_path / "data/candidate-reviewed-backgrounds.json").read_text())[
        "profiles"
    ][0]
    assert annotation["field_reviews"] == source["field_reviews"]
    registry = json.loads((tmp_path / "data/democratic-background-research.json").read_text())
    assert registry["candidates"][0]["remaining_fields"] == []
    assert (
        registry["candidates"][0]["retrieval_attempts"]
        == data["candidates"][0]["retrieval_attempts"]
    )
    leads = json.loads((tmp_path / "data/candidate-source-leads.json").read_text())
    assert leads[0]["url"] == source["url"]
    normalized_profile = reviewed_inputs(tmp_path)["reviewed_candidate_profiles"][0]
    assert normalized_profile["field_reviews"] == source["field_reviews"]
    candidate = {
        **context(),
        "background": {
            "reviewed_candidate_profiles": [normalized_profile],
            "official_member_profiles": [],
            "official_candidate_profiles": [],
            "member_authorized_biographies": [],
            "official_historian_observations": [],
            "dated_religion_observations": [],
        },
    }
    observation = background_observations([candidate], [])[0]
    assert (
        json.loads(observation["evidence"])["field_review"]
        == source["field_reviews"]["professional_history"]
    )


def test_provider_extraction_must_be_actual_text_with_supported_fragments(tmp_path):
    proposal, _ = setup_root(tmp_path)
    data = json.loads(proposal.read_text())
    source = data["candidates"][0]["sources"][0]
    source.pop("text_or_local_path")
    source["provider_extraction"] = (
        "Test Candidate biography for AA district 01. Worked as an engineer at Example Corp."
    )
    source["retrieval_method"] = "public_search_provider_page_extraction"
    write_json(proposal, data)
    result = ingest(tmp_path, [proposal.relative_to(tmp_path)], validate_only=True)
    assert result["status"] == "validated_no_changes"
    assert result["field_source_count"] == 1


def test_held_provider_excerpt_uses_extraction_receipt_and_preserves_observed_time(tmp_path):
    proposal, _ = setup_root(tmp_path)
    excerpt = tmp_path / "artifacts/democratic-background-research/provider.txt"
    excerpt.write_text(
        "Test Candidate biography for AA district 01. Worked as an engineer at Example Corp."
    )
    data = json.loads(proposal.read_text())
    source = data["candidates"][0]["sources"][0]
    source["text_or_local_path"] = str(excerpt)
    source["media_type"] = "text/plain"
    source["retrieval_method"] = "public_search_provider_page_extraction"
    observed = source["retrieved_at"]
    write_json(proposal, data)
    ingest(tmp_path, [proposal.relative_to(tmp_path)], validate_only=False)
    acquisition = json.loads((tmp_path / "data/candidate-acquisition.json").read_text())
    receipt = acquisition["sources"][0]
    assert receipt["id"].startswith("candidate-extraction-1-")
    assert receipt["retrieval_method"] == "public_search_provider_page_extraction"
    assert receipt["retrieved_at"] == observed
    assert receipt["imported_at"] != observed
    assert "artifacts/" not in receipt["path"]


def test_pdf_sources_require_one_based_pages(tmp_path):
    proposal, _ = setup_root(tmp_path)
    pdf = tmp_path / "artifacts/democratic-background-research/candidate.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with pdf.open("wb") as stream:
        writer.write(stream)
    data = json.loads(proposal.read_text())
    source = data["candidates"][0]["sources"][0]
    source["text_or_local_path"] = "artifacts/democratic-background-research/candidate.pdf"
    source["media_type"] = "application/pdf"
    source["pdf_pages"] = [0]
    write_json(proposal, data)
    with pytest.raises(ValueError, match="one-based pdf_pages"):
        validate(tmp_path, [proposal.relative_to(tmp_path)])


def test_identity_only_source_creates_receipt_but_no_reviewed_observation(tmp_path):
    proposal, _ = setup_root(tmp_path)
    data = json.loads(proposal.read_text())
    source = data["candidates"][0]["sources"][0]
    source["fields"] = {}
    source["support"] = {}
    source["qualification"] = "Identity corroboration only."
    write_json(proposal, data)
    result = ingest(tmp_path, [proposal.relative_to(tmp_path)], validate_only=False)
    assert result["identity_only_source_count"] == 1
    acquisition = json.loads((tmp_path / "data/candidate-acquisition.json").read_text())
    assert len(acquisition["sources"]) == 1
    reviewed = json.loads((tmp_path / "data/candidate-reviewed-backgrounds.json").read_text())
    assert reviewed["profiles"] == []
    registry = json.loads((tmp_path / "data/democratic-background-research.json").read_text())
    assert registry["candidates"][0]["sources"][0]["identity_only"] is True


def test_gap_support_records_source_specific_unknown_without_observation(tmp_path):
    proposal, _ = setup_root(tmp_path)
    data = json.loads(proposal.read_text())
    source = data["candidates"][0]["sources"][0]
    source["fields"] = {}
    source["support"] = {}
    source["gap_support"] = ["Test Candidate", "AA district 01"]
    source["qualification"] = (
        "Relevant biography reviewed; education is not stated and remains unknown."
    )
    write_json(proposal, data)
    ingest(tmp_path, [proposal.relative_to(tmp_path)], validate_only=False)
    repair = json.loads((tmp_path / "data/candidate-discovery-repair.json").read_text())
    review = repair["candidates"][0]["gap_review"]
    assert review["sources"][0]["support"] == ["Test Candidate", "AA district 01"]
    reviewed = json.loads((tmp_path / "data/candidate-reviewed-backgrounds.json").read_text())
    assert reviewed["profiles"] == []


def test_field_gap_review_does_not_expand_frozen_missing_person_queue(tmp_path):
    proposal, _ = setup_root(tmp_path)
    ledger_path = tmp_path / "data/candidate-research-dispositions.json"
    write_json(ledger_path, {"candidates": []})
    data = json.loads(proposal.read_text())
    source = data["candidates"][0]["sources"][0]
    source.update(
        fields={},
        support={},
        gap_support=["Test Candidate", "AA district 01"],
        qualification="Relevant profile reviewed; employment remains unknown.",
    )
    write_json(proposal, data)
    ingest(tmp_path, [proposal.relative_to(tmp_path)], validate_only=False)
    assert json.loads(ledger_path.read_text())["candidates"] == []
    repair = json.loads((tmp_path / "data/candidate-discovery-repair.json").read_text())
    assert repair["candidates"][0]["gap_review"]["sources"]
