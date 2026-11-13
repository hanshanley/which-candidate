import csv
import gzip
import io
import re
import zipfile
from collections import defaultdict
from datetime import date
from html.parser import HTMLParser

from pypdf import PdfReader

from .benchmarks import STATE_NAMES
from .storage import confined

RELIGIONS = (
    "catholic",
    "protestant",
    "jewish",
    "muslim",
    "atheist",
    "agnostic",
    "unaffiliated",
    "hindu",
    "buddhist",
    "orthodox",
    "lds",
    "unitarian_universalist",
    "humanist",
    "christian_unspecified",
    "other_christian",
    "other",
    "multiple",
    "unknown",
)
RACES = (
    "white",
    "black",
    "asian",
    "native_american",
    "nhpi",
    "asian_or_pacific_islander",
    "multiracial",
    "other",
    "unknown",
)
RACE_ORDERS = {
    2: "white",
    3: "black",
    4: "native_american",
    5: "asian",
    6: "nhpi",
    7: "other",
    8: "multiracial",
}
RACE_CONTROLS = ("black", "asian", "native_american", "nhpi", "other", "multiracial", "hispanic")


def religion_category(literal):
    if not literal:
        return "unknown"
    value = " ".join(literal.casefold().split()).rstrip(".")
    if value in ("unknown", "not stated", "n/a", "don't know/refused", "declined", "refused"):
        return "unknown"
    if re.search(r"\b(raised|attends|member|deacon|married)\b", value):
        return "unknown"
    exact = {
        "catholic": "catholic",
        "roman catholic": "catholic",
        "judaism": "jewish",
        "jewish": "jewish",
        "islam": "muslim",
        "muslim": "muslim",
        "atheist": "atheist",
        "atheism": "atheist",
        "agnostic": "agnostic",
        "unaffiliated": "unaffiliated",
        "none": "unaffiliated",
        "hindu": "hindu",
        "hinduism": "hindu",
        "buddhist": "buddhist",
        "buddhism": "buddhist",
        "humanist": "humanist",
        "unitarian": "unitarian_universalist",
        "unitarian universalist": "unitarian_universalist",
        "christian": "christian_unspecified",
        "other": "other",
        "mormon": "lds",
    }
    if value in exact:
        return exact[value]
    if re.fullmatch(r"(?:the )?church of jesus christ of latter-?\s*day saints", value):
        return "lds"
    if value in ("orthodox", "greek orthodox", "russian orthodox", "eastern orthodox"):
        return "orthodox"
    if re.fullmatch(
        r"(?:(?:southern|united|african|evangelical) )?"
        r"(?:baptist|methodist|lutheran|presbyterian|episcopal|episcopalian|"
        r"anglican|congregationalist|protestant|evangelical)(?: christian| episcopal)?",
        value,
    ) or value in (
        "protestant unspecified",
        "unspecified protestant",
        "nondenominational",
        "nondenom. protestant",
        "nondenominational protestant",
        "evangelical christian",
        "assemblies of god",
        "seventh-day adventist",
        "pentecostal",
        "adventist",
        "holiness",
        "reformed",
        "anglican/episcopal",
        "episcopalian/anglican",
        "presbyterian/evangelical",
        "christian (presbyterian)",
        "african methodist episcopal",
    ):
        return "protestant"
    if value in ("christian, non-denominational", "nondenominational christian"):
        return "christian_unspecified"
    if value in ("restorationist", "church of christ", "christian science", "christian scientist"):
        return "other_christian"
    parts = re.split(r"\s+and\s+|/", value)
    if len(parts) > 1 and all(p in exact for p in parts) and len({exact[p] for p in parts}) > 1:
        return "multiple"
    return "unknown"


