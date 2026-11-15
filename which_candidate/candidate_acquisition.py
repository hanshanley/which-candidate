"""Acquire missing candidates' public campaign biographies without promoting facts."""

import argparse
import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

from .incoming_biographies import visible_text
from .rebuild import ROOT
from .storage import read_rows, write_json


class BiographyLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.current = [dict(attrs).get("href", ""), []]

    def handle_data(self, data):
        if self.current is not None:
            self.current[1].append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.current is not None:
            self.links.append((self.current[0], " ".join(self.current[1])))
            self.current = None


def biography_links(raw, base):
    parser = BiographyLinks()
    parser.feed(raw.decode("utf-8", "replace"))
    hostname = urllib.parse.urlsplit(base).hostname
    if not hostname:
        return []
    host = hostname.removeprefix("www.")
    found = []
    for href, label in parser.links:
        url = urllib.parse.urljoin(base, href).split("#", 1)[0]
        parts = urllib.parse.urlsplit(url)
        if parts.scheme not in ("http", "https") or not parts.hostname:
            continue
        if parts.hostname.removeprefix("www.") != host:
            continue
        text = f"{parts.path} {label}".casefold()
        if (
            re.search(r"\b(?:about|meet|biography|bio)\b", text)
            and not re.search(r"\b(?:privacy|terms|donate|news|press|issues)\b", text)
            and url.rstrip("/") != base.rstrip("/")
            and url not in found
        ):
            found.append(url)
    return found[:2]


def acquire_candidate(candidate, root):
    originals = Path(root) / "data/raw/candidate-backgrounds-20261115"
    originals.mkdir(parents=True, exist_ok=True)
    sources, attempts = [], []
    queue = list(dict.fromkeys(candidate["campaign_websites"]))[:1]
    while queue and len(attempts) < 3:
        url = queue.pop(0)
        retrieved = datetime.now(timezone.utc).isoformat()
        attempt = {"url": url, "retrieved_at": retrieved}
        try:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "WhichCandidateResearch/1.0 (candidate biography research)"},
            )
            with urllib.request.urlopen(request, timeout=20) as response:
                body = response.read(8 * 1024 * 1024 + 1)
                resolved, status = response.url, response.status
                content_type = response.headers.get("Content-Type", "")
            attempt.update(http_status=status, resolved_url=resolved)
            if status != 200 or not body or len(body) > 8 * 1024 * 1024:
                attempt["status"] = "empty_or_unsupported_response"
            elif "html" not in content_type.casefold():
                attempt["status"] = "non_html_response"
            elif any(
                marker in visible_text(body)[:1500].casefold()
                for marker in ("verify you are human", "access denied", "just a moment...")
            ):
                attempt["status"] = "access_challenge_not_bypassed"
            else:
                digest = hashlib.sha256(body).hexdigest()
                filename = f"{candidate['candidate_id']}-{digest[:20]}.html"
                path = originals / filename
                path.write_bytes(body)
                source_id = f"candidate-bio-{candidate['candidate_id']}-{digest[:20]}"
                sources.append(
                    {
                        "id": source_id,
                        "url": url,
                        "resolved_url": resolved,
                        "path": str(path.relative_to(root)),
                        "retrieved_at": retrieved,
                        "publication_date": None,
                        "bytes": len(body),
                        "sha256": digest,
                        "source_kind": "downloaded_public_webpage",
                        "qualification": "retrieved_after_election; publication_date_unverified",
                    }
                )
                attempt.update(status="acquired_not_yet_reviewed", source_id=source_id)
                if len(attempts) == 0:
                    queue.extend(biography_links(body, resolved))
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as error:
            attempt.update(status="retrieval_failed", error=str(error))
        attempts.append(attempt)
    return {
        **{
            key: candidate[key]
            for key in ("candidate_id", "contest_id", "name", "state", "district", "party")
        },
        "attempts": attempts,
        "source_ids": sorted({source["id"] for source in sources}),
        "facts_reviewed": False,
        "counted_as_background_coverage": False,
    }, sources


def merge_receipts(rows):
    by_id = {}
    for row in rows:
        held = by_id.get(row["id"])
        if held is None:
            by_id[row["id"]] = dict(row)
            continue
        if any(held[key] != row[key] for key in ("bytes", "sha256", "path")):
            raise ValueError("Conflicting original bytes for an acquisition source")
        retrievals = held.setdefault(
            "retrievals",
            [{key: held[key] for key in ("url", "resolved_url", "retrieved_at")}],
        )
        for retrieval in row.get(
            "retrievals", [{key: row[key] for key in ("url", "resolved_url", "retrieved_at")}]
        ):
            if retrieval not in retrievals:
                retrievals.append(retrieval)
    return sorted(by_id.values(), key=lambda row: row["id"])


def acquire(root=ROOT):
    root = Path(root)
    path = root / "data/candidate-acquisition.json"
    manifest = (
        json.loads(path.read_text())
        if path.exists()
        else {
            "scope": "Missing candidate campaign biographies; downloads alone are not coverage",
            "candidates": [],
            "sources": [],
        }
    )
    manifest["sources"] = merge_receipts(manifest["sources"])
    for candidate in manifest["candidates"]:
        candidate["source_ids"] = sorted(set(candidate["source_ids"]))
    done = {
        (row["candidate_id"], attempt["url"])
        for row in manifest["candidates"]
        for attempt in row["attempts"]
    }
    profiles = read_rows(root / "results/house-study/candidate-profiles.jsonl.gz")
    candidates = [
        row
        for row in profiles
        if not row["acquired_background_observations"]
        and row["campaign_websites"]
        and (row["candidate_id"], row["campaign_websites"][0]) not in done
    ]
    leads_path = root / "data/candidate-source-leads.json"
    if leads_path.exists():
        by_id = {row["candidate_id"]: row for row in profiles}
        for lead in json.loads(leads_path.read_text()):
            row = by_id[lead["candidate_id"]]
            if lead["name"] != row["name"]:
                raise ValueError("Candidate source lead has conflicting subject")
            if (row["candidate_id"], lead["url"]) not in done:
                candidates.append({**row, "campaign_websites": [lead["url"]]})
    with ThreadPoolExecutor(max_workers=6) as pool:
        pending = {pool.submit(acquire_candidate, row, root): row for row in candidates}
        for future in as_completed(pending):
            candidate, sources = future.result()
            existing = next(
                (
                    row
                    for row in manifest["candidates"]
                    if row["candidate_id"] == candidate["candidate_id"]
                ),
                None,
            )
            if existing is None:
                manifest["candidates"].append(candidate)
            else:
                existing["attempts"].extend(candidate["attempts"])
                existing["source_ids"] = sorted(
                    set(existing["source_ids"]) | set(candidate["source_ids"])
                )
            manifest["sources"] = merge_receipts([*manifest["sources"], *sources])
            manifest["candidates"].sort(key=lambda row: row["candidate_id"])
            manifest["sources"].sort(key=lambda row: row["id"])
            write_json(path, manifest)
            print(candidate["name"], len(sources), "sources", flush=True)
    write_json(path, manifest)
    return {
        "attempted_candidates": len(manifest["candidates"]),
        "sources": len(manifest["sources"]),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(acquire(args.root), indent=2))
