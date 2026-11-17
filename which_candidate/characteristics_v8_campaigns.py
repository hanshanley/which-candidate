"""Roster-linked, resumable national challenger biography discovery."""

import argparse
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlsplit

from .characteristics_v7_batch import acquire, prior_sources
from .characteristics_v8_batch import WORK
from .storage import read_rows, write_json


class BiographyLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.href = None
        self.label = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.href = dict(attrs).get("href")
            self.label = []

    def handle_data(self, data):
        if self.href:
            self.label.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.href:
            self.links.append((self.href, " ".join(self.label)))
            self.href = None


def biography_urls(html, origin):
    parser = BiographyLinks()
    parser.feed(html)
    result = []
    host = urlsplit(origin).hostname
    for href, label in parser.links:
        url = urldefrag(urljoin(origin, href))[0]
        parts = urlsplit(url)
        if (
            parts.scheme in {"http", "https"}
            and parts.hostname == host
            and url.rstrip("/") != origin.rstrip("/")
            and re.search(r"\b(?:about|meet|biography|bio|story)\b", label, re.I)
            and not re.search(r"privacy|cookie|policy|team|staff|volunteer", label, re.I)
            and url not in result
        ):
            result.append(url)
    return result[:2]


def plan(root):
    root = Path(root)
    rows = read_rows(root / "results/house-characteristics-v7/candidate-traits.jsonl.gz")
    incumbency = {r["candidate_id"]: r for r in rows if r["trait"] == "incumbency"}
    sources = []
    for candidate in read_rows(root / "results/house/candidates.jsonl.gz"):
        if candidate["party"] != "Democratic":
            continue
        inc = incumbency[candidate["candidate_id"]]
        if inc["analysis_eligible"] and inc["analysis_value"]:
            continue
        urls = list(candidate["campaign_websites"])
        website = candidate.get("website") or {}
        if (
            website.get("cand_election_yr") == "2026"
            and website.get("cand_id") == candidate["identity"].get("fec_id")
            and website.get("normalized_website_url")
        ):
            urls.append(website["normalized_website_url"])
        urls = list(dict.fromkeys(url for url in urls if url.startswith(("https://", "http://"))))
        if not urls:
            continue
        sources.append(
            {
                "id": f"campaign-{candidate['candidate_id']}-home",
                "family": "national-original-campaigns",
                "url": urls[0],
                "native_campaign_urls": urls,
                "candidate_id": candidate["candidate_id"],
                "name": candidate["name"],
                "state": candidate["state"],
                "district": candidate["district"],
                "identity_method": "Native campaign URL or same-year exact-FEC website record; "
                "page subject still requires literal review",
                "potential_fields": [
                    "age",
                    "gender",
                    "race",
                    "ethnicity",
                    "religion",
                    "education",
                    "profession",
                    "prior_elected_office",
                    "other_government",
                    "military",
                ],
                "missing_fields": [
                    r["trait"]
                    for r in rows
                    if r["candidate_id"] == candidate["candidate_id"] and not r["analysis_eligible"]
                ],
            }
        )
    write_json(root / "data/house-characteristics-v8-campaign-plan.json", sources)
    return sources


def run(root, workers=4):
    root = Path(root)
    sources = plan(root)
    receipts = []
    retained = prior_sources(root)

    # Each worker owns a separate durable journal; the combined journal is
    # assembled by the parent only, so interruption cannot corrupt other jobs.
    def fetch(source):
        key = source["id"]
        workdir = f"{WORK}/campaign/{key}"
        result = acquire(root, sources={key: source}, workdir=workdir, prior=retained)[0]
        return {**result, "cached_path": f"{workdir}/{key}"}

    def save():
        write_json(
            root / WORK / "campaign-retrievals.json", sorted(receipts, key=lambda r: r["id"])
        )

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch, s): s for s in sources}
        while futures:
            for future in as_completed(list(futures)):
                source = futures.pop(future)
                result = future.result()
                receipts.append(result)
                save()
                print(result["id"], result["status"], flush=True)
                if source["id"].endswith("-home") and result["status"] == "acquired":
                    path = root / result["cached_path"]
                    html = path.read_text(errors="replace")
                    for index, url in enumerate(
                        biography_urls(html, result.get("resolved_url") or source["url"]), 1
                    ):
                        # Do not revisit an exhausted original under an about-page ID.
                        if url in {r.get("url") for r in receipts}:
                            continue
                        child = {
                            **source,
                            "id": source["id"].replace("-home", f"-bio{index}"),
                            "url": url,
                            "discovered_from": result["id"],
                        }
                        futures[pool.submit(fetch, child)] = child
    write_json(root / WORK / "campaign-source-ledger-snapshot.json", retained)
    return receipts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    run(Path(__file__).resolve().parents[1], args.workers)
