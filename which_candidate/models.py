from collections import defaultdict

import numpy as np
from scipy.stats import t

PRIMARY = {
    "incumbency": ("D_incumbent", "Democratic incumbent versus nonincumbent"),
    "ideology": ("rightward_01", "+0.1 rightward Nokken-Poole"),
    "defection": ("defection_5pp", "+5 pp party defection"),
    "age": ("age_10years", "+10 years of age"),
    "tenure": ("tenure_10years", "+10 years of chamber service"),
    "gender": ("source_F", "Source-recorded F versus M"),
}
SUPPLEMENTAL = {
    "born_in_state": ("born_in_state", "Born in represented state versus explicitly elsewhere"),
    "religion": ("reported_catholic", "Explicitly Catholic versus other reported religion"),
}


def available(row, model):
    if not row["eligible"]:
        return False
    if model == "baseline":
        return True
    if model == "incumbency":
        return row.get("D_incumbent") is not None and row.get("R_incumbent") is not None
    if row.get("D_incumbent") is not True or row.get("service_verified_incumbent") is not True:
        return False
    requirements = {
        "ideology": ("nokken_poole_dim1",),
        "ideology_lean": ("nokken_poole_dim1",),
        "defection": ("party_unity_score",),
        "joint": ("nokken_poole_dim1", "party_unity_score"),
        "age": ("age_years",),
        "tenure": ("chamber_tenure_years",),
        "gender": ("source_recorded_gender",),
        "born_in_state": ("born_in_state",),
        "religion": ("reported_catholic",),
    }
    if any(row.get(key) is None for key in requirements[model]):
        return False
    return model != "gender" or row["source_recorded_gender"] in ("M", "F")


def matrix(rows, model, cycles=None, forward=False, quadratic=True):
    terms = ["intercept", "lean_10pp"]
    if quadratic:
        terms.append("lean_squared")
    if forward:
        terms.append("midterm")
    else:
        terms.extend(f"cycle_{year}" for year in (cycles or [])[1:])
    extra = {
        "baseline": [],
        "incumbency": ["D_incumbent", "R_incumbent"],
        "ideology": ["rightward_01"],
        "ideology_lean": ["rightward_01", "rightward_x_lean"],
        "defection": ["defection_5pp"],
        "joint": ["rightward_01", "defection_5pp"],
        "age": ["age_10years"],
        "tenure": ["tenure_10years"],
        "gender": ["source_F"],
        "born_in_state": ["born_in_state"],
        "religion": ["reported_catholic"],
    }[model]
    terms.extend(extra)
    values = []
    for row in rows:
        lean = (row["presidential_D_two_party_share_pct"] - 50) / 10
        features = {
            "intercept": 1,
            "lean_10pp": lean,
            "lean_squared": lean * lean,
            "midterm": int(row["year"] % 4 != 0),
        }
        features.update({f"cycle_{year}": int(row["year"] == year) for year in cycles or []})
        if model == "incumbency":
            features.update(
                D_incumbent=int(row["D_incumbent"]), R_incumbent=int(row["R_incumbent"])
            )
        if model in ("ideology", "ideology_lean", "joint"):
            features["rightward_01"] = row["nokken_poole_dim1"] / 0.1
            features["rightward_x_lean"] = features["rightward_01"] * lean
        if model in ("defection", "joint"):
            features["defection_5pp"] = (1 - row["party_unity_score"]) * 100 / 5
        if model == "age":
            features["age_10years"] = (row["age_years"] - 55) / 10
        if model == "tenure":
            features["tenure_10years"] = row["chamber_tenure_years"] / 10
        if model == "gender":
            features["source_F"] = int(row["source_recorded_gender"] == "F")
        if model in SUPPLEMENTAL:
            key = SUPPLEMENTAL[model][0]
            features[key] = int(row[key])
        values.append([features[term] for term in terms])
    return np.asarray(values, dtype=float).reshape((len(rows), len(terms))), terms


