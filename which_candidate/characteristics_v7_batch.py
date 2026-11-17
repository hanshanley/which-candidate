"""Resumable source-family acquisition for the V6-based research batch."""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

from .storage import fingerprint, write_json

SOURCES = {
    "lublin-house-2023": {
        "url": "https://davidlublin.com/wp-content/uploads/2023/04/Replication-US-House.zip",
        "potential_fields": ["race", "ethnicity", "prior_elected_office"],
        "expected_candidates": ["Independently linked historical House members only"],
    },
    "lublin-state-2023": {
        "url": "https://davidlublin.com/wp-content/uploads/2023/04/State-Leg-Replication-Archive.zip",
        "potential_fields": ["race", "ethnicity", "prior_elected_office"],
        "expected_candidates": [
            "Native-roster former state legislators in the 33-state source population"
        ],
    },
    "cawp-officeholders-page": {
        "url": "https://cawp.rutgers.edu/data/women-elected-officials-database",
        "potential_fields": ["race", "ethnicity", "prior_elected_office"],
        "expected_candidates": [
            "Independently linked women officeholders; absence is not nonservice"
        ],
    },
    "cawp-officeholders-faq": {
        "url": "https://cawp.rutgers.edu/women-elected-officials-database-faqs",
        "potential_fields": ["classification_definitions"],
        "expected_candidates": [],
    },
    "cawp-officeholders-json": {
        "url": "https://cawp.rutgers.edu/women-elected-officials/export/roles/json?page&_format=json",
        "potential_fields": ["race", "ethnicity", "prior_elected_office"],
        "expected_candidates": ["Permitted public export linked by the acquired database page"],
    },
    "ballotpedia-survey-completion-2026": {
        "url": "https://ballotpedia.org/Elections_with_full_Candidate_Connection_survey_completion,_2026",
        "potential_fields": ["discovery_only"],
        "expected_candidates": [
            "Native-roster candidates only; primary completion is not general-election coverage"
        ],
    },
    "congressdata-current-data": {
        "url": "https://ippsr.msu.edu/congressdata",
        "potential_fields": ["verified_member_variables_only"],
        "expected_candidates": ["Independently linked historical members, not all challengers"],
    },
    "congressdata-current-codebook": {
        "url": "https://ippsr.msu.edu/congresscodebook",
        "potential_fields": ["variable_provenance"],
        "expected_candidates": [],
    },
    "umn-gronli-2023": {
        "url": "https://design.umn.edu/news/dream-big-interview-alumna-nikki-gronli-0",
        "potential_fields": ["education", "profession", "other_government"],
        "expected_candidates": ["Nikki Gronli"],
    },
    "brookings-gronli-2026": {
        "url": "https://www.brookingsregister.com/news/strong-middle-class-health-care-key-issues-for-us-house-hopeful-nikki-gronli/",
        "potential_fields": ["age", "profession", "other_government"],
        "expected_candidates": ["Nikki Gronli"],
    },
    "mn-legislature-2019": {
        "url": "https://www.sos.state.mn.us/media/3865/3-state-legislature-2019.pdf",
        "potential_fields": ["education", "profession", "prior_elected_office"],
        "expected_candidates": [
            "Native-roster historical Minnesota legislators including Matt Little"
        ],
    },
    "nv-benitez-thompson-2011": {
        "url": "https://archive.leg.state.nv.us/Session/76th2011/legislators/Assembly/Benitez-Thompson.pdf",
        "potential_fields": ["religion", "education", "profession", "prior_elected_office"],
        "expected_candidates": ["Teresa Benitez-Thompson; explicitly dated 2011 membership only"],
    },
    "cawp-officeholders-csv": {
        "url": "https://cawp.rutgers.edu/women-elected-officials/export/roles/csv?page&_format=csv",
        "potential_fields": ["race", "ethnicity", "prior_elected_office"],
        "expected_candidates": ["Alternative public export explicitly linked by database page"],
    },
}


def prior_sources(root):
    paths = sorted((root / "data").glob("*receipts.json"))
    paths += sorted((root / "data").glob("*acquisitions.json"))
    paths += [root / "data/research-sources.json"]
    result = []
    for path in paths:
        if not path.exists():
            continue
        value = json.loads(path.read_text())
        records = (
            value
            if isinstance(value, list)
            else (value.get("sources", []) if isinstance(value, dict) else [])
        )
        if not isinstance(records, list):
            continue
        for record in records:
            if (
                isinstance(record, dict)
                and record.get("sha256")
                and record.get("original_bytes_acquired") is not False
                and not record.get("status", "").startswith("failed")
            ):
                result.append({**record, "ledger": str(path.relative_to(root))})
    return result


def acquire(root, *, sources=SOURCES, workdir="artifacts/characteristics-v7", prior=None):
    root = Path(root)
    work = root / workdir
    work.mkdir(parents=True, exist_ok=True)
    output = work / "retrievals.json"
    known = {r["id"]: r for r in json.loads(output.read_text())} if output.exists() else {}
    prior = prior_sources(root) if prior is None else prior
    urls = {r[k]: r for r in prior for k in ("url", "origin_url", "resolved_url") if r.get(k)}
    hashes = {r["sha256"]: r for r in prior}
    for key, source in sources.items():
        path = work / key
        if key in known:
            if known[key]["status"] == "acquired":
                if fingerprint(path) != {k: known[key][k] for k in ("bytes", "sha256")}:
                    raise ValueError(f"Cached acquisition fingerprint changed: {key}")
            continue
        retained = urls.get(source["url"])
        if retained:
            known[key] = {
                "id": key,
                **source,
                "status": "retained_existing_source_not_new_acquisition",
                "sha256": retained["sha256"],
                "prior_ledger": retained["ledger"],
                "prior_source_id": retained.get("id"),
                "network_attempts": 0,
            }
        else:
            partial = work / f"{key}.part"
            response = subprocess.run(
                [
                    "curl",
                    "--http1.1",
                    "--location",
                    "--fail",
                    "--silent",
                    "--show-error",
                    "--connect-timeout",
                    "20",
                    "--max-time",
                    "90",
                    "--retry",
                    "0",
                    "--output",
                    str(partial),
                    "--write-out",
                    "%{url_effective}",
                    *(
                        ["--data", urlencode(source["post_data"], doseq=True)]
                        if source.get("post_data")
                        else []
                    ),
                    source["url"],
                ],
                capture_output=True,
                text=True,
            )
            receipt = {
                "id": key,
                **source,
                "resolved_url": response.stdout,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "retrieval_method": "original_download_curl_TLS_verified",
                "network_attempts": 1,
                "status": "failed_attempt_not_evidence" if response.returncode else "acquired",
            }
            if response.returncode:
                receipt["error"] = response.stderr
                partial.unlink(missing_ok=True)
            else:
                partial.replace(path)
                receipt.update(fingerprint(path))
                if receipt["sha256"] in hashes:
                    retained = hashes[receipt["sha256"]]
                    receipt.update(
                        status="duplicate_existing_hash_not_new_acquisition",
                        prior_ledger=retained["ledger"],
                        prior_source_id=retained.get("id"),
                    )
            known[key] = receipt
        write_json(output, list(known.values()))
    return list(known.values())


if __name__ == "__main__":
    print(json.dumps(acquire(Path(__file__).resolve().parents[1]), indent=2))
