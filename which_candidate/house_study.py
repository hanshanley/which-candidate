"""A coherent House study: qualified comparisons, held-out diagnostics and profiles."""

import argparse
import copy
import csv
import json
from collections import Counter
from pathlib import Path

import numpy as np

from .candidate_discovery import attach_repair
from .candidate_research import BACKGROUND_FIELDS, attach_dispositions, background_field_coverage
from .democratic_traits import democratic_trait_rows, write_trait_outputs
from .house_validation import (
    person_key,
    predictive_comparisons,
    selection_diagnostics,
)
from .models import PRIMARY, available, matrix
from .participation_context import attach as attach_participation_context
from .pipeline import csv_bytes
from .rebuild import ROOT, checked_fit
from .storage import fingerprint, read_rows, write_json, write_rows

LABELS = {
    "incumbency": "Democratic incumbent versus nonincumbent",
    "ideology": "Prior voting ideology: +0.1 conservative",
    "defection": "Party defection: +1 percentage point",
    "age": "Age: +10 years",
    "tenure": "House service: +10 years",
    "gender": "Source-recorded female versus male",
}


def trait_comparisons(panel):
    results = []
    for model in PRIMARY:
        sample = [r for r in panel if available(r, model)]
        common = [r for r in sample if r.get("previous_presidential_share") is not None]
        variants = {
            "primary": sample,
            "competitive_40_60": [
                r for r in sample if 40 <= r["presidential_D_two_party_share_pct"] <= 60
            ],
            "common_sample_2024": common,
            "common_sample_2020": [
                {
                    **r,
                    "presidential_D_two_party_share_pct": r["previous_presidential_share"],
                    "descriptive_gap_share_pp": (
                        r["D_two_party_share_pct"] - r["previous_presidential_share"]
                    ),
                }
                for r in common
            ],
        }
        for variant, rows in variants.items():
            design, terms = matrix(rows, model, [2026])
            focal = PRIMARY[model][0]
            if model == "defection":
                design[:, terms.index(focal)] *= 5
                terms[terms.index(focal)] = focal = "defection_1pp"
            fit = checked_fit(rows, design, terms, focal)
            if not fit["full_rank_state_deletions"]:
                fit["pvalue"] = None
            results.append(
                {
                    "model": model,
                    "label": LABELS[model],
                    "variant": variant,
                    "year": 2026,
                    "chamber": "house",
                    "interpretation": "updated_exploratory_association; not_causal",
                    **fit,
                    "ci_low_margin_pp": 2 * fit["ci_low"]
                    if fit.get("ci_low") is not None
                    else None,
                    "ci_high_margin_pp": 2 * fit["ci_high"]
                    if fit.get("ci_high") is not None
                    else None,
                }
            )
    family = sorted(
        [
            r
            for r in results
            if r["variant"] == "primary"
            and r.get("pvalue") is not None
            and r.get("publication_status") == "supported_exploratory"
        ],
        key=lambda r: r["pvalue"],
    )
    previous = 0
    for rank, row in enumerate(family):
        previous = max(previous, min(1, (len(PRIMARY) - rank) * row["pvalue"]))
        row["holm_pvalue"] = previous
    return results


def held_out_diagnostics(panel):
    """Fit the electoral-environment benchmark without the held-out state or person."""
    rows = [r for r in panel if r["eligible"]]
    design, _ = matrix(rows, "baseline", [2026])
    target = np.array([r["descriptive_gap_share_pp"] for r in rows])
    predictions, folds = [], []
    for state in sorted({r["state"] for r in rows}):
        test = [i for i, r in enumerate(rows) if r["state"] == state]
        people = {person_key(rows[i]) for i in test}
        train = [
            i for i, r in enumerate(rows) if r["state"] != state and person_key(r) not in people
        ]
        identified = len(train) > design.shape[1] + 3 and (
            np.linalg.matrix_rank(design[train]) == design.shape[1]
        )
        fold_id = f"2026:house:held-out-state:{state}"
        folds.append(
            {
                "fold_id": fold_id,
                "held_out_state": state,
                "status": "estimated" if identified else "insufficient_training_support",
                "training_candidate_ids": [rows[i]["D_candidate_election_id"] for i in train],
                "test_candidate_ids": [rows[i]["D_candidate_election_id"] for i in test],
                "training_states": sorted({rows[i]["state"] for i in train}),
                "training_people": sorted({person_key(rows[i]) for i in train}),
                "test_people": sorted(people),
            }
        )
        if not identified:
            continue
        beta = np.linalg.lstsq(design[train], target[train], rcond=None)[0]
        for i in test:
            row = rows[i]
            expected = row["presidential_D_two_party_share_pct"] + float(design[i] @ beta)
            predictions.append(
                {
                    "candidate_election_id": row["D_candidate_election_id"],
                    "contest_id": row["contest_id"],
                    "name": row["D_name"],
                    "state": state,
                    "district": row["district"],
                    "fold_id": fold_id,
                    "observed_D_share_pct": row["D_two_party_share_pct"],
                    "presidential_D_share_pct": row["presidential_D_two_party_share_pct"],
                    "expected_D_share_pct": expected,
                    "presidential_gap_margin_pp": 2 * row["descriptive_gap_share_pp"],
                    "held_out_residual_margin_pp": 2 * (row["D_two_party_share_pct"] - expected),
                    "expected_share_in_bounds": 0 <= expected <= 100,
                    "interpretation": "retrospective_state_person_held_out; not_candidate_effect",
                }
            )
    predictions.sort(key=lambda r: r["candidate_election_id"])
    residuals = np.array([r["held_out_residual_margin_pp"] / 2 for r in predictions])
    baseline = np.array([r["presidential_gap_margin_pp"] / 2 for r in predictions])
    metrics = {
        "n": len(predictions),
        "state_folds": len(folds),
        "presidential_baseline_MAE_share_pp": float(np.mean(np.abs(baseline))),
        "held_out_MAE_share_pp": float(np.mean(np.abs(residuals))),
        "held_out_RMSE_share_pp": float(np.sqrt(np.mean(residuals**2))),
        "held_out_bias_share_pp": float(np.mean(residuals)),
        "expected_shares_outside_0_100": sum(
            not r["expected_share_in_bounds"] for r in predictions
        ),
        "interpretation": "Retrospective within-cycle diagnostics using other states' 2026 "
        "outcomes, not forward forecasts. Incumbency and traits are not absorbed in this "
        "benchmark. Residuals are not causal candidate effects or exact WAR.",
    }
    return predictions, folds, metrics


