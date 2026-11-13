"""Pinned originals for the post-audit correction, never replacing v2 inputs."""

import argparse
import hashlib
import json
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from .fec import STATES
from .storage import write_json

UA = "Mozilla/5.0 (compatible; which-candidate research)"
SEARCH = (
    "https://civicapi.org/api/v2/race/search?startDate=2026-11-03&endDate=2026-11-03&limit=50000"
)


def acquire(data):
    data = Path(data)
    cache = data / "raw/corrections-v3"
    cache.mkdir(parents=True, exist_ok=True)
    index_path = cache / "index.json"
    index = json.loads(index_path.read_text()) if index_path.exists() else {}

    def fetch(url):
        if url in index and index[url]["status"] == "acquired":
            receipt = index[url]
            path = data / receipt["path"]
            if hashlib.sha256(path.read_bytes()).hexdigest() != receipt["sha256"]:
                raise ValueError(f"Changed pinned original: {url}")
            return receipt
        last = None
        for attempt in range(3):
            try:
                request = urllib.request.Request(url, headers={"User-Agent": UA})
                with urllib.request.urlopen(request, timeout=90) as response:
                    body = response.read()
                    final_url = response.url
                digest = hashlib.sha256(body).hexdigest()
                path = cache / digest
                path.write_bytes(body)
                return {
                    "url": url,
                    "resolved_url": final_url,
                    "path": str(path.relative_to(data)),
                    "sha256": digest,
                    "bytes": len(body),
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "status": "acquired",
                }
            except (OSError, ValueError) as error:
                last = str(error)
                time.sleep(attempt + 1)
        return {"url": url, "status": "unavailable", "error": last}

    catalog = fetch(SEARCH)
    if catalog["status"] != "acquired":
        raise ValueError(f"Native race catalog unavailable: {catalog}")
    index[SEARCH] = catalog
    write_json(index_path, index)
    races = json.loads((data / catalog["path"]).read_text())["races"]
    senate = [
        r
        for r in races
        if r.get("country") == "US"
        and r.get("province") in STATES
        and r.get("type") == "US Senate"
        and r.get("election_type") == "General"
    ]
    if len(senate) != 35:
        raise ValueError(f"Expected 35 national Senate races, got {len(senate)}: {senate[:2]}")
    house_audit = data / "raw/87600f4819217ac124a11120d9af49c6cf75d35e91839e10b2e29a165ee412cf.json"
    house_urls = sorted(
        set(re.findall(r"https://civicapi.org/api/v2/race/\d+", house_audit.read_text()))
    )
    if len(house_urls) != 435:
        raise ValueError("Incomplete House endpoint inventory")
    race_urls = house_urls + [f"https://civicapi.org/api/v2/race/{r['id']}" for r in senate]
    urls = [
        *race_urls,
        "https://bluedogdems.com/rosters/",
        "https://bluedogdems.com/endorsements/",
        "https://bluedogs-gluesenkampperez.house.gov/members",
        "https://justicedemocrats.com/candidates/",
        "https://bluedogdems.com/wp-json/wp/v2/pages?per_page=100&_fields=slug,link,title,date,modified",
        "https://clerk.house.gov/xml/lists/MemberData.xml",
        "https://progressives.house.gov/caucus-members",
        "https://elections.cdn.sos.ca.gov/statewide-elections/2026-general/cert-list-candidates.pdf",
        "https://sd02.senate.ca.gov/biography",
        "https://correa.house.gov/about/",
        "https://amo.house.gov/about",
        "https://steube.house.gov/about",
        "https://langworthy.house.gov/about",
        *[
            f"https://voteview.com/static/data/out/{kind}/{chamber}119_{kind}.csv"
            for chamber in ("H", "S")
            for kind in ("members", "votes", "rollcalls")
        ],
    ]
    with ThreadPoolExecutor(max_workers=5) as pool:
        for number, receipt in enumerate(pool.map(fetch, urls), 1):
            index[receipt["url"]] = receipt
            write_json(index_path, index)
            if number % 50 == 0 or receipt["status"] != "acquired":
                print(number, receipt["status"], receipt["url"], flush=True)
    # Capture indexes are themselves pinned; never silently use a post-election roster.
    archived_pages = [
        ("progressives.house.gov/caucus-members", year)
        for year in (2016, 2018, 2020, 2022, 2024, 2026)
    ] + [
        ("justicedemocrats.com/candidates/", 2026),
        ("bluedogdems.com/endorsements/", 2026),
    ]
    for page, year in archived_pages:
        url = (
            "https://web.archive.org/cdx/search/cdx"
            f"?url={page}&output=json"
            f"&filter=statuscode:200&from={year}&to={year}1102"
            "&filter=mimetype:text/html&collapse=timestamp:6"
        )
        receipt = fetch(url)
        index[url] = receipt
        if receipt["status"] == "acquired":
            captures = json.loads((data / receipt["path"]).read_text())
            if len(captures) > 1:
                timestamp = captures[-1][1]
                archive = f"https://web.archive.org/web/{timestamp}id_/https://{page}"
                index[archive] = {**fetch(archive), "election_year": year, "capture": timestamp}
        write_json(index_path, index)
    write_json(
        data / "correction-sources.json",
        {
            "contract": "which-candidate-corrections-v3-originals",
            "race_urls": race_urls,
            "sources": sorted(index.values(), key=lambda r: r["url"]),
        },
    )
    print("Pinned", len(index), "sources;", len(race_urls), "native race endpoints", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("data"))
    acquire(parser.parse_args().data)
