"""Complete House roster and source-qualified candidate information, not new model fits."""

import argparse
import csv
import gzip
import hashlib
import json
import re
import urllib.error
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import pyarrow.parquet as pq

from .candidate_databases import DIME_URL, _fetch, select_campaignview, select_dime
from .corrected import same_name
from .features import name_matches, read_candidate_master
from .house_backgrounds import (
    acquire_background_inputs,
    background_observations,
    background_profile,
)
from .pipeline import csv_bytes
from .rebuild import (
    CACHE,
    ROOT,
    capture_before_cutoff,
    csv_rows,
    district,
    source_receipts,
    unique_facts,
)
from .storage import fingerprint, read_rows, write_json, write_rows

PARTIES = {
    "Democratic": {"DEM", "DFL", "DNL"},
    "Republican": {"REP"},
    "Independent": {"IND"},
    "Libertarian": {"LIB"},
    "Green": {"GRE"},
    "Nonpartisan": {"N"},
    "Unaffiliated": {"UN"},
    "No Party Affiliation": {"NPA"},
    "No Party Preference": {"NOP"},
    "Constitution": {"CON"},
    "Conservative": {"CRV"},
    "Independent American": {"IAP"},
    "Pacific Green": {"PG"},
    "Natural Law": {"NLP"},
    "Socialist Workers": {"SWP"},
    "U.S. Taxpayers": {"UST"},
}
AGGREGATES = {"write-in", "write-ins", "write in", "none of the above", "other", "scattering"}


def is_person(name):
    return bool(name and name.strip()) and name.strip().casefold() not in AGGREGATES


def matches_name(name, record):
    return same_name(name, record["name"]) or name_matches(name, record["first"], record["last"])


def resolve_identity(candidate, fec_rows, websites, people=()):
    codes = PARTIES.get(candidate["party"], set())
    context = [
        r
        for r in fec_rows
        if r["election_year"] == 2026
        and r["chamber"] == "house"
        and r["state"] == candidate["state"]
        and (
            r["party"] in codes
            or (
                candidate["party"] == "Write-In"
                and district(r["district"]) == district(candidate["district"])
            )
        )
    ]

    def qualified_name(name, record):
        if matches_name(name, record):
            return True
        for person in people:
            if record["fec_id"] not in person["id"].get("fec", []):
                continue
            source = person["name"]
            aliases = [
                (source.get("nickname") or source["first"], source["last"]),
                *[
                    (a.get("first", source["first"]), a.get("last", source["last"]))
                    for a in person.get("other_names", [])
                ],
            ]
            if name_matches(name, source["first"], source["last"], aliases):
                return True
            for key in ("wikipedia", "ballotpedia"):
                title = re.sub(r"\s*\(.*\)$", "", person["id"].get(key, "").replace("_", " "))
                if same_name(name, title):
                    return True
        return False

    official = [r for r in context if qualified_name(candidate["name"], r)]
    ids = {r["fec_id"] for r in official}
    party = {"Democratic": "D", "Republican": "R"}.get(candidate["party"])
    if candidate["party"] == "Write-In" and len(ids) == 1:
        registration_parties = {r["party"] for r in official}
        if len(registration_parties) == 1:
            party = {"DEM": "D", "REP": "R"}.get(next(iter(registration_parties)))
    web = [
        r
        for r in websites
        if party
        and r["year"] == "2026"
        and r["office"] == "house"
        and r["state"] == candidate["state"]
        and r["party"] == party
        and (
            same_name(candidate["name"], r["candidate"])
            or any(
                r["cand_id"] == o["fec_id"] and qualified_name(r["candidate"], o) for o in official
            )
        )
        and (r["cand_id"] in ids or district(r["district"]) == district(candidate["district"]))
    ]
    web_ids = {r["cand_id"] for r in web if r["cand_id"]}
    if len(ids) == 1 and (not web_ids or web_ids == ids):
        fec_id = next(iter(ids))
        same_district = any(
            district(r["district"]) == district(candidate["district"]) for r in official
        )
        status = "official_name_party_year_state"
        if not same_district:
            status += "; registration_district_differs"
        if candidate["party"] == "Write-In":
            status += "; write_in_is_ballot_label; district_required"
    elif len(ids & web_ids) == 1 and len(web_ids) == 1:
        fec_id, status = next(iter(web_ids)), "official_and_publisher_concordance"
    elif not ids and len(web_ids) == 1:
        fec_id, status = next(iter(web_ids)), "publisher_name_party_year_district"
    else:
        fec_id = None
        status = "ambiguous_or_conflicting" if ids or len(web_ids) > 1 else "unmatched"
    website = [r for r in web if r["cand_id"] == fec_id]
    return {
        "fec_id": fec_id,
        "status": status,
        "official_alternatives": official,
        "publisher_alternatives": [
            {"candidate_cycle_id": r["candidate_cycle_id"], "fec_id": r["cand_id"]} for r in web
        ],
        "website": website[0] if len(website) == 1 else None,
    }


