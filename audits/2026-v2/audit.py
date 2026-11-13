"""Reproduce the v2 critique without changing any analysis or publication files."""

import csv
import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.stats import t

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
ANALYSIS = ROOT / "results/2026"
PUBLICATION = ROOT / "publication/2026-v2"
FOCAL = {
    "incumbency": "D_incumbent",
    "ideology": "rightward_01",
    "defection": "defection_5pp",
    "age": "age_10years",
    "tenure": "tenure_10years",
    "gender": "source_F",
}


def load(path):
    with gzip.open(path, "rt") as stream:
        return [json.loads(line) for line in stream]


def receipts():
    return {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for folder in (ANALYSIS, PUBLICATION)
        for path in sorted(folder.rglob("*"))
        if path.is_file()
    }


def check_csv(path, expected, keys):
    def key(row):
        return tuple(
            round(float(row[k]), 10) if k == "x" else "" if row[k] is None else str(row[k])
            for k in keys
        )

    expected = {key(r): r for r in expected}
    with path.open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == len(expected), (path, len(rows), len(expected))
    remaining = set(expected)
    for row in rows:
        identifier = key(row)
        assert identifier in remaining
        remaining.remove(identifier)
        for field, text in row.items():
            value = expected[identifier][field]
            if isinstance(value, (float, int)) and not isinstance(value, bool):
                np.testing.assert_allclose(float(text), value, rtol=1e-10, atol=1e-10)
            else:
                assert text == ("" if value is None else str(value))
    return len(rows)


def design(rows, names, context=None):
    values = []
    for row in rows:
        lean = (row["presidential_D_two_party_share_pct"] - 50) / 10
        columns = {"intercept": 1, "lean_10pp": lean, "lean_squared": lean**2}
        for name in names:
            if name in columns:
                continue
            if name.startswith("cycle_"):
                value = row["year"] == int(name.removeprefix("cycle_"))
            elif name in ("D_incumbent", "R_incumbent", "born_in_state", "reported_catholic"):
                value = row[name]
                assert value is not None
            elif name == "rightward_01":
                value = row["nokken_poole_dim1"] * 10
            elif name == "rightward_x_lean":
                value = row["nokken_poole_dim1"] * 10 * lean
            elif name == "defection_5pp":
                value = (1 - row["party_unity_score"]) * 20
            elif name == "age_10years":
                value = (row["age_years"] - 55) / 10
            elif name == "tenure_10years":
                value = row["chamber_tenure_years"] / 10
            elif name == "source_F":
                assert row["source_recorded_gender"] in ("M", "F")
                value = row["source_recorded_gender"] == "F"
            elif name.startswith("population_"):
                key = name.removeprefix("population_").removesuffix("_10pp")
                value = row["constituency_race_shares_pct"][key] / 10
            elif context and name.startswith(context["field"]):
                value = int(row[context["field"]] == context["category"])
                if name.endswith("_x_matching_share_10pp"):
                    share = row["constituency_race_shares_pct"][context["category"]]
                    value *= (share - context["interaction_center_population_pct"]) / 10
            else:
                raise ValueError(f"Unreviewed term: {name}")
            columns[name] = value
        values.append([columns[name] for name in names])
    return np.asarray(values, dtype=float)


def independent_fit(x, y, states):
    n, k = x.shape
    assert np.linalg.matrix_rank(x) == k
    inverse = np.linalg.pinv(x)
    beta = inverse @ y
    residual = y - x @ beta
    groups = sorted(set(states))
    covariance = np.zeros((k, k))
    for state in groups:
        mask = np.array([s == state for s in states])
        influence = inverse[:, mask] @ residual[mask]
        covariance += np.outer(influence, influence)
    covariance *= len(groups) / (len(groups) - 1) * (n - 1) / (n - k)
    return beta, covariance


def check_terms(terms, fits):
    indexed = {(f.get("target_year"), f["model_id"]): f for f in fits}
    for row in terms:
        fit = indexed[row["target_year"], row["model_id"]]
        j = fit["terms"].index(row["term"])
        for field, values in (
            ("estimate_share_pp", "coefficients"),
            ("ci_low", "ci_low"),
            ("ci_high", "ci_high"),
            ("pvalue", "pvalues"),
        ):
            np.testing.assert_allclose(row[field], fit[values][j], rtol=1e-10, atol=1e-10)


