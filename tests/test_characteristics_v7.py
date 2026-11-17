import io
import json
import zipfile

import pytest

from which_candidate.characteristics_research import reviewed_claims, source_text
from which_candidate.characteristics_v4 import birth_interval
from which_candidate.characteristics_v7 import restrict_identities
from which_candidate.characteristics_v7_batch import acquire
from which_candidate.characteristics_v7_extract import classification_claims, dated_house_link
from which_candidate.house_backgrounds import validate_reported_age


def csv_archive(text):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("members.csv", text)
    return buffer.getvalue()


def test_archive_row_scope_does_not_transfer_an_adjacent_identity():
    body = csv_archive("Name,State,Latino\nFirst Person,CA,0\nSecond Person,NV,1\n")
    source = {
        "id": "test-subject",
        "format": "zip_csv",
        "member": "members.csv",
        "text_scope": {"csv_row": 2},
        "identity_fragment": "Name=Second Person",
    }
    text = source_text(body, source)
    assert text == "Name=First Person | State=CA | Latino=0"
    with pytest.raises(ValueError, match="Unsupported research subject"):
        reviewed_claims(source, {}, text)
    source["text_scope"]["csv_row"] = 3
    assert source_text(body, source).endswith("Latino=1")


@pytest.mark.parametrize("row", [0, 1, 4, True, "2", -1])
def test_archive_rejects_invalid_record_scope(row):
    with pytest.raises(ValueError, match="Invalid research CSV row"):
        source_text(
            csv_archive("Name,Value\nFirst Person,\nSecond Person,0\n"),
            {"format": "zip_csv", "member": "members.csv", "text_scope": {"csv_row": row}},
        )


def test_archive_selection_retains_explicit_zero_and_missing_distinction():
    body = csv_archive('Name,Value,Other\n"First\nPerson",0,yes\nSecond Person,,no\n')
    source = {"format": "zip_csv", "member": "members.csv", "columns": ["Name", "Value"]}
    assert source_text(body, source).splitlines() == [
        "Name=First Person | Value=0",
        "Name=Second Person | Value=",
    ]
    with pytest.raises(ValueError, match="Missing research CSV columns"):
        source_text(body, source | {"columns": ["Missing"]})


def test_archive_rejects_non_csv_members_without_extracting_them():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("../outside.txt", "not a permitted CSV")
    with pytest.raises(ValueError, match="Unsupported or oversized"):
        source_text(buffer.getvalue(), {"format": "zip_csv", "member": "../outside.txt"})


def test_dated_reported_age_preserves_the_complete_election_age_interval():
    value = {
        "reported_age": 53,
        "reference_date": "2026-05-01",
        "birth_date_interval": ["1972-05-02", "1973-05-01"],
    }
    validate_reported_age(value)
    assert birth_interval(value) == [53, 54]
    with pytest.raises(ValueError, match="Unsupported reported-age bounds"):
        validate_reported_age(value | {"birth_date_interval": ["1973-01-01", "1973-01-01"]})
    with pytest.raises(ValueError, match="Invalid reported-age interval"):
        validate_reported_age(value | {"reported_age": True})


def test_classification_requires_actual_indicators_and_preserves_history_conflicts():
    record = {"race": "White", "latino": "0", "ethnicity": ""}
    claims = classification_claims([record], "literal")
    assert claims[1]["v7_review"]["analysis_value"] == "historical_Latino_0"
    assert len(classification_claims([record | {"latino": ""}], "literal")) == 1
    assert classification_claims([record | {"race": "", "latino": ""}], "literal") == []
    claims = classification_claims([record, record | {"latino": "1"}], "literal")
    assert claims[1]["value"]["source_latino_indicator"] == 1
    assert claims[1]["v7_review"]["analysis_value"] is None
    assert claims[0]["v7_review"]["analysis_value"] == "White"


def test_dated_house_match_does_not_transfer_an_adjacent_contest_or_term():
    member = {
        "name": {"first": "First", "last": "Person"},
        "terms": [
            {
                "type": "rep",
                "state": "CA",
                "district": 3,
                "start": "2019-01-03",
                "end": "2021-01-03",
            }
        ],
    }
    record = {"eyear": "2018", "state": "ca", "district": "03", "win_name": "First Person"}
    assert dated_house_link(member, record)
    assert not dated_house_link(member, record | {"district": "04"})
    assert not dated_house_link(member, record | {"eyear": "2020"})


@pytest.mark.parametrize(
    "old_value,new_value,trait",
    [
        (["Black", "Asian"], ["Black"], "race"),
        (["Middle Eastern"], ["White"], "race"),
        (["Hispanic"], {"source_latino_indicator": 0}, "ethnicity"),
    ],
)
def test_new_classification_does_not_erase_incompatible_existing_identity(
    old_value, new_value, trait
):
    row = {
        "candidate_id": "1",
        "trait": trait,
        "analysis_eligible": True,
        "analysis_value": "White",
        "eligibility_reason": "original",
    }
    observation = {
        "candidate_id": "1",
        "trait": trait,
        "value": new_value,
        "v7_review": {"analysis_value": "Black" if trait == "race" else "historical_Latino_0"},
    }
    old = {"candidate_id": "1", "trait": trait, "value": old_value}
    conflicts = []
    restrict_identities([row], [observation], [old], conflicts)
    assert row["analysis_eligible"] is False
    assert row["analysis_value"] is None
    assert len(conflicts) == 1


def test_acquisition_deduplicates_retained_urls_and_does_not_retry_denials(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir()
    (tmp_path / "data/research-sources.json").write_text(
        json.dumps(
            {
                "sources": [
                    {"id": "retained", "origin_url": "https://example.test/known", "sha256": "abc"}
                ]
            }
        )
    )
    work = tmp_path / "artifacts/characteristics-v7"
    work.mkdir(parents=True)
    (work / "retrievals.json").write_text(
        json.dumps([{"id": "denied", "status": "failed_attempt_not_evidence", "error": "HTTP 403"}])
    )
    monkeypatch.setattr(
        "which_candidate.characteristics_v7_batch.subprocess.run",
        lambda *a, **k: pytest.fail("No network attempt is permitted"),
    )
    result = acquire(
        tmp_path,
        sources={
            "known": {"url": "https://example.test/known"},
            "denied": {"url": "https://example.test/denied"},
        },
    )
    assert len(result) == 2
    assert result[1]["status"] == "retained_existing_source_not_new_acquisition"
    assert result[1]["network_attempts"] == 0
