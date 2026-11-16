"""Audit source-search relevance and track a separate, resumable field-gap repair."""

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote

from pypdf import PdfReader

from .benchmarks import STATE_NAMES
from .candidate_research import BACKGROUND_FIELDS, background_field_coverage
from .corrected import same_name
from .incoming_biographies import visible_text
from .rebuild import ROOT
from .reviewed_backgrounds import CONTEXT, normalized
from .storage import confined, fingerprint, read_rows, write_json

PATH = "data/candidate-discovery-repair.json"


def words(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.findall(r"[a-z0-9]+", text.casefold())


def assess_results(candidate, results):
    """Reject first-name-only hits; matching results remain leads, never evidence."""
    name = [
        word for word in words(candidate["name"]) if word not in {"jr", "sr", "ii", "iii", "iv"}
    ]
    relevant, rejected = [], []
    for result in results:
        if result.get("identity_review") == "rejected":
            rejected.append(result)
            continue
        title = words(result.get("title", ""))
        url = words(unquote(result.get("url", "")))
        snippet = words(result.get("snippet", ""))
        tokens = set(title + url + snippet)
        surname = name[-1] if name else ""
        given = name[0] if name else ""
        name_match = bool(surname and given and surname in tokens and given in tokens)
        compact = "".join(title + url)
        name_match |= len(name) > 1 and "".join(name) in compact
        political = bool(
            tokens & {"congress", "congressional", "candidate", "ballot", "ballotpedia", "campaign"}
        )
        institutional = bool(
            tokens & {"faculty", "biography", "professor", "university", "legislature"}
        )
        contextual = candidate["state"].casefold() in tokens or political or institutional
        accepted = name_match and contextual
        (relevant if accepted else rejected).append(result)
    return {
        "status": "contextual_leads_found" if relevant else "failed_irrelevant_or_empty_results",
        "relevant_results": relevant,
        "rejected_results": rejected,
        "qualification": "Automated lead screening only; factual identity and source review required.",
    }


def queries(candidate):
    name = candidate["name"].replace('"', "")
    state, district = candidate["state"], candidate["district"]
    return [
        f'"{name}" {state} "{district}" Congress biography education employment',
        f'"{name}" {state} campaign about university government voter guide',
        f'"{name}" {state} (site:edu OR site:gov OR site:vote411.org OR site:ballotpedia.org)',
    ]


def audit(root=ROOT):
    root = Path(root)
    path = root / PATH
    profiles = read_rows(root / "results/house-study/candidate-profiles.jsonl.gz")
    old = json.loads((root / "data/candidate-research-dispositions.json").read_text())
    old_by_id = {row["candidate_id"]: row for row in old["candidates"]}
    if path.exists():
        report = json.loads(path.read_text())
    else:
        rows = []
        for profile in profiles:
            observations = profile["acquired_background_observations"]
            missing = background_field_coverage(observations)["remaining_background_fields"]
            targets = [field for field in ("education", "professional_history") if field in missing]
            if observations and not targets:
                continue
            previous = old_by_id.get(profile["candidate_id"])
            rows.append(
                {
                    **{key: profile[key] for key in CONTEXT},
                    "baseline_has_observations": bool(observations),
                    "baseline_missing_fields": targets,
                    "queries": queries(profile),
                    "previous_search_audit": (
                        assess_results(profile, previous.get("search_result_links", []))
                        if previous
                        else None
                    ),
                    "attempts": [],
                    "reviewed_source_ids": [],
                    "discovery_status": "retry_required",
                }
            )
        rows.sort(
            key=lambda row: (
                bool(row["baseline_has_observations"]),
                row["party"] not in ("Democratic", "Republican"),
                row["state"],
                row["district"],
                row["name"],
            )
        )
        report = {
            "schema": "which_candidate.discovery_repair.v1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "baseline_profiles": fingerprint(
                root / "results/house-study/candidate-profiles.jsonl.gz"
            ),
            "baseline_candidates": len(profiles),
            "baseline_uncovered": sum(
                not row["acquired_background_observations"] for row in profiles
            ),
            "qualification": (
                "Prior irrelevant searches are failed discovery, not adequate negative evidence. "
                "This registry preserves attempts; source downloads and search snippets are not facts."
            ),
            "candidates": rows,
        }
    write_json(path, report)
    return {
        "people": len(report["candidates"]),
        "uncovered": sum(not row["baseline_has_observations"] for row in report["candidates"]),
        "covered_with_education_or_employment_gaps": sum(
            row["baseline_has_observations"] for row in report["candidates"]
        ),
    }


