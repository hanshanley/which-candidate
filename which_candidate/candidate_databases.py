"""Pinned, offline-replayable 2026 candidate database coverage, not new model fits."""

import argparse
import csv
import gzip
import hashlib
import html
import json
import math
import re
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from .demographics import read_pew
from .features import FeatureSources, name_matches
from .storage import confined, fingerprint, write_json

DIME_URL = (
    "https://www.dropbox.com/scl/fi/bcpmxvxwc7iwmqvchm2sp/"
    "dime_recipients_1979_2024.csv.gz?rlkey=4ii8765xw8y2svlzcbxzfvnbh&dl=1"
)
ROOT_SOURCES = (
    ("dime-recipients", DIME_URL, "dime-recipients.csv.gz"),
    ("dime-codebook", "https://bit.ly/dimeV4codebook", "dime-codebook.pdf"),
    (
        "campaignview-candidates",
        "https://www.campaignview.org/api/candidates",
        "campaignview-candidates.json",
    ),
    (
        "hilbig-roster",
        "https://www.hannohilbig.com/candidatewebsites/release_roster.csv",
        "hilbig-release-roster.csv",
    ),
    (
        "talarico-biography",
        "https://jamestalarico.com/meet-james-talarico/",
        "talarico-biography.html",
    ),
    ("hamilton-biography", "https://adamhamilton.com/about/", "hamilton-biography.html"),
    (
        "cawp-2026-candidates",
        "https://cawp.rutgers.edu/sites/default/files/data/2026%20Candidate%20List.csv",
        "cawp-candidates-2026.csv",
    ),
    (
        "cawp-2026-page",
        "https://cawp.rutgers.edu/data/candidates-women-candidates-2026",
        "cawp-women-candidates-2026.html",
    ),
    (
        "cawp-house-nonincumbent-winners",
        "https://e.infogram.com/7bfa64b9-59cb-4a13-953d-834d7274b2f4"
        "?embed_type=responsive_iframe&src=embed",
        "cawp-house-nonincumbent-winners.html",
    ),
    (
        "cawp-senate-nonincumbent-winners",
        "https://e.infogram.com/4c01f2e0-05ff-4321-956e-606c6b3331dc"
        "?embed_type=responsive_iframe&src=embed",
        "cawp-senate-nonincumbent-winners.html",
    ),
)


def load_queries(path):
    with gzip.open(path, "rt") as handle:
        rows = [json.loads(line) for line in handle]
    return [row for row in rows if row["year"] == 2026]


def _read_receipts(manifest, cache):
    receipts = json.loads(manifest.read_text())
    for source in receipts["sources"]:
        path = confined(cache, source["file"])
        if fingerprint(path) != {"sha256": source["sha256"], "bytes": source["bytes"]}:
            raise ValueError(f"Cached source changed: {source['id']}")
    return receipts


def _fetch(url):
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=90) as response:
                return response.read(), response.url
        except urllib.error.HTTPError as error:
            if error.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
        except (TimeoutError, urllib.error.URLError):
            if attempt == 2:
                raise
        time.sleep(2 * (attempt + 1))


