"""Dated background evidence; never a source of imputed current identity labels."""

import argparse
import hashlib
import json
import re
from datetime import date
from pathlib import Path

from pypdf import PdfReader

from .corrected import same_name
from .features import FeatureSources
from .incumbents import pinned_inputs, profile_inputs
from .rebuild import district
from .storage import fingerprint, read_rows, write_json

OREGON_PARTIES = {
    "Democrat": "Democratic",
    "Republican": "Republican",
    "Pacific Green": "Pacific Green",
    "Libertarian": "Libertarian",
    "Independent": "Independent",
    "Progressive": "Progressive",
}

UTAH_PARTIES = (
    "Independent American",
    "Democratic",
    "Republican",
    "Unaffiliated",
    "Libertarian",
    "Constitution",
)
# The held certification's text layer splits this surname.
UTAH_CERTIFICATION_OCR_NAMES = {"ADONIS HOOSL YN": "ADONIS HOOSLYN"}


def parse_utah_certification(text):
    headers = list(re.finditer(r"^U\.S\. House of Representatives District ([1-4])\.", text, re.M))
    result = []
    for index, header in enumerate(headers):
        end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        for name, party in re.findall(
            r"^([A-Z][A-Z .'-]+?) +(" + "|".join(UTAH_PARTIES) + r")\s*$",
            text[header.end() : end],
            re.M,
        ):
            result.append({"name": name, "district": header[1].zfill(2), "party": party})
    return result


def parse_utah_profile(text, certified):
    header = re.match(r"^Congressional District ([1-4])\s*\n", text)
    if not header:
        return None
    heading = text[header.end() :].lstrip().split("\n\n", 1)[0]
    name = " ".join(heading.split())
    matches = [
        row
        for row in certified
        if row["district"] == header[1].zfill(2)
        and same_name(name, UTAH_CERTIFICATION_OCR_NAMES.get(row["name"], row["name"]))
    ]
    profile = {
        "name": name,
        "state": "UT",
        "chamber": "house",
        "district": header[1].zfill(2),
        "party": matches[0]["party"] if len(matches) == 1 else None,
        "certified_ballot_name": matches[0]["name"] if len(matches) == 1 else None,
        "election_year": 2026,
        "fields": {},
        "review_status": "structured_candidate_supplied_fields; not_independently_verified",
        "model_ready": False,
    }
    if re.search(r"\bNO\s+PROFILE\s+SUBMITTED\b", text):
        return {**profile, "response_status": "no_profile_submitted"}
    if len(matches) != 1:
        return {**profile, "response_status": "certification_identity_unresolved"}
    for label, field in (
        ("CITY OF RESIDENCE", "residence_city"),
        ("YEARS OF RESIDENCE", "reported_years_of_residence"),
        ("AGE", "reported_age"),
        ("OCCUPATION", "occupation"),
    ):
        value = re.search(r"^" + label + r"[ \t]+(\S[^\n]*(?:\n[ \t]{10,}\S[^\n]*)*)", text, re.M)
        if value:
            profile["fields"][field] = " ".join(value[1].split())
    if profile["fields"]:
        website = re.search(r"^WEBSITE[ \t]+(\S+)", text, re.M)
        if website:
            profile["fields"]["campaign_website"] = website[1]
    return {
        **profile,
        "response_status": "structured_fields" if profile["fields"] else "no_structured_fields",
    }


def parse_oregon_page(text):
    headers = list(re.finditer(r"US Representative,\s*(\d+)(?:st|nd|rd|th) District\s*\n", text))
    result = []
    for index, header in enumerate(headers):
        end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        block = text[header.end() : end]
        if "Occupation:" not in block:
            continue
        heading = block.split("Occupation:", 1)[0]
        party = re.search(r"\b(" + "|".join(re.escape(p) for p in OREGON_PARTIES) + r")\b", heading)
        if not party:
            continue
        fields = {}
        for field, start, stop in (
            ("occupation", "Occupation:", "Occupational Background:"),
            ("occupational_background", "Occupational Background:", "Educational Background:"),
            ("education", "Educational Background:", "Prior Governmental Experience:"),
        ):
            if start not in block or stop not in block.split(start, 1)[1]:
                continue
            value = " ".join(block.split(start, 1)[1].split(stop, 1)[0].split())
            if value and len(value) <= 600:
                fields[field] = value
        if fields:
            result.append(
                {
                    "name": " ".join(heading[: party.start()].split()),
                    "state": "OR",
                    "chamber": "house",
                    "district": header[1].zfill(2),
                    "party": OREGON_PARTIES[party[1]],
                    "election_year": 2026,
                    "fields": fields,
                    "review_status": "structured_candidate_supplied_fields; not_independently_verified",
                    "source_block_sha256": hashlib.sha256(block.encode()).hexdigest(),
                    "model_ready": False,
                }
            )
    return result