def acquire_inputs(root):
    cache = root / CACHE
    receipts = source_receipts(cache)
    specs = json.loads((root / "data/research-sources.json").read_text())["sources"]
    fec, people, members, originals = [], [], [], []
    for spec in specs:
        if spec["kind"] not in ("fec_candidate_master", "legislators", "voteview_members"):
            continue
        path = root / "data" / spec["path"]
        if fingerprint(path) != {key: spec[key] for key in ("sha256", "bytes")}:
            raise ValueError(f"Changed research source: {spec['id']}")
        originals.append({"id": spec["id"], "url": spec["origin_url"], **fingerprint(path)})
        if spec["kind"] == "fec_candidate_master":
            fec.extend(r for r in read_candidate_master(path, spec) if r["chamber"] == "house")
        elif spec["kind"] == "legislators":
            for index, person in enumerate(json.loads(path.read_bytes())):
                if not any(t["type"] == "rep" and t["end"] >= "2023" for t in person["terms"]):
                    continue
                people.append(
                    {
                        **person,
                        "evidence": {"source_id": spec["id"], "json_pointer": f"/{index}"},
                    }
                )
        else:
            for number, row in enumerate(csv_rows(path), 2):
                if row["congress"] == "118" and row["chamber"] == "House":
                    members.append({**row, "source_id": spec["id"], "source_row": number})
    websites = [
        r for r in csv_rows(cache / "candidate-year-universe.csv") if r["office"] == "house"
    ]
    documents = {
        r["parent_document_id"]: r
        for r in pq.read_table(cache / "extraction-documents.parquet").to_pylist()
    }
    facts = []
    for fact, doc in unique_facts(
        pq.read_table(cache / "biography-facts.parquet").to_pylist(), documents
    ):
        if doc["year"] > 2026 or doc["office"] != "house":
            continue
        facts.append(
            {
                **{
                    key: fact.get(key)
                    for key in (
                        "record_id",
                        "candidate_cycle_id",
                        "candidate_record_key",
                        "parent_document_id",
                        "field",
                        "value",
                        "relationship",
                        "evidence_parent_start_char",
                        "evidence_parent_end_char",
                        "evidence_alignment_method",
                    )
                },
                "state": doc["state"],
                "party": doc["party"],
                "source_year": doc["year"],
                "first_capture_timestamp": doc["first_capture_timestamp"],
                "last_capture_timestamp": doc["last_capture_timestamp"],
                "captured_before_election": capture_before_cutoff(doc["first_capture_timestamp"]),
                "original_urls": doc["original_urls"],
                "wayback_urls": doc["wayback_urls"],
                "source_text_sha256": doc["extraction_source_text_sha256"],
                "evidence_sha256": hashlib.sha256(fact["evidence"].encode()).hexdigest(),
                "model_ready": False,
                "review_status": "machine_extracted; subject_and_field_require_review",
            }
        )
    donor_path = root / "data/raw/candidate-databases-20261113/dime-recipients.csv.gz"
    donor = []
    ids = {r["fec_id"] for r in fec} | {r["cand_id"] for r in websites}
    with gzip.open(donor_path, "rt") as stream:
        for number, row in enumerate(csv.DictReader(stream), 2):
            if row["Cand.ID"] in ids:
                donor.append({**row, "source_row": number})
    original = json.loads((root / "data/candidate-database-sources.json").read_text())
    receipt = next(r for r in original["sources"] if r["id"] == "dime-recipients")
    if fingerprint(donor_path) != {key: receipt[key] for key in ("bytes", "sha256")}:
        raise ValueError("Changed original DIME source")
    originals.append({"id": "dime-recipients", "url": DIME_URL, **fingerprint(donor_path)})
    return {
        "fec": fec,
        "websites": websites,
        "people": people,
        "members": members,
        "facts": facts,
        "donor": donor,
        "original_sources": originals,
        "website_source_receipts": receipts,
        "website_license": "CC BY 4.0; Hanno Hilbig et al.; doi:10.7910/DVN/BZ2JRS",
        **cached_historical_biographies(root),
        **acquire_background_inputs(root),
    }