def diagnostics(rows, names, focal, context=None):
    x = design(rows, names, context)
    y = np.array([r["descriptive_gap_share_pp"] for r in rows])
    states = [r["state"] for r in rows]
    groups = sorted(set(states))
    j = names.index(focal)
    beta, covariance = independent_fit(x, y, states)
    hat = np.sum(x * np.linalg.pinv(x).T, axis=1)
    controls = np.delete(x, j, axis=1)
    exposure = x[:, j] - controls @ np.linalg.lstsq(controls, x[:, j], rcond=None)[0]
    partial = exposure**2 / (exposure @ exposure)
    cluster_partial = [sum(w for w, s in zip(partial, states) if s == g) for g in groups]
    deletes = []
    for state in groups:
        keep = np.array([s != state for s in states])
        if np.linalg.matrix_rank(x[keep]) == x.shape[1]:
            deletes.append(
                {
                    "state": state,
                    "estimate": float(np.linalg.lstsq(x[keep], y[keep], rcond=None)[0][j]),
                }
            )
    se_cv1 = float(np.sqrt(covariance[j, j]))
    critical = t.ppf(0.975, len(groups) - 1)
    result = {
        "n": len(rows),
        "parameters": len(names),
        "state_clusters": len(groups),
        "estimate": float(beta[j]),
        "cv1_interval": [float(beta[j] - critical * se_cv1), float(beta[j] + critical * se_cv1)],
        "max_observation_leverage": float(hat.max()),
        "max_leverage_candidate": rows[int(hat.argmax())]["D_name"],
        "inverse_herfindahl_of_cluster_partial_leverage": float(
            1 / np.sum(np.square(cluster_partial))
        ),
        "leave_state_out": deletes,
    }
    if len(deletes) == len(groups):
        se_cv3 = float(
            np.sqrt(
                (len(groups) - 1)
                / len(groups)
                * sum((r["estimate"] - beta[j]) ** 2 for r in deletes)
            )
        )
        result.update(
            cv1_se=se_cv1,
            cv3_se=se_cv3,
            cv3_interval=[float(beta[j] - critical * se_cv3), float(beta[j] + critical * se_cv3)],
        )
    return result


