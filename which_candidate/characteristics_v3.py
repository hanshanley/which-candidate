"""New-source acquisition overlay on the immutable V2 fifteen-trait analysis."""

import argparse
import copy
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from . import characteristics_v2 as v2
from . import house_characteristics as v1
from .characteristics_acquisition import ACQUISITIONS, BASELINE, QUEUE
from .storage import read_rows

VERSION = "house-characteristics-v3"
OUT = f"results/{VERSION}"
SPEC = "docs/HOUSE_CHARACTERISTICS_V3_SPEC.md"


def new_rows(root):
    root = Path(root)
    previous = read_rows(root / v2.OUT / "candidate-traits.jsonl.gz")
    rows = copy.deepcopy(previous)
    by_key = {(r["candidate_id"], r["trait"]): r for r in rows}
    old_by_key = {(r["candidate_id"], r["trait"]): r for r in previous}
    candidates = read_rows(root / "results/house/candidates.jsonl.gz")
    panel = copy.deepcopy(read_rows(root / v2.OUT / "panel-overlay.jsonl.gz"))
    inputs = read_rows(root / "results/house/source-inputs.jsonl.gz")[0]
    observations = [
        r
        for r in inputs["reviewed_characteristic_observations"]
        if r["source_id"].startswith("v3-")
    ]
    grouped = defaultdict(list)
    for observation in observations:
        grouped[(observation["candidate_id"], observation["trait"])].append(observation)
    conflicts = []
    for key, claims in grouped.items():
        row = by_key[key]
        row["source_recorded_value"].setdefault("reviewed_facts", []).extend(claims)
        row["evidence"].extend(claims)
        row["review_status"] = "literal_and_identity_reviewed_v3"
        row["factual_qualified"] = True
        row["status"] = "qualified"
        row["acquisition_observation_ids"] = [c["observation_id"] for c in claims]
        trait = row["trait"]
        row["eligibility_reason"] += (
            " V3 reviewed explicit new/corroborating facts; source definitions, dates and "
            "prior claims retained. Factual qualification is separate from contrast support."
        )
        if trait == "gender":
            values = {c["value"] for c in claims}
            if row["analysis_eligible"]:
                values.add(row["analysis_value"])
            if len(values) != 1:
                row.update(
                    status="uncertain",
                    factual_qualified=False,
                    analysis_eligible=False,
                    analysis_value=None,
                    coding_status="conflicting_source_definitions",
                )
                conflicts.append({"candidate_id": key[0], "trait": trait, "values": sorted(values)})
            else:
                (value,) = values
                row.update(
                    value=value,
                    analysis_value=value,
                    analysis_eligible=True,
                    coding_status="explicit_source_gender_or_women_classification",
                    timing_status="dated_historical_or_2026_election_source",
                )
        elif trait in {"race", "ethnicity"}:
            row["value"] = {
                "explicit_source_observations": [
                    {
                        "value": c["value"],
                        "observation_date": c["publication_date"],
                        "source_id": c["source_id"],
                    }
                    for c in claims
                ]
            }
            if trait == "race":
                historical = [c for c in claims if c["source_id"].startswith("v3-cawp-history-")]
                identities = set().union(*(set(c["value"]) for c in historical))
                if ("Black" in identities) != ("White" in identities):
                    row.update(
                        analysis_value="Black" if "Black" in identities else "White",
                        analysis_eligible=True,
                        coding_status="explicit_CAWP_2024_identified_group",
                        timing_status="historical_2024_identity_not_verified_current",
                        contrast_status="historical_CAWP_women_Black_versus_White_requires_support",
                    )
                    row["eligibility_reason"] += (
                        " Analytical question is historical CAWP-identified Black versus White "
                        "among matched women candidates; other identities retained, Black/White "
                        "overlap excluded, unknown never a reference."
                    )
            else:
                row["contrast_status"] = "positive_Hispanic_Latina_no_nonHispanic_reference"
        elif trait == "incumbency":
            values = {c["value"] for c in claims}
            if row["analysis_eligible"] and row["analysis_value"] not in values:
                conflicts.append(
                    {
                        "candidate_id": key[0],
                        "trait": trait,
                        "existing": row["analysis_value"],
                        "new": sorted(values),
                        "disposition": "preserve_qualified_service_evidence",
                    }
                )
            elif len(values) == 1 and not row["analysis_eligible"]:
                (value,) = values
                row.update(
                    value=value,
                    analysis_value=value,
                    analysis_eligible=True,
                    coding_status="CAWP_2026_election_incumbency",
                    timing_status="explicit_2026_election_status",
                )
                row["eligibility_reason"] += (
                    " Source-reported election control, not verified lifetime federal service."
                )
        elif trait == "military":
            row["value"] = True
            row["contrast_status"] = "positive_service_no_explicit_nonservice_reference"
            if not row["analysis_eligible"]:
                row["timing_status"] = "undated_post_election_source_report"
        elif trait == "age":
            birthday = date.fromisoformat(claims[-1]["value"])
            age = (
                v1.CUTOFF.year
                - birthday.year
                - ((v1.CUTOFF.month, v1.CUTOFF.day) < (birthday.month, birthday.day))
            )
            row.update(
                value=age,
                analysis_value=age,
                analysis_eligible=True,
                coding_status="exact_official_historical_birthday",
                timing_status="immutable_birth_fact_retrospectively_retrieved",
            )
            row["uncertainty"]["age_years_interval"] = [age, age]
        elif trait == "education" and any(
            c["source_id"].startswith("v3-mn-little-") for c in claims
        ):
            row.update(
                value="doctoral_or_professional",
                analysis_value="doctoral_or_professional",
                analysis_eligible=True,
                coding_status="explicit_completed_JD_2014",
                timing_status="credential_explicitly_completed_before_election",
            )
        elif trait == "profession":
            codes = {
                "Eric Yonce": "business",
                "Lauren Jewett": "education",
                "Ned Pillersdorf": "legal",
                "Matt Little": "legal",
            }
            if row["name"] in codes:
                code = codes[row["name"]]
                row.update(
                    value=code,
                    analysis_value=code,
                    analysis_eligible=True,
                    coding_status="explicit_historical_occupation",
                    timing_status="dated_or_multidecade_experience_precedes_election",
                )
                row["eligibility_reason"] += (
                    " Successor-only historical-occupation review: a dated prior occupation "
                    "or explicit 16/20-plus years/decades establishes experience before the "
                    "election despite retrospective retrieval. This narrows the source "
                    "receipt's conservative timing hold; it does not assert current paid "
                    "employment, a precise job-start date or prospective availability."
                )
        if trait in {
            "religion",
            "education",
            "profession",
            "prior_elected_office",
            "other_government",
        }:
            if not row["analysis_eligible"]:
                row["value"] = {"explicit_source_observations": [c["value"] for c in claims]}
                row["coding_status"] = (
                    "positive_history_without_supported_reference"
                    if trait in {"prior_elected_office", "other_government"}
                    else "explicit_report_timing_or_coding_unresolved"
                )
                row["eligibility_reason"] += (
                    " Not promoted analytically: undated post-election report or no supported "
                    "reference. Contractor/advisory roles are not confirmed paid government employment."
                )
        row["prospective_model_eligible"] = False

    for outcome in panel:
        # Match native contest identities, not a parsed name or election-key suffix.
        matches = [
            c
            for c in candidates
            if c["contest_id"] == outcome["contest_id"]
            and c["name"] == outcome["D_name"]
            and c["party"] == "Democratic"
        ]
        if len(matches) == 1:
            cid = matches[0]["candidate_id"]
            status = by_key[(cid, "incumbency")]
            if outcome["D_incumbent"] is None and status["analysis_eligible"]:
                outcome["D_incumbent"] = status["analysis_value"]
                outcome["v3_D_incumbency_evidence"] = status.get(
                    "acquisition_observation_ids",
                    [{"frozen_v2_baseline_trait_row": status["baseline_trait_row"]}],
                )
        opponents = [
            c
            for c in candidates
            if c["contest_id"] == outcome["contest_id"]
            and c["name"] == outcome["R_name"]
            and c["party"] == "Republican"
        ]
        if len(opponents) == 1 and outcome["R_incumbent"] is None:
            status = by_key[(opponents[0]["candidate_id"], "incumbency")]
            if status["analysis_eligible"]:
                outcome["R_incumbent"] = status["analysis_value"]
                outcome["v3_R_incumbency_evidence"] = status.get(
                    "acquisition_observation_ids",
                    [{"frozen_v2_baseline_trait_row": status["baseline_trait_row"]}],
                )
    controls = {r["contest_id"]: r for r in panel}
    for row in rows:
        row["D_incumbency_control"] = controls[row["contest_id"]]["D_incumbent"]
        row["R_incumbency_control"] = controls[row["contest_id"]]["R_incumbent"]
        inc = by_key[(row["candidate_id"], "incumbency")]
        old_inc = old_by_key[(row["candidate_id"], "incumbency")]
        if (
            not old_inc["analysis_eligible"]
            and inc["analysis_value"] is False
            and row["trait"] in {"house_service", "voting_ideology", "party_unity"}
            and not row["analysis_eligible"]
        ):
            row.update(
                status="inapplicable",
                coding_status="resolved_not_current_federal_incumbent",
            )
            row["eligibility_reason"] += (
                " V3 resolves nonincumbency: current-incumbent-only legislative measure "
                "is structurally inapplicable, not a zero score or lifetime nonservice."
            )
        row["incumbency_group_v3"] = (
            "incumbent"
            if inc["analysis_value"] is True
            else "nonincumbent"
            if inc["analysis_value"] is False
            else "unknown_incumbency"
        )
        row["field_eligible"] = row["analysis_eligible"]
    return rows, candidates, panel, previous, observations, conflicts, old_by_key