def read_pew(path, spec):
    result = []
    pattern = re.compile(
        r"^([A-Z]{2})\s+(\d+|A[Ll]|At-[Ll]arge|Sen|Senator)\s+(.+?)\s+"
        r"([DRI])\s+(I|F|Continuing|Freshman)\s+(.+?)\s*$"
    )
    active_lines = 0
    for page_number, page in enumerate(PdfReader(path).pages, 1):
        text = page.extract_text(extraction_mode="layout")
        lines = re.sub(r"[\x00-\x08\x0b-\x1f]", "", text).splitlines()
        for line_number, line in enumerate(lines, 1):
            line = " ".join(line.split())
            if re.fullmatch(
                r"[A-Z]{2}\s+(?:\d+|A[Ll]|At-[Ll]arge|Sen|Senator)\s+.+?\s+"
                r"[DRI]\s+(?:I|F|Continuing|Freshman)",
                line,
            ) and line_number < len(lines):
                continuation = " ".join(lines[line_number].split())
                if not re.match(r"[A-Z]{2}\s+", continuation):
                    line += " " + continuation
            match = pattern.fullmatch(line)
            if not match:
                if re.match(r"^[A-Z]{2}\s+(?:\d+|A[Ll]|At-[Ll]arge|Sen(?:ator)?)\s+", line):
                    raise ValueError(
                        f"Unparsed Pew member line: {spec['id']}:{page_number}: {line}"
                    )
                continue
            active_lines += 1
            state, district, name, party, _, literal = match.groups()
            if state not in STATE_NAMES:
                raise ValueError("Unexpected Pew state")
            result.append(
                {
                    "name": name,
                    "state": state,
                    "chamber": "senate" if district.startswith("Sen") else "house",
                    "source_district": district,
                    "party": party,
                    "religion_literal": literal,
                    "religion_category": religion_category(literal),
                    "source_id": spec["id"],
                    "source_page": page_number,
                    "source_line": line_number,
                    "publication_date": spec["publication_date"],
                    "election_year": spec["election_year"],
                    "qualification": "Pew/CQ office questionnaire; historical snapshot",
                }
            )
    expected = {2018: 535, 2020: 534, 2022: 531, 2024: 534, 2026: 532}
    if active_lines != expected[spec["election_year"]]:
        raise ValueError(f"Incomplete Pew list {spec['id']}: {active_lines}")
    if len({(r["state"], r["chamber"], r["name"]) for r in result}) != len(result):
        raise ValueError("Duplicate Pew member")
    return result


def read_acs(path, spec):
    if path.suffix == ".gz":
        data = gzip.decompress(path.read_bytes())
    else:
        with zipfile.ZipFile(path) as archive:
            names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if len(names) != 1:
                raise ValueError("ACS archive requires exactly one complete CSV")
            data = archive.read(names[0])
    groups = defaultdict(dict)
    for number, row in enumerate(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))), 2):
        row = {key.upper(): value for key, value in row.items()}
        if not row["GEOID"]:
            continue
        if row["TBLID"] != spec["table"]:
            raise ValueError("Wrong ACS table")
        level = spec["summary_level"]
        match = re.fullmatch(rf"{level}(?:\d{{2}}|\d{{4}})US(\d{{2}})(\d{{2}}|ZZ)?", row["GEOID"])
        if not match or (level == "500") != bool(match[2]):
            raise ValueError(f"Invalid ACS geography: {row['GEOID']}")
        state_name = row["NAME"].rsplit(", ", 1)[-1].upper()
        state = next((s for s, full in STATE_NAMES.items() if full == state_name), None)
        if state is None:
            continue
        district = match[2] if level == "500" else None
        map_congress = None
        if level == "500":
            label = re.search(r"\((\d+)(?:th|st|nd|rd) Congress\)", row["NAME"])
            if not label or int(label[1]) != spec["map_congress"]:
                raise ValueError(f"ACS map label disagrees with qualification: {row['NAME']}")
            map_congress = int(label[1])
        order = int(row["ORDER"])
        key = (state, district)
        if order in groups[key]:
            raise ValueError("Duplicate ACS geography/table/order")
        value = float(row["ESTIMATE"])
        moe = float(row["MOE"])
        if value < 0 or moe < 0:
            raise ValueError("Suppressed/invalid ACS estimate")
        groups[key][order] = {
            "estimate": value,
            "moe": moe,
            "source_row": number,
            "title": row["TITLE"],
            "geoid": row["GEOID"],
            "map_congress": map_congress,
        }
    result = []
    for (state, district), cells in sorted(groups.items(), key=lambda item: str(item[0])):
        orders = list(RACE_ORDERS) if spec["table"] == "B02001" else [12]
        if 1 not in cells or not all(i in cells for i in orders):
            raise ValueError("Incomplete ACS selected population cells")
        total = cells[1]["estimate"]
        if district == "ZZ" and total == 0:
            result.append(
                {
                    "election_year": spec["election_year"],
                    "acs_year": spec["acs_year"],
                    "state": state,
                    "district": district,
                    "table": spec["table"],
                    "source_id": spec["id"],
                    "cells": cells,
                    "population_shares_pct": {},
                    "qualification": "excluded_zero_population_undefined_district",
                }
            )
            continue
        if total <= 0 or any(not 0 <= cells[i]["estimate"] <= total for i in orders):
            raise ValueError("Invalid ACS population denominator")
        if spec["table"] == "B02001" and abs(sum(cells[i]["estimate"] for i in orders) - total) > 1:
            raise ValueError("ACS race categories fail population accounting")
        shares = {
            RACE_ORDERS[i] if spec["table"] == "B02001" else "hispanic": cells[i]["estimate"]
            * 100
            / total
            for i in orders
        }
        result.append(
            {
                "election_year": spec["election_year"],
                "acs_year": spec["acs_year"],
                "state": state,
                "district": district,
                "table": spec["table"],
                "map_congress": cells[1]["map_congress"],
                "total_population": total,
                "population_shares_pct": shares,
                "source_id": spec["id"],
                "cells": {str(i): cells[i] for i in [1, *orders]},
                "qualification": "retrospective ACS five-year total population; not voters/CVAP",
            }
        )
    expected = 435 if spec["summary_level"] == "500" else 50
    selected_count = sum(r["district"] != "ZZ" for r in result)
    if selected_count != expected:
        raise ValueError(f"Incomplete ACS geography coverage {spec['id']}: {selected_count}")
    return result


