import csv
import io
import shutil
import zipfile
from copy import deepcopy
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import openpyxl
import pytest

from which_candidate.analysis import analysis_recipe, candidate_queries, package_analysis
from which_candidate.benchmarks import (
    STATE_NAMES,
    clerk_senate_2024,
    district_presidential,
    presidential_2024,
)
from which_candidate.biographies import biography_entries, birth_state
from which_candidate.features import FeatureSources, name_matches
from which_candidate.models import associations, fit_clustered, folds_and_predictions, purge
from which_candidate.pipeline import build
from which_candidate.research_sources import acquire_research
from which_candidate.storage import fingerprint, write_json, write_rows


def feature_fixture(tmp_path, congress=117, votes=100):
    person = {
        "id": {"bioguide": "D000001", "fec": ["H0CA00001"]},
        "name": {"first": "Jane", "last": "Doe", "official_full": "Jane A. Doe"},
        "bio": {"birthday": "1960-01-01", "gender": "F"},
        "terms": [{"type": "rep", "state": "CA", "start": "2013-01-03", "end": "2025-01-03"}],
    }
    write_json(tmp_path / "people.json", [person])
    members = tmp_path / "members.csv"
    with members.open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "congress",
                "chamber",
                "icpsr",
                "bioguide_id",
                "state_abbrev",
                "party_code",
                "nominate_dim1",
                "nokken_poole_dim1",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "congress": congress,
                "chamber": "House",
                "icpsr": "123.0",
                "bioguide_id": "D000001",
                "state_abbrev": "CA",
                "party_code": "100.0",
                "nominate_dim1": 9,
                "nokken_poole_dim1": -0.3,
            }
        )
    with (tmp_path / "unity.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "congress",
                "chamber",
                "icpsr",
                "party_code",
                "total_unity_votes",
                "with_party_unity_votes",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "congress": congress,
                "chamber": "House",
                "icpsr": "123",
                "party_code": "100",
                "total_unity_votes": votes,
                "with_party_unity_votes": votes - 5,
            }
        )
    sources = {
        "sources": [
            {"id": "people", "kind": "legislators", "path": "people.json"},
            {"id": "members", "kind": "voteview_members", "path": "members.csv"},
            {"id": "unity", "kind": "voteview_unity", "path": "unity.csv"},
        ]
    }
    return FeatureSources(sources, tmp_path)


def candidate(year=2024):
    return {
        "candidate_election_id": f"{year}:doe",
        "year": year,
        "state": "CA",
        "chamber": "house",
        "name": "Jane A. Doe",
        "fec_id": "H0CA00001",
        "source_incumbent": True,
        "election_date": f"{year}-11-05",
        "party_group": "D",
        "district": "01",
    }


@pytest.mark.parametrize(
    "year,congress", [(2016, 113), (2018, 114), (2020, 115), (2022, 116), (2024, 117)]
)
def test_legislative_features_use_prior_completed_congress_and_decimal_party_codes(
    tmp_path, year, congress
):
    sources = feature_fixture(tmp_path, congress)
    row = sources.features(candidate(year))
    assert row["lagged_congress"] == congress
    assert row["nokken_poole_dim1"] == -0.3
    assert row["party_unity_score"] == 0.95
    assert row["party_unity_votes"] == 100
    assert row["feature_evidence"][-2]["source_id"] == "members"


def test_future_congress_and_career_ideology_never_fill_missing_lag(tmp_path):
    sources = feature_fixture(tmp_path, 117)
    row = sources.features(candidate(2020))
    assert row["nokken_poole_dim1"] is None
    assert row["party_unity_score"] is None


def test_unity_minimum_denominator_retains_unknown_not_zero(tmp_path):
    row = feature_fixture(tmp_path, votes=49).features(candidate())
    assert row["party_unity_score"] is None
    assert row["party_unity_votes"] == 49


def test_dated_same_chamber_service_overrides_native_incumbent_marker(tmp_path):
    sources = feature_fixture(tmp_path)
    row = candidate()
    row["chamber"] = "senate"
    sources.people["D000001"]["terms"].append(
        {"type": "sen", "state": "CA", "start": "2025-01-03", "end": "2031-01-03"}
    )
    feature = sources.features(row)
    assert feature["incumbency_conflict"] is True
    assert feature["incumbent"] is False
    assert feature["chamber_tenure_years"] == 0
    assert feature["nokken_poole_dim1"] is None