def legislative_profile(candidate, identity, people, members, clerk_members=()):
    matches = [
        p
        for p in people
        if identity["fec_id"]
        and identity["fec_id"] in p["id"].get("fec", [])
        and any(t["state"] == candidate["state"] for t in p["terms"])
    ]
    status, clerk_evidence = "exact_fec_service_crosswalk", None
    if len(matches) == 1:
        person = matches[0]
    else:
        from .incumbents import clerk_person

        person, clerk_evidence = clerk_person(candidate, people, clerk_members)
        if person is None:
            return {"status": "no_unique_fec_service_crosswalk", "house_incumbent": None}
        status = "official_clerk_and_service_crosswalk"
    bioguide = person["id"]["bioguide"]
    active = [
        t for t in person["terms"] if t["type"] == "rep" and t["start"] <= "2026-11-03" < t["end"]
    ]
    birthday = person.get("bio", {}).get("birthday")
    age = None
    if birthday:
        born, election = date.fromisoformat(birthday), date(2026, 11, 3)
        age = election.year - born.year - ((election.month, election.day) < (born.month, born.day))
    votes = [r for r in members if r["bioguide_id"] == bioguide]
    voting = votes[0] if len(votes) == 1 else None
    return {
        "status": status,
        "bioguide_id": bioguide,
        "house_incumbent": bool(active),
        "age_at_election": age,
        "source_recorded_gender": person.get("bio", {}).get("gender"),
        "evidence": {
            **person["evidence"],
            **({"official_clerk": clerk_evidence} if clerk_evidence else {}),
        },
        "active_house_terms": active,
        "prior_voting_record": voting,
        "voting_measure": "118th Congress (2023-2024), Nokken-Poole first dimension",
    }


def normalize_campaignview(detail):
    return {
        "uid": detail.get("uid"),
        "FECCandID": detail.get("FECCandID", {}),
        "issues": {
            key: {
                "year": issue.get("year"),
                "header": issue.get("header"),
                "text_characters": len(issue.get("text") or ""),
                "text_sha256": hashlib.sha256((issue.get("text") or "").encode()).hexdigest(),
            }
            for key, issue in detail.get("issues", {}).items()
        },
    }


def cached_historical_biographies(root):
    path = root / "data/house-campaignview-sources.json"
    if not path.exists():
        return {}
    receipts = json.loads(path.read_text())
    cache = root / "data/raw/candidate-databases-20261113"
    index = {r["uid"]: r for r in json.loads((cache / "campaignview-candidates.json").read_text())}
    profiles = []
    for receipt in receipts["sources"]:
        source = cache / receipt["file"]
        if fingerprint(source) != {key: receipt[key] for key in ("bytes", "sha256")}:
            raise ValueError(f"Changed historical biography input: {receipt['id']}")
        if receipt["id"] == "campaignview-candidates":
            continue
        detail = normalize_campaignview(json.loads(source.read_text()))
        profiles.append({"index": index[detail["uid"]], "detail": detail, "receipt": receipt})
    return {"campaignview": profiles, "campaignview_failures": receipts["failures"]}


