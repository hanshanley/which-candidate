import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .storage import confined, fingerprint, write_json

CONTEXT = Path("data/raw/context/20261104T171449Z")
AUDIT = Path("data/house-comparability/20261112-01/complete-audit.json")


def import_participation(source, data_dir):
    source, data_dir = Path(source).resolve(), Path(data_dir).resolve()
    manifest_path = data_dir / "sources.json"
    if manifest_path.exists():
        manifest = load_sources(manifest_path)
        return {"status": "verified_existing_import", "sources": len(manifest["sources"])}
    original = json.loads((source / CONTEXT / "manifest.json").read_bytes())
    specs = []
    for year in (2016, 2018, 2020, 2022):
        name = f"fec-{year}.xlsx"
        receipt = original[name]
        path = source / CONTEXT / name
        if fingerprint(path) != {key: receipt[key] for key in ("bytes", "sha256")}:
            raise ValueError(f"Held FEC original does not match its receipt: {name}")
        specs.append(
            {
                "id": f"fec_{year}",
                "kind": "fec_workbook",
                "year": year,
                "parent_path": str(CONTEXT / name),
                "origin_url": receipt["url"],
                "original_retrieved_at": receipt["retrieved_at"],
                "redistribution": "US federal government compilation; retain source attribution",
            }
        )
    specs.append(
        {
            "id": "house_audit_2024_2026",
            "kind": "house_audit",
            "parent_path": str(AUDIT),
            "origin_url": "https://github.com/hanshanley/voter-participation",
            "original_retrieved_at": None,
            "redistribution": "Derived factual queries; not the original provider feed",
        }
    )
    data_dir.mkdir(parents=True, exist_ok=True)
    for spec in specs:
        path = confined(source, spec["parent_path"])
        spec.update(fingerprint(path))
        relative = Path("raw") / f"{spec['sha256']}{path.suffix}"
        destination = confined(data_dir, relative)
        destination.parent.mkdir(exist_ok=True)
        if destination.exists():
            if fingerprint(destination) != fingerprint(path):
                raise ValueError(f"Content-addressed cache collision: {destination}")
        else:
            shutil.copyfile(path, destination)
        spec["path"] = relative.as_posix()
    manifest = {
        "schema": "which_candidate.sources.v1",
        "imported_at": datetime.now(timezone.utc).isoformat(),
        "sources": specs,
        "parent_worktree_is_not_assumed_clean": True,
        "parent_repository_modified": False,
    }
    write_json(manifest_path, manifest)
    return {"status": "imported", "sources": len(specs)}


def load_sources(path):
    path = Path(path).resolve()
    manifest = json.loads(path.read_bytes())
    if manifest.get("schema") != "which_candidate.sources.v1":
        raise ValueError("Unsupported source manifest")
    seen = set()
    for spec in manifest["sources"]:
        if spec["id"] in seen:
            raise ValueError("Duplicate source ID")
        seen.add(spec["id"])
        cached = confined(path.parent, spec["path"])
        if fingerprint(cached) != {key: spec[key] for key in ("bytes", "sha256")}:
            raise ValueError(f"Source hash mismatch: {spec['id']}")
    return manifest
