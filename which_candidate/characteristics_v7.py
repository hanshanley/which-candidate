"""V7: independently linked historical classifications and unknown-field acquisition."""

import json
import unicodedata
from collections import defaultdict
from pathlib import Path

from . import characteristics_v2 as v2
from . import characteristics_v4 as overlay
from . import house_characteristics as v1
from .characteristics_v7_acquisition import ACQUISITIONS, BASELINE, PREVIOUS, QUEUE
from .storage import read_rows, write_json

VERSION = "house-characteristics-v7"
OUT = f"results/{VERSION}"
SPEC = "docs/HOUSE_CHARACTERISTICS_V7_SPEC.md"


def orthographic(value):
    return "".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c))


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
    reviews = overlay.held_fec_review(
        canonical, previous, panel, {**inputs, "fec": fec}, bridges={}, prefix="v7-"
    )
    native = {c["candidate_id"]: c for c in candidates}
    for review in reviews:
        candidate = native[review["candidate_id"]]
        review.update({k: candidate[k] for k in ("name", "district")})
        ids = {r["fec_id"] for r in review["held_records"]}
        review["held_records"] = [
            r
            for r in inputs["fec"]
            if r["fec_id"] in ids
            and r["chamber"] == "house"
            and r["election_year"] == 2026
            and r["state"] == candidate["state"]
            and district(r["district"]) == district(candidate["district"])
        ]
        review["identity_bridge"] = "full_tokens_diacritics_and_equivalent_at_large_notation_only"
        review["qualification"] += (
            " V7 removes diacritics only, retaining full token content/order; "
        )
        review["qualification"] += "no invented nickname or middle-name bridge."
    return reviews


def restrict_identities(rows, observations, previous_observations, conflicts):
    new = defaultdict(list)
    old = defaultdict(list)
    for observation in observations:
        new[(observation["candidate_id"], observation["trait"])].append(observation)
    for observation in previous_observations:
        old[(observation["candidate_id"], observation["trait"])].append(observation)
    for row in rows:
        key = (row["candidate_id"], row["trait"])
        if row["trait"] not in {"race", "ethnicity"} or key not in new:
            continue
        claims = new[key]
        reason = None
        if row["trait"] == "race":
            codes = {c["v7_review"]["analysis_value"] for c in claims}
            old_values = [
                value.casefold()
                for c in old[key]
                for value in (c["value"] if isinstance(c["value"], list) else [])
            ]
            if codes not in ({"Black"}, {"White"}):
                reason = "Mixed, nonbinary, missing or discordant historical source race classifications."
            elif any(v not in {next(iter(codes)).casefold()} for v in old_values):
                reason = "Existing explicit identity definitions are not concordant with the new binary classification."
            row["contrast_status"] = (
                "restricted_historical_Black_White_classification_not_universal_identity"
            )
        else:
            values = {
                c["value"].get("source_latino_indicator")
                for c in claims
                if isinstance(c["value"], dict)
            }
            positive_old = any(
                isinstance(c["value"], list)
                and any(
                    "hispanic" in v.casefold()
                    or "latina" in v.casefold()
                    or "mexican-american" in v.casefold()
                    for v in c["value"]
                )
                for c in old[key]
            )
            if values == {0} and positive_old:
                reason = "Author-coded zero conflicts with independently explicit Hispanic/Latina identity."
            row["contrast_status"] = (
                "explicit_historical_author_Latino_indicator_not_universal_ethnicity"
            )
        if reason:
            row.update(analysis_eligible=False, analysis_value=None, field_eligible=False)
            row["coding_status"] = "historical_identity_definition_or_conflict_hold"
            row["eligibility_reason"] += " " + reason
            conflicts.append({"candidate_id": key[0], "trait": key[1], "reason": reason})


def new_rows(root):
    result = overlay.new_rows(root, previous=PREVIOUS, prefix="v7-", held_reviewer=held_review)
    rows, _, _, _, observations, conflicts, _ = result
    inputs = read_rows(Path(root) / "results/house/source-inputs.jsonl.gz")[0]
    restrict_identities(
        rows,
        observations,
        [
            r
            for r in inputs["reviewed_characteristic_observations"]
            if not r["source_id"].startswith("v7-")
        ],
        conflicts,
    )
    return result


def party_coverage(root, rows, previous, observations):
    old = {(r["candidate_id"], r["trait"]): r for r in previous}
    cells = {(o["candidate_id"], o["trait"]) for o in observations}
    grouped = defaultdict(list)
    for row in rows:
        group = overlay.incumbent_group(old[(row["candidate_id"], "incumbency")])
        grouped[(row["trait"], row["party"], group, row["performance_eligible"])].append(row)
    result = []
    for (trait, party, group, eligible), subset in sorted(grouped.items()):
        keys = {(r["candidate_id"], trait) for r in subset}
        result.append(
            {
                "trait": trait,
                "party": party,
                "baseline_incumbency_group": group,
                "performance_eligible": eligible,
                "candidates": len(subset),
                "factual_before": sum(old[k]["factual_qualified"] for k in keys),
                "factual_after": sum(r["factual_qualified"] for r in subset),
                "analysis_before": sum(old[k]["analysis_eligible"] for k in keys),
                "analysis_after": sum(r["analysis_eligible"] for r in subset),
                "new_evidence_fields": len(keys & cells),
                "first_evidence_fields": sum(old[k]["status"] == "unknown" for k in keys & cells),
            }
        )
    v1.write_csv(Path(root) / OUT / "coverage-by-party-and-incumbency.csv", result)
    return result


