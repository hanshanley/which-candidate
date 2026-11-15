import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from which_candidate import candidate_acquisition as acquisition
from which_candidate.house_backgrounds import background_observations
from which_candidate.reviewed_backgrounds import matched_profiles, reviewed_inputs
from which_candidate.storage import read_rows, write_json

ROOT = Path(__file__).resolve().parents[1]


def test_biography_links_are_bounded_same_host_and_not_policy_or_donation_pages():
    raw = b"""
    <a href="/about">About Jane</a><a href="/about">About Jane</a>
    <a href="https://donate.example.org/about">Meet Jane</a>
    <a href="/issues/about">About our issues</a>
    <a href="/meet-jane#story">Meet Jane</a><a href="/biography">Biography</a>
    <a href="javascript:alert(1)">About</a>
    """
    assert acquisition.biography_links(raw, "https://www.example.org/") == [
        "https://www.example.org/about",
        "https://www.example.org/meet-jane",
    ]
    assert acquisition.biography_links(raw, "/relative") == []


def test_failed_downloads_do_not_produce_evidence_or_claim_coverage(tmp_path, monkeypatch):
    candidate = {
        "candidate_id": "1",
        "contest_id": "2026-CA-02",
        "name": "Jane Smith",
        "state": "CA",
        "district": "02",
        "party": "Republican",
        "campaign_websites": ["https://example.org/"],
    }

    def unavailable(*args, **kwargs):
        raise acquisition.urllib.error.URLError("unavailable")

    monkeypatch.setattr(acquisition.urllib.request, "urlopen", unavailable)
    record, sources = acquisition.acquire_candidate(candidate, tmp_path)
    assert not sources and not record["source_ids"]
    assert record["attempts"][0]["status"] == "retrieval_failed"
    assert record["counted_as_background_coverage"] is False


