"""Persist actual CongressData codes and native-person military-support decisions."""

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from .characteristics_v7_extract import retained_members, stable_member
from .house_characteristics import write_csv
from .storage import read_rows, write_json


def build(root):
    root = Path(root)
    work = root / "artifacts/characteristics-v7"
    receipts = {r["id"]: r for r in json.loads((work / "retrievals.json").read_text())}
    grouped = defaultdict(list)
    with (work / "congressdata-selected-member-years.csv").open() as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames
        records = list(reader)
    for row in records:
        if row["year"] and int(row["year"]) <= 2026:
            grouped[row["bioguide"]].append(row)
    members = retained_members(root)
    previous = {
        r["candidate_id"]: r
        for r in read_rows(root / "results/house-characteristics-v6/candidate-traits.jsonl.gz")
        if r["trait"] == "military"
    }
    positive = {
        "Enlisted rank, non-officer or rank unspecified",
        "Captain/Lieutenant",
        "Lieutenant/Ensign or officer with rank unspecified",
        "Major/Lieutenant Commander",
        "General/Admiral",
        "Colonel/Captain",
        "Lieutenant Colonel/Commander",
    }
    decisions = []
    for candidate in read_rows(root / "results/house/candidates.jsonl.gz"):
        member = stable_member(candidate, members)
        if not member:
            continue
        matched = grouped[member["id"]["bioguide"]]
        codes = sorted({r["MILITARY"] for r in matched if r["MILITARY"]})
        decisions.append(
            {
                "candidate_id": candidate["candidate_id"],
                "name": candidate["name"],
                "party": candidate["party"],
                "state": candidate["state"],
                "bioguide": member["id"]["bioguide"],
                "native_fec_id": candidate["identity"]["fec_id"],
                "matched_member_years": len(matched),
                "literal_military_codes": codes,
                "explicit_historical_positive": bool(set(codes) & positive),
                "omission_not_negative": "No military service mentioned" in codes,
                "baseline_analysis_eligible": previous[candidate["candidate_id"]][
                    "analysis_eligible"
                ],
                "decision": "No-service-mentioned and missing codes never qualify nonservice; "
                "positive codes reviewed separately against existing support.",
            }
        )
    result = {
        "originals": {
            key: {k: receipts[key][k] for k in ("url", "sha256", "bytes")}
            for key in ("congressdata-current-data", "congressdata-current-codebook")
        },
        "reader": (work / "congressdata-reader.txt").read_text().splitlines(),
        "selected_columns": columns,
        "member_year_rows": len(records),
        "actual_MILITARY_value_counts": dict(
            sorted(Counter(r["MILITARY"] for r in records).items())
        ),
        "explicit_positive_codes": sorted(positive),
        "new_positive_D_candidates_needing_qualification": [
            d["candidate_id"]
            for d in decisions
            if d["party"] == "Democratic"
            and d["explicit_historical_positive"]
            and not d["baseline_analysis_eligible"]
        ],
        "variable_decisions": {
            "MILITARY/military_rank": "Actual no-service-mentioned category/rank zero is not explicit nonservice.",
            "military": "Not a verified binary service indicator; no import.",
            "inc_pol_exp_any/PRIOR": "Before-Congress experience is not no-office-before-2026.",
            "inc_educ_undergrad/postgrad": "Degree-or-equivalent flags do not identify specific completed credentials.",
            "inc_business_exp/law_exp/educ_exp": "Broad historical categories do not silently replace narrower occupation definitions.",
            "inc_race/gender": "No import without verified provenance and identity-coding method; no inferred identity.",
            "birthday": "Retained independently linked congressional identities already supply qualified exact birthdays.",
        },
    }
    write_json(root / "data/house-characteristics-v7-congressdata-audit.json", result)
    write_csv(root / "data/house-characteristics-v7-congressdata-person-review.csv", decisions)
    return result


if __name__ == "__main__":
    print(json.dumps(build(Path(__file__).resolve().parents[1]), indent=2))