def test_undocumented_person_and_biographies_remain_unknown(tmp_path):
    sources = feature_fixture(tmp_path)
    row = {
        **candidate(),
        "name": "Unknown Person",
        "fec_id": "H0CA00999",
        "source_incumbent": False,
    }
    feature = sources.features(row)
    assert feature["bioguide_id"] is None
    assert feature["incumbent"] is False
    for key in ("age_years", "race_ethnicity", "religion", "born_in_state", "nokken_poole_dim1"):
        assert feature[key] is None


def test_age_and_tenure_stop_at_election_cutoff(tmp_path):
    source = feature_fixture(tmp_path)
    feature = source.features(candidate(2020))
    cutoff = date(2020, 11, 5)
    assert feature["age_years"] == (cutoff - date(1960, 1, 1)).days / 365.2425
    assert feature["chamber_tenure_years"] == (cutoff - date(2013, 1, 3)).days / 365.2425


def test_name_anchors_preserve_family_and_reject_initial_only_guesses():
    assert name_matches("Doe, Jane A.", "Jane", "Doe")
    assert name_matches("A J “John” Peters", "AJ (John)", "Peters")
    assert not name_matches("Jane Roe", "Jane", "Doe")
    assert not name_matches("J. Doe", "Jane", "Doe")
    assert name_matches("Anthony D’Esposito", "Anthony P.", "D'Esposito")
    assert name_matches("Raul Garcia", "Dr. Raul", "Garcia")


def test_wrong_map_year_cannot_supply_a_house_benchmark():
    row = {
        "contest_id": "example",
        "year": 2022,
        "state": "NY",
        "chamber": "house",
        "district": "01",
        "D_candidate_election_id": None,
        "exclusion_reasons": [],
        "D_two_party_share_pct": 55,
    }
    benchmarks = [
        {
            "map_year": 2024,
            "state": "NY",
            "district": "01",
            "presidential_D_two_party_share_pct": 50,
        }
    ]
    query = candidate_queries([row], [], [], benchmarks, [])[0]
    assert query["eligible"] is False
    assert query["descriptive_gap_share_pp"] is None


@pytest.mark.parametrize(
    "district,eligible", [("02-FULLTERM", True), ("02-UNEXPIRED", False), ("02-SPECIAL", False)]
)
def test_only_explicit_full_term_suffix_joins_regular_map(district, eligible):
    row = {
        "contest_id": "example",
        "year": 2018,
        "state": "PA",
        "chamber": "house",
        "district": district,
        "D_candidate_election_id": None,
        "exclusion_reasons": [],
        "D_two_party_share_pct": 55,
    }
    benchmarks = [
        {
            "map_year": 2018,
            "state": "PA",
            "district": "02",
            "presidential_D_two_party_share_pct": 50,
        }
    ]
    query = candidate_queries([row], [], [], benchmarks, [])[0]
    assert query["eligible"] is eligible
    assert query["district"] == district
    assert query["descriptive_gap_share_pp"] == (5 if eligible else None)


def test_biography_fields_are_explicit_not_residence_church_or_city_name_guesses():
    spec = {"id": "directory", "publication_date": "2024-04-25", "election_year": 2024}
    pages = [
        "JANE DOE, Democrat, of Sacramento, CA; born in Michigan City, IN, May 1, 1960; "
        "member: First Catholic Church; education: College;\n"
        "JOHN ROE, Democrat, of Hawaii; born in New Mexico; religion: Roman Catholic;\n",
        "Judy DeRowe, Democrat, of Dallas, TX; born in Mexico, MO, June 1, 1960; religion: Jewish;\n",
    ]
    rows = biography_entries(pages, spec)
    assert len(rows) == 3
    assert rows[0]["birth_state"] == "IN"
    assert rows[0]["religion"] is None
    assert rows[1]["state"] == "HI"
    assert rows[1]["birth_state"] is None
    assert rows[1]["religion"] == "Roman Catholic"
    assert rows[2]["birth_state"] == "MO"
    assert rows[2]["source_page"] == 2
    assert birth_state("in Santa Fe, New Mexico, May 1, 1960") == "NM"
    assert birth_state("in Toronto, Canada, May 1, 1960") == "FOREIGN"
    assert birth_state("in Tbilisi, Georgia, May 1, 1960") is None


