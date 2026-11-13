import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime

import openpyxl

STATES = set(
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT "
    "NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split()
)
ELECTION_DATES = {2016: "2016-11-08", 2018: "2018-11-06", 2020: "2020-11-03", 2022: "2022-11-08"}
DEMOCRATIC = {"D", "DEM", "DFL", "D-NPL", "DNL"}
REPUBLICAN = {"R", "REP", "REP/AIP"}
PRESIDENTIAL_NOMINEES = {
    2016: {"D": "P00003392", "R": "P80001571"},
    2020: {"D": "P80000722", "R": "P80001571"},
}
GENERIC = re.compile(r"^(scattered|scattering|write[- ]?ins?|all others|other votes)[,. ]*$", re.I)


def text(value):
    return str(value).strip() if value is not None else ""


def normalized(value):
    return " ".join(unicodedata.normalize("NFKC", text(value)).casefold().split())


def integer(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and value >= 0 and int(value) == value:
        return int(value)
    if isinstance(value, str) and re.fullmatch(r"\d+", value.strip()):
        return int(value)
    return None


def serial(value):
    return value.isoformat() if isinstance(value, (date, datetime)) else value


def district_key(value, chamber):
    value = " ".join(text(value).upper().split())
    if chamber == "president":
        return "STATE"
    if chamber == "house":
        match = re.fullmatch(r"(\d{1,2})\s*(.*)", value)
        if match:
            base, suffix = match.groups()
            return str(int(base)).zfill(2) + re.sub(r"\s+", "", suffix)
    return re.sub(r"\s+", "", value)


def selected_sheets(workbook):
    selected = {}
    for title in workbook.sheetnames:
        lower = title.lower()
        if "senate results by state" in lower:
            selected[title] = "senate"
        elif "house results by state" in lower:
            selected[title] = "house"
        elif "pres general results" in lower:
            selected[title] = "president"
    return selected


def extract_workbook(path, spec):
    native, decisions, candidates, accounting = [], [], [], []
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        sheets = selected_sheets(workbook)
        expected = {"house", "senate"} | ({"president"} if spec["year"] in (2016, 2020) else set())
        if set(sheets.values()) != expected or len(sheets) != len(expected):
            raise ValueError("Unexpected FEC worksheet selection")
        for title, chamber in sheets.items():
            sheet_rows = []
            # Some originals have formatting through column XFD, not actual fields there.
            for number, cells in enumerate(
                workbook[title].iter_rows(max_col=40, values_only=True), 1
            ):
                values = [serial(value) for value in cells]
                while values and values[-1] is None:
                    values.pop()
                if not any(value is not None for value in values):
                    continue
                row = {
                    "source_id": spec["id"],
                    "sheet": title,
                    "source_row": number,
                    "cells": values,
                }
                native.append(row)
                sheet_rows.append(row)
            rows, dispositions, totals = parse_sheet(sheet_rows, spec["year"], chamber)
            candidates.extend(rows)
            decisions.extend(dispositions)
            accounting.extend(totals)
    finally:
        workbook.close()
    return native, decisions, candidates, accounting


def parse_sheet(native, year, chamber):
    if not native or native[0]["source_row"] != 1:
        raise ValueError("FEC header missing")
    header = [text(value).upper() for value in native[0]["cells"]]
    state_i, name_i, party_i, votes_i, id_i = (
        (3, 7, 9, 10, 1) if chamber == "president" else (1, 8, 10, 15, 4)
    )
    if "STATE" not in header[state_i] or "PARTY" != header[party_i]:
        raise ValueError("Unexpected FEC state/party schema")
    expected = "GENERAL RESULTS" if chamber == "president" else "GENERAL VOTES"
    if header[votes_i] != expected:
        raise ValueError("Unexpected FEC general vote column")
    combined_i = next(
        (i for i, value in enumerate(header) if "COMBINED" in value and "%" not in value), None
    )
    footnotes_i = next((i for i, value in enumerate(header) if value == "FOOTNOTES"), None)
    if chamber == "president" and year == 2016:
        combined_i = 11
    groups, decisions, totals = defaultdict(list), [], []
    senate_scopes = defaultdict(set)
    if chamber == "senate":
        for item in native[1:]:
            cells = item["cells"] + [None] * (40 - len(item["cells"]))
            if text(cells[1]) in STATES and text(cells[3]):
                senate_scopes[text(cells[1])].add(district_key(cells[3], chamber))
    for native_row in native[1:]:
        values = native_row["cells"] + [None] * (40 - len(native_row["cells"]))
        state = text(values[state_i]).upper()
        name, party = text(values[name_i]), text(values[party_i])
        district = district_key(values[3], chamber)
        scope_resolution = "native_district"
        if not district and chamber == "senate" and len(senate_scopes[state]) == 1:
            district = next(iter(senate_scopes[state]))
            scope_resolution = "unique_native_senate_contest_within_state_sheet"
        contest_id = f"{year}:{chamber}:{state}:{district}:general:source_general"
        decision = {key: native_row[key] for key in ("source_id", "sheet", "source_row")}
        decision["contest_id"] = contest_id
        decision["scope_resolution"] = scope_resolution
        decision["status"] = "noncandidate_or_outside_selected_jurisdictions"
        marker = text(values[8] if chamber == "president" else values[9])
        if chamber == "president" and state in STATES and marker == "Total State Votes:":
            total = integer(values[11 if year == 2016 else 12])
            if total is not None:
                totals.append(dict(decision, votes=total, native_marker=marker))
        if state in STATES and marker and integer(values[votes_i]) is not None:
            if (chamber == "senate" and marker == "Total State Votes:") or (
                chamber == "house" and "District Votes:" in marker
            ):
                totals.append(dict(decision, votes=integer(values[votes_i]), native_marker=marker))
        if state in STATES and not marker and integer(values[votes_i]) is not None:
            if name == "None of These Candidates" or (not name and party == "W"):
                decision["status"] = "noncandidate_choice"
                decisions.append(decision)
                totals.append(
                    dict(
                        decision,
                        votes=integer(values[votes_i]),
                        native_marker=name or "unnamed write-ins",
                    )
                )
                continue
        if state not in STATES or not name or not party or marker:
            decisions.append(decision)
            continue
        raw_count = values[votes_i]
        note = text(values[footnotes_i]) if footnotes_i is not None else ""
        if (
            year == 2020
            and state == "MT"
            and chamber in ("house", "senate")
            and party == "GRE"
            and raw_count == "#"
            and note
            == "# The Montana Green Party candidates were removed from the general election "
            "ballot in August 2020 by court order."
        ):
            decision["status"] = "removed_from_general_ballot_native_note"
            decision["native_note"] = note
            decisions.append(decision)
            continue
        combined = values[combined_i] if combined_i is not None else None
        if raw_count is None and integer(combined) is None:
            decision["status"] = "no_general_vote_entry"
            decisions.append(decision)
            continue
        fec_id = text(values[id_i])
        verified_id = fec_id if re.fullmatch(r"[HSP][A-Z0-9]{8}", fec_id) else None
        local_id = verified_id or "name:" + normalized(name)
        if not district or (chamber == "house" and district == "H"):
            decision["status"] = "unresolved_contest_scope"
            decisions.append(decision)
            continue
        decision["status"] = (
            "combined_reference" if party == "Combined Parties:" else "candidate_party_line"
        )
        decisions.append(decision)
        groups[contest_id, local_id].append(
            {
                "source": decision,
                "name": name,
                "fec_id": verified_id,
                "party": party,
                "votes": integer(raw_count),
                "native_votes": raw_count,
                "combined_votes": integer(combined),
                "general_runoff_votes": integer(values[17]) if chamber != "president" else None,
                "incumbent_marker": text(values[5]) if chamber != "president" else None,
                "state": state,
                "district": district,
            }
        )
    result = []
    for (contest_id, local_id), lines in sorted(groups.items()):
        row = combine_lines(lines)
        row.update(
            candidate_election_id=f"{contest_id}:{local_id}",
            contest_id=contest_id,
            year=year,
            chamber=chamber,
            election_date=None
            if "UNEXPIRED" in lines[0]["district"] or "SPECIAL" in lines[0]["district"]
            else ELECTION_DATES[year],
            date_scope="regular_general_date; special dates not independently qualified",
            state=lines[0]["state"],
            district=lines[0]["district"],
            source_id=lines[0]["source"]["source_id"],
            stage="general",
            counting_round="source_general",
            source_status="official_fec_historical_compilation",
            cross_election_identity_verified=False,
            boundary_comparability_verified=False,
        )
        if chamber == "president":
            nominees = PRESIDENTIAL_NOMINEES[year]
            row["party_group"] = next(
                (party for party, fec_id in nominees.items() if row["fec_id"] == fec_id), "O"
            )
            row["party_classification"] = "national_presidential_nominee_fec_id"
        result.append(row)
    return result, decisions, totals


def combine_lines(lines):
    parts = [line for line in lines if line["party"] != "Combined Parties:"]
    parties = {line["party"] for line in parts}
    major = ("D" if parties & DEMOCRATIC else "") + ("R" if parties & REPUBLICAN else "")
    counts = [line["votes"] for line in parts]
    total = sum(counts) if counts and all(count is not None for count in counts) else None
    combined = {line["combined_votes"] for line in lines if line["combined_votes"] is not None}
    issues = []
    if len(parts) != len(parties):
        issues.append("duplicate_party_lines")
    if total is None:
        issues.append("missing_or_nonnumeric_votes")
    if len(combined) > 1 or (combined and total not in combined):
        issues.append("fusion_total_mismatch")
    if major == "DR":
        issues.append("conflicting_major_party_labels")
    if any(line.get("general_runoff_votes") is not None for line in lines):
        issues.append("general_runoff_stage_unqualified")
    names = sorted({line["name"] for line in lines})
    if len({normalized(name) for name in names}) > 1:
        issues.append("candidate_identity_name_conflict")
    first = lines[0]
    return {
        "name": first["name"],
        "native_name_aliases": names,
        "fec_id": first["fec_id"],
        "party_group": major if major in ("D", "R") else "O",
        "literal_parties": sorted(parties),
        "votes": total,
        "named_candidate": not bool(GENERIC.fullmatch(first["name"])),
        "source_incumbent": any(line["incumbent_marker"] == "(I)" for line in parts),
        "incumbency_independently_verified": False,
        "issues": issues,
        "source_rows": [line["source"] for line in lines],
        "combined_total_references": sorted(combined),
    }
