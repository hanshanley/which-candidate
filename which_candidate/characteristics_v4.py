"""V4 source-acquisition successor, preserving the frozen V3 estimands and evidence."""

import argparse
import calendar
import copy
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

from . import characteristics_v2 as v2
from . import house_characteristics as v1
from .characteristics_research import normalized
from .characteristics_v4_acquisition import ACQUISITIONS, BASELINE, QUEUE
from .storage import read_rows, write_json

VERSION = "house-characteristics-v4"
OUT = f"results/{VERSION}"
SPEC = "docs/HOUSE_CHARACTERISTICS_V4_SPEC.md"
PREVIOUS = "results/house-characteristics-v3"


def age_at(birthday):
    return (
        v1.CUTOFF.year
        - birthday.year
        - ((v1.CUTOFF.month, v1.CUTOFF.day) < (birthday.month, birthday.day))
    )


def birth_interval(value):
    if isinstance(value, str):
        age = age_at(date.fromisoformat(value))
        return [age, age]
    year, month = value["birth_year"], value.get("birth_month")
    earliest = date(year, month or 1, 1)
    latest = date(year, month or 12, calendar.monthrange(year, month or 12)[1])
    return [age_at(latest), age_at(earliest)]


def incumbent_group(row):
    return (
        "incumbent"
        if row["analysis_value"] is True
        else "nonincumbent"
        if row["analysis_value"] is False
        else "unknown_incumbency"
    )


def office_category_support(observations):
    categories = {
        "state": (
            "michigan house",
            "michigan senate",
            "iowa state",
            "state senator",
            "california senator",
            "california senate",
            "pennsylvania house",
        ),
        "local": (
            "city commission",
            "city council",
            "city commissioner",
            "councilmember",
            "supervisor",
            "mayor",
            "school board",
            "commissioner",
        ),
        "federal": ("us house",),
    }
    histories = []
    for observation in observations:
        if observation["trait"] != "prior_elected_office":
            continue
        value = observation["value"]
        if value["time_reference"] != "before_2026-11-03":
            raise ValueError("Incompatible V4 office-history time reference")
        history = value["history"].casefold()
        groups = value.get("supported_categories")
        if groups is None:
            groups = [
                group for group, words in categories.items() if any(w in history for w in words)
            ]
        elif not groups or len(set(groups)) != len(groups) or set(groups) - categories.keys():
            raise ValueError(f"Invalid reviewed office categories: {groups}")
        if not groups:
            raise ValueError(f"Unreviewed positive office category: {observation['candidate_id']}")
        histories.append(
            {
                "candidate_id": observation["candidate_id"],
                "observation_id": observation["observation_id"],
                "source_recorded_history": value["history"],
                "supported_categories": groups,
            }
        )
    return {
        "population": "Only newly acquired, explicitly before-2026 office histories; not all nominees.",
        "question": "Positive office categories, not service-versus-nonservice.",
        "histories": histories,
        "overlapping_counts": {
            group: sum(group in r["supported_categories"] for r in histories)
            for group in categories
        },
        "single_recorded_category_counts": {
            group: sum(r["supported_categories"] == [group] for r in histories)
            for group in categories
        },
        "limitation": "State/local histories overlap. A single recorded category is not proof "
        "of never holding another office. Disjoint recorded groups also fail the unchanged "
        "ten-candidate category gate. Earlier differently timed histories are not silently pooled.",
        "contrast_fitted": False,
    }


def held_fec_review(candidates, previous, panel, inputs):
    old = {(r["candidate_id"], r["trait"]): r for r in previous}
    needed_opponents = {r["contest_id"] for r in panel if r["R_name"] and r["R_incumbent"] is None}
    bridges = {
        "220322": ("FORD, JAMES (J.D.) DAVID", "v4-in-ford-2020-220322"),
        "221015": ("HARVIE, ROBERT J", "v4-pa-harvie-official-221015"),
    }
    acquired_ids = {
        o["source_id"]
        for o in inputs["reviewed_characteristic_observations"]
        if o["source_id"].startswith("v4-")
    }
    reviews = []
    for candidate in candidates:
        cid = candidate["candidate_id"]
        if old[(cid, "incumbency")]["analysis_eligible"]:
            continue
        if candidate["party"] != "Democratic" and not (
            candidate["party"] == "Republican" and candidate["contest_id"] in needed_opponents
        ):
            continue
        parties = {"DEM", "DFL"} if candidate["party"] == "Democratic" else {"REP"}
        bridge = bridges.get(cid)
        matches = [
            record
            for record in inputs["fec"]
            if record["chamber"] == "house"
            and record["election_year"] == 2026
            and record["state"] == candidate["state"]
            and record["district"] == candidate["district"]
            and record["party"] in parties
            and (
                normalized(record["first"] + " " + record["last"]) == normalized(candidate["name"])
                or bridge
                and bridge[1] in acquired_ids
                and record["name"] == bridge[0]
            )
        ]
        if (
            len({r["fec_id"] for r in matches}) != 1
            or len({r["incumbent"] for r in matches}) != 1
            or type(matches[0]["incumbent"]) is not bool
        ):
            continue
        reviews.append(
            {
                **{
                    k: candidate[k]
                    for k in ("candidate_id", "contest_id", "name", "state", "district", "party")
                },
                "trait": "incumbency",
                "value": matches[0]["incumbent"],
                "held_records": matches,
                "new_acquisition": False,
                "identity_bridge": bridge[1]
                if bridge
                else "exact_full_name_state_party_House_district_year",
                "qualification": "Unique held FEC person-contest record; explicit 2026 election "
                "classification, not independent verification of federal service or lifetime nonservice. "
                "Ambiguous multiple FEC IDs and unsupported nickname links stay held.",
            }
        )
    return reviews