def build(root):
    root = Path(root)
    v2.verify_frozen(root, BASELINE)
    rows, candidates, panel, previous, observations, conflicts, held = new_rows(root)
    holds = [
        r
        for r in rows
        if r["party"] == "Democratic" and r["trait"] == "incumbency" and not r["analysis_eligible"]
    ]
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
            "race": "Restricted historical source-classified Black/White officeholders and CAWP women; "
            "overlap, discordance and incompatible identity definitions excluded.",
            "ethnicity": "Explicit historical author-coded Latino 0/1 only; not a universal "
            "current Hispanic/non-Hispanic self-identification comparison.",
            "religion": "New 2011 church membership is factual historical evidence, not verified 2026 affiliation.",
            "military": "CongressData 'No military service mentioned' is not a negative; contrast unavailable.",
            "incumbency": f"{len(holds)} Democratic holds; orthographic normalization preserves all "
            "tokens and does not resolve nickname, middle-name or duplicate-ID ambiguity.",
        },
    )
    old = {(r["candidate_id"], r["trait"]): r for r in previous}
    for record in facts["trait_progress"]:
        record["newly_informed_candidates"] = len(
            {
                o["candidate_id"]
                for o in observations
                if o["party"] == "Democratic"
                and o["trait"] == record["trait"]
                and old[(o["candidate_id"], o["trait"])]["status"] == "unknown"
            }
        )
    facts["party_and_incumbency_coverage"] = party_coverage(root, rows, previous, observations)
    population = defaultdict(list)
    for observation in observations:
        key = (observation["candidate_id"], observation["trait"])
        population[
            (
                observation["party"],
                overlay.incumbent_group(old[(observation["candidate_id"], "incumbency")]),
            )
        ].append(key)
    facts["source_population_progress"] = [
        {
            "party": party,
            "baseline_incumbency_group": group,
            "source_candidates": len({k[0] for k in keys}),
            "new_evidence_fields": len(set(keys)),
            "first_evidence_fields": sum(old[k]["status"] == "unknown" for k in set(keys)),
        }
        for (party, group), keys in sorted(population.items())
    ]
    facts["newly_ineligible_D_fields"] = [
        {k: row[k] for k in ("candidate_id", "name", "trait", "eligibility_reason")}
        for row in rows
        if row["party"] == "Democratic"
        and old[(row["candidate_id"], row["trait"])]["analysis_eligible"]
        and not row["analysis_eligible"]
    ]
    facts["positive_office_category_support"]["limitation"] = (
        "Positive categories overlap and recorded single-category histories are incomplete. "
        "Nominal counts do not establish mutually exclusive service histories or a no-office reference."
    )
    write_json(
        root / OUT / "positive-office-category-support.json",
        facts["positive_office_category_support"],
    )
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
    from .characteristics_v7_publication import report

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
        facts["control_unlocked_contests"] = [
            r["contest_id"]
            for r, p in zip(panel, read_rows(root / PREVIOUS / "panel-overlay.jsonl.gz"))
            if r["eligible"]
            and (p["D_incumbent"] is None or p["R_incumbent"] is None)
            and r["D_incumbent"] is not None
            and r["R_incumbent"] is not None
        ]
        v1.write_csv(root / OUT / "v6-v7-trait-progress.csv", facts["trait_progress"])
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
            "data/house-characteristics-v7-identity-decisions.json",
            "docs/HOUSE_CHARACTERISTICS_V7_ACQUISITION.md",
            "data/house-characteristics-v7-congressdata-audit.json",
            "data/house-characteristics-v7-congressdata-person-review.csv",
            "scripts/characteristics-v7-congressdata.R",
            "which_candidate/characteristics_v4.py",
            "which_candidate/characteristics_v7.py",
            "which_candidate/characteristics_v7_extract.py",
            "which_candidate/characteristics_v7_batch.py",
            "which_candidate/characteristics_v7_publication.py",
            f"{PREVIOUS}/candidate-traits.jsonl.gz",
            f"{PREVIOUS}/panel-overlay.jsonl.gz",
            "data/house-characteristics-research.json",
            "data/house-characteristics-receipts.json",
        ),
    )


if __name__ == "__main__":
    print(json.dumps(build(Path(__file__).resolve().parents[1]), indent=2))
