"""Package the additive factual checkpoint without replacing frozen V9 downloads."""

import argparse
import copy
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

from .biographical_research import BASELINE, RESULTS, load_json, verify_frozen
from .storage import confined, fingerprint, write_json

BASE_SHA256 = "78447a60c4c1bda80714d6984a706ba7db9dce31bae04fe4fd5526b6aac1aa64"
ARCHIVE_NAME = "biographical-research-complete.zip"


def verify_offline(archive):
    archive = Path(archive).resolve()
    with TemporaryDirectory(prefix="biographical-offline-") as temporary:
        destination = Path(temporary)
        with zipfile.ZipFile(archive) as package:
            for name in package.namelist():
                confined(destination, name)
            package.extractall(destination)
        program = """
import json
import sys
from pathlib import Path

def deny_network(event, args):
    if event.startswith("socket.") or event in {"subprocess.Popen", "os.system"}:
        raise RuntimeError("Network and subprocesses disabled during factual replay")

sys.addaudithook(deny_network)
from which_candidate import biographical_research as research
from which_candidate.storage import fingerprint

root = Path.cwd().resolve()
assert Path(research.__file__).resolve().is_relative_to(root)
manifest_path = root / research.RESULTS / "manifest.json"
before = manifest_path.read_bytes()
expected = json.loads(before)
summary = research.build(root)
for name, receipt in expected["files"].items():
    if fingerprint(root / name) != receipt:
        raise RuntimeError(f"Offline output differs: {name}")
if manifest_path.read_bytes() != before:
    raise RuntimeError("Offline manifest differs")
baseline = json.loads((root / research.BASELINE).read_text())
research.verify_frozen(root, baseline)
print(json.dumps({
    "network_and_subprocesses_disabled": True,
    "identical_outputs_including_manifest": len(expected["files"]) + 1,
    "protected_scientific_files_verified": len(baseline["protected_sha256"]),
    "summary": summary,
}))
"""
        result = subprocess.run(
            [sys.executable, "-c", program],
            cwd=destination,
            capture_output=True,
            text=True,
            check=True,
        )
    return {**fingerprint(archive), **json.loads(result.stdout)}


def build(root, base=None, output=None):
    root = Path(root).resolve()
    base = Path(base).resolve() if base else root / "downloads/complete-queries.zip"
    output = Path(output).resolve() if output else root / "downloads" / ARCHIVE_NAME
    if (
        output.name in {"complete-queries.zip", "substack-figures.zip"}
        or output == base
        or output.suffix != ".zip"
        or (output.exists() and output.name != ARCHIVE_NAME)
    ):
        raise ValueError("Will not replace a frozen or unrelated download")
    if fingerprint(base)["sha256"] != BASE_SHA256:
        raise ValueError("Unverified immutable V9 base archive")
    baseline = load_json(root / BASELINE, {})
    if not baseline.get("protected_sha256"):
        raise ValueError("Missing protected scientific baseline")
    verify_frozen(root, baseline)
    manifest_path = root / RESULTS / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for section in ("inputs", "files"):
        for name, receipt in manifest[section].items():
            if fingerprint(confined(root, name)) != receipt:
                raise ValueError(f"Stale factual checkpoint: {name}")
    overlays = {
        name: confined(root, name)
        for name in {
            *baseline["protected_sha256"],
            *manifest["inputs"],
            *manifest["files"],
            f"{RESULTS}/manifest.json",
        }
    }
    for pattern in (
        "data/biographical-research*.json",
        "data/biographical-retrievals.json",
        "which_candidate/biographical_*.py",
        "tests/test_biographical*.py",
        "docs/BIOGRAPHICAL_RESEARCH.md",
        "audits/biographical-research-browser.json",
        "README.md",
    ):
        overlays.update(
            (p.relative_to(root).as_posix(), p) for p in root.glob(pattern) if p.is_file()
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="biographical-package-", dir=output.parent) as temporary:
        pending = Path(temporary) / ARCHIVE_NAME
        with (
            zipfile.ZipFile(base) as original,
            zipfile.ZipFile(pending, "x", compression=zipfile.ZIP_DEFLATED) as package,
        ):
            names = original.namelist()
            if len(names) != len(set(names)):
                raise ValueError("Duplicate immutable archive member")
            for name in sorted(set(names) | overlays.keys()):
                confined(root, name)
                if name in overlays:
                    info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o644 << 16
                    body = overlays[name].read_bytes()
                else:
                    info = copy.copy(original.getinfo(name))
                    body = original.read(name)
                package.writestr(info, body)
        with zipfile.ZipFile(pending) as package:
            for name, digest in baseline["protected_sha256"].items():
                if hashlib.sha256(package.read(name)).hexdigest() != digest:
                    raise ValueError(f"Changed protected archive member: {name}")
            members = len(package.namelist())
        pending.replace(output)
    receipt = {
        "archive": output.relative_to(root).as_posix()
        if output.is_relative_to(root)
        else output.name,
        **fingerprint(output),
        "immutable_base_sha256": BASE_SHA256,
        "members": members,
        "protected_members_verified": len(baseline["protected_sha256"]),
        "overlay_files": {name: fingerprint(p) for name, p in sorted(overlays.items())},
        "factual_outputs_reconstructible_offline": True,
        "independent_reextraction_of_unretained_web_originals": False,
        "new_web_originals_redistributed": False,
        "acquisition_complete": load_json(root / RESULTS / "summary.json", {}).get(
            "acquisition_complete", False
        ),
    }
    (root / "audits").mkdir(exist_ok=True)
    write_json(root / "audits/biographical-research-package.json", receipt)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, help="Byte-verified immutable V9 query ZIP")
    parser.add_argument("--output", type=Path, help="Separate additive research ZIP")
    parser.add_argument(
        "--verify-offline", action="store_true", help="Extract and replay the new package offline"
    )
    parser.add_argument(
        "--verify-existing", type=Path, help="Replay an existing research ZIP without repackaging"
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.verify_existing:
        result = verify_offline(args.verify_existing)
    else:
        result = build(root, args.base, args.output)
        if args.verify_offline:
            result["offline_verification"] = verify_offline(
                args.output or root / "downloads" / ARCHIVE_NAME
            )
            write_json(root / "audits/biographical-research-package.json", result)
    print(json.dumps({k: v for k, v in result.items() if k != "overlay_files"}, indent=2))