def record_search(root, candidate_id, *, query, provider, results, receipt=None):
    root = Path(root)
    path = root / PATH
    report = json.loads(path.read_text())
    candidate = next(row for row in report["candidates"] if row["candidate_id"] == candidate_id)
    screening = assess_results(candidate, results)
    candidate["attempts"].append(
        {
            "provider": provider,
            "query": query,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "receipt": receipt,
            **screening,
        }
    )
    candidate["discovery_status"] = (
        "leads_pending_source_review"
        if any(attempt["relevant_results"] for attempt in candidate["attempts"])
        else "retry_required"
    )
    write_json(path, report)
    return screening


def record_gap_review(root, candidate_id, *, disposition, source_support):
    """Pin a reviewed gap without turning failed discovery into absent credentials."""
    root = Path(root)
    path = root / PATH
    report = json.loads(path.read_text())
    candidate = next(row for row in report["candidates"] if row["candidate_id"] == candidate_id)
    acquisition = json.loads((root / "data/candidate-acquisition.json").read_text())
    owner = next(row for row in acquisition["candidates"] if row["candidate_id"] == candidate_id)
    sources = {row["id"]: row for row in acquisition["sources"]}
    if any(candidate[key] != owner[key] for key in CONTEXT) or not disposition.strip():
        raise ValueError("Gap review requires exact candidate context and a disposition")
    receipts = []
    for sid, review in source_support.items():
        if sid not in owner["source_ids"]:
            raise ValueError("Gap review source belongs to a different candidate")
        source = sources[sid]
        original = confined(root, source["path"])
        if fingerprint(original) != {key: source[key] for key in ("bytes", "sha256")}:
            raise ValueError("Gap review original changed")
        pages = review.get("pdf_pages") if isinstance(review, dict) else None
        support = review.get("support") if isinstance(review, dict) else review
        if source.get("media_type") == "application/pdf":
            reader = PdfReader(original)
            if (
                not isinstance(pages, list)
                or not pages
                or not all(type(page) is int and 1 <= page <= len(reader.pages) for page in pages)
            ):
                raise ValueError("Gap review PDF requires explicit valid page references")
            text = normalized(" ".join(reader.pages[page - 1].extract_text() for page in pages))
        else:
            if pages is not None:
                raise ValueError("Gap review PDF page references require a PDF source")
            text = normalized(visible_text(original.read_bytes()))
        if (
            not isinstance(support, list)
            or not support
            or any(
                not isinstance(fragment, str)
                or not normalized(fragment)
                or normalized(fragment) not in text
                for fragment in support
            )
        ):
            raise ValueError("Gap review supporting fragment is absent")
        receipts.append(
            {
                "source_id": sid,
                **{key: source[key] for key in ("url", "retrieved_at", "sha256", "bytes")},
                "support": support,
                **({"pdf_pages": pages} if pages is not None else {}),
            }
        )
    if not receipts:
        raise ValueError("Gap review requires a reviewed source, not a query list")
    candidate["research_disposition"] = disposition
    candidate["gap_review"] = {
        **{key: candidate[key] for key in CONTEXT},
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "sources": receipts,
        "qualification": "Reviewed source-specific gap, not an exhaustive public-data absence claim.",
    }
    ledger_path = root / "data/candidate-research-dispositions.json"
    ledger = json.loads(ledger_path.read_text())
    decision = next(
        (row for row in ledger["candidates"] if row["candidate_id"] == candidate_id), None
    )
    if decision is not None:
        decision["review_note"] = disposition
        decision["reviewed_source_ids"] = sorted(
            set(decision.get("reviewed_source_ids", [])) | set(source_support)
        )
    write_json(path, report)
    write_json(ledger_path, ledger)
    return candidate["gap_review"]


