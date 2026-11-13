import zipfile
from collections import defaultdict
from types import SimpleNamespace

import numpy as np
import pytest

from which_candidate.contextual import contextual_associations
from which_candidate.demographics import (
    RACE_CONTROLS,
    DemographicSources,
    read_historian,
    read_pew,
    religion_category,
)
from which_candidate.features import FeatureSources, read_candidate_master


@pytest.mark.parametrize(
    "literal,category",
    [
        ("Catholic", "catholic"),
        ("Baptist", "protestant"),
        ("Holiness", "protestant"),
        ("Atheist", "atheist"),
        ("Humanist", "humanist"),
        ("None", "unaffiliated"),
        ("Don't know/refused", "unknown"),
        ("Raised Lutheran", "unknown"),
        ("Member of a Catholic church", "unknown"),
        ("Christian", "christian_unspecified"),
        ("Jewish", "jewish"),
        ("Muslim", "muslim"),
        (None, "unknown"),
    ],
)
def test_religion_categories_do_not_infer_identity(literal, category):
    assert religion_category(literal) == category


def test_pew_lowercase_at_large_wrapping_and_incomplete_query(monkeypatch):
    lines = ["VT Al Peter Welch D I", "Catholic"] + [
        f"CA 1 Example Person{i} D I Protestant" for i in range(534)
    ]
    page = SimpleNamespace(extract_text=lambda **kwargs: "\n".join(lines))
    monkeypatch.setattr(
        "which_candidate.demographics.PdfReader", lambda path: SimpleNamespace(pages=[page])
    )
    spec = {"id": "test", "election_year": 2018, "publication_date": "2017-01-03"}
    rows = read_pew(None, spec)
    assert len(rows) == 535
    assert rows[0]["religion_category"] == "catholic"
    saved = lines[-1]
    lines[-1] = lines[-2]
    with pytest.raises(ValueError, match="Duplicate Pew"):
        read_pew(None, spec)
    lines[-1] = saved
    lines.pop()
    with pytest.raises(ValueError, match="Incomplete Pew"):
        read_pew(None, spec)


def test_historian_preserves_positive_categories_and_checks_coverage(tmp_path):
    path = tmp_path / "members.html"
    text = (
        "<table><tr><td>119th (2025-2027)<div>1 House, 0 Senate</div></td></tr>"
        "<tr><td>119th (2025-2027)</td><td>DOE, Jane<sup>12</sup></td>"
        "<td>NY</td><td>Democrat</td><td>House</td></tr></table>"
    )
    path.write_text(text)
    spec = {"id": "historian", "identity_group": "black"}
    rows = read_historian(path, spec)
    assert rows[0]["name"] == "DOE, Jane"
    assert rows[0]["identity_group"] == "black"
    path.write_text(text.replace("1 House", "2 House"))
    with pytest.raises(ValueError, match="Incomplete House Historian"):
        read_historian(path, spec)


def demographic_fixture():
    source = DemographicSources.__new__(DemographicSources)
    source.pew_index, source.historian_index = defaultdict(list), defaultdict(list)
    source.population_index, source.religious_index = defaultdict(list), {}
    source.map_change_evidence = {"changed_states": ["CA"]}
    sources = SimpleNamespace(people={"D1": {}}, aliases=lambda person: [("Jane", "Doe")])
    return source, sources


def test_missing_identity_is_not_white_or_non_hispanic_and_positive_records_combine():
    source, sources = demographic_fixture()
    feature = {"bioguide_id": "D1", "service_verified_incumbent": True}
    sources.people["D1"] = {"name": "Jane Doe"}
    row = {"year": 2026, "state": "NY", "chamber": "house", "election_date": "2026-11-03"}
    identity = source.candidate_identity(row, feature, sources)
    assert identity["race_category"] == "unknown"
    assert identity["hispanic_origin"] is None
    for group in ("black", "asian_or_pacific_islander", "hispanic"):
        source.historian_index[("NY", "house")].append(
            {
                "name": "DOE, Jane",
                "identity_group": group,
            }
        )
    identity = source.candidate_identity(row, feature, sources)
    assert identity["race_category"] == "multiracial"
    assert identity["hispanic_origin"] is True
    assert len(identity["racial_identity_evidence"]) == 3
    assert (
        source.candidate_identity({**row, "year": 2024}, feature, sources)["race_category"]
        == "unknown"
    )


