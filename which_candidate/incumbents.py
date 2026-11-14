"""Source-qualified incumbent biographies and a field-by-field completeness audit."""

import argparse
import bisect
import io
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from pypdf import PdfReader

from .benchmarks import STATE_NAMES
from .corrected import same_name, text
from .features import FeatureSources
from .pipeline import csv_bytes
from .storage import fingerprint, read_rows, write_json

CUTOFF = "2026-11-03"
CACHE = "data/raw/incumbents-20261114"
HEADER = re.compile(
    r"(?m)^[ \t]*([A-ZÀ-Þ][^;\n]{2,140}?),\s*"
    r"(Democrat(?:ic-Farmer-Labor(?: Party)?)?|Republican|Independent)(?:,|\s+of\b)"
)
LABEL = re.compile(
    r"\b(education|professional history|military service|election history|religion|"
    r"committees|caucuses|married|children|family|awards|memberships):",
    re.I,
)
FIELDS = {
    "education": "education",
    "professional history": "professional_history",
    "military service": "military_service",
    "election history": "election_history",
}
# Reviewed directory URLs for the same named member, state and active service record.
DIRECTORY_URL_ALIASES = {
    "dingell.house.gov": ("D000624", "MI"),
    "gregmurphy.house.gov": ("M001210", "NC"),
}
HISTORIAN = (
    ("G000606", "36507227802", "AZ"),
    ("G000607", None, "CA"),
    ("W000832", "36507230766", "CA"),
    ("F000485", "36507228813", "GA"),
    ("M001246", "36507228865", "NJ"),
    ("V000139", "36507227933", "TN"),
    ("M001245", "36507228199", "TX"),
    ("C001132", "25769822933", "AZ"),
    ("N000188", "15032409258", "NJ"),
    ("A000380", "36507223511", "RI"),
    ("S001185", "22624", "AL"),
)
EXTRA_SOURCES = (
    (
        "hamadeh-alias",
        "https://hamadeh.house.gov/contact/",
        "H001098",
        "AZ",
        None,
        "Abe Hamadeh",
        None,
    ),
    (
        "patronis-religion",
        "https://patronis.house.gov/about/meet-congressman-jimmy-patronis",
        "P000622",
        "FL",
        "Christian",
        "Jimmy Patronis is a Christian",
        None,
    ),
    (
        "fine-religion",
        "https://fine.house.gov/issues/issue/?IssueID=14969",
        "F000484",
        "FL",
        "Jewish",
        "As a proud Jewish American",
        None,
    ),
    (
        "fuller-religion",
        "https://clayfullerforgeorgia.com/",
        "F000485",
        "GA",
        "Christian",
        "As a devout Christian, Clay",
        None,
    ),
    (
        "gallagher-religion",
        "https://www.legistorm.com/stormfeed/view_rss/2239765/member/4916/title/"
        "gallagher-statement-on-assembly-honoring-anti-catholic-hate-group.html",
        "G000607",
        "CA",
        "Christian",
        "As a Christian, I love all people",
        "2023-06-05",
    ),
    (
        "wahab-religion",
        "https://pod.wave.co/podcast/the-joy-reid-show/"
        "the-muslims-are-coming-the-joy-reid-show-live",
        "W000832",
        "CA",
        "Muslim",
        "I am an Afghan, I am a Muslim",
        None,
    ),
    (
        "vanepps-religion",
        "https://www.govinfo.gov/content/pkg/CREC-2025-12-04/pdf/CREC-2025-12-04-pt1-PgH5030-5.pdf",
        "V000139",
        "TN",
        "Christian",
        "I come to this distinguished body as a Christian",
        "2025-12-04",
    ),
)


def host(url):
    return urlparse(url).netloc.casefold().removeprefix("www.")


def clean(value):
    value = re.sub(r"[-\u2010\u2013]\s*\n\s*(?=[a-z])", "", value)
    return " ".join(value.split()).strip(" ;")


