"""Validate and ingest reviewed Democratic background research proposals."""

import argparse
import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

from .candidate_acquisition import merge_candidate_result
from .candidate_discovery import capture_extraction, record_gap_review, record_search
from .incoming_biographies import visible_text
from .rebuild import ROOT
from .reviewed_backgrounds import (
    CONTEXT,
    KINDS,
    normalized,
    validated_field_reviews,
)
from .storage import fingerprint, write_json

PROPOSALS = (
    "artifacts/democratic-background-research/professional-proposals.json",
    "artifacts/democratic-background-research/education-a-proposals.json",
    "artifacts/democratic-background-research/education-parent-proposals.json",
)
RESEARCH_PATH = "data/democratic-background-research.json"
BASELINE_PATH = "data/democratic-background-gap-baseline.json"
CACHE = "data/raw/candidate-backgrounds-20261115"


def allowed_source_kind(value):
    if value in KINDS:
        return value
    if value == "official campaign biography":
        return "candidate_campaign_self_report"
    raise ValueError(f"Unsupported proposal source_kind: {value!r}")


def _fragments(value):
    values = [value] if isinstance(value, str) else value
    if not isinstance(values, list) or not values:
        raise ValueError("Support and identity anchors must be nonempty strings")
    if not all(isinstance(item, str) and normalized(item) for item in values):
        raise ValueError("Support and identity anchors must be nonempty strings")
    return values


def _proposal_paths(root, proposal_paths):
    paths = [root / name for name in (proposal_paths or PROPOSALS)]
    missing = [str(path.relative_to(root)) for path in paths if not path.exists()]
    if missing:
        raise ValueError("Missing proposal files: " + ", ".join(missing))
    return paths


def _actual_source(root, proposal_path, source):
    value = source.get("local_path") or source.get("text_or_local_path")
    local = None
    if isinstance(value, str) and "\n" not in value and len(value) < 1024:
        candidates = (root / value, proposal_path.parent / value)
        for path in candidates:
            try:
                if path.is_file():
                    local = path
                    break
            except OSError:
                continue
    extraction = source.get("provider_extraction") or source.get("extraction_text")
    if local is not None:
        body = local.read_bytes()
        media_type = source.get("media_type") or (
            "application/pdf"
            if local.suffix.casefold() == ".pdf" or body.startswith(b"%PDF")
            else "text/html"
            if local.suffix.casefold() in {".html", ".htm"}
            else "text/plain"
        )
        if media_type == "text/plain" and source.get("retrieval_method") in {
            "public_search_provider_page_extraction",
            "public_search_provider_result_excerpt",
            "public_web_fetch_page_extraction",
        }:
            return {
                "mode": "provider_extraction",
                "body": body,
                "media_type": media_type,
                "local_path": local,
            }
        return {
            "mode": "held_original",
            "body": body,
            "media_type": media_type,
            "local_path": local,
        }
    if isinstance(extraction, str) and extraction.strip():
        method = source.get("retrieval_method")
        if method not in {
            "public_search_provider_page_extraction",
            "public_search_provider_result_excerpt",
            "public_web_fetch_page_extraction",
        }:
            raise ValueError("Provider extraction requires an actual supported retrieval_method")
        return {
            "mode": "provider_extraction",
            "body": extraction.encode(),
            "media_type": "text/plain",
        }
    raise ValueError(
        "Source requires a held local original or provider_extraction; proposal paraphrases "
        "cannot become evidence"
    )


def _source_text(actual, source):
    body = actual["body"]
    pages = source.get("pdf_pages")
    if actual["media_type"] == "application/pdf":
        reader = PdfReader(BytesIO(body))
        if (
            not isinstance(pages, list)
            or not pages
            or not all(type(page) is int and 1 <= page <= len(reader.pages) for page in pages)
        ):
            raise ValueError("PDF proposal source requires explicit one-based pdf_pages")
        return normalized(" ".join(reader.pages[page - 1].extract_text() or "" for page in pages))
    if pages is not None:
        raise ValueError("pdf_pages are only valid for PDF proposal sources")
    if actual["media_type"] == "text/html":
        return normalized(visible_text(body))
    return normalized(body.decode("utf-8", "replace"))


def _normalized_searches(candidate):
    searches = []
    for search in candidate.get("searches", []):
        if not search.get("query") or not search.get("provider"):
            raise ValueError("Every proposed search requires query and provider")
        results = []
        for result in search.get("results", []):
            result = deepcopy(result)
            status = str(
                result.get("status")
                or result.get("status/rejection_reason")
                or result.get("rejection_reason")
                or ""
            ).casefold()
            if result.get("rejection_reason") or "reject" in status or "namesake" in status:
                result["identity_review"] = "rejected"
            results.append(result)
        searches.append(
            {
                "query": search["query"],
                "provider": search["provider"],
                "provider_reference": search.get("provider_reference"),
                "results": results,
            }
        )
    return searches