def capture_extraction(
    root,
    candidate,
    *,
    url,
    text,
    provider_reference,
    source_kind,
    search_preview=False,
    provider="search",
    source_observed_at=None,
):
    """Pin a provider's extracted page, explicitly not an original HTTP response."""
    from .candidate_acquisition import merge_candidate_result

    if provider not in {"search", "web_fetch"} or (provider == "web_fetch" and search_preview):
        raise ValueError("Extraction requires a known provider and an honest preview/page method")
    root = Path(root)
    body = text.encode("utf-8")
    digest = hashlib.sha256(body).hexdigest()
    relative = (
        f"data/raw/candidate-backgrounds-20261115/{candidate['candidate_id']}-{digest[:20]}.txt"
    )
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    source_id = f"candidate-extraction-{candidate['candidate_id']}-{digest[:20]}"
    imported_at = datetime.now(timezone.utc).isoformat()
    source = {
        "id": source_id,
        "url": url,
        "resolved_url": url,
        "retrieved_at": source_observed_at or imported_at,
        "imported_at": imported_at,
        "publication_date": None,
        "path": relative,
        **fingerprint(path),
        "source_kind": source_kind,
        "media_type": "text/plain",
        "retrieval_method": (
            "public_web_fetch_page_extraction"
            if provider == "web_fetch"
            else (
                "public_search_provider_result_excerpt"
                if search_preview
                else "public_search_provider_page_extraction"
            )
        ),
        "provider_reference": provider_reference,
        "qualification": (
            f"Pinned excerpt returned by the {'web-fetch' if provider == 'web_fetch' else 'search'} provider "
            f"({'indexed search preview' if search_preview else 'page extraction'}), "
            "not original server HTML or independent verification; upstream crawl time may differ. "
            "Retrospective/model-ineligible."
        ),
    }
    manifest_path = root / "data/candidate-acquisition.json"
    manifest = json.loads(manifest_path.read_text())
    merge_candidate_result(
        manifest,
        {
            **{key: candidate[key] for key in CONTEXT},
            "source_ids": [source_id],
            "attempts": [
                {
                    "url": url,
                    "retrieved_at": source["retrieved_at"],
                    "status": "acquired_not_yet_reviewed",
                    "source_id": source_id,
                    "retrieval_method": source["retrieval_method"],
                }
            ],
            "facts_reviewed": False,
            "counted_as_background_coverage": False,
        },
        [source],
    )
    write_json(manifest_path, manifest)
    return source_id


def record_roster_identity_review(root, candidate_id, *, disposition):
    """Document an unidentified write-in label without inventing biography evidence."""
    root = Path(root)
    held = root / "results/house"
    manifest = json.loads((held / "manifest.json").read_text())
    roster = held / "candidates.jsonl.gz"
    if fingerprint(roster) != manifest["files"]["candidates.jsonl.gz"]:
        raise ValueError("Identity review requires validated normalized roster inputs")
    candidate = next(row for row in read_rows(roster) if row["candidate_id"] == candidate_id)
    if (
        candidate["party"] != "Write-In"
        or candidate.get("identity", {}).get("fec_id")
        or candidate.get("campaign_websites")
        or not disposition.strip()
    ):
        raise ValueError("Roster-only identity review requires an unidentified write-in label")
    report_path = root / PATH
    report = json.loads(report_path.read_text())
    decision = next(row for row in report["candidates"] if row["candidate_id"] == candidate_id)
    if any(decision[key] != candidate[key] for key in CONTEXT):
        raise ValueError("Identity review conflicts with pinned candidate context")
    decision["roster_identity_review"] = {
        **{key: candidate[key] for key in CONTEXT},
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "normalized_roster": {"path": "results/house/candidates.jsonl.gz", **fingerprint(roster)},
        "native_source": candidate["source"],
        "votes": candidate["votes"],
        "disposition": disposition,
        "qualification": (
            "Review of the preserved election label, not a downloaded biography or proof "
            "of candidacy, identity, absent credentials or exhausted source discovery. "
            "No background observations or complete-person coverage credited."
        ),
    }
    write_json(report_path, report)
    return decision["roster_identity_review"]


