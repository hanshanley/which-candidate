"""V8-preserving evidence corrections, identity reviews and supported analyses."""

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree

from . import characteristics_v2 as v2
from . import characteristics_v4 as overlay
from . import house_characteristics as v1
from .characteristics_v8 import acquisition_accounting, historical_diagnostics
from .characteristics_v8_prediction import paired
from .characteristics_v9_acquisition import BASELINE, PLAN, PREVIOUS
from .characteristics_v9_controls import held_review
from .characteristics_v9_extract import ACQUISITIONS
from .storage import read_rows, write_json

VERSION = "house-characteristics-v9"
OUT = f"results/{VERSION}"
SPEC = "docs/HOUSE_CHARACTERISTICS_V9_SPEC.md"
QUEUE = "data/house-characteristics-v9-queue.csv"


def structural_eligibility(rows, candidates, inputs):
    """Use explicit Clerk first-Congress records, not an absent voting-data row."""
    first_members = defaultdict(list)
    for index, record in enumerate(inputs["clerk_members"], 1):
        member = ElementTree.fromstring(record["native_xml"])
        info = member.find("member-info")
        sworn = info.find("sworn-date")
        if (
            info.findtext("prior-congress") == "0"
            and sworn is not None
            and "20250103" <= sworn.get("date", "") <= "20261103"
        ):
            first_members[info.findtext("bioguideID")].append(
                {
                    "source_table": "source-inputs.clerk_members",
                    "source_row": index,
                    "bioguide_id": info.findtext("bioguideID"),
                    "prior_congresses": 0,
                    "sworn_date": sworn.get("date"),
                    "source": record["source"],
                }
            )
    by_id = {c["candidate_id"]: c for c in candidates}
    for row in rows:
        if row["trait"] != "voting_ideology":
            continue
        legislative = by_id[row["candidate_id"]].get("legislative", {})
        evidence = first_members.get(legislative.get("bioguide_id"), [])
        if (
            legislative.get("status")
            not in {
                "exact_fec_service_crosswalk",
                "official_clerk_and_service_crosswalk",
            }
            or len(evidence) != 1
        ):
            continue
        if row["analysis_eligible"] or row["factual_qualified"]:
            raise ValueError(
                f"First-Congress record conflicts with 118th-Congress ideology: {row['name']}"
            )
        row.update(
            status="inapplicable",
            coding_status="explicit_first_Congress_119_not_118",
            timing_status="documented_House_entry_after_118th_Congress",
            structural_evidence=evidence[0],
        )
        row["eligibility_reason"] += (
            " V9 structural eligibility: the Clerk explicitly records zero prior Congresses "
            "and first swearing-in during the 119th Congress; a 118th-Congress House voting "
            "ideology is inapplicable, not a missing or zero campaign-ideology score."
        )


def new_rows(root):
    result = overlay.new_rows(root, previous=PREVIOUS, prefix="v9-", held_reviewer=held_review)
    rows, candidates, panel, previous, observations, _, _ = result
    inputs = read_rows(Path(root) / "results/house/source-inputs.jsonl.gz")[0]
    structural_eligibility(rows, candidates, inputs)
    for row in rows:
        if (
            row["candidate_id"] == "220434"
            and row["trait"] == "incumbency"
            and row["analysis_eligible"]
        ):
            row["coding_status"] = "explicit_dated_candidate_negative_and_named_federal_incumbent"
            row["timing_status"] = "documented_2026-10-20_general_election_classification"
    for outcome in panel:
        evidence = outcome.get("v9_D_incumbency_evidence", {})
        if evidence.get("candidate_id") == "220434":
            evidence["source"] = "dated_WRKF_candidate_answer_and_positive_incumbent_service_bridge"
    old = {(r["candidate_id"], r["trait"]): r for r in previous}
    informed = {(o["candidate_id"], o["trait"]) for o in observations}
    for row in rows:
        key = (row["candidate_id"], row["trait"])
        if key in informed and row["trait"] in {
            "prior_elected_office",
            "other_government",
            "military",
        }:
            row["contrast_status"] = "scoped_facts_retained_insufficient_comparison_support"
            row["v9_history_time_reference"] = "per_observation_not_automatically_before_election"
        if row["trait"] == "age" and old[key]["analysis_eligible"] and row["analysis_eligible"]:
            row["uncertainty"]["age_years_interval"] = [row["analysis_value"]] * 2
    return result