def validate(root=ROOT, proposal_paths=None):
    root = Path(root)
    baseline_path = root / BASELINE_PATH
    baseline = json.loads(baseline_path.read_text())
    allowed = {row["candidate_id"]: row for row in baseline["candidates"]}
    paths = _proposal_paths(root, proposal_paths)
    plans, seen = [], set()
    for proposal_path in paths:
        proposal = json.loads(proposal_path.read_text())
        for candidate in proposal.get("candidates", []):
            cid = candidate.get("candidate_id")
            baseline_candidate = allowed.get(cid)
            if baseline_candidate is None:
                raise ValueError(f"Proposal candidate is outside the pinned gap baseline: {cid}")
            if any(candidate.get(key) != baseline_candidate[key] for key in CONTEXT):
                raise ValueError(f"Proposal identity conflicts with pinned baseline: {cid}")
            if candidate.get("target_fields") != baseline_candidate["target_fields"]:
                raise ValueError(f"Proposal target fields conflict with pinned baseline: {cid}")
            key = tuple(candidate[key] for key in CONTEXT)
            if key in seen:
                raise ValueError(f"Candidate appears in more than one proposal file: {cid}")
            seen.add(key)
            sources = []
            for source_number, source in enumerate(candidate.get("sources", []), 1):
                if not str(source.get("url", "")).startswith(("https://", "http://")):
                    raise ValueError(f"Proposal source requires a public URL for {cid}")
                if not source.get("retrieved_at"):
                    raise ValueError(f"Proposal source requires retrieved_at for {cid}")
                source_kind = allowed_source_kind(source.get("source_kind"))
                fields = {
                    field: values
                    for field, values in (source.get("fields") or {}).items()
                    if values
                }
                if set(fields) - set(candidate["target_fields"]):
                    raise ValueError(f"Source proposes a non-target field for {cid}")
                if any(
                    not isinstance(values, list)
                    or not values
                    or not all(isinstance(value, str) and value.strip() for value in values)
                    for values in fields.values()
                ):
                    raise ValueError(f"Proposed fields require nonempty value lists for {cid}")
                if set(source.get("support", {})) != set(fields):
                    raise ValueError(f"Every proposed field requires matching support for {cid}")
                actual = _actual_source(root, proposal_path, source)
                if actual["mode"] == "provider_extraction" and not source.get("provider_reference"):
                    raise ValueError(f"Provider extraction requires provider_reference for {cid}")
                text = _source_text(actual, source)
                anchors = _fragments(source.get("identity_support"))
                missing_anchors = [
                    fragment for fragment in anchors if normalized(fragment) not in text
                ]
                if missing_anchors:
                    raise ValueError(
                        f"Identity anchor absent from actual held source for {cid}, "
                        f"{source['url']}: {missing_anchors}"
                    )
                support = {
                    field: _fragments(fragments)
                    for field, fragments in source.get("support", {}).items()
                }
                missing_support = [
                    fragment
                    for fragments in support.values()
                    for fragment in fragments
                    if normalized(fragment) not in text
                ]
                if missing_support:
                    raise ValueError(
                        f"Field support absent from actual held source for {cid}, "
                        f"{source['url']}: {missing_support}"
                    )
                field_reviews = validated_field_reviews(fields, source.get("field_reviews"))
                gap = source.get("gap_review")
                if source.get("gap_support") is not None:
                    gap = {
                        "disposition": source.get("qualification"),
                        "support": source["gap_support"],
                    }
                if gap:
                    if fields:
                        raise ValueError("Gap review must use an identity-only source")
                    if not isinstance(gap, dict) or not str(gap.get("disposition", "")).strip():
                        raise ValueError(f"Gap review requires a disposition for {cid}")
                    gap_support = _fragments(gap.get("support"))
                    missing_gap = [
                        fragment for fragment in gap_support if normalized(fragment) not in text
                    ]
                    if missing_gap:
                        raise ValueError(
                            f"Gap review support absent from actual held source for {cid}, "
                            f"{source['url']}: {missing_gap}"
                        )
                sources.append(
                    {
                        "proposal_source_number": source_number,
                        "source": source,
                        "source_kind": source_kind,
                        "fields": fields,
                        "support": support,
                        "field_reviews": field_reviews,
                        "actual": actual,
                    }
                )
            plans.append(
                {
                    "proposal_path": proposal_path,
                    "candidate": candidate,
                    "searches": _normalized_searches(candidate),
                    "sources": sources,
                }
            )
    missing = set(allowed) - {plan["candidate"]["candidate_id"] for plan in plans}
    if missing:
        raise ValueError(f"Research proposals omit pinned candidates: {sorted(missing)}")
    return {
        "schema": "which_candidate.democratic_research_validation.v1",
        "baseline": fingerprint(baseline_path),
        "proposal_files": {path.relative_to(root).as_posix(): fingerprint(path) for path in paths},
        "candidate_count": len(plans),
        "source_count": sum(len(plan["sources"]) for plan in plans),
        "field_source_count": sum(
            bool(source["fields"]) for plan in plans for source in plan["sources"]
        ),
        "identity_only_source_count": sum(
            not source["fields"] for plan in plans for source in plan["sources"]
        ),
        "plans": plans,
    }


