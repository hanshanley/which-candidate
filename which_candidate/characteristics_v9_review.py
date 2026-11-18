"""Reproduce bounded original-review dispositions without promoting reading leads."""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader

from .benchmarks import STATE_NAMES
from .characteristics_research import normalized
from .storage import fingerprint, read_rows, write_json

WORK = "artifacts/characteristics-v9"
OUTPUT = "data/house-characteristics-v9-source-review.json"
DIRECTORY = "phone2action-117th-freshman-guide-2021"
FIELDS = (
    "Birthdate",
    "Ethnicity",
    "Gender",
    "Religion",
    "Military Service",
    "Education",
    "Occupation",
    "Notable Facts",
)
REVIEWED_NONSUPPORT = {
    "campaign-140477-home": "Dated 2022 campaign shell with financial-platform marketing; "
    "no supported requested biographical field.",
    "campaign-140477-bio1": "Financial-platform marketing, not a candidate career statement.",
    "campaign-140479-home": "Paused campaign/JavaScript shell, no own biographical statement.",
    "campaign-220677-home": "Campaign navigation mixed with unrelated VoIP marketing; "
    "use the separately qualified biography and authored questionnaire.",
    "campaign-221035-home": "Church is an election-day polling/media location, not the "
    "candidate's religious affiliation.",
    "campaign-220098-bio1": "Elected school-board role is not automatically paid "
    "non-elected government employment.",
    "campaign-220098-bio2": "Elected school-board role is not automatically paid "
    "non-elected government employment.",
    "campaign-220329-bio1": "Council and appointed/advisory boards do not establish "
    "paid non-elected government employment.",
    "campaign-220516-bio1": "Elected legislative service is not the unchanged "
    "non-elected government-employment definition.",
    "campaign-221151-home": "Endorsement, cookie and campaign widgets, no supported "
    "own education or career statement.",
}


def directory_page(text):
    lines = [" ".join(line.split()) for line in text.splitlines() if line.strip()]
    heading = next(
        (i for i, line in enumerate(lines) if line.startswith("U.S. REPRESENTATIVE,")), None
    )
    if heading is None:
        return None
    header = lines[heading]
    state = next((s for s, name in STATE_NAMES.items() if f", {name}," in header), None)
    district = re.search(r"DISTRICT (\d+)", header)
    if not state or not district:
        return {"printed_name": lines[heading - 1], "disposition": "unparsed_House_header"}
    labels = re.compile(
        r"^(Birthplace|Birthdate|Residence|Election|Chamber Rank|Next Election|"
        r"Ethnicity|Gender|Religion|Marital Status|Spouse Name|Family|Military Service|"
        r"Notable Facts|Education|Occupation|Nickname|Pronunciation):\s*(.*)"
    )
    fields, active = {}, None
    for line in lines[heading + 1 :]:
        match = labels.match(line)
        if match:
            active = match[1]
            fields[active] = match[2]
        elif active in {"Education", "Occupation", "Notable Facts"}:
            if line not in {"Republican", "Democrat", "HOUSE"}:
                fields[active] += " " + line
    return {
        "printed_name": lines[heading - 1],
        "state": state,
        "district_2021": int(district[1]),
        "party_2021": next(
            line for line in lines[heading + 1 :] if line in {"Democrat", "Republican"}
        ),
        "nickname": fields.get("Nickname", ""),
        "fields": {k: v.strip() for k, v in fields.items() if k in FIELDS},
    }


def matches_directory(record, person):
    def words(text):
        return re.findall(r"\w+", normalized(text))

    printed = words(record["printed_name"])
    name = person["name"]
    surname = words(name["last"])
    return (
        printed[-len(surname) :] == surname
        and words(name["first"]) in [printed[:1], words(record.get("nickname", ""))]
        and any(
            term["type"] == "rep"
            and term["state"] == record["state"]
            and term.get("district") == record["district_2021"]
            and term["party"] == record["party_2021"]
            and term["start"] <= "2021-02-01" < term["end"]
            for term in person["terms"]
        )
    )


