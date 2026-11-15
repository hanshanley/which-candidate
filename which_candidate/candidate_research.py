"""Reproducible uncovered-person queue and public source-discovery receipts."""

import argparse
import base64
import csv
import hashlib
import html
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from .corrected import same_name
from .incoming_biographies import visible_text
from .reviewed_backgrounds import CONTEXT
from .storage import fingerprint, read_rows, write_json

DIRECTORY = "https://vote-usa.org/Election.aspx?Election=U320261103GA"
CACHE = "data/raw/candidate-backgrounds-20261115"
OFFICIAL_LEADS = {
    "Claire Valdez": "https://www.assembly.state.ny.us/mem/Claire-Valdez/bio/",
    "Micah Lasher": "https://assembly.state.ny.us/mem/Micah-C-Lasher/bio/",
    "Jasmine Clark": "https://www.legis.ga.gov/api/document/docs/default-source/bios/clark-jasmine-4953.pdf",
    "Gabe Firment": "https://house.legis.state.la.us/H_Reps/members2?ID=22",
    "Blake Miguez": "https://www.lsmsa.edu/list-detail?pk=223270",
    "Bob Onder": "https://onder.house.gov/about",
    "Jennifer Balkcom": "https://webservices.ncleg.gov/ViewDocSiteFile/91592",
    "Chuck Gray": "https://docs.house.gov/meetings/HA/HA00/20260210/118938/HHRG-119-HA00-Bio-GrayC-20260210.pdf",
}
CAMPAIGN_LEADS = {
    "Stewart Cathey, Jr.": "https://www.stewartcathey.com/about",
    "Blake Miguez": "https://blakemiguez.com/about/",
    "Marty Jackley": "https://martyjackley.com/",
    "Gabe Firment": "https://www.firmentforcongress.com/",
    "Luke Bronin": "https://www.broninforcongress.com/",
    "Matt Gromlich": "https://www.mattgromlichforcongress.com/",
    "Tisha Benoit": "https://weareindependentusa.org/tisha",
    "James Pericola": "https://jamespericola.com/",
    "Robert People": "https://www.peopleforcongress.com/",
    "Dave Dawson": "https://davedawsonforiowa.com/about",
    "Priscilla Gonzalez": "https://prisforcongress.com/",
    "Caleb Walker": "https://www.calebforcongress.com/",
    "Conrad Cable": "https://www.conrad4congress2026.com/meet-conrad",
    "Dan McKay": "https://mckayforcongress.com/",
    "Monique Appeaning": "https://www.appeaningforcongress.com/",
    "Courtney McClain": "https://www.mcclainforsc.com/about",
    "Aaron Gies": "https://aaronforny23.com/",
    "Elizabeth Kirtley": "https://www.elizabethforus.com/",
    "Yolanda Prince": "https://yolandaprince.com/",
    "Teresa Fox": "https://foxforwa.com/",
}
PUBLIC_DIRECTORY_LEADS = {
    "Chris D. Chung": "https://wa.facetheballot.com/races/congressional-district-10",
    "Tisha Benoit": "https://onyourballot.vote411.org/race-detail.do?id=3724877",
}
DIRECTORY_ALIASES = {
    "219765": 'Thomas "Jay" Feely, IV',
    "220138": "Te Mayonna Brown",
    "220174": "Benjamin Matthew Day",
    "220195": "Jasmine Clark, Dr.",
    "220266": "Michael Scott Noack",
    "220324": 'Cynthia "Cinde" Wirth',
    "220397": 'John "Drew" Williams',
    "220534": "Thomas J. Smith",
    "220545": "Mike Bouchard",
    "220560": "Taras P. Nykoriak",
    "220900": "Eugene F. Douglass",
    "220906": 'Mahesh "Max" Ganorkar',
    "220818": "Rosemary Pino",
    "220784": "Ndidiamaka Ekwua Charlene Okpareke",
    "220716": "David Alton Flippo",
    "220860": "Jomo Williams",
    "220873": "Jackie Mary Auringer",
    "221026": "Martin Young",
    "221041": "David Alan Bradstock",
    "221140": "Federick D. Haynes, III",
    "221167": 'Nicole "Nikki" Gronli',
}
AT_LARGE_STATES = {"AK", "DE", "ND", "SD", "VT", "WY"}
BACKGROUND_FIELDS = {
    "education": {"education"},
    "professional_history": {
        "professional_history",
        "occupation",
        "occupational_background",
        "business_experience",
    },
    "prior_office": {"prior_office", "elected_office_experience", "governmental_experience"},
    "military_service": {"military_service"},
}
GAP_STATUSES = {
    "discovery_inadequate_retry_required",
    "contextual_leads_pending_review",
    "reviewed_no_qualified_facts",
    "questionnaire_fields_unavailable",
    "source_access_failed",
    "no_contextual_biography_located",
    "captured_page_without_qualifying_background",
}
SOURCE_OUTCOMES = {
    "accepted_reviewed_fields",
    "additional_source_not_credited",
    "directory_listing_not_background",
    "provider_page_not_candidate_evidence",
    "captured_questionnaire_answer_empty",
    "reviewed_no_qualified_facts",
    "captured_page_without_visible_background",
    "directory_subject_not_qualified",
    "directory_structured_fields_unavailable",
    "source_pending_factual_review",
}


