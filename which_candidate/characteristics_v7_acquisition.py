"""Freeze V6 and triage every candidate-trait cell before source acquisition."""

import json
from pathlib import Path

from .characteristics_v5_acquisition import freeze as previous_freeze
from .house_characteristics import write_csv
from .storage import fingerprint, read_rows, write_json

BASELINE = "data/house-characteristics-v7-baseline.json"
QUEUE = "data/house-characteristics-v7-queue.csv"
ACQUISITIONS = "data/house-characteristics-v7-acquisitions.json"
PREVIOUS = "results/house-characteristics-v6"
BASE_COMMIT = "02b37ca0093cd75f084c501816b2f61616f38d90"


def freeze(root):
    root = Path(root)
    if (root / BASELINE).exists():
        return json.loads((root / BASELINE).read_text())
    baseline = previous_freeze(root, version=7, baseline_commit=BASE_COMMIT)
    traits = read_rows(root / PREVIOUS / "candidate-traits.jsonl.gz")
    fits = {r["trait"]: r for r in read_rows(root / PREVIOUS / "fits.jsonl.gz")}
    incumbency = {r["candidate_id"]: r for r in traits if r["trait"] == "incumbency"}
    rows = []
    for r in traits:
        inc = incumbency[r["candidate_id"]]
        group = (
            "unresolved"
            if not inc["analysis_eligible"]
            else "incumbent"
            if inc["analysis_value"]
            else "nonincumbent"
        )
        missing = r["status"] == "unknown"
        qualification = not r["analysis_eligible"] and r["status"] not in {
            "unknown",
            "inapplicable",
        }
        support = fits[r["trait"]]["status"] != "estimated"
        rows.append(
            {
                k: r[k]
                for k in (
                    "candidate_id",
                    "contest_id",
                    "name",
                    "state",
                    "district",
                    "party",
                    "trait",
                )
            }
            | {
                "performance_eligible": r["performance_eligible"],
                "baseline_incumbency_group": group,
                "factual_status": r["status"],
                "factual_qualified": r["factual_qualified"],
                "analysis_eligible": r["analysis_eligible"],
                "no_source_observation": missing,
                "identity_timing_coding_or_conflict_hold": qualification,
                "contrast_support_missing": support,
                "qualification_requirement": r["eligibility_reason"],
                "coding_status": r["coding_status"],
                "timing_status": r["timing_status"],
                "opponent_incumbency_unresolved": r["R_incumbency_control"] is None,
                "comparison_requirement": (
                    "Explicit nonservice and positive service, never absence from biographies"
                    if r["trait"] in {"military", "prior_elected_office", "other_government"}
                    else "Source-defined explicit classifications with adequate category/state support"
                    if support
                    else "Existing supported contrast; preserve unknowns and full-population failures"
                ),
                "priority": (
                    0
                    if r["party"] == "Democratic"
                    and r["performance_eligible"]
                    and missing
                    and group != "incumbent"
                    else 1
                    if r["party"] == "Democratic"
                    and r["trait"] == "incumbency"
                    and not inc["analysis_eligible"]
                    else 2
                    if r["party"] == "Democratic"
                    and r["performance_eligible"]
                    and (qualification or support)
                    and group != "incumbent"
                    else 3
                    if r["party"] == "Democratic" and (missing or qualification)
                    else 4
                    if r["party"] == "Republican" and r["R_incumbency_control"] is None
                    else 5
                ),
            }
        )
    rows.sort(key=lambda r: (r["priority"], r["state"], r["name"], r["trait"]))
    assert len(rows) == 1284 * 15
    write_csv(root / QUEUE, rows)
    baseline.update(all_candidates=1284, trait_cells=len(rows), queue=fingerprint(root / QUEUE))
    write_json(root / BASELINE, baseline)
    return baseline


if __name__ == "__main__":
    result = freeze(Path(__file__).resolve().parents[1])
    print(
        json.dumps(
            {
                k: result[k]
                for k in (
                    "baseline_commit",
                    "all_candidates",
                    "democrats",
                    "eligible_democrats",
                    "trait_cells",
                )
            },
            indent=2,
        )
    )
