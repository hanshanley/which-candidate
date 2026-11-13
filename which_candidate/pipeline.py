import csv
import io
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

from .fec import extract_workbook
from .panel import audit_candidates, contest_panel, coverage, senate_benchmarks
from .sources import load_sources
from .storage import confined, fingerprint, write_json, write_rows


def code_receipts():
    root = Path(__file__).parent
    return {path.name: fingerprint(path) for path in sorted(root.glob("*.py"))}


def csv_bytes(rows):
    if not rows:
        return b""
    stream = io.StringIO(newline="")
    fields = list(dict.fromkeys(key for row in rows for key in row))
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                key: json.dumps(value, sort_keys=True) if isinstance(value, (list, dict)) else value
                for key, value in row.items()
            }
        )
    return stream.getvalue().encode()


def render_report(summary):
    lines = [
        "# Candidate returns: first research checkpoint",
        "",
        "**These are audited inputs, not conclusions about which kinds of Democrats do better.**",
        "",
        "| Year | Chamber | Candidate rows | Contests | Descriptive-share eligible |",
        "|---|---|---:|---:|---:|",
    ]
    for row in summary["groups"]:
        lines.append(
            f"| {row['year']} | {row['chamber']} | {row['candidate_rows']} | "
            f"{row['contests']} | {row['descriptive_share_eligible']} |"
        )
    lines.extend(
        [
            "",
            f"Retained {summary['native_fec_rows']:,} complete selected native FEC rows.",
            f"{summary['contests_with_reconciled_native_totals']:,} contests reconcile to "
            "a supplied native contest-total reference; "
            f"{summary['contests_with_native_total_mismatch']:,} mismatches are explicitly held.",
            "",
            f"The Senate pilot has {summary['eligible_senate_descriptive_gaps']} qualified "
            "descriptive presidential-benchmark gaps. These are not cycle-adjusted "
            "overperformance, forecasts, or causal candidate effects. Missing or excluded "
            "contests remain in the full query tables.",
            "",
            "## Remaining qualification",
            "",
        ]
    )
    lines.extend(f"- {limit}" for limit in summary["limits"])
    lines.extend(
        [
            "",
            "The 2026 House source is a held provider snapshot, not certified final returns. "
            "No new source acquisition or certification is implied by importing it.",
            "",
            "## Complete tables",
            "",
            "- `native-fec-rows.jsonl.gz`: every nonempty selected worksheet row and its cells.",
            "- `fec-row-decisions.jsonl.gz`: every non-header row's import disposition.",
            "- `candidate-returns.jsonl.gz` and `.csv`: every selected candidate aggregate.",
            "- `contests.jsonl.gz` and `.csv`: every contest, accounting result and exclusion.",
            "- `senate-benchmarks.jsonl.gz` and `.csv`: every Senate pilot decision, including holds.",
            "- `house-audit.json`: full unchanged previous/current all-district factual query.",
            "- `manifest.json`: exact source/code/output checksums.",
            "",
        ]
    )
    return "\n".join(lines)


def verify_output(output):
    output = Path(output)
    manifest = json.loads((output / "manifest.json").read_bytes())
    for relative, expected in manifest["files"].items():
        if fingerprint(confined(output, relative)) != expected:
            raise ValueError(f"Output checksum mismatch: {relative}")
    return manifest


def build(manifest_path, output):
    manifest_path, output = Path(manifest_path).resolve(), Path(output).resolve()
    sources = load_sources(manifest_path)
    recipe = {"source_manifest": fingerprint(manifest_path), "code": code_receipts()}
    if output.exists():
        previous = verify_output(output)
        if previous["recipe"] != recipe:
            raise ValueError("Changed inputs or code require a new output directory")
        return {"status": "verified_unchanged", "output": str(output), "source_parses": 0}
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".which-candidate-", dir=output.parent) as temp:
        destination = Path(temp)
        native, decisions, candidates, accounting = [], [], [], []
        for spec in sources["sources"]:
            path = confined(manifest_path.parent, spec["path"])
            if spec["kind"] == "fec_workbook":
                a, b, c, d = extract_workbook(path, spec)
                native.extend(a)
                decisions.extend(b)
                candidates.extend(c)
                accounting.extend(d)
            elif spec["kind"] == "house_audit":
                candidates.extend(audit_candidates(path, spec))
                shutil.copyfile(path, destination / "house-audit.json")
            else:
                raise ValueError(f"Unsupported source kind: {spec['kind']}")
        contests = contest_panel(candidates, accounting)
        benchmarks = senate_benchmarks(contests, candidates)
        summary = coverage(candidates, contests, native, decisions, benchmarks)
        tables = {
            "native-fec-rows": native,
            "fec-row-decisions": decisions,
            "native-contest-total-references": accounting,
            "candidate-returns": candidates,
            "contests": contests,
            "senate-benchmarks": benchmarks,
        }
        for name, rows in tables.items():
            write_rows(destination / f"{name}.jsonl.gz", rows)
            if name in ("candidate-returns", "contests", "senate-benchmarks"):
                (destination / f"{name}.csv").write_bytes(csv_bytes(rows))
        write_json(destination / "coverage.json", summary)
        (destination / "report.md").write_text(render_report(summary), encoding="utf-8")
        receipt = {
            "schema": "which_candidate.build.v1",
            "recipe": recipe,
            "sources": sources,
            "files": {path.name: fingerprint(path) for path in sorted(destination.iterdir())},
        }
        write_json(destination / "manifest.json", receipt)
        destination.rename(output)
    return {"status": "built", "output": str(output), "coverage": summary}


def package(project_root, manifest_path, output, archive_path):
    project_root = Path(project_root).resolve()
    manifest_path, output, archive_path = (
        Path(manifest_path).resolve(),
        Path(output).resolve(),
        Path(archive_path).resolve(),
    )
    sources = load_sources(manifest_path)
    built = verify_output(output)
    if built["recipe"] != {"source_manifest": fingerprint(manifest_path), "code": code_receipts()}:
        raise ValueError("Cannot package outputs from a different source/code recipe")
    if archive_path.exists():
        raise ValueError("Refusing to overwrite an existing research package")
    entries = {"data/sources.json": manifest_path}
    for spec in sources["sources"]:
        entries[f"data/{spec['path']}"] = confined(manifest_path.parent, spec["path"])
    for path in output.iterdir():
        if path.is_file():
            entries[f"data/processed/{path.name}"] = path
    for folder in ("which_candidate", "tests", "docs"):
        for path in sorted((project_root / folder).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix in (".py", ".md"):
                entries[path.relative_to(project_root).as_posix()] = path
    for name in ("pyproject.toml", "README.md", "requirements.lock"):
        path = project_root / name
        if path.exists():
            entries[name] = path
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, path in sorted(entries.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    return {"archive": str(archive_path), "members": len(entries), **fingerprint(archive_path)}
