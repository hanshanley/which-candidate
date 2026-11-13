"""Independent numerical audit of corrected outputs; no network or production fit helpers."""

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np

from which_candidate.storage import fingerprint, read_rows


def design(rows, names, variant):
    values = []
    for row in rows:
        pres = row["presidential_D_two_party_share_pct"]
        if variant == "alternate_presidential_same_sample":
            pres = row["previous_presidential_share"]
        lean = (pres - 50) / 10
        columns = {
            "intercept": lambda: 1,
            "lean_10pp": lambda: lean,
            "lean_squared": lambda: lean**2,
            "D_incumbent": lambda: int(row["D_incumbent"]),
            "R_incumbent": lambda: int(row["R_incumbent"]),
            "rightward_01": lambda: row["nokken_poole_dim1"] / 0.1,
            "defection_1pp": lambda: (
                100
                * (
                    1
                    - row[
                        "lagged_party_unity_score"
                        if variant == "prior_completed_congress"
                        else "party_unity_score"
                    ]
                )
            ),
            "age_10years": lambda: (row["age_years"] - 55) / 10,
            "tenure_10years": lambda: row["chamber_tenure_years"] / 10,
            "source_F": lambda: int(row["source_recorded_gender"] == "F"),
            "same_map_presidential_swing_10pp": lambda: (
                (pres - row["previous_presidential_share"]) / 10
            ),
        }
        values.append(
            [
                int(row["state"] == name.removeprefix("state_"))
                if name.startswith("state_")
                else columns[name]()
                for name in names
            ]
        )
    return np.asarray(values, dtype=float).reshape((len(rows), len(names)))