def test_future_ambiguous_and_nonincumbent_biographies_do_not_fill_features(tmp_path):
    sources = feature_fixture(tmp_path)
    bio = {
        "name": "JANE DOE",
        "state": "CA",
        "birth_state": "CA",
        "religion": "Catholic",
        "publication_date": "2025-01-01",
    }
    sources.biography_index[(2024, "CA")] = [bio]
    assert sources.features(candidate())["born_in_state"] is None
    bio["publication_date"] = "2024-04-25"
    feature = sources.features(candidate())
    assert feature["born_in_state"] is True
    assert feature["reported_catholic"] is True
    sources.biography_index[(2024, "CA")].append(dict(bio))
    assert sources.features(candidate())["religion"] is None
    sources.biography_index[(2024, "CA")] = [bio]
    sources.people["D000001"]["terms"][0]["end"] = "2021-01-03"
    assert sources.features(candidate())["born_in_state"] is None


def test_presidential_2024_totals_are_reconciled_not_assumed(tmp_path):
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "OFFICIAL 2024 PRES GE RESULTS"
    header = [None] * 31
    header[12], header[24], header[30] = "HARRIS", "TRUMP", "TOTAL VOTES"
    sheet.append(header)
    for state in STATE_NAMES:
        cells = [None] * 31
        cells[0], cells[12], cells[24], cells[30] = state, 40, 60, 101 if state == "TX" else 100
        sheet.append(cells)
    path = tmp_path / "president.xlsx"
    workbook.save(path)
    rows = presidential_2024(path, {"id": "president"})
    assert next(r for r in rows if r["state"] == "TX")["presidential_D_two_party_share_pct"] is None
    assert next(r for r in rows if r["state"] == "CA")["presidential_D_two_party_share_pct"] == 40


def test_map_metadata_mismatch_is_rejected_before_parsing(tmp_path):
    with pytest.raises(ValueError, match="qualification mismatch"):
        district_presidential(
            tmp_path / "missing.xlsx", {"map_year": 2022, "presidential_year": 2024}
        )


def test_clerk_parser_keeps_fusion_and_special_scopes_and_fails_on_unparsed_votes(monkeypatch):
    states = [*sorted(STATE_NAMES)[:32], "NY"]
    text = []
    for state in states:
        text.extend(
            [
                STATE_NAMES[state],
                "FOR UNITED STATES SENATOR",
                "Jane Doe, Democrat ........... 60",
                "John Roe, Republican ........... 40",
            ]
        )
        if state == "NY":
            text.append("Jane Doe, Working Families ........... 5")
        if state in ("CA", "NE"):
            text.extend(
                [
                    "(For unexpired term ending January 3, 2025)",
                    "Jane Doe, Democrat ........... 50",
                    "John Roe, Republican ........... 45",
                ]
            )
        text.append("FOR UNITED STATES REPRESENTATIVE")
    page = SimpleNamespace(extract_text=lambda **kwargs: "\n".join(text))
    monkeypatch.setattr(
        "which_candidate.benchmarks.PdfReader", lambda path: SimpleNamespace(pages=[page])
    )
    candidates, contests, _, native, decisions = clerk_senate_2024("unused", {"id": "clerk"})
    assert len(contests) == 35
    assert len(native) == len(decisions)
    assert all(
        not r["eligible_descriptive_two_party_share"]
        for r in contests
        if r["district"] == "UNEXPIRED"
    )
    assert any(r["votes"] == 65 for r in candidates)
    text.insert(2, "Jane Doe ...... missing")
    with pytest.raises(ValueError, match="Unparsed Clerk Senate line"):
        clerk_senate_2024("unused", {"id": "clerk"})


def synthetic_panel():
    rng = np.random.default_rng(42)
    rows = []
    for year in (2016, 2018, 2020, 2022, 2024):
        for state in range(12):
            for district in range(4):
                lean = float(rng.normal())
                d_inc, r_inc = bool(rng.integers(2)), bool(rng.integers(2))
                gap = 2 + lean * 1.5 + lean**2 * 0.4 + d_inc * 3 - r_inc * 2
                gap += (year - 2016) / 2 + float(rng.normal(scale=0.1))
                rows.append(
                    {
                        "eligible": True,
                        "chamber": "house",
                        "year": year,
                        "state": str(state),
                        "D_candidate_election_id": f"{year}:{state}:{district}",
                        "person_group": f"{state}:{district}",
                        "D_two_party_share_pct": 50 + 10 * lean + gap,
                        "presidential_D_two_party_share_pct": 50 + 10 * lean,
                        "descriptive_gap_share_pp": gap,
                        "D_incumbent": d_inc,
                        "R_incumbent": r_inc,
                        "service_verified_incumbent": d_inc,
                    }
                )
    return rows


