import hashlib
import io
import json
from pathlib import Path

from openpyxl import Workbook

from which_candidate.characteristics_acquisition import contextual_match
from which_candidate.characteristics_research import source_text
from which_candidate.storage import fingerprint, json_bytes, read_rows


def test_source_rows_preserve_non_utf8_names_and_blank_fields():
    body = "Name,State,Answer\nMaría,CA,\n".encode("cp1252")
    assert (
        source_text(body, {"format": "csv", "encoding": "cp1252"})
        == "Name=María | State=CA | Answer="
    )


def test_workbook_fragments_keep_whole_row_identity_and_literal_codes():
    book = Workbook()
    book.active.append(["Name", "Year", "Race"])
    book.active.append(["Example Candidate", 2024, "B/W"])
    buffer = io.BytesIO()
    book.save(buffer)
    assert (
        source_text(buffer.getvalue(), {"format": "xlsx"})
        == "Name=Example Candidate | Year=2024 | Race=B/W"
    )


def test_candidate_match_requires_full_name_and_contest_context():
    candidate = {
        "name": "Example Candidate",
        "state": "MN",
        "district": "AL",
        "party": "Democratic",
    }
    record = {
        "FName": "Example",
        "LName": "Candidate",
        "State": "MN",
        "Office": "U.S. Representative",
        "District": "AL",
        "Party": "D",
    }
    assert contextual_match(candidate, record, historical=True)
    for changed in (
        {"State": "CA"},
        {"District": 1},
        {"Party": "R"},
        {"LName": "Other"},
        {"Office": "U.S. Senator"},
    ):
        assert not contextual_match(candidate, record | changed, historical=True)


def test_v3_increment_preserves_every_frozen_output_identity_and_historical_claim():
    root = Path(__file__).resolve().parents[1]
    baseline = json.loads((root / "data/house-characteristics-v3-baseline.json").read_text())
    for path, digest in baseline["protected_sha256"].items():
        assert fingerprint(root / path)["sha256"] == digest
    inputs = read_rows(root / "results/house/source-inputs.jsonl.gz")[0]
    claims = {r["observation_id"]: r for r in inputs["reviewed_characteristic_observations"]}
    for key, digest in baseline["historical_reviewed_observations"].items():
        assert hashlib.sha256(json_bytes(claims[key])).hexdigest() == digest
    candidates = read_rows(root / "results/house/candidates.jsonl.gz")
    identities = [
        {k: c[k] for k in ("candidate_id", "contest_id", "name", "state", "district", "party")}
        for c in candidates
    ]
    assert (
        hashlib.sha256(json_bytes(identities)).hexdigest() == baseline["candidate_identity_sha256"]
    )