def acquire_historical_biographies(root):
    source = root / "results/house/source-inputs.jsonl.gz"
    inputs = read_rows(source)[0]
    candidates = read_rows(root / "results/house/candidates.jsonl.gz")
    cache = root / "data/raw/candidate-databases-20261113"
    original = json.loads((root / "data/candidate-database-sources.json").read_text())
    receipt_path = root / "data/house-campaignview-sources.json"
    receipts = (
        json.loads(receipt_path.read_text())
        if receipt_path.exists()
        else {"sources": [], "failures": []}
    )
    known = {r["id"]: r for r in [*original["sources"], *receipts["sources"]]}
    index_path = cache / "campaignview-candidates.json"
    index_receipt = known["campaignview-candidates"]
    if fingerprint(index_path) != {k: index_receipt[k] for k in ("bytes", "sha256")}:
        raise ValueError("Changed CampaignView index")
    ids = {
        r["identity"]["fec_id"]
        for r in candidates
        if r["identity"]["fec_id"] and not r["pre_election_biography_record_ids"]
    }
    index = [r for r in json.loads(index_path.read_text()) if r["FECCandID"] in ids]

    def download(record):
        uid = record["uid"]
        if not re.fullmatch(r"[a-z0-9-]+", uid):
            raise ValueError("Unsafe CampaignView UID")
        key, path = f"campaignview:{uid}", cache / f"campaignview-{uid}.json"
        url = f"https://www.campaignview.org/api/candidates/{uid}"
        if key in known:
            receipt = known[key]
            if fingerprint(path) != {k: receipt[k] for k in ("bytes", "sha256")}:
                raise ValueError(f"Changed CampaignView profile: {uid}")
        else:
            try:
                body, resolved = _fetch(url)
            except (urllib.error.URLError, TimeoutError) as error:
                return None, {"id": key, "error": str(error), "disposition": "not_bypassed"}
            path.write_bytes(body)
            receipt = {
                "id": key,
                "file": path.name,
                "origin_url": url,
                "resolved_url": resolved,
                **fingerprint(path),
                "acquired_at": datetime.now(timezone.utc).isoformat(),
            }
        detail = json.loads(path.read_text())
        normalized = normalize_campaignview(detail)
        return {"index": record, "detail": normalized, "receipt": receipt}, None

    with ThreadPoolExecutor(max_workers=4) as executor:
        outcomes = list(executor.map(download, index))
    inputs["campaignview"] = [value for value, error in outcomes if value]
    inputs["campaignview_failures"] = [error for value, error in outcomes if error]
    write_json(
        receipt_path,
        {
            "scope": "Historical biography leads for House candidates lacking current captures",
            "sources": [index_receipt, *[r["receipt"] for r in inputs["campaignview"]]],
            "failures": inputs["campaignview_failures"],
        },
    )
    return build(root, inputs=inputs)