def directory_profiles(pages):
    """Keep labelled factual sections, never offices, staff or personal details."""
    pages = [
        re.sub(r"^\d+[ \t]*(?:119th Congress|Congressional Directory)[^\n]*\n", "", page)
        for page in pages
    ]
    starts, offset = [], 0
    for page in pages:
        starts.append(offset)
        offset += len(page) + 1
    body = "\n".join(pages)
    headers = list(HEADER.finditer(body))
    result = []
    for index, header in enumerate(headers):
        end = headers[index + 1].start() if index + 1 < len(headers) else len(body)
        block = body[header.end() : end]
        office = re.search(r"\nCongressional Offices?\s*\n(https?://\S+)", block)
        if not office:
            continue
        biography = clean(block[: office.start()])
        labels = list(LABEL.finditer(biography))
        fields = {}
        born = re.search(r"\bborn\b[^;]*", biography)
        if born:
            fields["birth_clause"] = born[0]
        for position, label in enumerate(labels):
            field = FIELDS.get(label[1].casefold())
            stop = labels[position + 1].start() if position + 1 < len(labels) else len(biography)
            if field and (value := biography[label.end() : stop].strip(" ;.")):
                fields[field] = value
        result.append(
            {
                "source_member_name": clean(header[1]),
                "source_party": header[2],
                "official_member_url": office[1],
                "source_page": bisect.bisect_right(starts, header.start()),
                "fields": fields,
            }
        )
    return result


def historian_profile(html, bioguide_id):
    """Extract only the concise biography from the ID-qualified official page."""
    if bioguide_id not in html:
        raise ValueError(f"Historian page does not identify {bioguide_id}")
    parts = text(html).splitlines()
    candidates = [
        p for p in parts if "a Representative from " in p and "; born " in p and "; elected " in p
    ]
    if len(set(candidates)) != 1:
        raise ValueError(f"Ambiguous concise biography for {bioguide_id}")
    biography = candidates[0]
    fields, career, education, military = {}, [], [], []
    for clause in biography.split(";"):
        clause = clause.strip()
        if clause.startswith("born "):
            fields["birth_clause"] = clause
        elif clause.startswith("elected "):
            fields["election_history"] = clause.rstrip(".")
        elif re.match(
            r"(?:graduated|attended|[A-Z]\.(?:[A-Za-z]\.?){1,8},|Ph\.D\.|Marshall Scholar)",
            clause,
        ):
            education.append(clause)
        elif re.search(r"\b(?:U\.S\.|United States) (?:Army|Navy|Air Force|Marine)", clause) or (
            "National Guard" in clause
        ):
            military.append(clause)
        elif "a Representative from " not in clause:
            career.append(clause)
    for key, values in (
        ("education", education),
        ("professional_history", career),
        ("military_service", military),
    ):
        if values:
            fields[key] = "; ".join(values)
    return {"source_member_name": biography.split(", a Representative", 1)[0], "fields": fields}


def veteran_profiles(pages, people):
    states = "|".join(re.escape(s.title()) for s in STATE_NAMES.values())
    header = re.compile(
        r"(?m)^\s*(\d+)\.\s+(.+?)\s+(Democrat|Republican|Independent)"
        r"\s+(" + states + r")\s+(At Large|\d{1,2})\s+"
    )
    body = "\n".join(pages)
    headers = list(header.finditer(body))
    matcher = FeatureSources({"sources": []}, None)
    result = []
    for index, match in enumerate(headers):
        state = next(k for k, v in STATE_NAMES.items() if v.title() == match[4])
        end = headers[index + 1].start() if index + 1 < len(headers) else len(body)
        branch = body[match.end() : end]
        branch = re.split(
            r"(?m)^\s*\d+\.\s+|Page \d|Military Veterans|UNITED STATES HOUSE|REPRESENTATIVE",
            branch,
        )[0]
        name = match[2].replace("\n", " ")
        linked = [
            p
            for p in people
            if any(
                t["type"] == "rep" and t["state"] == state and t["start"] <= CUTOFF < t["end"]
                for t in p["terms"]
            )
            and matcher.matches_person({"name": name, "state": state}, p)
        ]
        if len(linked) == 1 and clean(branch):
            result.append(
                {
                    "bioguide_id": linked[0]["id"]["bioguide"],
                    "state": state,
                    "chamber": "house",
                    "source_member_name": name,
                    "source_table_row": int(match[1]),
                    "fields": {"military_service": clean(branch)},
                    "identity_qualification": "official_Clerk_positive_veteran_listing; name_state_service",
                    "model_ready": False,
                }
            )
    return result


