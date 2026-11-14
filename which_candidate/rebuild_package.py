"""Package complete research queries and upload-ready editorial figures."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from .publication import write_zip
from .rebuild import ROOT
from .rebuild_publication import VERSIONS
from .storage import fingerprint, write_json


def build(root=ROOT, output=None, *, version="2026-v4"):
    if version not in VERSIONS:
        raise ValueError(f"Unknown figure version: {version}")
    root = Path(root)
    output = Path(output) if output else root / "downloads"
    output.mkdir(parents=True, exist_ok=True)
    for folder in dict.fromkeys(
        ("results/2026-v4", "publication/2026-v4", f"publication/{version}")
    ):
        manifest = json.loads((root / folder / "manifest.json").read_text())
        for name, receipt in manifest["files"].items():
            if fingerprint(root / folder / name) != receipt:
                raise ValueError(f"Changed package input: {folder}/{name}")
    entries = {}
    for folder in (
        "which_candidate",
        "tests",
        "docs",
        "results",
        "publication/2026-v4",
        f"publication/{version}",
        ".github/skills/publication-charts",
    ):
        for path in (root / folder).rglob("*"):
            if path.is_file() and path.suffix in (
                ".py",
                ".md",
                ".json",
                ".gz",
                ".csv",
                ".png",
                ".svg",
            ):
                entries[path.relative_to(root).as_posix()] = path
    for path in (root / "data").glob("*.json"):
        entries[path.relative_to(root).as_posix()] = path
    for name in (
        "README.md",
        "pyproject.toml",
        "requirements.lock",
        "publication/active.json",
        "audits/2026-v4/critical-review.md",
        "audits/2026-v4/frozen-archives.json",
        "audits/2026-v4/same-sample-measurement.json",
    ):
        entries[name] = root / name
    names = (f"{version}-complete-queries.zip", f"{version}-substack-figures.zip")
    with TemporaryDirectory(prefix=".which-candidate-packages-", dir=output) as directory:
        staged = Path(directory)
        write_zip(staged / names[0], entries)
        figures = root / "publication" / version
        upload = {
            path.relative_to(figures).as_posix(): path
            for path in figures.rglob("*")
            if path.is_file() and path.parts[-2] != "marginoferror"
        }
        upload["complete-query-set.zip"] = staged / names[0]
        write_zip(staged / names[1], upload)
        receipts = {name: fingerprint(staged / name) for name in names}
        write_json(staged / f"{version}-downloads.json", receipts)
        all_names = (*names, f"{version}-downloads.json")
        for name in all_names:
            target = output / name
            if target.exists() and fingerprint(target) != fingerprint(staged / name):
                raise ValueError("Changed download requires a new output directory")
        for name in all_names:
            target = output / name
            if not target.exists():
                (staged / name).replace(target)
    return receipts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--version", choices=VERSIONS, default="2026-v4")
    args = parser.parse_args()
    print(json.dumps(build(args.root, args.output, version=args.version), indent=2))
