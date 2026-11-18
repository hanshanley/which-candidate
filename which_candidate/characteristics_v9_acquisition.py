"""V8-preserving national continuation and evidence-directed cached-source review."""

import argparse
import json
import re
from pathlib import Path

from .characteristics_research import source_text
from .characteristics_v5_acquisition import freeze as freeze_previous
from .characteristics_v7_batch import acquire as acquire_sources
from .house_characteristics import write_csv
from .storage import fingerprint, read_rows, write_json

BASELINE = "data/house-characteristics-v9-baseline.json"
PLAN = "data/house-characteristics-v9-source-plan.json"
WORK = "artifacts/characteristics-v9"
PREVIOUS = "results/house-characteristics-v8"
BASE_COMMIT = "818d7fc1ce46e611193daf3afe05015bc395887f"
MARKERS = {
    "education": r"\b(?:graduat|bachelor|master|doctor|degree|diploma|university|college)\w*",
    "profession": r"\b(?:worked|career|occupation|profession|engineer|attorney|teacher|nurse)\w*",
    "prior_elected_office": r"\b(?:elected|council|mayor|legislat|never held|no prior)\w*",
    "other_government": r"\b(?:government|department|civil servant|public employee)\w*",
    "age": r"\b(?:born|birthday|years old|year-old|date of birth)\b",
    "religion": r"\b(?:faith|religion|christian|catholic|jewish|muslim|atheist|buddhist)\w*",
    "military": r"\b(?:military|veteran|army|navy|marine|air force|never served)\w*",
    "race": r"\b(?:african american|black|white|asian|native american)\b",
    "ethnicity": r"\b(?:hispanic|latino|latina|latinx)\b",
}


def freeze(root):
    root = Path(root)
    if (root / BASELINE).exists():
        return json.loads((root / BASELINE).read_text())
    baseline = freeze_previous(root, version=9, baseline_commit=BASE_COMMIT)
    for path in (root / "data").glob("house-characteristics-v8-*"):
        if path.is_file():
            baseline["protected_sha256"][path.relative_to(root).as_posix()] = fingerprint(path)[
                "sha256"
            ]
    path = root / "audits/house-characteristics-v8-release.json"
    baseline["protected_sha256"][path.relative_to(root).as_posix()] = fingerprint(path)["sha256"]
    traits = read_rows(root / PREVIOUS / "candidate-traits.jsonl.gz")
    incumbency = {r["candidate_id"]: r for r in traits if r["trait"] == "incumbency"}
    rows = []
    for row in traits:
        inc = incumbency[row["candidate_id"]]
        group = (
            "unresolved"
            if not inc["analysis_eligible"]
            else "incumbent"
            if inc["analysis_value"]
            else "nonincumbent"
        )
        rows.append(
            {
                k: row[k]
                for k in (
                    "candidate_id",
                    "contest_id",
                    "name",
                    "state",
                    "district",
                    "party",
                    "trait",
                    "status",
                    "factual_qualified",
                    "analysis_eligible",
                    "performance_eligible",
                    "coding_status",
                    "timing_status",
                    "eligibility_reason",
                )
            }
            | {
                "baseline_incumbency_group": group,
                "priority": (
                    0
                    if row["party"] == "Democratic"
                    and group != "incumbent"
                    and row["status"] == "unknown"
                    else 1
                    if row["trait"] == "incumbency" and not row["analysis_eligible"]
                    else 2
                    if row["party"] == "Democratic" and not row["factual_qualified"]
                    else 3
                ),
                "structurally_inapplicable": row["status"] == "inapplicable",
                "no_evidence": row["status"] == "unknown",
            }
        )
    rows.sort(key=lambda r: (r["priority"], r["state"], r["name"], r["trait"]))
    assert len(rows) == 1284 * 15
    write_csv(root / "data/house-characteristics-v9-national-queue.csv", rows)
    baseline.update(all_candidates=1284, national_trait_cells=len(rows))
    write_json(root / BASELINE, baseline)
    return baseline


def acquire(root, family=None):
    root = Path(root)
    sources = json.loads((root / PLAN).read_text())["sources"]
    return acquire_sources(
        root,
        sources={
            r["id"]: {k: v for k, v in r.items() if k != "id"}
            for r in sources
            if family is None or r["family"] == family
        },
        workdir=WORK,
    )


def audit_cached(root):
    """Produce reading leads, never automatically qualified claims."""
    root = Path(root)
    previous = json.loads((root / "data/house-characteristics-v8-acquisitions.json").read_text())
    used = {r["id"].removeprefix("v8-") for r in previous["documents"]}
    traits = read_rows(root / PREVIOUS / "candidate-traits.jsonl.gz")
    unknown = {}
    for row in traits:
        if not row["factual_qualified"]:
            unknown.setdefault(row["candidate_id"], set()).add(row["trait"])
    result = []
    for receipt in previous["discovery_dispositions"]:
        if receipt["status"] != "acquired" or receipt["id"] in used:
            continue
        path = root / receipt.get("cached_path", f"artifacts/characteristics-v8/{receipt['id']}")
        if not path.exists():
            result.append({"id": receipt["id"], "disposition": "original_cache_unavailable"})
            continue
        if fingerprint(path) != {k: receipt[k] for k in ("bytes", "sha256")}:
            raise ValueError(f"Changed retained source: {receipt['id']}")
        candidate = receipt.get("candidate_id", "")
        wanted = unknown.get(candidate, set())
        text = source_text(path.read_bytes(), {})
        excerpts = {
            trait: [
                text[max(0, m.start() - 150) : m.end() + 220]
                for m in list(re.finditer(pattern, text, re.I))[:8]
            ]
            for trait, pattern in MARKERS.items()
            if trait in wanted
        }
        excerpts = {k: v for k, v in excerpts.items() if v}
        result.append(
            {
                "id": receipt["id"],
                "candidate_id": candidate,
                "url": receipt["url"],
                "sha256": receipt["sha256"],
                "cached_path": str(path.relative_to(root)),
                "text_characters": len(text),
                "unqualified_factual_fields": sorted(wanted),
                "disposition": "concrete_unqualified_field_reading_lead"
                if excerpts
                else "no_unqualified_field_marker_not_proof_of_exhaustion",
                "reading_excerpts": excerpts,
            }
        )
    work = root / WORK
    work.mkdir(parents=True, exist_ok=True)
    write_json(work / "retained-unused-review.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acquire", action="store_true")
    parser.add_argument("--family")
    parser.add_argument("--audit-cached", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    result = freeze(root)
    print("Frozen V8 files:", len(result["protected_sha256"]))
    if args.acquire:
        print(json.dumps(acquire(root, args.family), indent=2))
    if args.audit_cached:
        result = audit_cached(root)
        print("Retained unused originals reviewed:", len(result))
