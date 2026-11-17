"""Rebuild the complete current House project from pinned, normalized inputs."""

import argparse
import json
from pathlib import Path

from . import (
    house_candidates,
    house_members,
    house_study,
    participation_context,
    rebuild,
    rebuild_package,
    rebuild_publication,
)
from .house_report import render as render_house_report
from .storage import fingerprint, read_rows, write_json

ROOT = Path(__file__).resolve().parents[1]


def _refresh_coverage_plot_data(root):
    path = root / "publication/plot-data/candidate-evidence.csv"
    previous = house_study.csv_rows(path)
    current = {
        row["cohort"]: row for row in json.loads((root / "results/house/coverage.json").read_text())
    }
    plotted = (
        "cohort",
        "candidates",
        "factual_background",
        "donor_score",
        "prior_federal_voting_score",
    )
    rows = []
    for row in previous:
        updated = current[row["cohort"]]
        if any(str(updated[key]) != row[key] for key in plotted):
            if (
                (root / "data/house-characteristics-v8-acquisitions.json").exists()
                and all(
                    str(updated[key]) == row[key] for key in plotted if key != "factual_background"
                )
                and updated["factual_background"] >= int(row["factual_background"])
            ):
                rows.append(row)
                continue
            raise ValueError("Evidence refresh would change plotted coverage; keep frozen figures")
        rows.append(
            {key: value for key, value in updated.items() if not isinstance(value, (list, dict))}
        )
    path.write_bytes(house_study.csv_bytes(rows))


def build():
    rebuild.replay()
    house_candidates.build()
    house_members.build()
    participation_context.build()
    summary = house_study.build()
    rebuild_publication.build()
    downloads = rebuild_package.build()
    return {"study": summary, "downloads": downloads}


def refresh_evidence(root=ROOT):
    """Refresh evidence and successor while preserving earlier frozen fits and figures."""
    root = Path(root)
    chart_receipts = {
        path.relative_to(root).as_posix(): fingerprint(path)
        for path in (root / "publication").rglob("*")
        if path.is_file() and path.suffix in {".png", ".svg"}
    }
    if (root / "data/house-characteristics-v8-acquisitions.json").exists():
        house_candidates.build(
            root, inputs=read_rows(root / "results/house/source-inputs.jsonl.gz")[0]
        )
    house_members.build(root)
    if (root / "data/house-characteristics-v8-acquisitions.json").exists():
        from .characteristics_v8 import build as build_characteristics

        build_characteristics(root)
    elif (root / "data/house-characteristics-v7-acquisitions.json").exists():
        from .characteristics_v7 import build as build_characteristics

        build_characteristics(root)
    elif (root / "data/house-characteristics-v6-acquisitions.json").exists():
        from .characteristics_v6 import build as build_characteristics

        build_characteristics(root)
    elif (root / "data/house-characteristics-v5-acquisitions.json").exists():
        from .characteristics_v5 import build as build_characteristics

        build_characteristics(root)
    elif (root / "data/house-characteristics-v4-acquisitions.json").exists():
        from .characteristics_v4 import build as build_characteristics

        build_characteristics(root)
    elif (root / "data/house-characteristics-v3-acquisitions.json").exists():
        from .characteristics_v3 import build as build_characteristics

        build_characteristics(root)
    elif (root / "data/house-characteristics-v2-review-seal.json").exists():
        from .characteristics_v2 import build as build_characteristics

        build_characteristics(root)
    elif (root / "data/house-characteristics-review.json").exists():
        from .house_characteristics import build as build_characteristics

        build_characteristics(root)
    if (root / "data/participation-source-inputs.json").exists():
        participation_context.build(root)
    summary = house_study.refresh_evidence(root)
    _refresh_coverage_plot_data(root)
    publication = root / "publication"
    charts = json.loads((publication / "captions.json").read_text())
    (publication / "report.html").write_text(
        render_house_report(
            (root / "results/house-study/report.md").read_text(),
            read_rows(root / "results/house-study/candidate-profiles.jsonl.gz"),
            charts,
            {
                "current": house_study.csv_rows(root / "results/members/house-119-seats.csv"),
                "incoming": house_study.csv_rows(root / "results/members/house-120-seats.csv"),
            },
            (
                read_rows(root / "results/participation/state-context.jsonl.gz")
                if (root / "results/participation/manifest.json").exists()
                else []
            ),
            read_rows(root / "results/house-study/democratic-candidate-traits.jsonl.gz"),
        )
    )
    manifest = json.loads((publication / "manifest.json").read_text())
    manifest["inputs"] = {name: fingerprint(root / name) for name in manifest["inputs"]}
    manifest["files"] = {
        path.relative_to(publication).as_posix(): fingerprint(path)
        for path in sorted(publication.rglob("*"))
        if path.is_file() and path != publication / "manifest.json"
    }
    write_json(publication / "manifest.json", manifest)
    downloads = rebuild_package.build(root)
    refreshed_charts = {
        path.relative_to(root).as_posix(): fingerprint(path)
        for path in (root / "publication").rglob("*")
        if path.is_file() and path.suffix in {".png", ".svg"}
    }
    if any(
        refreshed_charts.get(name) != receipt
        for name, receipt in chart_receipts.items()
        if not name.startswith(
            "publication/characteristics-v8/"
            if (root / "data/house-characteristics-v8-acquisitions.json").exists()
            else "publication/characteristics-v7/"
            if (root / "data/house-characteristics-v7-acquisitions.json").exists()
            else "publication/characteristics-v6/"
            if (root / "data/house-characteristics-v6-acquisitions.json").exists()
            else "publication/characteristics-v5/"
            if (root / "data/house-characteristics-v5-acquisitions.json").exists()
            else "publication/characteristics-v4/"
        )
    ):
        raise ValueError("Evidence-only refresh changed publication charts")
    return {"study": summary, "downloads": downloads}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--evidence-only", action="store_true")
    args = parser.parse_args()
    print(json.dumps(refresh_evidence(args.root) if args.evidence_only else build(), indent=2))