def snapshot(cache, manifest, queries):
    """Keep acquisitions out of the replay and preserve per-endpoint failures."""
    cache.mkdir(parents=True, exist_ok=True)
    if manifest.exists():
        receipts = _read_receipts(manifest, cache)
    else:
        receipts = {"schema": 1, "sources": [], "failures": []}
    sources = {row["id"]: row for row in receipts["sources"]}

    def acquire(key, url, filename):
        if key in sources:
            return (
                json.loads(confined(cache, filename).read_text())
                if filename.endswith(".json")
                else None
            )
        path = confined(cache, filename)
        if path.exists():
            payload = path.read_bytes()
            acquired = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
            clock_basis = "existing_download_file_mtime"
            resolved = None
        else:
            payload, resolved = _fetch(url)
            path.write_bytes(payload)
            acquired = datetime.now(timezone.utc).isoformat()
            clock_basis = "completed_download_utc"
        row = {
            "id": key,
            "origin_url": url,
            "resolved_url": resolved,
            "file": filename,
            "acquired_at": acquired,
            "acquisition_clock_basis": clock_basis,
            **fingerprint(path),
        }
        sources[key] = row
        receipts["sources"] = sorted(sources.values(), key=lambda row: row["id"])
        receipts["failures"] = [failure for failure in receipts["failures"] if failure["id"] != key]
        write_json(manifest, receipts)
        return json.loads(payload) if filename.endswith(".json") else None

    index = None
    for key, url, filename in ROOT_SOURCES:
        try:
            value = acquire(key, url, filename)
        except urllib.error.HTTPError as error:
            receipts["failures"] = [row for row in receipts["failures"] if row["id"] != key] + [
                {"id": key, "http_status": error.code, "disposition": "not_bypassed"}
            ]
            write_json(manifest, receipts)
            continue
        if key == "campaignview-candidates":
            index = value
    ids = {row.get("D_fec_id") for row in queries if row.get("D_fec_id")}
    wanted = sorted(
        {
            row["uid"]
            for row in index or []
            if row["FECCandID"] in ids and row["cand_party"] == "Democrat"
        }
    )
    for number, uid in enumerate(wanted, 1):
        if not re.fullmatch(r"[a-z0-9-]+", uid):
            raise ValueError(f"Unsafe CampaignView UID: {uid}")
        key = f"campaignview:{uid}"
        try:
            acquire(
                key,
                f"https://www.campaignview.org/api/candidates/{uid}",
                f"campaignview-{uid}.json",
            )
        except urllib.error.HTTPError as error:
            receipts["failures"] = [row for row in receipts["failures"] if row["id"] != key] + [
                {"id": key, "http_status": error.code, "disposition": "not_bypassed"}
            ]
            write_json(manifest, receipts)
        if number % 20 == 0:
            print(f"CampaignView records: {number}/{len(wanted)}", flush=True)
        time.sleep(0.1)
    return receipts


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def select_dime(query, matches):
    if not query.get("D_name"):
        return {"status": "no_named_nominee", "score": None}
    if not query.get("D_fec_id"):
        return {"status": "missing_target_fec_id", "score": None}
    if not matches:
        return {"status": "no_exact_fec_match", "score": None}
    candidates = [
        row
        for row in matches
        if row["Cand.ID"] == query["D_fec_id"]
        and row["state"] == query["state"]
        and row["party"] == "100"
        and row["recipient.type"] == "cand"
        and _number(row["cycle"]) is not None
        and _number(row["cycle"]).is_integer()
        and _number(row["cycle"]) <= 2024
    ]
    if not candidates:
        return {"status": "state_party_type_or_vintage_conflict", "score": None}
    identities = {row["bonica.rid"] for row in candidates}
    if len(identities) != 1 or "" in identities:
        return {"status": "conflicting_source_person_ids", "score": None}
    latest = max(int(float(row["cycle"])) for row in candidates)
    latest_rows = [row for row in candidates if int(float(row["cycle"])) == latest]
    scores = {_number(row["recipient.cfscore.dyn"]) for row in latest_rows}
    if len(scores) != 1:
        return {"status": "conflicting_latest_cycle_scores", "score": None}
    score = scores.pop()
    if score is None:
        return {"status": "latest_cycle_score_missing", "score": None, "cycle": latest}
    return {
        "status": "exact_fec_state_party_unique_person",
        "score": score,
        "cycle": latest,
        "bonica_rid": next(iter(identities)),
        "source_rows": [row["source_row"] for row in latest_rows],
        "giver_counts": sorted({row["num.givers"] for row in latest_rows}),
        "measure": "recipient.cfscore.dyn",
        "vintage": "through_2024_activity; retrospectively_acquired_v4; not_2026_donations",
        "source_seats": sorted({row["seat"] for row in latest_rows}),
        "name_screen": (
            "consistent"
            if all(
                name_matches(query["D_name"], row["ffname"], row["lname"]) for row in latest_rows
            )
            else "manual_alias_review_required; exact_FEC_match_not_discarded"
        ),
        "model_ready": False,
    }


