import json
import socket
import zipfile
from copy import deepcopy
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pytest
from matplotlib.colors import to_rgb
from PIL import Image
from scipy.stats import t

from which_candidate import publication
from which_candidate.pipeline import verify_output
from which_candidate.storage import fingerprint, read_rows

ROOT = Path(__file__).resolve().parents[1]
ANALYSIS = ROOT / "results/2026"


@pytest.mark.parametrize("model,scale", [("ideology", 0.1), ("defection", 5)])
def test_record_plot_uses_saved_sample_controls_covariance_and_native_units(model, scale):
    panel = []
    for i, lean in enumerate((-1, 0, 2)):
        focal = i + 1
        panel.append(
            {
                "D_candidate_election_id": str(i),
                "D_name": f"Candidate {i}",
                "state": ("CA", "NY", "WA")[i],
                "chamber": "house",
                "year": 2026,
                "eligible": True,
                "D_incumbent": True,
                "service_verified_incumbent": True,
                "presidential_D_two_party_share_pct": 50 + lean * 10,
                "nokken_poole_dim1": focal * 0.1,
                "party_unity_score": 1 - focal * 0.05,
                "descriptive_gap_share_pp": 10 + 3 * lean + 2 * lean**2 + 7 * focal,
            }
        )
    fit = {
        "model": model,
        "chamber": "house",
        "status": "estimated",
        "n": 3,
        "state_clusters": 3,
        "candidate_election_ids": ["2", "0", "1"],
        "terms": ["intercept", "lean_10pp", "lean_squared", publication.PRIMARY[model][0]],
        "coefficients": [10, 3, 2, 7],
        "covariance": np.diag([1, 0.25, 0.25, 1]).tolist(),
    }
    extra = {**panel[0], "D_candidate_election_id": "unselected", "year": 2024}
    records = publication.adjusted_record_data([extra, *panel], fit)
    points = [r for r in records if r["kind"] == "candidate"]
    line = [r for r in records if r["kind"] == "fitted_mean"]
    assert [r["candidate_election_id"] for r in points] == ["2", "0", "1"]
    np.testing.assert_allclose([r["x"] for r in points], np.array([3, 1, 2]) * scale)
    centered_intercept = 10 + 3 / 3 + 2 * 5 / 3
    np.testing.assert_allclose(
        [r["adjusted_gap_share_pp"] for r in points],
        centered_intercept + 7 * np.array([3, 1, 2]),
    )
    for row in line:
        focal = row["x"] / scale
        assert row["adjusted_gap_share_pp"] == pytest.approx(centered_intercept + 7 * focal)
        se = np.sqrt(1 + 0.25 * (1 / 3) ** 2 + 0.25 * (5 / 3) ** 2 + focal**2)
        assert row["ci_high"] - row["adjusted_gap_share_pp"] == pytest.approx(t.ppf(0.975, 2) * se)
    for invalid in (
        {**fit, "candidate_election_ids": ["0", "0", "1"]},
        {**fit, "candidate_election_ids": ["0", "1", "absent"]},
        {**fit, "terms": list(reversed(fit["terms"]))},
        {**fit, "status": "rank_deficient_or_ill_conditioned"},
    ):
        with pytest.raises(ValueError):
            publication.adjusted_record_data(panel, invalid)
    with pytest.raises(ValueError, match="2026 fit sample"):
        publication.adjusted_record_data([{**panel[0], "year": 2024}, *panel[1:]], fit)


def test_held_senate_gender_comparison_is_not_plotted_as_zero():
    fits = read_rows(ANALYSIS / "2026-model-fits.jsonl.gz")
    terms = read_rows(ANALYSIS / "2026-model-terms.jsonl.gz")
    with plt.rc_context(publication.THEME):
        fig, records, _ = publication.trait_chart(fits, terms, "senate")
    gender = next(r for r in records if r["model"] == "gender")
    assert gender["status"] != "estimated"
    assert "estimate_share_pp" not in gender
    ax = fig.axes[0]
    assert any(text.get_text() == "Not estimable" for text in ax.texts)
    assert not any(
        line.get_marker() == "o" and 0 in np.asarray(line.get_ydata()) for line in ax.lines
    )
    plt.close(fig)


def test_annual_comparisons_keep_current_fits_and_separate_historical_samples():
    panel = read_rows(ANALYSIS / "candidate-queries.jsonl.gz")
    current_fits = read_rows(ANALYSIS / "2026-model-fits.jsonl.gz")
    current_terms = read_rows(ANALYSIS / "2026-model-terms.jsonl.gz")
    fits, terms = publication.annual_comparisons(panel, current_fits, current_terms)
    assert {r["target_year"] for r in fits} == set(publication.YEARS)
    assert len({r["comparison_fit_id"] for r in fits}) == len(fits)
    for source, exported in ((current_fits, fits), (current_terms, terms)):
        current = [
            {k: v for k, v in r.items() if not k.startswith("comparison_")}
            for r in exported
            if r["target_year"] == 2026
        ]
        assert current == source
    by_id = {r["D_candidate_election_id"]: r for r in panel}
    for fit in fits:
        assert len(fit["candidate_election_ids"]) == fit["n"]
        assert all(by_id[i]["year"] == fit["target_year"] for i in fit["candidate_election_ids"])
        if fit["target_year"] != 2026:
            assert fit["comparison_role"] == "exploratory_historical"
    with plt.rc_context(publication.THEME):
        fig, records, caption = publication.history_chart(fits, terms, "senate")
    assert len(records) == 36
    held = [r for r in records if r["status"] != "estimated"]
    assert held and all("estimate_share_pp" not in row for row in held)
    assert "not paired-candidate changes" in caption
    plt.close(fig)
    wrong_benchmark = deepcopy(panel)
    next(r for r in wrong_benchmark if r["eligible"])["presidential_year"] = 1900
    with pytest.raises(ValueError, match="benchmark vintages changed"):
        publication.annual_comparisons(wrong_benchmark, current_fits, current_terms)


