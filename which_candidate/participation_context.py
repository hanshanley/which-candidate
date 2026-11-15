"""Import public aggregate participation context without changing candidate models."""

import argparse
import gzip
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .corrected import same_name
from .pipeline import csv_bytes
from .rebuild import ROOT
from .storage import fingerprint, json_bytes, read_rows, write_json, write_rows

PACKET = "data/participation-source-inputs.json"
OUTPUT = "results/participation"
INPUTS = {
    "counts": "data/results-intake/baseline/counts/current.json.gz",
    "house": "data/results-intake/baseline/house/current-candidate-queries.json",
    "official": "data/official-native-products/20261113-hi-wy-house.json",
    "maine": "data/participation-house-round-context/20261114-01/source-facts.json",
    "maine_review": "data/participation-house-round-context/20261114-01/observations.json",
    "qualification": (
        "data/participation-access/20261115-current-source-qualification-01/observations.json"
    ),
}
CONTRACTS = {
    "counts": "participation.current_snapshot.v1",
    "official": "participation.reviewed_official_house_queries.v1",
    "maine": "participation.maine_house_round_source_facts.v1",
    "maine_review": "participation.house_round_context_delivery.v1",
}
QUALIFICATION = (
    "Retained source-defined aggregate context, not district turnout, candidate "
    "characteristics, unique voters or individual vote transfers. Regions, modes, "
    "demographic cells and snapshots are separate, not additive. No model inputs changed."
)


def pin_bytes(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def import_inputs(source, root=ROOT):
    source, root = Path(source), Path(root)
    revision = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
    ).strip()
    inputs = {}
    for key, relative in INPUTS.items():
        body = (source / relative).read_bytes()
        data = json.loads(gzip.decompress(body) if relative.endswith(".gz") else body)
        inputs[key] = {
            "path": relative,
            "original_file": pin_bytes(body),
            "normalized_payload": pin_bytes(json_bytes(data)),
            "data": data,
        }
    packet = {
        "schema": "which_candidate.participation_source_inputs.v1",
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "source_repository": "hanshanley/voter-participation",
        "source_revision": revision,
        "source_checkout_dirty": bool(
            subprocess.check_output(
                ["git", "-C", str(source), "status", "--porcelain"], text=True
            ).strip()
        ),
        "qualification": QUALIFICATION,
        "inputs": inputs,
    }
    validate_packet(packet)
    write_json(root / PACKET, packet)
    return {key: value["original_file"] for key, value in inputs.items()}


def validate_packet(packet):
    if packet["schema"] != "which_candidate.participation_source_inputs.v1":
        raise ValueError("Unsupported participation input packet")
    if set(packet["inputs"]) != set(INPUTS):
        raise ValueError("Participation input inventory changed")
    for key, entry in packet["inputs"].items():
        if entry["path"] != INPUTS[key]:
            raise ValueError("Participation input path changed")
        if pin_bytes(json_bytes(entry["data"])) != entry["normalized_payload"]:
            raise ValueError(f"Changed normalized participation input: {key}")
        if key in CONTRACTS and entry["data"]["contract"] != CONTRACTS[key]:
            raise ValueError(f"Unsupported participation source contract: {key}")
    data = {key: entry["data"] for key, entry in packet["inputs"].items()}
    if data["counts"]["snapshot"]["election_date"] != "2026-11-03":
        raise ValueError("Participation context requires the 2026 general election")
    if (
        data["maine"]["election_date"] != "2026-11-03"
        or data["maine"]["district"] != "ME-02"
        or data["maine"]["state_code"] != "ME"
        or data["maine"]["office"] != "house"
        or data["maine"]["party_labels_are_explicit_native_first_choice_markers"] is not True
        or data["qualification"]["all_51_estimate_eligibility_decisions"]["election_date"]
        != "2026-11-03"
    ):
        raise ValueError("Maine source context changed election or district")
    if (
        data["maine"]["raw_publisher_html_private_person_records_or_histories_included"]
        or data["maine_review"]["source_extraction_replayed"]
    ):
        raise ValueError("Expected public selected facts, not private records or original replay")
    return data


def count(value):
    if value is not None and (type(value) is not int or value < 0):
        raise ValueError("Source counts must be nonnegative integers or explicit unknowns")
    return value


