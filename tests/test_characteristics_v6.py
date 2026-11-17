import copy
import hashlib
import json
from pathlib import Path

import pytest

from which_candidate.characteristics_research import reviewed_claims
from which_candidate.characteristics_v2 import verify_frozen
from which_candidate.characteristics_v6 import BRIDGE, held_review, new_rows
from which_candidate.characteristics_v6_acquisition import BASELINE, freeze
from which_candidate.storage import json_bytes, read_rows

ROOT = Path(__file__).resolve().parents[1]


def test_v6_preserves_v5_and_all_historical_claims():
    baseline = freeze(ROOT)
    verify_frozen(ROOT, BASELINE)
    inputs = read_rows(ROOT / "results/house/source-inputs.jsonl.gz")[0]
    current = {
        r["observation_id"]: hashlib.sha256(json_bytes(r)).hexdigest()
        for r in inputs["reviewed_characteristic_observations"]
    }
    assert len(baseline["historical_reviewed_observations"]) == 823
    assert baseline["historical_reviewed_observations"].items() <= current.items()
    assert any(
        p.startswith("results/house-characteristics-v5/") for p in baseline["protected_sha256"]
    )


def test_v6_keeps_timing_identity_and_uncoded_reference_boundaries():
    rows, _, panel, previous, observations, conflicts, held = new_rows(ROOT)
    by_key = {(r["candidate_id"], r["trait"]): r for r in rows}
    old = {(r["candidate_id"], r["trait"]): r for r in previous}
    assert len(observations) == 36 and not conflicts
    assert by_key["220195", "age"]["analysis_value"] == 43
    assert by_key["220195", "profession"]["analysis_value"] == "education"
    assert by_key["220135", "education"]["analysis_value"] == "bachelors"
    assert by_key["220751", "education"]["analysis_value"] == "masters"
    assert by_key["220397", "education"]["factual_qualified"]
    assert not by_key["220397", "education"]["analysis_eligible"]
    for cid in ("220035", "219764"):
        assert not by_key[cid, "profession"]["analysis_eligible"]
    for cid in ("219846", "221177"):
        assert by_key[cid, "religion"]["analysis_value"] == "other_christian"
    for cid in ("220135", "220751"):
        assert by_key[cid, "race"]["factual_qualified"]
        assert not by_key[cid, "race"]["analysis_eligible"]
        assert (
            by_key[cid, "ethnicity"]["factual_qualified"]
            == old[cid, "ethnicity"]["factual_qualified"]
        )
        assert not by_key[cid, "ethnicity"]["analysis_eligible"]
    assert by_key["220135", "education"]["district"] == "22"
    assert [(r["candidate_id"], r["value"]) for r in held] == [("220397", False)]
    outcome = next(
        r for r in panel if r["contest_id"] == by_key["220397", "incumbency"]["contest_id"]
    )
    assert outcome["D_incumbent"] is False
    for row in rows:
        before = old[row["candidate_id"], row["trait"]]
        for field in ("candidate_id", "contest_id", "name", "state", "district", "party"):
            assert row[field] == before[field]
        if row["trait"] in {"prior_elected_office", "other_government"}:
            assert not row["analysis_eligible"]


def test_drew_bridge_requires_explicit_voice_and_unique_fec_person_contest():
    _, candidates, panel, previous, _, _, _ = new_rows(ROOT)
    inputs = read_rows(ROOT / "results/house/source-inputs.jsonl.gz")[0]
    assert any(
        r["candidate_id"] == "220397" for r in held_review(candidates, previous, panel, inputs)
    )
    missing_voice = copy.deepcopy(inputs)
    for o in missing_voice["reviewed_characteristic_observations"]:
        if o["source_id"] == BRIDGE:
            o.pop("identity_support")
    assert not any(
        r["candidate_id"] == "220397"
        for r in held_review(candidates, previous, panel, missing_voice)
    )
    ambiguous = copy.deepcopy(inputs)
    record = next(
        r
        for r in ambiguous["fec"]
        if r["name"] == "WILLIAMS, JOHN ANDREW" and r["election_year"] == 2026
    )
    ambiguous["fec"].append({**record, "fec_id": "ambiguous-second-id"})
    assert not any(
        r["candidate_id"] == "220397" for r in held_review(candidates, previous, panel, ambiguous)
    )


def test_literal_validator_rejects_broadcast_alias_not_present_in_subject_scope():
    registry = json.loads((ROOT / "data/house-characteristics-v6-acquisitions.json").read_text())
    source = next(s for s in registry["sources"] if s["id"] == BRIDGE)
    receipt = next(d for d in registry["documents"] if d["id"] == source["document_id"])
    text = " ".join([source["identity_fragment"], *(c["fragment"] for c in source["claims"])])
    with pytest.raises(ValueError, match="identity link"):
        reviewed_claims(source, receipt, text)
    text += " " + " ".join(source["claims"][0]["identity_support"])
    assert len(reviewed_claims(source, receipt, text)) == 2


def test_new_source_hashes_and_urls_are_not_repeated_historical_evidence():
    registry = json.loads((ROOT / "data/house-characteristics-v6-acquisitions.json").read_text())
    sources = json.loads((ROOT / "data/house-characteristics-research.json").read_text())["sources"]
    receipts = json.loads((ROOT / "data/house-characteristics-receipts.json").read_text())[
        "sources"
    ]
    assert not {s["url"] for s in registry["sources"]} & {
        s["url"] for s in sources if not s["id"].startswith("v6-")
    }
    assert not {s["sha256"] for s in registry["documents"]} & {
        s.get("sha256") for s in receipts if not s["id"].startswith("v6-")
    }
    assert registry["new_document_hashes"] == 8
    assert not any("convergence-" in s["id"] or "rns-" in s["id"] for s in registry["sources"])
