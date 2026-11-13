"""Verify and package the withdrawn 2026 source-research milestone."""

import argparse
import gzip
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from . import candidate_databases, generic_ballot
from .publication import write_zip
from .storage import confined, fingerprint, write_json, write_rows

CACHE = Path("data/raw/candidate-databases-20261113")
SOURCE_OUTPUT = Path("results/2026-source-expansion")
POLL_OUTPUT = Path("results/2026-poll-context")
QUERIES = Path("results/2026-v3/analysis/candidate-queries.jsonl.gz")
AUDIT = Path("audits/2026-source-verification.json")


def read_rows(path):
    with gzip.open(path, "rt") as handle:
        return [json.loads(line) for line in handle]


def require_complete(expected, actual):
    keys = [row["contest_id"] for row in actual]
    if len(keys) != len(set(keys)) or set(keys) != {row["contest_id"] for row in expected}:
        raise ValueError("Missing, duplicate or unexpected contest queries")


def caucus_decisions(queries, memberships, fits):
    fitted_ids = {
        candidate
        for fit in fits
        if fit["year"] == 2026
        and fit["comparison"] == "blue_dog_vs_cpc"
        and fit["variant"] == "lean_incumbency"
        for candidate in fit["candidate_election_ids"]
    }
    decisions = []
    for member in memberships:
        if member["year"] != 2026 or member["group"] not in {"blue_dog", "cpc"}:
            continue
        group = member["group"]
        matches = [
            row
            for row in queries
            if row["chamber"] == "house"
            and row.get(group)
            and any(
                evidence["name"] == member["name"] and evidence["group"] == group
                for evidence in row[f"{group}_evidence"]
            )
        ]
        decisions.append(
            {
                **member,
                "status": "matched_nominee" if matches else "not_matched_to_a_2026_nominee",
                "candidate_decisions": [
                    {
                        "contest_id": row["contest_id"],
                        "name": row["D_name"],
                        "eligible_v3": row["eligible"],
                        "analysis_exclusion_reasons": row["analysis_exclusion_reasons"],
                        "in_frozen_membership_model": row["D_candidate_election_id"] in fitted_ids,
                    }
                    for row in matches
                ],
            }
        )
    return decisions


def verify(root):
    queries = candidate_databases.load_queries(root / QUERIES)
    if len(queries) != 470:
        raise ValueError("The frozen 2026 universe must contain all 470 contests")
    candidate_rows = read_rows(root / SOURCE_OUTPUT / "candidate-queries.jsonl.gz")
    poll_rows = read_rows(root / POLL_OUTPUT / "candidate-poll-queries.jsonl.gz")
    require_complete(queries, candidate_rows)
    require_complete(queries, poll_rows)

    def deny_network(*args, **kwargs):
        raise RuntimeError("Network access attempted during offline replay")

    compared = {}
    with tempfile.TemporaryDirectory(prefix="which-candidate-replay-") as directory:
        temporary = Path(directory)
        with (
            patch("socket.socket.connect", deny_network),
            patch("socket.socket.connect_ex", deny_network),
        ):
            candidate_databases.build(
                root / CACHE,
                root / "data/candidate-database-sources.json",
                queries,
                temporary / "candidate",
                root / "data/research-sources.json",
                root / QUERIES,
                root / "data/candidate-self-descriptions.json",
            )
            generic_ballot.build(
                root / CACHE,
                root / "data/generic-ballot-sources.json",
                queries,
                temporary / "poll",
            )
        for original, replay in (
            (root / SOURCE_OUTPUT, temporary / "candidate"),
            (root / POLL_OUTPUT, temporary / "poll"),
        ):
            for path in sorted(replay.iterdir()):
                held = original / path.name
                if path.read_bytes() != held.read_bytes():
                    raise ValueError(f"Offline replay differs: {held}")
                compared[held.relative_to(root).as_posix()] = fingerprint(held)
    decisions = caucus_decisions(
        queries,
        read_rows(root / "results/2026-v3/inputs/memberships.jsonl.gz"),
        read_rows(root / "results/2026-v3/analysis/moderation-fits.jsonl.gz"),
    )
    write_rows(root / SOURCE_OUTPUT / "caucus-membership-decisions.jsonl.gz", decisions)
    summary = {}
    for group in ("blue_dog", "cpc"):
        members = [row for row in decisions if row["group"] == group]
        matched = [candidate for row in members for candidate in row["candidate_decisions"]]
        summary[group] = {
            "source_roster": len(members),
            "matched_nominees": len(matched),
            "v3_eligible": sum(row["eligible_v3"] for row in matched),
            "in_frozen_membership_model": sum(row["in_frozen_membership_model"] for row in matched),
        }
    write_json(root / SOURCE_OUTPUT / "caucus-membership-summary.json", summary)
    report = {
        "status": "verified_source_research_milestone_not_new_fits",
        "publication_status": "withdrawn",
        "queries": {"candidate_sources": len(candidate_rows), "poll_context": len(poll_rows)},
        "network_disabled_replay_files": compared,
        "caucus_membership_attrition": summary,
        "unresolved": [
            "DIME name aliases and cross-office identities require review before model use.",
            "Biographies and donation scores remain highly incumbent-selected.",
            "CAWP winner-only classifications do not cover all nominees.",
            "No comprehensive current religion/race or 50-state generic-ballot dataset acquired.",
            "User-supplied caucus WAR sample sizes/model have not been independently reproduced.",
            "Replacement analysis and publication figures are not approved or complete.",
        ],
    }
    write_json(root / AUDIT, report)
    return report


