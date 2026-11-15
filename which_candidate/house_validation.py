"""Paired, state-and-person-held-out tests of candidate-trait predictive value."""

import math

import numpy as np
from scipy.stats import t

from .models import PRIMARY, available, matrix

RECORD_MODELS = ("ideology", "defection", "age", "tenure", "gender")
PREDICTIVE_MODELS = {
    "incumbency": "D/R incumbency",
    "ideology": "Prior voting ideology",
    "defection": "Party defection",
    "age": "Age",
    "tenure": "House service",
    "gender": "Source-recorded gender",
    "donor": "Historical donor ideology",
    "joint_records": "All five incumbent-record traits",
}


def person_key(row):
    return (
        row.get("person_group")
        or row.get("bioguide_id")
        or row.get("D_fec_id")
        or row["D_candidate_election_id"]
    )


def qualifies(row, model):
    if model in PRIMARY:
        return available(row, model)
    if model == "joint_records":
        return all(available(row, name) for name in RECORD_MODELS)
    if model == "donor":
        donor = row.get("donor", {})
        return (
            available(row, "incumbency")
            and donor.get("qualified") is True
            and donor.get("score") is not None
            and math.isfinite(donor["score"])
        )
    raise ValueError(f"Unknown predictive model: {model}")


def designs(rows, model):
    baseline, base_terms = matrix(rows, "baseline", [2026])
    if model in PRIMARY:
        augmented, terms = matrix(rows, model, [2026])
    elif model == "joint_records":
        terms = [*base_terms, *(PRIMARY[name][0] for name in RECORD_MODELS)]
        augmented = np.column_stack(
            [baseline, *(matrix(rows, name, [2026])[0][:, -1] for name in RECORD_MODELS)]
        )
    elif model == "donor":
        baseline, base_terms = matrix(rows, "incumbency", [2026])
        augmented = np.column_stack([baseline, [r["donor"]["score"] / 0.5 for r in rows]])
        terms = [*base_terms, "donor_rightward_05"]
    else:
        raise ValueError(f"Unknown predictive model: {model}")
    return baseline, base_terms, augmented, terms


def paired_predictions(rows, model):
    rows = sorted(rows, key=lambda r: r["D_candidate_election_id"])
    baseline, base_terms, augmented, terms = designs(rows, model)
    target = np.array([r["descriptive_gap_share_pp"] for r in rows])
    predictions, folds = [], []
    for state in sorted({r["state"] for r in rows}):
        test = [i for i, row in enumerate(rows) if row["state"] == state]
        people = {person_key(rows[i]) for i in test}
        train = [
            i
            for i, row in enumerate(rows)
            if row["state"] != state and person_key(row) not in people
        ]
        training_states = sorted({rows[i]["state"] for i in train})
        supported = (
            len(train) > augmented.shape[1] + 3
            and len(training_states) >= 8
            and all(
                np.linalg.matrix_rank(design[train]) == design.shape[1]
                and np.linalg.cond(design[train]) < 1e10
                for design in (baseline, augmented)
            )
        )
        fold_id = f"2026:house:paired:{model}:{state}"
        folds.append(
            {
                "model": model,
                "fold_id": fold_id,
                "held_out_state": state,
                "baseline_terms": base_terms,
                "augmented_terms": terms,
                "training_candidate_ids": [rows[i]["D_candidate_election_id"] for i in train],
                "test_candidate_ids": [rows[i]["D_candidate_election_id"] for i in test],
                "training_states": training_states,
                "training_people": sorted({person_key(rows[i]) for i in train}),
                "test_people": sorted(people),
                "status": "estimated" if supported else "insufficient_training_support",
            }
        )
        if not supported:
            continue
        base_beta = np.linalg.lstsq(baseline[train], target[train], rcond=None)[0]
        trait_beta = np.linalg.lstsq(augmented[train], target[train], rcond=None)[0]
        for i in test:
            row = rows[i]
            base_share = row["presidential_D_two_party_share_pct"] + float(baseline[i] @ base_beta)
            trait_share = row["presidential_D_two_party_share_pct"] + float(
                augmented[i] @ trait_beta
            )
            base_error = row["D_two_party_share_pct"] - base_share
            trait_error = row["D_two_party_share_pct"] - trait_share
            predictions.append(
                {
                    "model": model,
                    "fold_id": fold_id,
                    "candidate_election_id": row["D_candidate_election_id"],
                    "contest_id": row["contest_id"],
                    "state": state,
                    "name": row["D_name"],
                    "observed_D_share_pct": row["D_two_party_share_pct"],
                    "baseline_expected_D_share_pct": base_share,
                    "augmented_expected_D_share_pct": trait_share,
                    "baseline_error_share_pp": base_error,
                    "augmented_error_share_pp": trait_error,
                    "absolute_error_gain_share_pp": abs(base_error) - abs(trait_error),
                    "baseline_share_in_bounds": 0 <= base_share <= 100,
                    "augmented_share_in_bounds": 0 <= trait_share <= 100,
                }
            )
    return predictions, folds