def extract_official_profiles(root):
    root = Path(root)
    receipts = json.loads((root / "data/house-background-sources.json").read_text())
    profiles = json.loads((root / "data/house-reviewed-profile-facts.json").read_text())
    grouped = {}
    source_by_id = {source["id"]: source for source in receipts["sources"]}
    nonresponses = []
    for source in receipts["sources"]:
        path = root / "data/raw/house-profiles-20261114" / source["file"]
        if fingerprint(path) != {key: source[key] for key in ("bytes", "sha256")}:
            raise ValueError(f"Changed original candidate source: {source['id']}")
    if "ut-guide" in source_by_id:
        certification = source_by_id["ut-certified"]
        cert_path = root / "data/raw/house-profiles-20261114" / certification["file"]
        certified = parse_utah_certification(PdfReader(cert_path).pages[1].extract_text())
        source = source_by_id["ut-guide"]
        path = root / "data/raw/house-profiles-20261114" / source["file"]
        for number, page in enumerate(PdfReader(path).pages, 1):
            profile = parse_utah_profile(page.extract_text(extraction_mode="layout"), certified)
            if not profile:
                continue
            profile["evidence"] = [
                {"source_id": "ut-guide", "pdf_page": number, "sha256": source["sha256"]}
            ]
            if profile["party"] is not None:
                profile["evidence"].append(
                    {
                        "source_id": "ut-certified",
                        "pdf_page": 2,
                        "sha256": certification["sha256"],
                    }
                )
            (profiles if profile["fields"] else nonresponses).append(profile)
    for source in receipts["sources"]:
        if not source["id"].startswith("or-"):
            continue
        path = root / "data/raw/house-profiles-20261114" / source["file"]
        for number, page in enumerate(PdfReader(path).pages, 1):
            for profile in parse_oregon_page(page.extract_text()):
                block_hash = profile.pop("source_block_sha256")
                key = json.dumps(profile, sort_keys=True)
                if key not in grouped:
                    grouped[key] = {**profile, "evidence": []}
                grouped[key]["evidence"].append(
                    {
                        "source_id": source["id"],
                        "pdf_page": number,
                        "sha256": source["sha256"],
                        "source_block_sha256": block_hash,
                    }
                )
    profiles.extend(grouped.values())
    write_json(root / "data/house-official-profile-facts.json", profiles)
    write_json(root / "data/house-official-profile-dispositions.json", nonresponses)
    return {
        "profiles": len(profiles),
        "sources": len(receipts["sources"]),
        "nonresponses": len(nonresponses),
    }


