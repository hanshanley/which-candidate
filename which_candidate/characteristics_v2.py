"""Evidence-qualified v2 overlay; v1 is an immutable relational evidence source."""

import argparse
import copy
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from . import house_characteristics as v1
from .house_validation import person_key
from .storage import fingerprint, json_bytes, read_rows, write_json, write_rows

VERSION = "house-characteristics-v2"
OUT = f"results/{VERSION}"
SPEC = "docs/HOUSE_CHARACTERISTICS_V2_SPEC.md"
REVIEW = "data/house-characteristics-v2-review.json"
SEAL = "data/house-characteristics-v2-review-seal.json"
PROTECTION = "data/house-characteristics-v2-frozen.json"
PROFILE_FIELDS = {
    "education": ("education",),
    "profession": ("professional_history", "occupation", "occupational_background"),
    "prior_elected_office": ("prior_office",),
    "other_government": ("public_service_experience", "governmental_experience"),
    "military": ("military_service",),
}


def digest(value):
    return hashlib.sha256(json_bytes(value)).hexdigest()


def selected_profiles(candidates, review):
    for candidate in candidates:
        if candidate["party"] != "Democratic":
            continue
        background = candidate["background"]
        for collection in ("reviewed_candidate_profiles", "official_candidate_profiles"):
            for index, profile in enumerate(background[collection]):
                if (
                    collection == "official_candidate_profiles"
                    or profile.get("source_kind") in review["profile_source_kinds"]
                ):
                    yield candidate, collection, index, profile


def seal_review(root):
    """Seal the already completed literal review, never run during ordinary replay."""
    root = Path(root)
    review = json.loads((root / REVIEW).read_text())
    candidates, _, _ = v1.sources(root)
    write_json(
        root / SEAL,
        {
            "review_sha256": digest(review),
            "profiles": [
                {
                    "identity": {
                        k: c[k]
                        for k in (
                            "candidate_id",
                            "contest_id",
                            "name",
                            "state",
                            "district",
                            "party",
                        )
                    },
                    "collection": collection,
                    "profile_index": index,
                    "profile_sha256": digest(profile),
                }
                for c, collection, index, profile in selected_profiles(candidates, review)
            ],
        },
    )
    protection = root / PROTECTION
    if not protection.exists():
        old = json.loads((root / "data/democratic-background-gap-baseline.json").read_text())
        hashes = dict(old["protected_analysis_sha256"])
        for folder in (v1.OUT, "publication/characteristics-v1"):
            hashes.update(
                {
                    p.relative_to(root).as_posix(): fingerprint(p)["sha256"]
                    for p in (root / folder).rglob("*")
                    if p.is_file()
                }
            )
        write_json(
            protection,
            {"baseline_commit": review["baseline_commit"], "protected_sha256": hashes},
        )


def verify_frozen(root):
    protection = json.loads((root / PROTECTION).read_text())
    for name, expected in protection["protected_sha256"].items():
        if fingerprint(root / name)["sha256"] != expected:
            raise ValueError(f"Changed frozen characteristics input: {name}")
    return len(protection["protected_sha256"])


def age_band(interval):
    if not interval or len(interval) != 2 or interval[0] > interval[1]:
        return None

    def band(age):
        return "under_40" if age < 40 else "40_to_59" if age < 60 else "60_or_older"

    return band(interval[0]) if band(interval[0]) == band(interval[1]) else None


def common_support(rows, trait):
    states = defaultdict(set)
    for row in rows:
        states[(row["D_incumbent"], row["R_incumbent"])].add(row["state"])
    return [r for r in rows if len(states[(r["D_incumbent"], r["R_incumbent"])]) >= 3]


