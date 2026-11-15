import csv
import json

import pytest

from which_candidate.candidate_research import (
    attach_dispositions,
    background_field_coverage,
    directory_candidates,
    directory_matches,
    establish_queue,
    finalize,
    search_links,
)
from which_candidate.storage import fingerprint, write_json, write_rows


def test_directory_preserves_office_context_and_finds_campaign_and_questionnaire_urls():
    raw = b"""
    <div class="office-title accordion-header"><span>District 7</span></div>
    <a href="CompareCandidates.aspx?State=NY&amp;Office=NYUSHouse7">Compare</a>
    <div class="candidate-cell"><div class="candidate-name">Claire Valdez - <a>D</a></div>
    <div class="candidate-website"><a href="https://example.org/about">Website</a></div>
    <a href="https://vote-usa.org/Intro.aspx?State=NY&amp;Id=NYValdezClaire">More</a></div>
    """
    assert directory_candidates(raw) == [
        {
            "name": "Claire Valdez",
            "state": "NY",
            "district": "07",
            "party_code": "D",
            "campaign_url": "https://example.org/about",
            "intro_url": "https://vote-usa.org/Intro.aspx?State=NY&Id=NYValdezClaire",
        }
    ]


def test_queue_uses_people_without_observations_and_stays_frozen(tmp_path):
    source = tmp_path / "results/house-study/candidate-profiles.jsonl.gz"
    source.parent.mkdir(parents=True)
    rows = [
        {
            "candidate_id": str(i),
            "contest_id": "race",
            "name": f"Person {i}",
            "state": "NY",
            "district": "07",
            "party": party,
            "campaign_websites": [],
            "acquired_background_observations": observations,
        }
        for i, party, observations in (
            (1, "Independent", []),
            (2, "Democratic", []),
            (3, "Republican", [{"field": "education"}]),
        )
    ]
    write_rows(source, rows)
    (tmp_path / "data").mkdir()
    queue = establish_queue(tmp_path)
    assert [row["candidate_id"] for row in queue["candidates"]] == ["2", "1"]
    assert queue["baseline_covered"] == 1
    write_rows(source, [])
    assert establish_queue(tmp_path) == queue
    assert json.loads((tmp_path / "data/candidate-research-queue.json").read_text()) == queue


def test_search_result_headings_are_leads_not_observations():
    raw = b'<h2><a href="https://candidate.example/about">About Candidate</a></h2>'
    assert search_links(raw) == [
        {"url": "https://candidate.example/about", "title": "About Candidate"}
    ]


def test_directory_at_large_alias_and_party_conflict_are_separate():
    candidate = {
        "candidate_id": "221167",
        "state": "SD",
        "district": "AL",
        "party": "Democratic",
        "name": "Nikki Gronli",
    }
    row = {"state": "SD", "district": "01", "party_code": "D", "name": 'Nicole "Nikki" Gronli'}
    assert directory_matches(candidate, [row]) == [row]
    assert not directory_matches(candidate, [{**row, "party_code": "R"}])
    assert not directory_matches(candidate, [{**row, "state": "WY"}])


def test_field_gaps_keep_unknowns_and_count_qualified_aliases_without_completeness_claims():
    coverage = background_field_coverage(
        [
            {"field": "education", "value": ["Unknown", " "]},
            {"field": "occupation", "value": ["Teacher"]},
            {"field": "governmental_experience", "value": "School board"},
            {"field": "military_service", "value": None},
            {"field": "religion", "value": "Unknown"},
        ]
    )
    assert coverage["background_fields_with_observations"] == [
        "prior_office",
        "professional_history",
    ]
    assert coverage["remaining_background_fields"] == ["education", "military_service"]