def evidence(packet, key, pointer):
    entry = packet["inputs"][key]
    return {
        "source_repository": packet["source_repository"],
        "source_revision": packet["source_revision"],
        "source_checkout_dirty": packet["source_checkout_dirty"],
        "input_path": entry["path"],
        "input_original_file": entry["original_file"],
        "input_normalized_payload": entry["normalized_payload"],
        "json_pointer": pointer,
        "replay_scope": "pinned_normalized_public_facts_not_original_publisher_extraction",
    }


def aggregate_rows(packet, data):
    current = data["counts"]
    snapshot = current["snapshot"]
    sections = [
        ("early_voting", snapshot["early_voting"], "/snapshot/early_voting"),
        ("demographics", snapshot["demographics"], "/snapshot/demographics"),
        ("reporting", snapshot["reporting"], "/snapshot/reporting"),
        ("reviewed_states", current["reviewed_states"], "/reviewed_states"),
    ]
    result = []
    for section, rows, pointer in sections:
        for index, row in enumerate(rows):
            receipts = [
                receipt
                for receipt in snapshot["sources"]
                if receipt["url"] == row["source_url"]
                and receipt.get("snapshot_id") == row.get("source_snapshot")
            ]
            result.append(
                {
                    "observation_id": f"participation:{section}:{index}",
                    "state_code": row["state_code"],
                    "election_date": snapshot["election_date"],
                    "source_section": section,
                    "geography_level": (
                        "state_group"
                        if section == "demographics"
                        else row.get("geography_level", "state")
                    ),
                    "geography": row.get("geography", row.get("county", "STATEWIDE")),
                    "mode": row.get("mode"),
                    "dimension": row.get("dimension"),
                    "group": row.get("group"),
                    "reported_count": count(row.get("ballots")),
                    "source_denominator": row.get("denominator"),
                    "source_denominator_basis": row.get("denominator_basis"),
                    "source_date": row.get("source_date"),
                    "source_update_label": row.get("source_update_label"),
                    "source_retrieved_at": row.get("source_retrieved_at"),
                    "source_url": row["source_url"],
                    "original_source_receipts": receipts,
                    "source_record": row,
                    "evidence": evidence(packet, "counts", f"{pointer}/{index}"),
                    "analytical_turnout_pct": None,
                    "district_join_qualified": False,
                    "model_ready": False,
                    "qualification": QUALIFICATION,
                }
            )
    return result


def house_rows(packet, data):
    result = []
    for index, row in enumerate(data["house"]):
        policies = [
            policy
            for policy in data["official"]["sources"]
            if policy["url"] == row["source_url"] and policy["state_code"] == row["state_code"]
        ]
        if not policies:
            continue
        if (
            len(policies) != 1
            or row["year"] != "2026"
            or row["office"] != "U.S. House"
            or policies[0]["stage"] != "general"
            or policies[0]["year"] != "2026"
            or policies[0]["office"] != "U.S. House"
            or policies[0]["kind"] not in ("candidate_records", "wide_candidate_control")
        ):
            raise ValueError("Ambiguous official House source context")
        policy = policies[0]
        districts = (
            [binding["district"] for binding in policy["districts"].values()]
            if policy["kind"] == "candidate_records"
            else [policy["district"]]
        )
        if row["district"] not in districts:
            raise ValueError("House row outside the reviewed official district inventory")
        literal = row["votes"]
        if not isinstance(literal, str) or not re.fullmatch(r"[0-9]+", literal):
            raise ValueError("Official votes must be explicit integer literals")
        result.append(
            {
                "observation_id": f"house:official:{index}",
                "state_code": row["state_code"],
                "district": row["district"].split("-")[1],
                "election_date": "2026-11-03",
                "source_name": row["name"],
                "party": row["party"],
                "category": "candidate" if row["party"] else "unassigned_write_ins",
                "reported_count": count(int(literal)),
                "snapshot_id": "reviewed_official_general_snapshot",
                "source_round": None,
                "source_update_label": policy["native_updated_at"],
                "source_retrieved_at": policy["retrieved_at_utc"],
                "source_url": row["source_url"],
                "source_pin": policy["source_pin"],
                "source_query_pin": data["official"]["query_pin"],
                "qualification": policy["count_scope"] + " " + QUALIFICATION,
                "evidence": evidence(packet, "house", f"/{index}"),
                "source_record": row,
                "source_policy": policy,
                "model_ready": False,
            }
        )
    for policy in data["official"]["sources"]:
        actual = [r for r in result if r["source_url"] == policy["url"]]
        expected = (
            sum(len(binding["candidate_ids"]) for binding in policy["districts"].values())
            if policy["kind"] == "candidate_records"
            else len(policy["candidates"])
        )
        if len(actual) != expected:
            raise ValueError("Incomplete official House candidate-choice inventory")
    for index, snapshot in enumerate(data["maine"]["snapshots"]):
        for category, value in snapshot["counts"].items():
            native_url = snapshot.get("source_url")
            result.append(
                {
                    "observation_id": f"house:ME:02:{snapshot['id']}:{category}",
                    "state_code": "ME",
                    "district": "02",
                    "election_date": "2026-11-03",
                    "source_name": data["maine"]["candidate_names"].get(category),
                    "party": {"D": "Democratic", "R": "Republican"}.get(category),
                    "category": category,
                    "reported_count": count(value),
                    "snapshot_id": snapshot["id"],
                    "source_round": snapshot.get("source_round"),
                    "source_update_label": snapshot["native_count_clock"],
                    "source_retrieved_at": (
                        data["maine_review"]["primary_source"]["retrieved_at_utc"]
                        if native_url == data["maine_review"]["primary_source"]["url"]
                        else None
                    ),
                    "source_url": native_url or snapshot["source_urls"][0],
                    "source_pin": snapshot.get("source_pin"),
                    "publication_date": snapshot.get("publication_date"),
                    "source_percent_literal": snapshot["native_percent_literals"][category],
                    "qualification": data["maine"]["qualification"]["reason"] + " " + QUALIFICATION,
                    "source_record": snapshot,
                    "evidence": evidence(packet, "maine", f"/snapshots/{index}/counts/{category}"),
                    "model_ready": False,
                }
            )
    return result