def directory_profile(raw, candidate):
    """Extract a public profile only after its name and 2026 House context match."""
    text = visible_text(raw)
    subject = re.search(r"Candidate Profile (.*?) Candidate for ", text)
    if not subject or not same_name(subject[1], candidate["name"]):
        return {"identity_status": "subject_not_qualified", "fields": {}}
    state = STATE_NAMES[candidate["state"]].title()
    district = candidate["district"]
    seat = (
        r"(?:At.Large|1(?:st)? Congressional District)"
        if district in {"AL", "00"}
        else rf"{int(district)}(?:st|nd|rd|th) Congressional District"
    )
    context = rf"Candidate for U\.S\. House of Representatives - {re.escape(state)} {seat} in 2026 "
    if not re.search(context, text):
        return {"identity_status": "contest_not_qualified", "fields": {}}
    fields = {}
    for section in re.findall(
        r"<section\b[^>]*>.*?</section>", raw.decode("utf-8", "replace"), re.S
    ):
        if not visible_text(section.encode()).startswith("About "):
            continue
        for label, field in (
            ("Professional Experience", "professional_history"),
            ("Degrees", "education"),
        ):
            if label not in section:
                continue
            chunk = section.split(label, 1)[1]
            if label == "Professional Experience":
                chunk = chunk.split("Degrees", 1)[0]
            values = [
                visible_text(value.encode())
                for value in re.findall(r'<div class="mb-2\b[^"]*">([^<]+)</div>', chunk, re.S)
            ]
            if values:
                fields[field] = values
    return {
        "identity_status": "name_and_2026_house_context_matched",
        "source_subject": subject[1],
        "fields": fields,
        "qualification": (
            "Public directory-reported fields pending manual review. A school listing "
            "without a degree is not graduation; date ranges and job labels are source-reported. "
            "Party is retained from the pinned candidate roster, not independently supplied here."
        ),
    }


def acquire_directory(root=ROOT):
    from .candidate_acquisition import acquire_candidate, merge_candidate_result

    root = Path(root)
    path = root / PATH
    report = json.loads(path.read_text())
    manifest_path = root / "data/candidate-acquisition.json"
    manifest = json.loads(manifest_path.read_text())
    leads_path = root / "data/candidate-source-leads.json"
    leads = json.loads(leads_path.read_text())
    known = {(lead["candidate_id"], lead["url"]) for lead in leads}
    pending = [row for row in report["candidates"] if "public_directory_lookup" not in row]

    def lookup(candidate):
        slug = "-".join(words(candidate["name"]))
        url = f"https://www.ballotready.org/people/{slug}"
        result, sources = acquire_candidate({**candidate, "campaign_websites": [url]}, root)
        extracted = []
        for source in sources:
            if source.get("media_type") == "text/html":
                extracted.append(
                    {
                        "source_id": source["id"],
                        **directory_profile((root / source["path"]).read_bytes(), candidate),
                    }
                )
        return candidate, url, result, sources, extracted

    with ThreadPoolExecutor(max_workers=4) as pool:
        for index, (candidate, url, result, sources, extracted) in enumerate(
            pool.map(lookup, pending), 1
        ):
            merge_candidate_result(manifest, result, sources)
            candidate["public_directory_lookup"] = {
                "url": url,
                "attempts": result["attempts"],
                "extracted_profiles": extracted,
                "status": (
                    "identity_matched_fields_pending_review"
                    if any(row["fields"] for row in extracted)
                    else "no_qualified_fields_from_this_url"
                ),
            }
            if (candidate["candidate_id"], url) not in known:
                leads.append(
                    {
                        **{key: candidate[key] for key in CONTEXT},
                        "url": url,
                        "source_kind": "public_voter_directory_biography",
                        "qualification": "Full-name public profile URL lookup; identity review required.",
                    }
                )
                known.add((candidate["candidate_id"], url))
            if index % 20 == 0 or index == len(pending):
                write_json(path, report)
                write_json(manifest_path, manifest)
                write_json(leads_path, leads)
    return {"attempted_people": len(pending)}


