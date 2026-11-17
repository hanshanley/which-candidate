"""Training-only nuisance reduction with candidate-specific estimability."""

import numpy as np

from . import house_characteristics as v1
from .characteristics_v2 import person_key


def paired(rows, trait, levels):
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
        unsupported = set()
        relations = []
        for j in reversed(range(len(names))):
            if names[j] not in {"D_incumbent", "R_incumbent"} or not train:
                continue
            others = [k for k in keep if k != j]
            relation = np.linalg.lstsq(base[np.ix_(train, others)], base[train, j], rcond=None)[0]
            if np.allclose(
                base[np.ix_(train, others)] @ relation, base[train, j], atol=1e-10, rtol=0
            ):
                residuals = base[np.ix_(test, others)] @ relation - base[test, j]
                unsupported.update(
                    i for i, residual in zip(test, residuals) if abs(residual) > 1e-10
                )
                relations.append(
                    {
                        "removed_term": names[j],
                        "retained_terms": [names[k] for k in others],
                        "training_relation": relation.tolist(),
                    }
                )
                keep.remove(j)
        designs = (base[:, keep], augmented[:, [*keep, *range(base.shape[1], augmented.shape[1])]])
        ranks = [int(np.linalg.matrix_rank(x[train])) if train else 0 for x in designs]
        conditions = [
            float(np.linalg.cond(x[train])) if train and ranks[i] == x.shape[1] else None
            for i, x in enumerate(designs)
        ]
        reason = None
        if len(train) <= designs[1].shape[1] + 3 or len({rows[i]["state"] for i in train}) < 8:
            reason = "insufficient_training_support"
        if any(rank != x.shape[1] for rank, x in zip(ranks, designs)):
            reason = reason or "rank_deficient_training_design"
        if any(c is None or c >= 1e10 for c in conditions):
            reason = reason or "ill_conditioned_training_design"
        supported = [] if reason else [i for i in test if i not in unsupported]
        failures = [
            {
                "candidate_election_id": rows[i]["D_candidate_election_id"],
                "reason": reason or "unseen_test_incumbency_stratum",
            }
            for i in test
            if i not in supported
        ]
        folds.append(
            {
                "trait": trait,
                "held_out_state": state,
                "status": "estimated"
                if not failures
                else "partially_estimated"
                if supported
                else "failed",
                "failure_reason": reason
                or ("unseen_test_incumbency_stratum" if failures else None),
                "training_ids": [rows[i]["D_candidate_election_id"] for i in train],
                "test_ids": [rows[i]["D_candidate_election_id"] for i in test],
                "training_people": sorted({person_key(rows[i]) for i in train}),
                "test_people": sorted(people),
                "baseline_terms": [names[i] for i in keep],
                "augmented_terms": [*[names[i] for i in keep], *focal],
                "training_ranks": ranks,
                "training_conditions": conditions,
                "training_only_preprocessing": True,
                "supported_test_ids": [rows[i]["D_candidate_election_id"] for i in supported],
                "prediction_failures": failures,
                "nuisance_relations": relations,
            }
        )
        if not supported:
            continue
        betas = [np.linalg.lstsq(x[train], y[train], rcond=None)[0] for x in designs]
        for i in supported:
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
