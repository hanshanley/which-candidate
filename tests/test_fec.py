import pytest

from which_candidate.fec import combine_lines, integer, parse_sheet

HEADER = [
    1,
    "STATE ABBREVIATION",
    "STATE",
    "DISTRICT",
    "FEC ID",
    "(I)",
    "CANDIDATE NAME (First)",
    "CANDIDATE NAME (Last)",
    "CANDIDATE NAME",
    "TOTAL VOTES",
    "PARTY",
    "PRIMARY VOTES",
    "PRIMARY %",
    "RUNOFF VOTES",
    "RUNOFF %",
    "GENERAL VOTES ",
    "GENERAL %",
    "GE RUNOFF ELECTION VOTES",
    "GE RUNOFF ELECTION %",
    "COMBINED GE PARTY TOTALS",
    "COMBINED %",
]


def native(number, cells):
    return {"source_id": "fixture", "sheet": "Senate", "source_row": number, "cells": cells}


def candidate(name, party, votes, fec_id="S0NY00001", combined=None, state="NY", district="S"):
    cells = [None] * len(HEADER)
    cells[1], cells[3], cells[4] = state, district, fec_id
    cells[8], cells[10], cells[15], cells[19] = name, party, votes, combined
    return cells


def parse(*rows):
    return parse_sheet(
        [native(1, HEADER)] + [native(i + 2, row) for i, row in enumerate(rows)],
        2020,
        "senate",
    )


def test_fusion_counts_components_once_and_retains_references():
    rows, decisions, _ = parse(
        candidate("Example, Jane", "Combined Parties:", None, combined=125),
        candidate("Example, Jane", "D", 100, combined=125),
        candidate("Example, Jane", "WF", 25, combined=125),
    )
    assert len(rows) == 1
    assert rows[0]["votes"] == 125
    assert rows[0]["party_group"] == "D"
    assert rows[0]["issues"] == []
    assert rows[0]["combined_total_references"] == [125]
    assert len(rows[0]["source_rows"]) == 3
    assert decisions[0]["status"] == "combined_reference"


@pytest.mark.parametrize("value", [None, "#", "Unopposed", -1, 1.5, True])
def test_unknown_or_invalid_vote_count_is_not_zero(value):
    assert integer(value) is None


def test_missing_candidate_count_and_primary_only_are_different():
    rows, decisions, _ = parse(
        candidate("No Count, Jane", "D", "Unopposed"),
        candidate("Primary Only, Jack", "R", None, fec_id="S0NY00002"),
    )
    assert len(rows) == 1
    assert rows[0]["votes"] is None
    assert rows[0]["issues"] == ["missing_or_nonnumeric_votes"]
    assert decisions[1]["status"] == "no_general_vote_entry"


def test_wrong_header_is_rejected():
    header = HEADER.copy()
    header[15] = "PRIMARY VOTES"
    with pytest.raises(ValueError, match="general vote"):
        parse_sheet([native(1, header)], 2020, "senate")


def test_duplicate_lines_and_conflicting_combined_totals_are_held():
    rows, _, _ = parse(
        candidate("Example, Jane", "D", 100, combined=150),
        candidate("Example, Jane", "D", 25, combined=125),
    )
    assert set(rows[0]["issues"]) == {"duplicate_party_lines", "fusion_total_mismatch"}


def test_special_and_regular_contests_do_not_merge():
    rows, _, _ = parse(
        candidate("Example, Jane", "D", 100, district="S-FULL TERM"),
        candidate("Example, Jane", "D", 50, district="S-UNEXPIRED TERM"),
    )
    assert len(rows) == 2
    assert len({row["contest_id"] for row in rows}) == 2
    assert next(row for row in rows if "UNEXPIRED" in row["district"])["election_date"] is None


def test_generic_writeins_are_not_named_nominees():
    rows, _, _ = parse(candidate("Scattered", "D", 10, fec_id="n/a"))
    assert rows[0]["named_candidate"] is False


def test_zero_is_an_observed_count():
    rows, _, _ = parse(candidate("Example, Jane", "D", 0))
    assert rows[0]["votes"] == 0
    assert rows[0]["issues"] == []


def test_major_party_conflict_is_retained_and_held():
    rows, _, _ = parse(
        candidate("Example, Jane", "D", 50),
        candidate("Example, Jane", "R", 50),
    )
    assert rows[0]["party_group"] == "O"
    assert "conflicting_major_party_labels" in rows[0]["issues"]