def new_rows(root, *, previous=PREVIOUS, prefix="v4-", held_reviewer=held_fec_review):
    root = Path(root)
    release = prefix.rstrip("-")
    release_label = release.upper()
    previous_label = f"V{int(release[1:]) - 1}"
    review_key = f"{release}_review"
    previous_path = previous
    previous = read_rows(root / previous_path / "candidate-traits.jsonl.gz")
    rows = copy.deepcopy(previous)
    by_key = {(r["candidate_id"], r["trait"]): r for r in rows}
    candidates = read_rows(root / "results/house/candidates.jsonl.gz")
    panel = copy.deepcopy(read_rows(root / previous_path / "panel-overlay.jsonl.gz"))
    inputs = read_rows(root / "results/house/source-inputs.jsonl.gz")[0]
    observations = [
        r
        for r in inputs["reviewed_characteristic_observations"]
        if r["source_id"].startswith(prefix)
    ]
    grouped = defaultdict(list)
    for observation in observations:
        grouped[(observation["candidate_id"], observation["trait"])].append(observation)
    conflicts = []
    ranks = {"associate": 0, "bachelors": 1, "masters": 2, "doctoral_or_professional": 3}
    for key, claims in grouped.items():
        row = by_key[key]
        row["source_recorded_value"].setdefault("reviewed_facts", []).extend(claims)
        row["evidence"].extend(claims)
        row[f"{release}_acquisition_observation_ids"] = [c["observation_id"] for c in claims]
        row["review_status"] = f"literal_subject_and_timing_reviewed_{release}"
        row["factual_qualified"] |= any(c[review_key]["factual_qualified"] for c in claims)
        if row["factual_qualified"]:
            row["status"] = "qualified"
        row["eligibility_reason"] += f" {release_label}: " + " ".join(
            dict.fromkeys(c["qualification"] for c in claims)
        )
        values = [
            c[review_key]["analysis_value"]
            for c in claims
            if c[review_key]["analysis_value"] is not None
        ]
        trait = row["trait"]
        chosen = None
        if trait == "age":
            intervals = [birth_interval(c["value"]) for c in claims]
            lower, upper = max(i[0] for i in intervals), min(i[1] for i in intervals)
            if row["analysis_eligible"] and not lower <= row["analysis_value"] <= upper:
                conflicts.append(
                    {
                        "candidate_id": key[0],
                        "trait": trait,
                        "existing": row["analysis_value"],
                        "new": intervals,
                    }
                )
                row.update(analysis_eligible=False, analysis_value=None, status="uncertain")
            elif lower <= upper:
                row["uncertainty"]["age_years_interval"] = [lower, upper]
                chosen = lower if lower == upper else None
                if chosen is None and not row["analysis_eligible"]:
                    row["value"] = {"age_years_interval": [lower, upper]}
                    row["coding_status"] = "source_birth_interval_not_exact_age"
            else:
                raise ValueError(f"Inconsistent newly acquired birth claims: {key}")
        elif trait == "education":
            if values:
                chosen = max(
                    [*values, *([row["analysis_value"]] if row["analysis_eligible"] else [])],
                    key=ranks.__getitem__,
                )
        elif trait == "profession":
            families = set(values)
            for c in claims:
                if isinstance(c["value"], list):
                    families.update(c["value"])
            if row["analysis_eligible"]:
                families.add(row["analysis_value"])
            if len(families) > 1:
                row.update(analysis_eligible=False, analysis_value=None)
                row["coding_status"] = "multiple_supported_historical_professional_families"
            elif values:
                chosen = values[-1]
        elif values:
            distinct = set(values)
            if row["analysis_eligible"]:
                distinct.add(row["analysis_value"])
            if len(distinct) == 1:
                chosen = values[-1]
            else:
                conflicts.append(
                    {"candidate_id": key[0], "trait": trait, "values": sorted(distinct)}
                )
                row.update(analysis_eligible=False, analysis_value=None, status="uncertain")
        if chosen is not None:
            row.update(
                value=chosen,
                analysis_value=chosen,
                analysis_eligible=True,
                coding_status=f"explicit_{release_label}_completed_credential_or_dated_historical_fact",
                timing_status="pre_election_fact_retrospectively_acquired",
            )
        if trait in {"prior_elected_office", "other_government"}:
            row[f"{release}_history_time_reference"] = "before_2026-11-03"
            row["contrast_status"] = "positive_histories_no_explicit_negative_reference"
        if trait == "military":
            row["contrast_status"] = "positive_service_no_explicit_nonservice_reference"
        if not row["analysis_eligible"] and trait != "age":
            row["value"] = {
                f"preserved_{previous_label}_value": row["value"],
                f"{release_label}_source_observations": [
                    {"value": c["value"], "publication_date": c["publication_date"]} for c in claims
                ],
            }
        row["prospective_model_eligible"] = False

    held = held_reviewer(candidates, previous, panel, inputs) if held_reviewer else []
    for review in held:
        row = by_key[(review["candidate_id"], "incumbency")]
        row["source_recorded_value"].setdefault(f"held_evidence_reviews_{release}", []).append(
            review
        )
        row["evidence"].append(review)
        row.update(
            value=review["value"],
            analysis_value=review["value"],
            analysis_eligible=True,
            status="qualified",
            factual_qualified=True,
            coding_status="explicit_held_FEC_election_classification_person_contest_review",
            timing_status="2026_election_record_not_verified_lifetime_service",
        )
        row["eligibility_reason"] += f" {release_label} held evidence: " + review["qualification"]
    for outcome in panel:
        for party, label in (("Democratic", "D"), ("Republican", "R")):
            matches = [
                c
                for c in candidates
                if c["contest_id"] == outcome["contest_id"]
                and c["party"] == party
                and c["name"] == outcome[f"{label}_name"]
            ]
            if len(matches) == 1 and outcome[f"{label}_incumbent"] is None:
                row = by_key[(matches[0]["candidate_id"], "incumbency")]
                if row["analysis_eligible"]:
                    outcome[f"{label}_incumbent"] = row["analysis_value"]
                    outcome[f"{release}_{label}_incumbency_evidence"] = {
                        "candidate_id": row["candidate_id"],
                        "source": "reviewed_held_FEC" if held_reviewer else "reviewed_new_FEC",
                        "service_verification_unchanged": True,
                    }
    outcomes = {r["contest_id"]: r for r in panel}
    for row in rows:
        row["D_incumbency_control"] = outcomes[row["contest_id"]]["D_incumbent"]
        row["R_incumbency_control"] = outcomes[row["contest_id"]]["R_incumbent"]
        row["field_eligible"] = row["analysis_eligible"]
        row[f"incumbency_group_{release}"] = incumbent_group(
            by_key[(row["candidate_id"], "incumbency")]
        )
    return rows, candidates, panel, previous, observations, conflicts, held


