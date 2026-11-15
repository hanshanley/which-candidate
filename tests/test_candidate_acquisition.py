import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from which_candidate import candidate_acquisition as acquisition
from which_candidate.house_backgrounds import background_observations
from which_candidate.reviewed_backgrounds import ingest, matched_profiles, reviewed_inputs
from which_candidate.storage import fingerprint, read_rows, write_json, write_rows

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
    assert not acquisition.biography_links(raw, "https://youtube.com/@candidate")
    assert not acquisition.biography_links(raw, "https://vote-usa.org/Intro.aspx?Id=CAJane")
    assert not acquisition.biography_links(raw, "https://lp.org/candidate/jane-smith/")


def test_biography_links_find_autobiographies_without_following_social_share_copies():
    raw = b"""
    <a href="/bio/?share=twitter">Share</a>
    <a href="/bio/?share=facebook">Share</a>
    <a href="/who-am-i">Who Am I</a>
    <a href="/my-story">My Story</a>
    """
    assert acquisition.biography_links(raw, "https://candidate.example/bio/") == [
        "https://candidate.example/who-am-i",
        "https://candidate.example/my-story",
    ]


def test_questionnaire_only_loads_declared_public_biography_answers_for_same_person():
    raw = b"""
    <div class="accordion-header bottom">Educational Background</div><div
      data-ajax="Content=INTRO&amp;Id=NYExample&amp;Question=8"></div>
    <div class="accordion-header bottom">Political Experience</div><div
      data-ajax="Content=INTRO&amp;Id=OtherPerson&amp;Question=5"></div>
    <div class="accordion-header bottom">Personal and Family</div><div
      data-ajax="Content=INTRO&amp;Id=NYExample&amp;Question=2"></div>
    """
    assert acquisition.public_questionnaire_links(
        raw, "https://vote-usa.org/Intro.aspx?State=NY&Id=NYExample"
    ) == ["https://vote-usa.org/AjaxContent.aspx?Content=INTRO&Id=NYExample&Question=8"]
    assert not acquisition.public_questionnaire_links(raw, "https://other.example/Intro.aspx")


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


@pytest.mark.parametrize(
    ("media_type", "accepted"), [("application/pdf", True), ("text/html", False)]
)
def test_large_scanned_publications_are_acquired_without_relaxing_html_limits(
    tmp_path, monkeypatch, media_type, accepted
):
    body = b"%PDF-1.4\n" + b" " * (9 * 1024 * 1024)

    class Response:
        url = "https://example.org/publication"
        status = 200
        headers = {"Content-Type": media_type}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, size):
            return body[:size]

    monkeypatch.setattr(acquisition.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    candidate, _, _ = review_fixture(tmp_path)
    record, sources = acquisition.acquire_candidate(
        {**candidate, "campaign_websites": [Response.url]}, tmp_path
    )
    assert bool(sources) is accepted
    assert record["counted_as_background_coverage"] is False
    if accepted:
        assert fingerprint(tmp_path / sources[0]["path"]) == {
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
        }
    else:
        assert record["attempts"][0]["status"] == "empty_or_unsupported_response"


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


def test_reviewed_annotation_cannot_request_model_promotion(tmp_path):
    _, _, annotation = review_fixture(tmp_path)
    annotation["profiles"][0]["model_ready"] = True
    with pytest.raises(ValueError, match="cannot become a model"):
        reviewed_inputs(tmp_path, profiles=annotation["profiles"])


@pytest.mark.parametrize("pages", [[2], [1], [0], [3], None])
def test_reviewed_pdf_requires_valid_pages_and_anchors_on_those_pages(tmp_path, pages):
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    _, _, annotation = review_fixture(tmp_path)
    writer = PdfWriter()
    for text in (
        "Different candidate and page",
        "Jane Smith earned a law degree from Example University",
    ):
        page = writer.add_blank_page(width=400, height=200)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        stream = DecodedStreamObject()
        stream.set_data(f"BT /F1 12 Tf 10 100 Td ({text}) Tj ET".encode())
        page[NameObject("/Contents")] = writer._add_object(stream)
    path = tmp_path / "data/raw/candidate-backgrounds-20261115/official.pdf"
    writer.write(path)
    manifest_path = tmp_path / "data/candidate-acquisition.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["sources"][0].update(
        path=str(path.relative_to(tmp_path)), media_type="application/pdf", **fingerprint(path)
    )
    write_json(manifest_path, manifest)
    profile = annotation["profiles"][0]
    profile["pdf_pages"] = pages
    profile["source_kind"] = "official_previous_office_biography"
    if pages == [2]:
        result = reviewed_inputs(tmp_path, profiles=[profile])["reviewed_candidate_profiles"][0]
        assert result["evidence"]["pdf_pages"] == [2]
        assert result["model_ready"] is False
    else:
        with pytest.raises(ValueError, match="valid page|support absent"):
            reviewed_inputs(tmp_path, profiles=[profile])