def progress(root, rows, previous, observations, conflicts):
    old = {(r["candidate_id"], r["trait"]): r for r in previous}
    acquired = [o for o in observations if not o["source_id"].startswith("v3-cawp-2026-held-")]
    old_people = {r["candidate_id"] for r in previous if r["factual_qualified"]}
    new_cells = {(o["candidate_id"], o["trait"]) for o in acquired}
    newly_informed = [
        r
        for r in rows
        if (r["candidate_id"], r["trait"]) in new_cells
        and old[(r["candidate_id"], r["trait"])]["status"] in {"unknown", "inapplicable"}
    ]
    existing_only = [
        r
        for r in rows
        if (r["candidate_id"], r["trait"]) not in new_cells
        and not old[(r["candidate_id"], r["trait"])]["factual_qualified"]
        and r["factual_qualified"]
    ]
    changes = []
    for row in rows:
        before = old[(row["candidate_id"], row["trait"])]
        if (
            row.get("acquisition_observation_ids")
            or row["analysis_eligible"] != before["analysis_eligible"]
        ):
            changes.append(
                {
                    **{
                        k: row[k]
                        for k in ("candidate_id", "contest_id", "name", "state", "party", "trait")
                    },
                    "performance_eligible": row["performance_eligible"],
                    "incumbency_group_before": (
                        "incumbent"
                        if old[(row["candidate_id"], "incumbency")]["analysis_value"] is True
                        else "nonincumbent"
                        if old[(row["candidate_id"], "incumbency")]["analysis_value"] is False
                        else "unknown_incumbency"
                    ),
                    "incumbency_group_after": row["incumbency_group_v3"],
                    "before_factual": before["factual_qualified"],
                    "after_factual": row["factual_qualified"],
                    "before_analysis": before["analysis_eligible"],
                    "after_analysis": row["analysis_eligible"],
                    "new_source_acquired": (row["candidate_id"], row["trait"]) in new_cells,
                    "before_value": before["analysis_value"],
                    "after_value": row["analysis_value"],
                    "reason": row["eligibility_reason"],
                }
            )
    output = Path(root) / OUT
    output.mkdir(parents=True, exist_ok=True)
    v1.write_csv(output / "acquisition-field-changes.csv", changes)
    v1.write_csv(output / "source-conflicts.csv", conflicts)
    groups = []
    for trait in v1.TRAITS:
        for group in ("incumbent", "nonincumbent", "unknown_incumbency"):
            for eligible in (False, True):
                subset = [
                    r
                    for r in rows
                    if r["party"] == "Democratic"
                    and r["trait"] == trait
                    and r["performance_eligible"] == eligible
                    and (
                        (
                            "incumbent"
                            if old[(r["candidate_id"], "incumbency")]["analysis_value"] is True
                            else "nonincumbent"
                            if old[(r["candidate_id"], "incumbency")]["analysis_value"] is False
                            else "unknown_incumbency"
                        )
                        == group
                    )
                ]
                groups.append(
                    {
                        "trait": trait,
                        "baseline_incumbency_group": group,
                        "performance_eligible": eligible,
                        "candidates": len(subset),
                        "before_factual": sum(
                            old[(r["candidate_id"], trait)]["factual_qualified"] for r in subset
                        ),
                        "after_factual": sum(r["factual_qualified"] for r in subset),
                        "before_analysis": sum(
                            old[(r["candidate_id"], trait)]["analysis_eligible"] for r in subset
                        ),
                        "after_analysis": sum(r["analysis_eligible"] for r in subset),
                        "new_source_candidate_trait_fields": sum(
                            (r["candidate_id"], trait) in new_cells for r in subset
                        ),
                    }
                )
    v1.write_csv(output / "coverage-by-incumbency.csv", groups)
    acquisition = json.loads((Path(root) / ACQUISITIONS).read_text())
    return {
        "acquisition": acquisition,
        "newly_acquired_observations": len(acquired),
        "newly_acquired_D_observations": sum(o["party"] == "Democratic" for o in acquired),
        "new_source_candidate_trait_fields": len(new_cells),
        "new_source_candidates": len({o["candidate_id"] for o in acquired}),
        "new_source_D_candidates": len(
            {o["candidate_id"] for o in acquired if o["party"] == "Democratic"}
        ),
        "newly_informed_candidate_trait_fields": len(newly_informed),
        "newly_informed_candidates": len({r["candidate_id"] for r in newly_informed}),
        "newly_informed_D_candidate_trait_fields": sum(
            r["party"] == "Democratic" for r in newly_informed
        ),
        "newly_informed_D_candidates": len(
            {r["candidate_id"] for r in newly_informed if r["party"] == "Democratic"}
        ),
        "newly_covered_people": len({r["candidate_id"] for r in newly_informed} - old_people),
        "existing_observations_newly_qualified": len(existing_only),
        "existing_D_fields_newly_qualified": sum(r["party"] == "Democratic" for r in existing_only),
        "newly_qualified_existing_fields": len(existing_only),
        "newly_analysis_eligible_fields": sum(
            not old[(r["candidate_id"], r["trait"])]["analysis_eligible"] and r["analysis_eligible"]
            for r in rows
        ),
        "newly_analysis_eligible_D_fields": sum(
            r["party"] == "Democratic"
            and not old[(r["candidate_id"], r["trait"])]["analysis_eligible"]
            and r["analysis_eligible"]
            for r in rows
        ),
        "D_unknown_incumbency_before": sum(
            r["party"] == "Democratic" and r["trait"] == "incumbency" and not r["analysis_eligible"]
            for r in previous
        ),
        "D_unknown_incumbency_after": sum(
            r["party"] == "Democratic" and r["trait"] == "incumbency" and not r["analysis_eligible"]
            for r in rows
        ),
        "source_conflicts": conflicts,
        "acquired_trait_counts": dict(Counter(o["trait"] for o in acquired)),
    }


def build(root):
    root = Path(root)
    v2.verify_frozen(root, BASELINE)
    rows, candidates, panel, previous, observations, conflicts, _ = new_rows(root)
    facts = progress(root, rows, previous, observations, conflicts)
    from .characteristics_v3_publication import report

    return v2.build(
        root,
        version=VERSION,
        dataset=(rows, candidates, panel, read_rows(root / v1.OUT / "candidate-traits.jsonl.gz")),
        protection=BASELINE,
        spec=SPEC,
        previous=previous,
        summary_update=facts,
        reporter=report,
        extra_inputs=(
            BASELINE,
            QUEUE,
            ACQUISITIONS,
            "which_candidate/characteristics_v3.py",
            "which_candidate/characteristics_v3_publication.py",
            "which_candidate/characteristics_acquisition.py",
            "which_candidate/characteristics_biographies.py",
            "which_candidate/characteristics_research.py",
            f"{v2.OUT}/candidate-traits.jsonl.gz",
            f"{v2.OUT}/panel-overlay.jsonl.gz",
            "data/house-characteristics-research.json",
            "data/house-characteristics-receipts.json",
        ),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(build(args.root), indent=2))