def pinned_inputs(root):
    folder = Path(root) / "results/2026-v3/inputs"
    manifest = json.loads((folder / "manifest.json").read_text())
    result = {}
    for key, name in (
        ("current_voting_records", "cutoff-records.jsonl.gz"),
        ("clerk_members", "house-membership-at-cutoff.jsonl.gz"),
    ):
        if fingerprint(folder / name) != manifest[name]:
            raise ValueError(f"Changed pinned incumbent input: {name}")
        result[key] = read_rows(folder / name)
    return result


def clerk_person(candidate, people, members):
    """An independent service link; it does not resolve ambiguous campaign IDs."""
    parties = {
        "Democratic": "D",
        "Republican": "R",
        "Independent": "I",
        "No Party Preference": "I",
    }
    matches = []
    for record in members:
        if record["publication_date"] != CUTOFF:
            raise ValueError("Clerk source must be the Election Day snapshot")
        member = ET.fromstring(record["native_xml"]).find("member-info")
        state = member.find("state").get("postal-code")
        if state != candidate["state"] or member.findtext("party") != parties.get(
            candidate["party"]
        ):
            continue
        if not same_name(candidate["name"], member.findtext("official-name")):
            continue
        bioguide = member.findtext("bioguideID")
        linked = [p for p in people if p["id"]["bioguide"] == bioguide]
        sworn = member.find("sworn-date")
        if len(linked) != 1 or sworn is None or sworn.get("date", "99999999") > "20261103":
            continue
        if not any(
            t["type"] == "rep" and t["state"] == state and t["start"] <= CUTOFF < t["end"]
            for t in linked[0]["terms"]
        ):
            continue
        matches.append((linked[0], record))
    return matches[0] if len(matches) == 1 else (None, None)


def profile_inputs(root):
    path = Path(root) / "data/incumbent-backgrounds.json"
    return json.loads(path.read_text()) if path.exists() else {"profiles": [], "aliases": []}


