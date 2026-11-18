"""V8: national statements, scoped negative histories and estimable predictions."""

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from . import characteristics_v2 as v2
from . import characteristics_v4 as overlay
from . import house_characteristics as v1
from .characteristics_v7 import orthographic
from .characteristics_v8_acquisition import ACQUISITIONS, BASELINE, PREVIOUS, QUEUE
from .characteristics_v8_prediction import paired
from .storage import read_rows, write_json

VERSION = "house-characteristics-v8"
OUT = f"results/{VERSION}"
SPEC = "docs/HOUSE_CHARACTERISTICS_V8_SPEC.md"


def held_review(candidates, previous, panel, inputs):
    def district(value):
        return "AL" if str(value) in {"00", "0", "AL"} else value

    canonical = [
        {**c, "name": orthographic(c["name"]), "district": district(c["district"])}
        for c in candidates
    ]
    fec = [
        {
            **r,
            "first": orthographic(r["first"]),
            "last": orthographic(r["last"]),
            "district": district(r["district"]),
        }
        for r in inputs["fec"]
    ]
    bridges = {}

    def tokens(value):
        return re.findall(r"\w+", orthographic(value).casefold())

    for observation in inputs["reviewed_characteristic_observations"]:
        bridge = observation.get("v8_identity_bridge")
        if not bridge or not observation["source_id"].startswith("v8-"):
            continue
        names = {r["name"] for r in fec if tokens(r["name"]) == tokens(bridge["legal_name"])}
        if len(names) == 1:
            bridges[observation["candidate_id"]] = (names.pop(), observation["source_id"])
    result = overlay.held_fec_review(
        canonical, previous, panel, {**inputs, "fec": fec}, bridges=bridges, prefix="v8-"
    )
    native = {c["candidate_id"]: c for c in candidates}
    for record in result:
        record.update({k: native[record["candidate_id"]][k] for k in ("name", "district")})
    return result


def office_support(observations):
    histories, negatives, held = [], [], []
    for observation in observations:
        if observation["trait"] != "prior_elected_office":
            continue
        value = observation["value"]
        record = {
            "candidate_id": observation["candidate_id"],
            "observation_id": observation["observation_id"],
            "value": value,
            "state": observation["state"],
            "party": observation["party"],
        }
        if not observation["v8_review"]["factual_qualified"]:
            held.append({**record, "reason": "Not a qualified public elected-office history."})
        elif value.get("time_reference") != "before_2026-11-03":
            held.append({**record, "reason": "Before-election timing not established."})
        elif value.get("explicit_negative"):
            negatives.append(record)
        else:
            histories.append(record)
    return {
        "population": "New source-supported histories, not all nominees.",
        "time_reference": "Before the 2026 election, not before first House entry.",
        "histories": histories,
        "explicit_scoped_negatives": negatives,
        "holds": held,
        "contrast_fitted": False,
        "limitation": "Four new explicit Elected Experience negatives do not supply the unchanged "
        "ten-candidate, three-state comparison gate. Other histories are undated, nonpublic, "
        "overlapping or incomplete; no absence-based negatives or new category contrast is fitted.",
    }


def new_rows(root):
    result = overlay.new_rows(root, previous=PREVIOUS, prefix="v8-", held_reviewer=held_review)
    rows, _, _, _, observations, _, _ = result
    by_key = defaultdict(list)
    for observation in observations:
        by_key[(observation["candidate_id"], observation["trait"])].append(observation)
    for row in rows:
        claims = by_key[(row["candidate_id"], row["trait"])]
        if claims and row["trait"] in {"prior_elected_office", "other_government", "military"}:
            row["contrast_status"] = "scoped_facts_retained_insufficient_comparison_support"
            row["v8_history_time_reference"] = "per_observation_not_automatically_before_election"
    return result