def result_matches(rows, candidates):
    for row in rows:
        row.update(candidate_id=None, contest_id=None, raw_difference_from_pinned_votes=None)
        if row["election_date"] != "2026-11-03":
            row["identity_status"] = "held_different_election"
            continue
        if not row["source_name"] or not row["party"]:
            row["identity_status"] = "nonperson_or_unassigned_category_not_a_candidate"
            continue
        name = re.sub(r"^\([A-Z]+\)\s*|\s*\([A-Z]+\)$", "", row["source_name"]).strip()
        contest = f"2026:house:{row['state_code']}:{row['district']}:general:source_general"
        matches = [
            candidate
            for candidate in candidates
            if candidate["contest_id"] == contest
            and candidate["state"] == row["state_code"]
            and candidate["district"] == row["district"]
            and candidate["party"] == row["party"]
            and same_name(candidate["name"], name)
        ]
        if len(matches) != 1:
            row["identity_status"] = "ambiguous_match" if matches else "unmatched_identity"
            continue
        candidate = matches[0]
        row.update(
            candidate_id=candidate["candidate_id"],
            contest_id=candidate["contest_id"],
            identity_status="unique_name_party_district_election_candidate_record",
            raw_difference_from_pinned_votes=(
                row["reported_count"] - candidate["votes"]
                if row["reported_count"] is not None and candidate["votes"] is not None
                else None
            ),
        )
    groups = defaultdict(list)
    for row in rows:
        if row["candidate_id"]:
            groups[(row["candidate_id"], row["contest_id"], row["snapshot_id"])].append(row)
    for duplicates in groups.values():
        if len(duplicates) > 1:
            for row in duplicates:
                row.update(
                    candidate_id=None,
                    contest_id=None,
                    raw_difference_from_pinned_votes=None,
                    identity_status="ambiguous_source_rows_for_candidate",
                )
    return rows