def paired(rows, trait, levels):
    """Training-only nuisance handling; an unseen test stratum stays unsupported."""
    base, augmented, names, focal = v1.designs(rows, trait, levels)
    y = np.array([r["descriptive_gap_share_pp"] for r in rows])
    predictions, folds = [], []
    for state in sorted({r["state"] for r in rows}):
        test = [i for i, r in enumerate(rows) if r["state"] == state]
        people = {person_key(rows[i]) for i in test}
        train = [
            i for i, r in enumerate(rows) if r["state"] != state and person_key(r) not in people
        ]
        keep = list(range(base.shape[1]))
        reason = None
        for j in reversed(range(len(names))):
            if names[j] not in {"D_incumbent", "R_incumbent"} or not train:
                continue
            others = [k for k in keep if k != j]
            relation = np.linalg.lstsq(base[np.ix_(train, others)], base[train, j], rcond=None)[0]
            if np.allclose(
                base[np.ix_(train, others)] @ relation, base[train, j], atol=1e-10, rtol=0
            ):
                if np.allclose(
                    base[np.ix_(test, others)] @ relation, base[test, j], atol=1e-10, rtol=0
                ):
                    keep.remove(j)
                else:
                    reason = "unseen_test_incumbency_stratum"
        designs = (base[:, keep], augmented[:, [*keep, *range(base.shape[1], augmented.shape[1])]])
        ranks = [int(np.linalg.matrix_rank(x[train])) if train else 0 for x in designs]
        conditions = [
            float(np.linalg.cond(x[train])) if train and ranks[i] == x.shape[1] else None
            for i, x in enumerate(designs)
        ]
        if len(train) <= designs[1].shape[1] + 3 or len({rows[i]["state"] for i in train}) < 8:
            reason = reason or "insufficient_training_support"
        if any(r != x.shape[1] for r, x in zip(ranks, designs)):
            reason = reason or "rank_deficient_training_design"
        if any(c is None or c >= 1e10 for c in conditions):
            reason = reason or "ill_conditioned_training_design"
        folds.append(
            {
                "trait": trait,
                "held_out_state": state,
                "status": "failed" if reason else "estimated",
                "failure_reason": reason,
                "training_ids": [rows[i]["D_candidate_election_id"] for i in train],
                "test_ids": [rows[i]["D_candidate_election_id"] for i in test],
                "training_people": sorted({person_key(rows[i]) for i in train}),
                "test_people": sorted(people),
                "baseline_terms": [names[i] for i in keep],
                "augmented_terms": [*[names[i] for i in keep], *focal],
                "training_ranks": ranks,
                "training_conditions": conditions,
                "training_only_preprocessing": True,
            }
        )
        if reason:
            continue
        betas = [np.linalg.lstsq(x[train], y[train], rcond=None)[0] for x in designs]
        for i in test:
            errors = [float(y[i] - x[i] @ b) for x, b in zip(designs, betas)]
            predictions.append(
                {
                    "trait": trait,
                    "candidate_election_id": rows[i]["D_candidate_election_id"],
                    "contest_id": rows[i]["contest_id"],
                    "state": state,
                    "name": rows[i]["D_name"],
                    "baseline_error_share_pp": errors[0],
                    "augmented_error_share_pp": errors[1],
                }
            )
    return predictions, folds


