import csv
import hashlib
import json
from pathlib import Path

from which_candidate.characteristics_v4_acquisition import BASELINE, QUEUE, freeze
from which_candidate.storage import fingerprint, json_bytes, read_rows

ROOT = Path(__file__).resolve().parents[1]


def test_v4_queue_retains_every_democrat_trait_and_incumbency_stratum():
    baseline = freeze(ROOT)
    with (ROOT / QUEUE).open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == baseline["trait_cells"] == 6735
    assert len({r["candidate_id"] for r in rows}) == 449
    assert baseline["eligible_democrats"] == 405
    assert baseline["incumbency_groups"] == {
        "incumbent": 183,
        "nonincumbent": 242,
        "unknown_incumbency": 24,
    }
    assert len({(r["candidate_id"], r["trait"]) for r in rows}) == len(rows)
    assert sum(r["opponent_incumbency_unresolved"] == "True" for r in rows) > 0


def test_v4_freeze_preserves_v3_bytes_identities_and_all_705_prior_claims():
    baseline = json.loads((ROOT / BASELINE).read_text())
    for path, digest in baseline["protected_sha256"].items():
        assert fingerprint(ROOT / path)["sha256"] == digest
    inputs = read_rows(ROOT / "results/house/source-inputs.jsonl.gz")[0]
    claims = {r["observation_id"]: r for r in inputs["reviewed_characteristic_observations"]}
    assert len(baseline["historical_reviewed_observations"]) == 705
    for key, digest in baseline["historical_reviewed_observations"].items():
        assert hashlib.sha256(json_bytes(claims[key])).hexdigest() == digest
    candidates = read_rows(ROOT / "results/house/candidates.jsonl.gz")
    identities = [
        {k: c[k] for k in ("candidate_id", "contest_id", "name", "state", "district", "party")}
        for c in candidates
    ]
    assert (
        hashlib.sha256(json_bytes(identities)).hexdigest() == baseline["candidate_identity_sha256"]
    )
