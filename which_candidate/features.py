import csv
import json
import re
import unicodedata
import zipfile
from collections import defaultdict
from datetime import date

import openpyxl

from .biographies import read_directory
from .fec import STATES
from .storage import confined


def tokens(value):
    value = value.replace("\u2019", "'").replace("\u2018", "'")
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    result = re.findall(r"[a-z0-9]+", value.casefold())
    return [word for word in result if word not in ("jr", "sr", "ii", "iii", "iv")]


def name_matches(name, first, last, aliases=()):
    if "," in name:
        family, given = name.split(",", 1)
        name = f"{given} {family}"
    value = tokens(name)
    if len(value) > 2 and len(value[0]) == len(value[1]) == 1:
        value = [value[0] + value[1], *value[2:]]
    if not value:
        return False
    names = [(first, last), *aliases]
    for given, family in names:
        a, b = tokens(given), tokens(family)
        if a and a[0] in ("dr", "sen", "rep"):
            a = a[1:]
        if a and len(a) > 1 and len(a[0]) == 1 and value[0] == a[1]:
            a = a[1:]
        if a and b and len(value) > len(b) and value[-len(b) :] == b:
            if value[0] == a[0] and len(a[0]) > 1:
                return True
            if min(len(value[0]), len(a[0])) >= 3 and (
                value[0].startswith(a[0]) or a[0].startswith(value[0])
            ):
                return True
            if value == a + b:
                return True
    return False


def read_nominees(path, spec):
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = []
    try:
        for sheet in workbook:
            for number, cells in enumerate(sheet.iter_rows(max_col=9, values_only=True), 1):
                if cells[0] not in STATES or not isinstance(cells[2], str):
                    continue
                district = cells[2].strip()
                if not (district.startswith("S") or re.fullmatch(r"\d{2}", district)):
                    continue
                fec_id = str(cells[3] or "").strip()
                rows.append(
                    {
                        "state": cells[0],
                        "election_year": spec.get("election_year", 2024),
                        "chamber": "senate" if district.startswith("S") else "house",
                        "district": district if district.startswith("S") else district.zfill(2),
                        "fec_id": fec_id if re.fullmatch(r"[HS]\d[A-Z]{2}\d{5}", fec_id) else None,
                        "incumbent": str(cells[4] or "").strip() == "(I)",
                        "first": str(cells[5] or "").strip(),
                        "last": str(cells[6] or "").strip(),
                        "name": str(cells[7] or "").strip(),
                        "party": cells[8],
                        "source_id": spec["id"],
                        "source_sheet": sheet.title,
                        "source_row": number,
                    }
                )
    finally:
        workbook.close()
    return rows


def read_candidate_master(path, spec):
    with zipfile.ZipFile(path) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith(".txt")]
        if len(names) != 1:
            raise ValueError("Expected one complete FEC candidate master")
        lines = archive.read(names[0]).decode("utf-8-sig").splitlines()
    rows = []
    for number, line in enumerate(lines, 1):
        cells = line.split("|")
        if len(cells) != 15:
            raise ValueError("Changed FEC candidate-master schema")
        identifier, name, party, year, state, office, district, incumbency = cells[:8]
        if year != str(spec["election_year"]) or office not in ("H", "S") or state not in STATES:
            continue
        if not re.fullmatch(r"[HS]\d[A-Z]{2}\d{5}", identifier):
            raise ValueError("Invalid FEC congressional candidate identifier")
        if "," in name:
            last, first = (part.strip() for part in name.split(",", 1))
        else:
            parts = name.rsplit(" ", 1)
            first, last = parts if len(parts) == 2 else ("", name)
        rows.append(
            {
                "election_year": int(year),
                "state": state,
                "chamber": "house" if office == "H" else "senate",
                "district": district.zfill(2) if office == "H" else "S",
                "fec_id": identifier,
                "incumbent": True
                if incumbency == "I"
                else False
                if incumbency in ("C", "O")
                else None,
                "first": first,
                "last": last,
                "name": name,
                "party": party,
                "source_id": spec["id"],
                "source_sheet": names[0],
                "source_row": number,
            }
        )
    return rows