def background_field_coverage(observations):
    unavailable = {
        "",
        "unknown",
        "n/a",
        "not available",
        "not provided",
        "no response",
        "no response provided",
        "none provided",
        "refused",
        "declined",
    }

    def supplied(value):
        if isinstance(value, (list, tuple)):
            return any(supplied(item) for item in value)
        if isinstance(value, dict):
            return any(supplied(item) for item in value.values())
        return value is not None and str(value).strip().casefold() not in unavailable

    fields = {row["field"] for row in observations if supplied(row["value"])}
    present = sorted(key for key, aliases in BACKGROUND_FIELDS.items() if fields & aliases)
    return {
        "background_fields_with_observations": present,
        "remaining_background_fields": sorted(set(BACKGROUND_FIELDS) - set(present)),
    }


def attach_dispositions(root, profiles):
    """Validate the completed research ledger against current normalized observations."""
    root = Path(root)
    queue_path = root / "data/candidate-research-queue.json"
    ledger_path = root / "data/candidate-research-dispositions.json"
    if not ledger_path.exists():
        return {}
    queue = json.loads(queue_path.read_text())
    ledger = json.loads(ledger_path.read_text())
    if ledger.get("schema") != "which_candidate.candidate_research.v1" or ledger.get(
        "queue_fingerprint"
    ) != fingerprint(queue_path):
        raise ValueError("Research dispositions require a finalized, unchanged queue")
    queued = {row["candidate_id"]: row for row in queue["candidates"]}
    decisions = {row["candidate_id"]: row for row in ledger["candidates"]}
    identities = {row["candidate_id"]: row for row in profiles}
    if (
        len(queued) != len(queue["candidates"])
        or len(decisions) != len(ledger["candidates"])
        or len(identities) != len(profiles)
        or decisions.keys() != queued.keys()
        or not queued.keys() <= identities.keys()
    ):
        raise ValueError("Research ledger must account for every queued person exactly once")
    acquisition = json.loads((root / "data/candidate-acquisition.json").read_text())
    receipts = {row["id"]: row for row in acquisition["sources"]}
    attempts = {row["candidate_id"]: row for row in acquisition["candidates"]}
    if len(receipts) != len(acquisition["sources"]) or len(attempts) != len(
        acquisition["candidates"]
    ):
        raise ValueError("Duplicate candidate or source in acquisition manifest")
    for profile in profiles:
        observations = profile["acquired_background_observations"]
        profile.update(background_field_coverage(observations))
        decision = decisions.get(profile["candidate_id"])
        profile["in_initial_research_queue"] = decision is not None
        if decision is None:
            profile["background_research"] = {
                "research_status": "outside_initial_uncovered_queue",
                "disposition": "Already had observations at the frozen research baseline.",
            }
            continue
        original = queued[profile["candidate_id"]]
        if any(profile[key] != original[key] or decision[key] != original[key] for key in CONTEXT):
            raise ValueError("Research disposition conflicts with candidate-contest context")
        status = decision["research_status"]
        if (
            status not in GAP_STATUSES | {"sourced_observations_partial"}
            or not decision.get("disposition", "").strip()
            or decision["acquired_observations"] != bool(observations)
            or (status == "sourced_observations_partial") != bool(observations)
            or decision["acquired_observation_count"] != len(observations)
            or any(
                decision[key] != profile[key]
                for key in ("background_fields_with_observations", "remaining_background_fields")
            )
        ):
            raise ValueError("Research disposition is stale or claims unsupported coverage")
        observed_sources = {
            row["evidence"]["source_id"]
            for row in observations
            if isinstance(row["evidence"], dict) and row["evidence"].get("source_id")
        }
        accepted = decision["accepted_source_ids"]
        if len(set(accepted)) != len(accepted) or set(accepted) != observed_sources:
            raise ValueError("Research accepted sources disagree with normalized evidence")
        acquisition_candidate = attempts.get(profile["candidate_id"])
        if acquisition_candidate and any(
            acquisition_candidate[key] != original[key] for key in CONTEXT
        ):
            raise ValueError("Research acquisition conflicts with candidate-contest context")
        owned = set((acquisition_candidate or {}).get("source_ids", []))
        outcomes = decision["source_outcomes"]
        outcome_ids = [row["source_id"] for row in outcomes]
        if (
            len(set(outcome_ids)) != len(outcome_ids)
            or set(outcome_ids) != owned
            or set(accepted)
            != {row["source_id"] for row in outcomes if row["status"] == "accepted_reviewed_fields"}
        ):
            raise ValueError("Research source outcomes must account for every acquired source")
        for outcome in decision["source_outcomes"]:
            receipt = receipts.get(outcome["source_id"], {})
            if (
                outcome["source_id"] not in owned
                or outcome["status"] not in SOURCE_OUTCOMES
                or outcome["sha256"] != receipt.get("sha256")
                or outcome["url"] != receipt.get("url")
                or outcome["retrieved_at"] != receipt.get("retrieved_at")
            ):
                raise ValueError("Research source outcome conflicts with acquisition receipt")
        profile["background_research"] = {
            key: decision[key]
            for key in (
                "research_status",
                "disposition",
                "accepted_source_ids",
                "source_outcomes",
                "failed_attempts",
                "search_query",
                "search_receipt",
            )
        }
    return {
        "baseline_candidates": queue["baseline_candidates"],
        "baseline_with_observations": queue["baseline_covered"],
        "initially_uncovered": len(queued),
        "newly_covered_people": sum(row["acquired_observations"] for row in decisions.values()),
        "remaining_uncovered_people": sum(
            not row["acquired_observations"] for row in decisions.values()
        ),
        "documented_dispositions": len(decisions),
        "remaining_fields": {
            field: sum(field in row["remaining_background_fields"] for row in profiles)
            for field in BACKGROUND_FIELDS
        },
        "interpretation": (
            "Field presence is not a complete or independently verified biography. "
            "Historical, self-reported and machine-extracted observations retain qualifications; "
            "missing service or office does not mean nonservice or never held office."
        ),
    }