def acquire_leads(root, additions):
    from .candidate_acquisition import acquire_candidate, merge_candidate_result

    root = Path(root)
    report = json.loads((root / PATH).read_text())
    people = {row["candidate_id"]: row for row in report["candidates"]}
    manifest_path = root / "data/candidate-acquisition.json"
    manifest = json.loads(manifest_path.read_text())
    leads_path = root / "data/candidate-source-leads.json"
    leads = json.loads(leads_path.read_text())
    known = {(row["candidate_id"], row["url"]) for row in leads}
    done = {
        (row["candidate_id"], attempt["url"])
        for row in manifest["candidates"]
        for attempt in row["attempts"]
    }
    work = []
    for candidate_id, urls in additions.items():
        candidate = people[candidate_id]
        for url in urls:
            if not url.startswith(("https://", "http://")):
                raise ValueError("A source lead must be a public HTTP URL")
            if (candidate_id, url) not in known:
                leads.append(
                    {
                        **{key: candidate[key] for key in CONTEXT},
                        "url": url,
                        "qualification": (
                            "Contextual search lead or explicit alias URL lookup; "
                            "requires downloaded-source identity and factual review."
                        ),
                    }
                )
                known.add((candidate_id, url))
            if (candidate_id, url) not in done:
                work.append({**candidate, "campaign_websites": [url]})
    write_json(leads_path, leads)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for candidate, sources in pool.map(lambda row: acquire_candidate(row, root), work):
            merge_candidate_result(manifest, candidate, sources)
            write_json(manifest_path, manifest)
    return {"attempted_candidate_urls": len(work)}


def acquire_directory_variants(root=ROOT):
    """Try name variants as leads; retain the same strict downloaded-page identity gate."""
    root = Path(root)
    report = json.loads((root / PATH).read_text())
    additions = {}
    for candidate in report["candidates"]:
        name = re.sub(r"\([^)]*\)|\"[^\"]*\"", "", candidate["name"])
        parts = [part for part in words(name) if part not in {"jr", "sr", "ii", "iii", "iv"}]
        if len(parts) < 2:
            continue
        slugs = {"-".join(parts), f"{parts[0]}-{parts[-1]}"}
        additions[candidate["candidate_id"]] = [
            f"https://www.ballotready.org/people/{slug}" for slug in sorted(slugs)
        ]
    result = acquire_leads(root, additions)
    acquisition = json.loads((root / "data/candidate-acquisition.json").read_text())
    sources = {row["id"]: row for row in acquisition["sources"]}
    people = {row["candidate_id"]: row for row in report["candidates"]}
    for candidate in acquisition["candidates"]:
        if candidate["candidate_id"] not in people:
            continue
        person = people[candidate["candidate_id"]]
        extracted = person["public_directory_lookup"]["extracted_profiles"]
        known = {row["source_id"] for row in extracted}
        for source_id in candidate["source_ids"]:
            source = sources[source_id]
            if (
                source_id in known
                or not source["url"].startswith("https://www.ballotready.org/people/")
                or source.get("media_type") != "text/html"
            ):
                continue
            raw = (root / source["path"]).read_bytes()
            if fingerprint(root / source["path"]) != {
                key: source[key] for key in ("bytes", "sha256")
            }:
                raise ValueError("Directory source changed before extraction")
            extracted.append({"source_id": source_id, **directory_profile(raw, person)})
    write_json(root / PATH, report)
    return result