def _pin_source(root, candidate, plan):
    source, actual = plan["source"], plan["actual"]
    digest = hashlib.sha256(actual["body"]).hexdigest()
    prefix = "candidate-extraction" if actual["mode"] == "provider_extraction" else "candidate-bio"
    expected_id = f"{prefix}-{candidate['candidate_id']}-{digest[:20]}"
    manifest_path = root / "data/candidate-acquisition.json"
    manifest = json.loads(manifest_path.read_text())
    existing = next((row for row in manifest["sources"] if row["id"] == expected_id), None)
    if existing is not None:
        owner = next(
            (
                row
                for row in manifest["candidates"]
                if row["candidate_id"] == candidate["candidate_id"]
            ),
            None,
        )
        if owner is None or expected_id not in owner["source_ids"]:
            raise ValueError(f"Existing source receipt has no matching owner: {expected_id}")
        held = root / existing["path"]
        if not held.exists():
            held.parent.mkdir(parents=True, exist_ok=True)
            held.write_bytes(actual["body"])
        if fingerprint(held) != {key: existing[key] for key in ("bytes", "sha256")}:
            raise ValueError(f"Existing held source changed: {expected_id}")
        return expected_id
    if actual["mode"] == "provider_extraction":
        method = source["retrieval_method"]
        provider = "web_fetch" if method == "public_web_fetch_page_extraction" else "search"
        return capture_extraction(
            root,
            candidate,
            url=source["url"],
            text=actual["body"].decode(),
            provider_reference=source["provider_reference"],
            source_kind=plan["source_kind"],
            search_preview=method == "public_search_provider_result_excerpt",
            provider=provider,
            source_observed_at=source["retrieved_at"],
        )
    body = actual["body"]
    suffix = (
        ".pdf"
        if actual["media_type"] == "application/pdf"
        else (".html" if actual["media_type"] == "text/html" else ".txt")
    )
    relative = f"{CACHE}/{candidate['candidate_id']}-{digest[:20]}{suffix}"
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(body)
    source_id = f"candidate-bio-{candidate['candidate_id']}-{digest[:20]}"
    receipt = {
        "id": source_id,
        "url": source["url"],
        "resolved_url": source.get("resolved_url", source["url"]),
        "retrieved_at": source["retrieved_at"],
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "publication_date": source.get("publication_date"),
        "path": relative,
        **fingerprint(target),
        "source_kind": "downloaded_public_webpage",
        "media_type": actual["media_type"],
        "retrieval_method": "copied_held_public_original",
        "provider_reference": source.get("provider_reference"),
        "qualification": (
            "Exact held public-source bytes copied into the normalized research cache; "
            "retrospective and model-ineligible."
        ),
    }
    merge_candidate_result(
        manifest,
        {
            **{key: candidate[key] for key in CONTEXT},
            "source_ids": [source_id],
            "attempts": [
                {
                    "url": source["url"],
                    "retrieved_at": source["retrieved_at"],
                    "status": "acquired_not_yet_reviewed",
                    "source_id": source_id,
                    "retrieval_method": receipt["retrieval_method"],
                }
            ],
            "facts_reviewed": False,
            "counted_as_background_coverage": False,
        },
        [receipt],
    )
    write_json(manifest_path, manifest)
    return source_id


