"""Resumable national acquisition; completed or denied originals are not retried."""

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urljoin

from .characteristics_v7_batch import acquire as acquire_sources

WORK = "artifacts/characteristics-v8"
PLAN = "data/house-characteristics-v8-source-plan.json"


def discover_washington(root):
    root = Path(root)
    index = root / WORK / "washington-pdfs-2026"
    value = json.loads((root / PLAN).read_text())
    existing = {r["id"] for r in value["sources"]}
    # These county editions jointly cover all ten congressional districts.
    # Statements repeated across county editions are deduplicated at extraction.
    for href in re.findall(r'href="([^"]+\.pdf[^"]*)"', index.read_text(), re.I):
        match = re.search(r"Edition%20(04|05|06|09|10|11|13|15)%20", href)
        if not match:
            # The index encodes a nonbreaking space after some edition numbers.
            match = re.search(r"Edition%20(04|05|06|09|10|11|13|15)%C2%A0", href)
        if not match:
            continue
        key = f"washington-edition-{match[1]}-2026"
        if key in existing:
            continue
        value["sources"].append(
            {
                "id": key,
                "family": "official-statements",
                "url": urljoin("https://www.sos.wa.gov/", href),
                "potential_fields": [
                    "education",
                    "profession",
                    "prior_elected_office",
                    "other_government",
                    "military",
                ],
                "expected_candidates": [
                    "Native congressional candidates actually printed; "
                    "elected-experience negatives require literal review"
                ],
            }
        )
        existing.add(key)
    from .storage import write_json

    write_json(root / PLAN, value)
    return value


def acquire(root, family=None):
    root = Path(root)
    planned = json.loads((root / PLAN).read_text())["sources"]
    supplement = root / "data/house-characteristics-v8-supplement-plan.json"
    if supplement.exists():
        planned += json.loads(supplement.read_text())["sources"]
    sources = {
        r["id"]: {k: v for k, v in r.items() if k != "id"}
        for r in planned
        if family is None or r["family"] == family
    }
    return acquire_sources(root, sources=sources, workdir=WORK)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family")
    parser.add_argument("--discover-washington", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.discover_washington:
        discover_washington(root)
    print(json.dumps(acquire(root, args.family), indent=2))