def review_directory_snapshot(root, expected_sha256):
    """Promote a specifically reviewed, immutable extraction snapshot, not future downloads."""
    root = Path(root)
    path = root / PATH
    if fingerprint(path)["sha256"] != expected_sha256:
        raise ValueError("Directory extraction snapshot changed since factual review")
    report = json.loads(path.read_text())
    review_path = root / "data/candidate-reviewed-backgrounds.json"
    review = json.loads(review_path.read_text())
    seen = {(row["candidate_id"], row["source_id"]): row for row in review["profiles"]}
    held_education = {
        "220409": "Directory labels a bachelor's at South Suburban College; credential unresolved.",
        "220798": "Directory labels a bachelor's at Atlantic Cape Community College; unresolved.",
        "220723": "Directory labels a bachelor's at Moorpark College; credential unresolved.",
        "221344": "Directory labels a bachelor's at Mesa Community College; credential unresolved.",
        "220487": "West Point degree/completion claim requires primary-source corroboration.",
        "220134": "Harvard MBA credential claim requires primary-source corroboration.",
        "140485": "Tarrant County College bachelor's label requires corroboration.",
        "221232": "Oxford PPE master's label requires corroboration of actual qualification.",
    }
    added = 0
    for candidate in report["candidates"]:
        lookup = candidate.get("public_directory_lookup", {})
        for profile in lookup.get("extracted_profiles", []):
            if not profile["fields"]:
                continue
            if profile["identity_status"] != "name_and_2026_house_context_matched":
                raise ValueError("Directory source lacks qualified candidate and contest identity")
            key = (candidate["candidate_id"], profile["source_id"])
            if key in seen:
                profile["reviewed_fields"] = sorted(seen[key]["fields"])
                continue
            fields = {
                field: values
                for field, values in profile["fields"].items()
                if not candidate["baseline_has_observations"]
                or field in candidate["baseline_missing_fields"]
            }
            if candidate["candidate_id"] in held_education:
                fields.pop("education", None)
                profile["education_review_hold"] = held_education[candidate["candidate_id"]]
            for field, excluded in profile.get("review_excluded_values", {}).items():
                if not set(excluded) <= set(profile["fields"].get(field, [])):
                    raise ValueError("Review exclusion does not match the extracted source entries")
                if field in fields:
                    fields[field] = [value for value in fields[field] if value not in excluded]
                    if not fields[field]:
                        del fields[field]
            profile["reviewed_snapshot_sha256"] = expected_sha256
            profile["reviewed_fields"] = sorted(fields)
            if not fields or key in seen:
                continue
            review["profiles"].append(
                {
                    **{key: candidate[key] for key in CONTEXT},
                    "source_id": profile["source_id"],
                    "source_kind": "public_voter_directory_biography",
                    "fields": {
                        field: [f"Public directory reports: {value}" for value in values]
                        for field, values in fields.items()
                    },
                    "support": fields,
                    "model_ready": False,
                    "qualification": (
                        "Manually reviewed public BallotReady directory entries; name and "
                        "2026 state/district House candidacy matched. Party is the pinned "
                        "roster value, not independently established by this page. "
                        "Directory-reported credentials/employment, not independent verification "
                        "or proven candidate submissions. Institution-only education listings "
                        "do not establish attendance, degree type or graduation. Dates and "
                        "'Present' are directory claims, not verified election-day employment. "
                        "No prior elected office or military-service fields inferred from the "
                        "professional-experience heading. Retrospective/model-ineligible."
                    ),
                }
            )
            candidate["reviewed_source_ids"].append(profile["source_id"])
            seen[key] = review["profiles"][-1]
            added += 1
    report.setdefault("reviewed_directory_snapshots", []).append(expected_sha256)
    write_json(review_path, review)
    write_json(path, report)
    return {"new_reviewed_source_profiles": added}


