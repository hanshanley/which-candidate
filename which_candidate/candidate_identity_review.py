"""Audit donor identities using independent, pinned congressional crosswalks."""

import argparse
import gzip
import json
from collections import Counter
from pathlib import Path

from .features import FeatureSources, name_matches
from .publication import write_zip
from .storage import confined, fingerprint, write_json, write_rows


def read_queries(path):
    with gzip.open(path, "rt") as handle:
        rows = [json.loads(line) for line in handle]
    ids = [row["contest_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Duplicate contest identity: {path}")
    return rows


def load_crosswalk(manifest):
    specs = [
        row for row in json.loads(manifest.read_text())["sources"] if row["kind"] == "legislators"
    ]
    if not specs:
        raise ValueError("No independent congressional crosswalk acquired")
    for spec in specs:
        if fingerprint(confined(manifest.parent, spec["path"])) != {
            "sha256": spec["sha256"],
            "bytes": spec["bytes"],
        }:
            raise ValueError(f"Crosswalk changed: {spec['id']}")
    return FeatureSources({"sources": specs}, manifest.parent), specs


def anchor(query, crosswalk):
    ids = crosswalk.fec.get(query.get("D_fec_id"), set())
    if len(ids) != 1:
        return None, "missing_or_ambiguous_target_FEC_crosswalk"
    person = crosswalk.people[next(iter(ids))]
    if query.get("bioguide_id") and query["bioguide_id"] != person["id"]["bioguide"]:
        return None, "frozen_Bioguide_conflicts_with_target_FEC_crosswalk"
    if not crosswalk.matches_person(
        {"name": query.get("D_name") or "", "state": query["state"]}, person
    ):
        return None, "target_name_or_state_conflicts_with_crosswalk"
    return person, "unique_target_FEC_name_state_crosswalk"


def review_alias(query, donor, source_rows, person, crosswalk):
    if not donor.get("name_screen", "").startswith("manual_alias_review_required"):
        return {"status": "not_required", "model_ready": False}
    aliases = crosswalk.aliases(person) if person else []
    observations = []
    for number in donor["source_rows"]:
        row = source_rows.get(number)
        if (
            row is None
            or row["Cand.ID"] != query.get("D_fec_id")
            or row["state"] != query["state"]
            or row["party"] != "100"
            or row["recipient.type"] != "cand"
            or row["bonica.rid"] != donor["bonica_rid"]
            or float(row["cycle"]) != donor["cycle"]
        ):
            raise ValueError("Donor alias evidence does not match the selected source identity")
        literal = f"{row['ffname']} {row['lname']}"
        observations.append(
            {
                "source_id": "dime-recipients",
                "source_row": number,
                "literal_name": literal,
                "crosswalk_alias_match": bool(aliases)
                and name_matches(literal, *aliases[0], aliases[1:]),
            }
        )
    corroborated = (
        bool(observations)
        and person is not None
        and all(row["crosswalk_alias_match"] for row in observations)
    )
    return {
        "status": (
            "independently_corroborated_alias"
            if corroborated
            else "unresolved_literal_alias; no_nickname_imputation"
        ),
        "observations": observations,
        "crosswalk_evidence": person["evidence"] if person else None,
        "model_ready": False,
    }


def review_lead(query, lead, person, crosswalk):
    if (
        lead["contest_id"] != query["contest_id"]
        or lead["target_fec_id"] != query.get("D_fec_id")
        or lead["target_name"] != query.get("D_name")
        or lead["state"] != query["state"]
        or lead["source_candidate_id"] == query.get("D_fec_id")
    ):
        raise ValueError("Alternate-ID lead does not belong to the target candidate")
    source_ids = crosswalk.fec.get(lead["source_candidate_id"], set())
    if person is None:
        status = "held; target_identity_not_independently_anchored"
    elif source_ids != {person["id"]["bioguide"]}:
        status = "held; alternate_ID_has_no_unique_same_person_crosswalk"
    else:
        aliases = crosswalk.aliases(person)
        status = (
            "independent_FEC_Bioguide_FEC_bridge"
            if name_matches(lead["source_name"], *aliases[0], aliases[1:])
            else "held; alternate_source_name_conflicts_with_crosswalk"
        )
    return {
        **lead,
        "identity_review_status": status,
        "crosswalk_evidence": person["evidence"] if person else None,
        "identity_evidence_not_score_qualification": True,
        "model_ready": False,
    }


def build(queries_path, expansion_path, donor_rows_path, manifest, output):
    frozen = [row for row in read_queries(queries_path) if row["year"] == 2026]
    expansion = read_queries(expansion_path)
    if len(frozen) != 470:
        raise ValueError("Identity review requires the complete frozen 470-contest universe")
    if {row["contest_id"] for row in frozen} != {row["contest_id"] for row in expansion}:
        raise ValueError("Source expansion does not retain exactly the frozen 2026 universe")
    frozen_by_id = {row["contest_id"]: row for row in frozen}
    with gzip.open(donor_rows_path, "rt") as handle:
        donor_rows = [json.loads(line) for line in handle]
    by_number = {row["source_row"]: row for row in donor_rows}
    if len(by_number) != len(donor_rows):
        raise ValueError("Duplicate original donor source row")
    crosswalk, specs = load_crosswalk(manifest)
    reviewed = []
    for expanded in expansion:
        query = frozen_by_id[expanded["contest_id"]]
        if (
            expanded["name"] != query.get("D_name")
            or expanded["fec_id"] != query.get("D_fec_id")
            or expanded["state"] != query["state"]
        ):
            raise ValueError("Source-expansion target conflicts with frozen identity")
        person, status = anchor(query, crosswalk)
        reviewed.append(
            {
                "contest_id": query["contest_id"],
                "name": query.get("D_name"),
                "fec_id": query.get("D_fec_id"),
                "state": query["state"],
                "chamber": query["chamber"],
                "bioguide_id": person["id"]["bioguide"] if person else None,
                "anchor_status": status,
                "exact_ID_alias_review": review_alias(
                    query, expanded["dime"], by_number, person, crosswalk
                ),
                "alternate_ID_reviews": [
                    review_lead(query, lead, person, crosswalk)
                    for lead in expanded["dime_cross_office_leads"]
                ],
                "model_ready": False,
            }
        )
    output.mkdir(parents=True, exist_ok=True)
    write_rows(output / "candidate-identity-queries.jsonl.gz", reviewed)
    summary = {
        "year": 2026,
        "publication_status": "withdrawn; identity_evidence_only",
        "contests": len(reviewed),
        "alias_status_counts": dict(
            Counter(row["exact_ID_alias_review"]["status"] for row in reviewed)
        ),
        "alternate_ID_status_counts": dict(
            Counter(
                lead["identity_review_status"]
                for row in reviewed
                for lead in row["alternate_ID_reviews"]
            )
        ),
        "contests_with_independent_alternate_ID_bridge": sum(
            any(
                lead["identity_review_status"] == "independent_FEC_Bioguide_FEC_bridge"
                for lead in row["alternate_ID_reviews"]
            )
            for row in reviewed
        ),
        "new_model_ready_scores": 0,
        "inputs": {
            path.as_posix(): fingerprint(path)
            for path in (queries_path, expansion_path, donor_rows_path, manifest)
        },
        "independent_crosswalk_sources": specs,
        "limitations": [
            "A verified identity bridge does not validate donor-score vintage or comparability.",
            "No new scores, demographic labels, regressions or website publication.",
            "Missing aliases are not filled with assumed nicknames or name-only matches.",
        ],
    }
    write_json(output / "summary.json", summary)
    return summary


def package(queries_path, expansion_path, donor_rows_path, manifest, output, destination):
    root = Path.cwd().resolve()
    _, specs = load_crosswalk(manifest)
    entries = {}
    paths = [
        queries_path,
        expansion_path,
        donor_rows_path,
        manifest,
        Path("README.md"),
        Path("pyproject.toml"),
        Path("requirements.lock"),
        Path("tests/test_candidate_identity_review.py"),
        output / "candidate-identity-queries.jsonl.gz",
        output / "summary.json",
        *Path("which_candidate").glob("*.py"),
        *Path("docs").glob("*.md"),
        *(confined(manifest.parent, spec["path"]) for spec in specs),
    ]
    for path in paths:
        relative = path.resolve().relative_to(root).as_posix()
        entries[relative] = path
    destination.parent.mkdir(parents=True, exist_ok=True)
    write_zip(destination, entries)
    return {"members": len(entries), **fingerprint(destination)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--queries",
        type=Path,
        default=Path("results/2026-v3/analysis/candidate-queries.jsonl.gz"),
    )
    parser.add_argument(
        "--expansion",
        type=Path,
        default=Path("results/2026-source-expansion/candidate-queries.jsonl.gz"),
    )
    parser.add_argument(
        "--donor-rows",
        type=Path,
        default=Path("results/2026-source-expansion/dime-matched-source-rows.jsonl.gz"),
    )
    parser.add_argument("--manifest", type=Path, default=Path("data/research-sources.json"))
    parser.add_argument("--output", type=Path, default=Path("results/2026-identity-review"))
    parser.add_argument("--package", type=Path, help="Create a complete identity-review replay ZIP")
    args = parser.parse_args()
    summary = build(args.queries, args.expansion, args.donor_rows, args.manifest, args.output)
    if args.package:
        summary = {
            **summary,
            "replay_package": package(
                args.queries,
                args.expansion,
                args.donor_rows,
                args.manifest,
                args.output,
                args.package,
            ),
        }
    print(
        json.dumps(
            summary,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
