import re
from collections import defaultdict

import openpyxl
from pypdf import PdfReader

from .fec import STATES, normalized
from .panel import contest_panel

STATE_NAMES = dict(
    pair.split(":")
    for pair in (
        "AL:ALABAMA|AK:ALASKA|AZ:ARIZONA|AR:ARKANSAS|CA:CALIFORNIA|CO:COLORADO|"
        "CT:CONNECTICUT|DE:DELAWARE|FL:FLORIDA|GA:GEORGIA|HI:HAWAII|ID:IDAHO|"
        "IL:ILLINOIS|IN:INDIANA|IA:IOWA|KS:KANSAS|KY:KENTUCKY|LA:LOUISIANA|"
        "ME:MAINE|MD:MARYLAND|MA:MASSACHUSETTS|MI:MICHIGAN|MN:MINNESOTA|"
        "MS:MISSISSIPPI|MO:MISSOURI|MT:MONTANA|NE:NEBRASKA|NV:NEVADA|"
        "NH:NEW HAMPSHIRE|NJ:NEW JERSEY|NM:NEW MEXICO|NY:NEW YORK|"
        "NC:NORTH CAROLINA|ND:NORTH DAKOTA|OH:OHIO|OK:OKLAHOMA|OR:OREGON|"
        "PA:PENNSYLVANIA|RI:RHODE ISLAND|SC:SOUTH CAROLINA|SD:SOUTH DAKOTA|"
        "TN:TENNESSEE|TX:TEXAS|UT:UTAH|VT:VERMONT|VA:VIRGINIA|WA:WASHINGTON|"
        "WV:WEST VIRGINIA|WI:WISCONSIN|WY:WYOMING"
    ).split("|")
)


def district_presidential(path, spec):
    year = spec["map_year"]
    if spec["presidential_year"] != (year if year % 4 == 0 else year - 2):
        raise ValueError("Presidential/map-year qualification mismatch")
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheet = workbook["Percentages" if year >= 2024 else "Results"]
    result = []
    try:
        for number, cells in enumerate(sheet.iter_rows(max_col=9, values_only=True), 1):
            if not isinstance(cells[0], str):
                continue
            match = re.fullmatch(r"([A-Z]{2})-(AL|\d{2})", cells[0])
            if not match:
                continue
            state, district = match.groups()
            if state not in STATES:
                continue
            district = "00" if district == "AL" else district
            d, r = cells[3:5]
            if not all(type(value) in (float, int) and value >= 0 for value in (d, r)):
                raise ValueError(f"Invalid presidential shares: {cells[0]}")
            if d + r <= 0:
                raise ValueError("Empty presidential denominator")
            row = {
                "map_year": year,
                "state": state,
                "district": district,
                "geography_vintage": f"{year}:house:{state}:{district}",
                "presidential_year": spec["presidential_year"],
                "presidential_D_two_party_share_pct": 100 * d / (d + r),
                "native_D_value": d,
                "native_R_value": r,
                "source_id": spec["id"],
                "source_sheet": sheet.title,
                "source_row": number,
                "qualification": "publisher_explicit_election_map; not independently_boundary_audited",
                "source_precision": "published_rounded_percentages"
                if year in (2016, 2018)
                else "published_calculated_percentages",
                "source_status": "publisher_calculated_estimate_not_certified_district_compilation",
            }
            if year == 2024:
                previous_d, previous_r = cells[6:8]
                row["alternate_presidential_year"] = 2020
                row["alternate_D_two_party_share_pct"] = (
                    100 * previous_d / (previous_d + previous_r)
                )
            result.append(row)
    finally:
        workbook.close()
    if len(result) != 435 or len({(r["state"], r["district"]) for r in result}) != 435:
        raise ValueError(f"Expected 435 unique map-qualified benchmarks for {year}")
    return result


def presidential_2024(path, spec):
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    sheet = workbook["OFFICIAL 2024 PRES GE RESULTS"]
    result = []
    try:
        header = next(sheet.iter_rows(values_only=True))
        if header[12] != "HARRIS" or header[24] != "TRUMP" or header[30] != "TOTAL VOTES":
            raise ValueError("Changed FEC 2024 presidential schema")
        for number, cells in enumerate(sheet.iter_rows(min_row=2, values_only=True), 2):
            if cells[0] not in STATES:
                continue
            values = cells[4:30]
            if any(value is not None and type(value) not in (int, float) for value in values):
                raise ValueError("Nonnumeric 2024 presidential count")
            total = sum(value or 0 for value in values)
            reconciled = total == cells[30]
            d, r = cells[12], cells[24]
            result.append(
                {
                    "year": 2024,
                    "state": cells[0],
                    "D_votes": d,
                    "R_votes": r,
                    "all_choice_votes": total,
                    "native_total": cells[30],
                    "native_total_reconciled": reconciled,
                    "presidential_D_two_party_share_pct": 100 * d / (d + r) if reconciled else None,
                    "source_id": spec["id"],
                    "source_sheet": sheet.title,
                    "source_row": number,
                }
            )
    finally:
        workbook.close()
    if len(result) != 50 or len({r["state"] for r in result}) != 50:
        raise ValueError("Expected 50 unique state presidential returns")
    return result


