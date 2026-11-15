import hashlib
from datetime import date

import pytest

from which_candidate.incoming_biographies import (
    exact_date,
    identity_index,
    qualify_identity,
    receipt,
    source_profiles,
    validate,
)


def test_exact_date_requires_one_valid_explicit_iso_date():
    assert exact_date("Born (1972-07-14) July 14, 1972") == "1972-07-14"
    assert exact_date("1977/1978 (age 48–49)") is None
    assert exact_date("December 1966") is None
    assert exact_date("1972-02-31") is None
    assert exact_date("1972-07-14 and 1973-07-14") is None


def test_identity_qualification_requires_candidate_and_full_seat_name_context():
    row = {
        "candidate_id": "123",
        "state": "NC",
        "district": "09",
        "name": "Richard Ojeda",
    }
    spec = dict(row)
    assert "same_state_district" in qualify_identity(spec, row)
    for key, value in (("state", "WV"), ("district", "03"), ("name", "Richard Smith")):
        changed = dict(spec)
        changed[key] = value
        with pytest.raises(ValueError, match="Identity mismatch"):
            qualify_identity(changed, row)


def test_identity_index_rejects_missing_and_duplicate_candidate_ids():
    with pytest.raises(ValueError, match="present and unique"):
        identity_index([{"candidate_id": ""}])
    with pytest.raises(ValueError, match="present and unique"):
        identity_index([{"candidate_id": "1"}, {"candidate_id": "1"}])


def test_receipt_pins_original_bytes(tmp_path, monkeypatch):
    import which_candidate.incoming_biographies as module

    monkeypatch.setattr(module, "ROOT", tmp_path)
    path = tmp_path / "source.html"
    raw = b"<html>reviewed evidence</html>"
    path.write_bytes(raw)
    item = receipt("source", "https://example.test", path, raw, "2026-11-14T00:00:00+00:00")
    assert item["bytes"] == len(raw)
    assert item["sha256"] == hashlib.sha256(raw).hexdigest()
    assert item["qualification"].endswith("model_ineligible")


def test_validator_preserves_enrollment_and_rejects_unqualified_completion(monkeypatch):
    import which_candidate.incoming_biographies as module

    rows = [
        {
            "candidate_id": "1",
            "state": "NC",
            "district": "14",
            "name": "Lakesha Womack",
            "entry_classification": "new_to_current_House; prior_federal_service_not_fully_resolved",
        }
    ]
    monkeypatch.setattr(module, "incoming_rows", lambda: rows)
    profile = {
        "candidate_id": "1",
        "state": "NC",
        "district": "14",
        "name": "Lakesha Womack",
        "fields": {
            "education": [
                {
                    "institution": "Vanderbilt Law School",
                    "credential": "Master of Legal Studies",
                    "completion_status": "enrolled_or_pursuing",
                    "literal": "Pursuing a Master of Legal Studies",
                }
            ]
        },
        "evidence": {
            "id": "external-existing",
            "source_kind": "primary_candidate_biography",
        },
        "field_audit": {"education": {"status": "explicit_in_cached_source"}},
        "identity_qualification": "test",
        "model_ready": False,
        "source_kind": "primary_candidate_biography",
    }
    assert validate({"profiles": [profile], "sources": [], "failures": []})
    profile["fields"]["education"][0] = {
        "institution": "Example University",
        "credential": None,
        "completion_status": "completed",
        "literal": "Attended Example University",
    }
    with pytest.raises(ValueError, match="requires a stated credential"):
        validate({"profiles": [profile], "sources": [], "failures": []})


def test_validator_never_accepts_model_ready(monkeypatch):
    import which_candidate.incoming_biographies as module

    monkeypatch.setattr(
        module,
        "incoming_rows",
        lambda: [
            {
                "candidate_id": "1",
                "state": "CA",
                "district": "01",
                "name": "Example Candidate",
            }
        ],
    )
    profile = {
        "candidate_id": "1",
        "state": "CA",
        "district": "01",
        "name": "Example Candidate",
        "fields": {"date_of_birth": date(1970, 1, 1).isoformat()},
        "evidence": {
            "id": "external-existing",
            "source_kind": "primary_candidate_biography",
        },
        "field_audit": {"date_of_birth": {"status": "explicit_in_cached_source"}},
        "identity_qualification": "test",
        "model_ready": True,
        "source_kind": "primary_candidate_biography",
    }
    with pytest.raises(ValueError, match="model-ineligible"):
        validate({"profiles": [profile], "sources": [], "failures": []})


def test_primary_fields_require_field_specific_cached_text_support(tmp_path, monkeypatch):
    import which_candidate.incoming_biographies as module

    raw = b"<html><body>Jane Example earned a law degree from Yale Law School.</body></html>"
    path = tmp_path / "source.html"
    path.write_bytes(raw)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    spec = {
        "candidate_id": "1",
        "state": "CT",
        "district": "01",
        "name": "Jane Example",
        "url": "https://example.test",
        "anchors": ["Jane Example"],
        "verify": ["Yale Law School"],
        "fields": {
            "education": [
                {
                    "institution": "University of Florida",
                    "credential": "JD",
                    "completion_status": "completed",
                    "literal": "University of Florida JD",
                }
            ]
        },
        "support": {"education": ["University of Florida"]},
    }
    monkeypatch.setattr(
        module,
        "source_specs",
        lambda: [("incoming-primary-1", spec)],
    )
    source = receipt(
        "incoming-primary-1",
        "https://example.test",
        path,
        raw,
        "2026-11-14T00:00:00+00:00",
    )
    rows = {
        "1": {
            "candidate_id": "1",
            "state": "CT",
            "district": "01",
            "name": "Jane Example",
        }
    }
    with pytest.raises(ValueError, match="does not support"):
        source_profiles(rows, [source])


def test_secondary_exact_dob_must_be_explicit_in_birth_literal(monkeypatch):
    import which_candidate.incoming_biographies as module

    monkeypatch.setattr(
        module,
        "incoming_rows",
        lambda: [
            {
                "candidate_id": "1",
                "state": "CA",
                "district": "01",
                "name": "Example Candidate",
            }
        ],
    )
    profile = {
        "candidate_id": "1",
        "state": "CA",
        "district": "01",
        "name": "Example Candidate",
        "fields": {
            "birth_literal": "1977/1978 (age 48-49)",
            "date_of_birth": "1977-01-01",
        },
        "evidence": {"id": "external-existing", "source_kind": "secondary_wikipedia"},
        "field_audit": {
            "birth_literal": {"status": "parsed_from_secondary_infobox_or_roster"},
            "date_of_birth": {"status": "parsed_from_secondary_infobox_or_roster"},
        },
        "identity_qualification": "test",
        "model_ready": False,
        "source_kind": "secondary_wikipedia",
    }
    with pytest.raises(ValueError, match="occur explicitly"):
        validate({"profiles": [profile], "sources": [], "failures": []})
