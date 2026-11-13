import argparse
import json
from pathlib import Path

from .pipeline import build, package, verify_output
from .sources import import_participation


def main(argv=None):
    parser = argparse.ArgumentParser(description="Auditable candidate-performance research")
    commands = parser.add_subparsers(dest="command", required=True)
    importer = commands.add_parser("import-participation", help="Copy and pin held source facts")
    importer.add_argument("--source", type=Path, required=True)
    importer.add_argument("--data-dir", type=Path, default=Path("data"))
    builder = commands.add_parser("build", help="Build complete audited queries without network")
    builder.add_argument("--manifest", type=Path, default=Path("data/sources.json"))
    builder.add_argument("--output", type=Path, default=Path("data/processed"))
    verifier = commands.add_parser("verify", help="Verify every generated output hash")
    verifier.add_argument("--output", type=Path, default=Path("data/processed"))
    packager = commands.add_parser(
        "package", help="Package all selected inputs, queries, code and tests"
    )
    packager.add_argument("--manifest", type=Path, default=Path("data/sources.json"))
    packager.add_argument("--output", type=Path, default=Path("data/processed"))
    packager.add_argument("--archive", type=Path, default=Path("artifacts/complete-analysis.zip"))
    packager.add_argument("--project-root", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    try:
        if args.command == "import-participation":
            result = import_participation(args.source, args.data_dir)
        elif args.command == "build":
            result = build(args.manifest, args.output)
        elif args.command == "verify":
            manifest = verify_output(args.output)
            result = {"status": "verified", "files": len(manifest["files"])}
        else:
            result = package(args.project_root, args.manifest, args.output, args.archive)
    except (ValueError, FileNotFoundError, KeyError) as error:
        parser.exit(1, f"error: {error}\n")
    print(json.dumps(result, indent=2, sort_keys=True))
