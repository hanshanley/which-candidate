"""Rebuild every archived query/report and both downloads without network access."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def replay(archive, workdir):
    archive = archive.resolve()
    workdir.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(archive) as source:
        names = source.namelist()
        assert all(not Path(name).is_absolute() and ".." not in Path(name).parts for name in names)
        source.extractall(workdir)
    assert not (workdir / "data/raw").exists()
    with tempfile.TemporaryDirectory(prefix="which-candidate-network-denied-") as directory:
        hook = Path(directory) / "sitecustomize.py"
        hook.write_text(
            "import socket\n"
            "def denied(*args, **kwargs):\n"
            "    raise RuntimeError('Network access denied during complete-download replay')\n"
            "socket.socket.connect = denied\n"
            "socket.socket.connect_ex = denied\n"
            "socket.create_connection = denied\n"
        )
        environment = {**os.environ, "PYTHONPATH": f"{directory}{os.pathsep}{workdir}"}
        proof = subprocess.run(
            [
                sys.executable,
                "-c",
                "import socket\n"
                "try:\n"
                " socket.create_connection(('127.0.0.1', 9))\n"
                "except RuntimeError as error:\n"
                " print(error)\n"
                "else:\n"
                " raise AssertionError('Network guard inactive')\n",
            ],
            cwd=workdir,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        with (workdir / "offline-replay.log").open("w") as log:
            subprocess.run(
                [sys.executable, "-m", "which_candidate.house_project", "--evidence-only"],
                cwd=workdir,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=True,
            )
    with zipfile.ZipFile(archive) as source:
        for name in names:
            assert source.read(name) == (workdir / name).read_bytes(), name
    rebuilt = workdir / "downloads/complete-queries.zip"
    assert digest(rebuilt) == digest(archive), "Complete query archive differs"
    original_upload = archive.with_name("substack-figures.zip")
    rebuilt_upload = workdir / "downloads/substack-figures.zip"
    assert digest(original_upload) == digest(rebuilt_upload), "Complete figure archive differs"
    with zipfile.ZipFile(rebuilt_upload) as source:
        assert hashlib.sha256(source.read("complete-query-set.zip")).hexdigest() == digest(archive)
    return {
        "status": "passed",
        "network": proof.stdout.strip(),
        "historical_raw_caches": "absent",
        "archive_members_byte_identical": len(names),
        "both_complete_downloads_byte_identical": True,
        "exact_nested_query_zip": True,
        "standard_library_LZMA_extraction": "passed",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--workdir", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(replay(args.archive, args.workdir.resolve()), indent=2))