def acquire(root):
    root = Path(root)
    inputs = read_rows(root / "results/house/source-inputs.jsonl.gz")[0]
    cache = root / CACHE
    cache.mkdir(parents=True, exist_ok=True)
    receipt_path = root / "data/incumbent-background-sources.json"
    prior = json.loads(receipt_path.read_text()) if receipt_path.exists() else profile_inputs(root)
    receipts = {r["id"]: r for r in prior.get("sources", [])}
    failures = []

    def persist():
        write_json(
            receipt_path,
            {"sources": sorted(receipts.values(), key=lambda r: r["id"]), "failures": failures},
        )

    def download(key, url):
        pdf = url.endswith(".pdf")
        path = cache / f"{key}.{'pdf' if pdf else 'html'}"
        if key in receipts:
            if fingerprint(path) != {k: receipts[key][k] for k in ("bytes", "sha256")}:
                raise ValueError(f"Changed original incumbent source: {key}")
            return path.read_bytes() if pdf else path.read_text()
        proc = subprocess.run(
            ["curl", "--fail", "--location", "--max-time", "60", "--silent", "--show-error", url],
            capture_output=True,
        )
        if proc.returncode:
            failures.append(
                {
                    "id": key,
                    "url": url,
                    "disposition": "not_bypassed",
                    "error": proc.stderr.decode(),
                }
            )
            persist()
            return None
        path.write_bytes(proc.stdout)
        receipts[key] = {
            "id": key,
            "url": url,
            "path": str(path.relative_to(root)),
            **fingerprint(path),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "publication_date": None,
            "temporal_status": "undated_page_retrieved_after_election; model_ineligible",
        }
        persist()
        return proc.stdout if pdf else proc.stdout.decode()

    specs = json.loads((root / "data/research-sources.json").read_text())["sources"]
    directory = next(s for s in specs if s["id"] == "congressional_directory_2026")
    path = root / "data" / directory["path"]
    if fingerprint(path) != {k: directory[k] for k in ("bytes", "sha256")}:
        raise ValueError("Changed original congressional directory")
    receipt = {
        "id": directory["id"],
        "url": directory["origin_url"],
        "path": str(path.relative_to(root)),
        **fingerprint(path),
        "publication_date": directory["publication_date"],
        "temporal_status": "published_before_election",
    }
    receipts[receipt["id"]] = receipt
    pages = [p.extract_text() for p in PdfReader(path).pages[:327]]
    parsed = directory_profiles(pages)
    people = inputs["people"]
    by_host = {}
    for person in people:
        for term in person["terms"]:
            if term["type"] == "rep" and term["start"] <= CUTOFF < term["end"] and term.get("url"):
                by_host.setdefault(host(term["url"]), {})[person["id"]["bioguide"]] = person
    by_id = {p["id"]["bioguide"]: p for p in people}
    profiles = []
    for profile in parsed:
        member_host = host(profile["official_member_url"])
        linked = list(by_host.get(member_host, {}).values())
        if not linked and member_host in DIRECTORY_URL_ALIASES:
            bioguide, state = DIRECTORY_URL_ALIASES[member_host]
            person = by_id[bioguide]
            name = re.sub(r",?\s*M\.D\.\s*$", "", profile["source_member_name"])
            if not FeatureSources({"sources": []}, None).matches_person(
                {"name": name, "state": state}, person
            ):
                raise ValueError("Reviewed directory website alias no longer matches")
            linked = [person]
        if len(linked) != 1:
            continue
        person = linked[0]
        active = [
            t for t in person["terms"] if t["type"] == "rep" and t["start"] <= CUTOFF < t["end"]
        ]
        if len(active) != 1:
            continue
        profiles.append(
            {
                **profile,
                "bioguide_id": person["id"]["bioguide"],
                "state": active[0]["state"],
                "chamber": "house",
                "evidence": {**receipt, "source_page": profile["source_page"]},
                "source_kind": "official_congressional_directory",
                "identity_qualification": "unique_active_official_member_url; reviewed_aliases",
                "model_ready": False,
            }
        )
    for bioguide, detail, state in HISTORIAN:
        key = f"historian-{bioguide}"
        url = (
            "https://history.house.gov/People/Listing/G/GALLAGHER,-James-(G000607)/"
            if bioguide == "G000607"
            else f"https://history.house.gov/People/Detail/{detail}"
        )
        html = download(key, url)
        if html is not None:
            profiles.append(
                {
                    **historian_profile(html, bioguide),
                    "bioguide_id": bioguide,
                    "state": state,
                    "chamber": "house",
                    "evidence": receipts[key],
                    "source_kind": "official_House_Historian_biography",
                    "identity_qualification": "official_Historian_stable_bioguide_id",
                    "model_ready": False,
                }
            )
    aliases = []
    for key, url, bioguide, state, literal, marker, published in EXTRA_SOURCES:
        html = download(key, url)
        if html is None:
            continue
        value = clean(
            "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(html)).pages)
            if isinstance(html, bytes)
            else text(html)
        )
        if published:
            receipts[key]["publication_date"] = published
            receipts[key]["temporal_status"] = "dated_public_self_description_before_election"
            persist()
        if key == "hamadeh-alias":
            if "Abe Hamadeh" not in value:
                raise ValueError("Official Hamadeh alias no longer present")
            aliases.append(
                {
                    "bioguide_id": bioguide,
                    "name": "Abe Hamadeh",
                    "state": state,
                    "evidence": receipts[key],
                }
            )
            continue
        if marker not in value:
            raise ValueError(f"Explicit religious self-description absent: {key}")
        profiles.append(
            {
                "bioguide_id": bioguide,
                "state": state,
                "chamber": "house",
                "fields": {"religion_literal": literal},
                "evidence": receipts[key],
                "source_kind": (
                    "published_interview_transcript"
                    if key == "wahab-religion"
                    else "archived_official_press_release"
                    if key == "gallagher-religion"
                    else "official_congressional_record_self_description"
                    if key == "vanepps-religion"
                    else "candidate_campaign_self_description"
                    if key == "fuller-religion"
                    else "official_member_self_description"
                ),
                "identity_qualification": (
                    "published_interview_self_description; not_audio_verified"
                    if key == "wahab-religion"
                    else "archived_official_self_description"
                    if key == "gallagher-religion"
                    else "direct_public_self_description"
                ),
                "model_ready": False,
            }
        )
    reviewed_path = root / "data/incumbent-reviewed-observations.json"
    if reviewed_path.exists():
        for profile in json.loads(reviewed_path.read_text())["profiles"]:
            key = f"reviewed-{profile['bioguide_id']}"
            evidence = {
                "id": key,
                "url": profile["source_url"],
                "path": str(reviewed_path.relative_to(root)),
                **fingerprint(reviewed_path),
                "publication_date": profile["publication_date"],
                "temporal_status": "dated_statement; present_rendering_not_archived_at_election",
                "acquisition_method": profile["acquisition_method"],
                "original_html_acquired": profile["original_html_acquired"],
            }
            receipts[key] = evidence
            profiles.append({**profile, "evidence": evidence})
        persist()
    key = "clerk-veterans-2026"
    original = download(key, "https://clerk.house.gov/documents/Military%20Veterans.pdf")
    if original is not None:
        veteran_pages = [p.extract_text() for p in PdfReader(io.BytesIO(original)).pages]
        if "October 1, 2026" not in "\n".join(veteran_pages):
            raise ValueError("Clerk veterans list no longer has the reviewed pre-election date")
        receipts[key]["publication_date"] = "2026-10-01"
        receipts[key]["temporal_status"] = "published_before_election"
        persist()
        profiles.extend(
            {
                **p,
                "evidence": receipts[key],
                "source_kind": "official_Clerk_positive_veteran_roster",
            }
            for p in veteran_profiles(veteran_pages, people)
        )
    result = {
        "scope": "Source-qualified member biographies and public self-descriptions; not new model inputs",
        "profiles": profiles,
        "aliases": aliases,
        "sources": sorted(receipts.values(), key=lambda r: r["id"]),
        "failures": failures,
    }
    write_json(root / "data/incumbent-backgrounds.json", result)
    return {"profiles": len(profiles), "sources": len(receipts), "failures": failures}