def _merge_annotation(review, candidate, source_id, plan):
    existing = next(
        (
            row
            for row in review["profiles"]
            if row["candidate_id"] == candidate["candidate_id"] and row["source_id"] == source_id
        ),
        None,
    )
    annotation = existing or {
        **{key: candidate[key] for key in CONTEXT},
        "source_id": source_id,
        "fields": {},
        "support": {},
        "model_ready": False,
    }
    if any(annotation.get(key, candidate[key]) != candidate[key] for key in CONTEXT):
        raise ValueError(f"Existing reviewed annotation conflicts with proposal: {source_id}")
    for field, values in plan["fields"].items():
        annotation["fields"][field] = list(
            dict.fromkeys([*annotation["fields"].get(field, []), *values])
        )
        old = annotation["support"].get(field, [])
        old = [old] if isinstance(old, str) else old
        annotation["support"][field] = list(dict.fromkeys([*old, *plan["support"][field]]))
    annotation.setdefault("field_reviews", {}).update(plan["field_reviews"])
    qualification = plan["source"].get("qualification", {})
    if not isinstance(qualification, str):
        qualification = json.dumps(qualification, sort_keys=True, ensure_ascii=True)
    previous_qualification = annotation.get("qualification")
    if previous_qualification:
        qualification = (
            previous_qualification
            if qualification in previous_qualification
            else f"{previous_qualification}\nAdditional review qualification: {qualification}"
        )
    annotation.update(
        {
            **{key: candidate[key] for key in CONTEXT},
            "source_kind": plan["source_kind"],
            "qualification": qualification,
            "model_ready": False,
        }
    )
    if plan["source"].get("pdf_pages") is not None:
        annotation["pdf_pages"] = plan["source"]["pdf_pages"]
    if not existing:
        review["profiles"].append(annotation)


def _accounting(root):
    acquisition = json.loads((root / "data/candidate-acquisition.json").read_text())
    reviewed = json.loads((root / "data/candidate-reviewed-backgrounds.json").read_text())
    discovery = json.loads((root / "data/candidate-discovery-repair.json").read_text())
    return {
        "acquisition_sources": len({row["id"] for row in acquisition["sources"]}),
        "reviewed_candidate_sources": len(
            {(row["candidate_id"], row["source_id"]) for row in reviewed["profiles"]}
        ),
        "reviewed_candidate_fields": len(
            {
                (row["candidate_id"], field)
                for row in reviewed["profiles"]
                for field in row["fields"]
            }
        ),
        "discovery_search_attempts": sum(
            len(row.get("attempts", [])) for row in discovery["candidates"]
        ),
    }


def _merge_research_candidate(existing, current):
    if existing is None:
        return current
    if any(existing[key] != current[key] for key in CONTEXT):
        raise ValueError(
            f"Existing Democratic research registry conflicts with identity: "
            f"{current['candidate_id']}"
        )

    def unique(rows):
        found = {}
        for row in rows:
            found[json.dumps(row, sort_keys=True, ensure_ascii=True)] = row
        return list(found.values())

    return {
        **existing,
        **{key: current[key] for key in (*CONTEXT, "target_fields")},
        "searches": unique([*existing.get("searches", []), *current["searches"]]),
        "rejected_matches": unique(
            [*existing.get("rejected_matches", []), *current["rejected_matches"]]
        ),
        "sources": list(
            {
                row["source_id"]: row for row in [*existing.get("sources", []), *current["sources"]]
            }.values()
        ),
        "remaining_fields": current["remaining_fields"],
        "limitations": unique([*existing.get("limitations", []), *current["limitations"]]),
        "retrieval_attempts": unique(
            [*existing.get("retrieval_attempts", []), *current.get("retrieval_attempts", [])]
        ),
    }