def office_support(observations):
    return {
        "population": "V9 source-supported histories, not all nominees.",
        "histories": [o for o in observations if o["trait"] == "prior_elected_office"],
        "contrast_fitted": False,
        "limitation": "No new comparable elected-office negative category. Retained V8 "
        "scoped negatives and incomplete histories do not meet the unchanged support gates.",
    }


def source_outcomes(acquisition, observations, first):
    attempts = acquisition["discovery_dispositions"]
    plan = {s["id"]: s for s in acquisition["sources"]}
    grouped = defaultdict(list)
    for attempt in attempts:
        grouped[attempt["family"]].append(attempt)
    grouped["retained-original-extraction-corrections"]
    outcomes = []
    for family, requests in sorted(grouped.items()):
        ids = {r["id"] for r in requests}
        claims = [
            o
            for o in observations
            if (
                plan[o["source_id"]]["evidence_acquisition_role"]
                == "retained_original_new_extraction"
                if family == "retained-original-extraction-corrections"
                else plan[o["source_id"]]["document_id"].removeprefix("v9-") in ids
            )
        ]
        keys = {(o["candidate_id"], o["trait"]) for o in claims}
        outcomes.append(
            {
                "family": family,
                "requests": len(requests),
                "acquired_requests": sum(r["status"] == "acquired" for r in requests),
                "failed_requests": sum(r["status"] != "acquired" for r in requests),
                "unique_acquired_hashes": len(
                    {r["sha256"] for r in requests if r["status"] == "acquired"}
                ),
                "evidence_hashes": len({o["receipt"]["sha256"] for o in claims}),
                "observations": len(claims),
                "candidate_trait_fields": len(keys),
                "first_evidence_fields": len(keys & first),
            }
        )
    return outcomes


def disposition(row):
    if row["analysis_eligible"]:
        analytical = "eligible"
    elif row["status"] == "inapplicable":
        analytical = "structurally_inapplicable"
    elif row["status"] == "uncertain" and any(
        word in row["eligibility_reason"].casefold()
        for word in ("conflict", "discordant", "ambiguous")
    ):
        analytical = "identity_or_conflict_hold"
    elif row["factual_qualified"] or row["status"] != "unknown":
        analytical = "timing_or_coding_hold"
    else:
        analytical = "unknown_or_population_eligibility_unresolved"
    return {
        **{
            k: row[k]
            for k in (
                "candidate_id",
                "contest_id",
                "name",
                "state",
                "district",
                "party",
                "trait",
                "performance_eligible",
                "factual_qualified",
                "analysis_eligible",
                "status",
                "coding_status",
                "timing_status",
                "eligibility_reason",
            )
        },
        "analytical_disposition": analytical,
        "structural_evidence": row.get("structural_evidence"),
    }


def remaining_queue(root, rows, fits):
    current = {(r["candidate_id"], r["trait"]): r for r in rows}
    estimated = {f["trait"]: f["status"] == "estimated" for f in fits}
    with (root / "data/house-characteristics-v9-national-queue.csv").open() as stream:
        records = list(csv.DictReader(stream))
    for record in records:
        row = current[(record["candidate_id"], record["trait"])]
        record.update(disposition(row))
        record.update(
            no_evidence=row["status"] == "unknown",
            identity_or_conflict=record["analytical_disposition"] == "identity_or_conflict_hold",
            timing_or_coding=record["analytical_disposition"] == "timing_or_coding_hold",
            structurally_inapplicable=row["status"] == "inapplicable",
            missing_comparison_support=not estimated[row["trait"]],
            opponent_incumbency_unresolved=row["R_incumbency_control"] is None,
        )
    v1.write_csv(root / OUT / "remaining-candidate-trait-queue.csv", records)
    for field in (
        "no_evidence",
        "identity_or_conflict",
        "timing_or_coding",
        "missing_comparison_support",
    ):
        v1.write_csv(
            root / OUT / f"remaining-{field.replace('_', '-')}.csv",
            [r for r in records if r[field]],
        )
    counts = Counter(
        (
            r["trait"],
            r["party"],
            r["baseline_incumbency_group"],
            r["factual_qualified"],
            r["analytical_disposition"],
        )
        for r in records
    )
    v1.write_csv(
        root / OUT / "dispositions-by-party-and-incumbency.csv",
        [
            {
                "trait": t,
                "party": p,
                "baseline_incumbency_group": g,
                "factual_qualified": f,
                "analytical_disposition": a,
                "candidates": n,
            }
            for (t, p, g, f, a), n in sorted(counts.items())
        ],
    )