def read_religious_context(path, spec):
    result = []
    with path.open(newline="") as stream:
        for number, row in enumerate(csv.DictReader(stream), 2):
            year = int(row["YrElected"])
            if year not in (2016, 2018):
                continue
            if int(row["CongSession"]) != (year - 1788) // 2 + 1:
                raise ValueError("Religion context election/congress mismatch")
            values = {
                k: float(row[k]) for k in ("Catholic", "EvanProt", "MainProt", "Other", "NoCong")
            }
            if (
                any(not 0 <= v <= 100 for v in values.values())
                or abs(sum(values.values()) - 100) > 0.01
            ):
                raise ValueError("Invalid congregation-adherence accounting")
            result.append(
                {
                    "election_year": year,
                    "state": row["stateabbr"],
                    "district": row["CDnum"].zfill(2),
                    "source_id": spec["id"],
                    "source_row": number,
                    "religious_shares_pct": values,
                    "map_qualified": not (year == 2018 and row["stateabbr"] == "PA"),
                    "qualification": (
                        "2010 congregation adherence; population-apportioned split counties;"
                        " Other includes Black Protestants; NoCong is not atheist/unaffiliated"
                    ),
                }
            )
    if any(sum(r["election_year"] == year for r in result) != 435 for year in (2016, 2018)):
        raise ValueError("Incomplete religious-context district coverage")
    return result


class IdentityTableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self.cells, self.fragments = [], [], None
        self.suppressed = 0

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.cells = []
        elif tag in ("td", "th"):
            self.fragments = []
        elif tag == "sup":
            self.suppressed += 1

    def handle_data(self, data):
        if self.fragments is not None and not self.suppressed:
            self.fragments.append(data)

    def handle_endtag(self, tag):
        if tag == "sup":
            self.suppressed -= 1
        elif tag in ("td", "th") and self.fragments is not None:
            self.cells.append(" ".join(" ".join(self.fragments).split()))
            self.fragments = None
        elif tag == "tr":
            self.rows.append(self.cells)


def read_historian(path, spec):
    parser = IdentityTableParser()
    parser.feed(path.read_text())
    result, expected = [], None
    for number, cells in enumerate(parser.rows, 1):
        if len(cells) == 1:
            match = re.fullmatch(r"119th \(2025-2027\) (\d+) House, (\d+) Senate", cells[0])
            if match:
                expected = {"house": int(match[1]), "senate": int(match[2])}
        if len(cells) != 5 or cells[0] != "119th (2025-2027)":
            continue
        _, name, state, party, chamber = cells
        if chamber not in ("House", "Senate") or "," not in name:
            raise ValueError("Unparsed House Historian member row")
        result.append(
            {
                "congress": 119,
                "name": name,
                "state": state,
                "party": party,
                "chamber": chamber.lower(),
                "identity_group": spec["identity_group"],
                "source_id": spec["id"],
                "source_table_row": number,
                "qualification": "positive House Historian identification; absence is not a negative",
            }
        )
    if not expected or any(
        sum(r["chamber"] == chamber for r in result) != count for chamber, count in expected.items()
    ):
        raise ValueError("Incomplete House Historian 119th-Congress table")
    if len({(r["state"], r["chamber"], r["name"]) for r in result}) != len(result):
        raise ValueError("Duplicate House Historian member")
    return result


