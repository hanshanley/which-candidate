import pytest

from which_candidate.panel import contest_panel, senate_benchmarks


def row(party, votes, year=2020, chamber="senate", state="NY", district="S", suffix=""):
    contest_id = f"{year}:{chamber}:{state}:{district}:general:source_general"
    return {
        "candidate_election_id": contest_id + ":" + party + suffix,
        "contest_id": contest_id,
        "year": year,
        "chamber": chamber,
        "state": state,
        "district": district,
        "party_group": party,
        "votes": votes,
        "named_candidate": True,
        "issues": [],
        "source_id": "fixture",
        "source_status": "fixture",
        "boundary_comparability_verified": False,
        "name": "Example " + party,
        "source_incumbent": False,
    }


def test_share_and_margin_have_distinct_units():
    result = contest_panel([row("D", 60), row("R", 40)], [])[0]
    assert result["D_two_party_share_pct"] == 60
    assert result["D_minus_R_margin_pp"] == 20
    assert result["eligible_adjusted_overperformance"] is False


def test_unopposed_does_not_get_a_performance_score():
    result = contest_panel([row("D", 60)], [])[0]
    assert result["R_votes"] == 0
    assert result["D_two_party_share_pct"] is None
    assert "requires_one_named_R_nominee" in result["exclusion_reasons"]


@pytest.mark.parametrize(
    "state,year,district,reason",
    [
        ("NY", 2020, "S-UNEXPIREDTERM", "special_election_scope_unqualified"),
        ("LA", 2020, "S", "louisiana_stage_unqualified"),
        ("ME", 2020, "S", "ranked_choice_round_unqualified"),
        ("AK", 2022, "S", "ranked_choice_round_unqualified"),
    ],
)
def test_unqualified_election_systems_are_held(state, year, district, reason):
    rows = [row(party, 50, state=state, year=year, district=district) for party in ("D", "R")]
    result = contest_panel(rows, [])[0]
    assert reason in result["exclusion_reasons"]
    assert result["D_two_party_share_pct"] is None


def test_two_democratic_nominees_are_not_one_nominee():
    rows = [row("D", 30), row("D", 20, suffix="other"), row("R", 50)]
    result = contest_panel(rows, [])[0]
    assert "requires_one_named_D_nominee" in result["exclusion_reasons"]


def test_missing_counts_are_retained_not_filled():
    rows = [row("D", None), row("R", 50)]
    result = contest_panel(rows, [{"contest_id": rows[0]["contest_id"], "votes": 50}])[0]
    assert result["D_votes"] is None
    assert result["all_candidate_votes"] is None
    assert result["D_two_party_share_pct"] is None
    assert result["native_total_reconciled"] is None
    assert "native_contest_total_mismatch" not in result["exclusion_reasons"]


def test_native_accounting_conflict_holds_contest():
    rows = [row("D", 60), row("R", 40)]
    totals = [{"contest_id": rows[0]["contest_id"], "votes": 101}]
    result = contest_panel(rows, totals)[0]
    assert result["native_total_reconciled"] is False
    assert "native_contest_total_mismatch" in result["exclusion_reasons"]


def test_candidate_id_duplicates_fail_instead_of_double_counting():
    with pytest.raises(ValueError, match="Duplicate candidate"):
        contest_panel([row("D", 60), row("D", 60)], [])


def test_senate_benchmark_is_explicitly_descriptive_and_uses_correct_year():
    rows = [
        row("D", 60, year=2022),
        row("R", 40, year=2022),
        row("D", 55, chamber="president", district="STATE"),
        row("R", 45, chamber="president", district="STATE"),
    ]
    result = senate_benchmarks(contest_panel(rows, []), rows)[0]
    assert result["presidential_year"] == 2020
    assert result["descriptive_benchmark_gap_share_pp"] == 5
    assert result["cycle_adjusted"] is False
    assert result["causal_candidate_effect"] is False


def test_missing_presidential_benchmark_is_not_borrowed_from_another_state():
    rows = [row("D", 60), row("R", 40)]
    result = senate_benchmarks(contest_panel(rows, []), rows)[0]
    assert result["eligible_descriptive_gap"] is False
    assert result["descriptive_benchmark_gap_share_pp"] is None


def test_noncandidate_choices_reconcile_without_inventing_a_candidate():
    rows = [row("D", 60), row("R", 40)]
    totals = [
        {"contest_id": rows[0]["contest_id"], "votes": 110},
        {"contest_id": rows[0]["contest_id"], "votes": 10, "status": "noncandidate_choice"},
    ]
    result = contest_panel(rows, totals)[0]
    assert result["candidate_rows"] == 2
    assert result["all_candidate_votes"] == 100
    assert result["all_recorded_choice_votes"] == 110
    assert result["native_total_reconciled"] is True
    assert result["D_two_party_share_pct"] == 60


def test_louisiana_presidential_election_is_not_held_for_congressional_rules():
    rows = [row(party, 50, state="LA", chamber="president") for party in ("D", "R")]
    assert contest_panel(rows, [])[0]["eligible_descriptive_two_party_share"] is True