def select_campaignview(query, matches, details):
    accepted, held = [], []
    for record in matches:
        uid = record["uid"]
        detail = details.get(uid)
        if (
            record["FECCandID"] != query.get("D_fec_id")
            or record["state_postal"] != query["state"]
            or record["cand_party"] != "Democrat"
        ):
            held.append({"uid": uid, "reason": "state_or_party_conflict"})
        elif detail is None:
            held.append({"uid": uid, "reason": "detail_not_acquired"})
        elif (
            detail.get("uid") != uid
            or query["D_fec_id"] not in detail.get("FECCandID", {}).values()
        ):
            held.append({"uid": uid, "reason": "detail_identity_conflict"})
        else:
            issues = []
            for key, issue in sorted(detail["issues"].items()):
                if (
                    not isinstance(issue.get("year"), int)
                    or issue["year"] not in record["years"]
                    or issue["year"] > 2024
                ):
                    held.append({"uid": uid, "key": key, "reason": "unqualified_issue_year"})
                    continue
                text = issue.get("text") or ""
                issues.append(
                    {
                        "key": key,
                        "year": issue["year"],
                        "header": issue["header"],
                        "text_characters": len(text),
                        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                        "biography": issue["header"] == "Candidate Biography",
                    }
                )
            accepted.append({"uid": uid, "years": record["years"], "issues": issues})
    return {
        "status": "exact_fec_state_party_detail_verified" if accepted else "no_qualified_record",
        "records": accepted,
        "held": held,
        "historical_biography_available": any(
            issue["biography"] and issue["text_characters"] > 0
            for record in accepted
            for issue in record["issues"]
        ),
        "current_2026_biography": False,
        "identity_labels_extracted": False,
    }


def _write_rows(path, rows):
    payload = "".join(json.dumps(row, sort_keys=True, allow_nan=False) + "\n" for row in rows)
    path.write_bytes(gzip.compress(payload.encode(), mtime=0))


def cross_office_leads(path, queries):
    """Name-screened research leads, never accepted identities or model inputs."""
    by_state, leads = defaultdict(list), defaultdict(list)
    for query in queries:
        if query.get("D_name"):
            by_state[query["state"]].append(query)
    with gzip.open(path, "rt") as handle:
        for number, row in enumerate(csv.DictReader(handle), 1):
            cycle = _number(row["cycle"])
            if (
                row["party"] != "100"
                or row["recipient.type"] != "cand"
                or cycle is None
                or not cycle.is_integer()
                or cycle > 2024
            ):
                continue
            for query in by_state.get(row["state"], []):
                if row["Cand.ID"] != query.get("D_fec_id") and name_matches(
                    query["D_name"], row["ffname"], row["lname"]
                ):
                    leads[query["contest_id"]].append(
                        {
                            "contest_id": query["contest_id"],
                            "target_name": query["D_name"],
                            "target_fec_id": query.get("D_fec_id"),
                            "source_row": number,
                            "source_id": "dime-recipients",
                            "source_name": row.get("name"),
                            "source_candidate_id": row["Cand.ID"],
                            "source_person_id": row["bonica.rid"],
                            "state": row["state"],
                            "source_seat": row["seat"],
                            "cycle": int(cycle),
                            "donation_score": _number(row["recipient.cfscore.dyn"]),
                            "status": "manual_cross_office_identity_review_required",
                            "model_ready": False,
                        }
                    )
    return leads


def select_cawp(query, records, population="women_candidates; includes_primary_losers"):
    matched = []
    for row in records:
        if (
            row["State"] != query["state"]
            or row["Party"] != "D"
            or row["Office"] != ("U.S. Rep." if query["chamber"] == "house" else "U.S. Sen.")
            or not query.get("D_name")
            or not name_matches(query["D_name"], row["First Name"], row["Last Name"])
        ):
            continue
        if query["chamber"] == "house":
            district = 0 if row["Dist."] == "AL" else _number(row["Dist."])
            target_district = 0 if query.get("district") == "AL" else _number(query.get("district"))
            if district is None or target_district is None or district != target_district:
                continue
        matched.append(row)
    return {
        "status": (
            "unique_name_state_office_district_review_required"
            if len(matched) == 1
            else "ambiguous_contextual_matches"
            if matched
            else "no_contextual_match"
        ),
        "records": matched,
        "source_population": population,
        "absence_is_not_male": True,
        "race_field_available": any(row.get("Racial Identification") for row in matched),
        "identity_label_promoted": False,
    }


