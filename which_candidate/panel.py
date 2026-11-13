import json
import re
from collections import Counter, defaultdict

from .fec import GENERIC


def audit_candidates(path, spec):
    audit = json.loads(path.read_bytes())
    districts = audit["district_queries"]
    if len(districts) != 435 or len({row["district"] for row in districts}) != 435:
        raise ValueError("The complete unique 435-district House audit is required")
    result = []
    for district_index, district in enumerate(districts):
        for endpoint, year in (("previous", 2024), ("current", 2026)):
            for index, row in enumerate(district[endpoint]["source_candidate_rows"]):
                code, native_district = district["district"].split("-", 1)
                contest_id = f"{year}:house:{code}:{native_district}:general:source_general"
                votes = row["votes"]
                if votes is not None and (type(votes) is not int or votes < 0):
                    raise ValueError("Audit contains invalid count")
                result.append(
                    {
                        "candidate_election_id": f"{contest_id}:audit:{index}",
                        "contest_id": contest_id,
                        "year": year,
                        "chamber": "house",
                        "state": district["state_code"],
                        "district": district["district"].split("-", 1)[1],
                        "election_date": f"{year}-11-{'05' if year == 2024 else '03'}",
                        "date_scope": "regular_general_date; round unqualified",
                        "stage": "general",
                        "counting_round": "source_general",
                        "name": row["name"],
                        "fec_id": None,
                        "party_group": row["group"],
                        "literal_parties": row["literal_parties"],
                        "votes": votes,
                        "named_candidate": row["named"]
                        and not bool(GENERIC.fullmatch(row["name"])),
                        "source_incumbent": None,
                        "incumbency_independently_verified": False,
                        "source_status": "held_clerk_factual_query"
                        if year == 2024
                        else "provisional_provider_snapshot",
                        "source_updated_at": row.get("source_updated_at"),
                        "origin_url": row.get("source_url"),
                        "cross_election_identity_verified": False,
                        "boundary_comparability_verified": district[
                            "geographic_boundary_stability_independently_qualified"
                        ],
                        "issues": [] if votes is not None else ["missing_or_nonnumeric_votes"],
                        "source_id": spec["id"],
                        "source_rows": [
                            {
                                "source_id": spec["id"],
                                "json_pointer": (
                                    f"/district_queries/{district_index}/"
                                    f"{endpoint}/source_candidate_rows/{index}"
                                ),
                            }
                        ],
                        "combined_total_references": [],
                    }
                )
    return result


