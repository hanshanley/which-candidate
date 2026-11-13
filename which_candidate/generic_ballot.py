"""Verify primary state generic-ballot packets; do not impute district baselines."""

import argparse
import json
import re
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path

from pypdf import PdfReader

from .candidate_databases import load_queries
from .fec import STATES
from .storage import confined, fingerprint, write_json, write_rows

POLLS = (
    {
        "id": "siena-ny-20261028",
        "pollster": "Siena Research Institute",
        "state": "NY",
        "release_date": "2026-10-28",
        "field_start": "2026-10-19",
        "field_end": "2026-10-22",
        "population": "likely_voters",
        "sample_n": 807,
        "reported_single_proportion_moe_pp": 4.1,
        "mode": "telephone_and_text_to_web",
        "question_id": "Q6",
        "construct": "generic_vote_intention",
        "question_page": 1,
        "methodology_page": 6,
        "wording_anchor": "If the election for your representative in Congress was held today",
        "file": "siena-ny-20261028-crosstabs.pdf",
        "release_url": (
            "https://sri.siena.edu/2026/10/28/siena-poll-of-likely-new-york-state-voters/"
        ),
        "packet_url": (
            "https://sri.siena.edu/wp-content/uploads/2026/10/2026-October-SNY-Crosstabs.pdf"
        ),
    },
    {
        "id": "marist-mi-20260930",
        "pollster": "Marist Poll",
        "state": "MI",
        "release_date": "2026-09-30",
        "field_start": "2026-09-24",
        "field_end": "2026-09-27",
        "population": "registered_voters",
        "sample_n": 1235,
        "reported_single_proportion_moe_pp": 3.8,
        "mode": "live_telephone_text_and_online",
        "question_id": "USCNGS01",
        "construct": "generic_vote_intention",
        "question_page": 14,
        "methodology_page": 1,
        "wording_anchor": (
            "If November's election for Congress were held today, which party's candidate"
        ),
        "file": "marist-mi-20260930-tables.pdf",
        "release_url": (
            "https://maristpoll.marist.edu/polls/midterm-elections-in-michigan-september-2026/"
        ),
        "packet_url": (
            "https://maristpoll.marist.edu/wp-content/uploads/2026/09/"
            "Marist-Poll_MI-NOS-and-Tables_202609281401@9159_7e99y.pdf"
        ),
    },
    {
        "id": "quinnipiac-pa-20261007",
        "pollster": "Quinnipiac University",
        "state": "PA",
        "release_date": "2026-10-07",
        "field_start": "2026-10-01",
        "field_end": "2026-10-05",
        "population": "likely_voters",
        "sample_n": 1159,
        "reported_single_proportion_moe_pp": 3.9,
        "mode": "live_telephone",
        "question_id": "Q2",
        "construct": "house_control_preference",
        "question_page": 4,
        "methodology_page": 3,
        "wording_anchor": "Party win control of the United States House of Representatives",
        "file": "quinnipiac-pa-20261007.pdf",
        "release_url": "https://poll.qu.edu/poll-release?releaseid=3970",
        "packet_url": "https://poll.qu.edu/images/polling/pa/pa10072026_pgrx47.pdf",
    },
)


def qualify_poll(spec, democrat, republican, cutoff="2026-11-03"):
    start, end, release, cutoff = (
        date.fromisoformat(value)
        for value in (spec["field_start"], spec["field_end"], spec["release_date"], cutoff)
    )
    if not start <= end <= release < cutoff:
        raise ValueError("Poll dates exceed the election cutoff or are out of order")
    if spec["population"] not in {"likely_voters", "registered_voters"}:
        raise ValueError("Unqualified respondent population")
    if spec["construct"] not in {"generic_vote_intention", "house_control_preference"}:
        raise ValueError("Unqualified question construct")
    if (
        not 0 <= democrat <= 100
        or not 0 <= republican <= 100
        or not 0 < democrat + republican <= 100
    ):
        raise ValueError("Invalid reported D/R percentages")
    return {
        **spec,
        "democrat_pct": democrat,
        "republican_pct": republican,
        "unallocated_pct_from_rounded_DR": 100 - democrat - republican,
        "D_minus_R_margin_pp": democrat - republican,
        "D_two_party_share_pct": (
            100 * democrat / (democrat + republican)
            if spec["construct"] == "generic_vote_intention"
            else None
        ),
        "D_normalized_control_preference_pct": (
            100 * democrat / (democrat + republican)
            if spec["construct"] == "house_control_preference"
            else None
        ),
        "question_type": spec["construct"],
        "geography": "statewide",
        "days_field_end_to_election": (cutoff - end).days,
        "qualification": "published_before_election; original_acquired_retrospectively",
        "margin_or_normalized_share_ci": None,
        "uncertainty_note": (
            "Published MOE is not a D-minus-R margin MOE or a normalized-share CI. "
            "Do not double it or use it as residual uncertainty."
        ),
    }