def incumbent_tables(candidates, inputs):
    rows = []
    for candidate in candidates:
        legislative = candidate["legislative"]
        if legislative["house_incumbent"] is not True:
            continue
        bioguide = legislative["bioguide_id"]
        profiles = candidate["background"].get("official_member_profiles", [])
        fields = {}
        for profile in profiles:
            for key, value in profile["fields"].items():
                fields.setdefault(key, []).append(value)
        religion = sorted(
            candidate["background"]["dated_religion_observations"],
            key=lambda r: r["publication_date"],
        )
        latest = religion[-1] if religion else None
        literal = latest["religion_literal"] if latest else None
        religion_date = latest["publication_date"] if latest else None
        religion_status = "no_qualified_disclosure"
        if latest:
            religion_status = (
                "explicit_unknown_or_refused"
                if re.search(r"unknown|refused|don.t know", literal, re.I)
                else "dated_office_response; current_affiliation_unverified"
            )
        direct = [p for p in profiles if "religion_literal" in p["fields"]]
        if not latest and direct:
            selected = max(direct, key=lambda p: p["evidence"]["publication_date"] or "")
            literal = selected["fields"]["religion_literal"]
            religion_date = selected["evidence"]["publication_date"]
            religion_status = (
                "dated_public_self_description"
                if religion_date and religion_date < CUTOFF
                else "undated_public_self_description; not_pre_election_verified"
            )
        voting = [
            r
            for r in inputs.get("current_voting_records", [])
            if r["bioguide_id"] == bioguide and r["chamber"] == "house"
        ]
        if len(voting) > 1:
            raise ValueError(f"Ambiguous current voting record: {bioguide}")
        vote = voting[0] if voting else {}
        people = [p for p in inputs["people"] if p["id"]["bioguide"] == bioguide]
        person = people[0]
        terms = [
            (date.fromisoformat(t["start"]), min(date.fromisoformat(t["end"]), date(2026, 11, 3)))
            for t in person["terms"]
            if t["type"] == "rep" and t["start"] < CUTOFF
        ]
        merged = []
        for start, end in sorted(terms):
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
            else:
                merged.append((start, end))
        prior = legislative.get("prior_voting_record") or {}
        rows.append(
            {
                **{
                    k: candidate[k]
                    for k in ("candidate_id", "contest_id", "name", "state", "district", "party")
                },
                "bioguide_id": bioguide,
                "fec_id": candidate["identity"]["fec_id"],
                "service_identity_status": legislative["status"],
                "age_at_election": legislative["age_at_election"],
                "source_recorded_gender": legislative["source_recorded_gender"],
                "first_house_service": min(start for start, _ in merged).isoformat(),
                "house_service_days_at_election": sum((end - start).days for start, end in merged),
                **{
                    field: fields[field][0] if fields.get(field) else None
                    for field in (
                        "birth_clause",
                        "education",
                        "professional_history",
                        "military_service",
                        "election_history",
                    )
                },
                "military_status": "explicit_positive_service"
                if fields.get("military_service")
                else "not_stated_in_structured_official_biography; not_a_negative",
                "religion_literal": literal,
                "religion_observation_date": religion_date,
                "religion_status": religion_status,
                "current_congress": 119,
                "voting_source_party_code": vote.get("party_code"),
                "voting_record_scope": (
                    "source member/party-coded spell; not guaranteed full-Congress coverage; "
                    "unity is relative to the source party, not necessarily native ballot affiliation"
                ),
                "voting_cutoff_exclusive": CUTOFF,
                "cast_yea_nay_votes": vote.get("cast_votes"),
                "party_unity_votes": vote.get("unity_votes"),
                "votes_with_party": vote.get("with_party"),
                "party_unity_score": vote.get("unity_score"),
                "last_party_unity_vote": vote.get("last_unity_vote"),
                "voting_status": (
                    "cutoff_only_party_unity; minimum_50_party_dividing_votes"
                    if vote.get("unity_score") is not None
                    else "record_present_but_below_50_party_dividing_votes"
                    if vote
                    else "no_qualified_cutoff_record"
                ),
                "prior_congress": 118,
                "prior_nokken_poole_dim1": prior.get("nokken_poole_dim1"),
                "historical_donor_score": candidate["donor"].get("score")
                if candidate["donor"].get("name_screen") == "consistent"
                else None,
                "biography_evidence": json.dumps([p["evidence"] for p in profiles], sort_keys=True),
                "religion_evidence": json.dumps(
                    latest or [p for p in profiles if "religion_literal" in p["fields"]],
                    sort_keys=True,
                ),
                "voting_evidence": json.dumps(vote, sort_keys=True),
                "service_evidence": json.dumps(legislative["evidence"], sort_keys=True),
                "positive_historian_identity_groups": ";".join(
                    sorted(
                        {
                            r["identity_group"]
                            for r in candidate["background"]["official_historian_observations"]
                        }
                    )
                )
                or None,
                "identity_classification_status": (
                    "positive_official_Historian_classification; not_self_identification"
                    if candidate["background"]["official_historian_observations"]
                    else "no_positive_Historian_observation; not_a_negative"
                ),
                "historian_identity_evidence": json.dumps(
                    candidate["background"]["official_historian_observations"], sort_keys=True
                ),
                "new_background_fields_model_ready": False,
            }
        )
    fields = (
        "age_at_election",
        "source_recorded_gender",
        "first_house_service",
        "birth_clause",
        "education",
        "professional_history",
        "military_service",
        "religion_literal",
        "cast_yea_nay_votes",
        "party_unity_score",
        "prior_nokken_poole_dim1",
        "historical_donor_score",
        "positive_historian_identity_groups",
    )
    gaps = [
        {
            **{k: row[k] for k in ("candidate_id", "name", "state", "district", "bioguide_id")},
            "field": field,
            "status": row["military_status"]
            if field == "military_service"
            else row["religion_status"]
            if field == "religion_literal"
            else row["voting_status"]
            if field in ("cast_yea_nay_votes", "party_unity_score")
            else row["identity_classification_status"]
            if field == "positive_historian_identity_groups"
            else "no_qualified_observation; not_zero",
        }
        for row in rows
        for field in fields
        if row[field] is None
        or (field == "religion_literal" and row["religion_status"] == "explicit_unknown_or_refused")
    ]
    report = {
        "scope": "Incumbent candidates qualified at the November 3, 2026 cutoff",
        "candidates": len(rows),
        "party_counts": dict(sorted(Counter(r["party"] for r in rows).items())),
        "coverage": {f: sum(r[f] is not None for r in rows) for f in fields},
        "religion_statuses": dict(sorted(Counter(r["religion_status"] for r in rows).items())),
        "substantive_religion_observations": sum(
            r["religion_status"] not in ("no_qualified_disclosure", "explicit_unknown_or_refused")
            for r in rows
        ),
        "voting_statuses": dict(sorted(Counter(r["voting_status"] for r in rows).items())),
        "interpretation": (
            "Complete incumbent rows, not universally disclosed traits. Religion responses can "
            "be dated, refused or unknown. Military omission is not nonservice. Current voting, "
            "prior ideology and historical donor scores are distinct. New biographies are "
            "descriptive and do not refit frozen performance models."
        ),
    }
    return rows, gaps, report


