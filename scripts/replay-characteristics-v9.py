"""Replay V9 with the unchanged complete-archive, network-denied verifier."""

import argparse
import json
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--workdir", required=True, type=Path)
    args = parser.parse_args()
    replay = runpy.run_path(str(ROOT / "scripts/replay-characteristics-v8.py"))["replay"]
    print(json.dumps(replay(args.archive, args.workdir.resolve()), indent=2))