def reviewed_rows(root):
    candidates, panel, inputs = v1.sources(root)
    review = json.loads((root / REVIEW).read_text())
    seal = json.loads((root / SEAL).read_text())
    if seal["review_sha256"] != digest(review):
        raise ValueError("Changed review decisions require literal re-review and explicit sealing")
    selected = list(selected_profiles(candidates, review))
    expected = [
        {
            "identity": {
                k: c[k]
                for k in ("candidate_id", "contest_id", "name", "state", "district", "party")
            },
            "collection": collection,
            "profile_index": index,
            "profile_sha256": digest(profile),
        }
        for c, collection, index, profile in selected
    ]
    if expected != seal["profiles"]:
        raise ValueError("Changed candidate identity or reviewed source profile")
    baseline = read_rows(root / v1.OUT / "candidate-traits.jsonl.gz")
    rows = []
    for index, old in enumerate(baseline, start=1):
        row = copy.deepcopy(old)
        row["baseline_trait_row"] = index
        row["source_recorded_value"] = {"baseline_trait_row": index}
        row["evidence"] = [{"table": f"{v1.OUT}/candidate-traits.jsonl.gz", "row": index}]
        row["factual_qualified"] = old["status"] == "qualified"
        row["analysis_eligible"] = old["field_eligible"]
        row["analysis_value"] = old["value"]
        row["coding_status"] = "coded" if old["value"] is not None else "unresolved"
        row["timing_status"] = "qualified_pre_cutoff" if old["field_eligible"] else "unresolved"
        row["contrast_status"] = "requires_sample_support"
        rows.append(row)
    by_key = {(r["candidate_id"], r["trait"]): r for r in rows}

    def qualify(row, value, reason, facts=(), *, analysis=False, analysis_value=None):
        row.update(
            status="qualified",
            value=value,
            factual_qualified=True,
            eligibility_reason=reason,
            review_status="literal_and_identity_reviewed_v2",
        )
        row["source_recorded_value"].setdefault("reviewed_facts", []).extend(facts)
        row["evidence"].extend(facts)
        if analysis:
            row.update(
                analysis_eligible=True,
                analysis_value=value if analysis_value is None else analysis_value,
                coding_status="coded",
                timing_status="qualified_pre_cutoff",
            )

    for row, old in zip(rows, baseline):
        if row["party"] != "Democratic":
            continue
        if row["trait"] in {"race", "ethnicity"} and old["status"] == "dated_reported":
            qualify(
                row,
                {"explicit_positive_observations": old["source_recorded_value"]},
                "Explicit source-recorded positive identities qualify factually; definitions, "
                "multiple labels and report types are preserved. No negative/reference identity.",
            )
            row["contrast_status"] = "no_complete_reference_classification"
        if row["trait"] == "age" and old["status"] != "qualified":
            interval = old["uncertainty"]["age_years_interval"]
            if interval:
                qualify(
                    row,
                    {"age_years_interval": interval},
                    "Reviewed secondary birth-year report supports only these Election Day "
                    "age bounds. No exact birthday or primary continuous-age input inferred.",
                )
                row["coding_status"] = "interval_only"
        if row["trait"] == "religion" and old["status"] == "dated_reported":
            value = old["source_recorded_value"]
            text = json.dumps(value, ensure_ascii=False).lower()
            if "refused" in text or "don't know" in text or "don’t know" in text:
                row.update(
                    status="unknown",
                    eligibility_reason="Questionnaire nonresponse/refusal is retained, not an affiliation.",
                )
            elif value:
                qualify(
                    row,
                    {"historical_religious_description": value},
                    "Explicit dated historical description qualifies as a reported observation, "
                    "not verified current affiliation or a same-vintage analytical category.",
                )
    for candidate, collection, _, profile in selected:
        cid = candidate["candidate_id"]
        evidence = profile.get("evidence")
        kind = profile.get("source_kind", "official_candidate_supplied_voter_guide")
        date = evidence.get("publication_date") if isinstance(evidence, dict) else None
        for trait, fields in PROFILE_FIELDS.items():
            if trait not in {"education", "profession"}:
                continue
            literal = {f: profile["fields"][f] for f in fields if profile["fields"].get(f)}
            if not literal:
                continue
            row = by_key[(cid, trait)]
            facts = [
                {
                    "profile_sha256": digest(profile),
                    "source_kind": kind,
                    "literal": literal,
                    "supporting_excerpt": profile.get("support", literal),
                    "observation_date": date,
                    "receipt": evidence,
                    "qualification": profile.get("qualification", profile.get("review_status")),
                }
            ]
            # Degree conflicts and attendance are factual records, not completed attainment.
            if trait == "education":
                code = review["documented_attainment"].get(cid)
                reason = review["coding_holds"].get(
                    cid,
                    "Reviewed explicit completed credential; source-reported, not independently verified.",
                )
                text = json.dumps(literal, ensure_ascii=False)
                temporal = (
                    bool(date and date < v1.CUTOFF.isoformat())
                    or collection == "official_candidate_profiles"
                    or (
                        cid in review["pre_election_completed_attainment"]
                        and (cid != "221019" or "2003-2006" in text)
                    )
                )
                if cid == "220698":
                    row.update(
                        status="uncertain",
                        eligibility_reason=reason,
                        factual_qualified=False,
                        coding_status="conflicting_attainment",
                    )
                    row["source_recorded_value"].setdefault("reviewed_facts", []).extend(facts)
                    row["evidence"].extend(facts)
                    continue
                qualify(
                    row,
                    {"documented_completed_attainment": code, "education_observations": literal},
                    reason
                    + (
                        " Pre-election timing supported."
                        if temporal
                        else " Publication/credential date unresolved; descriptive only."
                    ),
                    facts,
                    analysis=bool(code and temporal),
                    analysis_value=code,
                )
                if not code:
                    row["coding_status"] = "completed_attainment_unresolved"
            elif trait == "profession":
                text = "; ".join(
                    "; ".join(v) if isinstance(v, list) else v for v in literal.values()
                )
                families = [
                    family
                    for family, pattern in v1.OCCUPATIONS.items()
                    if re.search(pattern, text, re.I)
                ]
                temporal = bool(date and date < v1.CUTOFF.isoformat()) or (
                    collection == "official_candidate_profiles"
                )
                qualify(
                    row,
                    {
                        "reported_history": literal,
                        "occupational_families": families,
                        "paid_employment": "not_established_universally",
                    },
                    "Reviewed literal professional history; appointed/elected posts and unpaid "
                    "roles remain distinct. "
                    + (
                        "Dated pre-election source."
                        if temporal
                        else "Election-day timing unresolved; no analytical promotion."
                    ),
                    facts,
                    analysis=temporal and len(families) == 1,
                    analysis_value=families[0] if len(families) == 1 else None,
                )
            else:
                qualify(
                    row,
                    {"reported_positive_history": literal},
                    "Explicit positive history only; absence is not a negative reference.",
                    facts,
                )
                row["contrast_status"] = "no_reviewed_negative_reference"
        for trait, decisions in review["positive_claim_fragments"].items():
            if cid in decisions:
                text = " ".join(
                    "; ".join(value) if isinstance(value, list) else value
                    for value in profile["fields"].values()
                )
                fragments = [f for f in decisions[cid] if f.casefold() in text.casefold()]
                if fragments:
                    qualify(
                        by_key[(cid, trait)],
                        {"reviewed_positive_history": True},
                        "Literal reviewed positive "
                        + trait.replace("_", " ")
                        + " history; a positive-only inventory does not establish a contrast.",
                        [
                            {
                                "profile_sha256": digest(profile),
                                "literal": fragments,
                                "receipt": evidence,
                            }
                        ],
                    )
                    by_key[(cid, trait)]["contrast_status"] = "no_reviewed_negative_reference"
    people = {p["id"]["bioguide"]: p for p in inputs["people"]}
    voting = {
        r["bioguide_id"]: r for r in inputs["current_voting_records"] if r["chamber"] == "house"
    }
    by_candidate = {c["candidate_id"]: c for c in candidates}
    panel = copy.deepcopy(panel)
    for cid, bioguide in review["incumbency_resolutions"].items():
        c, person = by_candidate[cid], people[bioguide]
        if c["legislative"].get("bioguide_id") != bioguide:
            raise ValueError("Service override lacks exact person bridge")
        terms = [
            term
            for term in person["terms"]
            if term["type"] == "rep"
            and term["state"] == c["state"]
            and int(term["district"]) == int(c["district"])
            and term["start"] <= v1.CUTOFF.isoformat() < term["end"]
        ]
        if len(terms) != 1:
            raise ValueError("Service override lacks unique active same-district House term")
        outcome = next(r for r in panel if r["contest_id"] == c["contest_id"])
        if outcome["D_candidate_election_id"] and outcome["D_name"] != c["name"]:
            raise ValueError("Service override selected a different candidate")
        outcome.update(D_incumbent=True, service_verified_incumbent=True)
        evidence = [
            {
                "person": person["evidence"],
                "active_term": terms[0],
                "exact_candidate_crosswalk": c["legislative"]["evidence"],
            }
        ]
        qualify(
            by_key[(cid, "incumbency")],
            True,
            "Exact dated FEC/person/service bridge.",
            evidence,
            analysis=True,
        )
        qualify(
            by_key[(cid, "house_service")],
            v1.service_years(person["terms"]),
            "Union of exact pre-cutoff House intervals; v2-only service resolution.",
            evidence,
            analysis=True,
        )
        for trait, record, field in (
            ("voting_ideology", c["legislative"].get("prior_voting_record"), "nokken_poole_dim1"),
            ("party_unity", voting.get(bioguide), "unity_score"),
        ):
            if record and record.get(field) not in (None, ""):
                qualify(
                    by_key[(cid, trait)],
                    float(record[field]),
                    "Held, qualified pre-election legislative record after exact service bridge.",
                    [record],
                    analysis=True,
                )
        for row in rows:
            if row["candidate_id"] == cid:
                row["D_incumbency_control"] = True
    for row in rows:
        row["field_eligible"] = row["analysis_eligible"]
    return rows, candidates, panel, baseline


