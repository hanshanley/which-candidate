"""Validate new trait receipts and incrementally retain them in normalized inputs."""

import argparse
import csv
import io
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from openpyxl import load_workbook
from pypdf import PdfReader

from .corrected import text as html_text
from .house_candidates import _fetch, build
from .storage import fingerprint, read_rows, write_json


def normalized(value):
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def canonical_receipt(receipt):
    return {
        k: v
        for k, v in receipt.items()
        if k not in {"status", "reviewed_claims", "rejected_attributions", "previous_attempts"}
    }


def reviewed_claims(source, receipt, text=None):
    if (
        text is not None
        and source.get("identity_fragment")
        and normalized(source["identity_fragment"]) not in normalized(text)
    ):
        raise ValueError(f"Unsupported research subject: {source['id']}")
    result = []
    for index, claim in enumerate(source["claims"]):
        if text is not None and normalized(claim["fragment"]) not in normalized(text):
            raise ValueError(f"Unsupported research fragment: {source['id']}:{index}")
        if text is not None and any(
            normalized(fragment) not in normalized(text)
            for fragment in claim.get("identity_support", [])
        ):
            raise ValueError(f"Unsupported research identity link: {source['id']}:{index}")
        result.append(
            {
                **{
                    k: source[k]
                    for k in (
                        "candidate_id",
                        "contest_id",
                        "name",
                        "state",
                        "district",
                        "party",
                    )
                },
                **claim,
                "observation_id": f"{source['id']}:{index}",
                "source_id": source["id"],
                "source_kind": source["kind"],
                "publication_date": source["publication_date"],
                "receipt": canonical_receipt(receipt),
                "identity_qualification": source["identity_qualification"],
                "model_ready": False,
                "review_status": "fragment_and_identity_reviewed",
            }
        )
    return result


def source_text(body, source):
    if source.get("format") == "xlsx":
        book = load_workbook(io.BytesIO(body), read_only=True, data_only=True)
        records = iter(book[source.get("sheet", book.sheetnames[0])].values)
        columns = next(records)
        return "\n".join(
            " | ".join(
                f"{key}={value if value is not None else ''}" for key, value in zip(columns, row)
            )
            for row in records
        )
    if source.get("format") == "csv":
        records = csv.DictReader(io.StringIO(body.decode(source.get("encoding", "utf-8-sig"))))
        return "\n".join(" | ".join(f"{k}={v}" for k, v in row.items()) for row in records)
    scope = source.get("text_scope", {})
    if body.startswith(b"%PDF"):
        pages = PdfReader(io.BytesIO(body)).pages
        text = (
            pages[scope["page"] - 1].extract_text() or ""
            if "page" in scope
            else "\n".join(p.extract_text() or "" for p in pages)
        )
    else:
        text = html_text(body.decode("utf-8", errors="replace"))
    text = normalized(text) if scope else text
    for boundary in ("start", "end"):
        if boundary not in scope:
            continue
        marker = normalized(scope[boundary])
        if marker not in text:
            raise ValueError(f"Missing research subject boundary: {source['id']}:{boundary}")
        index = text.index(marker)
        text = text[index:] if boundary == "start" else text[:index]
    return text


