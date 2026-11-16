"""V5 acquisition successor using the unchanged fifteen-block validation design."""

import json
from pathlib import Path

from . import characteristics_v2 as v2
from . import characteristics_v4 as overlay
from . import house_characteristics as v1
from .characteristics_v5_acquisition import ACQUISITIONS, BASELINE, PREVIOUS, QUEUE
from .storage import read_rows

VERSION = "house-characteristics-v5"
OUT = f"results/{VERSION}"
SPEC = "docs/HOUSE_CHARACTERISTICS_V5_SPEC.md"


def new_rows(root):
    return overlay.new_rows(root, previous=PREVIOUS, prefix="v5-", held_reviewer=None)


def build(root):
    root = Path(root)
    v2.verify_frozen(root, BASELINE)
    rows, candidates, panel, previous, observations, conflicts, held = new_rows(root)
    holds = sum(
        r["party"] == "Democratic" and r["trait"] == "incumbency" and not r["analysis_eligible"]
        for r in rows
    )
    facts = overlay.progress(
        root,
        rows,
        previous,
        observations,
        conflicts,
        held,
        out=OUT,
        acquisition=ACQUISITIONS,
        limitations_override={
            "incumbency": f"{holds} Democratic holds remain; new FEC campaign-name links "
            "qualify election classifications, not independently verified service.",
            "religion": "New explicit undated description is factual at retrieval, not qualified "
            "at election; analytical religious coverage does not increase.",
        },
    )
    from .characteristics_v5_publication import report

    def finalize(fits):
        old_fits = {r["trait"]: r for r in read_rows(root / PREVIOUS / "fits.jsonl.gz")}
        current = {r["trait"]: r for r in fits}
        for record in facts["trait_progress"]:
            trait = record["trait"]
            record.update(
                fitted_before=old_fits[trait]["n"],
                fitted_after=current[trait]["n"],
                estimated_before=old_fits[trait]["status"] == "estimated",
                estimated_after=current[trait]["status"] == "estimated",
            )
        facts["newly_estimable_contrasts"] = [
            r["trait"]
            for r in fits
            if r["status"] == "estimated" and old_fits[r["trait"]]["status"] != "estimated"
        ]
        v1.write_csv(root / OUT / "v4-v5-trait-progress.csv", facts["trait_progress"])
        return facts

    return v2.build(
        root,
        version=VERSION,
        dataset=(rows, candidates, panel, read_rows(root / v1.OUT / "candidate-traits.jsonl.gz")),
        protection=BASELINE,
        spec=SPEC,
        previous=previous,
        summary_update=finalize,
        reporter=report,
        reuse_from=PREVIOUS,
        extra_inputs=(
            BASELINE,
            QUEUE,
            ACQUISITIONS,
            SPEC,
            "which_candidate/characteristics_v4.py",
            "which_candidate/characteristics_v5.py",
            "which_candidate/characteristics_v5_batch.py",
            "which_candidate/characteristics_v5_publication.py",
            f"{PREVIOUS}/candidate-traits.jsonl.gz",
            f"{PREVIOUS}/panel-overlay.jsonl.gz",
            "data/house-characteristics-research.json",
            "data/house-characteristics-receipts.json",
        ),
    )


if __name__ == "__main__":
    print(json.dumps(build(Path(__file__).resolve().parents[1]), indent=2))
