"""Package complete research queries and upload-ready editorial figures."""

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from .publication import write_zip
from .rebuild import ROOT
from .storage import fingerprint, write_json


def build(root=ROOT, output=None):
    root = Path(root)
    output = Path(output) if output else root / "downloads"
    output.mkdir(parents=True, exist_ok=True)
    manifests = {
        folder: json.loads((root / folder / "manifest.json").read_text())
        for folder in (
            "results/2026-v4",
            "results/house",
            "results/members",
            "results/house-study",
            "publication",
            *(
                ("results/participation",)
                if (root / "data/participation-source-inputs.json").exists()
                else ()
            ),
        )
    }
    if "results/participation" in manifests:
        for name, receipt in manifests["results/participation"]["inputs"].items():
            if fingerprint(root / name) != receipt:
                raise ValueError(f"Stale participation package input: {name}")
    for folder, manifest in manifests.items():
        for name, receipt in manifest["files"].items():
            if fingerprint(root / folder / name) != receipt:
                raise ValueError(f"Changed package input: {folder}/{name}")
    entries = {}
    for folder in (
        "which_candidate",
        "tests",
        "docs",
        "results",
        ".github/skills/publication-charts",
    ):
        for path in (root / folder).rglob("*"):
            if (
                path.is_file()
                and not (folder == "results" and path.suffix in (".png", ".svg"))
                and path.suffix
                in (
                    ".py",
                    ".md",
                    ".json",
                    ".gz",
                    ".csv",
                    ".png",
                    ".svg",
                )
            ):
                entries[path.relative_to(root).as_posix()] = path
    figure_files = (*manifests["publication"]["files"], "manifest.json")
    for name in figure_files:
        entries[f"publication/{name}"] = root / "publication" / name
    for path in (root / "data").glob("*.json"):
        entries[path.relative_to(root).as_posix()] = path
    for name in (
        "README.md",
        "pyproject.toml",
        "requirements.lock",
        "audits/2026-v4/critical-review.md",
        "audits/2026-v4/same-sample-measurement.json",
        "audits/house-backgrounds.json",
        "audits/incumbent-backgrounds.json",
        "audits/full-house-members.json",
        "audits/house-project.md",
        "audits/candidate-research.json",
        "audits/candidate-discovery-repair.json",
        *(
            ("audits/participation-intake.json",)
            if (root / "data/participation-source-inputs.json").exists()
            else ()
        ),
    ):
        entries[name] = root / name
    names = ("complete-queries.zip", "substack-figures.zip")
    with TemporaryDirectory(prefix=".which-candidate-packages-", dir=output) as directory:
        staged = Path(directory)
        write_zip(staged / names[0], entries)
        figures = root / "publication"
        upload = {
            name: figures / name for name in figure_files if Path(name).parts[0] != "marginoferror"
        }
        upload["complete-query-set.zip"] = staged / names[0]
        write_zip(staged / names[1], upload)
        receipts = {name: fingerprint(staged / name) for name in names}
        write_json(staged / "downloads.json", receipts)
        all_names = (*names, "downloads.json")
        for name in all_names:
            target = output / name
            if not target.exists() or fingerprint(target) != fingerprint(staged / name):
                (staged / name).replace(target)
    return receipts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.root, args.output), indent=2))