class DemographicSources:
    def __init__(self, manifest, root):
        self.acs, self.pew, self.religious = [], [], []
        self.historian = []
        self.map_change_evidence = None
        for spec in manifest["sources"]:
            if spec["kind"] == "map_change_evidence":
                text = confined(root, spec["path"]).read_text()
                if "120th Congress" not in text or any(
                    STATE_NAMES[state].title() not in text for state in spec["changed_states"]
                ):
                    raise ValueError("District-change qualification evidence changed")
                self.map_change_evidence = spec
            reader = {
                "acs_composition": read_acs,
                "pew_member_religion": read_pew,
                "district_religiosity": read_religious_context,
                "house_historian_identity": read_historian,
            }.get(spec["kind"])
            if reader:
                rows = reader(confined(root, spec["path"]), spec)
                {
                    "acs_composition": self.acs,
                    "pew_member_religion": self.pew,
                    "district_religiosity": self.religious,
                    "house_historian_identity": self.historian,
                }[spec["kind"]].extend(rows)
        self.population_index = defaultdict(list)
        for row in self.acs:
            self.population_index[(row["election_year"], row["state"], row["district"])].append(row)
        self.religious_index = {
            (r["election_year"], r["state"], r["district"]): r for r in self.religious
        }
        self.pew_index = defaultdict(list)
        for row in self.pew:
            self.pew_index[(row["election_year"], row["state"], row["chamber"])].append(row)
        self.historian_index = defaultdict(list)
        for row in self.historian:
            self.historian_index[(row["state"], row["chamber"])].append(row)

    def candidate_identity(self, row, feature, sources):
        from .features import name_matches

        result = {
            "religion_category": religion_category(feature.get("religion")),
            "religion_category_source": "authorized_directory" if feature.get("religion") else None,
            "religion_category_evidence": [],
            "race_category": "unknown",
            "races": [],
            "hispanic_origin": None,
            "racial_identity_evidence": [],
            "race_ethnicity_status": "unknown; never_inferred",
        }
        person = sources.people.get(feature["bioguide_id"])
        if not person or not feature.get("service_verified_incumbent"):
            return result
        aliases = sources.aliases(person)
        matches = [
            p
            for p in self.pew_index[(row["year"], row["state"], row["chamber"])]
            if date.fromisoformat(p["publication_date"]) < date.fromisoformat(row["election_date"])
            and name_matches(p["name"], *aliases[0], aliases[1:])
        ]
        if len(matches) == 1:
            result.update(
                religion_category=matches[0]["religion_category"],
                religion_category_source="Pew/CQ_office_questionnaire",
                religion_category_evidence=matches,
            )
        elif len(matches) > 1:
            result.update(
                religion_category="unknown", religion_category_source="ambiguous_Pew_match"
            )
        for ref in feature.get("feature_evidence", []):
            if ref.get("feature") != "supplemental_biography":
                continue
            result["racial_identity_evidence"].extend(ref.get("racial_identity_evidence", []))
            result["races"] = ref.get("races", [])
            result["hispanic_origin"] = ref.get("hispanic_origin")
        races = set(result["races"])
        if row["year"] == 2026:
            for record in self.historian_index[(row["state"], row["chamber"])]:
                if name_matches(record["name"], *aliases[0], aliases[1:]):
                    result["racial_identity_evidence"].append(record)
                    if record["identity_group"] == "hispanic":
                        result["hispanic_origin"] = (
                            None if result["hispanic_origin"] is False else True
                        )
                    else:
                        races.add(record["identity_group"])
        if races & {"asian", "nhpi"}:
            races.discard("asian_or_pacific_islander")
        result["races"] = sorted(races)
        result["race_category"] = (
            "multiracial" if len(races) > 1 else next(iter(races)) if races else "unknown"
        )
        if races or result["hispanic_origin"] is not None:
            result["race_ethnicity_status"] = "documented_identity_evidence; never_inferred"
        return result

    def context(self, row):
        district = row.get("benchmark_district") if row["chamber"] == "house" else None
        year = 2024 if row["year"] == 2026 else row["year"]
        population = self.population_index[(year, row["state"], district)]
        if (
            row["year"] == 2026
            and row["chamber"] == "house"
            and (
                not self.map_change_evidence
                or row["state"] in self.map_change_evidence["changed_states"]
            )
        ):
            population = []
            status = "held_119th_to_120th_map_changed_or_unqualified"
        elif row["chamber"] == "house" and row["year"] == 2020 and row["state"] == "NC":
            population = []
            status = "held_116th_map_incompatible_with_2020_NC_election"
        else:
            status = "qualified_retrospective_population" if len(population) == 2 else "missing"
        shares = {}
        for item in population:
            shares.update(item["population_shares_pct"])
        if "asian" in shares and "nhpi" in shares:
            shares["asian_or_pacific_islander"] = shares["asian"] + shares["nhpi"]
        religious = self.religious_index.get((row["year"], row["state"], district))
        if not religious or not religious["map_qualified"] or row["chamber"] != "house":
            religious = None
        return {
            "constituency_composition_status": status,
            "constituency_race_shares_pct": shares,
            "constituency_population_evidence": population,
            "constituency_map_evidence": self.map_change_evidence if row["year"] == 2026 else None,
            "constituency_religion_shares_pct": religious["religious_shares_pct"]
            if religious
            else {},
            "constituency_religion_evidence": religious,
            "constituency_religion_status": "qualified_approximate_RCMS_context"
            if religious
            else "unavailable_on_election_map",
        }
