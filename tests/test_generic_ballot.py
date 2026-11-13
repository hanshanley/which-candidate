import gzip
import json

import pytest

from which_candidate.generic_ballot import (
    POLLS,
    build,
    candidate_context,
    extract_poll,
    qualify_poll,
)
from which_candidate.storage import fingerprint, write_json


def test_siena_parser_uses_generic_total_not_named_race_or_subgroup():
    text = (
        "Governor Democrat 60% Republican 30%\n"
        "Q6. If the election for your representative in Congress was held today\n"
        "the Democrat 54% 88% 6%\nthe Republican 39% 10% 90%\n"
    )
    poll = extract_poll(POLLS[0], text)
    assert poll["democrat_pct"] == 54
    assert poll["republican_pct"] == 39
    assert poll["D_minus_R_margin_pp"] == 15
    assert poll["D_two_party_share_pct"] == pytest.approx(100 * 54 / 93)
    assert poll["margin_or_normalized_share_ci"] is None


def test_marist_parser_requires_party_order_and_statewide_total():
    text = (
        "If November's election for Congress were held today, which party's candidate\n"
        "Democrat Republican Another party\n"
        "Registered Voters 53% 44% 1%\nParty Identification Democrat 99% 1% 0%\n"
    )
    poll = extract_poll(POLLS[1], text)
    assert poll["D_two_party_share_pct"] == pytest.approx(100 * 53 / 97)
    assert poll["population"] == "registered_voters"
    with pytest.raises(ValueError, match="column order"):
        extract_poll(POLLS[1], text.replace("Democrat Republican", "Republican Democrat"))
    with pytest.raises(ValueError, match="total not found"):
        extract_poll(POLLS[1], text.replace("Registered Voters", "Women"))


@pytest.mark.parametrize(
    "changes",
    [
        {"field_end": "2026-11-04"},
        {"release_date": "2026-11-04"},
        {"release_date": "2026-11-03"},
        {"field_start": "2026-10-25"},
        {"population": "adults"},
    ],
)
def test_wrong_population_or_dates_are_not_qualified(changes):
    with pytest.raises(ValueError):
        qualify_poll({**POLLS[0], **changes}, 54, 39)


def test_absent_state_is_missing_not_zero_and_house_gets_no_prediction():
    poll = qualify_poll(POLLS[0], 54, 39)
    query = {"state": "NY", "chamber": "house", "contest_id": "NY1", "D_name": "A"}
    context = candidate_context(query, [poll])
    assert context["poll_ids"] == [poll["id"]]
    assert context["expected_candidate_vote_share"] is None
    assert context["candidate_WAR"] is None
    context = candidate_context({**query, "state": "TX"}, [poll])
    assert context["poll_ids"] == []
    assert context["status"] == "no_acquired_state_poll"


def test_house_control_is_never_relabelled_generic_vote_intention():
    text = (
        "1. Governor Shapiro 59% Garrity 34%\n"
        "2. If the election were today, would you want to see the Republican Party or the Democratic\n"
        "Party win control of the United States House of Representatives?\n"
        "Republican Party 39% 93% 2%\nDemocratic Party 54 4 95\nDK/NA 7 3 2\n"
    )
    poll = extract_poll(POLLS[2], text)
    assert poll["democrat_pct"] == 54
    assert poll["D_two_party_share_pct"] is None
    query = {"state": "PA", "chamber": "house", "contest_id": "PA1"}
    context = candidate_context(query, [poll])
    assert context["generic_vote_intention_poll_ids"] == []
    assert context["house_control_preference_poll_ids"] == [poll["id"]]


def test_offline_build_retains_all_queries_and_rejects_changed_packet(tmp_path, monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("Offline poll build attempted network access")

    monkeypatch.setattr("socket.socket.connect", no_network)
    packet = tmp_path / POLLS[0]["file"]
    packet.write_bytes(b"synthetic packet parsed by the test reader")
    manifest = tmp_path / "manifest.json"
    write_json(
        manifest,
        {"sources": [{"id": POLLS[0]["id"], "file": packet.name, **fingerprint(packet)}]},
    )
    text = (
        "Q6. If the election for your representative in Congress was held today\n"
        "the Democrat 54% 88%\nthe Republican 39% 10%\n"
    )

    class Page:
        def extract_text(self, **kwargs):
            return text

    class Reader:
        pages = [Page()]

        def __init__(self, path):
            pass

    monkeypatch.setattr("which_candidate.generic_ballot.POLLS", POLLS[:1])
    monkeypatch.setattr("which_candidate.generic_ballot.PdfReader", Reader)
    queries = [
        {"contest_id": "NY1", "state": "NY", "chamber": "house"},
        {"contest_id": "TX1", "state": "TX", "chamber": "senate"},
    ]
    output = tmp_path / "output"
    build(tmp_path, manifest, queries, output)
    with gzip.open(output / "candidate-poll-queries.jsonl.gz", "rt") as handle:
        rows = [json.loads(line) for line in handle]
    assert [row["contest_id"] for row in rows] == ["NY1", "TX1"]
    coverage = json.loads((output / "state-coverage.json").read_text())
    assert len(coverage["all_50_states"]) == 50
    assert coverage["all_50_states"]["TX"] == []
    assert coverage["generic_vote_intention_states"] == ["NY"]
    assert coverage["house_control_preference_states"] == []
    before = {path.name: path.read_bytes() for path in output.iterdir()}
    build(tmp_path, manifest, queries, output)
    assert before == {path.name: path.read_bytes() for path in output.iterdir()}
    packet.write_bytes(b"changed")
    with pytest.raises(ValueError, match="Pinned poll packet changed"):
        build(tmp_path, manifest, queries, output)