def fit_clustered(x, y, clusters):
    n, k = x.shape
    groups = sorted(set(clusters))
    result = {"n": n, "parameters": k, "state_clusters": len(groups)}
    if n <= k + 3 or len(groups) < 8:
        return {**result, "status": "insufficient_rows_or_state_clusters"}
    coefficients, _, rank, singular = np.linalg.lstsq(x, y, rcond=None)
    condition = float(singular[0] / singular[-1]) if singular[-1] > 0 else None
    result.update(rank=int(rank), condition_number=condition)
    if rank != k or condition is None or condition > 1e10:
        return {**result, "status": "rank_deficient_or_ill_conditioned"}
    residual = y - x @ coefficients
    meat = np.zeros((k, k))
    cluster_array = np.asarray(clusters)
    for group in groups:
        mask = cluster_array == group
        score = x[mask].T @ residual[mask]
        meat += np.outer(score, score)
    bread = np.linalg.pinv(x.T @ x)
    covariance = bread @ meat @ bread
    covariance *= len(groups) / (len(groups) - 1) * (n - 1) / (n - k)
    error = np.sqrt(np.maximum(np.diag(covariance), 0))
    critical = t.ppf(0.975, len(groups) - 1)
    pvalues = [
        float(2 * t.sf(abs(b / se), len(groups) - 1)) if se > 0 else float(b == 0)
        for b, se in zip(coefficients, error)
    ]
    return {
        **result,
        "status": "estimated",
        "coefficients": coefficients.tolist(),
        "standard_errors": error.tolist(),
        "ci_low": (coefficients - critical * error).tolist(),
        "ci_high": (coefficients + critical * error).tolist(),
        "pvalues": pvalues,
        "covariance": covariance.tolist(),
        "rmse_share_pp": float(np.sqrt(np.mean(residual**2))),
    }


def associations(panel):
    fits, terms = [], []
    for chamber in ("house", "senate"):
        historical = [r for r in panel if r["chamber"] == chamber and r["year"] <= 2022]
        for model in (*PRIMARY, *SUPPLEMENTAL, "joint", "ideology_lean"):
            sample = [r for r in historical if available(r, model)]
            variants = {
                "primary"
                if model in PRIMARY
                else "supplemental"
                if model in SUPPLEMENTAL
                else "joint_or_interaction": sample
            }
            if model in ("incumbency", "ideology", "defection"):
                variants["competitive_40_60"] = [
                    r for r in sample if 40 <= r["presidential_D_two_party_share_pct"] <= 60
                ]
                variants["linear_lean"] = sample
                for year in (2016, 2018, 2020, 2022):
                    variants[f"cycle_only_{year}"] = [r for r in sample if r["year"] == year]
            for variant, rows in variants.items():
                model_id = f"{chamber}:{model}:{variant}"
                cycles = sorted({r["year"] for r in rows})
                x, names = matrix(rows, model, cycles, quadratic=variant != "linear_lean")
                y = np.array([r["descriptive_gap_share_pp"] for r in rows])
                fit = fit_clustered(x, y, [r["state"] for r in rows])
                fits.append(
                    {
                        "model_id": model_id,
                        "chamber": chamber,
                        "model": model,
                        "variant": variant,
                        "terms": names,
                        "candidate_election_ids": [r["D_candidate_election_id"] for r in rows],
                        **fit,
                    }
                )
                if fit["status"] != "estimated":
                    continue
                for index, name in enumerate(names):
                    terms.append(
                        {
                            "model_id": model_id,
                            "chamber": chamber,
                            "model": model,
                            "variant": variant,
                            "term": name,
                            "estimate_share_pp": fit["coefficients"][index],
                            "ci_low": fit["ci_low"][index],
                            "ci_high": fit["ci_high"][index],
                            "pvalue": fit["pvalues"][index],
                            "holm_pvalue": None,
                            "n": fit["n"],
                            "state_clusters": fit["state_clusters"],
                            "primary_focal": variant == "primary" and name == PRIMARY[model][0],
                            "supplemental_focal": variant == "supplemental"
                            and name == SUPPLEMENTAL[model][0],
                        }
                    )
        focal = [r for r in terms if r["chamber"] == chamber and r["primary_focal"]]
        previous = 0
        for rank, row in enumerate(sorted(focal, key=lambda r: r["pvalue"])):
            previous = max(previous, min(1.0, row["pvalue"] * (len(PRIMARY) - rank)))
            row["holm_pvalue"] = previous
    return fits, terms


def purge(train, test):
    states = {r["state"] for r in test}
    people = {r["person_group"] for r in test if r.get("person_group")}
    return [r for r in train if r["state"] not in states and r.get("person_group") not in people]


