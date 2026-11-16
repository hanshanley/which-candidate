import csv
import hashlib
import json
from collections import Counter
from copy import deepcopy
from datetime import date
from pathlib import Path

import numpy as np
import pytest

from which_candidate import characteristics_research as research
from which_candidate import house_characteristics as traits
from which_candidate.house_backgrounds import validate_characteristics
from which_candidate.storage import fingerprint, json_bytes, read_rows, write_json, write_rows

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("education", "expected", "degrees"),
    [
        ("J.D. and M.B.A., University, 2001", "doctoral_or_professional", {"J.D.", "M.B.A."}),
        ("A.B., College; M.Phil., University", "masters", {"A.B.", "M.Phil."}),
        ("attended University; honorary Ph.D., College", None, set()),
        (
            "B.S.N., University; M.S.N., College; M.P.H., School",
            "masters",
            {"B.S.N.", "M.S.N.", "M.P.H."},
        ),
    ],
)
def test_reviewed_credentials_preserve_completed_degree_boundaries(education, expected, degrees):
    result = traits.directory_codes({"fields": {"education": education}})
    assert result["education"] == expected
    assert {r["degree"] for r in result["credentials"]} == degrees


def test_government_internship_is_not_legal_practice():
    assert (
        traits.directory_codes(
            {"fields": {"professional_history": "intern, Office of the Attorney General"}}
        )["profession"]
        is None
    )


def test_birth_year_only_remains_a_bounded_interval():
    assert traits.birth_year_interval("1982") == [43, 44]
    assert traits.birth_year_interval("1977/1978") == [47, 49]
    assert traits.birth_year_interval("circa 1982") is None
    assert traits.birth_year_interval("2027") is None


def research_fixture(root):
    (root / "results/house").mkdir(parents=True)
    (root / "data").mkdir()
    source = {
        "id": "test-biography",
        "candidate_id": "123",
        "contest_id": "2026:AA:01",
        "name": "Example Candidate",
        "state": "AA",
        "district": "01",
        "party": "Democratic",
        "url": "https://example.test/biography",
        "kind": "official_biography",
        "publication_date": "2025-01-01",
        "identity_qualification": "Exact contest identity.",
        "claims": [
            {
                "trait": "age",
                "value": "1980-01-02",
                "fragment": "born in 1980",
                "qualification": "Explicit birthday.",
            }
        ],
    }
    receipt = {
        "id": source["id"],
        "url": source["url"],
        "sha256": "a" * 64,
        "bytes": 20,
        "retrieved_at": "2026-11-16T00:00:00Z",
        "status": "reviewed",
    }
    write_rows(root / "results/house/candidates.jsonl.gz", [source])
    write_json(root / "data/house-characteristics-research.json", {"sources": [source]})
    write_json(root / "data/house-characteristics-receipts.json", {"sources": [receipt]})
    write_json(root / "data/candidate-source-leads.json", [])
    return source, receipt


def test_absent_raw_cache_requires_exact_normalized_claims(tmp_path, monkeypatch):
    source, receipt = research_fixture(tmp_path)
    observations = research.reviewed_claims(source, receipt)
    write_rows(
        tmp_path / "results/house/source-inputs.jsonl.gz",
        [{"reviewed_characteristic_observations": observations}],
    )
    monkeypatch.setattr(research, "build", lambda root, inputs: inputs)
    monkeypatch.setattr(
        research, "_fetch", lambda url: pytest.fail("Offline validation attempted network")
    )
    assert research.ingest(tmp_path, offline=True)["normalized_claims"] == 1
    source["claims"][0]["fragment"] = "different statement with identical claim count"
    write_json(tmp_path / "data/house-characteristics-research.json", {"sources": [source]})
    with pytest.raises(ValueError, match="Changed or missing normalized"):
        research.ingest(tmp_path, offline=True)


def test_source_fragment_validation_is_atomic(tmp_path, monkeypatch):
    source, receipt = research_fixture(tmp_path)
    source["claims"].append({**source["claims"][0], "fragment": "not in this document"})
    write_json(tmp_path / "data/house-characteristics-research.json", {"sources": [source]})
    cache = tmp_path / "data/raw/house-characteristics-v1/test-biography"
    cache.parent.mkdir(parents=True)
    cache.write_text("<p>born in 1980</p>")
    receipt.update(fingerprint(cache))
    write_json(tmp_path / "data/house-characteristics-receipts.json", {"sources": [receipt]})
    write_rows(tmp_path / "results/house/source-inputs.jsonl.gz", [{}])
    captured = []
    monkeypatch.setattr(research, "build", lambda root, inputs: captured.append(inputs))
    result = research.ingest(tmp_path, offline=True)
    assert result["normalized_claims"] == 0
    assert captured[0]["reviewed_characteristic_observations"] == []
    assert result["receipts"][0]["status"] == "failed_attempt_not_evidence"


