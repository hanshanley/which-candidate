import zipfile

import pytest

from which_candidate import biographical_package as package
from which_candidate.biographical_research import BASELINE, RESULTS
from which_candidate.storage import fingerprint, write_json


@pytest.fixture
def checkpoint(tmp_path, monkeypatch):
    for folder in ("data", "downloads", "results/frozen", RESULTS):
        (tmp_path / folder).mkdir(parents=True, exist_ok=True)
    protected = tmp_path / "results/frozen/fit.csv"
    protected.write_text("unchanged scientific fit\n")
    journal = tmp_path / "data/biographical-research.json"
    journal.write_text('{"documents": [{"value": "actual curated fact"}]}\n')
    derived = tmp_path / RESULTS / "summary.json"
    write_json(derived, {"acquisition_complete": False})
    write_json(
        tmp_path / BASELINE,
        {"protected_sha256": {"results/frozen/fit.csv": fingerprint(protected)["sha256"]}},
    )
    write_json(
        tmp_path / RESULTS / "manifest.json",
        {
            "inputs": {
                name: fingerprint(tmp_path / name)
                for name in (BASELINE, "data/biographical-research.json")
            },
            "files": {f"{RESULTS}/summary.json": fingerprint(derived)},
        },
    )
    base = tmp_path / "downloads/complete-queries.zip"
    with zipfile.ZipFile(base, "x") as archive:
        archive.writestr("retained-original", b"all immutable permitted inputs")
    monkeypatch.setattr(package, "BASE_SHA256", fingerprint(base)["sha256"])
    return tmp_path


def test_complete_inputs_and_missing_protected_member_are_packaged(checkpoint):
    base = checkpoint / "downloads/complete-queries.zip"
    before = fingerprint(base)
    first = package.build(checkpoint)
    with zipfile.ZipFile(checkpoint / first["archive"]) as archive:
        assert archive.read("retained-original") == b"all immutable permitted inputs"
        assert b"actual curated fact" in archive.read("data/biographical-research.json")
        assert archive.read("results/frozen/fit.csv") == b"unchanged scientific fit\n"
    assert fingerprint(base) == before
    assert not first["acquisition_complete"]
    assert not first["independent_reextraction_of_unretained_web_originals"]
    assert package.build(checkpoint)["sha256"] == first["sha256"]


@pytest.mark.parametrize("changed", ["base", "science", "factual"])
def test_changed_inputs_are_rejected(checkpoint, changed):
    target, message = {
        "base": ("downloads/complete-queries.zip", "immutable V9 base"),
        "science": ("results/frozen/fit.csv", "protected scientific"),
        "factual": (f"{RESULTS}/summary.json", "Stale factual checkpoint"),
    }[changed]
    with (checkpoint / target).open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(ValueError, match=message):
        package.build(checkpoint)


def test_frozen_download_cannot_be_overwritten(checkpoint):
    with pytest.raises(ValueError, match="Will not replace"):
        package.build(checkpoint, output=checkpoint / "downloads/complete-queries.zip")