def finalize_repair(root=ROOT):
    """Reconcile the repair queue against normalized facts, without pretending failed URLs suffice."""
    root = Path(root)
    path = root / PATH
    report = json.loads(path.read_text())
    baseline = json.loads((root / "data/candidate-discovery-baseline.json").read_text())
    if baseline["profile_fingerprint"] != report["baseline_profiles"]:
        raise ValueError("Repair accounting baseline conflicts with the frozen queue")
    old = {row["candidate_id"]: row for row in baseline["candidates"]}
    held = root / "results/house"
    manifest = json.loads((held / "manifest.json").read_text())
    for name in ("candidates.jsonl.gz", "background-observations.csv"):
        if fingerprint(held / name) != manifest["files"][name]:
            raise ValueError("Repair accounting requires unchanged normalized inputs")
    current = read_rows(held / "candidates.jsonl.gz")
    if len(current) != len(old) or {row["candidate_id"] for row in current} != old.keys():
        raise ValueError("Repair accounting must preserve the complete candidate denominator")
    observations = {}
    with (held / "background-observations.csv").open() as stream:
        for row in csv.DictReader(stream):
            observations.setdefault(row["candidate_id"], []).append(
                {
                    "field": row["field"],
                    "value": json.loads(row["value"]),
                    "evidence": json.loads(row["evidence"]) if row["evidence"] else {},
                }
            )
    profiles = {row["candidate_id"]: row for row in current}
    reviewed = {
        (row["candidate_id"], row["source_id"])
        for row in json.loads((root / "data/candidate-reviewed-backgrounds.json").read_text())[
            "profiles"
        ]
    }
    for candidate in report["candidates"]:
        cid = candidate["candidate_id"]
        if any(candidate[key] != profiles[cid][key] for key in CONTEXT):
            raise ValueError("Repair queue candidate context changed")
        records = observations.get(cid, [])
        coverage = background_field_coverage(records)
        candidate.update(coverage)
        candidate["newly_covered"] = not candidate["baseline_has_observations"] and bool(records)
        candidate["newly_filled_fields"] = sorted(
            set(old[cid]["remaining_background_fields"])
            - set(coverage["remaining_background_fields"])
        )
        candidate["reviewed_source_ids"] = sorted(
            {
                row["evidence"]["source_id"]
                for row in records
                if isinstance(row["evidence"], dict)
                and (cid, row["evidence"].get("source_id")) in reviewed
            }
        )
        if records:
            candidate["discovery_status"] = "sourced_observations_partial"
            candidate["disposition"] = (
                f"Has {len(records)} observations; this pass filled "
                f"{len(candidate['newly_filled_fields'])} previously missing fields. "
                f"Still unknown: {', '.join(coverage['remaining_background_fields']) or 'none of the four tracked categories'}. "
                "Field presence is not biographical completeness or independent verification."
            )
        elif candidate.get("research_disposition"):
            candidate["discovery_status"] = "reviewed_gap_documented"
            candidate["disposition"] = candidate["research_disposition"]
        elif any(attempt["relevant_results"] for attempt in candidate["attempts"]):
            candidate["discovery_status"] = "leads_pending_source_review"
            candidate["disposition"] = (
                "Contextual search leads await downloaded-source identity and factual review. "
                "No facts credited from lead titles or search-result snippets."
            )
        else:
            candidate["discovery_status"] = "retry_required"
            candidate["disposition"] = (
                f"No accepted biography for {candidate['name']} in "
                f"{candidate['state']}-{candidate['district']} ({candidate['party']}). "
                "Recorded full-name/alias public-directory requests failed identity/context "
                "qualification or supplied no reviewed target fields. Earlier irrelevant "
                "searches and failed guessed URLs are not adequate negative evidence. "
                "Further contextual discovery remains required; all four fields stay unknown."
            )
        identity_review = candidate.get("roster_identity_review")
        if identity_review:
            if (
                any(identity_review[key] != profiles[cid][key] for key in CONTEXT)
                or identity_review["native_source"] != profiles[cid].get("source")
                or identity_review["votes"] != profiles[cid].get("votes")
            ):
                raise ValueError("Write-in identity review conflicts with normalized roster")
            if not records:
                candidate["disposition"] += " " + identity_review["disposition"]
    present = {cid: background_field_coverage(observations.get(cid, [])) for cid in old}
    report["summary"] = {
        "baseline_candidates": len(old),
        "baseline_with_observations": sum(row["has_observations"] for row in old.values()),
        "current_with_observations": sum(bool(observations.get(cid)) for cid in old),
        "newly_covered_people": sum(row["newly_covered"] for row in report["candidates"]),
        "newly_filled_fields": {
            field: sum(
                field in old[cid]["remaining_background_fields"]
                and field not in present[cid]["remaining_background_fields"]
                for cid in old
            )
            for field in BACKGROUND_FIELDS
        },
        "remaining_fields": {
            field: sum(field in row["remaining_background_fields"] for row in present.values())
            for field in BACKGROUND_FIELDS
        },
        "baseline_covered_people_with_new_fields": sum(
            row["baseline_has_observations"] and bool(row["newly_filled_fields"])
            for row in report["candidates"]
        ),
        "baseline_covered_people_still_missing_target_fields": sum(
            row["baseline_has_observations"]
            and bool(set(row["baseline_missing_fields"]) & set(row["remaining_background_fields"]))
            for row in report["candidates"]
        ),
        "remaining_uncovered_people": sum(not observations.get(cid) for cid in old),
        "remaining_uncovered_by_party": {
            party: sum(
                row["party"] == party and not observations.get(row["candidate_id"])
                for row in current
            )
            for party in sorted({row["party"] for row in current})
        },
        "inadequate_discovery_still_requiring_retry": sum(
            row["discovery_status"] == "retry_required" for row in report["candidates"]
        ),
        "uncovered_records_with_roster_identity_holds": sum(
            not observations.get(row["candidate_id"]) and bool(row.get("roster_identity_review"))
            for row in report["candidates"]
        ),
        "qualification": (
            "Counts are normalized factual/source-reported observations, not downloaded pages. "
            "Unknown fields and inadequate discovery remain explicit. All new evidence is "
            "retrospective/model-ineligible; no claim of complete biographies."
        ),
    }
    write_json(path, report)
    return report["summary"]