def contest_panel(candidates, accounting):
    groups, expected_totals, other_choices = defaultdict(list), defaultdict(list), defaultdict(list)
    identities = [row["candidate_election_id"] for row in candidates]
    if len(identities) != len(set(identities)):
        raise ValueError("Duplicate candidate-election ID")
    for row in candidates:
        groups[row["contest_id"]].append(row)
    for row in accounting:
        target = other_choices if row.get("status") == "noncandidate_choice" else expected_totals
        target[row["contest_id"]].append(row["votes"])
    contests = []
    for contest_id, rows in sorted(groups.items()):
        first = rows[0]
        major = {
            party: [row for row in rows if row["party_group"] == party and row["named_candidate"]]
            for party in ("D", "R")
        }
        counts = {
            party: sum(row["votes"] for row in rows if row["party_group"] == party)
            if all(row["votes"] is not None for row in rows if row["party_group"] == party)
            else None
            for party in ("D", "R", "O")
        }
        reasons = sorted({issue for row in rows for issue in row["issues"]})
        for party in ("D", "R"):
            if len(major[party]) != 1:
                reasons.append(f"requires_one_named_{party}_nominee")
        district = first["district"]
        if "UNEXPIRED" in district or "SPECIAL" in district:
            reasons.append("special_election_scope_unqualified")
        if first["state"] == "LA" and first["chamber"] != "president":
            reasons.append("louisiana_stage_unqualified")
        if (first["state"] == "AK" and first["year"] >= 2022) or (
            first["state"] == "ME" and first["year"] >= 2018
        ):
            reasons.append("ranked_choice_round_unqualified")
        if any(value is None for value in counts.values()):
            reasons.append("incomplete_candidate_counts")
        candidate_total = sum(counts.values()) if None not in counts.values() else None
        noncandidate_votes = sum(other_choices[contest_id])
        contest_total = (
            candidate_total + noncandidate_votes if candidate_total is not None else None
        )
        source_totals = sorted(set(expected_totals[contest_id]))
        if source_totals and (
            len(source_totals) != 1
            or (contest_total is not None and contest_total != source_totals[0])
        ):
            reasons.append("native_contest_total_mismatch")
        denominator = (
            counts["D"] + counts["R"] if counts["D"] is not None and counts["R"] is not None else 0
        )
        if denominator <= 0:
            reasons.append("no_positive_two_party_denominator")
        qualified = not reasons
        share = 100 * counts["D"] / denominator if qualified else None
        contests.append(
            {
                "contest_id": contest_id,
                "year": first["year"],
                "chamber": first["chamber"],
                "state": first["state"],
                "district": district,
                "source_id": first["source_id"],
                "source_status": first["source_status"],
                "source_updated_at_values": sorted(
                    {r["source_updated_at"] for r in rows if r.get("source_updated_at")}
                ),
                "stage": first.get("stage"),
                "counting_round": first.get("counting_round"),
                "candidate_rows": len(rows),
                "named_D_nominees": len(major["D"]),
                "named_R_nominees": len(major["R"]),
                "D_votes": counts["D"],
                "R_votes": counts["R"],
                "O_votes": counts["O"],
                "all_candidate_votes": candidate_total,
                "noncandidate_choice_votes": noncandidate_votes,
                "all_recorded_choice_votes": contest_total,
                "native_contest_total_references": source_totals,
                "native_total_reconciled": contest_total == source_totals[0]
                if len(source_totals) == 1 and contest_total is not None
                else None,
                "eligible_descriptive_two_party_share": qualified,
                "exclusion_reasons": sorted(set(reasons)),
                "D_two_party_share_pct": share,
                "D_minus_R_margin_pp": 2 * share - 100 if share is not None else None,
                "eligible_adjusted_overperformance": False,
                "adjusted_overperformance_hold": "partisan_benchmark_and_cycle_model_not_yet_qualified",
                "boundary_comparability_verified": first["boundary_comparability_verified"],
                "D_candidate_election_id": major["D"][0]["candidate_election_id"]
                if len(major["D"]) == 1
                else None,
            }
        )
    return contests


def senate_2026_candidates(path, spec):
    audit = json.loads(path.read_bytes())
    if audit["contract"] != "participation.ak_senate_native_scope.v1":
        raise ValueError("Unsupported statewide Senate control audit")
    selected = [
        (i, row) for i, row in enumerate(audit["control_decisions"]) if row["provider"] == "civic"
    ]
    expected_states = set(
        "AL AK AR CO DE FL GA ID IL IA KS KY LA ME MA MI MN MS MT NE NH NJ NM NC OH OK OR RI SC SD TN TX VA WV WY".split()
    )
    if {r["state"] for _, r in selected} != expected_states:
        raise ValueError("Incomplete 35-race 2026 Senate query")
    seen, result = set(), []
    for index, row in selected:
        state, name = row["state"], row["candidate"]
        if (state, name) in seen:
            raise ValueError("Duplicate statewide Senate candidate")
        seen.add((state, name))
        votes = str(row["native_state_votes"])
        if not re.fullmatch(r"\d+", votes):
            raise ValueError("Invalid native statewide Senate count")
        stage = "general_special" if state in ("FL", "OH") else "general"
        contest_id = f"2026:senate:{state}:STATE:{stage}:source_general"
        party = row["party"]
        result.append(
            {
                "candidate_election_id": f"{contest_id}:audit:{index}",
                "contest_id": contest_id,
                "year": 2026,
                "chamber": "senate",
                "state": state,
                "district": "STATE",
                "election_date": "2026-11-03",
                "date_scope": "2026 general; FL/OH special seats separately identified",
                "stage": stage,
                "counting_round": row["native_round"],
                "name": name,
                "fec_id": None,
                "party_group": "D"
                if party in ("Democratic", "Democratic-Farmer-Labor")
                else "R"
                if party == "Republican"
                else "O",
                "literal_parties": [party],
                "votes": int(votes),
                "named_candidate": not bool(GENERIC.fullmatch(name)),
                "source_incumbent": None,
                "source_status": "provisional_provider_state_total_in_derived_audit",
                "source_updated_at": row["native_updated"],
                "origin_url": spec["origin_url"],
                "boundary_comparability_verified": True,
                "issues": [],
                "source_id": spec["id"],
                "source_rows": [
                    {"source_id": spec["id"], "json_pointer": f"/control_decisions/{index}"}
                ],
                "native_accounting_evidence": row,
                "combined_total_references": [],
            }
        )
    return result