def inventory(panel, inputs):
    candidates, choices, facts = [], [], []
    grouped, donors = defaultdict(list), defaultdict(list)
    for fact in inputs["facts"]:
        grouped[fact["candidate_cycle_id"]].append(fact)
    for donor in inputs["donor"]:
        donors[donor["Cand.ID"]].append(donor)
    for race in panel:
        for native in race["native_evidence"]["native"]["candidates"]:
            row = {
                "candidate_id": str(native["candidate_id"]),
                "contest_id": race["contest_id"],
                "state": race["state"],
                "district": race["district"],
                "chamber": "house",
                "year": 2026,
                "name": native["name"],
                "party": native["party"],
                "votes": native["votes"],
                "source_reported_percent": native["percent"],
                "native_flags_unverified": {
                    k: native.get(k) for k in ("incumbent", "winner", "advanced")
                },
                "counting_round": race["counting_round"],
                "source_updated_at_values": race["source_updated_at_values"],
                "source": race["native_evidence"]["source"],
                "disposition": "named_candidate"
                if is_person(native["name"])
                else "aggregate_choice",
            }
            choices.append(dict(row))
            if row["disposition"] != "named_candidate":
                continue
            identity = resolve_identity(row, inputs["fec"], inputs["websites"], inputs["people"])
            website = identity.pop("website")
            row["identity"] = identity
            row["website"] = website
            row["legislative"] = legislative_profile(
                row, identity, inputs["people"], inputs["members"], inputs.get("clerk_members", ())
            )
            party = {"Democratic": "democrat", "Republican": "republican"}.get(row["party"])
            if row["party"] == "Write-In" and identity["fec_id"]:
                registered = {r["party"] for r in identity["official_alternatives"]}
                if len(registered) == 1:
                    party = {"DEM": "democrat", "REP": "republican"}.get(next(iter(registered)))
            matched_facts = []
            if website:
                for fact in grouped[website["candidate_cycle_id"]]:
                    if fact["state"] != row["state"] or fact["party"] != party:
                        raise ValueError("Conflicting House biography context")
                    matched_facts.append({**fact, "candidate_id": row["candidate_id"]})
            facts.extend(matched_facts)
            row["pre_election_biography_fields"] = sorted(
                {f["field"] for f in matched_facts if f["captured_before_election"]}
            )
            row["biography_record_ids"] = [f["record_id"] for f in matched_facts]
            row["pre_election_biography_record_ids"] = [
                f["record_id"] for f in matched_facts if f["captured_before_election"]
            ]
            historical = []
            if identity["fec_id"]:
                for source in inputs["websites"]:
                    if (
                        source["year"] >= "2026"
                        or source["office"] != "house"
                        or source["cand_id"] != identity["fec_id"]
                        or source["state"] != row["state"]
                    ):
                        continue
                    if not (
                        same_name(row["name"], source["candidate"])
                        or any(
                            matches_name(source["candidate"], official)
                            for official in identity["official_alternatives"]
                        )
                    ):
                        continue
                    for fact in grouped[source["candidate_cycle_id"]]:
                        if fact["captured_before_election"]:
                            historical.append(
                                {**fact, "candidate_id": row["candidate_id"], "historical": True}
                            )
            facts.extend(historical)
            row["historical_campaign_record_ids"] = [f["record_id"] for f in historical]
            row["historical_campaign_fields"] = sorted({f["field"] for f in historical})
            row["donor"] = (
                select_dime(
                    {"D_name": row["name"], "D_fec_id": identity["fec_id"], "state": row["state"]},
                    donors[identity["fec_id"]],
                    party_code="100" if party == "democrat" else "200",
                )
                if party
                else {"status": "party_not_supported", "score": None}
            )
            cv = [
                r
                for r in inputs.get("campaignview", [])
                if identity["fec_id"] and r["index"]["FECCandID"] == identity["fec_id"]
            ]
            row["historical_biography"] = (
                select_campaignview(
                    {"D_fec_id": identity["fec_id"], "state": row["state"]},
                    [r["index"] for r in cv],
                    {r["detail"]["uid"]: r["detail"] for r in cv},
                    party_label="Democrat" if party == "democrat" else "Republican",
                )
                if party
                else {"historical_biography_available": False}
            )
            row["selected_democratic_analysis_candidate"] = (
                row["party"] == "Democratic" and row["name"] == race["D_name"]
            )
            row["verified_religion"] = None
            row["verified_race_ethnicity"] = None
            row["identity_trait_status"] = "not_coded_in_this_all_candidate_inventory"
            row["background"] = background_profile(row, inputs)
            row["campaign_websites"] = sorted(
                {
                    *([website["website_url"]] if website and website["website_url"] else []),
                    *[
                        profile["fields"]["campaign_website"]
                        for profile in row["background"]["official_candidate_profiles"]
                        if profile["fields"].get("campaign_website")
                    ],
                }
            )
            row["religion_evidence_status"] = (
                "dated_office_observations; current_affiliation_unverified"
                if row["background"]["dated_religion_observations"]
                else "no_qualified_office_observation"
            )
            row["race_ethnicity_evidence_status"] = (
                "dated_official_observations; current_self_identification_unverified"
                if row["background"]["official_historian_observations"]
                else "no_qualified_historian_observation"
            )
            row["missing_information"] = [
                key
                for key, present in (
                    ("fec_id", identity["fec_id"]),
                    ("campaign_website", row["campaign_websites"]),
                    ("pre_election_biography", row["pre_election_biography_record_ids"]),
                    ("verified_religion", False),
                    ("verified_race_ethnicity", False),
                )
                if not present
            ]
            candidates.append(row)
    keys = [(r["contest_id"], r["candidate_id"]) for r in choices]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate native House candidate/choice key")
    return candidates, choices, facts


