"""Acquire the authors' CongressData deposit; keep historical records distinct from 2026."""

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .rebuild import ROOT
from .storage import fingerprint, read_rows, write_json

DEPOSIT = "https://api.figshare.com/v2/articles/28146914"
CACHE = "data/raw/congressdata-20261114"


def acquire(root=ROOT):
    import pandas as pd
    import rdata

    root = Path(root)
    cache = root / CACHE
    cache.mkdir(parents=True, exist_ok=True)
    receipt_path = root / "data/congressdata-sources.json"
    prior = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
    receipts = {r["id"]: r for r in prior.get("sources", [])}

    def download(key, url, suffix):
        path = cache / f"{key}{suffix}"
        if key in receipts:
            if fingerprint(path) != {k: receipts[key][k] for k in ("bytes", "sha256")}:
                raise ValueError(f"Changed CongressData original: {key}")
            return path
        subprocess.run(
            [
                "curl",
                "--fail",
                "--location",
                "--silent",
                "--show-error",
                "--max-time",
                "180",
                "--output",
                str(path),
                url,
            ],
            check=True,
        )
        receipts[key] = {
            "id": key,
            "url": url,
            "path": str(path.relative_to(root)),
            **fingerprint(path),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }
        write_json(receipt_path, {"sources": list(receipts.values())})
        return path

    metadata = json.loads(download("figshare-metadata", DEPOSIT, ".json").read_text())
    native = next(f for f in metadata["files"] if f["name"] == "congress.rda")
    path = download("congressdata-deposit", native["download_url"], ".rda")
    if path.stat().st_size != native["size"]:
        raise ValueError("CongressData deposit size differs from publisher metadata")
    if hashlib.md5(path.read_bytes(), usedforsecurity=False).hexdigest() != native["computed_md5"]:
        raise ValueError("CongressData deposit differs from publisher checksum")
    codebook = download(
        "congressdata-v3-codebook",
        "https://raw.githubusercontent.com/IPPSR/CongressData/main/congress_codebook_3.pdf",
        ".pdf",
    )
    description = download(
        "congressdata-package-description",
        "https://raw.githubusercontent.com/IPPSR/CongressData/main/DESCRIPTION",
        ".txt",
    )
    if "License: GPL-3" not in description.read_text():
        raise ValueError("CongressData package license declaration changed")
    license_text = download(
        "congressdata-package-license", "https://www.gnu.org/licenses/gpl-3.0.txt", ".txt"
    )
    from pypdf import PdfReader

    codebook_text = "\n".join(p.extract_text() for p in PdfReader(codebook).pages)
    constructors = dict(rdata.conversion.DEFAULT_CLASS_MAP)
    constructors["Date"] = lambda obj, attrs: pd.to_datetime(obj, unit="D", origin="1970-01-01")
    objects = rdata.read_rda(path, constructor_dict=constructors)
    frames = [f for f in objects.values() if {"bioguide", "year"}.issubset(f.columns)]
    if len(frames) != 1:
        raise ValueError("Expected one Bioguide/member-year CongressData frame")
    data = frames[0]
    inputs = read_rows(root / "results/house/source-inputs.jsonl.gz")[0]
    additions = json.loads((root / "data/house-member-profiles.json").read_text())
    ids = {p["id"]["bioguide"] for p in inputs["people"]}
    ids.update(p["id"]["bioguide"] for p in additions.get("additional_service_people", []))
    selected = data[data["bioguide"].isin(ids)].copy()
    if selected.duplicated(["bioguide", "year"]).any():
        # A member-year may have multiple district/term spells. Preserve all latest-year rows.
        duplicate_status = "member_year_spells_preserved"
    else:
        duplicate_status = "unique_member_year"
    latest = selected[selected["year"] == selected.groupby("bioguide")["year"].transform("max")]
    rows = json.loads(latest.to_json(orient="records", date_format="iso"))
    rows.sort(key=lambda r: (r["bioguide"], json.dumps(r, sort_keys=True)))
    result = {
        "scope": "Latest available historical member-year rows for the held service crosswalk; "
        "all source variables preserved, not current 2026 beliefs or new model inputs",
        "attribution": "Grossmann, Matt, Caleb Lucas, and Benjamin Yoel. 2025. Introducing "
        "CongressData and Correlates of State Policy. Scientific Data 12:1185. "
        "Also cite each variable's original source in the included v3 codebook.",
        "license": metadata["license"],
        "source": receipts["congressdata-deposit"],
        "deposit_metadata": receipts["figshare-metadata"],
        "codebook_source": receipts["congressdata-v3-codebook"],
        "codebook_package_license": {
            "license": "GPL-3.0",
            "scope": "Codebook distributed in the upstream CongressData package; "
            "distinct from the Figshare data deposit's CC BY 4.0 license",
            "declaration_source": receipts["congressdata-package-description"],
            "declaration_text": description.read_text(),
            "license_source": receipts["congressdata-package-license"],
            "license_text": license_text.read_text(),
        },
        "codebook_qualification": "v3 current codebook; deposit variable availability checked "
        "against actual column names, not assumed identical",
        "codebook_text": codebook_text,
        "source_rows": len(data),
        "source_columns": len(data.columns),
        "source_year_min": int(data["year"].min()),
        "source_year_max": int(data["year"].max()),
        "member_year_status": duplicate_status,
        "columns": list(data.columns),
        "rows": rows,
        "model_ready": False,
        "acquisition_reader": {
            "library": "rdata",
            "version": rdata.__version__,
            "pandas_version": pd.__version__,
            "date_conversion": "R Date days since 1970-01-01 converted to ISO timestamps",
        },
    }
    write_json(root / "data/congressdata-members.json", result)
    return {k: v for k, v in result.items() if k not in ("rows", "codebook_text", "columns")} | {
        "retained_members": len({r["bioguide"] for r in rows}),
        "retained_rows": len(rows),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(acquire(args.root), indent=2))