def test_combined_only_cannot_manufacture_component_counts():
    rows, _, _ = parse(candidate("Example, Jane", "Combined Parties:", None, combined=150))
    assert rows[0]["votes"] is None
    assert "missing_or_nonnumeric_votes" in rows[0]["issues"]


def test_combine_lines_preserves_observed_incumbent_indicator():
    lines = [
        {
            "party": "D",
            "votes": 50,
            "combined_votes": None,
            "incumbent_marker": "(I)",
            "name": "Example, Jane",
            "fec_id": "S0NY00001",
            "source": {"source_row": 2},
        }
    ]
    assert combine_lines(lines)["source_incumbent"] is True


def test_missing_senate_district_uses_only_unique_within_sheet_scope():
    rows, decisions, _ = parse(
        candidate("Example, Jane", "D", 100),
        candidate("Other, Sam", "W", 12, fec_id="n/a", district=None),
    )
    assert len({row["contest_id"] for row in rows}) == 1
    assert decisions[1]["scope_resolution"] == "unique_native_senate_contest_within_state_sheet"


def test_missing_senate_scope_not_inferred_when_two_terms_exist():
    rows, decisions, _ = parse(
        candidate("Example, Jane", "D", 100, district="S-FULL TERM"),
        candidate("Example, Jane", "D", 100, district="S-UNEXPIRED TERM"),
        candidate("Other, Sam", "W", 12, fec_id="n/a", district=None),
    )
    assert len(rows) == 2
    assert decisions[-1]["status"] == "unresolved_contest_scope"


def test_none_of_these_and_unnamed_writeins_are_accounting_not_people():
    none = candidate("None of These Candidates", None, 10)
    writeins = candidate(None, "W", 5)
    rows, decisions, accounting = parse(none, writeins)
    assert rows == []
    assert [row["status"] for row in decisions] == ["noncandidate_choice"] * 2
    assert [row["votes"] for row in accounting] == [10, 5]


def test_source_general_with_later_runoff_is_held():
    cells = candidate("Example, Jane", "D", 100)
    cells[17] = 120
    rows, _, _ = parse(cells)
    assert "general_runoff_stage_unqualified" in rows[0]["issues"]


def test_reused_fec_id_with_different_names_is_not_a_verified_identity():
    rows, _, _ = parse(
        candidate("Example, Jane", "D", 100),
        candidate("Someone, Else", "WF", 10),
    )
    assert rows[0]["native_name_aliases"] == ["Example, Jane", "Someone, Else"]
    assert "candidate_identity_name_conflict" in rows[0]["issues"]


@pytest.mark.parametrize("chamber", ["house", "senate"])
def test_native_ballot_removal_note_is_not_an_unknown_general_vote_count(chamber):
    header = HEADER + ["PE WINNER INDICATOR", "GE WINNER INDICATOR", "FOOTNOTES"]
    cells = candidate("Example, Jane", "GRE", "#", state="MT") + [None] * 3
    cells[23] = (
        "# The Montana Green Party candidates were removed from the general election "
        "ballot in August 2020 by court order."
    )
    rows, decisions, _ = parse_sheet([native(1, header), native(2, cells)], 2020, chamber)
    assert rows == []
    assert decisions[0]["status"] == "removed_from_general_ballot_native_note"
    assert decisions[0]["native_note"] == cells[23]


def test_presidential_benchmark_identifies_nominee_not_every_democratic_label():
    header = [None] * 14
    header[3], header[9], header[10] = "STATE ABBREVIATION", "PARTY", "GENERAL RESULTS"
    major, minor = [None] * 14, [None] * 14
    for cells, name, fec_id, count in (
        (major, "Biden, Joseph R.", "P80000722", 100),
        (minor, "Other, Jane", "P00000001", 1),
    ):
        cells[1], cells[3], cells[7], cells[9], cells[10] = fec_id, "AZ", name, "D", count
    rows, _, _ = parse_sheet(
        [native(1, header), native(2, major), native(3, minor)], 2020, "president"
    )
    assert {row["name"]: row["party_group"] for row in rows} == {
        "Biden, Joseph R.": "D",
        "Other, Jane": "O",
    }