def analytical_rows(rows, *, bands=False):
    result = copy.deepcopy(rows)
    for row in result:
        row["value"] = row["analysis_value"]
        row["field_eligible"] = row["analysis_eligible"]
        if bands and row["trait"] == "age":
            row["value"] = age_band(row["uncertainty"]["age_years_interval"])
            row["field_eligible"] = row["factual_qualified"] and row["value"] is not None
    return result


def coverage(rows):
    result = v1.coverage(rows)
    for record in result:
        subset = [
            r
            for r in rows
            if r["trait"] == record["trait"]
            and (
                record["cohort"] == "all_named"
                or record["cohort"] == "democrats"
                and r["party"] == "Democratic"
                or record["cohort"] == "eligible_democrats"
                and r["performance_eligible"]
            )
        ]
        record["factual_qualified"] = sum(r["factual_qualified"] for r in subset)
        record["analysis_eligible"] = sum(r["analysis_eligible"] for r in subset)
    return result


def expanded_rows(rows, baseline):
    result = copy.deepcopy(rows)
    for row in result:
        old = baseline[row["baseline_trait_row"] - 1]
        row["source_recorded_value"] = {
            "existing": old["source_recorded_value"],
            "additional": row["source_recorded_value"].get("reviewed_facts", []),
        }
        row["evidence"] = [*old["evidence"], *row["evidence"]]
        row["eligibility_reason"] += (
            " Analytical field eligible."
            if row["analysis_eligible"]
            else " Not an eligible primary analytical field."
        )
    return result