def acquire_background_inputs(root):
    manifest = json.loads((root / "results/2026/manifest.json").read_text())
    records, sources = {}, []
    for key, name in (
        ("member_biographies", "directory-biographies.jsonl.gz"),
        ("religion_observations", "Pew-member-religion.jsonl.gz"),
        ("historian_observations", "House-Historian-identity.jsonl.gz"),
    ):
        path = root / "results/2026" / name
        if fingerprint(path) != manifest["files"][name]:
            raise ValueError(f"Changed pinned background table: {name}")
        records[key] = read_rows(path)
        sources.append({"path": f"results/2026/{name}", **fingerprint(path)})
    specs = json.loads((root / "data/research-sources.json").read_text())["sources"]
    ids = {r["source_id"] for rows in records.values() for r in rows}
    for spec in specs:
        if spec["id"] in ids:
            path = root / "data" / spec["path"]
            if fingerprint(path) != {key: spec[key] for key in ("sha256", "bytes")}:
                raise ValueError(f"Changed original background source: {spec['id']}")
            sources.append(
                {
                    "id": spec["id"],
                    "url": spec["origin_url"],
                    "publication_date": spec.get("publication_date"),
                    **fingerprint(path),
                }
            )
    official = root / "data/house-official-profile-facts.json"
    records["official_profiles"] = json.loads(official.read_text()) if official.exists() else []
    dispositions = root / "data/house-official-profile-dispositions.json"
    records["official_profile_dispositions"] = (
        json.loads(dispositions.read_text()) if dispositions.exists() else []
    )
    receipts = root / "data/house-background-sources.json"
    records["background_source_receipts"] = (
        json.loads(receipts.read_text()) if receipts.exists() else {}
    )
    by_id = {}
    for source in records["background_source_receipts"].get("sources", []):
        path = root / "data/raw/house-profiles-20261114" / source["file"]
        if fingerprint(path) != {key: source[key] for key in ("sha256", "bytes")}:
            raise ValueError(f"Changed official candidate profile: {source['id']}")
        by_id[source["id"]] = source
    for profile in records["official_profiles"]:
        for evidence in profile["evidence"]:
            source = by_id[evidence["source_id"]]
            if evidence.get("sha256", source["sha256"]) != source["sha256"]:
                raise ValueError("Official profile annotation source changed")
            evidence["sha256"] = source["sha256"]
    records["background_original_sources"] = sources
    records["incumbent_backgrounds"] = profile_inputs(root)
    for source in records["incumbent_backgrounds"].get("sources", []):
        if fingerprint(root / source["path"]) != {key: source[key] for key in ("sha256", "bytes")}:
            raise ValueError(f"Changed original incumbent source: {source['id']}")
    records.update(pinned_inputs(root))
    from .reviewed_backgrounds import reviewed_inputs

    records.update(reviewed_inputs(root))
    return records


def validate_reported_age(value):
    from datetime import timedelta

    if (
        set(value) != {"reported_age", "reference_date", "birth_date_interval"}
        or type(value["reported_age"]) is not int
        or not 0 <= value["reported_age"] <= 125
        or not isinstance(value["birth_date_interval"], list)
        or len(value["birth_date_interval"]) != 2
    ):
        raise ValueError("Invalid reported-age interval")
    reference = date.fromisoformat(value["reference_date"])
    earliest, latest = map(date.fromisoformat, value["birth_date_interval"])

    def age_on_reference(birthday):
        return (
            reference.year
            - birthday.year
            - ((reference.month, reference.day) < (birthday.month, birthday.day))
        )

    if (
        not earliest <= latest <= reference <= date(2026, 11, 3)
        or age_on_reference(earliest) != value["reported_age"]
        or age_on_reference(latest) != value["reported_age"]
        or age_on_reference(earliest - timedelta(days=1)) == value["reported_age"]
        or age_on_reference(latest + timedelta(days=1)) == value["reported_age"]
    ):
        raise ValueError("Unsupported reported-age bounds")


def validate_characteristics(records, candidates):
    identities = {(r["contest_id"], r["candidate_id"]): r for r in candidates}
    seen = set()
    for record in records:
        candidate = identities.get((record["contest_id"], record["candidate_id"]))
        if not candidate or any(
            candidate[k] != record[k] for k in ("name", "state", "district", "party")
        ):
            raise ValueError("Unqualified characteristic identity")
        if record["observation_id"] in seen:
            raise ValueError("Duplicate characteristic observation")
        seen.add(record["observation_id"])
        if (
            record["review_status"] != "fragment_and_identity_reviewed"
            or record["model_ready"] is not False
            or not record["fragment"].strip()
            or not record["qualification"].strip()
            or not record["identity_qualification"].strip()
        ):
            raise ValueError("Unreviewed characteristic evidence")
        if record["trait"] not in {
            "age",
            "gender",
            "race",
            "ethnicity",
            "religion",
            "education",
            "profession",
            "military",
            "prior_elected_office",
            "other_government",
            "incumbency",
        }:
            raise ValueError("Unsupported acquired characteristic")
        receipt = record["receipt"]
        if (
            not re.fullmatch(r"[a-f0-9]{64}", receipt["sha256"])
            or receipt["bytes"] <= 0
            or not receipt["url"].startswith(("https://", "http://"))
            or not receipt["retrieved_at"]
        ):
            raise ValueError("Invalid characteristic receipt")
        if record["trait"] == "incumbency" and not isinstance(record["value"], bool):
            raise ValueError("Incumbency classification must be an explicit boolean")
        if record["trait"] == "age":
            value = record["value"]
            if isinstance(value, dict):
                if "reported_age" in value:
                    validate_reported_age(value)
                elif (
                    set(value) not in ({"birth_year"}, {"birth_year", "birth_month"})
                    or any(type(v) is not int for v in value.values())
                    or not 1 <= value["birth_year"] < 2026
                    or not 1 <= value.get("birth_month", 1) <= 12
                ):
                    raise ValueError("Invalid characteristic birth interval")
            else:
                birthday = date.fromisoformat(value)
                if birthday >= date(2026, 11, 3):
                    raise ValueError("Invalid characteristic birthday")


