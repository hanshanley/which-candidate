"""Freeze V7 and maintain separate national evidence and support queues."""

import json
from pathlib import Path

from .characteristics_v5_acquisition import freeze as previous_freeze
from .house_characteristics import write_csv
from .storage import fingerprint, read_rows, write_json

BASELINE = "data/house-characteristics-v8-baseline.json"
QUEUE = "data/house-characteristics-v8-queue.csv"
ACQUISITIONS = "data/house-characteristics-v8-acquisitions.json"
PREVIOUS = "results/house-characteristics-v7"
BASE_COMMIT = "08339cadd6a895de29d8418c22ee337aa7e7a50a"


def freeze(root):
    root = Path(root)
    if (root / BASELINE).exists():
        return json.loads((root / BASELINE).read_text())
    baseline = previous_freeze(root, version=8, baseline_commit=BASE_COMMIT)
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
        identity = any(
            word in f"{r['coding_status']} {r['eligibility_reason']}".casefold()
            for word in ("conflict", "identity hold", "ambiguous", "discordant")
        )
        missing = r["status"] == "unknown"
        held = not r["analysis_eligible"] and r["status"] not in {"unknown", "inapplicable"}
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
                    "performance_eligible",
                    "factual_qualified",
                    "analysis_eligible",
                    "coding_status",
                    "timing_status",
                    "eligibility_reason",
                )
            }
            | {
                "baseline_incumbency_group": group,
                "factual_status": r["status"],
                "no_evidence": missing,
                "identity_or_conflict": held and identity,
                "timing_or_coding": held and not identity,
                "missing_comparison_support": fits[r["trait"]]["status"] != "estimated",
                "opponent_incumbency_unresolved": r["R_incumbency_control"] is None,
                "priority": (
                    0
                    if r["party"] == "Democratic"
                    and r["performance_eligible"]
                    and group != "incumbent"
                    and missing
                    else 1
                    if r["trait"] == "incumbency" and not inc["analysis_eligible"]
                    else 2
                    if r["party"] == "Democratic" and group != "incumbent" and (missing or held)
                    else 3
                    if r["party"] == "Democratic" and (missing or held)
                    else 4
                ),
            }
        )
    rows.sort(key=lambda r: (r["priority"], r["state"], r["name"], r["trait"]))
    assert len(rows) == 1284 * 15
    write_csv(root / QUEUE, rows)
    for name in (
        "no_evidence",
        "identity_or_conflict",
        "timing_or_coding",
        "missing_comparison_support",
    ):
        write_csv(
            root / f"data/house-characteristics-v8-queue-{name.replace('_', '-')}.csv",
            [r for r in rows if r[name]],
        )
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