def test_adjustment_recovers_known_incumbency_association_and_ignores_locked_outcomes():
    panel = synthetic_panel()
    _, terms = associations(panel)
    coefficient = next(r for r in terms if r["primary_focal"])
    assert coefficient["estimate_share_pp"] == pytest.approx(3, abs=0.06)
    changed = deepcopy(panel)
    for row in changed:
        if row["year"] == 2024:
            row["descriptive_gap_share_pp"] += 100
    assert associations(changed)[1] == terms


def test_folds_hold_out_states_people_and_future_cycles():
    folds, predictions = folds_and_predictions(synthetic_panel())
    assert predictions
    for fold in folds:
        assert not set(fold["train_states"]) & set(fold["test_states"])
        assert fold["candidate_group_overlap"] == 0
        if ":forward:" in fold["fold_id"]:
            assert max(fold["train_years"]) < min(fold["test_years"])
    assert any(r.get("locked_validation_2024") for r in predictions)


def test_purge_removes_cross_state_repeated_people():
    train = [{"state": "CA", "person_group": "same"}, {"state": "NY", "person_group": "other"}]
    assert purge(train, [{"state": "TX", "person_group": "same"}]) == [train[1]]


def test_rank_deficient_fit_is_a_hold_not_a_finding():
    x = np.ones((30, 2))
    fit = fit_clustered(x, np.arange(30), [str(i // 2) for i in range(30)])
    assert fit["status"] == "rank_deficient_or_ill_conditioned"
    assert "coefficients" not in fit


def test_research_import_pins_complete_bytes_and_verifies_without_refetch(tmp_path, monkeypatch):
    payload = b"complete downloaded original, not just its metadata"
    monkeypatch.setattr("urllib.request.urlopen", lambda *args, **kwargs: io.BytesIO(payload))
    spec = {
        "id": "test",
        "kind": "test",
        "origin_url": "https://example.test/source",
        "suffix": ".txt",
    }
    assert acquire_research(tmp_path, [spec])["status"] == "imported"
    cached = next((tmp_path / "raw").iterdir())
    assert cached.read_bytes() == payload

    def denied(*args, **kwargs):
        raise AssertionError("Pinned acquisition must not request the network")

    monkeypatch.setattr("urllib.request.urlopen", denied)
    assert acquire_research(tmp_path, [spec])["status"] == "verified_existing_import"
    cached.write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="Source hash mismatch"):
        acquire_research(tmp_path, [spec])


def test_analysis_archive_keeps_originals_queries_and_project_relative_paths(tmp_path):
    from test_pipeline import source_fixture

    manifest = source_fixture(tmp_path)
    root = Path(__file__).parents[1]
    for folder in ("which_candidate", "tests", "docs"):
        shutil.copytree(
            root / folder, tmp_path / folder, ignore=shutil.ignore_patterns("__pycache__")
        )
    for name in ("README.md", "pyproject.toml", "requirements.lock"):
        shutil.copyfile(root / name, tmp_path / name)
    for name in ("research-sources.json", "supplemental-returns-sources.json"):
        write_json(manifest.parent / name, {"schema": "which_candidate.sources.v1", "sources": []})
    returns = manifest.parent / "returns-v2"
    build(manifest, returns)
    output = manifest.parent / "analysis-v1"
    output.mkdir()
    query = output / "candidate-queries.jsonl.gz"
    write_rows(query, [{"eligible": False, "exclusion": "kept"}, {"eligible": True}])
    write_json(
        output / "manifest.json",
        {
            "recipe": analysis_recipe(manifest.parent, returns, tmp_path),
            "files": {query.name: fingerprint(query)},
        },
    )
    archive = tmp_path / "complete.zip"
    package_analysis(tmp_path, manifest.parent, returns, output, archive)
    with zipfile.ZipFile(archive) as packed:
        assert packed.read("data/fixture.xlsx") == (manifest.parent / "fixture.xlsx").read_bytes()
        assert packed.read("data/analysis-v1/candidate-queries.jsonl.gz") == query.read_bytes()
        assert "data/returns-v2/fec-row-decisions.jsonl.gz" in packed.namelist()
        assert "which_candidate/biographies.py" in packed.namelist()
        assert "tests/test_analysis.py" in packed.namelist()
    with pytest.raises(ValueError, match="overwrite"):
        package_analysis(tmp_path, manifest.parent, returns, output, archive)