def test_incremental_ingestion_preserves_normalized_evidence_without_old_originals(
    tmp_path, monkeypatch
):
    from which_candidate import house_candidates

    candidate, old_original, annotation = review_fixture(tmp_path)
    held_profile = reviewed_inputs(tmp_path)["reviewed_candidate_profiles"][0]
    old_original.unlink()
    body = b"<h1>Jane Smith</h1><p>Jane worked as a public defender.</p>"
    path = tmp_path / "data/raw/candidate-backgrounds-20261115/new.html"
    path.write_bytes(body)
    manifest_path = tmp_path / "data/candidate-acquisition.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["sources"].append(
        {
            **manifest["sources"][0],
            "id": "page-2",
            "path": str(path.relative_to(tmp_path)),
            **fingerprint(path),
        }
    )
    manifest["candidates"][0]["source_ids"].append("page-2")
    write_json(manifest_path, manifest)
    annotation["profiles"].append(
        {
            "candidate_id": "1",
            "name": "Jane Smith",
            "source_id": "page-2",
            "fields": {"professional_history": ["Public defender"]},
            "support": {"professional_history": "worked as a public defender"},
        }
    )
    write_json(tmp_path / "data/candidate-reviewed-backgrounds.json", annotation)
    held = tmp_path / "results/house"
    held.mkdir(parents=True)
    inputs = {"reviewed_candidate_profiles": [held_profile], "untouched_historical": [1, 2, 3]}
    write_rows(held / "source-inputs.jsonl.gz", [inputs])
    write_rows(held / "candidates.jsonl.gz", [candidate])
    write_json(
        held / "manifest.json",
        {
            "files": {
                name: fingerprint(held / name)
                for name in ("source-inputs.jsonl.gz", "candidates.jsonl.gz")
            }
        },
    )
    captured = {}

    def build(root, *, output, inputs):
        captured.update(inputs)
        return {"rebuilt": True}

    monkeypatch.setattr(house_candidates, "build", build)
    result = ingest(tmp_path)
    assert result["validated_new_or_changed_profiles"] == 1
    assert result["preserved_normalized_profiles"] == 1
    assert captured["untouched_historical"] == inputs["untouched_historical"]
    assert captured["reviewed_candidate_profiles"][0] == held_profile
    assert len(captured["reviewed_candidate_profiles"]) == 2
    assert not old_original.exists()
    path.write_bytes(b"changed")
    with pytest.raises(ValueError, match="original changed"):
        ingest(tmp_path)


def test_unchanged_ingestion_needs_no_originals_and_preserves_input_order(tmp_path, monkeypatch):
    from which_candidate import house_candidates

    candidate, original, _ = review_fixture(tmp_path)
    profile = reviewed_inputs(tmp_path)["reviewed_candidate_profiles"][0]
    original.unlink()
    held = tmp_path / "results/house"
    held.mkdir(parents=True)
    inputs = {"reviewed_candidate_profiles": [profile], "historical_records": [{"id": 9}]}
    for name, rows in (("source-inputs.jsonl.gz", [inputs]), ("candidates.jsonl.gz", [candidate])):
        write_rows(held / name, rows)
    write_json(
        held / "manifest.json",
        {
            "files": {
                name: fingerprint(held / name)
                for name in ("source-inputs.jsonl.gz", "candidates.jsonl.gz")
            }
        },
    )
    calls = []

    def build(root, *, output, inputs):
        calls.append(deepcopy(inputs))
        return {"rebuilt": True}

    monkeypatch.setattr(house_candidates, "build", build)
    for _ in range(2):
        result = ingest(tmp_path)
        assert result["validated_new_or_changed_profiles"] == 0
        assert result["preserved_normalized_profiles"] == 1
    assert calls == [inputs, inputs]


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
        assert profile in matched_profiles(candidate, inputs)
        records = [
            row
            for row in observations
            if row["candidate_id"] == candidate["candidate_id"]
            and isinstance(evidence := json.loads(row["evidence"]), dict)
            and evidence.get("source_id") == profile["evidence"]["source_id"]
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
    bronin_campaign = [
        profile
        for profile in profiles
        if profile["name"] == "Luke Bronin"
        and "broninforcongress.com" in profile["evidence"]["url"]
    ]
    assert len(bronin_campaign) == 1
    assert "Navy intelligence officer" in bronin_campaign[0]["fields"]["military_service"][0]
    assert (
        "degree completion not established" in selected["Rhett Marques"]["fields"]["education"][0]
    )
