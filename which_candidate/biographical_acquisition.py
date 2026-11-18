"""Resumable native campaign discovery; retrieval never completes person research."""

import argparse
import hashlib
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from urllib.parse import urldefrag, urlsplit

from .biographical_research import RESULTS, load_json
from .characteristics_research import source_text
from .characteristics_v8_campaigns import biography_urls
from .storage import confined, fingerprint, read_rows, write_json

JOURNAL = "data/biographical-retrievals.json"
CACHE = "artifacts/biographical-research/sources"
MARKERS = {
    "age": r"\bborn\b|\bage\s+\d+|\b\d{2}-year-old\b",
    "gender": r"\bwoman\b|\bman\b|\bnon.?binary\b|\btransgender\b",
    "race": r"\bblack\b|\bwhite\b|\basian\b|\bafrican.american\b|\bindigenous\b",
    "ethnicity": r"\blatin[oaex]\b|\bhispanic\b",
    "religion": r"\bchurch\b|\bchristian\b|\bjewish\b|\bmuslim\b|\batheist\b|\bfaith\b",
    "education": r"\bdegree\b|\bgraduat|\buniversity\b|\bcollege\b",
    "profession": r"\bcareer\b|\bworked\b|\bwork as\b|\bprofession|\bengineer\b",
    "prior_elected_office": r"\belected\b|\bmayor\b|\bcouncil\b|\brepresentative\b",
    "other_government": r"\bfederal\b|\bgovernment\b|\bcivil servant\b|\bagency\b",
    "military": r"\bmilitary\b|\bveteran\b|\barmy\b|\bnavy\b|\bair force\b|\bmarine\b",
}


def canonical_url(url):
    return urldefrag(url.strip())[0].rstrip("/")


def source_records(value):
    if isinstance(value, dict):
        if isinstance(value.get("url"), str) and (
            "retrieved_at" in value or "retrieval_method" in value or "sha256" in value
        ):
            yield value
        for item in value.values():
            yield from source_records(item)
    elif isinstance(value, list):
        for item in value:
            yield from source_records(item)


def prior_index(root):
    root = Path(root)
    paths = sorted((root / "data").glob("house-characteristics*.json"))
    paths += sorted((root / "artifacts").glob("characteristics-*/**/retrievals.json"))
    index = {}
    for path in paths:
        for record in source_records(load_json(path, {})):
            candidates = []
            if record.get("cache_path"):
                candidate = Path(record["cache_path"])
                if not candidate.is_absolute():
                    candidate = root / candidate
                if candidate.resolve().is_relative_to(root.resolve()):
                    candidates.append(candidate)
            for key in ("id", "document_id"):
                if record.get(key) and Path(str(record[key])).name == str(record[key]):
                    candidates.extend(
                        (
                            path.parent / str(record[key]),
                            root / "data/raw/house-characteristics-v1" / str(record[key]),
                        )
                    )
            cached = next(
                (
                    p
                    for p in candidates
                    if p.is_file() and record.get("sha256") == fingerprint(p)["sha256"]
                ),
                None,
            )
            status = record.get("status", "")
            attempt = None
            if cached:
                attempt = {
                    **record,
                    "status": "retained_original",
                    "cache_path": cached.relative_to(root).as_posix(),
                    "network_attempts": 0,
                }
            elif status in {"failed", "blocked", "access_failure"} or status.startswith("failed_"):
                attempt = {
                    **record,
                    "status": "retained_access_failure",
                    "network_attempts": 0,
                }
            if attempt:
                for url in (record["url"], record.get("resolved_url", "")):
                    if url and (
                        canonical_url(url) not in index or attempt["status"] == "retained_original"
                    ):
                        index[canonical_url(url)] = attempt
    return index


