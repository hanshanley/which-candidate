import pytest

from which_candidate.source_milestone import caucus_decisions, require_complete


def test_complete_query_check_rejects_replaced_or_duplicate_contests():
    expected = [{"contest_id": "one"}, {"contest_id": "two"}]
    require_complete(expected, expected)
    for actual in (expected[:1], [expected[0], expected[0]], [{"contest_id": "other"}]):
        with pytest.raises(ValueError, match="contest queries"):
            require_complete(expected, actual)


def test_caucus_attrition_retains_absent_members_and_model_holds():
    memberships = [
        {"year": 2026, "group": "blue_dog", "name": "A"},
        {"year": 2026, "group": "blue_dog", "name": "Absent"},
    ]
    query = {
        "chamber": "house",
        "blue_dog": True,
        "blue_dog_evidence": [memberships[0]],
        "contest_id": "one",
        "D_name": "A",
        "D_candidate_election_id": "candidate-one",
        "eligible": True,
        "analysis_exclusion_reasons": [],
    }
    decisions = caucus_decisions([query], memberships, [])
    assert len(decisions) == 2
    assert decisions[0]["candidate_decisions"][0]["eligible_v3"]
    assert not decisions[0]["candidate_decisions"][0]["in_frozen_membership_model"]
    assert decisions[1]["status"] == "not_matched_to_a_2026_nominee"