def package(root, destination, include_cache=False):
    report = json.loads((root / AUDIT).read_text())
    for name, expected in report["network_disabled_replay_files"].items():
        if fingerprint(confined(root, name)) != expected:
            raise ValueError(f"Verified output changed before packaging: {name}")
    entries = {}
    for folder, pattern in (
        ("which_candidate", "*.py"),
        ("tests", "*.py"),
        ("docs", "*.md"),
        (str(SOURCE_OUTPUT), "*"),
        (str(POLL_OUTPUT), "*"),
    ):
        for path in (root / folder).glob(pattern):
            if path.is_file():
                entries[path.relative_to(root).as_posix()] = path
    for name in (
        "README.md",
        "pyproject.toml",
        "requirements.lock",
        "data/candidate-database-sources.json",
        "data/candidate-self-descriptions.json",
        "data/generic-ballot-sources.json",
        "data/research-sources.json",
        str(QUERIES),
        "results/2026-v3/inputs/memberships.jsonl.gz",
        "results/2026-v3/analysis/moderation-fits.jsonl.gz",
        "audits/2026-source-expansion.json",
        "audits/2026-withdrawal.json",
        str(AUDIT),
    ):
        entries[name] = root / name
    if include_cache:
        if not destination.resolve().is_relative_to((root / "artifacts").resolve()):
            raise ValueError("Restricted-original replay packages must stay in ignored artifacts/")
        for manifest in (
            "data/candidate-database-sources.json",
            "data/generic-ballot-sources.json",
        ):
            for source in json.loads((root / manifest).read_text())["sources"]:
                name = (CACHE / source["file"]).as_posix()
                path = confined(root / CACHE, source["file"])
                if fingerprint(path) != {"sha256": source["sha256"], "bytes": source["bytes"]}:
                    raise ValueError(f"Original changed before packaging: {name}")
                entries[name] = path
        for source in json.loads(
            (root / SOURCE_OUTPUT / "reused-source-receipts.json").read_text()
        ):
            name = (Path("data") / source["path"]).as_posix()
            path = confined(root / "data", source["path"])
            if fingerprint(path) != {"sha256": source["sha256"], "bytes": source["bytes"]}:
                raise ValueError(f"Original changed before packaging: {name}")
            entries[name] = path
    destination.parent.mkdir(parents=True, exist_ok=True)
    write_zip(destination, entries)
    return {"members": len(entries), **fingerprint(destination)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["verify", "package"])
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument(
        "--output", type=Path, default=Path("downloads/2026-source-complete-queries.zip")
    )
    parser.add_argument("--include-cache", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    report = (
        verify(root) if args.command == "verify" else package(root, args.output, args.include_cache)
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