def build(root=ROOT, output=None):
    root = Path(root)
    packet_path = root / PACKET
    if not packet_path.exists():
        return None
    packet = json.loads(packet_path.read_bytes())
    data = validate_packet(packet)
    candidates = read_rows(root / "results/house/candidates.jsonl.gz")
    aggregates = aggregate_rows(packet, data)
    results = result_matches(house_rows(packet, data), candidates)
    decisions = data["qualification"]["all_51_source_decisions"]
    coverage = data["counts"]["snapshot"]["coverage"]
    if len({r["state_code"] for r in decisions}) != len(decisions) or {
        r["state_code"] for r in decisions
    } != {r["state_code"] for r in coverage}:
        raise ValueError("Participation state coverage and qualification decisions disagree")
    states = []
    for decision in decisions:
        rows = [r for r in aggregates if r["state_code"] == decision["state_code"]]
        states.append(
            {
                "state_context_id": f"2026:{decision['state_code']}",
                "state_code": decision["state_code"],
                "statewide_observations": [
                    r for r in rows if r["geography_level"] in ("state", "statewide")
                ],
                "regional_observations": sum(
                    r["geography_level"] not in ("state", "statewide", "state_group") for r in rows
                ),
                "demographic_observations": [
                    r for r in rows if r["source_section"] == "demographics"
                ],
                "source_intake_decision": decision,
                "qualification": QUALIFICATION,
                "model_ready": False,
            }
        )
    known = {r["state_code"] for r in states}
    if any(r["state_code"] not in known for r in aggregates):
        raise ValueError("Aggregate observation has no state coverage decision")
    summary = {
        "source_repository": packet["source_repository"],
        "source_revision": packet["source_revision"],
        "source_checkout_dirty": packet["source_checkout_dirty"],
        "imported_at": packet["imported_at"],
        "state_coverage_decisions": len(states),
        "aggregate_observations": len(aggregates),
        "aggregate_sections": dict(Counter(r["source_section"] for r in aggregates)),
        "states_with_aggregate_observations": len({r["state_code"] for r in aggregates}),
        "house_result_observations": len(results),
        "house_districts": len({(r["state_code"], r["district"]) for r in results}),
        "candidate_records_with_supplementary_results": len(
            {(r["candidate_id"], r["contest_id"]) for r in results if r["candidate_id"]}
        ),
        "matched_house_result_observations": sum(bool(r["candidate_id"]) for r in results),
        "house_identity_decisions": dict(Counter(r["identity_status"] for r in results)),
        "new_background_observations": 0,
        "new_background_coverage": 0,
        "model_inputs_changed": False,
        "qualification": QUALIFICATION,
    }
    output = Path(output) if output else root / OUTPUT
    output.mkdir(parents=True, exist_ok=True)
    for name, rows in (
        ("aggregate-observations", aggregates),
        ("house-source-results", results),
        ("state-context", states),
    ):
        write_rows(output / f"{name}.jsonl.gz", rows)
        (output / f"{name}.csv").write_bytes(csv_bytes(rows))
    write_json(output / "summary.json", summary)
    write_json(
        output / "manifest.json",
        {
            "schema": "which_candidate.participation_context.v1",
            "inputs": {
                PACKET: fingerprint(packet_path),
                "results/house/candidates.jsonl.gz": fingerprint(
                    root / "results/house/candidates.jsonl.gz"
                ),
            },
            "files": {
                path.name: fingerprint(path)
                for path in sorted(output.iterdir())
                if path.name != "manifest.json"
            },
        },
    )
    return summary


def attach(root, profiles):
    root = Path(root)
    if not (root / PACKET).exists():
        return None
    manifest = json.loads((root / OUTPUT / "manifest.json").read_bytes())
    for relative, receipt in manifest["inputs"].items():
        if fingerprint(root / relative) != receipt:
            raise ValueError("Stale participation inputs; rebuild participation_context first")
    for name, receipt in manifest["files"].items():
        if fingerprint(root / OUTPUT / name) != receipt:
            raise ValueError(f"Changed participation output: {name}")
    states = {r["state_code"]: r for r in read_rows(root / OUTPUT / "state-context.jsonl.gz")}
    matches = defaultdict(list)
    for row in read_rows(root / OUTPUT / "house-source-results.jsonl.gz"):
        if row["candidate_id"]:
            matches[(row["candidate_id"], row["contest_id"])].append(row)
    for profile in profiles:
        contest = f"2026:house:{profile['state']}:{profile['district']}:general:source_general"
        if profile["contest_id"] != contest:
            continue
        state = states.get(profile["state"])
        if state is None:
            continue
        profile["participation_source_context"] = {
            "state_context_id": state["state_context_id"],
            "statewide_observations": len(state["statewide_observations"]),
            "regional_observations": state["regional_observations"],
            "demographic_observations": len(state["demographic_observations"]),
            "house_source_results": matches.get(
                (profile["candidate_id"], profile["contest_id"]), []
            ),
            "model_ready": False,
            "qualification": QUALIFICATION,
        }
    return json.loads((root / OUTPUT / "summary.json").read_bytes())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--import-from", type=Path)
    args = parser.parse_args()
    if args.import_from:
        import_inputs(args.import_from, args.root)
    print(json.dumps(build(args.root), indent=2))