def audit(inputs, analysis):
    for folder in (inputs, analysis):
        for name, receipt in json.loads((folder / "manifest.json").read_text()).items():
            assert fingerprint(folder / name) == receipt, name
    panel = read_rows(analysis / "candidate-queries.jsonl.gz")
    by_id = {r["D_candidate_election_id"]: r for r in panel}
    current = [r for r in panel if r["year"] == 2026]
    assert Counter(r["chamber"] for r in current) == {"house": 435, "senate": 35}
    assert len({r["native_evidence"]["source"]["url"] for r in current}) == 470
    native_candidates = 0
    for row in current:
        candidates = row["native_evidence"]["native"]["candidates"]
        native_candidates += len(candidates)
        assert row["all_candidate_votes"] == sum(c["votes"] for c in candidates)
        assert sum(row[f"{p}_votes"] for p in ("D", "R", "O")) == row["all_candidate_votes"]
        assert row["v2_counts"]
        if row["eligible"]:
            assert row["other_share_pct"] < 10
            assert row["state"] not in ("AK", "ME")
            assert row["descriptive_gap_share_pp"] == (
                100 * row["D_votes"] / (row["D_votes"] + row["R_votes"])
                - row["presidential_D_two_party_share_pct"]
            )
    for name, party, expected in (
        ("Mike McGuire", "D", False),
        ("Lou Correa", "D", True),
        ("Gabriel Amo", "D", True),
        ("Greg Steube", "R", True),
        ("Nick Langworthy", "R", True),
    ):
        matches = [r for r in current if r.get(f"{party}_name") == name]
        assert len(matches) == 1, name
        assert matches[0][f"{party}_incumbent"] is expected, name
    fits_checked, deletions_checked = 0, 0
    for fit in read_rows(analysis / "trait-fits.jsonl.gz"):
        if fit["status"] != "estimated":
            continue
        rows = [by_id[i] for i in fit["candidate_election_ids"]]
        x = design(rows, fit["terms"], fit["variant"])
        y = np.array(
            [
                r["D_two_party_share_pct"]
                - r[
                    "previous_presidential_share"
                    if fit["variant"] == "alternate_presidential_same_sample"
                    else "presidential_D_two_party_share_pct"
                ]
                for r in rows
            ]
        )
        beta = np.linalg.lstsq(x, y, rcond=None)[0]
        np.testing.assert_allclose(beta, fit["coefficients"], atol=1e-8, rtol=1e-8)
        states = np.array([r["state"] for r in rows])
        errors = y - x @ beta
        scores = [x[states == s].T @ errors[states == s] for s in sorted(set(states))]
        meat = sum(np.outer(s, s) for s in scores)
        bread = np.linalg.pinv(x.T @ x)
        n, k = x.shape
        g = len(scores)
        covariance = bread @ meat @ bread * g / (g - 1) * (n - 1) / (n - k)
        np.testing.assert_allclose(covariance, fit["covariance"], atol=1e-8, rtol=1e-7)
        focal = fit["terms"].index(fit["focal_term"])
        for deletion in fit["cluster_deletions"]:
            if deletion["estimate_share_pp"] is None:
                continue
            keep = states != deletion["omitted_state"]
            expected = np.linalg.lstsq(x[keep], y[keep], rcond=None)[0][focal]
            np.testing.assert_allclose(expected, deletion["estimate_share_pp"], atol=1e-8)
            deletions_checked += 1
        assert fit["estimate_margin_pp"] == 2 * fit["estimate_share_pp"]
        fits_checked += 1
    residuals = read_rows(analysis / "structural-residuals.jsonl.gz")
    betas = {}
    baseline_terms = ["intercept", "lean_10pp", "lean_squared", "D_incumbent", "R_incumbent"]
    for record in residuals:
        target = by_id[record["candidate_election_id"]]
        train = [by_id[i] for i in record["training_ids"]]
        assert all(r["state"] != target["state"] and r["year"] == target["year"] for r in train)
        assert target["person_group"] not in {r["person_group"] for r in train}
        key = record["year"], record["variant"], record["state"]
        terms = baseline_terms + (
            ["same_map_presidential_swing_10pp"] if record["variant"] == "same_map_swing" else []
        )
        if key not in betas:
            x = design(train, terms, record["variant"])
            y = np.array([r["descriptive_gap_share_pp"] for r in train])
            betas[key] = np.linalg.lstsq(x, y, rcond=None)[0]
        expected = (
            target["descriptive_gap_share_pp"]
            - design([target], terms, record["variant"])[0] @ betas[key]
        )
        np.testing.assert_allclose(expected, record["residual_share_pp"], atol=1e-8)
        assert record["residual_margin_pp"] == 2 * record["residual_share_pp"]
    pipeline_checked = 0
    for fit in read_rows(analysis / "moderation-fits.jsonl.gz"):
        if (fit["year"], fit["comparison"], fit["method"]) != (
            2026,
            "blue_dog_vs_cpc",
            "cross_fitted_structural",
        ):
            continue
        records = [r for r in residuals if r["year"] == 2026 and r["variant"] == fit["variant"]]
        sample = [by_id[r["candidate_election_id"]] for r in records]
        group_ids = set(fit["candidate_election_ids"])
        terms = baseline_terms + (
            ["same_map_presidential_swing_10pp"] if fit["variant"] == "same_map_swing" else []
        )
        means = [
            np.mean(
                [
                    r["residual_share_pp"]
                    for r in records
                    if r["candidate_election_id"] in group_ids
                    and by_id[r["candidate_election_id"]]["blue_dog"] is blue
                ]
            )
            for blue in (False, True)
        ]
        np.testing.assert_allclose(means[1] - means[0], fit["estimate_share_pp"], atol=1e-8)
        x = design(sample, terms, fit["variant"])
        y = np.array([r["descriptive_gap_share_pp"] for r in sample])
        states = np.array([r["state"] for r in sample])
        for deletion in fit["benchmark_pipeline_deletions"]:
            omitted = deletion["omitted_state"]
            values = {}
            for state in sorted(set(states) - {omitted}):
                train = (states != state) & (states != omitted)
                beta = np.linalg.lstsq(x[train], y[train], rcond=None)[0]
                for i in np.flatnonzero(states == state):
                    if sample[i]["D_candidate_election_id"] in group_ids:
                        values[i] = y[i] - x[i] @ beta
            means = [
                np.mean([v for i, v in values.items() if sample[i]["blue_dog"] is blue])
                for blue in (False, True)
            ]
            np.testing.assert_allclose(
                means[1] - means[0], deletion["estimate_share_pp"], atol=1e-8
            )
            pipeline_checked += 1
    folds = read_rows(analysis / "folds.jsonl.gz")
    for fold in folds:
        train = [by_id[i] for i in fold["train_ids"]]
        test = [by_id[i] for i in fold["test_ids"]]
        assert not {r["state"] for r in train} & {r["state"] for r in test}
        assert not {r["person_group"] for r in train} & {r["person_group"] for r in test}
        if "chronological" in fold["fold_id"]:
            assert max(r["year"] for r in train) < min(r["year"] for r in test)
    return {
        "retained_2026": len(current),
        "native_candidate_rows": native_candidates,
        "independent_trait_fits": fits_checked,
        "independent_trait_deletions": deletions_checked,
        "independent_structural_residuals": len(residuals),
        "independent_2026_caucus_pipeline_deletions": pipeline_checked,
        "folds_without_state_or_person_overlap": len(folds),
        "incumbency_corrections_verified": 5,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, default=Path("results/2026-v3/inputs"))
    parser.add_argument("--analysis", type=Path, default=Path("results/2026-v3/analysis"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    value = json.dumps(audit(args.inputs, args.analysis), indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(value)
    print(value)