def directory_matches(candidate, rows):
    district = "01" if candidate["state"] in AT_LARGE_STATES else candidate["district"]
    return [
        row
        for row in rows
        if row["state"] == candidate["state"]
        and (
            "01"
            if row["state"] in AT_LARGE_STATES and row["district"] in ("00", "01")
            else row["district"]
        )
        == district
        and (
            same_name(row["name"], candidate["name"])
            or row["name"] == DIRECTORY_ALIASES.get(candidate["candidate_id"])
        )
        and (
            row["party_code"] is None
            or candidate["party"] not in ("Democratic", "Republican")
            or row["party_code"] == {"Democratic": "D", "Republican": "R"}[candidate["party"]]
        )
    ]


def add_official_leads(root):
    root = Path(root)
    path = root / "data/candidate-source-leads.json"
    leads = json.loads(path.read_text())
    known = {(row["candidate_id"], row["url"]) for row in leads}
    for candidate in establish_queue(root)["candidates"]:
        for registry, kind in (
            (OFFICIAL_LEADS, "official_previous_office_biography"),
            (CAMPAIGN_LEADS, "candidate_campaign_self_report"),
            (PUBLIC_DIRECTORY_LEADS, "public_voter_directory_biography"),
        ):
            url = registry.get(candidate["name"])
            if url and (candidate["candidate_id"], url) not in known:
                leads.append(
                    {
                        **{key: candidate[key] for key in CONTEXT},
                        "url": url,
                        "source_kind": kind,
                    }
                )
                known.add((candidate["candidate_id"], url))
    for lead in leads:
        if lead.get("source_kind") == "candidate_supplied_voter_directory":
            lead["source_kind"] = "public_voter_directory_biography"
    write_json(path, leads)