def research_fixture(root):
    candidates = [
        {
            "candidate_id": str(i),
            "contest_id": f"contest-{i}",
            "name": f"Person {i}",
            "state": "NY",
            "district": f"{i:02}",
            "party": party,
        }
        for i, party in ((1, "Democratic"), (2, "Write-In"))
    ]
    (root / "data").mkdir()
    write_json(
        root / "data/candidate-research-queue.json",
        {"baseline_candidates": 2, "baseline_covered": 0, "candidates": candidates},
    )
    write_json(
        root / "data/candidate-research-dispositions.json",
        {
            "candidates": [
                {**row, "directory_matches": [], "search_query": "query", "search_receipt": {}}
                for row in candidates
            ]
        },
    )
    sources = []
    for i, url, body in (
        (1, "https://candidate.example/about", b"College graduate."),
        (2, "https://vote-usa.org/AjaxContent.aspx?Question=8", b""),
    ):
        path = root / "data" / f"source-{i}.html"
        path.write_bytes(body)
        sources.append(
            {
                "id": f"source-{i}",
                "url": url,
                "path": str(path.relative_to(root)),
                "retrieved_at": "2026-11-15T20:00:00+00:00",
                "media_type": "text/html",
                **fingerprint(path),
            }
        )
    write_json(
        root / "data/candidate-acquisition.json",
        {
            "sources": sources,
            "candidates": [
                {
                    **row,
                    "source_ids": [f"source-{row['candidate_id']}"],
                    "attempts": [],
                }
                for row in candidates
            ],
        },
    )
    held = root / "results/house"
    held.mkdir(parents=True)
    write_rows(held / "candidates.jsonl.gz", candidates)
    with (held / "background-observations.csv").open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=["candidate_id", "field", "value", "evidence"])
        writer.writeheader()
        writer.writerow(
            {
                "candidate_id": "1",
                "field": "education",
                "value": json.dumps("College graduate"),
                "evidence": json.dumps({"source_id": "source-1"}),
            }
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
    return [
        {
            **row,
            "acquired_background_observations": (
                [
                    {
                        "field": "education",
                        "value": "College graduate",
                        "evidence": {"source_id": "source-1"},
                    }
                ]
                if row["candidate_id"] == "1"
                else []
            ),
        }
        for row in candidates
    ]


def test_finalization_accounts_for_accepted_facts_and_empty_answers_and_replays_without_raw(
    tmp_path,
):
    profiles = research_fixture(tmp_path)
    summary = finalize(tmp_path)
    assert summary["newly_covered_people"] == summary["remaining_uncovered_people"] == 1
    ledger_path = tmp_path / "data/candidate-research-dispositions.json"
    ledger = json.loads(ledger_path.read_text())
    assert ledger["candidates"][0]["research_status"] == "sourced_observations_partial"
    assert ledger["candidates"][1]["research_status"] == "questionnaire_fields_unavailable"
    assert ledger["candidates"][1]["accepted_source_ids"] == []
    assert attach_dispositions(tmp_path, profiles) == summary
    before = fingerprint(ledger_path)
    for path in (tmp_path / "data").glob("source-*.html"):
        path.unlink()
    assert finalize(tmp_path) == summary
    assert fingerprint(ledger_path) == before


@pytest.mark.parametrize(
    "change", ["coverage", "identity", "receipt", "omitted", "duplicate", "promotion"]
)
def test_ledger_rejects_stale_counts_wrong_context_and_unsupported_source_claims(tmp_path, change):
    profiles = research_fixture(tmp_path)
    finalize(tmp_path)
    path = tmp_path / "data/candidate-research-dispositions.json"
    ledger = json.loads(path.read_text())
    first = ledger["candidates"][0]
    if change == "coverage":
        first["acquired_observation_count"] = 2
    elif change == "identity":
        first["party"] = "Republican"
    elif change == "receipt":
        first["source_outcomes"][0]["sha256"] = "bad hash"
    elif change == "omitted":
        first["source_outcomes"] = []
    elif change == "duplicate":
        first["source_outcomes"] *= 2
    else:
        ledger["candidates"][1]["source_outcomes"][0]["status"] = "accepted_reviewed_fields"
    write_json(path, ledger)
    with pytest.raises(ValueError):
        attach_dispositions(tmp_path, profiles)


def test_nonempty_questionnaire_needs_review_and_never_automatically_becomes_evidence(tmp_path):
    research_fixture(tmp_path)
    path = tmp_path / "data/source-2.html"
    path.write_text("Army veteran")
    acquisition_path = tmp_path / "data/candidate-acquisition.json"
    acquisition = json.loads(acquisition_path.read_text())
    acquisition["sources"][1].update(fingerprint(path))
    write_json(acquisition_path, acquisition)
    with pytest.raises(ValueError, match="still needs review"):
        finalize(tmp_path)
    ledger_path = tmp_path / "data/candidate-research-dispositions.json"
    ledger = json.loads(ledger_path.read_text())
    ledger["candidates"][1]["review_note"] = "Ambiguous account; no service claim credited."
    ledger["candidates"][1]["reviewed_source_ids"] = ["source-2"]
    write_json(ledger_path, ledger)
    assert finalize(tmp_path)["remaining_uncovered_people"] == 1
    new_path = tmp_path / "data/new-source.html"
    new_path.write_text("Another page not included in the old review.")
    acquisition["sources"].append(
        {
            **acquisition["sources"][1],
            "id": "source-3",
            "url": "https://candidate.example/new",
            "path": str(new_path.relative_to(tmp_path)),
            **fingerprint(new_path),
        }
    )
    acquisition["candidates"][1]["source_ids"].append("source-3")
    write_json(acquisition_path, acquisition)
    with pytest.raises(ValueError, match="still needs a review"):
        finalize(tmp_path)


def test_finalization_rejects_duplicate_people_before_writing_decisions(tmp_path):
    research_fixture(tmp_path)
    path = tmp_path / "data/candidate-research-dispositions.json"
    ledger = json.loads(path.read_text())
    ledger["candidates"].append(ledger["candidates"][0])
    write_json(path, ledger)
    with pytest.raises(ValueError, match="exactly once"):
        finalize(tmp_path)