def background_profile(candidate, inputs):
    from .reviewed_backgrounds import matched_profiles

    target_id = candidate["identity"]["fec_id"]
    people = [p for p in inputs["people"] if target_id and target_id in p["id"].get("fec", [])]
    legislative = candidate.get("legislative", {})
    if not people and legislative.get("status") == "official_clerk_and_service_crosswalk":
        people = [
            p for p in inputs["people"] if p["id"]["bioguide"] == legislative.get("bioguide_id")
        ]
    matcher = FeatureSources({"sources": []}, None)

    def qualified(record):
        if len(people) != 1 or record["state"] != candidate["state"]:
            return False
        if record.get("chamber", "house") != "house":
            return False
        if record.get("publication_date", "") >= "2026-11-03":
            return False
        if matcher.matches_person({"name": record["name"], "state": record["state"]}, people[0]):
            return True
        aliases = [
            candidate["name"],
            *[
                alias["name"]
                for alias in inputs.get("incumbent_backgrounds", {}).get("aliases", [])
                if alias["bioguide_id"] == people[0]["id"]["bioguide"]
                and alias["state"] == candidate["state"]
            ],
        ]
        return any(same_name(record["name"], alias) for alias in aliases)

    def observations(key):
        return [
            {
                **record,
                "bioguide_id": people[0]["id"]["bioguide"],
                "current_identity_label": False,
                "model_ready": False,
            }
            for record in inputs.get(key, [])
            if qualified(record)
        ]

    profiles = [
        record
        for record in inputs.get("official_profiles", [])
        if record["state"] == candidate["state"]
        and district(record["district"]) == district(candidate["district"])
        and record["party"] == candidate["party"]
        and same_name(record["name"], candidate["name"])
        and record["election_year"] == 2026
        and record.get("chamber") == "house"
        and record.get("fields")
    ]
    return {
        "reviewed_candidate_profiles": matched_profiles(candidate, inputs),
        "official_candidate_profiles": profiles,
        "official_member_profiles": [
            profile
            for profile in inputs.get("incumbent_backgrounds", {}).get("profiles", [])
            if len(people) == 1
            and legislative.get("house_incumbent") is True
            and profile["bioguide_id"] == people[0]["id"]["bioguide"]
            and profile["state"] == candidate["state"]
            and profile["chamber"] == "house"
        ],
        "dated_religion_observations": observations("religion_observations"),
        "member_authorized_biographies": observations("member_biographies"),
        "official_historian_observations": observations("historian_observations"),
        "reviewed_characteristic_observations": [
            record
            for record in inputs.get("reviewed_characteristic_observations", [])
            if all(
                str(record[key]) == str(candidate[key])
                for key in ("candidate_id", "contest_id", "name", "state", "district", "party")
            )
        ],
        "interpretation": (
            "Dated source evidence, not current verified identity or new model inputs; "
            "absence is unknown, never a negative classification"
        ),
    }


