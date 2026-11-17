import json
from pathlib import Path

import numpy as np
import pytest

from which_candidate.characteristics_research import source_text
from which_candidate.characteristics_v7_batch import acquire, prior_sources
from which_candidate.characteristics_v8_campaigns import biography_urls
from which_candidate.characteristics_v8_guides import oregon_statement, washington_statement
from which_candidate.characteristics_v8_prediction import paired
from which_candidate.storage import read_rows

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("field", "value", "allowed"),
    (
        ("factual_background", 11, True),
        ("factual_background", 9, False),
        ("donor_score", 6, False),
        ("candidates", 101, False),
    ),
)
def test_new_source_coverage_keeps_earlier_figure_snapshot_without_relaxing_other_gates(
    tmp_path, field, value, allowed
):
    from which_candidate.house_project import _refresh_coverage_plot_data
    from which_candidate.pipeline import csv_bytes

    previous = {
        "cohort": "all",
        "candidates": 100,
        "factual_background": 10,
        "donor_score": 5,
        "prior_federal_voting_score": 8,
    }
    for folder in ("publication/plot-data", "results/house", "data"):
        (tmp_path / folder).mkdir(parents=True)
    path = tmp_path / "publication/plot-data/candidate-evidence.csv"
    original = csv_bytes([previous])
    path.write_bytes(original)
    (tmp_path / "data/house-characteristics-v8-acquisitions.json").write_text("{}")
    (tmp_path / "results/house/coverage.json").write_text(json.dumps([{**previous, field: value}]))
    if allowed:
        _refresh_coverage_plot_data(tmp_path)
    else:
        with pytest.raises(ValueError, match="keep frozen figures"):
            _refresh_coverage_plot_data(tmp_path)
    assert path.read_bytes() == original


def test_plain_csv_scope_preserves_default_and_excludes_unneeded_personal_fields():
    body = b"Name,Race,Address\nJane Doe,Black,private location\nOther Person,White,other\n"
    assert source_text(body, {"format": "csv"}).count("Address=") == 2
    scoped = {"format": "csv", "columns": ["Name", "Race"], "text_scope": {"csv_row": 2}}
    assert source_text(body, scoped) == "Name=Jane Doe | Race=Black"
    for row in (1, 4, True):
        with pytest.raises(ValueError, match="CSV row"):
            source_text(body, {**scoped, "text_scope": {"csv_row": row}})
    with pytest.raises(ValueError, match="CSV columns"):
        source_text(body, {**scoped, "columns": ["not present"]})


def test_in_progress_or_unlevelled_education_is_not_a_completed_higher_credential():
    from which_candidate.characteristics_v8_extract import credential_code

    assert credential_code("B.A., State University; M.B.A. candidate") == "bachelors"
    assert credential_code("PhD student") is None
    assert credential_code("law degree") is None
    assert credential_code("Attended Harvard University") is None


def test_identity_only_and_rejected_proxy_claims_do_not_count_as_first_facts():
    from which_candidate.characteristics_v8 import acquisition_accounting

    old = [
        {
            "candidate_id": "1",
            "trait": t,
            "name": "Jane",
            "contest_id": "contest",
            "state": "AA",
            "party": "Democratic",
            "performance_eligible": True,
            "analysis_value": None,
            "analysis_eligible": False,
            "status": "unknown",
            "factual_qualified": False,
            "eligibility_reason": "held",
        }
        for t in ("education", "religion", "incumbency")
    ]
    new = [{**r, "factual_qualified": r["trait"] != "religion"} for r in old]
    observations = [
        {
            "candidate_id": "1",
            "trait": r["trait"],
            "v8_review": {"factual_qualified": r["trait"] == "education"},
        }
        for r in old
    ]
    first, _, _, _ = acquisition_accounting(new, old, observations)
    assert first == {("1", "education")}


def test_church_community_activity_is_not_affiliation():
    from which_candidate.characteristics_v8_extract import national_claims

    claim = national_claims(
        [["religion", "helps at church events", {"reported_community_activity": "church events"}]]
    )[0]
    assert claim["v8_review"]["factual_qualified"] is False
    assert claim["v8_review"]["analysis_value"] is None


def test_dated_military_range_qualifies_without_promoting_future_or_undated_service():
    from which_candidate.characteristics_v8_extract import national_claims

    for fragment, expected in (
        ("U.S. Navy from 1994–1998", True),
        ("U.S. Navy from 2026–2030", None),
        ("U.S. Navy veteran", None),
    ):
        observation = national_claims([["military", fragment, True]])[0]
        assert observation["v8_review"]["analysis_value"] is expected


def test_explicit_own_military_negative_survives_as_false_not_unknown():
    from which_candidate.characteristics_v8_extract import institutional_claims

    collected = []

    def add(key, candidate, claims, **kwargs):
        collected.extend(claims)

    institutional_claims(
        ROOT,
        {"tennessee-unicoi-guide-2026": {}},
        {"221173": {}},
        add,
        [],
    )
    military = next(r for r in collected if r["trait"] == "military")
    assert military["value"] is False
    assert military["v8_review"]["factual_qualified"] is True
    assert military["v8_review"]["analysis_value"] is False
    assert military["fragment"] == "Military Background: No Military Background."


