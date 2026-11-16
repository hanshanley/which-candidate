"""Freeze the V2 research population before acquiring V3 source-family evidence."""

import argparse
import copy
import csv
import io
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from openpyxl import load_workbook

from .characteristics_research import normalized
from .house_characteristics import TRAITS, write_csv
from .storage import fingerprint, json_bytes, read_rows, write_json

BASELINE = "data/house-characteristics-v3-baseline.json"
QUEUE = "data/house-characteristics-v3-queue.csv"
ACQUISITIONS = "data/house-characteristics-v3-acquisitions.json"
ATTRIBUTION = (
    "Center for American Women and Politics, Eagleton Institute of Politics, "
    "Rutgers University-New Brunswick. CAWP Congressional Women Candidates Database, "
    "1990-2024 workbook; accessed November 16, 2026. Noncommercial research use. "
    "Race codes are source classifications: self-identification or CAWP multiple-source "
    "verification, not necessarily direct self-identification. Multiple codes are retained; "
    "unavailable is unknown. Historical classification is not a verified current identity."
)


def freeze(root):
    root = Path(root)
    if (root / BASELINE).exists():
        return json.loads((root / BASELINE).read_text())
    old = json.loads((root / "data/house-characteristics-v2-frozen.json").read_text())
    protected = dict(old["protected_sha256"])
    for folder in ("results/house-characteristics-v2", "publication/characteristics-v2"):
        protected.update(
            (p.relative_to(root).as_posix(), fingerprint(p)["sha256"])
            for p in (root / folder).rglob("*")
            if p.is_file()
        )
    traits = read_rows(root / "results/house-characteristics-v2/candidate-traits.jsonl.gz")
    candidates = read_rows(root / "results/house/candidates.jsonl.gz")
    with (root / "results/house-characteristics-v2/remaining-gaps.csv").open() as stream:
        gaps = {(r["candidate_id"], r["trait"]) for r in csv.DictReader(stream)}
    with (root / "results/house-characteristics-v2/selection.csv").open() as stream:
        selected = {(r["contest_id"], r["name"], r["trait"]): r for r in csv.DictReader(stream)}
    incumbency = {r["candidate_id"]: r for r in traits if r["trait"] == "incumbency"}
    rows = []
    for row in traits:
        if row["party"] != "Democratic":
            continue
        inc = incumbency[row["candidate_id"]]
        group = (
            "incumbent"
            if inc["analysis_value"] is True
            else ("nonincumbent" if inc["analysis_value"] is False else "unknown_incumbency")
        )
        source_gap = row["status"] == "unknown"
        coding_gap = not row["analysis_eligible"] and row["status"] not in {
            "unknown",
            "inapplicable",
        }
        rows.append(
            {
                k: row[k]
                for k in ("candidate_id", "contest_id", "name", "state", "district", "trait")
            }
            | {
                "performance_eligible": row["performance_eligible"],
                "incumbency_group": group,
                "factual_status": row["status"],
                "factual_qualified": row["factual_qualified"],
                "analysis_eligible": row["analysis_eligible"],
                "needs_source_evidence": source_gap,
                "needs_coding_or_timing": coding_gap,
                "contrast_support_separate": row["trait"]
                in {"race", "ethnicity", "prior_elected_office", "other_government", "military"},
                "in_remaining_gaps": (row["candidate_id"], row["trait"]) in gaps,
                "v2_selection_reason": selected.get(
                    (row["contest_id"], row["name"], row["trait"]), {}
                ).get("reason"),
                "field_eligibility_reason": row["eligibility_reason"],
                "priority": 0
                if row["trait"] == "incumbency" and group == "unknown_incumbency"
                else 1
                if row["performance_eligible"] and not row["analysis_eligible"]
                else 2,
            }
        )
    rows.sort(
        key=lambda r: (
            r["priority"],
            r["incumbency_group"] == "incumbent",
            r["state"],
            r["name"],
            r["trait"],
        )
    )
    write_csv(root / QUEUE, rows)
    import hashlib

    inputs = read_rows(root / "results/house/source-inputs.jsonl.gz")[0]
    normalized = inputs.get("reviewed_characteristic_observations", [])
    result = {
        "baseline_commit": "30d8a8c064e694180bb486d982bc1c5db6bdea59",
        "protected_sha256": protected,
        "baseline_inputs": {
            name: fingerprint(root / name)
            for name in (
                "results/house-characteristics-v2/candidate-traits.csv",
                "results/house-characteristics-v2/remaining-gaps.csv",
                "results/house-characteristics-v2/selection.csv",
                "results/house/source-inputs.jsonl.gz",
                "results/house/background-observations.csv",
            )
        },
        "historical_reviewed_observations": {
            r["observation_id"]: hashlib.sha256(json_bytes(r)).hexdigest() for r in normalized
        },
        "historical_background_observations": fingerprint(
            root / "results/house/background-observations.csv"
        ),
        "candidate_identity_sha256": hashlib.sha256(
            json_bytes(
                [
                    {
                        k: c[k]
                        for k in (
                            "candidate_id",
                            "contest_id",
                            "name",
                            "state",
                            "district",
                            "party",
                        )
                    }
                    for c in candidates
                ]
            )
        ).hexdigest(),
        "democrats": len({r["candidate_id"] for r in rows}),
        "trait_cells": len(rows),
        "traits": list(TRAITS),
        "incumbency_groups": dict(
            Counter(r["incumbency_group"] for r in rows if r["trait"] == "incumbency")
        ),
        "eligible_incumbency_groups": dict(
            Counter(
                r["incumbency_group"]
                for r in rows
                if r["trait"] == "incumbency" and r["performance_eligible"]
            )
        ),
        "queue": fingerprint(root / QUEUE),
    }
    write_json(root / BASELINE, result)
    return result