def ingest(root, *, offline=False):
    root = Path(root)
    candidates = read_rows(root / "results/house/candidates.jsonl.gz")
    inputs = read_rows(root / "results/house/source-inputs.jsonl.gz")[0]
    journal = json.loads((root / "data/house-characteristics-research.json").read_text())
    cache = root / "data/raw/house-characteristics-v1"
    cache.mkdir(parents=True, exist_ok=True)
    receipts_path = root / "data/house-characteristics-receipts.json"
    previous = json.loads(receipts_path.read_text()) if receipts_path.exists() else {"sources": []}
    old = {r["id"]: r for r in previous["sources"]}
    observations = {
        r["observation_id"]: r for r in inputs.get("reviewed_characteristic_observations", [])
    }
    receipts = []
    document_texts = {}
    for source in journal["sources"]:
        matches = [
            c
            for c in candidates
            if all(
                str(c[k]) == str(source[k])
                for k in ("candidate_id", "contest_id", "name", "state", "district", "party")
            )
        ]
        if len(matches) != 1:
            raise ValueError(f"Unqualified research identity: {source['id']}")
        if not re.fullmatch(r"[a-z0-9-]+", source["id"]):
            raise ValueError("Unsafe research cache key")
        document = source.get("document_id", source["id"])
        if not re.fullmatch(r"[a-z0-9-]+", document):
            raise ValueError("Unsafe shared document cache key")
        path = cache / document
        receipt = old.get(source["id"])
        if receipt and receipt["status"].startswith("reviewed") and not path.exists():
            saved = [r for r in observations.values() if r["source_id"] == source["id"]]
            if saved != reviewed_claims(source, receipt):
                raise ValueError("Changed or missing normalized evidence for absent original")
            receipts.append(receipt)
            continue
        if offline and (not receipt or receipt["status"] == "failed_attempt_not_evidence"):
            if receipt is None:
                raise ValueError("Offline source has no acquisition disposition")
            receipts.append(receipt)
            continue
        try:
            if receipt and path.exists():
                if fingerprint(path) != {k: receipt[k] for k in ("bytes", "sha256")}:
                    raise ValueError("Changed held characteristic source")
            else:
                public_extract = source.get("reviewed_public_extract")
                try:
                    body, resolved = _fetch(source["url"])
                    retrieval_method = "original_download"
                    original_failure = None
                except OSError as error:
                    if public_extract is None:
                        raise
                    body = public_extract["text"].encode()
                    resolved = public_extract["origin_url"]
                    retrieval_method = "reviewed_public_index_extract_not_original_pdf"
                    original_failure = str(error)
                path.write_bytes(body)
                receipt = {
                    "id": source["id"],
                    "url": source["url"],
                    "resolved_url": resolved,
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "retrieval_method": retrieval_method,
                    "original_request_failure": original_failure,
                    "original_bytes_acquired": original_failure is None,
                    **fingerprint(path),
                }
            receipt = canonical_receipt(receipt)
            body = path.read_bytes()
            key = (
                document,
                receipt["sha256"],
                source.get("format"),
                source.get("encoding"),
                json.dumps(source.get("text_scope", {}), sort_keys=True),
            )
            if key not in document_texts:
                document_texts[key] = source_text(body, source)
            text = document_texts[key]
            checked = reviewed_claims(source, receipt, text)
            observations.update({r["observation_id"]: r for r in checked})
            receipts.append(
                {
                    **receipt,
                    "status": "reviewed",
                    "reviewed_claims": len(source["claims"]),
                    "rejected_attributions": source.get("rejected_attributions", []),
                    "previous_attempts": [
                        *old.get(source["id"], {}).get("previous_attempts", []),
                        *(
                            [
                                dict(
                                    (k, v)
                                    for k, v in old[source["id"]].items()
                                    if k != "previous_attempts"
                                )
                            ]
                            if old.get(source["id"], {}).get("status")
                            == "failed_attempt_not_evidence"
                            else []
                        ),
                    ],
                }
            )
        except (OSError, ValueError) as error:
            receipts.append(
                {
                    "id": source["id"],
                    "url": source["url"],
                    "status": "failed_attempt_not_evidence",
                    "error": str(error),
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                }
            )
    inputs["reviewed_characteristic_observations"] = list(observations.values())
    result = build(root, inputs=inputs)
    write_json(receipts_path, {"sources": receipts})
    leads_path = root / "data/candidate-source-leads.json"
    leads = json.loads(leads_path.read_text())
    known = {(r["candidate_id"], r["url"]) for r in leads}
    for source in journal["sources"]:
        if (source["candidate_id"], source["url"]) not in known:
            leads.append(
                {
                    k: source[k]
                    for k in (
                        "candidate_id",
                        "contest_id",
                        "name",
                        "state",
                        "district",
                        "party",
                        "url",
                    )
                }
            )
    write_json(leads_path, leads)
    return {"build": result, "receipts": receipts, "normalized_claims": len(observations)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    print(json.dumps(ingest(args.root, offline=args.offline), indent=2))