def coverage(candidates):
    result = []
    groups = {
        "all_named": candidates,
        "democrats": [r for r in candidates if r["party"] == "Democratic"],
        "republicans": [r for r in candidates if r["party"] == "Republican"],
        "other_parties": [r for r in candidates if r["party"] not in ("Democratic", "Republican")],
    }
    for group, rows in groups.items():
        result.append(
            {
                "cohort": group,
                "candidates": len(rows),
                "fec_id": sum(bool(r["identity"]["fec_id"]) for r in rows),
                "campaign_website": sum(bool(r["campaign_websites"]) for r in rows),
                "pre_election_biography": sum(
                    bool(r["pre_election_biography_record_ids"]) for r in rows
                ),
                "donor_score": sum(
                    r["donor"].get("score") is not None
                    and r["donor"].get("name_screen") == "consistent"
                    for r in rows
                ),
                "prior_federal_voting_score": sum(
                    bool(r["legislative"].get("prior_voting_record"))
                    and r["legislative"]["prior_voting_record"].get("nokken_poole_dim1") is not None
                    for r in rows
                ),
                "historical_biography": sum(
                    r["historical_biography"]["historical_biography_available"] for r in rows
                ),
                "historical_campaign_facts": sum(
                    bool(r["historical_campaign_record_ids"]) for r in rows
                ),
                "official_candidate_profile": sum(
                    bool(r["background"]["official_candidate_profiles"]) for r in rows
                ),
                "reviewed_candidate_profile": sum(
                    bool(r["background"].get("reviewed_candidate_profiles")) for r in rows
                ),
                "dated_religion_observations": sum(
                    bool(r["background"]["dated_religion_observations"]) for r in rows
                ),
                "member_authorized_background": sum(
                    bool(
                        r["background"]["member_authorized_biographies"]
                        or r["background"].get("official_member_profiles")
                    )
                    for r in rows
                ),
                "official_historian_identification": sum(
                    bool(r["background"]["official_historian_observations"]) for r in rows
                ),
                "any_background_evidence": sum(
                    bool(
                        r["biography_record_ids"]
                        or r["historical_biography"]["historical_biography_available"]
                        or r["historical_campaign_record_ids"]
                        or r["background"]["official_candidate_profiles"]
                        or r["background"]["member_authorized_biographies"]
                        or r["background"].get("official_member_profiles")
                        or r["background"].get("reviewed_candidate_profiles")
                        or r["background"].get("reviewed_characteristic_observations")
                        or r["background"]["dated_religion_observations"]
                        or r["background"]["official_historian_observations"]
                    )
                    for r in rows
                ),
                "factual_background": sum(
                    bool(
                        r["biography_record_ids"]
                        or r["historical_campaign_record_ids"]
                        or r["background"]["official_candidate_profiles"]
                        or r["background"]["member_authorized_biographies"]
                        or r["background"].get("official_member_profiles")
                        or r["background"].get("reviewed_candidate_profiles")
                        or r["background"].get("reviewed_characteristic_observations")
                        or r["background"]["dated_religion_observations"]
                        or r["background"]["official_historian_observations"]
                    )
                    for r in rows
                ),
            }
        )
    return result