def build(root):
    root = Path(root)
    protected = verify_frozen(root)
    if not (root / SPEC).exists():
        raise ValueError("V2 pre-fit specification missing")
    rows, candidates, panel, baseline = reviewed_rows(root)
    output = root / OUT
    output.mkdir(parents=True, exist_ok=True)
    write_rows(output / "candidate-traits.jsonl.gz", rows)
    v1.write_csv(output / "candidate-traits.csv", rows)
    v1.write_csv(output / "coverage.csv", coverage(rows))
    write_rows(output / "panel-overlay.jsonl.gz", panel)
    write_json(output / "source-receipts.json", v1.source_catalog(root))
    results = v1.analyze(
        analytical_rows(rows),
        panel,
        predictor=paired,
        prediction_selector=common_support,
        strict_education=False,
    )
    names = ("fits", "terms", "predictions", "folds", "state-deletions", "selection", "sensitivity")
    full_diagnostics = []
    for fit in results[0]:
        if fit["status"] != "estimated":
            continue
        ids = set(fit["candidate_election_ids"])
        values = {
            r["contest_id"]: r["analysis_value"]
            for r in rows
            if r["trait"] == fit["trait"] and r["performance_eligible"]
        }
        cohort = [
            {**r, "_value": values[r["contest_id"]]}
            for r in panel
            if r["D_candidate_election_id"] in ids
        ]
        levels = sorted({r["_value"] for r in cohort}) if fit["reference"] is not None else None
        prediction, folds = paired(cohort, fit["trait"], levels)
        full_diagnostics.extend(folds)
        fit["full_population_prediction"] = {
            "population_candidates": len(cohort),
            "paired_candidates": len(prediction),
            "all_folds_complete": len(prediction) == len(cohort),
            "qualification": "No full-population interval asserted from restricted validation.",
        }
        if fit["trait"] in {"education", "profession"}:
            previous = {
                r["contest_id"]: r
                for r in baseline
                if r["trait"] == fit["trait"] and r["performance_eligible"] and r["field_eligible"]
            }
            strict = [
                {**r, "_value": previous[r["contest_id"]]["value"]}
                for r in cohort
                if r["contest_id"] in previous
            ]
            results[6].append(
                {
                    "trait": fit["trait"],
                    "sensitivity": "v1_qualified_values_only",
                    "qualification": "Exclude newly qualified analytical education/profession values; retain v2 service controls.",
                    **v1.fit(strict, fit["trait"], levels),
                }
            )
    write_rows(output / "full-population-folds.jsonl.gz", full_diagnostics)
    for name, result in zip(names, results):
        write_rows(output / f"{name}.jsonl.gz", result)
        if name != "folds":
            v1.write_csv(output / f"{name}.csv", result)
    band_dataset = analytical_rows(rows, bands=True)
    # Only age is eligible in this explicitly separate sensitivity pipeline.
    for row in band_dataset:
        if row["trait"] != "age":
            row["field_eligible"] = False
    bands = v1.analyze(
        band_dataset,
        panel,
        predictor=paired,
        prediction_selector=common_support,
        categorical_traits={"age"},
        strict_education=False,
    )
    write_json(output / "age-band-sensitivity.json", bands[0][0])
    write_rows(output / "age-band-predictions.jsonl.gz", bands[2])
    write_rows(output / "age-band-folds.jsonl.gz", bands[3])
    write_rows(output / "age-band-state-deletions.jsonl.gz", bands[4])
    selection_summary = []
    for trait in v1.TRAITS:
        for included in (True, False):
            subset = [r for r in results[5] if r["trait"] == trait and r["included"] == included]
            leans = [r["lean"] for r in subset if r["lean"] is not None]
            selection_summary.append(
                {
                    "trait": trait,
                    "included": included,
                    "candidates": len(subset),
                    "states": len({r["state"] for r in subset}),
                    "known_D_incumbents": sum(r["D_incumbent"] is True for r in subset),
                    "unknown_D_incumbency": sum(r["D_incumbent"] is None for r in subset),
                    "mean_presidential_D_share": float(np.mean(leans)) if leans else None,
                    "provisional_D_leads": sum(r["provisional_D_leads"] is True for r in subset),
                    "reasons": dict(Counter(r["reason"] for r in subset if r["reason"])),
                }
            )
    v1.write_csv(output / "selection-summary.csv", selection_summary)
    changes = []
    for row, old in zip(rows, baseline):
        if row["status"] != old["status"] or row["analysis_eligible"] != old["field_eligible"]:
            changes.append(
                {k: row[k] for k in ("candidate_id", "contest_id", "name", "party", "trait")}
                | {
                    "before_status": old["status"],
                    "after_status": row["status"],
                    "before_analysis_eligible": old["field_eligible"],
                    "after_analysis_eligible": row["analysis_eligible"],
                    "reason": row["eligibility_reason"],
                }
            )
    v1.write_csv(output / "qualification-changes.csv", changes)
    before = v1.coverage(baseline)
    after = coverage(rows)
    summary = {
        "version": VERSION,
        "candidate_records": len(candidates),
        "democrats": sum(c["party"] == "Democratic" for c in candidates),
        "eligible_democrats": sum(r["eligible"] for r in panel),
        "trait_fields": len(v1.TRAITS),
        "primary_family_size": len(v1.TRAITS),
        "protected_frozen_files": protected,
        "age_band_sensitivity": bands[0][0],
        "newly_acquired_observations": 0,
        "newly_covered_people": 0,
        "newly_qualified_existing_fields": sum(
            r["before_status"] != "qualified" and r["after_status"] == "qualified" for r in changes
        ),
        "newly_analysis_eligible_fields": sum(
            not r["before_analysis_eligible"] and r["after_analysis_eligible"] for r in changes
        ),
        "supported_blocks": [r["trait"] for r in results[0] if r["status"] == "estimated"],
        "unavailable_blocks": [r["trait"] for r in results[0] if r["status"] != "estimated"],
        "holm_below_005": [r["trait"] for r in results[0] if r["holm_pvalue"] < 0.05],
        "coverage": after,
        "before_coverage": before,
        "evidence_storage": "baseline_trait_row is a 1-based row reference into immutable "
        "results/house-characteristics-v1/candidate-traits.jsonl.gz; both are in complete downloads.",
    }
    write_json(output / "summary.json", summary)
    from .characteristics_publication import build as publish
    from .characteristics_v2_publication import report

    publish(root, version=VERSION, reporter=report, rows_override=expanded_rows(rows, baseline))
    inputs = (
        SPEC,
        REVIEW,
        SEAL,
        PROTECTION,
        f"{v1.OUT}/candidate-traits.jsonl.gz",
        "results/house/candidates.jsonl.gz",
        "results/house/source-inputs.jsonl.gz",
        "results/house-study/candidate-comparisons.jsonl.gz",
    )
    write_json(
        output / "manifest.json",
        {
            "version": VERSION,
            "inputs": {name: fingerprint(root / name) for name in inputs},
            "files": {
                p.name: fingerprint(p)
                for p in sorted(output.iterdir())
                if p.is_file() and p.name != "manifest.json"
            },
        },
    )
    verify_frozen(root)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--seal-review", action="store_true")
    args = parser.parse_args()
    if args.seal_review:
        seal_review(args.root)
    else:
        print(json.dumps(build(args.root), indent=2))