def contextual_match(candidate, record, *, historical=False):
    name = " ".join(
        str(record.get(k) or "")
        for k in (
            ("FName", "MName", "LName")
            if historical
            else ("First Name", "Middle Name", "Last Name")
        )
    )
    district = str(record.get("District" if historical else "Dist.") or "AL")
    district = "AL" if district in {"0", "00", "AL"} else district.zfill(2)
    return (
        normalized(name) == normalized(candidate["name"])
        and record.get("State") == candidate["state"]
        and district == candidate["district"]
        and record.get("Party") == {"Democratic": "D", "Republican": "R"}.get(candidate["party"])
        and record.get("Office") == ("U.S. Representative" if historical else "U.S. Rep.")
    )


def register_batch(root):
    """Register reviewed, actually downloaded originals; never redownload per person."""
    root = Path(root)
    journal_path = root / "data/house-characteristics-research.json"
    receipts_path = root / "data/house-characteristics-receipts.json"
    journal = json.loads(journal_path.read_text())
    receipts = json.loads(receipts_path.read_text())
    if any(s["id"].startswith("v3-") for s in journal["sources"]):
        raise ValueError("V3 batch already registered; do not duplicate observations")
    from .house_characteristics import source_catalog

    held = source_catalog(root)
    held_hashes = {r["sha256"] for r in held}
    originals = {
        "v3-cawp-history": (
            "cawp-congress-1990-2024.xlsx",
            "https://cawp.rutgers.edu/sites/default/files/2025-10/CONGRESS_MASTER_1990-2024.xlsx",
        ),
        "v3-cawp-codebook": (
            "cawp-codebook.pdf",
            "https://cawp.rutgers.edu/sites/default/files/resources/congress_statewide_codebook_external.pdf",
        ),
        "v3-cawp-2026-held": (
            "cawp-candidates.csv",
            "https://cawp.rutgers.edu/sites/default/files/data/2026%20Candidate%20List.csv",
        ),
        "v3-withhonor": (
            "withhonor-endorsements.html",
            "https://withhonorfundii.org/endorsements/",
        ),
    }
    cache = root / "data/raw/house-characteristics-v1"
    cache.mkdir(parents=True, exist_ok=True)
    documents = {}
    for key, (filename, url) in originals.items():
        path = root / "artifacts/characteristics-v3" / filename
        receipt = {
            "id": key,
            "url": url,
            "resolved_url": url,
            "retrieved_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
            "retrieval_clock_basis": "completed_curl_download_file_mtime",
            "retrieval_method": "original_download_curl_TLS_verified",
            "original_bytes_acquired": True,
            "new_document_hash": fingerprint(path)["sha256"] not in held_hashes,
            **fingerprint(path),
        }
        documents[key] = receipt
        (cache / key).write_bytes(path.read_bytes())
    candidates = read_rows(root / "results/house/candidates.jsonl.gz")
    book = load_workbook(
        io.BytesIO((cache / "v3-cawp-history").read_bytes()), read_only=True, data_only=True
    )
    records = iter(book.active.values)
    columns = next(records)
    history = [(i + 2, dict(zip(columns, values))) for i, values in enumerate(records)]
    current = list(
        csv.DictReader(io.StringIO((cache / "v3-cawp-2026-held").read_bytes().decode("cp1252")))
    )
    sources, rejections = [], []

    def add(candidate, document, claims, year, kind, **metadata):
        if not claims:
            return
        source_id = f"{document}-{candidate['candidate_id']}"
        sources.append(
            {
                "id": source_id,
                "document_id": document,
                **{
                    k: candidate[k]
                    for k in ("candidate_id", "contest_id", "name", "state", "district", "party")
                },
                "url": documents[document]["url"],
                "publication_date": str(year) if year else None,
                "kind": kind,
                "identity_qualification": (
                    "Exact full name, state, House office, district and party; source election "
                    "year is separately preserved. No first-name or namesake matching."
                ),
                "claims": claims,
                **metadata,
            }
        )
        receipts["sources"].append(
            {
                **copy.deepcopy(documents[document]),
                "id": source_id,
                "status": "acquired_pending_fragment_validation",
            }
        )

    race_codes = {
        "W": "White",
        "B": "Black",
        "AP": "Asian American/Pacific Islander",
        "NA": "Native American/Native Alaskan",
        "MENA": "Middle Eastern/North African",
        "MU": "Multi-Racial",
    }
    for candidate in candidates:
        rows = [
            (i, r)
            for i, r in history
            if r["Year"] == 2024 and contextual_match(candidate, r, historical=True)
        ]
        if len(rows) == 1:
            row_number, record = rows[0]
            fragment = " | ".join(f"{k}={v if v is not None else ''}" for k, v in record.items())
            tokens = (record["Race"] or "unavailable").split("/")
            identities = [race_codes[t] for t in tokens if t in race_codes]
            qualification = ATTRIBUTION + f" Sheet1 row {row_number}; observation year 2024."
            claims = [
                {
                    "trait": "gender",
                    "value": "F",
                    "fragment": fragment,
                    "qualification": qualification
                    + " Membership in a staff-verified women-candidate dataset; not inferred sex.",
                }
            ]
            if identities:
                claims.append(
                    {
                        "trait": "race",
                        "value": identities,
                        "fragment": fragment,
                        "qualification": qualification,
                        "source_codes": record["Race"],
                    }
                )
            if "H" in tokens:
                claims.append(
                    {
                        "trait": "ethnicity",
                        "value": ["Hispanic/Latina"],
                        "fragment": fragment,
                        "qualification": qualification,
                        "source_codes": record["Race"],
                    }
                )
            add(
                candidate,
                "v3-cawp-history",
                claims,
                2024,
                "CAWP_staff_verified_historical_candidate_dataset",
                format="xlsx",
                source_row=row_number,
                attribution=ATTRIBUTION,
            )
        for index, record in history:
            source_name = " ".join(str(record.get(k) or "") for k in ("FName", "MName", "LName"))
            if (
                record["Year"] == 2024
                and normalized(source_name) == normalized(candidate["name"])
                and not contextual_match(candidate, record, historical=True)
            ):
                rejections.append(
                    {
                        "candidate_id": candidate["candidate_id"],
                        "name": candidate["name"],
                        "source_row": index,
                        "source": "v3-cawp-history",
                        "reason": "Name agrees but state/district/party/House context differs; no automatic cross-contest transfer.",
                        "record": record,
                    }
                )
        rows = [r for r in current if contextual_match(candidate, r)]
        if len(rows) == 1:
            record = rows[0]
            fragment = " | ".join(f"{k}={v}" for k, v in record.items())
            claims = [
                {
                    "trait": "gender",
                    "value": "F",
                    "fragment": fragment,
                    "qualification": "Previously acquired 2026 CAWP women-candidate list; newly coded existing evidence, NOT new acquisition. Source records women, not inferred sex.",
                }
            ]
            status = record["General Seat Status"]
            if status in {"C", "O", "CP", "I", "I/U", "IU"}:
                claims.append(
                    {
                        "trait": "incumbency",
                        "value": status in {"I", "I/U", "IU"},
                        "fragment": fragment,
                        "qualification": f"2026 House General Seat Status={status}; CAWP published I/C/O definitions. Previously acquired evidence, newly reviewed. Not a complete lifetime service history.",
                    }
                )
            add(
                candidate,
                "v3-cawp-2026-held",
                claims,
                2026,
                "CAWP_staff_verified_current_candidate_dataset",
                format="csv",
                encoding="cp1252",
            )

    import re

    from .corrected import text

    veteran_text = text((cache / "v3-withhonor").read_text())
    for candidate in candidates:
        district = str(int(candidate["district"])) if candidate["district"] != "AL" else "AL"
        pattern = (
            re.escape(f"{candidate['name']}, {candidate['state']}-")
            + rf"0?{re.escape(district)}, U\.S\. ([^\n]+)"
        )
        match = re.search(pattern, veteran_text)
        if match:
            add(
                candidate,
                "v3-withhonor",
                [
                    {
                        "trait": "military",
                        "value": match.group(1),
                        "fragment": match.group(0),
                        "qualification": "Explicit named branch/veteran classification, not inferred from endorsement. Undated live list: qualified positive source report, retrospective timing unresolved; no nonservice reference.",
                    }
                ],
                None,
                "veteran_endorsing_organization_explicit_service_report",
            )
    journal["sources"].extend(sources)
    write_json(journal_path, journal)
    write_json(receipts_path, receipts)
    result = {
        "documents": list(documents.values()),
        "attribution": ATTRIBUTION,
        "new_document_hashes": sum(r["new_document_hash"] for r in documents.values()),
        "sources": len(sources),
        "new_acquired_claims": sum(
            len(s["claims"]) for s in sources if documents[s["document_id"]]["new_document_hash"]
        ),
        "existing_evidence_claims_newly_coded": sum(
            len(s["claims"])
            for s in sources
            if not documents[s["document_id"]]["new_document_hash"]
        ),
        "rejected_matches": rejections,
        "discovery_dispositions": [
            {
                "source": "CandiData 2024",
                "status": "acquired_discovery_not_ingested",
                "reason": "Exact FEC matches add no unknown Democratic gender; demographic source definitions incomplete. No coding promotion.",
            },
            {
                "source": "CAWP 2026 candidate CSV",
                "status": "byte_identical_held_source_not_new",
                "sha256": documents["v3-cawp-2026-held"]["sha256"],
            },
            {
                "source": "Future Caucus 2026",
                "status": "aggregate_report_not_candidate_microdata",
                "reason": "No acquired public candidate-level microdata; KnowWho access not purchased.",
            },
        ],
    }
    write_json(root / ACQUISITIONS, result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--register-batch", action="store_true")
    args = parser.parse_args()
    result = register_batch(args.root) if args.register_batch else freeze(args.root)
    print(
        json.dumps(
            {
                k: v
                for k, v in result.items()
                if k
                not in {"protected_sha256", "historical_reviewed_observations", "baseline_inputs"}
            },
            indent=2,
        )
    )