def senate_benchmarks(contests, candidates):
    lookup = {
        (row["year"], row["state"]): row
        for row in contests
        if row["chamber"] == "president" and row["eligible_descriptive_two_party_share"]
    }
    people = {row["candidate_election_id"]: row for row in candidates}
    result = []
    for row in contests:
        if row["chamber"] != "senate":
            continue
        benchmark_year = row["year"] if row["year"] % 4 == 0 else row["year"] - 2
        benchmark = lookup.get((benchmark_year, row["state"]))
        reasons = list(row["exclusion_reasons"])
        if benchmark is None:
            reasons.append("qualified_presidential_state_benchmark_missing")
        qualified = not reasons
        candidate = people.get(row["D_candidate_election_id"], {})
        result.append(
            {
                "contest_id": row["contest_id"],
                "year": row["year"],
                "state": row["state"],
                "district": row["district"],
                "D_candidate": candidate.get("name"),
                "D_candidate_election_id": row["D_candidate_election_id"],
                "source_incumbent": candidate.get("source_incumbent"),
                "presidential_year": benchmark_year,
                "presidential_contest_id": benchmark["contest_id"] if benchmark else None,
                "D_two_party_share_pct": row["D_two_party_share_pct"],
                "presidential_D_two_party_share_pct": benchmark["D_two_party_share_pct"]
                if benchmark
                else None,
                "descriptive_benchmark_gap_share_pp": (
                    row["D_two_party_share_pct"] - benchmark["D_two_party_share_pct"]
                    if qualified
                    else None
                ),
                "eligible_descriptive_gap": qualified,
                "exclusion_reasons": sorted(set(reasons)),
                "cycle_adjusted": False,
                "causal_candidate_effect": False,
            }
        )
    return result


def coverage(candidates, contests, native, decisions, benchmarks):
    counts = Counter((row["year"], row["chamber"]) for row in candidates)
    groups = []
    for (year, chamber), count in sorted(counts.items()):
        rows = [row for row in contests if row["year"] == year and row["chamber"] == chamber]
        groups.append(
            {
                "year": year,
                "chamber": chamber,
                "candidate_rows": count,
                "contests": len(rows),
                "descriptive_share_eligible": sum(
                    row["eligible_descriptive_two_party_share"] for row in rows
                ),
                "adjusted_overperformance_eligible": 0,
            }
        )
    return {
        "schema": "which_candidate.coverage.v1",
        "native_fec_rows": len(native),
        "fec_row_decisions": len(decisions),
        "candidate_rows": len(candidates),
        "contests": len(contests),
        "groups": groups,
        "eligible_senate_descriptive_gaps": sum(
            row["eligible_descriptive_gap"] for row in benchmarks
        ),
        "contests_with_reconciled_native_totals": sum(
            row["native_total_reconciled"] is True for row in contests
        ),
        "contests_with_native_total_mismatch": sum(
            row["native_total_reconciled"] is False for row in contests
        ),
        "qualified_characteristic_analysis": False,
        "limits": [
            "Historical FEC congressional coverage currently stops at 2022.",
            "2024 and provisional 2026 House rows are imported from the complete participation audit.",
            "This base returns stage excludes supplemental Senate outcomes; the analysis stage imports 2024/2026.",
            "House district benchmarks and map qualifications are added in the analysis stage.",
            "Senate presidential gaps are descriptive, not cycle-adjusted candidate effects.",
            "Candidate identities, legislative features and biographies are added in the analysis stage.",
        ],
    }