def main():
    before = receipts()
    panel = load(ANALYSIS / "candidate-queries.jsonl.gz")
    by_id = {r["D_candidate_election_id"]: r for r in panel if r["D_candidate_election_id"]}
    fits = load(ANALYSIS / "2026-model-fits.jsonl.gz")
    contextual = load(ANALYSIS / "contextual-model-fits.jsonl.gz")
    annual = load(PUBLICATION / "comparison/annual-model-fits.jsonl.gz")
    validation = load(ANALYSIS / "validation.jsonl.gz")
    checked = 0
    for fit in fits + annual + contextual + load(ANALYSIS / "model-fits.jsonl.gz"):
        if fit["status"] != "estimated":
            continue
        rows = [by_id[i] for i in fit["candidate_election_ids"]]
        assert len(rows) == fit["n"]
        assert all(r["eligible"] and r["chamber"] == fit["chamber"] for r in rows)
        if fit.get("target_year") is not None:
            assert all(r["year"] == fit["target_year"] for r in rows)
        x = design(rows, fit["terms"], fit if "field" in fit else None)
        beta, covariance = independent_fit(
            x, np.array([r["descriptive_gap_share_pp"] for r in rows]), [r["state"] for r in rows]
        )
        np.testing.assert_allclose(beta, fit["coefficients"], rtol=1e-7, atol=1e-8)
        np.testing.assert_allclose(covariance, fit["covariance"], rtol=1e-6, atol=1e-8)
        error = np.sqrt(np.diag(covariance))
        critical = t.ppf(0.975, fit["state_clusters"] - 1)
        np.testing.assert_allclose(beta - critical * error, fit["ci_low"], rtol=1e-6, atol=1e-8)
        np.testing.assert_allclose(beta + critical * error, fit["ci_high"], rtol=1e-6, atol=1e-8)
        pvalues = [
            2 * t.sf(abs(value) / se, fit["state_clusters"] - 1) if se > 0 else 1.0
            for value, se in zip(beta, error)
        ]
        np.testing.assert_allclose(pvalues, fit["pvalues"], rtol=1e-6, atol=1e-10)
        checked += 1

    terms = load(ANALYSIS / "2026-model-terms.jsonl.gz")
    annual_terms = load(PUBLICATION / "comparison/annual-model-terms.jsonl.gz")
    check_terms(terms, fits)
    check_terms(annual_terms, annual)
    for chamber in ("house", "senate"):
        for year in (2016, 2018, 2020, 2022, 2024, 2026):
            focal = [
                r
                for r in annual_terms
                if r["chamber"] == chamber and r["target_year"] == year and r["primary_focal"]
            ]
            previous = 0
            for rank, row in enumerate(sorted(focal, key=lambda r: r["pvalue"])):
                previous = max(previous, min(1.0, row["pvalue"] * (6 - rank)))
                assert abs(previous - row["holm_pvalue"]) < 1e-12
    plotted_checks = 0
    for chamber in ("house", "senate"):
        for suffix, source in (("characteristics", terms), ("history", annual_terms)):
            path = PUBLICATION / f"plot-data/{chamber}-{suffix}.csv"
            with path.open() as stream:
                for row in csv.DictReader(stream):
                    plotted_checks += 1
                    if row["status"] != "estimated":
                        assert not row.get("estimate_share_pp")
                        continue
                    match = next(
                        r
                        for r in source
                        if r["chamber"] == chamber
                        and r["model"] == row["model"]
                        and r["primary_focal"]
                        and r["target_year"] == int(row.get("year") or 2026)
                    )
                    for field in ("estimate_share_pp", "ci_low", "ci_high", "holm_pvalue", "n"):
                        assert abs(float(row[field]) - match[field]) < 1e-10
    identity_terms = load(ANALYSIS / "contextual-model-terms.jsonl.gz")
    check_terms(identity_terms, contextual)
    for chamber in ("house", "senate"):
        family = [r for r in identity_terms if r["chamber"] == chamber and r["focal"]]
        previous = 0
        for rank, row in enumerate(sorted(family, key=lambda r: r["pvalue"])):
            previous = max(previous, min(1.0, row["pvalue"] * (len(family) - rank)))
            assert abs(previous - row["holm_pvalue"]) < 1e-12
    plotted_checks += check_csv(
        PUBLICATION / "plot-data/identity-comparisons.csv",
        [
            r
            for r in identity_terms
            if r["chamber"] == "house" and r["focal"] and r["variant"] == "census_adjusted"
        ],
        ("model_id",),
    )
    categories = load(ANALYSIS / "identity-category-counts.jsonl.gz")
    coverage = [r for r in categories if r["chamber"] == "house" and r["phase"] == "primary_2026"]
    with (PUBLICATION / "plot-data/identity-coverage.csv").open() as stream:
        coverage_csv = list(csv.DictReader(stream))
    assert len(coverage_csv) == len(coverage)
    for record in coverage_csv:
        expected = next(
            r
            for r in coverage
            if r["field"] == record["field"]
            and ("" if r["category"] is None else str(r["category"])) == record["category"]
        )
        for field in ("rows", "people", "states"):
            assert int(record[field]) == expected[field]
    plotted_checks += len(coverage_csv)
    geography = [
        {
            "candidate_election_id": r["D_candidate_election_id"],
            "chamber": r["chamber"],
            "state": r["state"],
            "name": r["D_name"],
            "D_incumbent": r["D_incumbent"],
            "presidential_D_two_party_share_pct": r["presidential_D_two_party_share_pct"],
            "D_two_party_share_pct": r["D_two_party_share_pct"],
        }
        for r in panel
        if r["year"] == 2026 and r["eligible"]
    ]
    plotted_checks += check_csv(
        PUBLICATION / "plot-data/partisan-geography.csv", geography, ("candidate_election_id",)
    )
    plotted_checks += check_csv(
        PUBLICATION / "plot-data/predictive-lift.csv",
        [r for r in validation if r["year"] == 2026],
        ("chamber", "model", "year"),
    )
    record_points = []
    for fit in fits:
        if (
            fit["chamber"] != "house"
            or fit["variant"] != "primary"
            or fit["model"] not in ("ideology", "defection")
        ):
            continue
        rows = [by_id[i] for i in fit["candidate_election_ids"]]
        x = design(rows, fit["terms"])
        beta = np.array(fit["coefficients"])
        j = fit["terms"].index(FOCAL[fit["model"]])
        controls = x.copy()
        controls[:, j] = 0
        center = controls.mean(axis=0)
        adjusted = (
            np.array([r["descriptive_gap_share_pp"] for r in rows]) - (controls - center) @ beta
        )
        scale = 0.1 if fit["model"] == "ideology" else 5
        for i, row in enumerate(rows):
            record_points.append(
                {
                    "kind": "candidate",
                    "model": fit["model"],
                    "candidate_election_id": row["D_candidate_election_id"],
                    "name": row["D_name"],
                    "state": row["state"],
                    "x": x[i, j] * scale,
                    "adjusted_gap_share_pp": adjusted[i],
                    "raw_gap_share_pp": row["descriptive_gap_share_pp"],
                    "ci_low": None,
                    "ci_high": None,
                }
            )
        for value in np.linspace(x[:, j].min(), x[:, j].max(), 100):
            prediction = center.copy()
            prediction[j] = value
            mean = float(prediction @ beta)
            error = float(np.sqrt(max(0, prediction @ np.array(fit["covariance"]) @ prediction)))
            critical = t.ppf(0.975, fit["state_clusters"] - 1)
            record_points.append(
                {
                    "kind": "fitted_mean",
                    "model": fit["model"],
                    "candidate_election_id": None,
                    "name": None,
                    "state": None,
                    "x": value * scale,
                    "adjusted_gap_share_pp": mean,
                    "raw_gap_share_pp": None,
                    "ci_low": mean - critical * error,
                    "ci_high": mean + critical * error,
                }
            )
    plotted_checks += check_csv(
        PUBLICATION / "plot-data/house-voting-records.csv",
        record_points,
        ("kind", "model", "candidate_election_id", "x"),
    )

    primary = {}
    for fit in fits:
        if fit["variant"] != "primary" or fit["status"] != "estimated":
            continue
        rows = [by_id[i] for i in fit["candidate_election_ids"]]
        focal = FOCAL[fit["model"]]
        item = diagnostics(rows, fit["terms"], focal)
        if fit["chamber"] == "senate" and fit["model"] == "incumbency":
            item["without_montana_sensitivity"] = diagnostics(
                [r for r in rows if r["state"] != "MT"], fit["terms"], focal
            )
        if fit["chamber"] == "house":
            x = design(rows, fit["terms"])
            groups = sorted({r["state"] for r in rows})
            state_dummies = [[int(r["state"] == s) for s in groups[1:]] for r in rows]
            state_x = np.column_stack((x, state_dummies))
            assert np.linalg.matrix_rank(state_x) == state_x.shape[1]
            state_beta = np.linalg.lstsq(
                state_x, [r["descriptive_gap_share_pp"] for r in rows], rcond=None
            )[0]
            item["state_fixed_effects_sensitivity"] = float(state_beta[fit["terms"].index(focal)])
        if fit["model"] in ("ideology", "defection"):
            values = [
                r["nokken_poole_dim1"]
                if fit["model"] == "ideology"
                else (1 - r["party_unity_score"]) * 100
                for r in rows
            ]
            item["observed_feature_range"] = [min(values), max(values)]
        primary[fit["model_id"]] = item

    identity = {}
    for fit in contextual:
        if fit["variant"] != "census_adjusted" or fit["status"] != "estimated":
            continue
        rows = [by_id[i] for i in fit["candidate_election_ids"]]
        focal = f"{fit['field']}_{fit['category']}"
        identity[fit["model_id"]] = {
            **diagnostics(rows, fit["terms"], focal, fit),
            "group_support": fit["group_support"],
        }

    missingness = {}
    for chamber in ("house", "senate"):
        cohort = [
            r for r in panel if r["year"] == 2026 and r["chamber"] == chamber and r["eligible"]
        ]
        incumbents = [
            r
            for r in cohort
            if r["D_incumbent"] is True and r["service_verified_incumbent"] is True
        ]
        missing = [r for r in incumbents if r["nokken_poole_dim1"] is None]
        missingness[chamber] = {
            "eligible_nominees": len(cohort),
            "verified_incumbents": len(incumbents),
            "missing_incumbent_ideology": len(missing),
            "missing_ideology_with_under_two_years_service": sum(
                r["chamber_tenure_years"] < 2 for r in missing
            ),
        }

    historical_benchmark_sensitivity = []
    for fit in annual:
        if fit["target_year"] != 2024 or fit["chamber"] != "house" or fit["variant"] != "primary":
            continue
        rows = [by_id[i] for i in fit["candidate_election_ids"]]
        alternative = [
            {
                **r,
                "presidential_D_two_party_share_pct": r["benchmark_evidence"][
                    "alternate_D_two_party_share_pct"
                ],
                "descriptive_gap_share_pp": r["D_two_party_share_pct"]
                - r["benchmark_evidence"]["alternate_D_two_party_share_pct"],
            }
            for r in rows
        ]
        j = fit["terms"].index(FOCAL[fit["model"]])
        x = design(alternative, fit["terms"])
        beta = np.linalg.lstsq(x, [r["descriptive_gap_share_pp"] for r in alternative], rcond=None)[
            0
        ]
        historical_benchmark_sensitivity.append(
            {
                "model": fit["model"],
                "n": len(rows),
                "same_year_2024": fit["coefficients"][j],
                "lagged_2020": float(beta[j]),
            }
        )

    mcguire_fit = next(f for f in fits if f["model_id"] == "house:incumbency:primary")
    sample = [by_id[i] for i in mcguire_fit["candidate_election_ids"]]
    mcguire = next(r for r in sample if r["state"] == "CA" and r["district"] == "01")
    assert mcguire["D_name"] == "Mike McGuire" and mcguire["D_incumbent"] is True
    corrected = [{**r, "D_incumbent": False} if r is mcguire else r for r in sample]
    correction = diagnostics(corrected, mcguire_fit["terms"], "D_incumbent")

    folds = load(ANALYSIS / "folds.jsonl.gz")
    forward_count = 0
    for fold in folds:
        train = [by_id[i] for i in fold["train_ids"]]
        test = [by_id[i] for i in fold["test_ids"]]
        assert not {r["state"] for r in train} & {r["state"] for r in test}
        assert not {r["person_group"] for r in train} & {r["person_group"] for r in test}
        if ":forward:" in fold["fold_id"]:
            assert all(a["year"] < b["year"] for a in train for b in test)
            forward_count += int(any(r["year"] == 2026 for r in test))
    assert receipts() == before
    result = {
        "release_reviewed": "2026-v2",
        "audit_date": "2026-11-13",
        "all_values_are_share_percentage_points_unless_labeled": True,
        "sensitivity_warning": "Post-publication diagnostic checks, not new confirmatory tests or replacement results.",
        "independent_fit_checks_including_repeated_2026_fits": checked,
        "plotted_csv_rows_checked_across_nine_figures": plotted_checks,
        "fold_checks": len(folds),
        "forward_2026_fold_checks": forward_count,
        "frozen_inputs_unchanged": True,
        "input_sha256": before,
        "primary_diagnostics": primary,
        "contextual_diagnostics": identity,
        "sample_coverage": missingness,
        "identity_coverage_2026_house_incumbents": coverage,
        "historical_benchmark_sensitivity": historical_benchmark_sensitivity,
        "mcguire_only_incumbency_correction_sensitivity": correction,
        "validation_2026": [r for r in validation if r["year"] == 2026],
        "third_party_senate_cases_over_10pct": [
            {
                "state": r["state"],
                "D_name": r["D_name"],
                "other_share_pct": 100 * r["O_votes"] / r["all_candidate_votes"],
                "gap_share_pp": r["descriptive_gap_share_pp"],
            }
            for r in panel
            if r["year"] == 2026
            and r["chamber"] == "senate"
            and r["eligible"]
            and r["O_votes"] / r["all_candidate_votes"] > 0.1
        ],
        "external_primary_sources": {
            "mcguire_state_senate_biography": "https://sd02.senate.ca.gov/biography",
            "mcguire_fec_record_with_conflicting_incumbent_flag": "https://www.fec.gov/data/candidate/H6CA01269/",
            "california_special_candidates": "https://elections.cdn.sos.ca.gov/special-elections/2026-cd1/cert-list-primary.pdf",
            "california_general_candidates": "https://elections.cdn.sos.ca.gov/statewide-elections/2026-general/cert-list-candidates.pdf",
            "gallagher_federal_service": "https://history.house.gov/People/Listing/G/GALLAGHER%2C-James-%28G000607%29/",
            "cluster_inference_methods": "https://doi.org/10.1016/j.jeconom.2022.04.001",
            "asa_pvalue_statement": "https://doi.org/10.1080/00031305.2016.1154108",
            "voteview_measurement": "https://voteview.com/articles/data_help_members",
        },
    }
    destination = HERE / "audit-results.json"
    destination.write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(f"Verified {checked} fits, {plotted_checks} plotted comparisons and {len(folds)} folds.")
    print(f"Saved {destination.relative_to(ROOT)}; frozen analysis/publication bytes unchanged.")


if __name__ == "__main__":
    main()