def csv_rows(path):
    with Path(path).open() as stream:
        return list(csv.DictReader(stream))


def acquired_evidence(candidates, observations, facts):
    identities = {(r["candidate_id"], r["contest_id"]): r for r in candidates}
    if len(identities) != len(candidates):
        raise ValueError("Duplicate candidate/contest identity")
    fact_index = {(r["candidate_id"], r["record_id"]): r for r in facts}
    output = {}
    for row in observations:
        key = (row["candidate_id"], row["contest_id"])
        candidate = identities.get(key)
        if candidate is None or any(
            str(candidate[field]) != str(row[field])
            for field in ("name", "state", "district", "party")
        ):
            raise ValueError(f"Unqualified candidate observation identity: {key}")
        value = json.loads(row["value"])
        evidence = json.loads(row["evidence"]) if row["evidence"] else None
        if isinstance(evidence, dict) and evidence.get("record_id"):
            fact = fact_index.get((row["candidate_id"], evidence["record_id"]))
            if fact:
                if fact["field"] != row["field"] or fact["state"] != row["state"]:
                    raise ValueError(f"Conflicting campaign evidence: {key}")
                evidence = {
                    **evidence,
                    **{
                        field: fact[field]
                        for field in (
                            "original_urls",
                            "wayback_urls",
                            "source_text_sha256",
                            "evidence_sha256",
                            "captured_before_election",
                        )
                        if field in fact
                    },
                }
        output.setdefault(key, []).append(
            {
                "field": row["field"],
                "value": value,
                "source_kind": row["source_kind"],
                "source_year": row["source_year"],
                "observation_date": row["observation_date"] or None,
                "evidence": evidence,
                "qualification": row["qualification"],
                "model_ready": row["model_ready"] == "True",
            }
        )
    return output


def attach_research_history(root, profiles):
    """Validate frozen research milestones separately from later normalized additions."""
    root = Path(root)
    if not (root / "data/house-characteristics-v3-acquisitions.json").exists():
        return attach_dispositions(root, profiles), attach_repair(root, profiles)
    inputs = read_rows(root / "results/house/source-inputs.jsonl.gz")[0]
    supplemental = {
        (o["candidate_id"], o["contest_id"], o["source_id"])
        for o in inputs["reviewed_characteristic_observations"]
        if o["source_id"].startswith(("v3-", "v4-", "v5-", "v6-"))
    }
    historical = copy.deepcopy(profiles)
    counts = {}
    for profile in historical:
        original = profile["acquired_background_observations"]
        profile["acquired_background_observations"] = [
            o
            for o in original
            if not isinstance(o.get("evidence"), dict)
            or (
                profile["candidate_id"],
                profile["contest_id"],
                o["evidence"].get("id"),
            )
            not in supplemental
        ]
        counts[profile["candidate_id"]] = len(original) - len(
            profile["acquired_background_observations"]
        )
    research = attach_dispositions(root, historical)
    repair = attach_repair(root, historical)
    for current, old in zip(profiles, historical):
        for key in (
            "background_research",
            "in_initial_research_queue",
            "background_discovery_repair",
        ):
            if key in old:
                current[key] = old[key]
        current.update(background_field_coverage(current["acquired_background_observations"]))
        if counts[current["candidate_id"]]:
            current["supplemental_v3_observation_count"] = counts[current["candidate_id"]]
            current["background_research"]["historical_disposition_qualification"] = (
                "Frozen earlier research milestone; later versioned observations remain in the "
                "current complete evidence table and do not rewrite historical receipts."
            )
    remaining = {
        field: sum(field in p["remaining_background_fields"] for p in profiles)
        for field in BACKGROUND_FIELDS
    }
    for summary in (research, repair):
        if summary:
            summary["historical_remaining_fields"] = summary["remaining_fields"]
            summary["remaining_fields"] = remaining
            summary["supplemental_v3_observations"] = sum(counts.values())
            summary["historical_milestone_not_new_acquisition"] = True
    return research, repair