def refresh_directory_leads(root):
    root = Path(root)
    path = root / "data/candidate-research-dispositions.json"
    ledger = json.loads(path.read_text())
    receipt = ledger["directory_receipt"]
    original = root / receipt["path"]
    if fingerprint(original) != {key: receipt[key] for key in ("bytes", "sha256")}:
        raise ValueError("Directory original changed")
    rows = directory_candidates(original.read_bytes())
    leads_path = root / "data/candidate-source-leads.json"
    leads = json.loads(leads_path.read_text())
    known = {(row["candidate_id"], row["url"]) for row in leads}
    for candidate in ledger["candidates"]:
        matches = directory_matches(candidate, rows)
        candidate["directory_matches"] = matches
        for match in matches:
            for kind, field in (
                ("candidate_campaign_self_report", "campaign_url"),
                ("public_voter_directory_biography", "intro_url"),
            ):
                url = match[field]
                if url and url.startswith("http://"):
                    url = "https://" + url[len("http://") :]
                if url and (candidate["candidate_id"], url) not in known:
                    leads.append(
                        {
                            **{key: candidate[key] for key in CONTEXT},
                            "url": url,
                            "source_kind": kind,
                            "discovery_url": DIRECTORY,
                            "directory_name": match["name"],
                            "directory_party_code": match["party_code"],
                            "qualification": "Contextual discovery lead; factual identity review still required",
                        }
                    )
                    known.add((candidate["candidate_id"], url))
    write_json(path, ledger)
    write_json(leads_path, leads)


def directory_candidates(raw):
    rows = []
    for office in raw.decode("utf-8", "replace").split(
        '<div class="office-title accordion-header">'
    )[1:]:
        context = re.search(r'CompareCandidates\.aspx\?([^"]+)', office)
        if context is None:
            continue
        query = urllib.parse.parse_qs(html.unescape(context[1]))
        state = query["State"][0]
        seat = re.fullmatch(state + r"USHouse(\d*)", query.get("Office", [""])[0])
        if seat is None:
            continue
        for cell in office.split('<div class="candidate-cell">')[1:]:
            name = re.search(r'<div class="candidate-name">(.*?)</div>', cell, re.S)
            intro = re.search(r'href="([^"]*Intro\.aspx\?[^"]+)"', cell)
            if name is None or intro is None:
                continue
            literal = visible_text(name[1].encode())
            party = re.search(r" - ([A-Z])$", literal)
            website = re.search(r'<div class="candidate-website">.*?href="([^"]+)"', cell, re.S)
            rows.append(
                {
                    "name": re.sub(r" - [A-Z]$", "", literal).strip(),
                    "state": state,
                    "district": (seat[1] or "0").zfill(2),
                    "party_code": party[1] if party else None,
                    "intro_url": html.unescape(intro[1]),
                    "campaign_url": html.unescape(website[1]) if website else None,
                }
            )
    return rows