def directory_review(root, receipts):
    receipt = next(r for r in receipts if r["id"] == DIRECTORY and r["status"] == "acquired")
    path = root / WORK / DIRECTORY
    if fingerprint(path) != {k: receipt[k] for k in ("bytes", "sha256")}:
        raise ValueError("Changed freshman-directory original")
    inputs = read_rows(root / "results/house/source-inputs.jsonl.gz")[0]
    people = {p["id"]["bioguide"]: p for p in inputs["people"]}
    candidates = read_rows(root / "results/house/candidates.jsonl.gz")
    baseline = {
        (r["candidate_id"], r["trait"]): r
        for r in read_rows(root / "results/house-characteristics-v8/candidate-traits.jsonl.gz")
    }
    rows = []
    for number, page in enumerate(PdfReader(path).pages, 1):
        record = directory_page(page.extract_text() or "")
        if record is None:
            continue
        record.update(page=number, source_sha256=receipt["sha256"])
        if "fields" not in record:
            rows.append(record)
            continue
        matches = [
            c
            for c in candidates
            if c["legislative"].get("status")
            in {"exact_fec_service_crosswalk", "official_clerk_and_service_crosswalk"}
            and c["legislative"].get("bioguide_id") in people
            and matches_directory(record, people[c["legislative"]["bioguide_id"]])
        ]
        record["matched_candidate_ids"] = [c["candidate_id"] for c in matches]
        if len(matches) != 1:
            record["disposition"] = "no_unique_verified_native_2021_person_term"
            rows.append(record)
            continue
        candidate = matches[0]
        person = people[candidate["legislative"]["bioguide_id"]]
        record["native_name"] = candidate["name"]
        record["bioguide_id"] = person["id"]["bioguide"]
        birth = record["fields"].get("Birthdate", "")
        try:
            printed_birth = datetime.strptime(birth, "%m/%d/%Y").date().isoformat()
        except ValueError:
            printed_birth = None
        record["birthdate_conflict"] = (
            printed_birth is not None
            and person.get("bio", {}).get("birthday") is not None
            and printed_birth != person["bio"]["birthday"]
        )
        record["previously_unqualified_fields"] = [
            trait
            for label, trait in (
                ("Birthdate", "age"),
                ("Ethnicity", "race"),
                ("Gender", "gender"),
                ("Religion", "religion"),
                ("Military Service", "military"),
                ("Education", "education"),
                ("Occupation", "profession"),
            )
            if record["fields"].get(label)
            and not baseline[(candidate["candidate_id"], trait)]["factual_qualified"]
        ]
        service = record["fields"].get("Military Service")
        record["military_disposition"] = (
            "source_None_semantics_unverified_and_2021_not_2026"
            if service == "None"
            else "no_field_not_negative"
            if service is None
            else "literal_historical_positive_not_automatically_new_coverage"
        )
        record["disposition"] = (
            "retain_field_specific_conflict_no_automatic_promotion"
            if record["birthdate_conflict"]
            else "historical_directory_report_no_automatic_2026_promotion"
        )
        rows.append(record)
    return {
        "source": {k: receipt[k] for k in ("id", "url", "sha256", "bytes")},
        "population": "117th Congress freshmen in this February 2021 directory, not 2026 nominees",
        "qualification": "Literal source fields, not independent verification. Missing/None "
        "semantics and current-vintage negatives require publisher clarification. Identity "
        "requires native service crosswalk plus source name/nickname, 2021 state/district/party.",
        "records": rows,
    }


def build(root):
    root = Path(root)
    acquisition = json.loads((root / "data/house-characteristics-v9-acquisitions.json").read_text())
    leads = json.loads((root / WORK / "retained-unused-review.json").read_text())
    accepted = {
        d["source_id"]
        for d in acquisition["extraction_decisions"]
        if d.get("source_id") and d["accepted"]
    }
    held = {
        d["source_id"]
        for d in acquisition["extraction_decisions"]
        if d.get("source_id") and not d["accepted"]
    }
    reviews = []
    for lead in leads:
        key = lead["id"]
        reviews.append(
            {k: lead[k] for k in ("id", "candidate_id", "url", "sha256", "text_characters")}
            | {
                "disposition": (
                    "accepted_literal_extraction_correction"
                    if key in accepted
                    else "identity_bridge_still_held"
                    if key in held
                    else "unrelated_gambling_content_not_candidate_evidence"
                    if key == "campaign-220012-home"
                    else "reviewed_scope_or_subject_does_not_support_missing_field"
                    if key in REVIEWED_NONSUPPORT
                    else "bounded_field_excerpts_reviewed_no_claim_registered"
                    if lead.get("reading_excerpts")
                    else "no_original_marker_full_body_review_not_asserted"
                ),
                "review_scope": "Bounded field-directed excerpts plus selected full readings; "
                "not a claim of exhaustive manual review of every full original.",
                **(
                    {"specific_nonsupport_reason": REVIEWED_NONSUPPORT[key]}
                    if key in REVIEWED_NONSUPPORT and key not in accepted
                    else {}
                ),
            }
        )
    result = {
        "retained_original_reviews": reviews,
        "freshman_directory": directory_review(root, acquisition["discovery_dispositions"]),
        "south_carolina": {
            "method": "Ordinary public General 2026 selector, declared House search POST, "
            "candidate-detail link and public signed SICPP form; no access bypass.",
            "inspected_source_ids": [
                "south-carolina-general-search-2026",
                "south-carolina-candidate-search-script",
                "south-carolina-house-search-results-2026",
                "south-carolina-khalifa-public-detail-2026",
                "south-carolina-khalifa-filed-statement-2026",
            ],
            "fields": ["office", "party", "ballot_name", "filing_date", "candidate_status"],
            "signed_form": "SEC FORM 1009-202312, one scanned page, directly rendered and read; "
            "legal name Zyon El-Khalifa, ballot name Zyon Khalifa, Democratic, House district 2. "
            "Contact/registration fields excluded from analytical exports.",
            "outcome": "No age, gender, race, ethnicity, religion, education, occupation or "
            "service-history field on the inspected statement. Do not fetch every candidate's "
            "unchanged form to inflate document totals.",
        },
    }
    write_json(root / OUTPUT, result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    result = build(Path(__file__).resolve().parents[1])
    print("Retained review records:", len(result["retained_original_reviews"]))
    print("Directory House records:", len(result["freshman_directory"]["records"]))