def acquisition_accounting(rows, previous, observations, *, review_key="v8_review"):
    old = {(r["candidate_id"], r["trait"]): r for r in previous}
    new = {(r["candidate_id"], r["trait"]): r for r in rows}
    qualified = {
        (o["candidate_id"], o["trait"]) for o in observations if o[review_key]["factual_qualified"]
    }
    first = {
        k
        for k in qualified
        if old[k]["status"] == "unknown"
        and not old[k]["factual_qualified"]
        and new[k]["factual_qualified"]
    }
    cells = {(o["candidate_id"], o["trait"]) for o in observations}
    changes, breakdown = [], []
    for key in sorted(cells):
        before, after = old[key], new[key]
        changes.append(
            {
                **{
                    k: after[k]
                    for k in ("candidate_id", "name", "contest_id", "state", "party", "trait")
                },
                "baseline_incumbency_group": overlay.incumbent_group(old[(key[0], "incumbency")]),
                "first_observation": key in first,
                "new_source_observations": sum(
                    (o["candidate_id"], o["trait"]) == key for o in observations
                ),
                "before_factual": before["factual_qualified"],
                "after_factual": after["factual_qualified"],
                "before_analysis": before["analysis_eligible"],
                "after_analysis": after["analysis_eligible"],
                "reason": after["eligibility_reason"],
            }
        )
    grouped = defaultdict(list)
    for row in rows:
        group = overlay.incumbent_group(old[(row["candidate_id"], "incumbency")])
        grouped[(row["trait"], row["party"], group, row["performance_eligible"])].append(row)
    for (trait, party, group, eligible), subset in sorted(grouped.items()):
        keys = {(r["candidate_id"], trait) for r in subset}
        breakdown.append(
            {
                "trait": trait,
                "party": party,
                "baseline_incumbency_group": group,
                "performance_eligible": eligible,
                "candidates": len(keys),
                "factual_before": sum(old[k]["factual_qualified"] for k in keys),
                "factual_after": sum(new[k]["factual_qualified"] for k in keys),
                "analysis_before": sum(old[k]["analysis_eligible"] for k in keys),
                "analysis_after": sum(new[k]["analysis_eligible"] for k in keys),
                "new_evidence_fields": len(keys & cells),
                "first_evidence_fields": len(keys & first),
                "supplementary_or_unqualified_fields": len((keys & cells) - first),
            }
        )
    return first, qualified, changes, breakdown


def historical_diagnostics(root, rows):
    """Describe the frozen estimand, not a searched alternative specification."""
    folder = root / PREVIOUS
    fit = next(r for r in read_rows(folder / "fits.jsonl.gz") if r["trait"] == "ethnicity")
    selected = [
        r
        for r in read_rows(folder / "selection.jsonl.gz")
        if r["trait"] == "ethnicity" and r["included"]
    ]
    states = Counter(r["state"] for r in selected)
    return {
        "baseline_version": "V7",
        "trait": "historical_author_Latino_indicator",
        "fit": fit,
        "state_counts": dict(sorted(states.items())),
        "incumbents": sum(r["D_incumbent"] is True for r in selected),
        "nonincumbents": sum(r["D_incumbent"] is False for r in selected),
        "unresolved": sum(r["D_incumbent"] is None for r in selected),
        "included_candidates": selected,
        "overlap_with_other_analytical_fields": {
            trait: sum(
                r["trait"] == trait
                and r["analysis_eligible"]
                and r["contest_id"] in {s["contest_id"] for s in selected}
                and r["party"] == "Democratic"
                for r in rows
            )
            for trait in v1.TRAITS
        },
        "existing_robustness": [
            r for r in read_rows(folder / "sensitivity.jsonl.gz") if r["trait"] == "ethnicity"
        ],
        "exclusion_counts": dict(
            Counter(
                r["reason"]
                for r in read_rows(folder / "selection.jsonl.gz")
                if r["trait"] == "ethnicity" and not r["included"]
            )
        ),
        "limitation": "89 historically classified, linked candidates in 27 states; officeholder "
        "selection and source definitions limit transport. Association is not causal or proof of "
        "predictive improvement. Existing sensitivity/deletion files retain unsuccessful checks.",
    }


