"""V6 requirements-led acquisition loops, with the frozen fifteen-block design."""

import json
from pathlib import Path

from . import characteristics_v2 as v2
from . import characteristics_v4 as overlay
from . import house_characteristics as v1
from .characteristics_v6_acquisition import ACQUISITIONS, BASELINE, PREVIOUS, QUEUE
from .storage import read_rows

VERSION = "house-characteristics-v6"
OUT = f"results/{VERSION}"
SPEC = "docs/HOUSE_CHARACTERISTICS_V6_SPEC.md"
BRIDGE = "v6-pbs-fancy-farm-2025-220397"
SELF_IDENTIFICATION = "MY NAME IS JOHN ANDREW WILLIAMS, BUT YOU CAN CALL ME DREW."


def held_review(candidates, previous, panel, inputs):
    support = {
        fragment
        for o in inputs["reviewed_characteristic_observations"]
        if o["source_id"] == BRIDGE and o["candidate_id"] == "220397"
        for fragment in o.get("identity_support", [])
    }
    bridges = (
        {"220397": ("WILLIAMS, JOHN ANDREW", BRIDGE)}
        if SELF_IDENTIFICATION in support
        and "DREW IS THE DEMOCRATIC CANDIDATE FOR THE FIRST CONGRESSIONAL DISTRICT." in support
        else {}
    )
    return overlay.held_fec_review(
        candidates, previous, panel, inputs, bridges=bridges, prefix="v6-"
    )


def new_rows(root):
    return overlay.new_rows(root, previous=PREVIOUS, prefix="v6-", held_reviewer=held_review)


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
            "incumbency": f"{holds} Democratic holds remain; one literal broadcast alias qualifies "
            "a held FEC election classification, not independently verified lifetime service.",
            "religion": "Dated broad Christian descriptions are not inferred Protestant labels; "
            "small categories and selective coverage remain support limits.",
            "race": "New undated AAPI self-descriptions remain outside the historical CAWP women contrast.",
            "ethnicity": "New family-origin statements do not establish explicit ethnic identity "
            "or a complementary reference; no newly qualified identity.",
        },
    )
    from .characteristics_v6_publication import report

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
        v1.write_csv(root / OUT / "v5-v6-trait-progress.csv", facts["trait_progress"])
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
            "which_candidate/characteristics_v6.py",
            "which_candidate/characteristics_v6_batch.py",
            "which_candidate/characteristics_v6_publication.py",
            "which_candidate/characteristics_v5_publication.py",
            f"{PREVIOUS}/candidate-traits.jsonl.gz",
            f"{PREVIOUS}/panel-overlay.jsonl.gz",
            "data/house-characteristics-research.json",
            "data/house-characteristics-receipts.json",
        ),
    )


if __name__ == "__main__":
    print(json.dumps(build(Path(__file__).resolve().parents[1]), indent=2))