def build(root):
    root = Path(root)
    v2.verify_frozen(root, BASELINE)
    rows, candidates, panel, previous, observations, conflicts, held = new_rows(root)
    facts = overlay.progress(
        root,
        rows,
        previous,
        observations,
        conflicts,
        held,
        out=OUT,
        acquisition=ACQUISITIONS,
        office_support_fn=office_support,
        limitations_override={
            "gender": "Explicit public descriptions retained; incompatible source definitions not pooled.",
            "race": "Own descriptions do not extend the restricted historical Black/White estimand.",
            "ethnicity": "Own descriptions separate from the historical author-coded Latino contrast.",
            "prior_elected_office": "Scoped retained negatives insufficient; histories not before first House entry.",
            "other_government": "Documented jobs distinct from advisory, elected and contractor roles; negative support absent.",
            "military": "Positive records and one retained explicit negative; negative category below ten in three states.",
            "incumbency": "Three V8 controls resolved: two signed-FEC bridges and one dated personal negative with verified incumbent.",
            "voting_ideology": "118th-Congress record; explicit 119th first entrants are structurally inapplicable.",
        },
    )
    first, qualified, changes, breakdown = acquisition_accounting(
        rows, previous, observations, review_key="v9_review"
    )
    old = {(r["candidate_id"], r["trait"]): r for r in previous}
    source_by_id = {s["id"]: s for s in facts["acquisition"]["sources"]}
    retained_cells = {
        (o["candidate_id"], o["trait"])
        for o in observations
        if source_by_id[o["source_id"]]["evidence_acquisition_role"]
        == "retained_original_new_extraction"
        and o["v9_review"]["factual_qualified"]
    }
    v1.write_csv(root / OUT / "acquisition-field-changes.csv", changes)
    groups = defaultdict(set)
    for cid, trait in first:
        row = next(r for r in rows if r["candidate_id"] == cid and r["trait"] == trait)
        groups[(row["party"], overlay.incumbent_group(old[(cid, "incumbency")]))].add((cid, trait))
    facts.update(
        newly_informed_candidate_trait_fields=len(first),
        newly_informed_candidates=len({k[0] for k in first}),
        newly_qualified_existing_fields=sum(
            not old[(r["candidate_id"], r["trait"])]["factual_qualified"]
            and old[(r["candidate_id"], r["trait"])]["status"] != "unknown"
            and r["factual_qualified"]
            for r in rows
        ),
        existing_D_fields_newly_qualified=sum(
            r["party"] == "Democratic"
            and not old[(r["candidate_id"], r["trait"])]["factual_qualified"]
            and old[(r["candidate_id"], r["trait"])]["status"] != "unknown"
            and r["factual_qualified"]
            for r in rows
        ),
        resolved_incumbency_controls=sum(
            r["trait"] == "incumbency"
            and not old[(r["candidate_id"], r["trait"])]["analysis_eligible"]
            and r["analysis_eligible"]
            for r in rows
        ),
        first_evidence_definition="Previously unknown V8 field now factually qualified; "
        "retained-original corrections, new-original evidence and control reviews separated.",
        first_evidence_retained_original_fields=len(first & retained_cells),
        first_evidence_groups=[
            {
                "party": p,
                "baseline_incumbency_group": g,
                "fields": len(keys),
                "candidates": len({k[0] for k in keys}),
            }
            for (p, g), keys in sorted(groups.items())
        ],
        source_family_outcomes=source_outcomes(facts["acquisition"], observations, first),
        party_and_incumbency_coverage=breakdown,
    )
    v1.write_csv(root / OUT / "source-family-outcomes.csv", facts["source_family_outcomes"])
    for record in facts["trait_progress"]:
        trait = record["trait"]
        subset = [r for r in rows if r["trait"] == trait and r["party"] == "Democratic"]
        keys = {(r["candidate_id"], trait) for r in subset}
        record.update(
            cohort_denominator=len(subset),
            newly_informed_candidates=len(keys & first),
            first_retained_original_fields=len(keys & first & retained_cells),
            newly_qualified_factual_fields=sum(
                not old[k]["factual_qualified"] for k in keys & qualified
            ),
            existing_fields_newly_qualified=sum(
                not old[(r["candidate_id"], trait)]["factual_qualified"]
                and old[(r["candidate_id"], trait)]["status"] != "unknown"
                and r["factual_qualified"]
                for r in subset
            ),
            retained_reported_fields_newly_qualified=sum(
                not old[k]["factual_qualified"] and old[k]["status"] != "unknown"
                for k in keys & retained_cells
            ),
            no_qualified_factual_value=sum(not r["factual_qualified"] for r in subset),
            unknown_after=sum(r["status"] == "unknown" for r in subset),
            structurally_inapplicable=sum(r["status"] == "inapplicable" for r in subset),
            identity_or_conflict_holds=sum(
                disposition(r)["analytical_disposition"] == "identity_or_conflict_hold"
                for r in subset
            ),
            timing_or_coding_holds=sum(
                disposition(r)["analytical_disposition"] == "timing_or_coding_hold" for r in subset
            ),
        )
    holds = [
        r
        for r in rows
        if r["trait"] == "incumbency" and r["party"] == "Democratic" and not r["analysis_eligible"]
    ]
    v1.write_csv(
        root / OUT / "remaining-incumbency-holds.csv",
        [
            {
                k: r[k]
                for k in (
                    "candidate_id",
                    "name",
                    "state",
                    "district",
                    "performance_eligible",
                    "eligibility_reason",
                )
            }
            for r in holds
        ],
    )
    write_json(
        root / OUT / "historical-latino-population.json", historical_diagnostics(root, previous)
    )
    from .characteristics_v9_publication import report

    def finalize(fits):
        remaining_queue(root, rows, fits)
        prior = {r["trait"]: r for r in read_rows(root / PREVIOUS / "fits.jsonl.gz")}
        current = {r["trait"]: r for r in fits}
        panel_by_id = {r["D_candidate_election_id"]: r for r in panel}
        predicted = defaultdict(set)
        for prediction in read_rows(root / OUT / "full-population-predictions.jsonl.gz"):
            predicted[prediction["trait"]].add(prediction["candidate_election_id"])
        for group in breakdown:
            trait = group["trait"]
            members = {
                (r["contest_id"], r["name"])
                for r in rows
                if r["trait"] == trait
                and r["party"] == group["party"]
                and r["performance_eligible"] == group["performance_eligible"]
                and overlay.incumbent_group(old[(r["candidate_id"], "incumbency")])
                == group["baseline_incumbency_group"]
            }
            for column, ids in (
                ("fitted_after", current[trait].get("candidate_election_ids", [])),
                ("full_fit_prediction_supported", predicted[trait]),
            ):
                group[column] = (
                    sum(
                        (panel_by_id[cid]["contest_id"], panel_by_id[cid]["D_name"]) in members
                        for cid in ids
                    )
                    if group["party"] == "Democratic"
                    else 0
                )
        v1.write_csv(root / OUT / "coverage-by-party-and-incumbency.csv", breakdown)
        for record in facts["trait_progress"]:
            trait = record["trait"]
            prediction = current[trait].get("full_population_prediction", {})
            record.update(
                fitted_before=prior[trait]["n"],
                fitted_after=current[trait]["n"],
                prediction_supported=prediction.get("paired_candidates", 0),
                prediction_target=prediction.get("population_candidates", 0),
            )
        facts["newly_estimable_contrasts"] = [
            t
            for t in v1.TRAITS
            if current[t]["status"] == "estimated" and prior[t]["status"] != "estimated"
        ]
        facts["control_unlocked_contests"] = [
            r["contest_id"]
            for r, p in zip(panel, read_rows(root / PREVIOUS / "panel-overlay.jsonl.gz"))
            if r["eligible"]
            and (p["D_incumbent"] is None or p["R_incumbent"] is None)
            and r["D_incumbent"] is not None
            and r["R_incumbent"] is not None
        ]
        v1.write_csv(root / OUT / "v8-v9-trait-progress.csv", facts["trait_progress"])
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
        predictor=paired,
        extra_inputs=(
            BASELINE,
            QUEUE,
            PLAN,
            ACQUISITIONS,
            SPEC,
            "data/house-characteristics-v9-national-queue.csv",
            "which_candidate/characteristics_v9.py",
            "which_candidate/characteristics_v9_controls.py",
            "which_candidate/characteristics_v9_extract.py",
            "which_candidate/characteristics_v9_retained.py",
            "which_candidate/characteristics_v9_review.py",
            "which_candidate/characteristics_v9_publication.py",
            "data/house-characteristics-v9-source-review.json",
            f"{PREVIOUS}/candidate-traits.jsonl.gz",
            f"{PREVIOUS}/panel-overlay.jsonl.gz",
            "data/house-characteristics-research.json",
            "data/house-characteristics-receipts.json",
        ),
    )


if __name__ == "__main__":
    print(json.dumps(build(Path(__file__).resolve().parents[1]), indent=2))