def test_normalized_ingestion_rejects_identity_changes_and_analytical_promotion(tmp_path):
    source, receipt = research_fixture(tmp_path)
    observation = research.reviewed_claims(source, receipt)[0]
    validate_characteristics([observation], [source])
    for field, value in [("district", "02"), ("model_ready", True), ("fragment", "")]:
        changed = deepcopy(observation)
        changed[field] = value
        with pytest.raises(ValueError):
            validate_characteristics([changed], [source])
    with pytest.raises(ValueError, match="Duplicate"):
        validate_characteristics([observation, observation], [source])


def test_house_service_unions_intervals_excludes_breaks_and_future_service():
    periods = [
        {"type": "rep", "start": "2020-01-01", "end": "2022-01-01"},
        {"type": "rep", "start": "2021-01-01", "end": "2023-01-01"},
        {"type": "rep", "start": "2025-01-01", "end": "2028-01-01"},
        {"type": "sen", "start": "2010-01-01", "end": "2020-01-01"},
        {"type": "rep", "start": "2027-01-01", "end": "2029-01-01"},
    ]
    days = (date(2023, 1, 1) - date(2020, 1, 1)).days
    days += (traits.CUTOFF - date(2025, 1, 1)).days
    assert traits.service_years(periods) == pytest.approx(days / 365.2425)


def test_paired_prediction_holds_state_and_repeated_person_out_together():
    rows = []
    for s in range(12):
        for j in range(6):
            lean = 30 + 3 * s + 0.7 * j
            rows.append(
                {
                    "state": str(s),
                    "contest_id": f"{s}:{j}",
                    "D_candidate_election_id": f"{s}:{j}",
                    "D_name": f"Candidate {s}:{j}",
                    "person_group": "repeated" if s < 2 and j == 0 else f"{s}:{j}",
                    "D_incumbent": j % 2 == 0,
                    "R_incumbent": j % 3 == 0,
                    "presidential_D_two_party_share_pct": lean,
                    "descriptive_gap_share_pp": 2 + np.sin(s + j),
                    "_value": 25 + s + 3 * j,
                }
            )
    predictions, folds = traits.paired(rows, "age", None)
    assert len(predictions) == len(rows)
    for fold in folds:
        assert not set(fold["training_people"]) & set(fold["test_people"])
        assert not set(fold["training_ids"]) & set(fold["test_ids"])
        assert all(not x.startswith(fold["held_out_state"] + ":") for x in fold["training_ids"])


def test_persisted_successor_does_not_infer_negative_identities_or_service():
    path = ROOT / traits.OUT / "candidate-traits.jsonl.gz"
    if not path.exists():
        pytest.skip("Successor not generated yet")
    rows = read_rows(path)
    assert len(rows) == 1284 * 15
    assert len({(r["contest_id"], r["candidate_id"], r["trait"]) for r in rows}) == len(rows)
    for r in rows:
        assert not r["prospective_model_eligible"]
        if r["trait"] in {"race", "ethnicity"}:
            assert not r["field_eligible"] and r["value"] is None
        if r["trait"] == "military":
            assert r["value"] is None or r["value"] is True
        if r["status"] in {"unknown", "uncertain", "inapplicable"}:
            assert not r["field_eligible"]
    fits = read_rows(ROOT / traits.OUT / "fits.jsonl.gz")
    assert len(fits) == 15
    assert all(r["primary_family_size"] == 15 for r in fits)
    unsupported = {r["trait"] for r in fits if r["status"] != "estimated"}
    assert {
        "race",
        "ethnicity",
        "military",
        "prior_elected_office",
        "other_government",
    } <= unsupported
    summary = json.loads((ROOT / traits.OUT / "summary.json").read_text())
    assert summary["candidate_records"] == 1284 and summary["democrats"] == 449