def write_tables(folder, candidates, inputs):
    rows, gaps, report = incumbent_tables(candidates, inputs)
    cohort = []
    for source in inputs.get("clerk_members", []):
        member = ET.fromstring(source["native_xml"]).find("member-info")
        state = member.find("state").get("postal-code")
        name, bioguide = member.findtext("official-name"), member.findtext("bioguideID")
        matches = [c for c in candidates if c["state"] == state and same_name(c["name"], name)]
        accepted = [r for r in rows if r["bioguide_id"] == bioguide]
        cohort.append(
            {
                "bioguide_id": bioguide,
                "official_name": name,
                "state": state,
                "official_district": member.findtext("district"),
                "candidate_ids": ";".join(c["candidate_id"] for c in (accepted or matches)),
                "disposition": (
                    "qualified_incumbent_candidate"
                    if accepted
                    else "candidate_label_present_but_identity_held"
                    if matches
                    else "no_matching_candidate_label_in_pinned_returns; not_proof_of_non_candidacy"
                ),
            }
        )
    report["clerk_cohort_dispositions"] = dict(
        sorted(Counter(r["disposition"] for r in cohort).items())
    )
    (folder / "incumbents.csv").write_bytes(csv_bytes(rows))
    (folder / "incumbent-missing-fields.csv").write_bytes(csv_bytes(gaps))
    (folder / "incumbent-cohort-audit.csv").write_bytes(csv_bytes(cohort))
    write_json(folder / "incumbent-coverage.json", report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(acquire(args.root), indent=2))