@pytest.mark.parametrize(
    ("body", "status", "count"),
    [(b"<h1>Jane Smith</h1>", 200, 1), (b"", 202, 0), (b"Verify you are human", 200, 0)],
)
def test_downloaded_pages_are_pinned_but_never_automatically_promoted(
    tmp_path, monkeypatch, body, status, count
):
    class Response:
        url = "https://example.org/"
        headers = {"Content-Type": "text/html"}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, size):
            return body

    Response.status = status
    monkeypatch.setattr(acquisition.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    candidate, _, _ = review_fixture(tmp_path)
    record, sources = acquisition.acquire_candidate(
        {**candidate, "campaign_websites": [Response.url]}, tmp_path
    )
    assert len(sources) == count
    assert record["facts_reviewed"] is False
    assert record["counted_as_background_coverage"] is False
    for source in sources:
        assert (tmp_path / source["path"]).read_bytes() == body
        assert source["sha256"] == hashlib.sha256(body).hexdigest()
        assert source["publication_date"] is None


def test_identical_pages_preserve_alternate_retrieval_receipts():
    receipt = {
        "id": "page",
        "sha256": "abc",
        "bytes": 12,
        "path": "page.html",
        "url": "https://example.org/about",
        "resolved_url": "https://example.org/about",
        "retrieved_at": "2026-11-15T12:00:00+00:00",
    }
    alternative = {**receipt, "url": "https://example.org/meet"}
    merged = acquisition.merge_receipts([receipt, alternative])
    assert len(merged) == 1
    assert {row["url"] for row in merged[0]["retrievals"]} == {
        receipt["url"],
        alternative["url"],
    }
    with pytest.raises(ValueError, match="Conflicting original bytes"):
        acquisition.merge_receipts([receipt, {**alternative, "bytes": 13}])


def review_fixture(root):
    body = b"<h1>Jane Smith</h1><p>Jane earned a law degree from Example University.</p>"
    digest = hashlib.sha256(body).hexdigest()
    relative = f"data/raw/candidate-backgrounds-20261115/1-{digest[:20]}.html"
    original = root / relative
    original.parent.mkdir(parents=True)
    original.write_bytes(body)
    candidate = {
        "candidate_id": "1",
        "contest_id": "2026-CA-02",
        "name": "Jane Smith",
        "state": "CA",
        "district": "02",
        "party": "Republican",
        "source_ids": ["page-1"],
    }
    source = {
        "id": "page-1",
        "url": "https://example.org/about",
        "resolved_url": "https://example.org/about",
        "retrieved_at": "2026-11-15T12:00:00+00:00",
        "publication_date": None,
        "sha256": digest,
        "bytes": len(body),
        "path": relative,
    }
    annotation = {
        "qualification": "post-election self-report; descriptive only",
        "profiles": [
            {
                "candidate_id": "1",
                "name": "Jane Smith",
                "source_id": "page-1",
                "fields": {"education": ["Law degree, Example University"]},
                "support": {"education": "law degree from Example University"},
            }
        ],
    }
    write_json(
        root / "data/candidate-acquisition.json", {"candidates": [candidate], "sources": [source]}
    )
    write_json(root / "data/candidate-reviewed-backgrounds.json", annotation)
    return candidate, original, annotation


@pytest.mark.parametrize("field", ["contest_id", "name", "state", "district", "party"])
def test_reviewed_evidence_cannot_cross_candidate_contest_context(tmp_path, field):
    candidate, _, _ = review_fixture(tmp_path)
    inputs = reviewed_inputs(tmp_path)
    assert len(matched_profiles(candidate, inputs)) == 1
    assert not matched_profiles({**candidate, "candidate_id": "other-person"}, inputs)
    with pytest.raises(ValueError, match="candidate-contest context"):
        matched_profiles({**candidate, field: "conflicting"}, inputs)


def test_reviewed_pages_require_original_bytes_anchors_and_subject(tmp_path):
    _, original, annotation = review_fixture(tmp_path)
    assert reviewed_inputs(tmp_path)["reviewed_candidate_profiles"][0]["model_ready"] is False
    changed = deepcopy(annotation)
    changed["profiles"][0]["support"]["education"] = "received a doctorate"
    write_json(tmp_path / "data/candidate-reviewed-backgrounds.json", changed)
    with pytest.raises(ValueError, match="support absent"):
        reviewed_inputs(tmp_path)
    changed["profiles"][0]["name"] = "John Smith"
    write_json(tmp_path / "data/candidate-reviewed-backgrounds.json", changed)
    with pytest.raises(ValueError, match="conflicting subject"):
        reviewed_inputs(tmp_path)
    write_json(tmp_path / "data/candidate-reviewed-backgrounds.json", annotation)
    original.write_bytes(b"<h1>Different page</h1>")
    with pytest.raises(ValueError, match="original changed"):
        reviewed_inputs(tmp_path)


def test_every_accepted_field_becomes_a_qualified_observation_not_a_model_feature():
    from which_candidate.house_candidates import coverage

    inputs = read_rows(ROOT / "results/house/source-inputs.jsonl.gz")[0]
    profiles = inputs["reviewed_candidate_profiles"]
    candidates = read_rows(ROOT / "results/house/candidates.jsonl.gz")
    by_id = {row["candidate_id"]: row for row in candidates}
    observations = background_observations(candidates, [])
    assert coverage(candidates)[0]["member_authorized_background"] == sum(
        bool(
            candidate["background"]["member_authorized_biographies"]
            or candidate["background"].get("official_member_profiles")
        )
        for candidate in candidates
    )
    for profile in profiles:
        candidate = by_id[profile["candidate_id"]]
        assert matched_profiles(candidate, inputs) == [profile]
        records = [
            row
            for row in observations
            if row["candidate_id"] == candidate["candidate_id"]
            and row["source_kind"] == profile["source_kind"]
        ]
        assert {row["field"] for row in records} == set(profile["fields"])
        for row in records:
            evidence = json.loads(row["evidence"])
            assert evidence["sha256"] == profile["evidence"]["sha256"]
            assert evidence["publication_date"] is None
            assert row["model_ready"] is False and row["source_year"] is None
    selected = {row["name"]: row for row in profiles}
    assert "military_service" not in selected["Mark Teixeira"]["fields"]
    assert "military_service" not in selected["Rachel Grage"]["fields"]
    assert "military_service" not in selected["Carmela Conroy"]["fields"]
    assert "Luke Bronin" not in selected
    assert (
        "degree completion not established" in selected["Rhett Marques"]["fields"]["education"][0]
    )
