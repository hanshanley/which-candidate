"""Independently reconstruct V7 OLS, clustered uncertainty, folds and outer deletions."""

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
    out = ROOT / "results/house-characteristics-v7"
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
            test_people = people(test)
            train = [
                cid
                for cid in ids
                if panel[cid]["state"] != state and not people([cid]) & test_people
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
    folds = read_rows(out / "folds.jsonl.gz")
    predictions = {
        (r["trait"], r["candidate_election_id"]): r for r in read_rows(out / "predictions.jsonl.gz")
    }
    deletions = read_rows(out / "state-deletions.jsonl.gz")
    association_checks = prediction_checks = deletion_checks = 0
    for fit in fits:
        if fit["status"] != "estimated":
            continue
        trait, ids = fit["trait"], fit["candidate_election_ids"]
        design = matrix(ids, fit["terms"], trait)
        outcome = np.array([panel[cid]["descriptive_gap_share_pp"] for cid in ids])
        beta = np.linalg.solve(design.T @ design, design.T @ outcome)
        residual = outcome - design @ beta
        states = sorted({panel[cid]["state"] for cid in ids})
        scores = [
            design[[panel[cid]["state"] == state for cid in ids]].T
            @ residual[[panel[cid]["state"] == state for cid in ids]]
            for state in states
        ]
        bread = np.linalg.inv(design.T @ design)
        covariance = bread @ sum(np.outer(s, s) for s in scores) @ bread
        n, k = design.shape
        covariance *= len(states) / (len(states) - 1) * (n - 1) / (n - k)
        np.testing.assert_allclose(beta, fit["coefficients"], atol=1e-8)
        np.testing.assert_allclose(
            beta - t.ppf(0.975, len(states) - 1) * np.sqrt(np.diag(covariance)),
            fit["ci_low"],
            atol=1e-8,
        )
        np.testing.assert_allclose(
            beta + t.ppf(0.975, len(states) - 1) * np.sqrt(np.diag(covariance)),
            fit["ci_high"],
            atol=1e-8,
        )
        q = len(fit["focal_terms"])
        statistic = beta[-q:] @ np.linalg.solve(covariance[-q:, -q:], beta[-q:]) / q
        assert abs(float(f.sf(statistic, q, len(states) - 1)) - fit["omnibus_pvalue"]) < 1e-8
        association_checks += 1
        for fold in [r for r in folds if r["trait"] == trait]:
            assert fold["status"] == "estimated" and fold["training_only_preprocessing"]
            train, test = fold["training_ids"], fold["test_ids"]
            assert not {panel[cid]["state"] for cid in train} & {
                panel[cid]["state"] for cid in test
            }
            assert not people(train) & people(test)
            for kind in ("baseline", "augmented"):
                names = fold[f"{kind}_terms"]
                x = matrix(train, names, trait)
                y = np.array([panel[cid]["descriptive_gap_share_pp"] for cid in train])
                coef = np.linalg.solve(x.T @ x, x.T @ y)
                predicted = matrix(test, names, trait) @ coef
                for cid, value in zip(test, predicted):
                    actual_error = panel[cid]["descriptive_gap_share_pp"] - value
                    assert (
                        abs(actual_error - predictions[(trait, cid)][f"{kind}_error_share_pp"])
                        < 1e-8
                    )
            prediction_checks += len(test)
        paired_ids = [cid for block, cid in predictions if block == trait]
        gain = independent_gain(paired_ids, fit)
        delete = [r for r in deletions if r["trait"] == trait]
        actual_deletions = []
        for record in delete:
            assert record["complete"]
            reduced = [cid for cid in paired_ids if panel[cid]["state"] != record["deleted_state"]]
            value = independent_gain(reduced, fit)
            assert abs(value - record["MAE_gain_share_pp"]) < 1e-9
            actual_deletions.append(value)
            deletion_checks += 1
        vector = np.array(actual_deletions)
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
    return {
        "independent_clustered_associations_checked": association_checks,
        "independent_matched_predictions_checked": prediction_checks,
        "independent_complete_outer_deletions_refitted": deletion_checks,
        "holm_family_size": 15,
        "state_person_separation_and_full_rank": "passed",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    result = validate()
    text = json.dumps(result, indent=2) + "\n"
    if arguments.output:
        arguments.output.write_text(text)
    print(text)