def test_incremental_research_preserves_every_historical_collection_and_observation():
    baseline = json.loads((ROOT / "data/house-characteristics-baseline.json").read_text())
    inputs = read_rows(ROOT / "results/house/source-inputs.jsonl.gz")[0]
    for collection, expected in baseline["preserved_normalized_collection_sha256"].items():
        assert hashlib.sha256(json_bytes(inputs[collection])).hexdigest() == expected
    with (ROOT / "results/house/background-observations.csv").open() as stream:
        rows = [
            json.dumps(r, sort_keys=True)
            for r in csv.DictReader(stream)
            if not (
                isinstance(evidence := json.loads(r["evidence"]), dict)
                and evidence.get("id", "").startswith(("v3-", "v4-"))
            )
        ]
    new = Counter(baseline["new_observation_row_sha256"])
    historical = []
    for row in rows:
        digest = hashlib.sha256(row.encode()).hexdigest()
        if new[digest]:
            new[digest] -= 1
        else:
            historical.append(row)
    assert not +new
    assert len(historical) == baseline["baseline_observations"]
    assert (
        hashlib.sha256(json_bytes(sorted(historical))).hexdigest()
        == baseline["historical_observation_rows_sha256"]
    )


@pytest.mark.parametrize("trait", ["donor_ideology", "incumbency"])
def test_key_fits_match_independent_normal_equations_and_cluster_sandwich(trait):
    fits = read_rows(ROOT / traits.OUT / "fits.jsonl.gz")
    result = next(r for r in fits if r["trait"] == trait)
    observations = {
        r["contest_id"]: r
        for r in read_rows(ROOT / traits.OUT / "candidate-traits.jsonl.gz")
        if r["trait"] == trait and r["performance_eligible"]
    }
    ids = set(result["candidate_election_ids"])
    panel = [
        r
        for r in read_rows(ROOT / "results/house-study/candidate-comparisons.jsonl.gz")
        if r["D_candidate_election_id"] in ids
    ]
    x, y = [], []
    for row in panel:
        lean = (row["presidential_D_two_party_share_pct"] - 50) / 10
        values = [1, lean, lean**2, int(row["D_incumbent"]), int(row["R_incumbent"])]
        if trait == "donor_ideology":
            values.append(observations[row["contest_id"]]["value"] / 0.5)
        x.append(values)
        y.append(row["descriptive_gap_share_pp"])
    x, y = np.array(x), np.array(y)
    bread = np.linalg.inv(x.T @ x)
    beta = bread @ x.T @ y
    residuals = y - x @ beta
    states = np.array([r["state"] for r in panel])
    groups = sorted(set(states))
    meat = np.zeros_like(bread)
    for state in groups:
        score = x[states == state].T @ residuals[states == state]
        meat += np.outer(score, score)
    n, k = x.shape
    g = len(groups)
    covariance = bread @ meat @ bread * g / (g - 1) * (n - 1) / (n - k)
    np.testing.assert_allclose(beta, result["coefficients"], atol=1e-10)
    np.testing.assert_allclose(covariance, result["covariance"], atol=1e-10)


def test_persisted_prediction_folds_and_fixed_multiplicity_family():
    from scipy.stats import f

    panel = read_rows(ROOT / "results/house-study/candidate-comparisons.jsonl.gz")
    states = {r["D_candidate_election_id"]: r["state"] for r in panel}
    for fold in read_rows(ROOT / traits.OUT / "folds.jsonl.gz"):
        assert not set(fold["training_people"]) & set(fold["test_people"])
        assert not set(fold["training_ids"]) & set(fold["test_ids"])
        assert all(states[i] != fold["held_out_state"] for i in fold["training_ids"])
        assert all(states[i] == fold["held_out_state"] for i in fold["test_ids"])
    fits = read_rows(ROOT / traits.OUT / "fits.jsonl.gz")
    previous = 0
    for rank, result in enumerate(sorted(fits, key=lambda r: r.get("omnibus_pvalue", 1))):
        pvalue = 1
        if result["status"] == "estimated":
            q = len(result["focal_terms"])
            beta = np.array(result["coefficients"][-q:])
            cov = np.array(result["covariance"])[-q:, -q:]
            pvalue = f.sf(beta @ np.linalg.inv(cov) @ beta / q, q, result["state_clusters"] - 1)
            assert result["omnibus_pvalue"] == pytest.approx(pvalue)
        previous = max(previous, min(1, pvalue * (15 - rank)))
        assert result["holm_pvalue"] == pytest.approx(previous)
