"""Check V9 coverage and reuse the frozen independent numerical reconstruction."""

import argparse
import csv
import json
import runpy
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from which_candidate.storage import fingerprint, read_rows  # noqa: E402


def validate():
    out = ROOT / "results/house-characteristics-v9"
    previous = read_rows(ROOT / "results/house-characteristics-v8/candidate-traits.jsonl.gz")
    current = read_rows(out / "candidate-traits.jsonl.gz")
    old = {(r["candidate_id"], r["trait"]): r for r in previous}
    new = {(r["candidate_id"], r["trait"]): r for r in current}
    assert len(current) == len(new) == 1284 * 15
    assert new.keys() == old.keys()
    baseline = json.loads((ROOT / "data/house-characteristics-v9-baseline.json").read_text())
    for name, digest in baseline["protected_sha256"].items():
        assert fingerprint(ROOT / name)["sha256"] == digest, name
    with (out / "v8-v9-trait-progress.csv").open() as stream:
        progress = list(csv.DictReader(stream))
    for record in progress:
        trait = record["trait"]
        rows = [r for r in current if r["party"] == "Democratic" and r["trait"] == trait]
        assert len(rows) == int(record["cohort_denominator"]) == 449
        for suffix, sample in (
            ("before", [old[(r["candidate_id"], trait)] for r in rows]),
            ("after", rows),
        ):
            assert sum(r["factual_qualified"] for r in sample) == int(record[f"factual_{suffix}"])
            assert sum(r["analysis_eligible"] for r in sample) == int(
                record[f"analytical_{suffix}"]
            )
        assert sum(not r["factual_qualified"] for r in rows) == int(
            record["no_qualified_factual_value"]
        )
        assert sum(r["status"] == "unknown" for r in rows) == int(record["unknown_after"])
        assert sum(r["status"] == "inapplicable" for r in rows) == int(
            record["structurally_inapplicable"]
        )
    with (out / "coverage-by-party-and-incumbency.csv").open() as stream:
        grouped = list(csv.DictReader(stream))
    for trait in {r["trait"] for r in current}:
        subset = [r for r in grouped if r["trait"] == trait]
        assert sum(int(r["candidates"]) for r in subset) == 1284
        assert sum(int(r["candidates"]) for r in subset if r["party"] == "Democratic") == 449
        for field in ("factual", "analysis"):
            key = "factual_qualified" if field == "factual" else "analysis_eligible"
            assert sum(int(r[f"{field}_after"]) for r in subset) == sum(
                r[key] for r in current if r["trait"] == trait
            )
    summary = json.loads((out / "summary.json").read_text())
    observations = read_rows(ROOT / "results/house/source-inputs.jsonl.gz")[0][
        "reviewed_characteristic_observations"
    ]
    acquired_facts = {
        (r["candidate_id"], r["trait"])
        for r in observations
        if r["source_id"].startswith("v9-") and r["v9_review"]["factual_qualified"]
    }
    first = {
        key
        for key, row in new.items()
        if key in acquired_facts and old[key]["status"] == "unknown" and row["factual_qualified"]
    }
    assert len(first) == summary["newly_informed_candidate_trait_fields"]
    assert len({key[0] for key in first}) == summary["newly_informed_candidates"]
    assert summary["D_unknown_incumbency_after"] == 0
    assert summary["control_unlocked_contests"] == ["2026:house:SC:02:general:source_general"]
    military = Counter(
        r["analysis_value"]
        for r in current
        if r["party"] == "Democratic" and r["trait"] == "military" and r["analysis_eligible"]
    )
    assert military == {True: 36, False: 1}
    kaylee = [r for r in current if r["name"] == "Kaylee Peterson" and r["trait"] == "age"]
    assert len(kaylee) == 1 and not kaylee[0]["analysis_eligible"]
    queues = []
    for name in ("no-evidence", "identity-or-conflict", "timing-or-coding"):
        with (out / f"remaining-{name}.csv").open() as stream:
            queues.append({(r["candidate_id"], r["trait"]) for r in csv.DictReader(stream)})
    assert all(not a & b for index, a in enumerate(queues) for b in queues[index + 1 :])
    frozen = runpy.run_path(str(ROOT / "scripts/validate-characteristics-v8.py"))
    # The frozen checker has a fixed input directory, but unchanged numerical contracts.
    # A disposable compatibility copy checks V9 without editing V8 or invoking the fitter.
    with tempfile.TemporaryDirectory(prefix="which-candidate-v9-independent-") as directory:
        compatible = Path(directory)
        shutil.copytree(out, compatible / "results/house-characteristics-v8")
        checker = frozen["validate"]
        checker.__globals__["ROOT"] = compatible
        numerical = checker()
    return {
        "version": "house-characteristics-v9",
        "protected_frozen_files_verified": len(baseline["protected_sha256"]),
        "candidate_trait_cells_reconciled": len(current),
        "all_party_grouped_coverage_reconciles": True,
        "first_evidence_fields": len(first),
        "first_evidence_candidates": len({key[0] for key in first}),
        "remaining_D_incumbency_holds": 0,
        "military_positive_values": military[True],
        "military_explicit_negative_values": military[False],
        "undated_age_not_promoted": True,
        "first_three_queues_disjoint": True,
        **numerical,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    text = json.dumps(validate(), indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    print(text)