def public_fetch(url, root, label, timeout=25):
    stamp = datetime.now(timezone.utc).isoformat()
    receipt = {"url": url, "retrieved_at": stamp, "publication_date": None}
    try:
        request = urllib.request.Request(
            url, headers={"User-Agent": "WhichCandidateResearch/1.0 (public biography research)"}
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(8 * 1024 * 1024 + 1)
            receipt.update(
                http_status=response.status,
                resolved_url=response.url,
                media_type=response.headers.get("Content-Type", "").split(";")[0],
            )
        if not body or len(body) > 8 * 1024 * 1024 or receipt["http_status"] != 200:
            return {**receipt, "status": "empty_or_unsupported_response"}, None
        if any(
            marker in visible_text(body)[:1500].casefold()
            for marker in ("verify you are human", "access denied", "just a moment...")
        ):
            return {**receipt, "status": "access_challenge_not_bypassed"}, None
        digest = hashlib.sha256(body).hexdigest()
        suffix = ".pdf" if receipt["media_type"] == "application/pdf" else ".html"
        path = Path(root) / CACHE / f"{label}-{digest[:20]}{suffix}"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        return {
            **receipt,
            "status": "acquired_not_reviewed",
            "path": str(path.relative_to(root)),
            **fingerprint(path),
        }, body
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as error:
        return {**receipt, "status": "retrieval_failed", "error": str(error)}, None


def establish_queue(root):
    root = Path(root)
    source = root / "results/house-study/candidate-profiles.jsonl.gz"
    path = root / "data/candidate-research-queue.json"
    if path.exists():
        return json.loads(path.read_text())
    profiles = read_rows(source)
    missing = [row for row in profiles if not row["acquired_background_observations"]]
    missing.sort(
        key=lambda row: (
            0 if row["party"] in ("Democratic", "Republican") else 1,
            row["state"],
            row["district"],
            row["party"],
            row["name"],
            row["candidate_id"],
        )
    )
    queue = {
        "scope": "Frozen initially uncovered 2026 House people; not the per-field gap table",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "profile_input": fingerprint(source),
        "baseline_candidates": len(profiles),
        "baseline_covered": len(profiles) - len(missing),
        "baseline_uncovered": len(missing),
        "candidates": [
            {**{key: row[key] for key in CONTEXT}, "campaign_websites": row["campaign_websites"]}
            for row in missing
        ],
    }
    write_json(path, queue)
    return queue


def search_links(body):
    results = []
    for heading in re.findall(r"<h2\b[^>]*>(.*?)</h2>", body.decode("utf-8", "replace"), re.S):
        link = re.search(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', heading, re.S)
        if link is None:
            continue
        url = html.unescape(link[1])
        parts = urllib.parse.urlsplit(url)
        if parts.hostname and parts.hostname.endswith("bing.com"):
            encoded = urllib.parse.parse_qs(parts.query).get("u", [""])[0]
            if encoded.startswith("a1"):
                try:
                    url = base64.urlsafe_b64decode(encoded[2:] + "===").decode()
                except (ValueError, UnicodeError):
                    continue
        if urllib.parse.urlsplit(url).scheme not in ("http", "https"):
            continue
        results.append({"url": url, "title": visible_text(link[2].encode())})
    return results[:10]


def discover(root):
    from .candidate_discovery import assess_results

    root = Path(root)
    queue = establish_queue(root)
    directory_receipt, body = public_fetch(DIRECTORY, root, "vote-usa-directory", timeout=60)
    rows = directory_candidates(body) if body else []
    leads_path = root / "data/candidate-source-leads.json"
    leads = json.loads(leads_path.read_text()) if leads_path.exists() else []
    known = {(row["candidate_id"], row["url"]) for row in leads}
    ledger_path = root / "data/candidate-research-dispositions.json"
    ledger = (
        json.loads(ledger_path.read_text())
        if ledger_path.exists()
        else {
            "scope": "Candidate-specific source search; sourced facts and unresolved gaps stay separate",
            "directory_receipt": directory_receipt,
            "candidates": [],
        }
    )
    completed = {
        row["candidate_id"]
        for row in ledger["candidates"]
        if row.get("acquired_observations")
        or assess_results(row, row.get("search_result_links", []))["relevant_results"]
    }

    def research(candidate):
        matches = directory_matches(candidate, rows)
        query = f'"{candidate["name"]}" {candidate["state"]} Congress 2026 biography'
        url = "https://www.bing.com/search?" + urllib.parse.urlencode({"q": query})
        receipt, search_body = public_fetch(url, root, f"search-{candidate['candidate_id']}")
        links = search_links(search_body) if search_body else []
        quality = assess_results(candidate, links)
        return {
            **{key: candidate[key] for key in CONTEXT},
            "research_status": (
                "source_discovery_completed; factual_review_pending"
                if quality["relevant_results"]
                else "discovery_inadequate_retry_required"
            ),
            "directory_matches": matches,
            "search_query": query,
            "search_receipt": receipt,
            "search_result_links": links,
            "search_quality": quality,
            "acquired_observations": False,
            "disposition": "No facts credited from directory listings or search snippets.",
        }

    pending = [row for row in queue["candidates"] if row["candidate_id"] not in completed]
    for major in (True, False):
        group = [row for row in pending if (row["party"] in ("Democratic", "Republican")) == major]
        with ThreadPoolExecutor(max_workers=4) as executor:
            for result in executor.map(research, group):
                for match in result["directory_matches"]:
                    for kind, field in (
                        ("candidate_campaign_self_report", "campaign_url"),
                        ("public_voter_directory_biography", "intro_url"),
                    ):
                        url = match[field]
                        if url and url.startswith("http://"):
                            url = "https://" + url[len("http://") :]
                        if url and (result["candidate_id"], url) not in known:
                            leads.append(
                                {
                                    **{key: result[key] for key in CONTEXT},
                                    "url": url,
                                    "source_kind": kind,
                                    "discovery_url": DIRECTORY,
                                    "directory_name": match["name"],
                                    "directory_party_code": match["party_code"],
                                }
                            )
                            known.add((result["candidate_id"], url))
                previous = next(
                    (
                        row
                        for row in ledger["candidates"]
                        if row["candidate_id"] == result["candidate_id"]
                    ),
                    None,
                )
                if previous is None:
                    ledger["candidates"].append(result)
                else:
                    history = previous.setdefault("search_history", [])
                    history.append(
                        {
                            key: previous[key]
                            for key in ("search_query", "search_receipt", "search_result_links")
                        }
                    )
                    previous.update(
                        {
                            key: result[key]
                            for key in (
                                "search_query",
                                "search_receipt",
                                "search_result_links",
                                "search_quality",
                            )
                        }
                    )
                write_json(ledger_path, ledger)
                write_json(leads_path, leads)
                print(
                    result["name"],
                    len(result["directory_matches"]),
                    "directory matches",
                    flush=True,
                )
    return {
        "queued": len(queue["candidates"]),
        "searched": len(ledger["candidates"]),
        "leads": len(leads),
    }


def finalize(root):
    """Reconcile accepted normalized facts and explicit remaining-gap review notes."""
    root = Path(root)
    queue_path = root / "data/candidate-research-queue.json"
    ledger_path = root / "data/candidate-research-dispositions.json"
    queue = json.loads(queue_path.read_text())
    ledger = json.loads(ledger_path.read_text())
    repair_path = root / "data/candidate-discovery-repair.json"
    repair = (
        {row["candidate_id"]: row for row in json.loads(repair_path.read_text())["candidates"]}
        if repair_path.exists()
        else {}
    )
    decisions = {row["candidate_id"]: row for row in ledger["candidates"]}
    if len(decisions) != len(ledger["candidates"]) or set(decisions) != {
        row["candidate_id"] for row in queue["candidates"]
    }:
        raise ValueError("Finalization requires every queued research decision exactly once")
    acquisition = json.loads((root / "data/candidate-acquisition.json").read_text())
    candidates = {row["candidate_id"]: row for row in acquisition["candidates"]}
    sources = {row["id"]: row for row in acquisition["sources"]}
    held = root / "results/house"
    manifest = json.loads((held / "manifest.json").read_text())
    for name in ("candidates.jsonl.gz", "background-observations.csv"):
        if fingerprint(held / name) != manifest["files"][name]:
            raise ValueError(f"Changed normalized research input: {name}")
    observations = {}
    with (held / "background-observations.csv").open() as stream:
        for row in csv.DictReader(stream):
            observations.setdefault(row["candidate_id"], []).append(
                {
                    "field": row["field"],
                    "value": json.loads(row["value"]),
                    "evidence": json.loads(row["evidence"]) if row["evidence"] else None,
                }
            )
    for original in queue["candidates"]:
        cid = original["candidate_id"]
        decision = decisions[cid]
        if any(original[key] != decision[key] for key in CONTEXT):
            raise ValueError("Research decision conflicts with frozen candidate context")
        records = observations.get(cid, [])
        accepted = {
            row["evidence"]["source_id"]
            for row in records
            if isinstance(row["evidence"], dict) and row["evidence"].get("source_id")
        }
        candidate = candidates.get(cid, {"source_ids": [], "attempts": []})
        previous = {row["source_id"]: row for row in decision.get("source_outcomes", [])}
        follow_up = repair.get(cid, {})
        directory_profiles = {
            row["source_id"]: row
            for row in follow_up.get("public_directory_lookup", {}).get("extracted_profiles", [])
        }
        outcomes = []
        for sid in candidate["source_ids"]:
            source = sources[sid]
            location = urllib.parse.urlsplit(source["url"])
            directory = location.hostname in {"vote-usa.org", "www.vote-usa.org"}
            outcome = {
                "source_id": sid,
                **{key: source[key] for key in ("url", "sha256", "retrieved_at")},
            }
            if sid in accepted:
                status = "accepted_reviewed_fields"
            elif sid in previous and all(
                previous[sid][key] == source[key] for key in ("sha256", "url", "retrieved_at")
            ):
                status = previous[sid]["status"]
            elif records:
                status = "additional_source_not_credited"
            elif sid in directory_profiles:
                if fingerprint(root / source["path"]) != {
                    key: source[key] for key in ("bytes", "sha256")
                }:
                    raise ValueError("Changed source while finalizing directory disposition")
                extracted = directory_profiles[sid]
                status = (
                    "directory_subject_not_qualified"
                    if extracted["identity_status"] != "name_and_2026_house_context_matched"
                    else (
                        "source_pending_factual_review"
                        if extracted["fields"]
                        else "directory_structured_fields_unavailable"
                    )
                )
            elif directory and location.path.lower() == "/intro.aspx":
                status = "directory_listing_not_background"
            elif directory and location.path.lower() == "/ajaxcontent.aspx":
                path = root / source["path"]
                if fingerprint(path) != {key: source[key] for key in ("bytes", "sha256")}:
                    raise ValueError("Changed source while finalizing questionnaire disposition")
                if not visible_text(path.read_bytes()).strip():
                    status = "captured_questionnaire_answer_empty"
                elif decision.get("review_note") and sid in decision.get("reviewed_source_ids", []):
                    status = "reviewed_no_qualified_facts"
                else:
                    raise ValueError(f"Nonempty questionnaire still needs review: {cid}, {sid}")
            elif directory:
                status = "provider_page_not_candidate_evidence"
            elif decision.get("review_note") and sid in decision.get("reviewed_source_ids", []):
                status = "reviewed_no_qualified_facts"
            else:
                path = root / source["path"]
                if fingerprint(path) != {key: source[key] for key in ("bytes", "sha256")}:
                    raise ValueError("Changed source while finalizing page disposition")
                if (
                    source.get("media_type") != "application/pdf"
                    and not visible_text(path.read_bytes()).strip()
                ):
                    status = "captured_page_without_visible_background"
                else:
                    raise ValueError(
                        f"Captured source still needs a review disposition: {cid}, {sid}"
                    )
            outcomes.append({**outcome, "status": status})
        failures = [row for row in candidate["attempts"] if not row.get("source_id")]
        if records:
            status = "sourced_observations_partial"
            note = (
                f"Accepted {len(records)} factual/source-reported observations from "
                f"{len(accepted)} reviewed sources. This is partial background evidence, "
                "not a complete or independently verified biography."
            )
        elif decision.get("review_note"):
            status = "reviewed_no_qualified_facts"
            note = decision["review_note"]
        elif outcomes:
            questionnaire = any(
                row["status"] == "captured_questionnaire_answer_empty" for row in outcomes
            )
            status = (
                "questionnaire_fields_unavailable"
                if questionnaire
                else "captured_page_without_qualifying_background"
            )
            note = (
                "Context-matched directory/profile requests yielded no accepted background "
                "fields. Empty captured answers or page shells do not establish nonservice, "
                "lack of education, or that the candidate did not submit information."
            )
        elif failures:
            status = "source_access_failed"
            note = (
                f"Located {len(failures)} source-request attempts, but none yielded accepted "
                "candidate-background evidence. Access/transport failures are recorded, not "
                "bypassed or interpreted as absent credentials."
            )
        else:
            status = "no_contextual_biography_located"
            note = (
                f"No accepted biography located for {original['name']} in "
                f"{original['state']}-{original['district']} ({original['party']}). "
                f"The nationwide directory returned {len(decision['directory_matches'])} "
                "contextual matches; the individual search receipt and returned links "
                "are discovery-only, not evidence or an exhaustive absence claim."
            )
        follow_up = repair.get(cid)
        if not records and follow_up:
            if follow_up["discovery_status"] == "retry_required":
                status = "discovery_inadequate_retry_required"
                note = (
                    "Earlier first-name-only/irrelevant results are failed discovery, not "
                    "adequate candidate research. Further contextual source discovery is "
                    "required; unsuccessful URL lookups do not establish absent biographies."
                )
            elif follow_up["discovery_status"] == "leads_pending_source_review":
                status = "contextual_leads_pending_review"
                note = (
                    "The repaired discovery pass located contextual leads that still need "
                    "source acquisition, identity qualification and factual review. No "
                    "background fields are credited from search results alone."
                )
            elif follow_up["discovery_status"] == "reviewed_gap_documented":
                status = "reviewed_no_qualified_facts"
                note = follow_up["disposition"]
        decision.update(
            research_status=status,
            disposition=note,
            acquired_observations=bool(records),
            acquired_observation_count=len(records),
            accepted_source_ids=sorted(accepted),
            source_outcomes=outcomes,
            failed_attempts=failures,
            **background_field_coverage(records),
        )
        candidate["facts_reviewed"] = bool(accepted) or bool(decision.get("review_note"))
        candidate["counted_as_background_coverage"] = bool(records)
    ledger.update(
        schema="which_candidate.candidate_research.v1",
        queue_fingerprint=fingerprint(queue_path),
        finalized_at=ledger.get("finalized_at", datetime.now(timezone.utc).isoformat()),
        qualification=(
            "Bounded research-pass outcomes, not exhaustive public-data absence claims. "
            "Search snippets and downloads are never promoted to facts. Missing fields "
            "remain unknown; all newly accepted evidence is descriptive/model-ineligible."
        ),
    )
    write_json(ledger_path, ledger)
    write_json(root / "data/candidate-acquisition.json", acquisition)
    profiles = [
        {**row, "acquired_background_observations": observations.get(row["candidate_id"], [])}
        for row in read_rows(held / "candidates.jsonl.gz")
    ]
    return attach_dispositions(root, profiles)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--finalize", action="store_true")
    args = parser.parse_args()
    print(json.dumps(finalize(args.root) if args.finalize else discover(args.root), indent=2))