def clerk_senate_2024(path, spec):
    reader = PdfReader(path)
    state_lookup = {name: code for code, name in STATE_NAMES.items()}
    state, active, district = None, False, "STATE"
    groups, native, decisions, pages = defaultdict(list), [], [], []
    for page_number, page in enumerate(reader.pages, 1):
        text = page.extract_text(extraction_mode="layout")
        pages.append({"source_id": spec["id"], "page": page_number, "text": text})
        for line_number, raw in enumerate(text.splitlines(), 1):
            line = raw.strip()
            heading = line.split("\u2014")[0].strip()
            if heading in state_lookup:
                if state != state_lookup[heading]:
                    state, active, district = state_lookup[heading], False, "STATE"
                continue
            if line == str(page_number - 2):
                continue
            if line.startswith("FOR UNITED STATES SENATOR"):
                if state is None:
                    raise ValueError("Senate section without state")
                if "Continued" not in line:
                    district = "STATE"
                active = True
                continue
            if active and ("FOR UNITED STATES REPRESENTATIVE" in line or "Recapitulation" in line):
                active = False
            if not active or not line:
                continue
            reference = {
                "source_id": spec["id"],
                "page": page_number,
                "line": line_number,
                "text": line,
                "state": state,
            }
            native.append(reference)
            if line.startswith("(For unexpired"):
                district = "UNEXPIRED"
                decisions.append({**reference, "status": "special_election_scope"})
                continue
            if line.startswith("(For full term"):
                district = "STATE"
                decisions.append({**reference, "status": "regular_election_scope"})
                continue
            match = re.fullmatch(r"(.+?)\s*\.{3,}\s*([\d,]+)", line)
            if not match:
                raise ValueError(f"Unparsed Clerk Senate line {page_number}:{line_number}: {line}")
            label, count = match.groups()
            votes = int(count.replace(",", ""))
            if ", " not in label:
                decisions.append({**reference, "votes": votes, "status": "noncandidate_choice"})
                continue
            # Candidate suffixes contain commas; the final party delimiter is unambiguous.
            name, party = label.rsplit(", ", 1)
            # Write-in labels may themselves contain no final candidate/party split.
            if "Write-in (" in label:
                name, party = label.split(", Write-in (", 1)
                party = "Write-in (" + party
            group = (
                "D"
                if party
                in (
                    "Democrat",
                    "Democratic",
                    "Democratic-Farmer-Labor",
                    "Democratic-Nonpartisan League",
                    "Working Families",
                )
                else "R"
                if party in ("Republican", "Conservative")
                else "O"
            )
            contest_id = f"2024:senate:{state}:{district}:general:source_general"
            groups[(contest_id, normalized(name))].append(
                {
                    **reference,
                    "name": name,
                    "party": party,
                    "party_group": group,
                    "votes": votes,
                    "district": district,
                    "contest_id": contest_id,
                }
            )
            decisions.append({**reference, "votes": votes, "status": "candidate_party_line"})
    candidates = []
    for (contest_id, key), rows in sorted(groups.items()):
        first = rows[0]
        parties = {r["party_group"] for r in rows} - {"O"}
        candidates.append(
            {
                "candidate_election_id": f"{contest_id}:clerk:{key}",
                "contest_id": contest_id,
                "year": 2024,
                "chamber": "senate",
                "state": first["state"],
                "district": first["district"],
                "election_date": "2024-11-05",
                "name": first["name"],
                "fec_id": None,
                "party_group": next(iter(parties)) if len(parties) == 1 else "O",
                "literal_parties": sorted({r["party"] for r in rows}),
                "votes": sum(r["votes"] for r in rows),
                "named_candidate": True,
                "source_incumbent": None,
                "source_status": "official_clerk_compilation",
                "source_id": spec["id"],
                "source_rows": rows,
                "issues": ["conflicting_party_identity"] if len(parties) > 1 else [],
                "boundary_comparability_verified": True,
            }
        )
    contests = contest_panel(candidates, [])
    if len(contests) != 35:
        raise ValueError(
            f"Expected 33 regular plus 2 special 2024 Senate contests, got {len(contests)}"
        )
    return candidates, contests, pages, native, decisions
