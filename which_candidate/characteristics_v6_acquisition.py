"""Freeze V5 before the next requirements-led acquisition loops."""

import json
from pathlib import Path

from .characteristics_v5_acquisition import freeze as freeze_previous

BASELINE = "data/house-characteristics-v6-baseline.json"
QUEUE = "data/house-characteristics-v6-queue.csv"
ACQUISITIONS = "data/house-characteristics-v6-acquisitions.json"
PREVIOUS = "results/house-characteristics-v5"
BASE_COMMIT = "9f6713cf126895d1f631e7972bf157229f763861"


def freeze(root):
    return freeze_previous(root, version=6, baseline_commit=BASE_COMMIT)


if __name__ == "__main__":
    result = freeze(Path(__file__).resolve().parents[1])
    print(json.dumps({k: v for k, v in result.items() if k != "protected_sha256"}, indent=2))
