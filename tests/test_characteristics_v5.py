import csv
import hashlib
import json
from pathlib import Path

from which_candidate.characteristics_v2 import verify_frozen
from which_candidate.characteristics_v5_acquisition import BASELINE, QUEUE, freeze
from which_candidate.storage import json_bytes, read_rows

ROOT = Path(__file__).resolve().parents[1]


def test_v5_freeze_preserves_all_prior_outputs_claims_and_complete_queue():
    baseline = freeze(ROOT)
    verify_frozen(ROOT, BASELINE)
    assert baseline["democrats"] == 449
    assert baseline["eligible_democrats"] == 405
    assert any(
        p.startswith("results/house-characteristics-v4/") for p in baseline["protected_sha256"]
    )
    inputs = read_rows(ROOT / "results/house/source-inputs.jsonl.gz")[0]
    current = {
        r["observation_id"]: hashlib.sha256(json_bytes(r)).hexdigest()
        for r in inputs["reviewed_characteristic_observations"]
    }
    assert len(baseline["historical_reviewed_observations"]) == 796
    assert baseline["historical_reviewed_observations"].items() <= current.items()
    with (ROOT / QUEUE).open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == len({(r["candidate_id"], r["trait"]) for r in rows}) == 6735
    assert len({r["candidate_id"] for r in rows}) == 449
    assert sum(r["trait"] == "incumbency" and r["analysis_eligible"] == "False" for r in rows) == 17
    assert freeze(ROOT) == json.loads((ROOT / BASELINE).read_text())