def background_observations(candidates, facts):
    by_id = {r["candidate_id"]: r for r in candidates}
    rows = []

    def append(candidate, field, value, source_kind, source_year, date, evidence, status):
        if value is None or value == "" or value == []:
            return
        rows.append(
            {
                **{
                    k: candidate[k]
                    for k in ("candidate_id", "contest_id", "name", "state", "district", "party")
                },
                "field": field,
                "value": json.dumps(value, ensure_ascii=True, sort_keys=True),
                "source_kind": source_kind,
                "source_year": source_year,
                "observation_date": date,
                "evidence": json.dumps(evidence, sort_keys=True),
                "qualification": status,
                "model_ready": False,
            }
        )

    for fact in facts:
        append(
            by_id[fact["candidate_id"]],
            fact["field"],
            fact["value"],
            "historical_campaign_extraction" if fact.get("historical") else "campaign_extraction",
            fact["source_year"],
            fact["first_capture_timestamp"],
            {"record_id": fact["record_id"], "parent_document_id": fact["parent_document_id"]},
            fact["review_status"],
        )
    for candidate in candidates:
        background = candidate["background"]
        for record in background.get("reviewed_characteristic_observations", []):
            append(
                candidate,
                {
                    "military": "military_service",
                    "religion": "religion_literal",
                    "age": "date_of_birth",
                }.get(record["trait"], record["trait"])
                if not (record["trait"] == "age" and isinstance(record["value"], dict))
                else "birth_interval",
                record["value"],
                record["source_kind"],
                int(record["publication_date"][:4]) if record["publication_date"] else None,
                record["publication_date"],
                {
                    **record["receipt"],
                    "supporting_fragment": record["fragment"],
                    "identity_qualification": record["identity_qualification"],
                },
                record["qualification"] + "; retrospectively_reviewed; descriptive_only",
            )
        for profile in background.get("reviewed_candidate_profiles", []):
            for field, value in sorted(profile["fields"].items()):
                append(
                    candidate,
                    field,
                    value,
                    profile["source_kind"],
                    None,
                    profile["evidence"]["retrieved_at"],
                    {
                        **profile["evidence"],
                        "supporting_fragments": profile["support"][field],
                        **(
                            {"field_review": profile["field_reviews"][field]}
                            if field in profile.get("field_reviews", {})
                            else {}
                        ),
                    },
                    profile["qualification"],
                )
        for profile in background.get("official_member_profiles", []):
            for field, value in profile["fields"].items():
                append(
                    candidate,
                    field,
                    value,
                    profile.get("source_kind", "official_congressional_biography"),
                    int(profile["evidence"]["publication_date"][:4])
                    if profile["evidence"]["publication_date"]
                    else None,
                    profile["evidence"]["publication_date"],
                    profile["evidence"],
                    profile["identity_qualification"] + "; descriptive_only; absence_unknown",
                )
        for profile in background["official_candidate_profiles"]:
            for field, value in profile["fields"].items():
                append(
                    candidate,
                    field,
                    value,
                    "official_candidate_supplied_profile",
                    profile["election_year"],
                    profile.get("publication_date"),
                    profile["evidence"],
                    profile["review_status"],
                )
        for record in background["dated_religion_observations"]:
            append(
                candidate,
                "religion_literal",
                record["religion_literal"],
                "dated_Pew_CQ_office_questionnaire",
                record["election_year"],
                record["publication_date"],
                {k: record[k] for k in ("source_id", "source_page", "source_line")},
                "historical_office_response; not_current_verified_affiliation",
            )
        for record in background["member_authorized_biographies"]:
            for field in ("birth_clause", "birth_state", "religion", "hispanic_origin", "races"):
                append(
                    candidate,
                    field,
                    record[field],
                    "member_authorized_directory",
                    record["election_year"],
                    record["publication_date"],
                    {k: record[k] for k in ("source_id", "source_page")},
                    record["qualification"],
                )
        for record in background["official_historian_observations"]:
            append(
                candidate,
                "historian_identity_group",
                record["identity_group"],
                "official_House_Historian_positive_identification",
                f"Congress {record['congress']}",
                None,
                {k: record[k] for k in ("source_id", "source_table_row")},
                "official_positive_classification; not_self_identification; absence_unknown",
            )
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(extract_official_profiles(args.root), indent=2))