def attach_repair(root, profiles):
    """Expose finalized repair decisions without confusing field gains with people."""
    path = Path(root) / PATH
    if not path.exists():
        return {}
    report = json.loads(path.read_text())
    decisions = {row["candidate_id"]: row for row in report["candidates"]}
    identities = {row["candidate_id"]: row for row in profiles}
    summary = report["summary"]
    if (
        len(decisions) != len(report["candidates"])
        or len(identities) != len(profiles)
        or not decisions.keys() <= identities.keys()
        or summary["baseline_candidates"] != len(profiles)
        or summary["current_with_observations"]
        != sum(bool(row["acquired_background_observations"]) for row in profiles)
        or summary["remaining_fields"]
        != {
            field: sum(
                field
                in background_field_coverage(row["acquired_background_observations"])[
                    "remaining_background_fields"
                ]
                for row in profiles
            )
            for field in BACKGROUND_FIELDS
        }
    ):
        raise ValueError("Discovery repair requires finalized, current coverage accounting")
    for cid, decision in decisions.items():
        profile = identities[cid]
        coverage = background_field_coverage(profile["acquired_background_observations"])
        if any(profile[key] != decision[key] for key in CONTEXT) or any(
            coverage[key] != decision[key] for key in coverage
        ):
            raise ValueError("Discovery repair conflicts with candidate identity or coverage")
        profile["background_discovery_repair"] = {
            key: decision[key]
            for key in (
                "baseline_has_observations",
                "baseline_missing_fields",
                "discovery_status",
                "disposition",
                "newly_covered",
                "newly_filled_fields",
                "reviewed_source_ids",
            )
        }
        if decision.get("gap_review"):
            profile["background_discovery_repair"]["gap_review"] = decision["gap_review"]
        if decision.get("roster_identity_review"):
            profile["background_discovery_repair"]["roster_identity_review"] = decision[
                "roster_identity_review"
            ]
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--acquire-directory", action="store_true")
    parser.add_argument("--acquire-directory-variants", action="store_true")
    parser.add_argument("--acquire-leads", type=Path)
    parser.add_argument("--review-directory-snapshot")
    parser.add_argument("--finalize", action="store_true")
    args = parser.parse_args()
    if args.finalize:
        result = finalize_repair(args.root)
    elif args.acquire_directory_variants:
        result = acquire_directory_variants(args.root)
    elif args.acquire_leads:
        result = acquire_leads(args.root, json.loads(args.acquire_leads.read_text()))
    elif args.review_directory_snapshot:
        result = review_directory_snapshot(args.root, args.review_directory_snapshot)
    else:
        result = acquire_directory(args.root) if args.acquire_directory else audit(args.root)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