def candidate_profiles(candidates, panel, seated, incoming, predictions, evidence=None):
    contests = {r["contest_id"]: r for r in panel}
    members = {r["bioguide_id"]: r for r in seated if r["bioguide_id"]}
    newcomers = {r["candidate_id"]: r for r in incoming if r["candidate_id"]}
    predictions = {r["contest_id"]: r for r in predictions}
    profiles = []
    for candidate in candidates:
        contest = contests[candidate["contest_id"]]
        selected = candidate["selected_democratic_analysis_candidate"] is True
        member = members.get(candidate["legislative"].get("bioguide_id"), {})
        arrival = newcomers.get(candidate["candidate_id"], {})
        background = member or arrival
        prediction = predictions.get(candidate["contest_id"], {}) if selected else {}
        profiles.append(
            {
                "candidate_id": candidate["candidate_id"],
                "candidate_election_id": contest.get("D_candidate_election_id")
                if selected
                else None,
                "contest_id": candidate["contest_id"],
                "name": candidate["name"],
                "state": candidate["state"],
                "district": candidate["district"],
                "party": candidate["party"],
                "votes": candidate["votes"],
                "provider_winner_flag": candidate["native_flags_unverified"]["winner"],
                "selected_democratic_analysis_candidate": selected,
                "comparison_eligible": bool(selected and contest["eligible"]),
                "comparison_holds": contest["exclusion_reasons"],
                "comparison_status": "qualified_D_comparison"
                if selected and contest["eligible"]
                else "held_D_comparison"
                if selected
                else "not_selected_D_nominee",
                "observed_D_share_pct": contest["D_two_party_share_pct"] if selected else None,
                "presidential_D_share_pct": contest["presidential_D_two_party_share_pct"],
                "presidential_gap_margin_pp": (
                    2 * contest["descriptive_gap_share_pp"]
                    if selected and contest["eligible"]
                    else None
                ),
                "held_out_residual_margin_pp": prediction.get("held_out_residual_margin_pp"),
                "bioguide_id": candidate["legislative"].get("bioguide_id"),
                "current_House_member": bool(member),
                "incoming_classification": arrival.get("entry_classification"),
                "date_of_birth": background.get("date_of_birth") or None,
                "education": background.get("education")
                or background.get("wikipedia_education")
                or background.get("candidate_profile_education")
                or None,
                "professional_history": background.get("professional_history")
                or background.get("reported_prior_background")
                or None,
                "religion_literal": background.get("religion_literal") or None,
                "religion_status": background.get("religion_status") or "not_qualified",
                "military_service": background.get("military_service") or None,
                "background_evidence": [
                    background.get(key)
                    for key in (
                        "biography_evidence",
                        "religion_evidence",
                        "reviewed_biography_evidence",
                        "wikipedia_roster_evidence",
                    )
                    if background.get(key)
                ],
                "campaign_websites": candidate["campaign_websites"],
                "machine_biography_fields_unreviewed": candidate["pre_election_biography_fields"],
                "acquired_background_observations": (evidence or {}).get(
                    (candidate["candidate_id"], candidate["contest_id"]), []
                ),
                "background_model_ready": False,
                "new_background_used_in_trait_models": False,
            }
        )
    return profiles


