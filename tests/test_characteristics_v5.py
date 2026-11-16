import csv
import hashlib
import json
from pathlib import Path

import pytest

from which_candidate.characteristics_research import reviewed_claims
from which_candidate.characteristics_v2 import verify_frozen
from which_candidate.characteristics_v5 import new_rows
from which_candidate.characteristics_v5_acquisition import BASELINE, QUEUE, freeze
from which_candidate.house_study import attach_research_history
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


def test_v5_new_sources_preserve_timing_intervals_and_unresolved_aliases():
    rows, _, panel, previous, observations, conflicts, held = new_rows(ROOT)
    by_key = {(r["candidate_id"], r["trait"]): r for r in rows}
    old = {(r["candidate_id"], r["trait"]): r for r in previous}
    assert len(observations) == 27 and not conflicts and not held
    assert by_key["220281", "age"]["analysis_value"] == 49
    assert by_key["220484", "age"]["analysis_value"] == 32
    assert by_key["221188", "age"]["analysis_value"] == 31
    interval = by_key["220715", "age"]
    assert interval["uncertainty"]["age_years_interval"] == [47, 48]
    assert not interval["analysis_eligible"]
    religion = by_key["221188", "religion"]
    assert religion["factual_qualified"] and not religion["analysis_eligible"]
    for cid in ("220484", "220715"):
        assert not by_key[cid, "profession"]["analysis_eligible"]
    for cid in ("219729", "220538", "220596", "221215", "221251"):
        assert by_key[cid, "incumbency"]["analysis_value"] is False
        outcome = next(
            r for r in panel if r["contest_id"] == by_key[cid, "incumbency"]["contest_id"]
        )
        assert outcome["D_incumbent"] is False
    for cid in ("220397", "221041", "221075"):
        assert not by_key[cid, "incumbency"]["analysis_eligible"]
    for r in rows:
        before = old[r["candidate_id"], r["trait"]]
        for field in ("candidate_id", "contest_id", "name", "state", "district", "party"):
            assert r[field] == before[field]
        if r["trait"] in {"gender", "race", "ethnicity"}:
            assert r["analysis_value"] == before["analysis_value"]
        if r["trait"] in {"prior_elected_office", "other_government"}:
            assert not r["analysis_eligible"]


def test_identity_bridge_requires_literal_authorized_committee_not_nickname_assumption():
    registry = json.loads((ROOT / "data/house-characteristics-v5-acquisitions.json").read_text())
    source = next(s for s in registry["sources"] if "fec-parsi-" in s["id"])
    receipt = next(d for d in registry["documents"] if d["id"] == source["document_id"])
    fragments = [source["identity_fragment"], source["claims"][0]["fragment"]]
    with pytest.raises(ValueError, match="identity link"):
        reviewed_claims(source, receipt, " ".join(fragments))
    fragments.extend(source["claims"][0]["identity_support"])
    assert reviewed_claims(source, receipt, " ".join(fragments))[0]["value"] is False


def test_v5_additions_do_not_rewrite_frozen_research_dispositions():
    profiles = read_rows(ROOT / "results/house-study/candidate-profiles.jsonl.gz")
    assert any(
        str(o.get("evidence", {}).get("id", "")).startswith("v5-")
        for p in profiles
        for o in p["acquired_background_observations"]
        if isinstance(o.get("evidence"), dict)
    )
    research, repair = attach_research_history(ROOT, profiles)
    assert research["historical_milestone_not_new_acquisition"]
    assert repair["historical_milestone_not_new_acquisition"]