def extract_poll(spec, text):
    normalized = " ".join(text.split())
    if spec["wording_anchor"] not in normalized:
        raise ValueError(f"Wrong question page: {spec['id']}")
    if spec["construct"] == "house_control_preference":
        question = re.split(r"(?m)^\s*2\.\s", text, maxsplit=1)
        if len(question) != 2 or spec["wording_anchor"] not in " ".join(question[1].split()):
            raise ValueError("Quinnipiac House-control question not found")
        d = re.search(r"(?m)^\s*Democratic Party\s+(\d+)%?\s", question[1])
        r = re.search(r"(?m)^\s*Republican Party\s+(\d+)%?\s", question[1])
        if not d or not r:
            raise ValueError("Quinnipiac House-control total rows not found")
        return qualify_poll(spec, int(d[1]), int(r[1]))
    if spec["id"].startswith("siena"):
        question = text.split("Q6.", 1)[1]
        d = re.search(r"(?m)^\s*the Democrat\s+(\d+)%", question)
        r = re.search(r"(?m)^\s*the Republican\s+(\d+)%", question)
        if not d or not r:
            raise ValueError("Siena generic-ballot total rows not found")
        return qualify_poll(spec, int(d[1]), int(r[1]))
    if not re.search(r"Democrat\s+Republican", text):
        raise ValueError("Marist party column order changed")
    total = re.search(r"(?m)^\s*Registered Voters\s+(\d+)%\s+(\d+)%", text)
    if not total:
        raise ValueError("Marist statewide registered-voter total not found")
    return qualify_poll(spec, int(total[1]), int(total[2]))


def candidate_context(query, polls):
    available = [poll["id"] for poll in polls if poll["state"] == query["state"]]
    return {
        "contest_id": query["contest_id"],
        "candidate_election_id": query.get("D_candidate_election_id"),
        "name": query.get("D_name"),
        "state": query["state"],
        "chamber": query["chamber"],
        "poll_ids": available,
        "generic_vote_intention_poll_ids": [
            poll["id"]
            for poll in polls
            if poll["state"] == query["state"] and poll["construct"] == "generic_vote_intention"
        ],
        "house_control_preference_poll_ids": [
            poll["id"]
            for poll in polls
            if poll["state"] == query["state"] and poll["construct"] == "house_control_preference"
        ],
        "status": "state_context_only" if available else "no_acquired_state_poll",
        "expected_candidate_vote_share": None,
        "candidate_WAR": None,
        "reason": (
            "A statewide congressional preference is not a district prediction or a "
            "candidate-free Senate counterfactual. RV/LV, dates and polling error differ."
        ),
    }


def acquire(cache, manifest):
    cache.mkdir(parents=True, exist_ok=True)
    old = json.loads(manifest.read_text()) if manifest.exists() else {"sources": []}
    old = {row["id"]: row for row in old["sources"]}
    sources = []
    for spec in POLLS:
        path = confined(cache, spec["file"])
        if spec["id"] in old:
            receipt = old[spec["id"]]
            if fingerprint(path) != {"sha256": receipt["sha256"], "bytes": receipt["bytes"]}:
                raise ValueError("Previously pinned poll changed")
        else:
            existing = path.exists()
            if not existing:
                subprocess.run(
                    [
                        "curl",
                        "--fail",
                        "--location",
                        "--max-time",
                        "120",
                        spec["packet_url"],
                        "--output",
                        str(path),
                    ],
                    check=True,
                )
            receipt = {
                "id": spec["id"],
                "file": spec["file"],
                "origin_url": spec["packet_url"],
                "release_url": spec["release_url"],
                "acquired_at": datetime.fromtimestamp(
                    path.stat().st_mtime, timezone.utc
                ).isoformat(),
                "acquisition_clock_basis": (
                    "existing_download_file_mtime" if existing else "completed_download_file_mtime"
                ),
                **fingerprint(path),
            }
        sources.append(receipt)
    write_json(manifest, {"schema": 1, "sources": sources})


def build(cache, manifest, queries, output):
    receipts = json.loads(manifest.read_text())
    by_id = {row["id"]: row for row in receipts["sources"]}
    polls = []
    for spec in POLLS:
        receipt = by_id[spec["id"]]
        path = confined(cache, receipt["file"])
        if fingerprint(path) != {"sha256": receipt["sha256"], "bytes": receipt["bytes"]}:
            raise ValueError("Pinned poll packet changed")
        page = PdfReader(path).pages[spec["question_page"] - 1]
        poll = extract_poll(spec, page.extract_text(extraction_mode="layout"))
        poll["source_receipt"] = receipt
        polls.append(poll)
    output.mkdir(parents=True, exist_ok=True)
    write_rows(output / "poll-observations.jsonl.gz", polls)
    write_rows(
        output / "candidate-poll-queries.jsonl.gz",
        [candidate_context(query, polls) for query in queries],
    )
    write_json(
        output / "state-coverage.json",
        {
            "acquired_states": sorted({poll["state"] for poll in polls}),
            "generic_vote_intention_states": sorted(
                {poll["state"] for poll in polls if poll["construct"] == "generic_vote_intention"}
            ),
            "house_control_preference_states": sorted(
                {poll["state"] for poll in polls if poll["construct"] == "house_control_preference"}
            ),
            "all_50_states": {
                state: [poll["id"] for poll in polls if poll["state"] == state]
                for state in sorted(STATES)
            },
            "not_a_50_state_dataset": True,
            "pooling": "none; do_not_average_different_states_populations_or_dates",
            "publication_status": "withdrawn; research_only",
        },
    )
    write_json(output / "source-receipts.json", receipts)
    return polls


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["acquire", "build"])
    parser.add_argument("--cache", type=Path, default=Path("data/raw/candidate-databases-20261113"))
    parser.add_argument("--manifest", type=Path, default=Path("data/generic-ballot-sources.json"))
    parser.add_argument("--output", type=Path, default=Path("results/2026-poll-context"))
    parser.add_argument(
        "--queries",
        type=Path,
        default=Path("results/2026-v3/analysis/candidate-queries.jsonl.gz"),
    )
    args = parser.parse_args()
    if args.command == "acquire":
        acquire(args.cache, args.manifest)
    else:
        polls = build(args.cache, args.manifest, load_queries(args.queries), args.output)
        print(json.dumps(polls, indent=2))


if __name__ == "__main__":
    main()
