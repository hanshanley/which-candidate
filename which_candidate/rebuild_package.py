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
                ("results/house-characteristics-v1",)
                if (root / "results/house-characteristics-v1/manifest.json").exists()
                else ()
            ),
            *(
                ("results/house-characteristics-v2",)
                if (root / "results/house-characteristics-v2/manifest.json").exists()
                else ()
            ),
            *(
                ("results/house-characteristics-v3",)
                if (root / "results/house-characteristics-v3/manifest.json").exists()
                else ()
            ),
            *(
                ("results/house-characteristics-v4",)
                if (root / "results/house-characteristics-v4/manifest.json").exists()
                else ()
            ),
            *(
                ("results/house-characteristics-v5",)
                if (root / "results/house-characteristics-v5/manifest.json").exists()
                else ()
            ),
            *(
                ("results/house-characteristics-v6",)
                if (root / "results/house-characteristics-v6/manifest.json").exists()
                else ()
            ),
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
    if (root / "data/house-characteristics-v2-frozen.json").exists():
        from .characteristics_v2 import verify_frozen

        verify_frozen(root)
    has_v3 = "results/house-characteristics-v3" in manifests
    if has_v3:
        from .characteristics_acquisition import BASELINE
        from .characteristics_v2 import verify_frozen

        verify_frozen(root, BASELINE)
    has_v4 = "results/house-characteristics-v4" in manifests
    if has_v4:
        from .characteristics_v2 import verify_frozen
        from .characteristics_v4_acquisition import BASELINE

        verify_frozen(root, BASELINE)
    has_v5 = "results/house-characteristics-v5" in manifests
    if has_v5:
        from .characteristics_v2 import verify_frozen
        from .characteristics_v5_acquisition import BASELINE

        verify_frozen(root, BASELINE)
    has_v6 = "results/house-characteristics-v6" in manifests
    if has_v6:
        from .characteristics_v2 import verify_frozen
        from .characteristics_v6_acquisition import BASELINE

        verify_frozen(root, BASELINE)
    current_version = (
        "v6" if has_v6 else "v5" if has_v5 else "v4" if has_v4 else "v3" if has_v3 else "v2"
    )
    if f"results/house-characteristics-{current_version}" in manifests:
        for name, receipt in manifests[f"results/house-characteristics-{current_version}"][
            "inputs"
        ].items():
            if fingerprint(root / name) != receipt:
                raise ValueError(f"Stale {current_version} characteristics package input: {name}")
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
    if (root / "data/house-characteristics-v3-queue.csv").exists():
        entries["data/house-characteristics-v3-queue.csv"] = (
            root / "data/house-characteristics-v3-queue.csv"
        )
    if (root / "data/house-characteristics-v4-queue.csv").exists():
        entries["data/house-characteristics-v4-queue.csv"] = (
            root / "data/house-characteristics-v4-queue.csv"
        )
    if (root / "data/house-characteristics-v5-queue.csv").exists():
        entries["data/house-characteristics-v5-queue.csv"] = (
            root / "data/house-characteristics-v5-queue.csv"
        )
    if (root / "data/house-characteristics-v6-queue.csv").exists():
        entries["data/house-characteristics-v6-queue.csv"] = (
            root / "data/house-characteristics-v6-queue.csv"
        )
    baseline_path = root / "data/democratic-background-gap-baseline.json"
    if baseline_path.exists():
        for name, sha256 in json.loads(baseline_path.read_text())[
            "protected_analysis_sha256"
        ].items():
            path = root / name
            if fingerprint(path)["sha256"] != sha256:
                raise ValueError(f"Changed frozen package input: {name}")
            entries[name] = path
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
            ("audits/house-characteristics-v1-validation.json",)
            if (root / "audits/house-characteristics-v1-validation.json").exists()
            else ()
        ),
        *(
            ("audits/house-characteristics-v2-validation.json",)
            if (root / "audits/house-characteristics-v2-validation.json").exists()
            else ()
        ),
        *(
            ("audits/house-characteristics-v3-validation.json",)
            if (root / "audits/house-characteristics-v3-validation.json").exists()
            else ()
        ),
        *(
            ("audits/house-characteristics-v4-validation.json",)
            if (root / "audits/house-characteristics-v4-validation.json").exists()
            else ()
        ),
        *(
            ("audits/house-characteristics-v5-validation.json",)
            if (root / "audits/house-characteristics-v5-validation.json").exists()
            else ()
        ),
        *(
            ("audits/house-characteristics-v6-validation.json",)
            if (root / "audits/house-characteristics-v6-validation.json").exists()
            else ()
        ),
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
        write_zip(
            staged / names[0],
            entries,
            lzma_text_threshold=64 * 1024,
            lzma_names={name for name in entries if name.endswith("/folds.jsonl.gz")},
        )
        figures = root / "publication"
        upload = {
            name: figures / name
            for name in figure_files
            if Path(name).parts[0] != "marginoferror" and name != "report.html"
        }
        upload["complete-query-set.zip"] = staged / names[0]
        upload["READ-ME.md"] = root / "docs/DOWNLOADS.md"
        # Full trait tables remain in the exact nested complete-query archive;
        # duplicating them here would exceed GitHub's single-file size limit.
        write_zip(
            staged / names[1],
            upload,
            lzma_text_threshold=64 * 1024,
            lzma_names={"complete-query-set.zip"},
        )
        receipts = {name: fingerprint(staged / name) for name in names}
        if any(receipt["bytes"] >= 100 * 1024 * 1024 for receipt in receipts.values()):
            raise ValueError(
                f"Complete download exceeds GitHub's 100-MiB single-file limit: {receipts}"
            )
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