@pytest.fixture(scope="module")
def release(tmp_path_factory):
    destination = tmp_path_factory.mktemp("publication") / "2026-v1"
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            socket.socket,
            "connect",
            lambda *args: pytest.fail("Publication generation attempted network access"),
        )
        manifest = publication.build_publication(ANALYSIS, destination)
    return destination, manifest


def test_export_changes_only_exact_opaque_background_pixels(release):
    output, manifest = release
    old, new = (
        np.array([round(v * 255) for v in to_rgb(color)] + [255], dtype=np.uint8)
        for color in publication.BACKGROUNDS.values()
    )
    for chart in manifest["charts"]:
        with Image.open(output / chart["files"]["substack"]["png"]) as image:
            original = np.array(image.convert("RGBA"))
        with Image.open(output / chart["files"]["marginoferror"]["png"]) as image:
            themed = np.array(image.convert("RGBA"))
        assert themed.shape == original.shape
        mask = np.all(original == old, axis=2)
        assert mask.any() and (~mask).any()
        assert np.all(themed[mask] == new)
        np.testing.assert_array_equal(themed[~mask], original[~mask])
        assert themed.shape[:2] == (
            chart["files"]["marginoferror"]["height"],
            chart["files"]["marginoferror"]["width"],
        )


def test_complete_archives_retain_all_queries_code_tests_and_resolving_captions(release):
    output, manifest = release
    with zipfile.ZipFile(output / manifest["downloads"]["queries"]) as archive:
        for source in ANALYSIS.rglob("*"):
            if source.is_file():
                name = f"results/2026/{source.relative_to(ANALYSIS).as_posix()}"
                assert archive.read(name) == source.read_bytes()
        assert (
            archive.read("which_candidate/publication.py")
            == (ROOT / "which_candidate/publication.py").read_bytes()
        )
        assert "tests/test_publication.py" in archive.namelist()
        assert "requirements.lock" in archive.namelist()
        for name in ("annual-model-fits", "annual-model-terms"):
            for extension in ("csv", "jsonl.gz"):
                path = f"comparison/{name}.{extension}"
                assert archive.read(path) == (output / path).read_bytes()
        for chart in manifest["charts"]:
            assert archive.read(chart["data"]) == (output / chart["data"]).read_bytes()
    with zipfile.ZipFile(output / manifest["downloads"]["substack"]) as archive:
        assert (
            archive.read("complete-query-set.zip")
            == (output / manifest["downloads"]["queries"]).read_bytes()
        )
        for chart in json.loads(archive.read("captions.json")):
            for extension in ("png", "svg"):
                name = chart["files"]["substack"][extension]
                assert archive.read(name) == (output / name).read_bytes()
            assert chart["data"] in archive.namelist()


def test_publication_is_byte_reproducible_immutable_and_preserves_analysis(release, tmp_path):
    output, manifest = release
    before = {p: fingerprint(p) for p in ANALYSIS.rglob("*") if p.is_file()}
    second = tmp_path / "replay"
    assert publication.build_publication(ANALYSIS, second) == manifest
    for name in (*manifest["files"], "manifest.json"):
        assert (output / name).read_bytes() == (second / name).read_bytes()
    stamp = (output / "manifest.json").stat().st_mtime_ns
    assert publication.build_publication(ANALYSIS, output) == manifest
    assert (output / "manifest.json").stat().st_mtime_ns == stamp
    assert all(fingerprint(p) == expected for p, expected in before.items())
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(publication, "STYLE_REFERENCE", {"revision": "changed"})
        with pytest.raises(ValueError, match="new output directory"):
            publication.build_publication(ANALYSIS, output)
    (second / "captions.json").write_text("changed")
    with pytest.raises(ValueError, match="checksum mismatch"):
        verify_output(second)


def test_non_2026_saved_fit_is_rejected(monkeypatch, tmp_path):
    def wrong_year(path):
        rows = read_rows(path)
        if path.name == "2026-model-fits.jsonl.gz":
            rows = deepcopy(rows)
            rows[0]["target_year"] = 2024
        return rows

    monkeypatch.setattr(publication, "read_rows", wrong_year)
    with pytest.raises(ValueError, match="Non-2026 fit"):
        publication.build_publication(ANALYSIS, tmp_path / "wrong-year")


def test_site_staging_checks_bytes_and_refuses_overwrites(release, tmp_path):
    output, manifest = release
    site = tmp_path / "site"
    site.mkdir()
    (site / "astro.config.mjs").write_text("")
    target = publication.stage_site(output, site)
    assert verify_output(target) == manifest
    assert publication.stage_site(output, site) == target
    (target / "plot-data/house-characteristics.csv").write_text("changed")
    with pytest.raises(ValueError, match="checksum mismatch"):
        publication.stage_site(output, site)