def cawp_winner_classifications(path, source_id, chamber):
    text = path.read_text()
    marker = re.search(r"window\.infographicData\s*=\s*", text)
    if marker is None:
        raise ValueError("CAWP public embedded data not found")
    data, _ = json.JSONDecoder().raw_decode(text[marker.end() :])
    entities = data["elements"]["content"]["content"]["entities"]
    records = []
    for entity_id, entity in entities.items():
        sheets = entity.get("props", {}).get("chartData", {}).get("data", [])
        for sheet_number, sheet in enumerate(sheets, 1):
            rows = [
                [cell.get("value", "") if isinstance(cell, dict) else cell for cell in row]
                for row in sheet
            ]
            if not rows or "Racial Identification" not in rows[0]:
                continue
            header = rows[0]
            for number, values in enumerate(rows[1:], 2):
                if len(values) != len(header):
                    raise ValueError("CAWP individual classification row width changed")
                row = dict(zip(header, values, strict=True))
                if not row.get("Last Name") or not row.get("Racial Identification"):
                    continue
                records.append(
                    {
                        **row,
                        "Office": "U.S. Rep." if chamber == "house" else "U.S. Sen.",
                        "Dist.": row.get("District", ""),
                        "source_id": source_id,
                        "source_entity": entity_id,
                        "source_sheet": sheet_number,
                        "source_row": number,
                        "evidence_type": "CAWP_reported_racial_identification",
                        "source_scope": "women_nonincumbent_winners_only",
                        "eligible_pre_election_predictor": False,
                        "identity_label_promoted": False,
                    }
                )
    return records


def religion_observations(queries, manifest):
    """Keep dated person-level evidence distinct from a current affiliation."""
    root = manifest.parent
    specs = json.loads(manifest.read_text())["sources"]
    selected = [spec for spec in specs if spec["kind"] in {"legislators", "pew_member_religion"}]
    for spec in selected:
        if fingerprint(confined(root, spec["path"])) != {
            "sha256": spec["sha256"],
            "bytes": spec["bytes"],
        }:
            raise ValueError(f"Existing research source changed: {spec['id']}")
    identities = FeatureSources(
        {"sources": [spec for spec in selected if spec["kind"] == "legislators"]}, root
    )
    observations = []
    for spec in selected:
        if spec["kind"] == "pew_member_religion":
            observations.extend(read_pew(confined(root, spec["path"]), spec))
    result = {}
    for query in queries:
        person = identities.people.get(query.get("bioguide_id"))
        matched = []
        if person and identities.matches_person(
            {"name": query["D_name"], "state": query["state"]}, person
        ):
            for record in observations:
                if (
                    record["state"] == query["state"]
                    and record["publication_date"] < (query.get("election_date") or "2026-11-03")
                    and identities.matches_person(
                        {"name": record["name"], "state": record["state"]}, person
                    )
                ):
                    matched.append({**record, "bioguide_id": query["bioguide_id"]})
        result[query["contest_id"]] = sorted(
            matched, key=lambda record: (record["publication_date"], record["source_id"])
        )
    return result, selected


def reviewed_descriptions(queries, annotations, receipts, cache):
    sources = {row["id"]: row for row in receipts["sources"]}
    results = []
    for observation in json.loads(annotations.read_text())["observations"]:
        observation = {
            **observation,
            "status": "unmatched_subject_identity",
            "eligible_pre_election_predictor": False,
            "qualification": "reviewed_self_description_only; v3_labels_not_overwritten",
        }
        targets = [
            row
            for row in queries
            if (
                row.get("D_fec_id"),
                row.get("D_name"),
                row["state"],
                row["chamber"],
            )
            == (
                observation["fec_id"],
                observation["name"],
                observation["state"],
                observation["chamber"],
            )
        ]
        if targets:
            source = sources.get(observation["source_id"])
            if source is None:
                observation["status"] = "source_not_acquired"
            else:
                raw = confined(cache, source["file"]).read_text()
                if "campaignview_issue_key" in observation:
                    detail = json.loads(raw)
                    if observation["fec_id"] not in detail["FECCandID"].values():
                        raise ValueError("Reviewed biography FEC identity changed")
                    issue = detail["issues"][observation["campaignview_issue_key"]]
                    if issue["header"] != "Candidate Biography":
                        raise ValueError("Reviewed source is not a biography")
                    if issue["year"] != observation["source_year_label"]:
                        raise ValueError("Reviewed biography year changed")
                    raw = issue["text"]
                text = " ".join(html.unescape(re.sub(r"<[^>]*>", " ", raw)).split())
                if observation["quote"] not in text:
                    raise ValueError("Reviewed self-description not found in pinned source")
                observation.update(
                    status="verified_subject_and_pinned_self_description",
                    contest_ids=[row["contest_id"] for row in targets],
                    source_sha256=source["sha256"],
                    acquired_at=source.get("acquired_at"),
                )
        results.append(observation)
    return results