def fetch(root, url):
    key = hashlib.sha256(url.encode()).hexdigest()[:24]
    directory = root / CACHE
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / key
    result = subprocess.run(
        [
            "curl",
            "--silent",
            "--show-error",
            "--location",
            "--max-redirs",
            "5",
            "--proto",
            "=http,https",
            "--proto-redir",
            "=http,https",
            "--connect-timeout",
            "10",
            "--max-time",
            "35",
            "--retry",
            "0",
            "--output",
            str(target),
            "--write-out",
            "%{http_code}\n%{url_effective}",
            url,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    info = result.stdout.splitlines()
    status = int(info[0]) if info and info[0].isdigit() else 0
    record = {
        "url": url,
        "resolved_url": info[-1] if len(info) > 1 else url,
        "http_status": status,
        "network_attempts": 1,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "retrieval_method": "curl_TLS_verified_one_attempt",
    }
    if result.returncode or status >= 400 or not target.exists():
        record.update(
            status="access_failure",
            error=result.stderr.strip()[:500],
            original_bytes_acquired=False,
        )
        if target.exists():
            target.unlink()
    else:
        record.update(
            status="acquired",
            cache_path=target.relative_to(root).as_posix(),
            original_bytes_acquired=True,
            **fingerprint(target),
        )
    return record


def run(root, limit=None, workers=4):
    root = Path(root).resolve()
    candidates = read_rows(root / "results/house/candidates.jsonl.gz")
    traits = read_rows(root / "results/house-characteristics-v9/candidate-traits.jsonl.gz")
    unknown = {}
    incumbency = {}
    for row in traits:
        if row["trait"] in MARKERS and not row["factual_qualified"]:
            unknown[row["candidate_id"]] = unknown.get(row["candidate_id"], 0) + 1
        elif row["trait"] == "incumbency":
            incumbency[row["candidate_id"]] = row["incumbency_group_v9"]
    candidates.sort(
        key=lambda c: (
            c["party"] != "Democratic",
            incumbency[c["candidate_id"]] == "incumbent",
            -unknown.get(c["candidate_id"], 0),
            c["state"],
            c["name"],
        )
    )
    if limit is not None:
        candidates = candidates[:limit]
    state = load_json(root / JOURNAL, {"sources": {}, "candidates": {}})
    previous = prior_index(root)
    lock = Lock()
    host_locks = {}
    blocked_hosts = set()

    def retrieve(url):
        url = canonical_url(url)
        parts = urlsplit(url)
        if parts.scheme not in {"https", "http"} or not parts.hostname or "," in parts.hostname:
            return {"url": url, "status": "invalid_native_url", "network_attempts": 0}
        host = parts.hostname.lower().removeprefix("www.")
        with lock:
            host_lock = host_locks.setdefault(host, Lock())
        with host_lock:
            with lock:
                prior = state["sources"].get(url) or previous.get(url)
                if prior:
                    state["sources"][url] = prior
                    return prior
                if host in blocked_hosts:
                    record = {
                        "url": url,
                        "status": "blocked_host_not_requested",
                        "network_attempts": 0,
                    }
                    state["sources"][url] = record
                    return record
            record = fetch(root, url)
            with lock:
                state["sources"][url] = record
                if record.get("http_status") in {401, 403, 429}:
                    blocked_hosts.add(host)
                write_json(root / JOURNAL, state)
            return record

    def candidate_sources(candidate):
        key = candidate["candidate_id"]
        with lock:
            if key in state["candidates"]:
                return key
        records = []
        seen_hosts = set()
        for url in candidate["campaign_websites"]:
            host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
            if host in seen_hosts:
                continue
            seen_hosts.add(host)
            page = retrieve(url)
            records.append(page["url"])
            if page.get("cache_path"):
                path = confined(root, page["cache_path"])
                raw = path.read_bytes()
                try:
                    text = source_text(raw, {})
                    if not text:
                        raise ValueError("empty extracted text")
                    markers = [
                        trait
                        for trait, pattern in MARKERS.items()
                        if re.search(pattern, text, re.IGNORECASE)
                    ]
                    with lock:
                        page["trait_reading_leads"] = markers
                        page["lead_status"] = "unreviewed_not_factual_evidence"
                    links = biography_urls(
                        raw.decode("utf-8", errors="replace"), page.get("resolved_url", url)
                    )
                    for link in links:
                        other = retrieve(link)
                        records.append(other["url"])
                except (ValueError, UnicodeError, OSError) as exc:
                    with lock:
                        page["extraction_failure"] = str(exc)[:300]
        with lock:
            state["candidates"][key] = {
                "candidate_id": key,
                "name": candidate["name"],
                "party": candidate["party"],
                "source_urls": records,
                "status": "retrieval_only_not_person_research"
                if records
                else "no_native_campaign_url_not_researched",
            }
            write_json(root / JOURNAL, state)
        return key

    with ThreadPoolExecutor(max_workers=workers) as pool:
        jobs = [pool.submit(candidate_sources, c) for c in candidates]
        for count, job in enumerate(as_completed(jobs), 1):
            job.result()
            if count % 25 == 0:
                print(f"Native campaign retrieval processed {count}/{len(candidates)}", flush=True)
    output = root / RESULTS
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "unreviewed-campaign-reading-leads.json", state)
    return {
        "candidates_processed_for_retrieval": len(state["candidates"]),
        "sources": len(state["sources"]),
        "person_research_completed_by_retrieval": 0,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    print(json.dumps(run(Path(__file__).resolve().parents[1], args.limit, args.workers), indent=2))