def ingest(root=ROOT, proposal_paths=None, *, validate_only=True):
    root = Path(root)
    validation = validate(root, proposal_paths)
    public = {key: value for key, value in validation.items() if key != "plans"}
    if validate_only:
        return {**public, "status": "validated_no_changes"}
    before = _accounting(root)
    review_path = root / "data/candidate-reviewed-backgrounds.json"
    review = json.loads(review_path.read_text())
    research_candidates = []
    for plan in validation["plans"]:
        candidate = plan["candidate"]
        repair = json.loads((root / "data/candidate-discovery-repair.json").read_text())
        decision = next(
            (
                row
                for row in repair["candidates"]
                if row["candidate_id"] == candidate["candidate_id"]
            ),
            None,
        )
        if decision is None or any(decision[key] != candidate[key] for key in CONTEXT):
            raise ValueError(
                f"Discovery registry lacks exact proposal identity: {candidate['candidate_id']}"
            )
        recorded_searches = []
        for search in plan["searches"]:
            duplicate = any(
                attempt.get("query") == search["query"]
                and attempt.get("provider") == search["provider"]
                and attempt.get("receipt") == search["provider_reference"]
                for attempt in decision.get("attempts", [])
            )
            if not duplicate:
                record_search(
                    root,
                    candidate["candidate_id"],
                    query=search["query"],
                    provider=search["provider"],
                    results=search["results"],
                    receipt=search["provider_reference"],
                )
            recorded_searches.append(search)
        source_records = []
        for source_plan in plan["sources"]:
            source_id = _pin_source(root, candidate, source_plan)
            if source_plan["fields"]:
                _merge_annotation(review, candidate, source_id, source_plan)
            gap = source_plan["source"].get("gap_review")
            if source_plan["source"].get("gap_support") is not None:
                gap = {
                    "disposition": source_plan["source"].get("qualification"),
                    "support": source_plan["source"]["gap_support"],
                }
            if gap:
                if source_plan["fields"]:
                    raise ValueError("Gap review must use an identity-only source")
                record_gap_review(
                    root,
                    candidate["candidate_id"],
                    disposition=gap["disposition"],
                    source_support={
                        source_id: {
                            "support": _fragments(gap["support"]),
                            **(
                                {"pdf_pages": source_plan["source"]["pdf_pages"]}
                                if source_plan["actual"]["media_type"] == "application/pdf"
                                else {}
                            ),
                        }
                    },
                )
            source_records.append(
                {
                    "source_id": source_id,
                    "url": source_plan["source"]["url"],
                    "source_kind": source_plan["source_kind"],
                    "fields": sorted(source_plan["fields"]),
                    "field_reviews": source_plan["field_reviews"],
                    "identity_only": not bool(source_plan["fields"]),
                    "qualification": source_plan["source"].get("qualification"),
                    "provider_reference": source_plan["source"].get("provider_reference"),
                    "retrieval_method": source_plan["source"].get("retrieval_method"),
                }
            )
        research_candidates.append(
            {
                **{key: candidate[key] for key in CONTEXT},
                "target_fields": candidate["target_fields"],
                "searches": recorded_searches,
                "rejected_matches": candidate.get("rejected_matches", []),
                "sources": source_records,
                "remaining_fields": sorted(
                    set(candidate["target_fields"])
                    - {field for source in plan["sources"] for field in source["fields"]}
                ),
                "limitations": candidate.get("limitations", []),
                "retrieval_attempts": candidate.get("retrieval_attempts", []),
            }
        )
    review["profiles"].sort(key=lambda row: (row["candidate_id"], row["source_id"]))
    write_json(review_path, review)
    leads_path = root / "data/candidate-source-leads.json"
    leads = json.loads(leads_path.read_text()) if leads_path.exists() else []
    known_leads = {(row["candidate_id"], row["url"]) for row in leads}
    for candidate in research_candidates:
        for source in candidate["sources"]:
            key = (candidate["candidate_id"], source["url"])
            if key not in known_leads:
                leads.append(
                    {
                        **{key: candidate[key] for key in CONTEXT},
                        "url": source["url"],
                        "source_kind": source["source_kind"],
                        "identity_only": source["identity_only"],
                        "research_registry": RESEARCH_PATH,
                    }
                )
                known_leads.add(key)
    write_json(leads_path, leads)
    after = _accounting(root)
    registry_path = root / RESEARCH_PATH
    previous = json.loads(registry_path.read_text()) if registry_path.exists() else {}
    existing_candidates = {row["candidate_id"]: row for row in previous.get("candidates", [])}
    for candidate in research_candidates:
        existing_candidates[candidate["candidate_id"]] = _merge_research_candidate(
            existing_candidates.get(candidate["candidate_id"]), candidate
        )
    run = {
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "proposal_files": public["proposal_files"],
        "accounting": {
            "before": before,
            "after": after,
            "unique_change": {key: after[key] - before[key] for key in before},
        },
    }
    registry = {
        **previous,
        "schema": "which_candidate.democratic_research.v1",
        "updated_at": run["ingested_at"],
        **public,
        "qualification": (
            "Research receipts and reviewed held sources. Search results are leads, manually "
            "rejected identities remain rejected, proposal paraphrases are not evidence, and "
            "all accepted fields remain retrospective/model-ineligible."
        ),
        "accounting": {
            "before": previous.get("accounting", {}).get("before", before),
            "after": after,
            "unique_change": {
                key: after[key] - previous.get("accounting", {}).get("before", before)[key]
                for key in before
            },
        },
        "runs": [*previous.get("runs", []), run],
        "candidates": sorted(existing_candidates.values(), key=lambda row: row["candidate_id"]),
    }
    write_json(registry_path, registry)
    return {**public, "status": "ingested", "accounting": run["accounting"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--proposals", type=Path, action="append")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--validate-only", action="store_true")
    mode.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(ingest(args.root, args.proposals, validate_only=not args.apply), indent=2))