def build(root=ROOT, output=None, from_cache=False, inputs=None):
    root = Path(root)
    output = Path(output) if output else root / "results/house"
    panel_path = root / "results/2026-v4/candidate-queries.jsonl.gz"
    expected_panel = json.loads((root / "results/2026-v4/manifest.json").read_text())["files"][
        "candidate-queries.jsonl.gz"
    ]
    if fingerprint(panel_path) != expected_panel:
        raise ValueError("Changed pinned House election panel")
    if inputs is None:
        if from_cache:
            inputs = acquire_inputs(root)
        else:
            source = root / "results/house/source-inputs.jsonl.gz"
            expected = json.loads((root / "results/house/manifest.json").read_text())["files"][
                source.name
            ]
            if fingerprint(source) != expected:
                raise ValueError("Changed normalized House inputs")
            inputs = read_rows(source)[0]
    panel = [r for r in read_rows(panel_path) if r["chamber"] == "house"]
    if len(panel) != 435 or len({r["contest_id"] for r in panel}) != 435:
        raise ValueError("House inventory requires all 435 unique contests")
    candidates, choices, facts = inventory(panel, inputs)
    if inputs.get("reviewed_characteristic_observations"):
        from .house_backgrounds import validate_characteristics

        validate_characteristics(inputs["reviewed_characteristic_observations"], candidates)
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".house-candidates-", dir=output.parent) as directory:
        staged = Path(directory)
        write_rows(staged / "source-inputs.jsonl.gz", [inputs])
        write_rows(staged / "candidates.jsonl.gz", candidates)
        write_rows(staged / "all-choices.jsonl.gz", choices)
        write_rows(staged / "biography-facts.jsonl.gz", facts)
        (staged / "background-observations.csv").write_bytes(
            csv_bytes(background_observations(candidates, facts))
        )
        from .incumbents import write_tables

        write_tables(staged, candidates, inputs)
        write_json(staged / "coverage.json", coverage(candidates))
        flat = [
            {
                **{
                    k: r[k]
                    for k in (
                        "candidate_id",
                        "contest_id",
                        "state",
                        "district",
                        "name",
                        "party",
                        "votes",
                    )
                },
                "fec_id": r["identity"]["fec_id"],
                "identity_match": r["identity"]["status"],
                "website_url": ";".join(r["campaign_websites"]),
                "bioguide_id": r["legislative"].get("bioguide_id"),
                "house_incumbent": r["legislative"]["house_incumbent"],
                "age_at_election": r["legislative"].get("age_at_election"),
                "pre_election_biography_records": len(r["pre_election_biography_record_ids"]),
                "biography_fields": ";".join(r["pre_election_biography_fields"]),
                "historical_campaign_fields": ";".join(r["historical_campaign_fields"]),
                "official_profile_records": len(r["background"]["official_candidate_profiles"]),
                "reviewed_candidate_profile_records": len(
                    r["background"].get("reviewed_candidate_profiles", [])
                ),
                "dated_religion_observations": len(r["background"]["dated_religion_observations"]),
                "member_authorized_biography_records": len(
                    r["background"]["member_authorized_biographies"]
                ),
                "additional_member_background_records": len(
                    r["background"].get("official_member_profiles", [])
                ),
                "historical_donor_score": r["donor"].get("score"),
                "donor_name_screen": r["donor"].get("name_screen"),
                "historical_biography_available": r["historical_biography"][
                    "historical_biography_available"
                ],
                "religion_status": r["religion_evidence_status"],
                "race_ethnicity_status": r["race_ethnicity_evidence_status"],
                "missing_information": ";".join(r["missing_information"]),
            }
            for r in candidates
        ]
        (staged / "candidates.csv").write_bytes(csv_bytes(flat))
        (staged / "missing-information.csv").write_bytes(
            csv_bytes([r for r in flat if r["missing_information"]])
        )
        manifest = {
            "schema": "which_candidate.house_candidates.v2",
            "scope": "2026 House only; all named candidates in the pinned provider returns",
            "count_status": "November 12-13 provider snapshot; provisional, not certified",
            "contests": len(panel),
            "named_candidates": len(candidates),
            "aggregate_choices": len(choices) - len(candidates),
            "native_choice_rows": len(choices),
            "panel_input": fingerprint(panel_path),
            "biography_labels_model_ready": False,
            "interpretation": "Complete roster, not complete traits; unmatched and unknown are explicit",
            "files": {p.name: fingerprint(p) for p in sorted(staged.iterdir())},
        }
        write_json(staged / "manifest.json", manifest)
        output.mkdir(parents=True, exist_ok=True)
        for path in sorted(staged.iterdir(), key=lambda p: p.name == "manifest.json"):
            target = output / path.name
            if not target.exists() or fingerprint(path) != fingerprint(target):
                path.replace(target)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--from-cache", action="store_true")
    parser.add_argument("--acquire-historical-biographies", action="store_true")
    args = parser.parse_args()
    result = (
        acquire_historical_biographies(args.root)
        if args.acquire_historical_biographies
        else build(args.root, args.output, args.from_cache)
    )
    print(json.dumps(result, indent=2))