def build(
    cache, manifest, queries, output, research_manifest=None, queries_archive=None, annotations=None
):
    if any(query["year"] != 2026 for query in queries):
        raise ValueError("Source expansion is restricted to the 2026 universe")
    if len({query["contest_id"] for query in queries}) != len(queries):
        raise ValueError("Duplicate input contest identity")
    receipts = _read_receipts(manifest, cache)
    receipt_by_id = {row["id"]: row for row in receipts["sources"]}
    source_by_file = {row["file"]: row for row in receipts["sources"]}
    for key, filename in (
        ("dime-recipients", "dime-recipients.csv.gz"),
        ("campaignview-candidates", "campaignview-candidates.json"),
        ("hilbig-roster", "hilbig-release-roster.csv"),
    ):
        if receipt_by_id.get(key, {}).get("file") != filename:
            raise ValueError(f"Missing required source pin: {key}")
    required_ids = {row.get("D_fec_id") for row in queries if row.get("D_fec_id")}
    religions, reused_sources = (
        religion_observations(queries, research_manifest) if research_manifest else ({}, [])
    )
    reviewed = reviewed_descriptions(queries, annotations, receipts, cache) if annotations else []
    dime = defaultdict(list)
    source_rows, source_count = [], 0
    chamber_conflicts = 0
    with gzip.open(cache / "dime-recipients.csv.gz", "rt") as handle:
        for number, row in enumerate(csv.DictReader(handle), 1):
            source_count += 1
            if row["Cand.ID"] in required_ids:
                row = {**row, "source_row": number, "source_id": "dime-recipients"}
                source_rows.append(row)
                dime[row["Cand.ID"]].append(row)
            if (
                re.fullmatch(r"[HS]\d[A-Z]{2}\d{5}", row["Cand.ID"])
                and row["seat"] in {"federal:house", "federal:senate"}
                and row["Cand.ID"][0] != ("H" if row["seat"] == "federal:house" else "S")
            ):
                chamber_conflicts += 1
    index = json.loads((cache / "campaignview-candidates.json").read_text())
    cv, cv_rows, details = defaultdict(list), [], {}
    for number, row in enumerate(index, 1):
        if row["FECCandID"] in required_ids:
            cv_rows.append({**row, "source_row": number})
            cv[row["FECCandID"]].append(row)
            filename = f"campaignview-{row['uid']}.json"
            if filename in source_by_file:
                details[row["uid"]] = json.loads(confined(cache, filename).read_text())
    website_rows, websites = [], defaultdict(list)
    with (cache / "hilbig-release-roster.csv").open(newline="") as handle:
        for number, record in enumerate(csv.DictReader(handle), 1):
            if record["cand_id"] in required_ids:
                record = {**record, "source_row": number, "source_id": "hilbig-roster"}
                website_rows.append(record)
                websites[record["cand_id"]].append(record)
    cawp_records = []
    if "cawp-candidates-2026.csv" in source_by_file:
        with (cache / "cawp-candidates-2026.csv").open(encoding="cp1252", newline="") as handle:
            cawp_records = [
                {**row, "source_row": number, "source_id": "cawp-2026-candidates"}
                for number, row in enumerate(csv.DictReader(handle), 1)
            ]
    cawp_race_records = []
    for chamber in ("house", "senate"):
        source_id = f"cawp-{chamber}-nonincumbent-winners"
        if source_id in receipt_by_id:
            cawp_race_records.extend(
                cawp_winner_classifications(
                    confined(cache, receipt_by_id[source_id]["file"]), source_id, chamber
                )
            )
    leads = cross_office_leads(
        cache / "dime-recipients.csv.gz",
        [
            query
            for query in queries
            if select_dime(query, dime.get(query.get("D_fec_id"), []))["score"] is None
        ],
    )
    result, groups = [], defaultdict(Counter)
    for query in queries:
        fec = query.get("D_fec_id")
        d = select_dime(query, dime.get(fec, []))
        c = select_campaignview(query, cv.get(fec, []), details)
        row = {
            "contest_id": query["contest_id"],
            "candidate_election_id": query.get("D_candidate_election_id"),
            "name": query.get("D_name"),
            "fec_id": fec,
            "state": query["state"],
            "chamber": query["chamber"],
            "eligible_v3": query["eligible"],
            "federal_incumbent": query.get("D_incumbent"),
            "won_two_party_comparison": query.get("won_two_party_comparison"),
            "prior_vote_ideology_available": query.get("nokken_poole_dim1") is not None,
            "v3_religion": query.get("religion_category", "unknown"),
            "v3_race": query.get("race_category", "unknown"),
            "dime": d,
            "dime_cross_office_leads": leads.get(query["contest_id"], []),
            "campaignview": c,
            "cawp": select_cawp(query, cawp_records),
            "cawp_reported_race": select_cawp(
                query, cawp_race_records, population="women_nonincumbent_winners_only"
            ),
            "historical_website_attempts": websites.get(fec, []),
            "dated_religion_observations": religions.get(query["contest_id"], []),
            "religion_evidence_policy": "dated_observations_only; v3_labels_not_overwritten",
            "reviewed_self_descriptions": [
                observation
                for observation in reviewed
                if query["contest_id"] in observation.get("contest_ids", [])
            ],
            "identity_inference": "none; DIME automated_gender_not_used_as_identity_feature",
        }
        result.append(row)
        cohort = (
            "incumbent"
            if row["federal_incumbent"] is True
            else "nonincumbent"
            if row["federal_incumbent"] is False
            else "incumbency_unknown"
        )
        outcome = (
            "won_two_party"
            if row["won_two_party_comparison"] is True and row["name"]
            else "lost_two_party"
            if row["won_two_party_comparison"] is False and row["name"]
            else "outcome_unavailable"
        )
        keys = ["all", row["chamber"], cohort, outcome, f"{row['chamber']}:{cohort}"]
        if row["name"]:
            keys.append("named_nominees")
        if row["eligible_v3"]:
            keys += ["eligible", f"{row['chamber']}:eligible"]
        for key in keys:
            groups[key]["contests"] += 1
            groups[key]["named_D_candidates"] += bool(row["name"])
            groups[key]["v3_eligible"] += row["eligible_v3"]
            groups[key]["prior_vote_ideology"] += row["prior_vote_ideology_available"]
            groups[key]["dime_score"] += d["score"] is not None
            groups[key]["dime_cross_office_lead"] += bool(row["dime_cross_office_leads"])
            groups[key]["dime_name_alias_review"] += (
                d["score"] is not None and d["name_screen"] != "consistent"
            )
            groups[key]["dime_without_prior_vote_score"] += (
                d["score"] is not None and not row["prior_vote_ideology_available"]
            )
            groups[key]["historical_campaign_bio"] += c["historical_biography_available"]
            groups[key]["cawp_contextual_match"] += (
                row["cawp"]["status"] == "unique_name_state_office_district_review_required"
            )
            groups[key]["cawp_reported_race_match"] += (
                row["cawp_reported_race"]["status"]
                == "unique_name_state_office_district_review_required"
            )
            groups[key]["historical_website_capture"] += any(
                record["captured"] == "True"
                and record["state"] == row["state"]
                and record["party"] == "D"
                for record in row["historical_website_attempts"]
            )
            has_dated_religion = any(
                observation["religion_category"] != "unknown"
                for observation in row["dated_religion_observations"]
            )
            groups[key]["dated_religion_evidence"] += has_dated_religion
            groups[key]["dated_religion_with_v3_unknown"] += has_dated_religion and row[
                "v3_religion"
            ] in (None, "unknown")
            groups[key]["reviewed_religion_self_description"] += bool(
                row["reviewed_self_descriptions"]
            )
    output.mkdir(parents=True, exist_ok=True)
    _write_rows(output / "candidate-queries.jsonl.gz", result)
    _write_rows(output / "dime-matched-source-rows.jsonl.gz", source_rows)
    _write_rows(
        output / "dime-cross-office-review.jsonl.gz",
        [lead for row in result for lead in row["dime_cross_office_leads"]],
    )
    _write_rows(output / "campaignview-matched-index.jsonl.gz", cv_rows)
    _write_rows(output / "cawp-source-rows.jsonl.gz", cawp_records)
    _write_rows(output / "cawp-reported-race-source-rows.jsonl.gz", cawp_race_records)
    _write_rows(output / "historical-website-attempts.jsonl.gz", website_rows)
    _write_rows(
        output / "identity-review-queue.jsonl.gz",
        [
            {
                "contest_id": row["contest_id"],
                "name": row["name"],
                "fec_id": row["fec_id"],
                "state": row["state"],
                "chamber": row["chamber"],
                "religion_needs_evidence": row["v3_religion"] in (None, "unknown"),
                "race_needs_evidence": row["v3_race"] in (None, "unknown"),
                "campaignview_uids": [record["uid"] for record in row["campaignview"]["records"]],
                "historical_websites": [
                    record["website_url"] for record in row["historical_website_attempts"]
                ],
                "review_rule": (
                    "Explicit sourced self-identification only; check dates and identity; "
                    "do not infer from names, photos, neighborhoods or generic issue references."
                ),
            }
            for row in result
            if row["name"]
            and (row["v3_religion"] in (None, "unknown") or row["v3_race"] in (None, "unknown"))
        ],
    )
    write_json(output / "source-receipts.json", receipts)
    write_json(output / "reused-source-receipts.json", reused_sources)
    write_json(output / "reviewed-self-descriptions.json", reviewed)
    summary = {
        "scope": "all_input_2026_contests; Democratic_nominee_evidence; no_new_election_fits",
        "dime": {
            "original_rows": source_count,
            "matched_source_rows": len(source_rows),
            "matched_fec_ids_before_qualification": len(dime),
            "status_counts": dict(Counter(row["dime"]["status"] for row in result)),
            "fec_prefix_chamber_conflicts_in_original": chamber_conflicts,
            "note": "FEC prefix inconsistencies can include cross-chamber careers; not corrected here.",
        },
        "campaignview": {
            "index_rows": len(index),
            "matched_fec_ids_before_qualification": len(cv),
            "detail_records_acquired": len(details),
            "historical_years": sorted({year for row in index for year in row["years"]}),
            "note": "Old biographies, not current 2026 identities or policy positions.",
        },
        "cawp": {
            "original_rows": len(cawp_records),
            "individual_winner_race_records": len(cawp_race_records),
            "encoding": "cp1252",
            "note": (
                "Current women candidate roster, including primary losers and state offices. "
                "CSV contains no race or religion field. Separate public winner embeds "
                "supply literal reported race observations, not all-nominee or pre-election "
                "labels. No missing-gender or race inference."
            ),
        },
        "coverage": {key: dict(value) for key, value in sorted(groups.items())},
        "inputs": {
            "queries_archive": fingerprint(queries_archive) if queries_archive else None,
            "religion_publication_cutoff": "2026-11-03",
            "database_manifest": fingerprint(manifest),
            "self_description_annotations": fingerprint(annotations) if annotations else None,
            "reused_research_manifest": fingerprint(research_manifest)
            if research_manifest
            else None,
            "parsed_2026_query_sha256": hashlib.sha256(
                json.dumps(queries, sort_keys=True, allow_nan=False).encode()
            ).hexdigest(),
            "dime_receipt": receipt_by_id["dime-recipients"],
        },
        "publication_status": "withdrawn; research_only; no_automatic_republication",
    }
    write_json(output / "coverage.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["acquire", "build"])
    parser.add_argument("--cache", type=Path, default=Path("data/raw/candidate-databases-20261113"))
    parser.add_argument(
        "--manifest", type=Path, default=Path("data/candidate-database-sources.json")
    )
    parser.add_argument(
        "--queries",
        type=Path,
        default=Path("results/2026-v3/analysis/candidate-queries.jsonl.gz"),
    )
    parser.add_argument("--output", type=Path, default=Path("results/2026-source-expansion"))
    parser.add_argument(
        "--research-manifest", type=Path, default=Path("data/research-sources.json")
    )
    parser.add_argument(
        "--annotations", type=Path, default=Path("data/candidate-self-descriptions.json")
    )
    args = parser.parse_args()
    queries = load_queries(args.queries)
    if args.command == "acquire":
        snapshot(args.cache, args.manifest, queries)
    else:
        print(
            json.dumps(
                build(
                    args.cache,
                    args.manifest,
                    queries,
                    args.output,
                    args.research_manifest,
                    args.queries,
                    args.annotations,
                ),
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