def test_post_acquisition_uses_the_export_body_and_does_not_retry_failure(tmp_path, monkeypatch):
    commands = []

    class Response:
        returncode = 22
        stdout = "https://example.test/export"
        stderr = "403"

    def request(command, **kwargs):
        commands.append(command)
        return Response()

    monkeypatch.setattr("which_candidate.characteristics_v7_batch.subprocess.run", request)
    sources = {
        "export": {
            "url": "https://example.test/export",
            "post_data": {"officeIds": "1,2", "electionId": "344"},
        }
    }
    for _ in range(2):
        acquire(tmp_path, sources=sources, workdir="separate", prior=[])
    assert len(commands) == 1
    assert "--data" in commands[0]
    assert "officeIds=1%2C2&electionId=344" in commands[0]


def test_summary_only_acquisition_ledger_is_not_a_source_collection(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data/earlier-acquisitions.json").write_text(json.dumps({"sources": 17}))
    assert prior_sources(tmp_path) == []


def test_acquisition_work_directory_is_isolated_and_denial_resumes(tmp_path, monkeypatch):
    class Response:
        returncode = 22
        stdout = "https://example.test/denied"
        stderr = "403"

    calls = []

    def request(*args, **kwargs):
        calls.append(args)
        return Response()

    monkeypatch.setattr("which_candidate.characteristics_v7_batch.subprocess.run", request)
    sources = {"denied": {"url": "https://example.test/denied"}}
    for _ in range(2):
        result = acquire(tmp_path, sources=sources, workdir="separate", prior=[])
    assert len(calls) == 1
    assert result[0]["status"] == "failed_attempt_not_evidence"
    assert (tmp_path / "separate/retrievals.json").exists()
    assert not (tmp_path / "artifacts/characteristics-v7").exists()


def test_about_discovery_stays_on_original_site_and_excludes_staff_and_fragments():
    html = (
        '<a href="/meet#bio">Meet Jane</a><a href="/meet">Meet Jane</a>'
        '<a href="https://donate.test/about">About Jane</a>'
        '<a href="/staff">About our team</a><a href="/story">My story</a>'
    )
    assert biography_urls(html, "https://campaign.test") == [
        "https://campaign.test/meet",
        "https://campaign.test/story",
    ]


def test_oregon_subject_is_the_heading_not_an_opponent_or_contents_mention():
    assert oregon_statement("US Representative, 2nd District Chris Beck ... 32") is None
    statement = oregon_statement(
        "US Representative, 2nd District Chris Beck Democrat Independent "
        "Occupation: Observer Occupational Background: Advisor "
        "Educational Background: Brown, BA Prior Governmental Experience: "
        "State Representative. Unlike Cliff Bentz, I will do this."
    )
    assert statement["printed_name"] == "Chris Beck"
    assert statement["printed_party"] == "Democrat"
    assert statement["fields"]["Educational Background"] == "Brown, BA"


def test_washington_explicit_none_is_retained_but_not_automatically_reclassified():
    statement = washington_statement(
        "United States Representative | District 4 | 2-year term\nJohn\n"
        "Elected Experience\nNone.\nOther Professional Experience\nAir Force career.\n"
        "Education\nBS\nCommunity Service\nVolunteered\nStatement\nMy priorities\n"
        "Contact\nhttps://campaign.test\nDuresky\n(Prefers Democratic Party)"
    )
    assert statement["printed_name"] == "John Duresky"
    assert statement["fields"]["Elected Experience"] == "None."


def test_frozen_religion_fold_keeps_estimable_row_without_imputing_unsupported_opponent():
    from which_candidate.characteristics_v2 import paired as previous

    folder = ROOT / "results/house-characteristics-v7"
    fit = next(r for r in read_rows(folder / "fits.jsonl.gz") if r["trait"] == "religion")
    values = {
        r["contest_id"]: r["analysis_value"]
        for r in read_rows(folder / "candidate-traits.jsonl.gz")
        if r["trait"] == "religion" and r["performance_eligible"]
    }
    ids = set(fit["candidate_election_ids"])
    cohort = [
        {**r, "_value": values[r["contest_id"]]}
        for r in read_rows(folder / "panel-overlay.jsonl.gz")
        if r["D_candidate_election_id"] in ids
    ]
    levels = sorted({r["_value"] for r in cohort})
    before, _ = previous(cohort, "religion", levels)
    after, folds = paired(cohort, "religion", levels)
    assert len(before) == 121
    assert len(after) == 122
    assert len(cohort) == 123
    ia = next(f for f in folds if f["held_out_state"] == "IA")
    assert ia["status"] == "partially_estimated"
    assert len(ia["test_ids"]) == 2
    assert ia["supported_test_ids"] == ["2026:house:IA:02:general:source_general:audit:0"]
    assert ia["prediction_failures"] == [
        {
            "candidate_election_id": "2026:house:IA:03:general:source_general:audit:0",
            "reason": "unseen_test_incumbency_stratum",
        }
    ]
    lookup = {r["candidate_election_id"]: r for r in after}
    for row in before:
        for key in ("baseline_error_share_pp", "augmented_error_share_pp"):
            assert np.isclose(row[key], lookup[row["candidate_election_id"]][key], atol=1e-9)
    for fold in folds:
        assert not set(fold["training_people"]) & set(fold["test_people"])
