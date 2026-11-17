"""Reconstruct V8 without calling its fitting or prediction implementations."""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import f, t

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from which_candidate.storage import read_rows  # noqa: E402


def validate():
    out = ROOT / "results/house-characteristics-v8"
    panel = {r["D_candidate_election_id"]: r for r in read_rows(out / "panel-overlay.jsonl.gz")}
    values = {
        (r["contest_id"], r["trait"]): r["analysis_value"]
        for r in read_rows(out / "candidate-traits.jsonl.gz")
        if r["party"] == "Democratic" and r["performance_eligible"]
    }
    scales = {"age": 10, "house_service": 10, "donor_ideology": 0.5, "voting_ideology": 0.1}

    def matrix(ids, names, trait):
        result = []
        for cid in ids:
            row = panel[cid]
            lean = (row["presidential_D_two_party_share_pct"] - 50) / 10
            value = values[(row["contest_id"], trait)]
            fixed = {
                "intercept": 1,
                "lean_10pp": lean,
                "lean_squared": lean**2,
                "D_incumbent": int(row["D_incumbent"]),
                "R_incumbent": int(row["R_incumbent"]),
            }
            result.append(
                [
                    fixed[name]
                    if name in fixed
                    else (1 - value) / 0.05
                    if name == "defection_5pp"
                    else int(value == name.split(":", 1)[1].split("_vs_", 1)[0])
                    if ":" in name
                    else value / scales[name]
                    for name in names
                ]
            )
        return np.array(result, dtype=float)

    def people(ids):
        return {
            panel[cid].get("person_group")
            or panel[cid].get("bioguide_id")
            or panel[cid].get("D_fec_id")
            or cid
            for cid in ids
        }

    def independent_gain(ids, fit):
        names = ["intercept", "lean_10pp", "lean_squared"]
        if fit["trait"] != "incumbency":
            names += [
                k for k in ("D_incumbent", "R_incumbent") if len({panel[cid][k] for cid in ids}) > 1
            ]
        differences = []
        for state in sorted({panel[cid]["state"] for cid in ids}):
            test = [cid for cid in ids if panel[cid]["state"] == state]
            train = [
                cid
                for cid in ids
                if panel[cid]["state"] != state and not people([cid]) & people(test)
            ]
            kept = list(names)
            for name in reversed(names):
                if name not in {"D_incumbent", "R_incumbent"}:
                    continue
                others = [k for k in kept if k != name]
                relation = np.linalg.lstsq(
                    matrix(train, others, fit["trait"]),
                    matrix(train, [name], fit["trait"]),
                    rcond=None,
                )[0]
                if np.allclose(
                    matrix(train, others, fit["trait"]) @ relation,
                    matrix(train, [name], fit["trait"]),
                    atol=1e-10,
                    rtol=0,
                ):
                    np.testing.assert_allclose(
                        matrix(test, others, fit["trait"]) @ relation,
                        matrix(test, [name], fit["trait"]),
                        atol=1e-10,
                        rtol=0,
                    )
                    kept.remove(name)
            errors = []
            y_train = np.array([panel[cid]["descriptive_gap_share_pp"] for cid in train])
            y_test = np.array([panel[cid]["descriptive_gap_share_pp"] for cid in test])
            for terms in (kept, kept + fit["focal_terms"]):
                design = matrix(train, terms, fit["trait"])
                assert np.linalg.matrix_rank(design) == design.shape[1]
                assert np.linalg.cond(design) < 1e10
                assert len(train) > design.shape[1] + 3
                assert len({panel[cid]["state"] for cid in train}) >= 8
                coefficients = np.linalg.lstsq(design, y_train, rcond=None)[0]
                errors.append(y_test - matrix(test, terms, fit["trait"]) @ coefficients)
            differences.extend(np.abs(errors[0]) - np.abs(errors[1]))
        assert len(differences) == len(ids)
        return float(np.mean(differences))

    fits = read_rows(out / "fits.jsonl.gz")
    assert len(fits) == len({row["trait"] for row in fits}) == 15
    deletions = read_rows(out / "state-deletions.jsonl.gz")
    associations = prediction_checks = deletion_checks = full_checks = 0
    failures = []
    for fit in fits:
        if fit["status"] != "estimated":
            continue
        trait, ids = fit["trait"], fit["candidate_election_ids"]
        design = matrix(ids, fit["terms"], trait)
        outcome = np.array([panel[cid]["descriptive_gap_share_pp"] for cid in ids])
        beta = np.linalg.lstsq(design, outcome, rcond=None)[0]
        residual = outcome - design @ beta
        states = sorted({panel[cid]["state"] for cid in ids})
        scores = [
            design[[panel[cid]["state"] == state for cid in ids]].T
            @ residual[[panel[cid]["state"] == state for cid in ids]]
            for state in states
        ]
        bread = np.linalg.inv(design.T @ design)
        n, k = design.shape
        covariance = bread @ sum(np.outer(s, s) for s in scores) @ bread
        covariance *= len(states) / (len(states) - 1) * (n - 1) / (n - k)
        width = t.ppf(0.975, len(states) - 1) * np.sqrt(np.diag(covariance))
        for computed, stored in (
            (beta, fit["coefficients"]),
            (beta - width, fit["ci_low"]),
            (beta + width, fit["ci_high"]),
        ):
            np.testing.assert_allclose(computed, stored, atol=1e-8)
        q = len(fit["focal_terms"])
        statistic = beta[-q:] @ np.linalg.solve(covariance[-q:, -q:], beta[-q:]) / q
        assert abs(float(f.sf(statistic, q, len(states) - 1)) - fit["omnibus_pvalue"]) < 1e-8
        associations += 1
        for prefix in ("", "full-population-"):
            predictions = {
                r["candidate_election_id"]: r
                for r in read_rows(out / f"{prefix}predictions.jsonl.gz")
                if r["trait"] == trait
            }
            observed = set()
            for fold in read_rows(out / f"{prefix}folds.jsonl.gz"):
                if fold["trait"] != trait:
                    continue
                assert fold["training_only_preprocessing"]
                train, target = fold["training_ids"], fold["test_ids"]
                assert not {panel[cid]["state"] for cid in train} & {
                    panel[cid]["state"] for cid in target
                }
                assert not people(train) & people(target)
                supported = fold.get(
                    "supported_test_ids", target if fold["status"] == "estimated" else []
                )
                for relation in fold.get("nuisance_relations", []):
                    terms, removed = relation["retained_terms"], [relation["removed_term"]]
                    coefficients = np.linalg.lstsq(
                        matrix(train, terms, trait), matrix(train, removed, trait), rcond=None
                    )[0]
                    np.testing.assert_allclose(
                        matrix(train, terms, trait) @ coefficients,
                        matrix(train, removed, trait),
                        atol=1e-10,
                        rtol=0,
                    )
                    residuals = (
                        matrix(target, terms, trait) @ coefficients - matrix(target, removed, trait)
                    ).ravel()
                    assert all(
                        abs(value) <= 1e-10 if cid in supported else abs(value) > 1e-10
                        for cid, value in zip(target, residuals)
                    )
                if not prefix:
                    assert fold["status"] == "estimated"
                for cid in set(target) - set(supported):
                    assert cid not in predictions
                    failures.append({"trait": trait, "candidate_election_id": cid})
                if not supported:
                    continue
                for kind in ("baseline", "augmented"):
                    names = fold[f"{kind}_terms"]
                    x = matrix(train, names, trait)
                    assert np.linalg.matrix_rank(x) == x.shape[1]
                    assert np.linalg.cond(x) < 1e10
                    y = np.array([panel[cid]["descriptive_gap_share_pp"] for cid in train])
                    coef = np.linalg.lstsq(x, y, rcond=None)[0]
                    predicted = matrix(supported, names, trait) @ coef
                    for cid, value in zip(supported, predicted):
                        error = panel[cid]["descriptive_gap_share_pp"] - value
                        assert abs(error - predictions[cid][f"{kind}_error_share_pp"]) < 1e-8
                observed.update(supported)
            assert observed == set(predictions)
            if prefix:
                full_checks += len(observed)
                assert len(observed) == fit["full_population_prediction"]["paired_candidates"]
            else:
                prediction_checks += len(observed)
                gain = independent_gain(list(predictions), fit)
                vector = []
                for record in [r for r in deletions if r["trait"] == trait]:
                    assert record["complete"]
                    reduced = [
                        cid for cid in predictions if panel[cid]["state"] != record["deleted_state"]
                    ]
                    value = independent_gain(reduced, fit)
                    assert abs(value - record["MAE_gain_share_pp"]) < 1e-9
                    vector.append(value)
                    deletion_checks += 1
                vector = np.array(vector)
                width = t.ppf(0.975, len(vector) - 1) * np.sqrt(
                    (len(vector) - 1) / len(vector) * np.sum((vector - vector.mean()) ** 2)
                )
                np.testing.assert_allclose(
                    [gain, gain - width, gain + width],
                    [
                        fit["prediction"][name]
                        for name in ("MAE_gain_share_pp", "gain_ci_low", "gain_ci_high")
                    ],
                    atol=1e-9,
                )
    previous = 0
    for rank, fit in enumerate(sorted(fits, key=lambda row: row.get("omnibus_pvalue", 1))):
        previous = max(previous, min(1, (15 - rank) * fit.get("omnibus_pvalue", 1)))
        assert abs(previous - fit["holm_pvalue"]) < 1e-10
    assert failures == [
        {
            "trait": "religion",
            "candidate_election_id": "2026:house:IA:03:general:source_general:audit:0",
        }
    ]
    return {
        "independent_clustered_associations_checked": associations,
        "independent_matched_predictions_checked": prediction_checks,
        "independent_full_population_predictions_checked": full_checks,
        "independent_complete_outer_deletions_refitted": deletion_checks,
        "explicit_full_population_failures": failures,
        "holm_family_size": 15,
        "state_person_separation_and_full_rank": "passed",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    text = json.dumps(validate(), indent=2) + "\n"
    if arguments.output:
        arguments.output.write_text(text)
    print(text)