def source_outcomes(root, observations, first, previous, rows):
    acquisition = json.loads((root / ACQUISITIONS).read_text())
    attempts = {r["id"]: r for r in acquisition["discovery_dispositions"]}
    sources = {r["id"]: r for r in acquisition["sources"]}
    baseline = {(r["candidate_id"], r["trait"]): r for r in previous}
    current = {(r["candidate_id"], r["trait"]): r for r in rows}
    families = []
    for family in sorted({r["family"] for r in attempts.values()}):
        requests = [r for r in attempts.values() if r["family"] == family]
        claimed = [
            o
            for o in observations
            if attempts[sources[o["source_id"]]["document_id"].removeprefix("v8-")]["family"]
            == family
        ]
        cells = {(o["candidate_id"], o["trait"]) for o in claimed}
        first_cells = first & cells
        document_ids = {sources[o["source_id"]]["document_id"] for o in claimed}
        families.append(
            {
                "family": family,
                "requests": len(requests),
                "acquired_requests": sum(r["status"] == "acquired" for r in requests),
                "unique_acquired_hashes": len(
                    {r["sha256"] for r in requests if r["status"] == "acquired"}
                ),
                "failed_requests": sum(
                    r["status"] == "failed_attempt_not_evidence" for r in requests
                ),
                "retained_existing_requests": sum(
                    r["status"] == "retained_existing_source_not_new_acquisition" for r in requests
                ),
                "registered_documents": len(document_ids),
                "observations": len(claimed),
                "first_evidence_fields": len(first_cells),
                "first_evidence_candidates": len({k[0] for k in first_cells}),
                "newly_analytical_fields": sum(
                    current[k]["analysis_eligible"] and not baseline[k]["analysis_eligible"]
                    for k in cells
                ),
            }
        )
    v1.write_csv(root / OUT / "source-family-outcomes.csv", families)
    return families