def error_metrics(predictions):
    if not predictions:
        return {
            key: None
            for key in (
                "baseline_MAE_share_pp",
                "augmented_MAE_share_pp",
                "MAE_gain_share_pp",
                "baseline_RMSE_share_pp",
                "augmented_RMSE_share_pp",
                "baseline_bias_share_pp",
                "augmented_bias_share_pp",
            )
        }
    baseline = np.array([r["baseline_error_share_pp"] for r in predictions])
    augmented = np.array([r["augmented_error_share_pp"] for r in predictions])
    return {
        "baseline_MAE_share_pp": float(np.mean(np.abs(baseline))),
        "augmented_MAE_share_pp": float(np.mean(np.abs(augmented))),
        "MAE_gain_share_pp": float(np.mean(np.abs(baseline) - np.abs(augmented))),
        "baseline_RMSE_share_pp": float(np.sqrt(np.mean(baseline**2))),
        "augmented_RMSE_share_pp": float(np.sqrt(np.mean(augmented**2))),
        "baseline_bias_share_pp": float(np.mean(baseline)),
        "augmented_bias_share_pp": float(np.mean(augmented)),
    }


def predictive_comparisons(panel):
    summaries, predictions, folds, deletions = [], [], [], []
    for model, label in PREDICTIVE_MODELS.items():
        sample = [r for r in panel if qualifies(r, model)]
        paired, model_folds = paired_predictions(sample, model)
        states = sorted({r["state"] for r in sample})
        complete = bool(sample) and len(paired) == len(sample)
        metrics = error_metrics(paired)
        replicates = []
        if complete and len(sample) >= 30 and len(states) >= 10:
            for state in states:
                reduced = [r for r in sample if r["state"] != state]
                deleted_predictions, deleted_folds = paired_predictions(reduced, model)
                deletion_complete = len(deleted_predictions) == len(reduced)
                gain = error_metrics(deleted_predictions)["MAE_gain_share_pp"]
                deletions.append(
                    {
                        "model": model,
                        "deleted_state": state,
                        "removed_candidate_ids": [
                            r["D_candidate_election_id"] for r in sample if r["state"] == state
                        ],
                        "remaining_candidates": len(reduced),
                        "paired_predictions": len(deleted_predictions),
                        "failed_folds": [
                            r["fold_id"] for r in deleted_folds if r["status"] != "estimated"
                        ],
                        "status": "estimated" if deletion_complete else "incomplete",
                        "MAE_gain_share_pp": gain if deletion_complete else None,
                    }
                )
                if deletion_complete:
                    replicates.append(gain)
        supported = len(states) >= 10 and len(replicates) == len(states) and complete
        error = (
            float(
                np.sqrt(
                    (len(states) - 1)
                    / len(states)
                    * np.sum((np.array(replicates) - np.mean(replicates)) ** 2)
                )
            )
            if supported
            else None
        )
        width = float(t.ppf(0.975, len(states) - 1)) * error if error is not None else None
        summaries.append(
            {
                "model": model,
                "label": label,
                "qualified_candidates": len(sample),
                "paired_predictions": len(paired),
                "state_clusters": len(states),
                "complete_paired_predictions": complete,
                "complete_state_deletions": len(replicates),
                "candidate_election_ids": [r["D_candidate_election_id"] for r in sample],
                **metrics,
                "jackknife_standard_error_share_pp": error,
                "gain_ci_low_share_pp": metrics["MAE_gain_share_pp"] - width
                if width is not None
                else None,
                "gain_ci_high_share_pp": metrics["MAE_gain_share_pp"] + width
                if width is not None
                else None,
                "baseline_shares_outside_0_100": sum(
                    not r["baseline_share_in_bounds"] for r in paired
                ),
                "augmented_shares_outside_0_100": sum(
                    not r["augmented_share_in_bounds"] for r in paired
                ),
                "publication_status": "supported_exploratory"
                if supported
                else "diagnostic_only_incomplete_support",
                "interpretation": "Retrospective paired prediction, not forward forecasts "
                "or causal effects. Pointwise full-pipeline state-jackknife interval; "
                "no model selection or multiplicity-adjusted discovery claim.",
            }
        )
        predictions.extend(paired)
        folds.extend(model_folds)
    return summaries, predictions, folds, deletions


def selection_diagnostics(panel, winner_flags):
    rows = [r for r in panel if r["eligible"]]
    groups = {("all", "all_qualified"): rows}
    for row in rows:
        role = (
            "verified_D_incumbent"
            if row.get("D_incumbent") is True and row.get("service_verified_incumbent") is True
            else "recorded_D_nonincumbent"
            if row.get("D_incumbent") is False
            else "unverified_or_unknown"
        )
        lean = row["presidential_D_two_party_share_pct"]
        band = "below_40" if lean < 40 else "40_to_60" if lean <= 60 else "above_60"
        flag = winner_flags.get(row["contest_id"])
        winner = (
            "flagged_winner"
            if flag is True
            else "not_flagged_winner"
            if flag is False
            else "unknown_flag"
        )
        for axis, group in (
            ("D_incumbency", role),
            ("presidential_D_share", band),
            ("native_winner_flag", winner),
        ):
            groups.setdefault((axis, group), []).append(row)
    output = []
    for model in PREDICTIVE_MODELS:
        for (axis, group), cohort in sorted(groups.items()):
            included = [r for r in cohort if qualifies(r, model)]
            excluded = [r for r in cohort if not qualifies(r, model)]
            record = {
                "model": model,
                "partition": axis,
                "group": group,
                "qualified_comparisons": len(cohort),
                "included": len(included),
                "excluded": len(excluded),
                "included_pct": 100 * len(included) / len(cohort),
            }
            for name, subset in (("included", included), ("excluded", excluded)):
                for field in ("presidential_D_two_party_share_pct", "descriptive_gap_share_pp"):
                    record[f"{name}_mean_{field}"] = (
                        float(np.mean([r[field] for r in subset])) if subset else None
                    )
            output.append(record)
    return output