def folds_and_predictions(panel):
    predictions, folds = [], []
    for chamber in ("house", "senate"):
        eligible = [r for r in panel if r["chamber"] == chamber and r["eligible"]]
        historical = [r for r in eligible if r["year"] <= 2022]
        for state in sorted({r["state"] for r in historical}):
            test = [r for r in historical if r["state"] == state]
            train = purge(historical, test)
            cycles = sorted({r["year"] for r in historical})
            x, names = matrix(train, "baseline", cycles)
            fit = fit_clustered(
                x,
                np.array([r["descriptive_gap_share_pp"] for r in train]),
                [r["state"] for r in train],
            )
            fold_id = f"{chamber}:retrospective:{state}"
            folds.append(fold_record(fold_id, train, test, {"terms": names, **fit}))
            if fit["status"] == "estimated":
                test_x, _ = matrix(test, "baseline", cycles)
                expected = test_x @ fit["coefficients"]
                for row, gap in zip(test, expected):
                    predictions.append(
                        {
                            "kind": "retrospective_state_held_out",
                            "fold_id": fold_id,
                            "chamber": chamber,
                            "year": row["year"],
                            "state": state,
                            "candidate_election_id": row["D_candidate_election_id"],
                            "observed_share_pct": row["D_two_party_share_pct"],
                            "expected_share_pct": row["presidential_D_two_party_share_pct"]
                            + float(gap),
                            "cross_fitted_overperformance_share_pp": row["descriptive_gap_share_pp"]
                            - float(gap),
                        }
                    )
        for model in (*PRIMARY, *SUPPLEMENTAL):
            sample = [r for r in eligible if available(r, model)]
            for year in (2018, 2020, 2022, 2024):
                for state in sorted({r["state"] for r in sample if r["year"] == year}):
                    test = [r for r in sample if r["year"] == year and r["state"] == state]
                    train = purge([r for r in sample if r["year"] < year], test)
                    fold_id = f"{chamber}:forward:{model}:{year}:{state}"
                    fitted, fit_records = {}, {}
                    for kind in ("baseline", model):
                        x, names = matrix(train, kind, forward=True)
                        # The first backtest has only presidential-year training data.
                        keep = (
                            [
                                i
                                for i in range(len(names))
                                if names[i] == "intercept" or np.ptp(x[:, i]) > 0
                            ]
                            if len(train)
                            else list(range(len(names)))
                        )
                        x = x[:, keep]
                        fit = fit_clustered(
                            x,
                            np.array([r["descriptive_gap_share_pp"] for r in train]),
                            [r["state"] for r in train],
                        )
                        fit_records[kind] = {"terms": [names[i] for i in keep], **fit}
                        if fit["status"] == "estimated":
                            tx, _ = matrix(test, kind, forward=True)
                            fitted[kind] = (tx[:, keep] @ fit["coefficients"]).tolist()
                    folds.append(
                        fold_record(
                            fold_id,
                            train,
                            test,
                            {
                                "status": "estimated" if len(fitted) == 2 else "not_estimable",
                                "models": fit_records,
                            },
                        )
                    )
                    if len(fitted) != 2:
                        continue
                    for index, row in enumerate(test):
                        predictions.append(
                            {
                                "kind": "chronological_state_held_out",
                                "fold_id": fold_id,
                                "model": model,
                                "chamber": chamber,
                                "year": year,
                                "state": state,
                                "candidate_election_id": row["D_candidate_election_id"],
                                "observed_gap": row["descriptive_gap_share_pp"],
                                "baseline_predicted_gap": fitted["baseline"][index],
                                "feature_predicted_gap": fitted[model][index],
                                "locked_validation_2024": year == 2024,
                            }
                        )
    return folds, predictions


def fold_record(fold_id, train, test, fit):
    return {
        "fold_id": fold_id,
        "status": fit["status"],
        "fit": fit,
        "train_ids": [r["D_candidate_election_id"] for r in train],
        "test_ids": [r["D_candidate_election_id"] for r in test],
        "train_years": sorted({r["year"] for r in train}),
        "test_years": sorted({r["year"] for r in test}),
        "train_states": sorted({r["state"] for r in train}),
        "test_states": sorted({r["state"] for r in test}),
        "candidate_group_overlap": len(
            {r["person_group"] for r in train} & {r["person_group"] for r in test}
        ),
    }


def validation_summary(predictions):
    grouped = defaultdict(list)
    for row in predictions:
        if row["kind"] == "chronological_state_held_out":
            grouped[(row["chamber"], row["model"], row["year"])].append(row)
    result = []
    for (chamber, model, year), rows in sorted(grouped.items()):
        record = {"chamber": chamber, "model": model, "year": year, "n": len(rows)}
        for prefix, field in (
            ("baseline", "baseline_predicted_gap"),
            ("feature", "feature_predicted_gap"),
        ):
            error = np.array([r["observed_gap"] - r[field] for r in rows])
            record[f"{prefix}_mae"] = float(np.mean(np.abs(error)))
            record[f"{prefix}_rmse"] = float(np.sqrt(np.mean(error**2)))
            record[f"{prefix}_bias"] = float(np.mean(error))
            record[f"{prefix}_retrospective_centered_mae"] = float(
                np.mean(np.abs(error - np.mean(error)))
            )
        record["mae_improvement"] = record["baseline_mae"] - record["feature_mae"]
        result.append(record)
    return result