def remaining_queue(root, rows, fits):
    current = {(r["candidate_id"], r["trait"]): r for r in rows}
    estimated = {f["trait"]: f["status"] == "estimated" for f in fits}
    queue = list(csv.DictReader((root / QUEUE).open()))
    for record in queue:
        row = current[(record["candidate_id"], record["trait"])]
        for key in (
            "factual_qualified",
            "analysis_eligible",
            "coding_status",
            "timing_status",
            "eligibility_reason",
        ):
            record[key] = row[key]
        record["factual_status"] = row["status"]
        record["no_evidence"] = row["status"] == "unknown"
        held = not row["analysis_eligible"] and row["status"] not in {"unknown", "inapplicable"}
        identity = any(
            word in row["eligibility_reason"].casefold()
            for word in ("conflict", "identity hold", "ambiguous", "discordant")
        )
        record["identity_or_conflict"] = held and identity
        record["timing_or_coding"] = held and not identity
        record["missing_comparison_support"] = not estimated[row["trait"]]
        record["opponent_incumbency_unresolved"] = row["R_incumbency_control"] is None
    v1.write_csv(root / OUT / "remaining-candidate-trait-queue.csv", queue)
    for kind in (
        "no_evidence",
        "identity_or_conflict",
        "timing_or_coding",
        "missing_comparison_support",
    ):
        v1.write_csv(
            root / OUT / f"remaining-{kind.replace('_', '-')}.csv", [r for r in queue if r[kind]]
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
            "gender": "Explicit official filing labels retained factually; incompatible source definitions not pooled.",
            "race": "New filing classifications are not silently pooled into the historical author Black/White estimand.",
            "ethnicity": "Existing restricted historical author-coded Latino indicator only; no universal current contrast.",
            "prior_elected_office": "Four scoped guide negatives; insufficient comparison support; undated histories separate.",
            "other_government": "Explicit jobs distinguished from advisory, elected and contractor roles; negative reference absent.",
            "military": "Dated positive service and one explicit scoped no-military-background response; "
            "the negative category remains below ten candidates in three states.",
            "incumbency": "Unique legal-name/authorized-campaign/website bridges only; ambiguous IDs stay held.",
        },
    )
    first, qualified, changes, breakdown = acquisition_accounting(rows, previous, observations)
    v1.write_csv(root / OUT / "acquisition-field-changes.csv", changes)
    v1.write_csv(root / OUT / "coverage-by-party-and-incumbency.csv", breakdown)
    facts.update(
        newly_informed_candidate_trait_fields=len(first),
        newly_informed_candidates=len({k[0] for k in first}),
        first_evidence_definition="Previously unknown field with newly acquired qualified factual evidence; "
        "identity-only claims and rejected proxies excluded.",
        supplementary_or_unqualified_fields=facts["new_source_candidate_trait_fields"] - len(first),
        party_and_incumbency_coverage=breakdown,
    )
    first_groups = defaultdict(set)
    for cid, trait in first:
        row = next(r for r in rows if r["candidate_id"] == cid and r["trait"] == trait)
        first_groups[
            (
                row["party"],
                overlay.incumbent_group(
                    next(
                        r
                        for r in previous
                        if r["candidate_id"] == cid and r["trait"] == "incumbency"
                    )
                ),
            )
        ].add((cid, trait))
    facts["first_evidence_groups"] = [
        {
            "party": party,
            "baseline_incumbency_group": group,
            "fields": len(keys),
            "candidates": len({k[0] for k in keys}),
        }
        for (party, group), keys in sorted(first_groups.items())
    ]
    facts["source_family_outcomes"] = source_outcomes(root, observations, first, previous, rows)
    old = {(r["candidate_id"], r["trait"]): r for r in previous}
    for record in facts["trait_progress"]:
        trait = record["trait"]
        keys = {
            (r["candidate_id"], trait)
            for r in rows
            if r["trait"] == trait and r["party"] == "Democratic"
        }
        record["newly_informed_candidates"] = len(keys & first)
        record["new_first_qualified_factual_fields"] = sum(
            not old[k]["factual_qualified"] for k in keys & qualified
        )
        record["cohort_denominator"] = len(keys)
        record["unknown_after"] = sum(
            not r["factual_qualified"]
            for r in rows
            if r["trait"] == trait and r["party"] == "Democratic"
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
    from .characteristics_v8_publication import report

    def finalize(fits):
        remaining_queue(root, rows, fits)
        prior = {r["trait"]: r for r in read_rows(root / PREVIOUS / "fits.jsonl.gz")}
        current = {r["trait"]: r for r in fits}
        panel_by_id = {r["D_candidate_election_id"]: r for r in panel}
        prediction_ids = defaultdict(set)
        for prediction in read_rows(root / OUT / "full-population-predictions.jsonl.gz"):
            prediction_ids[prediction["trait"]].add(prediction["candidate_election_id"])
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
            group["fitted_after"] = (
                sum(
                    (panel_by_id[cid]["contest_id"], panel_by_id[cid]["D_name"]) in members
                    for cid in current[trait].get("candidate_election_ids", [])
                )
                if group["party"] == "Democratic"
                else 0
            )
            group["full_fit_prediction_supported"] = (
                sum(
                    (panel_by_id[cid]["contest_id"], panel_by_id[cid]["D_name"]) in members
                    for cid in prediction_ids[trait]
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
        v1.write_csv(root / OUT / "v7-v8-trait-progress.csv", facts["trait_progress"])
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
        recompute_traits=("religion",),
        extra_inputs=(
            BASELINE,
            QUEUE,
            ACQUISITIONS,
            SPEC,
            "data/house-characteristics-v8-identity-decisions.json",
            "data/house-characteristics-v8-national-review.json",
            "data/house-characteristics-v8-followup-review.json",
            "data/house-characteristics-v8-source-plan.json",
            "data/house-characteristics-v8-supplement-plan.json",
            "which_candidate/characteristics_v8.py",
            "which_candidate/characteristics_v8_extract.py",
            "which_candidate/characteristics_v8_prediction.py",
            "which_candidate/characteristics_v8_publication.py",
            f"{PREVIOUS}/candidate-traits.jsonl.gz",
            f"{PREVIOUS}/panel-overlay.jsonl.gz",
            "data/house-characteristics-research.json",
            "data/house-characteristics-receipts.json",
        ),
    )


if __name__ == "__main__":
    print(json.dumps(build(Path(__file__).resolve().parents[1]), indent=2))