def progress(
    root,
    rows,
    previous,
    observations,
    conflicts,
    held,
    *,
    out=OUT,
    acquisition=ACQUISITIONS,
    limitations_override=None,
):
    root = Path(root)
    output = root / out
    output.mkdir(parents=True, exist_ok=True)
    old = {(r["candidate_id"], r["trait"]): r for r in previous}
    cells = {(r["candidate_id"], r["trait"]) for r in observations}
    informed = {key for key in cells if old[key]["status"] == "unknown"}
    changes = []
    for row in rows:
        key = (row["candidate_id"], row["trait"])
        before = old[key]
        if key in cells or row["analysis_eligible"] != before["analysis_eligible"]:
            changes.append(
                {
                    **{
                        k: row[k]
                        for k in ("candidate_id", "contest_id", "name", "state", "party", "trait")
                    },
                    "performance_eligible": row["performance_eligible"],
                    "baseline_incumbency_group": incumbent_group(
                        old[(row["candidate_id"], "incumbency")]
                    ),
                    "new_source_observations": sum(
                        (o["candidate_id"], o["trait"]) == key for o in observations
                    ),
                    "first_observation": key in informed,
                    "before_factual": before["factual_qualified"],
                    "after_factual": row["factual_qualified"],
                    "before_analysis": before["analysis_eligible"],
                    "after_analysis": row["analysis_eligible"],
                    "before_value": before["analysis_value"],
                    "after_value": row["analysis_value"],
                    "reason": row["eligibility_reason"],
                }
            )
    v1.write_csv(output / "acquisition-field-changes.csv", changes)
    v1.write_csv(output / "source-conflicts.csv", conflicts)
    write_json(output / "held-evidence-reviews.json", held)
    office_support = office_category_support(observations)
    write_json(output / "positive-office-category-support.json", office_support)
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
                    and incumbent_group(old[(r["candidate_id"], "incumbency")]) == group
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
                            (r["candidate_id"], trait) in cells for r in subset
                        ),
                    }
                )
    v1.write_csv(output / "coverage-by-incumbency.csv", groups)
    acquisition = json.loads((root / acquisition).read_text())
    limitations = {
        "age": "Exact age remains incumbent-heavy; year/month intervals are separate.",
        "gender": "No new explicit gender classification; inferred historical gender rejected.",
        "race": "Restricted historical CAWP women; additional identity groups fail category support.",
        "ethnicity": "Positive identities retained; no defensible complementary reference.",
        "religion": "Explicit dated descriptions only; new challenger coverage remains selective.",
        "education": "Completed supported level only; attendance, undated timing and contradictions held.",
        "profession": "Four historical families only; mixed families and outside occupations held.",
        "prior_elected_office": "New histories are before 2026, not before first House entry; no negative reference.",
        "other_government": "Non-elected roles recorded; paid employment not inferred from advisory membership.",
        "military": "Positive service support improves; no supported nonservice reference.",
        "incumbency": "17 Democratic holds remain; FEC classification is not verified service.",
        "house_service": "Verified current federal incumbents only.",
        "donor_ideology": "Selective donor-linked population, not universal moderation.",
        "voting_ideology": "Lagged Congress-specific incumbent record; not campaign ideology.",
        "party_unity": "Cutoff-qualified current incumbent record; newcomers are not zero.",
    }
    if limitations_override:
        limitations.update(limitations_override)
    trait_progress = []
    for trait in v1.TRAITS:
        subset = [r for r in rows if r["party"] == "Democratic" and r["trait"] == trait]
        acquired = [o for o in observations if o["party"] == "Democratic" and o["trait"] == trait]
        trait_progress.append(
            {
                "trait": trait,
                "new_evidence_source_hashes": len({o["receipt"]["sha256"] for o in acquired}),
                "new_observations": len(acquired),
                "source_informed_candidates": len({o["candidate_id"] for o in acquired}),
                "newly_informed_candidates": len({cid for cid, t in informed if t == trait}),
                "existing_fields_newly_qualified": sum(
                    r["party"] == "Democratic" and r["trait"] == trait for r in held
                ),
                "factual_before": sum(
                    old[(r["candidate_id"], trait)]["factual_qualified"] for r in subset
                ),
                "factual_after": sum(r["factual_qualified"] for r in subset),
                "analytical_before": sum(
                    old[(r["candidate_id"], trait)]["analysis_eligible"] for r in subset
                ),
                "analytical_after": sum(r["analysis_eligible"] for r in subset),
                "remaining_limitations": limitations[trait],
            }
        )
    return {
        "acquisition": acquisition,
        "newly_acquired_observations": len(observations),
        "new_source_candidates": len({o["candidate_id"] for o in observations}),
        "new_source_candidate_trait_fields": len(cells),
        "newly_informed_candidate_trait_fields": len(informed),
        "newly_informed_candidates": len({k[0] for k in informed}),
        "existing_observations_newly_qualified": len(held),
        "existing_D_fields_newly_qualified": sum(r["party"] == "Democratic" for r in held),
        "newly_qualified_existing_fields": len(held),
        "newly_analysis_eligible_D_fields": sum(
            r["party"] == "Democratic"
            and r["analysis_eligible"]
            and not old[(r["candidate_id"], r["trait"])]["analysis_eligible"]
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
        "positive_office_category_support": office_support,
        "coverage_by_incumbency": groups,
        "trait_progress": trait_progress,
    }


def build(root):
    root = Path(root)
    v2.verify_frozen(root, BASELINE)
    rows, candidates, panel, previous, observations, conflicts, held = new_rows(root)
    facts = progress(root, rows, previous, observations, conflicts, held)
    from .characteristics_v4_publication import report

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
        v1.write_csv(root / OUT / "v3-v4-trait-progress.csv", facts["trait_progress"])
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
            "which_candidate/characteristics_v4.py",
            "which_candidate/characteristics_v4_publication.py",
            "which_candidate/characteristics_v4_batch.py",
            f"{PREVIOUS}/candidate-traits.jsonl.gz",
            f"{PREVIOUS}/panel-overlay.jsonl.gz",
            "data/house-characteristics-research.json",
            "data/house-characteristics-receipts.json",
        ),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(build(args.root), indent=2))