def test_2026_district_composition_requires_unchanged_map_but_state_context_does_not():
    source, _ = demographic_fixture()
    for state, district in (("NY", "01"), ("CA", "01"), ("CA", None)):
        source.population_index[(2024, state, district)] = [
            {"population_shares_pct": {"asian": 20, "nhpi": 2}},
            {"population_shares_pct": {"hispanic": 10}},
        ]
    row = {"year": 2026, "chamber": "house", "state": "CA", "benchmark_district": "01"}
    assert source.context(row)["constituency_race_shares_pct"] == {}
    assert (
        source.context({**row, "state": "NY"})["constituency_race_shares_pct"][
            "asian_or_pacific_islander"
        ]
        == 22
    )
    assert (
        source.context({**row, "chamber": "senate"})["constituency_race_shares_pct"]["hispanic"]
        == 10
    )
    assert source.context(row)["constituency_religion_shares_pct"] == {}
    source.map_change_evidence = None
    assert source.context({**row, "state": "NY"})["constituency_race_shares_pct"] == {}


def test_fec_master_matches_actual_nominees_and_preserves_party_and_district_anchors(tmp_path):
    path = tmp_path / "cn.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "cn.txt",
            "\n".join(
                "|".join(
                    [
                        identifier,
                        "DOE, JANE",
                        party,
                        "2026",
                        "NY",
                        "H",
                        district,
                        "C",
                        "C",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                    ]
                )
                for identifier, party, district in (
                    ("H6NY01001", "DEM", "01"),
                    ("H6NY01002", "REP", "01"),
                    ("H6NY02001", "DEM", "02"),
                )
            ),
        )
    spec = {
        "id": "master",
        "kind": "fec_candidate_master",
        "election_year": 2026,
        "path": path.name,
    }
    assert len(read_candidate_master(path, spec)) == 3
    source = FeatureSources({"sources": [spec]}, tmp_path)
    row = {
        "year": 2026,
        "name": "Jane Doe",
        "state": "NY",
        "chamber": "house",
        "district": "01",
        "party_group": "D",
        "fec_id": None,
        "election_date": "2026-11-03",
        "source_incumbent": None,
    }
    resolved = source.resolve(row)
    assert resolved["fec_id"] == "H6NY01001"
    assert resolved["native_incumbent"] is False


def test_contextual_models_fit_2026_only_and_retain_unknown_group_holds():
    rng = np.random.default_rng(42)
    rows = []
    for i in range(64):
        shares = {g: float(rng.uniform(1, 8)) for g in RACE_CONTROLS}
        shares["white"] = 100 - sum(v for g, v in shares.items() if g != "hispanic")
        shares["asian_or_pacific_islander"] = shares["asian"] + shares["nhpi"]
        rows.append(
            {
                "year": 2026,
                "chamber": "house",
                "state": f"S{i % 16}",
                "eligible": True,
                "D_incumbent": True,
                "service_verified_incumbent": True,
                "person_group": f"person:{i}",
                "D_candidate_election_id": f"2026:{i}",
                "religion_category": "catholic" if i % 2 else "protestant",
                "race_category": "black" if i % 2 else "asian_or_pacific_islander",
                "hispanic_origin": None,
                "presidential_D_two_party_share_pct": float(rng.uniform(30, 80)),
                "descriptive_gap_share_pp": float(rng.normal()),
                "constituency_race_shares_pct": shares,
                "constituency_religion_shares_pct": {},
            }
        )
    fits, terms, counts = contextual_associations(
        rows
        + [{**r, "year": 2024, "D_candidate_election_id": f"2024:{i}"} for i, r in enumerate(rows)]
    )
    assert any(r["reference"] == "black" and r["status"] == "estimated" for r in fits)
    assert terms and all(r["target_year"] == 2026 for r in terms)
    assert all(all(i.startswith("2026:") for i in r["candidate_election_ids"]) for r in fits)
    assert all(r["status"] != "estimated" for r in fits if r["category"] == "atheist")
    assert all(
        r["rows"] == 0 for r in counts if r["phase"] == "primary_2026" and r["category"] == "white"
    )
