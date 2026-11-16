"""Freeze V3 before a bounded, requirements-led V4 source acquisition."""

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from .house_characteristics import TRAITS, write_csv
from .storage import fingerprint, json_bytes, read_rows, write_json

BASELINE = "data/house-characteristics-v4-baseline.json"
QUEUE = "data/house-characteristics-v4-queue.csv"
ACQUISITIONS = "data/house-characteristics-v4-acquisitions.json"
BASE_COMMIT = "aaf20ef27227f783a2083ed353ca1aecfdbcfeea"


def freeze(root):
    root = Path(root)
    if (root / BASELINE).exists():
        return json.loads((root / BASELINE).read_text())
    old = json.loads((root / "data/house-characteristics-v3-baseline.json").read_text())
    protected = dict(old["protected_sha256"])
    for folder in ("results/house-characteristics-v3", "publication/characteristics-v3"):
        protected.update(
            (p.relative_to(root).as_posix(), fingerprint(p)["sha256"])
            for p in (root / folder).rglob("*")
            if p.is_file()
        )
    for name in (
        "docs/HOUSE_CHARACTERISTICS_V3_SPEC.md",
        "data/house-characteristics-v3-baseline.json",
        "data/house-characteristics-v3-queue.csv",
        "data/house-characteristics-v3-acquisitions.json",
        "audits/house-characteristics-v3-validation.json",
    ):
        protected[name] = fingerprint(root / name)["sha256"]
    traits = read_rows(root / "results/house-characteristics-v3/candidate-traits.jsonl.gz")
    candidates = read_rows(root / "results/house/candidates.jsonl.gz")
    inputs = read_rows(root / "results/house/source-inputs.jsonl.gz")[0]
    with (root / "results/house-characteristics-v3/selection.csv").open() as stream:
        selected = {(r["contest_id"], r["name"], r["trait"]): r for r in csv.DictReader(stream)}
    inc = {r["candidate_id"]: r for r in traits if r["trait"] == "incumbency"}
    rows = []
    for row in traits:
        if row["party"] != "Democratic":
            continue
        group = (
            "incumbent"
            if inc[row["candidate_id"]]["analysis_value"] is True
            else "nonincumbent"
            if inc[row["candidate_id"]]["analysis_value"] is False
            else "unknown_incumbency"
        )
        rows.append(
            {
                k: row[k]
                for k in ("candidate_id", "contest_id", "name", "state", "district", "trait")
            }
            | {
                "performance_eligible": row["performance_eligible"],
                "incumbency_group": group,
                "factual_status": row["status"],
                "factual_qualified": row["factual_qualified"],
                "analysis_eligible": row["analysis_eligible"],
                "needs_source_evidence": row["status"] == "unknown",
                "needs_coding_or_timing": not row["analysis_eligible"]
                and row["status"] not in {"unknown", "inapplicable"},
                "age_interval_separate": row["uncertainty"].get("age_years_interval"),
                "factual_requirement": row["eligibility_reason"],
                "v3_selection_reason": selected.get(
                    (row["contest_id"], row["name"], row["trait"]), {}
                ).get("reason"),
                "opponent_incumbency_unresolved": row["R_incumbency_control"] is None,
                "priority": 0
                if row["trait"] == "incumbency" and group == "unknown_incumbency"
                else 1
                if row["performance_eligible"] and not row["analysis_eligible"]
                else 2,
            }
        )
    rows.sort(
        key=lambda r: (
            r["priority"],
            r["incumbency_group"] == "incumbent",
            r["state"],
            r["name"],
            r["trait"],
        )
    )
    write_csv(root / QUEUE, rows)
    assert len(rows) == 449 * len(TRAITS) == 6735
    result = {
        "baseline_commit": BASE_COMMIT,
        "protected_sha256": protected,
        "historical_reviewed_observations": {
            r["observation_id"]: hashlib.sha256(json_bytes(r)).hexdigest()
            for r in inputs["reviewed_characteristic_observations"]
        },
        "candidate_identity_sha256": hashlib.sha256(
            json_bytes(
                [
                    {
                        k: c[k]
                        for k in (
                            "candidate_id",
                            "contest_id",
                            "name",
                            "state",
                            "district",
                            "party",
                        )
                    }
                    for c in candidates
                ]
            )
        ).hexdigest(),
        "democrats": 449,
        "eligible_democrats": len({r["candidate_id"] for r in rows if r["performance_eligible"]}),
        "trait_cells": len(rows),
        "traits": list(TRAITS),
        "incumbency_groups": dict(
            Counter(r["incumbency_group"] for r in rows if r["trait"] == "incumbency")
        ),
        "eligible_incumbency_groups": dict(
            Counter(
                r["incumbency_group"]
                for r in rows
                if r["trait"] == "incumbency" and r["performance_eligible"]
            )
        ),
        "queue": fingerprint(root / QUEUE),
        "baseline_inputs": {
            name: fingerprint(root / name)
            for name in (
                "results/house-characteristics-v3/candidate-traits.jsonl.gz",
                "results/house-characteristics-v3/remaining-gaps.csv",
                "results/house-characteristics-v3/selection.csv",
                "results/house/source-inputs.jsonl.gz",
            )
        },
    }
    write_json(root / BASELINE, result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    result = freeze(args.root)
    print(json.dumps({k: v for k, v in result.items() if k != "protected_sha256"}, indent=2))