def render_report(summary, fits, donors, measurements):
    democratic_audit = summary.get("democratic_candidate_traits", {}).get("research_audit")
    primary = [r for r in fits if r["variant"] == "primary"]
    passing = summary["primary_tests_passing_Holm_005"]
    conclusion = (
        "None of the six primary characteristic comparisons clears the six-test Holm correction."
        if passing == 0
        else f"{passing} of the six primary comparisons clear the six-test Holm correction."
    )
    predictive = summary["predictive_value"]
    positive = sum(
        row["gain_ci_low_share_pp"] is not None and row["gain_ci_low_share_pp"] > 0
        for row in predictive
    )
    joint = next(row for row in predictive if row["model"] == "joint_records")
    joint_description = (
        f"The joint five-trait incumbent model changes held-out MAE from "
        f"{joint['baseline_MAE_share_pp']:.3f} to "
        f"{joint['augmented_MAE_share_pp']:.3f} share points among "
        f"{joint['paired_predictions']} paired candidates. That point comparison "
        "must be read with its interval and cohort restriction, not as a selected "
        "winning model."
        if joint["baseline_MAE_share_pp"] is not None
        else "The joint incumbent-record model lacks paired prediction support."
    )
    lines = [
        "# Which Democratic House candidates did better in 2026?",
        "",
        "## The answer",
        "",
        f"Across {summary['eligible_comparisons']} qualified House comparisons, the evidence "
        f"does not establish a universal winning candidate type. {conclusion} "
        "These estimates are not proof that candidate characteristics do not matter.",
        "",
        "A practical check compares predictions for held-out states. Comparisons "
        "with a pointwise uncertainty interval wholly above zero improvement: "
        f"**{positive}/{len(predictive)}**. A trait can have an in-sample association "
        "without providing reliable added predictive value for other candidates. "
        "The paired results below quantify that distinction rather than selecting "
        "a favorite candidate formula.",
        "",
        "Historical donor ideology and prior voting ideology point in opposite directions "
        "even among the same candidates. A single moderate-versus-progressive label would "
        "hide that difference. These are observational associations, not the effect of "
        "replacing one nominee with another.",
        "",
        "## The main comparisons",
        "",
        "Outcome: congressional minus 2024 presidential Democratic two-party share, "
        "reported here in D-minus-R margin points (twice the share-point difference). "
        "All models adjust for district lean and lean squared. Incumbency also adjusts "
        "for Republican incumbency; the other five comparisons are among verified "
        "Democratic incumbents only.",
        "",
        "| Comparison | Adjusted margin pp [95% pointwise interval] | Candidates | States | Holm p |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in primary:
        value = row.get("estimate_margin_pp")
        low, high = row.get("ci_low_margin_pp"), row.get("ci_high_margin_pp")
        estimate = (
            f"{value:+.2f} [{low:+.2f}, {high:+.2f}]"
            if low is not None and row.get("publication_status") == "supported_exploratory"
            else "Diagnostic only / unavailable"
        )
        pvalue = row.get("holm_pvalue")
        lines.append(
            f"| {row['label']} | {estimate} | {row['n']} | {row['state_clusters']} | "
            + (f"{pvalue:.3f}" if pvalue is not None else "Unavailable")
            + " |"
        )
    metrics = summary["held_out_diagnostics"]
    lines.extend(
        [
            "",
            "Intervals use the larger of state-cluster CR1 and delete-one-state CV3 "
            "standard errors, with t(G-1) critical values. They are pointwise, not "
            "simultaneous intervals. Full-rank state deletions and sample/leverage "
            "support gates apply. Competitive-seat and identical-sample 2020/2024 "
            "benchmark sensitivities are in `trait-fits.csv`.",
            "",
            "## Why raw presidential gaps are not a candidate ranking",
            "",
            "A midterm national environment can lift or depress many candidates at once. "
            "The raw gap also depends on the presidential candidate, constituency map "
            "and election-year differences. The separate held-out benchmark learns "
            "the 2026 gap-versus-lean curve from other states, excluding the held-out "
            "candidate's person identity as well. It intentionally does not adjust away "
            "incumbency or the traits under study.",
            "",
            f"The diagnostic covers **{metrics['n']} candidates in "
            f"{metrics['state_folds']} state-held-out folds**. Presidential-baseline "
            f"mean absolute error is {metrics['presidential_baseline_MAE_share_pp']:.2f} "
            f"share points; the held-out benchmark's is "
            f"{metrics['held_out_MAE_share_pp']:.2f}, with signed bias "
            f"{metrics['held_out_bias_share_pp']:+.2f}. These are retrospective "
            "within-cycle errors, not a forward election forecast. Individual residuals "
            "are descriptive diagnostics, not causal candidate effects or Split Ticket WAR. "
            f"{metrics['expected_shares_outside_0_100']} unconstrained expected shares "
            "fall outside 0-100%; these are explicitly flagged, not silently clipped.",
            "",
            "## Ideology depends on what is measured",
            "",
        ]
    )
    for row in donors:
        if row["chamber"] == "house" and row["variant"] in (
            "all_qualified",
            "current_benchmark_common_sample",
            "previous_benchmark_common_sample",
        ):
            lines.append(
                f"- Historical donor score, {row['variant'].replace('_', ' ')}: "
                f"{row['estimate_margin_pp']:+.2f} margin points per +0.5 conservative "
                f"score units [95% interval {2 * row['ci_low']:+.2f}, "
                f"{2 * row['ci_high']:+.2f}] (n={row['n']})."
            )
    lines.extend(
        [
            "",
            "The same-incumbent measurement check holds the people and controls fixed:",
            "",
            "| Measure and model | Adjusted margin pp [95% pointwise interval] | Candidates |",
            "| --- | ---: | ---: |",
        ]
    )
    for row in measurements:
        if row["chamber"] != "house":
            continue
        donor = "donor" in row["variant"]
        label = "Donor score, +0.5 conservative" if donor else "Prior voting, +0.1 conservative"
        adjustment = "joint" if row["variant"].startswith("joint_") else "separate"
        lines.append(
            f"| {label}, {adjustment} model | {row['estimate_margin_pp']:+.2f} "
            f"[{2 * row['ci_low']:+.2f}, {2 * row['ci_high']:+.2f}] | {row['n']} |"
        )
    lines.extend(
        [
            "",
            "Donor scores describe historical funding coalitions through 2024, not "
            "2026 platforms. Prior voting ideology comes from the 118th Congress "
            "(2023-2024). Party defection uses dated 119th-Congress votes before "
            "November 3, 2026; absence or abstention is not an opposing vote. "
            "Newcomers do not receive zero federal ideology.",
            "",
            "## Do candidate traits improve held-out predictions?",
            "",
            "An association is not evidence that a trait improves predictions for "
            "other candidates. Each comparison below fits a baseline and an augmented "
            "model on exactly the same people, holds out an entire state and purges "
            "the held-out people's identities from training. Positive gain means "
            "lower mean absolute error after adding the trait, in **vote-share** "
            "points, not margin points. These are retrospective 2026 diagnostics.",
            "",
            "| Added information | Paired candidates | Baseline MAE | With traits MAE | MAE gain [95% pointwise interval] |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in summary["predictive_value"]:
        gain = row["MAE_gain_share_pp"]
        low, high = row["gain_ci_low_share_pp"], row["gain_ci_high_share_pp"]
        value = (
            f"{gain:+.3f} [{low:+.3f}, {high:+.3f}]"
            if low is not None
            else f"{gain:+.3f}; interval unsupported"
            if gain is not None
            else "Unavailable"
        )
        baseline = row["baseline_MAE_share_pp"]
        augmented = row["augmented_MAE_share_pp"]
        lines.append(
            f"| {row['label']} | {row['paired_predictions']}/{row['qualified_candidates']} "
            f"| {baseline:.3f} | {augmented:.3f} | {value} |"
            if baseline is not None
            else f"| {row['label']} | 0/{row['qualified_candidates']} | Unavailable | "
            "Unavailable | Unavailable |"
        )
    lines.extend(
        [
            "",
            "Baselines adjust for lean and lean squared; both donor models also "
            "include known Democratic and Republican incumbency. The five individual "
            "record traits and their joint block apply only to verified Democratic "
            "incumbents. Different rows use different complete-case cohorts and "
            "must not be ranked as if they were the same population. The joint row "
            "uses all five record traits together; it is not a selected winning model.",
            "",
            "Intervals refit **the entire paired cross-validation pipeline after "
            "deleting each state**, including both models and every remaining fold. "
            "They use the state-jackknife standard error and t(G-1) critical value. "
            "Incomplete folds/deletions suppress intervals. These intervals are "
            "exploratory and pointwise, not multiple-testing-adjusted discoveries. "
            "Neither positive gains nor retrospective calibration establish forward "
            "forecast skill or causal candidate quality. Exact predictions, fold "
            "membership and deletion diagnostics are downloadable.",
            "",
            joint_description,
            "",
            "## How selective are these comparisons?",
            "",
            "| Information | Included out of all qualified comparisons | Coverage |",
            "| --- | ---: | ---: |",
        ]
    )
    labels = {r["model"]: r["label"] for r in summary["predictive_value"]}
    for row in summary["trait_selection"]:
        if row["partition"] == "all":
            lines.append(
                f"| {labels[row['model']]} | {row['included']}/{row['qualified_comparisons']} "
                f"| {row['included_pct']:.1f}% |"
            )
    lines.extend(
        [
            "",
            "This is feature availability **and the model's population restriction**, "
            "not a claim that every excluded candidate lacks a biography. The complete "
            "`trait-selection.csv` splits included/excluded candidates by recorded "
            "incumbency, presidential lean and native provisional winner flag, and "
            "reports their mean lean and raw gap. Not flagged as a winner does not "
            "establish a loss. Selection can change the answer: incumbent-only "
            "voting associations cannot establish the best type of challenger.",
            "",
            "## Who is in the project?",
            "",
            f"- All **{summary['named_candidates']} named candidates** in all 435 House "
            "districts are retained, including Republicans, other parties and losers.",
            f"- **{summary['held_comparisons']} contests** remain held from the main "
            "two-party comparison. Every hold is downloadable.",
            "- The sitting roster is a different population: 435 voting seats, 433 "
            "named occupants and two vacancies in the November 3 Clerk snapshot "
            "retrieved November 13; six nonvoting seats are separate.",
            "- The incoming roster is provisional, not certified. Continuing and "
            "returning members are separated from other reported winners.",
            "",
            "The interactive report includes the candidate profile browser. Education, "
            "career, military and religion evidence is descriptive, with unknowns "
            "preserved. New biographies and unreviewed campaign extractions do not "
            "silently enter these models. Religion responses are dated observations, "
            "not verified current beliefs. Source files, coverage and gap ledgers are "
            "part of the complete download.",
            f"The election browser now exposes **{summary['acquired_background_observations']:,} "
            f"acquired observations for {summary['candidates_with_acquired_observations']} "
            "candidates**, including losing candidates, rather than only listing "
            "unreviewed field names. Every observation retains its actual value, "
            "source kind/year, date, qualification and receipt. Unreviewed extractions "
            "are labeled, not presented as verified facts. Individual evidence "
            "tables and filtered profiles can both be downloaded.",
            "",
            "The frozen missing-person research queue and its candidate-specific "
            "outcomes are downloadable in `research-dispositions.csv`. The browser "
            "shows each outcome and the fields still absent from the acquired "
            "evidence. `background-field-coverage.csv` covers all named candidates. "
            "An accepted field is not a complete biography; missing service or "
            "office is not a negative label. Search hits, empty questionnaires, "
            "failed requests and downloaded-but-unaccepted pages do not count as facts.",
            (
                "The targeted Democratic background pass covers all 449 records in the "
                "standardized trait download. It fills "
                f"{democratic_audit['newly_filled_fields']['education']} education and "
                f"{democratic_audit['newly_filled_fields']['professional_history']} "
                "professional-history gaps, not newly covered people. "
                f"{democratic_audit['remaining_missing_field_counts']['education']} "
                "education gaps remain: Kristi Burke and Melissa McDonough. Attendance, "
                "degree completion, paid versus unpaid roles and conflicting source claims "
                "remain explicit. These retrospective fields do not change the frozen analyses."
                if democratic_audit
                else ""
            ),
            (
                "The discovery correction retracts the adequacy of the earlier "
                "first-name-only searches. The separate 701-person repair queue "
                "includes already-covered people missing education or employment. "
                f"Since its baseline, {summary['candidate_discovery_repair']['newly_covered_people']} "
                "people gained observations and "
                f"{sum(summary['candidate_discovery_repair']['newly_filled_fields'].values())} "
                "candidate-by-field gaps were filled. "
                f"{summary['candidate_discovery_repair']['remaining_uncovered_people']} "
                "people still lack observations; "
                f"{summary['candidate_discovery_repair']['inadequate_discovery_still_requiring_retry']} "
                "still require adequate discovery. Individual correction outcomes "
                "are in `discovery-repair-dispositions.csv`. Documented attempts "
                "do not establish exhaustive research or complete biographies."
                if summary.get("candidate_discovery_repair")
                else ""
            ),
            "",
            (
                "The voter-participation supplement adds "
                f"**{summary['participation_source_intake']['aggregate_observations']:,} "
                "source-defined aggregate observations** and "
                f"{summary['participation_source_intake']['house_result_observations']} "
                "House source-category/snapshot records across "
                f"{summary['participation_source_intake']['house_districts']} districts. "
                "Statewide counts, regional early/mail rows and aggregate demographic "
                "cells retain their different source dates, definitions and receipts. "
                "Hawaii and Wyoming confirm pinned candidate counts; Maine's later "
                "RCV counts remain separate from the frozen provider snapshot. "
                "Unreported final categories remain unknown. These are not candidate "
                "backgrounds, district turnout, unique people or voter transfers. "
                "The local browser and `results/participation/` expose the context; "
                "no frozen outcome, analysis sample, trait input or biography-gap "
                "count changes."
                if summary.get("participation_source_intake")
                else ""
            ),
            "",
            "## What remains unresolved",
            "",
            "Counts are the pinned November 12-13 provisional provider snapshot, not "
            "certified outcomes. Most challenger/loser traits are less well documented "
            "than incumbents' traits. Education/career evidence cannot establish the "
            "association of those characteristics for all nominees while unreviewed "
            "fields remain ineligible. Race/ethnicity coverage does not provide a "
            "valid complete negative-reference group. District religious composition "
            "is unavailable. None of these absences means that a trait has no effect.",
            "",
            "## Reproduce",
            "",
            "Run `python -m which_candidate.house_project` from the installed project "
            "or extracted complete-query download. This rebuilds normalized analysis, "
            "candidate/member tables, this study, the current publication and complete "
            "downloads without acquiring new sources. Run `pytest -q`, `ruff check .` "
            "and `ruff format --check .` for validation. The website remains withdrawn.",
            "",
        ]
    )
    return "\n".join(lines)


def build(root=ROOT, output=None):
    root = Path(root)
    output = Path(output) if output else root / "results/house-study"
    for directory in ("results/2026-v4", "results/house", "results/members"):
        manifest = json.loads((root / directory / "manifest.json").read_text())
        for name, receipt in manifest["files"].items():
            if fingerprint(root / directory / name) != receipt:
                raise ValueError(f"Changed study input: {directory}/{name}")
    panel = [
        r
        for r in read_rows(root / "results/2026-v4/candidate-queries.jsonl.gz")
        if r["chamber"] == "house"
    ]
    if len(panel) != 435 or len({r["contest_id"] for r in panel}) != 435:
        raise ValueError("The study requires all 435 unique House contests")
    candidates = read_rows(root / "results/house/candidates.jsonl.gz")
    evidence = acquired_evidence(
        candidates,
        csv_rows(root / "results/house/background-observations.csv"),
        read_rows(root / "results/house/biography-facts.jsonl.gz"),
    )
    fits = trait_comparisons(panel)
    predictions, folds, metrics = held_out_diagnostics(panel)
    profiles = candidate_profiles(
        candidates,
        panel,
        csv_rows(root / "results/members/house-119-seats.csv"),
        csv_rows(root / "results/members/house-120-seats.csv"),
        predictions,
        evidence,
    )
    research, repair = attach_research_history(root, profiles)
    participation = attach_participation_context(root, profiles)
    research_path = root / "data/democratic-background-research.json"
    targeted = (
        {row["candidate_id"]: row for row in json.loads(research_path.read_text())["candidates"]}
        if research_path.exists()
        else {}
    )
    for profile in profiles:
        profile["democratic_background_research"] = targeted.get(profile["candidate_id"])
    traits = democratic_trait_rows(profiles)
    trait_index = {(row["candidate_id"], row["contest_id"]): row for row in traits}
    for profile in profiles:
        profile["standardized_democratic_traits"] = trait_index.get(
            (profile["candidate_id"], profile["contest_id"])
        )
    output.mkdir(parents=True, exist_ok=True)
    trait_provenance = write_trait_outputs(
        output,
        traits,
        csv_bytes,
        {
            name: root / name
            for name in (
                "results/house/manifest.json",
                "results/house/source-inputs.jsonl.gz",
                "data/democratic-background-gap-baseline.json",
                "data/democratic-background-research.json",
            )
            if (root / name).exists()
        },
    )
    predictive, paired_predictions, paired_folds, deletions = predictive_comparisons(panel)
    selection = selection_diagnostics(
        panel,
        {
            r["contest_id"]: r["native_flags_unverified"]["winner"]
            for r in candidates
            if r["selected_democratic_analysis_candidate"] is True
        },
    )
    summary = {
        "year": 2026,
        "chamber": "house",
        "contests": len(panel),
        "eligible_comparisons": sum(r["eligible"] for r in panel),
        "held_comparisons": sum(not r["eligible"] for r in panel),
        "named_candidates": len(profiles),
        "parties": dict(Counter(r["party"] for r in profiles)),
        "hold_reasons": dict(
            Counter(reason for r in panel if not r["eligible"] for reason in r["exclusion_reasons"])
        ),
        "primary_tests": len(PRIMARY),
        "primary_tests_passing_Holm_005": sum(
            r["variant"] == "primary"
            and r.get("holm_pvalue") is not None
            and r["holm_pvalue"] < 0.05
            for r in fits
        ),
        "held_out_diagnostics": metrics,
        "predictive_value": predictive,
        "trait_selection": selection,
        "acquired_background_observations": sum(len(rows) for rows in evidence.values()),
        "candidates_with_acquired_observations": len(evidence),
        "candidate_background_research": research,
        "candidate_discovery_repair": repair,
        "participation_source_intake": participation,
        "democratic_candidate_traits": trait_provenance,
        "new_background_fields_used_in_models": False,
        "frozen_analysis_outputs_changed": False,
        "website_publication": "withdrawn",
    }
    write_rows(output / "trait-fits.jsonl.gz", fits)
    write_rows(output / "validation-folds.jsonl.gz", folds)
    write_rows(output / "candidate-profiles.jsonl.gz", profiles)
    write_rows(output / "candidate-comparisons.jsonl.gz", panel)
    write_rows(output / "trait-validation-folds.jsonl.gz", paired_folds)
    write_rows(output / "trait-validation-predictions.jsonl.gz", paired_predictions)
    write_rows(output / "trait-validation-deletions.jsonl.gz", deletions)
    for name, rows in (
        ("trait-fits.csv", fits),
        ("held-out-performance.csv", predictions),
        ("candidate-profiles.csv", profiles),
        ("trait-predictive-value.csv", predictive),
        ("trait-validation-predictions.csv", paired_predictions),
        ("trait-selection.csv", selection),
        (
            "discovery-repair-dispositions.csv",
            [
                {
                    **{
                        key: row[key]
                        for key in (
                            "candidate_id",
                            "contest_id",
                            "name",
                            "state",
                            "district",
                            "party",
                        )
                    },
                    **row["background_discovery_repair"],
                    "remaining_background_fields": row["remaining_background_fields"],
                }
                for row in profiles
                if row.get("background_discovery_repair")
            ],
        ),
        (
            "research-dispositions.csv",
            [
                {
                    **{
                        key: row[key]
                        for key in (
                            "candidate_id",
                            "contest_id",
                            "name",
                            "state",
                            "district",
                            "party",
                        )
                    },
                    **row["background_research"],
                    "background_fields_with_observations": row[
                        "background_fields_with_observations"
                    ],
                    "remaining_background_fields": row["remaining_background_fields"],
                }
                for row in profiles
                if row.get("in_initial_research_queue")
            ],
        ),
        (
            "background-field-coverage.csv",
            [
                {
                    **{
                        key: row[key]
                        for key in (
                            "candidate_id",
                            "contest_id",
                            "name",
                            "state",
                            "district",
                            "party",
                        )
                    },
                    "observation_count": len(row["acquired_background_observations"]),
                    "background_fields_with_observations": row.get(
                        "background_fields_with_observations", []
                    ),
                    "remaining_background_fields": row.get("remaining_background_fields", []),
                }
                for row in profiles
            ],
        ),
    ):
        (output / name).write_bytes(csv_bytes(rows))
    write_json(output / "summary.json", summary)
    donors = read_rows(root / "results/2026-v4/donor-fits.jsonl.gz")
    measurements = read_rows(root / "results/2026-v4/measurement-fits.jsonl.gz")
    (output / "report.md").write_text(render_report(summary, fits, donors, measurements))
    write_json(
        output / "manifest.json",
        {
            "schema": "which_candidate.house_study.v1",
            "inputs": {
                **{
                    name: fingerprint(root / name)
                    for name in (
                        "data/candidate-discovery-repair.json",
                        "data/candidate-discovery-baseline.json",
                        "data/participation-source-inputs.json",
                        "data/democratic-background-research.json",
                    )
                    if (root / name).exists()
                },
                **(
                    {
                        "results/participation/manifest.json": fingerprint(
                            root / "results/participation/manifest.json"
                        )
                    }
                    if participation
                    else {}
                ),
                **{
                    f"{directory}/manifest.json": fingerprint(root / directory / "manifest.json")
                    for directory in ("results/2026-v4", "results/house", "results/members")
                },
            },
            "files": {
                p.name: fingerprint(p)
                for p in sorted(output.iterdir())
                if p.is_file() and p.name != "manifest.json"
            },
        },
    )
    return summary


def _verify_protected(root, baseline):
    for name, sha256 in baseline["protected_analysis_sha256"].items():
        path = root / name
        if not path.exists() or fingerprint(path)["sha256"] != sha256:
            raise ValueError(f"Frozen analysis changed: {name}")
    for name, sha256 in baseline.get("additional_local_snapshot_sha256", {}).items():
        path = root / name
        if path.exists() and fingerprint(path)["sha256"] != sha256:
            raise ValueError(f"Frozen local snapshot changed: {name}")


def refresh_evidence(root=ROOT, output=None):
    """Refresh descriptive evidence outputs while reusing every fitted analysis artifact."""
    root = Path(root)
    output = Path(output) if output else root / "results/house-study"
    baseline_path = root / "data/democratic-background-gap-baseline.json"
    baseline = json.loads(baseline_path.read_text())
    _verify_protected(root, baseline)
    house_manifest = json.loads((root / "results/house/manifest.json").read_text())
    for name, receipt in house_manifest["files"].items():
        if fingerprint(root / "results/house" / name) != receipt:
            raise ValueError(f"Changed evidence input: results/house/{name}")
    panel = read_rows(output / "candidate-comparisons.jsonl.gz")
    candidates = read_rows(root / "results/house/candidates.jsonl.gz")
    previous_profiles = read_rows(output / "candidate-profiles.jsonl.gz")
    previous = {
        row["contest_id"]: {
            "contest_id": row["contest_id"],
            "held_out_residual_margin_pp": row["held_out_residual_margin_pp"],
        }
        for row in previous_profiles
        if row["selected_democratic_analysis_candidate"]
    }
    evidence = acquired_evidence(
        candidates,
        csv_rows(root / "results/house/background-observations.csv"),
        read_rows(root / "results/house/biography-facts.jsonl.gz"),
    )
    profiles = candidate_profiles(
        candidates,
        panel,
        csv_rows(root / "results/members/house-119-seats.csv"),
        csv_rows(root / "results/members/house-120-seats.csv"),
        list(previous.values()),
        evidence,
    )
    research, repair = attach_research_history(root, profiles)
    participation = attach_participation_context(root, profiles)
    research_path = root / "data/democratic-background-research.json"
    targeted = (
        {row["candidate_id"]: row for row in json.loads(research_path.read_text())["candidates"]}
        if research_path.exists()
        else {}
    )
    for profile in profiles:
        profile["democratic_background_research"] = targeted.get(profile["candidate_id"])
    traits = democratic_trait_rows(profiles)
    trait_index = {(row["candidate_id"], row["contest_id"]): row for row in traits}
    for profile in profiles:
        profile["standardized_democratic_traits"] = trait_index.get(
            (profile["candidate_id"], profile["contest_id"])
        )
    write_rows(output / "candidate-profiles.jsonl.gz", profiles)
    (output / "candidate-profiles.csv").write_bytes(csv_bytes(profiles))
    for name, rows in (
        (
            "research-dispositions.csv",
            [
                {
                    **{
                        key: row[key]
                        for key in (
                            "candidate_id",
                            "contest_id",
                            "name",
                            "state",
                            "district",
                            "party",
                        )
                    },
                    **row["background_research"],
                    "background_fields_with_observations": row[
                        "background_fields_with_observations"
                    ],
                    "remaining_background_fields": row["remaining_background_fields"],
                }
                for row in profiles
                if row.get("in_initial_research_queue")
            ],
        ),
        (
            "discovery-repair-dispositions.csv",
            [
                {
                    **{
                        key: row[key]
                        for key in (
                            "candidate_id",
                            "contest_id",
                            "name",
                            "state",
                            "district",
                            "party",
                        )
                    },
                    **row["background_discovery_repair"],
                    "remaining_background_fields": row["remaining_background_fields"],
                }
                for row in profiles
                if row.get("background_discovery_repair")
            ],
        ),
        (
            "background-field-coverage.csv",
            [
                {
                    **{
                        key: row[key]
                        for key in (
                            "candidate_id",
                            "contest_id",
                            "name",
                            "state",
                            "district",
                            "party",
                        )
                    },
                    "observation_count": len(row["acquired_background_observations"]),
                    "background_fields_with_observations": row[
                        "background_fields_with_observations"
                    ],
                    "remaining_background_fields": row["remaining_background_fields"],
                }
                for row in profiles
            ],
        ),
    ):
        (output / name).write_bytes(csv_bytes(rows))
    provenance = write_trait_outputs(
        output,
        traits,
        csv_bytes,
        {
            "results/house/manifest.json": root / "results/house/manifest.json",
            "results/house/source-inputs.jsonl.gz": (root / "results/house/source-inputs.jsonl.gz"),
            "data/democratic-background-gap-baseline.json": baseline_path,
            **(
                {"data/democratic-background-research.json": research_path}
                if research_path.exists()
                else {}
            ),
        },
    )
    summary = json.loads((output / "summary.json").read_text())
    summary.update(
        {
            "named_candidates": len(profiles),
            "parties": dict(Counter(row["party"] for row in profiles)),
            "acquired_background_observations": sum(len(rows) for rows in evidence.values()),
            "candidates_with_acquired_observations": len(evidence),
            "candidate_background_research": research,
            "candidate_discovery_repair": repair,
            "participation_source_intake": participation,
            "democratic_candidate_traits": provenance,
            "new_background_fields_used_in_models": False,
            "frozen_analysis_outputs_changed": False,
        }
    )
    write_json(output / "summary.json", summary)
    (output / "report.md").write_text(
        render_report(
            summary,
            read_rows(output / "trait-fits.jsonl.gz"),
            read_rows(root / "results/2026-v4/donor-fits.jsonl.gz"),
            read_rows(root / "results/2026-v4/measurement-fits.jsonl.gz"),
        )
    )
    manifest = json.loads((output / "manifest.json").read_text())
    manifest["schema"] = "which_candidate.house_study.v2"
    manifest["inputs"] = {
        name: fingerprint(root / name)
        for name in (
            *manifest["inputs"],
            "data/democratic-background-gap-baseline.json",
            "data/democratic-background-research.json",
        )
        if (root / name).exists()
    }
    manifest["files"] = {
        path.name: fingerprint(path)
        for path in sorted(output.iterdir())
        if path.is_file() and path.name != "manifest.json"
    }
    write_json(output / "manifest.json", manifest)
    _verify_protected(root, baseline)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--evidence-only", action="store_true")
    args = parser.parse_args()
    function = refresh_evidence if args.evidence_only else build
    print(json.dumps(function(args.root, args.output), indent=2))