class FeatureSources:
    def __init__(self, manifest, root):
        self.people, self.fec, self.members, self.unity = (
            {},
            defaultdict(set),
            defaultdict(list),
            defaultdict(list),
        )
        self.nominees = []
        self.biographies = []
        for spec in manifest["sources"]:
            path = confined(root, spec["path"])
            if spec["kind"] == "legislators":
                for index, person in enumerate(json.loads(path.read_bytes())):
                    bioguide = person["id"]["bioguide"]
                    if bioguide in self.people:
                        raise ValueError(f"Duplicate crosswalk person: {bioguide}")
                    self.people[bioguide] = {
                        **person,
                        "evidence": {"source_id": spec["id"], "json_pointer": f"/{index}"},
                    }
                    for fec_id in person["id"].get("fec", []):
                        self.fec[fec_id].add(bioguide)
            elif spec["kind"] in ("voteview_members", "voteview_unity"):
                with path.open(newline="") as stream:
                    for number, row in enumerate(csv.DictReader(stream), 2):
                        if not row["congress"] or not 113 <= int(row["congress"]) <= 118:
                            continue
                        row = {**row, "evidence": {"source_id": spec["id"], "source_row": number}}
                        for field in ("party_code", "icpsr"):
                            if row[field]:
                                number_value = float(row[field])
                                if not number_value.is_integer():
                                    raise ValueError(f"Noninteger Voteview {field}")
                                row[field] = str(int(number_value))
                        if spec["kind"] == "voteview_members":
                            key = (int(row["congress"]), row["chamber"].lower(), row["bioguide_id"])
                            self.members[key].append(row)
                        else:
                            key = (int(row["congress"]), row["chamber"].lower(), row["icpsr"])
                            self.unity[key].append(row)
            elif spec["kind"] == "fec_nominees_2024":
                self.nominees.extend(read_nominees(path, spec))
            elif spec["kind"] == "fec_candidate_master":
                self.nominees.extend(read_candidate_master(path, spec))
            elif spec["kind"] == "congressional_directory":
                self.biographies.extend(read_directory(path, spec))
        self.biography_index = defaultdict(list)
        for row in self.biographies:
            self.biography_index[(row["election_year"], row["state"])].append(row)
        self.roster_index = defaultdict(list)
        for row in self.nominees:
            self.roster_index[(row["election_year"], row["state"], row["chamber"])].append(row)
        self.state_people = defaultdict(set)
        for key, person in self.people.items():
            for term in person["terms"]:
                if int(term["end"][:4]) >= 2010:
                    chamber = "house" if term["type"] == "rep" else "senate"
                    self.state_people[(term["state"], chamber)].add(key)

    def aliases(self, person):
        name = person["name"]
        result = [(name["first"], name["last"])]
        if name.get("middle"):
            result.append((f"{name['first']} {name['middle']}", name["last"]))
        if name.get("official_full"):
            full, last = tokens(name["official_full"]), tokens(name["last"])
            if last and full[-len(last) :] == last:
                result.append((" ".join(full[: -len(last)]), name["last"]))
        if name.get("nickname"):
            result.append((name["nickname"], name["last"]))
        for other in person.get("other_names", []):
            result.append((other.get("first", name["first"]), other.get("last", name["last"])))
        return result

    def matches_person(self, row, person):
        aliases = self.aliases(person)
        if not any(term["state"] == row["state"] for term in person["terms"]):
            return False
        return name_matches(row["name"], *aliases[0], aliases[1:])

    def resolve(self, row):
        fec_id, incumbent = row.get("fec_id"), row.get("source_incumbent")
        roster_refs, roster_status = [], "not_applicable"
        if row["year"] in (2024, 2026):
            matches = []
            for nominee in self.roster_index[(row["year"], row["state"], row["chamber"])]:
                district = "00" if row["district"] == "AL" else row["district"]
                if row["chamber"] == "house" and nominee["district"] != district:
                    continue
                if row["year"] == 2026 and nominee["party"] not in (
                    ("DEM", "DFL") if row["party_group"] == "D" else ("REP",)
                ):
                    continue
                aliases = []
                if "," in nominee["name"]:
                    family, given = nominee["name"].split(",", 1)
                    aliases.append((given, family))
                for person_id in self.fec.get(nominee["fec_id"], ()):
                    aliases.extend(self.aliases(self.people[person_id]))
                if name_matches(row["name"], nominee["first"], nominee["last"], aliases):
                    matches.append(nominee)
            values = {(r["fec_id"], r["incumbent"]) for r in matches}
            roster_status = (
                "unique_fec_and_incumbency"
                if len(values) == 1
                else "unmatched"
                if not values
                else "ambiguous"
            )
            if len(values) == 1:
                fec_id, incumbent = next(iter(values))
                roster_refs = [
                    {key: r[key] for key in ("source_id", "source_sheet", "source_row")}
                    for r in matches
                ]
        identities = [
            key for key in self.fec.get(fec_id, ()) if self.matches_person(row, self.people[key])
        ]
        identity_method = "exact_fec_with_name_and_state_checks"
        if not identities and row.get("election_date"):
            cutoff = date.fromisoformat(row["election_date"])
            for key in sorted(self.state_people[(row["state"], row["chamber"])]):
                person = self.people[key]
                if self.matches_person(row, person) and any(
                    term["state"] == row["state"]
                    and term["type"] == ("rep" if row["chamber"] == "house" else "sen")
                    and cutoff.year - 6 <= int(term["end"][:4])
                    and int(term["start"][:4]) <= cutoff.year + 2
                    for term in person["terms"]
                ):
                    identities.append(key)
            identity_method = (
                "unique_documented_name_state_chamber_dated_service; fec_crosswalk_gap"
            )
        person_id = identities[0] if len(identities) == 1 else None
        person = self.people.get(person_id)
        return {
            "fec_id": fec_id,
            "native_incumbent": incumbent,
            "roster_match_status": roster_status,
            "roster_evidence": roster_refs,
            "identity_status": identity_method
            if person
            else "unmatched_or_conflicting_congressional_identity",
            "bioguide_id": person_id,
            "person_group": f"bioguide:{person_id}"
            if person_id
            else f"fec:{fec_id}"
            if fec_id
            else f"unresolved:{row['candidate_election_id']}",
        }

    def features(self, row):
        resolved = self.resolve(row)
        person = self.people.get(resolved["bioguide_id"])
        cutoff = date.fromisoformat(row["election_date"]) if row.get("election_date") else None
        chamber_type = "rep" if row["chamber"] == "house" else "sen"
        active, past = [], []
        refs = list(resolved["roster_evidence"])
        result = {
            **resolved,
            "candidate_election_id": row["candidate_election_id"],
            "year": row["year"],
            "chamber": row["chamber"],
            "state": row["state"],
            "party_group": row["party_group"],
            "name": row["name"],
            "incumbent": None
            if resolved["native_incumbent"] is True
            else resolved["native_incumbent"],
            "service_verified_incumbent": None,
            "incumbency_conflict": False,
            "age_years": None,
            "chamber_tenure_years": None,
            "source_recorded_gender": None,
            "nokken_poole_dim1": None,
            "party_unity_score": None,
            "party_unity_votes": None,
            "lagged_congress": (row["year"] - 1789) // 2,
            "lagged_record_status": "no_verified_same_chamber_record",
            "race_ethnicity": None,
            "religion": None,
            "born_in_state": None,
            "birth_state": None,
            "reported_catholic": None,
            "race_ethnicity_status": "no_qualified_self_identification_evidence; never_inferred",
            "biography_status": "no_unique_pre_election_authorized_biography",
        }
        # This formula selects the Congress completed in January of the election's prior year.
        if not person or not cutoff:
            result["feature_evidence"] = refs
            return result
        refs.append(person["evidence"])
        for index, term in enumerate(person["terms"]):
            start, end = date.fromisoformat(term["start"]), date.fromisoformat(term["end"])
            if start < cutoff:
                past.append((start, min(end, cutoff), term))
            if (
                term["type"] == chamber_type
                and term["state"] == row["state"]
                and start <= cutoff < end
            ):
                active.append(term)
                refs.append({**person["evidence"], "term_index": index})
        verified = bool(active)
        result["service_verified_incumbent"] = verified
        if resolved["native_incumbent"] is not None and resolved["native_incumbent"] != verified:
            result["incumbency_conflict"] = True
        result["incumbent"] = verified
        birthday = person.get("bio", {}).get("birthday")
        if birthday and date.fromisoformat(birthday) < cutoff:
            result["age_years"] = (cutoff - date.fromisoformat(birthday)).days / 365.2425
        result["source_recorded_gender"] = person.get("bio", {}).get("gender")
        if verified:
            aliases = self.aliases(person)
            biographies = [
                b
                for b in self.biography_index[(row["year"], row["state"])]
                if date.fromisoformat(b["publication_date"]) < cutoff
                and name_matches(b["name"], *aliases[0], aliases[1:])
            ]
            if len(biographies) == 1:
                biography = biographies[0]
                result["biography_status"] = "unique_pre_election_member_authorized_biography"
                result["birth_state"] = biography["birth_state"]
                result["religion"] = biography["religion"]
                if biography["birth_state"] is not None:
                    result["born_in_state"] = biography["birth_state"] == row["state"]
                if biography["religion"] is not None:
                    value = " ".join(biography["religion"].casefold().split()).rstrip(".")
                    if value not in ("unknown", "not stated", "n/a"):
                        if value in ("catholic", "roman catholic"):
                            result["reported_catholic"] = True
                        elif "catholic" not in value:
                            result["reported_catholic"] = False
                refs.append({"feature": "supplemental_biography", **biography})
        intervals = sorted((a, b) for a, b, t in past if t["type"] == chamber_type and b > a)
        merged = []
        for start, end in intervals:
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
            else:
                merged.append((start, end))
        result["chamber_tenure_years"] = sum((b - a).days for a, b in merged) / 365.2425
        congress = result["lagged_congress"]
        records = [
            r
            for r in self.members.get((congress, row["chamber"], resolved["bioguide_id"]), [])
            if r["state_abbrev"] == row["state"] and r["party_code"] == "100"
        ]
        if len(records) == 1:
            record = records[0]
            refs.append(record["evidence"])
            score = record["nokken_poole_dim1"]
            if score not in ("", "NA"):
                result["nokken_poole_dim1"] = float(score)
                result["lagged_record_status"] = (
                    "prior_completed_congress; retrospective_estimate_vintage"
                )
            unity = self.unity.get((congress, row["chamber"], record["icpsr"]), [])
            if len(unity) == 1 and unity[0]["party_code"] == "100":
                item = unity[0]
                count, with_party = (
                    int(item["total_unity_votes"]),
                    int(item["with_party_unity_votes"]),
                )
                if not 0 <= with_party <= count:
                    raise ValueError("Invalid party unity denominator")
                result["party_unity_votes"] = count
                if count >= 50:
                    result["party_unity_score"] = with_party / count
                refs.append(item["evidence"])
        result["feature_evidence"] = refs
        return result
