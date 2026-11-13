import json
import socket
from pathlib import Path

import openpyxl
import pytest
from test_fec import HEADER, candidate

from which_candidate.pipeline import build, csv_bytes, package, verify_output
from which_candidate.sources import load_sources
from which_candidate.storage import fingerprint, read_rows, write_json


def source_fixture(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    workbook = openpyxl.Workbook()
    workbook.remove(workbook.active)
    for chamber in ("Senate", "House"):
        sheet = workbook.create_sheet(f"2018 US {chamber} Results by State")
        sheet.append(HEADER)
        district = "S" if chamber == "Senate" else "01"
        sheet.append(candidate("Example, Jane", "D", 60, district=district))
        sheet.append(candidate("Example, John", "R", 40, fec_id="S0NY00002", district=district))
    path = data / "fixture.xlsx"
    workbook.save(path)
    workbook.close()
    manifest = data / "sources.json"
    write_json(
        manifest,
        {
            "schema": "which_candidate.sources.v1",
            "sources": [
                {
                    "id": "fec_2018",
                    "kind": "fec_workbook",
                    "year": 2018,
                    "path": "fixture.xlsx",
                    **fingerprint(path),
                }
            ],
        },
    )
    return manifest


def test_pipeline_replays_without_network_and_keeps_complete_decisions(tmp_path, monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("Network is forbidden in a rebuild")

    monkeypatch.setattr(socket, "socket", denied)
    monkeypatch.setattr(socket, "create_connection", denied)
    manifest = source_fixture(tmp_path)
    first, second = tmp_path / "first", tmp_path / "second"
    build(manifest, first)
    build(manifest, second)
    assert (first / "manifest.json").read_bytes() == (second / "manifest.json").read_bytes()
    for path in first.iterdir():
        assert path.read_bytes() == (second / path.name).read_bytes()
    assert len(read_rows(first / "candidate-returns.jsonl.gz")) == 4
    assert len(read_rows(first / "fec-row-decisions.jsonl.gz")) == 4
    assert build(manifest, first)["source_parses"] == 0


def test_corrupt_source_fails_before_build(tmp_path):
    manifest = source_fixture(tmp_path)
    (manifest.parent / "fixture.xlsx").write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="Source hash mismatch"):
        build(manifest, tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_corrupt_output_is_not_silently_overwritten(tmp_path):
    manifest = source_fixture(tmp_path)
    output = tmp_path / "output"
    build(manifest, output)
    (output / "coverage.json").write_text("{}")
    with pytest.raises(ValueError, match="Output checksum"):
        build(manifest, output)


def test_source_path_cannot_escape_manifest_directory(tmp_path):
    manifest = source_fixture(tmp_path)
    data = json.loads(manifest.read_bytes())
    data["sources"][0]["path"] = "../outside.xlsx"
    write_json(manifest, data)
    with pytest.raises(ValueError, match="escapes"):
        load_sources(manifest)


def test_csv_retains_fields_present_only_in_later_sources():
    result = csv_bytes([{"name": "first"}, {"name": "later", "provenance": "kept"}])
    assert result.decode() == "name,provenance\nfirst,\nlater,kept\n"


def test_complete_package_contains_inputs_code_queries_and_tests(tmp_path):
    import zipfile

    manifest = source_fixture(tmp_path)
    output, archive = tmp_path / "output", tmp_path / "complete.zip"
    build(manifest, output)
    root = Path(__file__).parents[1]
    result = package(root, manifest, output, archive)
    assert result["members"] > 10
    with zipfile.ZipFile(archive) as packed:
        names = packed.namelist()
        assert "data/fixture.xlsx" in names
        assert "data/processed/candidate-returns.jsonl.gz" in names
        assert "data/processed/fec-row-decisions.jsonl.gz" in names
        assert "which_candidate/fec.py" in names
        assert "tests/test_fec.py" in names
        assert not any(".venv" in name for name in names)
    verify_output(output)
