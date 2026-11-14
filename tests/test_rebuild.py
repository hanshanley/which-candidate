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

from which_candidate import publication, rebuild, rebuild_package, rebuild_publication
from which_candidate.storage import fingerprint, read_rows, write_json

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "change",
    [
        {"year": "2024"},
        {"state": "NY"},
        {"office": "senate"},
        {"party": "R"},
        {"cand_id": "H00000002"},
        {"candidate": "Another Person"},
        {"district": "2"},
    ],
)
def test_website_match_requires_all_candidate_context(change):
    candidate = {
        "state": "CA",
        "chamber": "house",
        "district": 1,
        "D_fec_id": "H00000001",
        "D_name": "Jane Smith",
    }
    record = {
        "year": "2026",
        "state": "CA",
        "office": "house",
        "party": "D",
        "district": "01",
        "cand_id": "H00000001",
        "candidate": "Jane Smith",
    }
    assert rebuild.qualify_website(candidate, [record]) == record
    assert rebuild.qualify_website(candidate, [record, record]) is None
    assert rebuild.qualify_website(candidate, [{**record, **change}]) is None
    assert rebuild.qualify_website({**candidate, "D_fec_id": None}, [record]) is None
    assert (
        rebuild.qualify_website({**candidate, "district": 0}, [{**record, "district": "AL"}])
        is not None
    )


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        20261102000000,
        "20261103000000",
        "20261104000000",
        "20260230000000",
        "20261301000000",
        "20261032235959",
        "20261102235960",
        "19990101000000",
        "20261102",
        "２０２６１１０２００００００",
    ],
)
def test_invalid_or_late_capture_cannot_be_a_pre_election_feature(value):
    assert not rebuild.capture_before_cutoff(value)
    assert rebuild.capture_before_cutoff("20261102235959")


def test_fact_deduplication_is_stable_and_prefers_valid_earliest_capture():
    facts = [
        {
            "candidate_cycle_id": "c",
            "candidate_record_key": "k",
            "parent_document_id": parent,
            "record_id": record,
        }
        for parent, record in [("bad", "0"), ("later", "2"), ("early", "1")]
    ]
    documents = {
        parent: {"candidate_cycle_id": "c", "first_capture_timestamp": capture}
        for parent, capture in [
            ("bad", "00000000000000"),
            ("later", "20261104000000"),
            ("early", "20261101000000"),
        ]
    }
    expected = rebuild.unique_facts(facts, documents)
    assert expected == rebuild.unique_facts(list(reversed(facts)), documents)
    assert expected[0][0]["record_id"] == "1"
    with pytest.raises(ValueError, match="conflicting biography"):
        rebuild.unique_facts(facts, {**documents, "early": {"candidate_cycle_id": "wrong"}})


@pytest.mark.parametrize(
    "change",
    [
        {"score": float("nan")},
        {"score": float("inf")},
        {"score": True},
        {"cycle": 2026},
        {"cycle": 2023},
        {"cycle": 1900},
        {"cycle": True},
        {"name_screen": "alias_review"},
        {"status": "no_exact_fec_match"},
    ],
)
def test_donor_qualification_does_not_promote_bad_identity_or_vintage(change):
    value = {
        "status": "exact_fec_state_party_unique_person",
        "name_screen": "consistent",
        "score": -0.5,
        "cycle": 2024,
        "giver_counts": ["200", "100"],
    }
    assert rebuild.donor_decision({"dime": value}, 100)["qualified"]
    assert not rebuild.donor_decision({"dime": value}, 101)["qualified"]
    assert not rebuild.donor_decision({"dime": {**value, **change}})["qualified"]


def test_redundant_incumbency_controls_preserve_the_design_space():
    rows = [
        {
            "presidential_D_two_party_share_pct": 35 + i,
            "D_incumbent": True,
            "R_incumbent": False,
            "donor": {"score": np.sin(i)},
        }
        for i in range(20)
    ]
    design, names = rebuild.donor_design(rows)
    assert names == ["intercept", "lean_10pp", "lean_squared", "donor_rightward_05"]
    full = np.column_stack([design[:, :3], np.ones(20), np.zeros(20), design[:, -1]])
    outcome = np.cos(np.arange(20))
    np.testing.assert_allclose(
        design @ np.linalg.lstsq(design, outcome, rcond=None)[0],
        full @ np.linalg.lstsq(full, outcome, rcond=None)[0],
        atol=1e-12,
    )


def test_publisher_original_and_transformed_checksums_are_both_enforced(tmp_path, monkeypatch):
    import hashlib

    original, transformed = b"original-stata", b"served-table"
    (tmp_path / "rows.dta").write_bytes(original)
    (tmp_path / "rows.tab").write_bytes(transformed)
    write_json(
        tmp_path / "fake-catalog.json",
        {
            "data": {
                "latestVersion": {
                    "files": [
                        {
                            "dataFile": {
                                "id": 1,
                                "filename": "rows.tab",
                                "filesize": len(transformed),
                                "originalFileSize": len(original),
                                "checksum": {
                                    "type": "MD5",
                                    "value": hashlib.md5(original).hexdigest(),
                                },
                            }
                        }
                    ]
                }
            }
        },
    )
    monkeypatch.setattr(rebuild, "SOURCES", {"fake": ("doi", "license", {1: "rows.tab"})})
    monkeypatch.setattr(
        rebuild,
        "TABULAR",
        {"rows.tab": ("rows.dta", hashlib.sha256(transformed).hexdigest())},
    )
    receipts = rebuild.source_receipts(tmp_path)
    assert receipts[-1]["publisher_checksum_scope"] == "original_stata_not_transformed_tsv"
    (tmp_path / "rows.dta").write_bytes(b"X" + original[1:])
    with pytest.raises(ValueError, match="Publisher checksum mismatch"):
        rebuild.source_receipts(tmp_path)
    (tmp_path / "rows.dta").write_bytes(original)
    (tmp_path / "rows.tab").write_bytes(b"X" + transformed[1:])
    with pytest.raises(ValueError, match="transformed tabular source"):
        rebuild.source_receipts(tmp_path)


def test_state_deletion_rank_loss_suppresses_a_spurious_interval():
    rng = np.random.default_rng(42)
    rows = [
        {
            "state": f"S{i // 4}",
            "D_candidate_election_id": str(i),
            "D_incumbent": bool(i % 2),
            "R_incumbent": i < 4,
            "presidential_D_two_party_share_pct": 35 + i,
            "descriptive_gap_share_pp": float(rng.normal()),
            "donor": {"score": float(rng.normal())},
        }
        for i in range(40)
    ]
    x, names = rebuild.donor_design(rows)
    fit = rebuild.checked_fit(rows, x, names, names[-1])
    assert fit["status"] == "estimated"
    assert not fit["full_rank_state_deletions"]
    assert fit["publication_status"] == "diagnostic_only_rank_loss_on_state_deletion"
    assert fit["ci_low"] is fit["ci_high"] is None


@pytest.fixture(scope="module")
def release(tmp_path_factory):
    destination = tmp_path_factory.mktemp("rebuild")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            socket.socket,
            "connect",
            lambda *args: pytest.fail("Normalized replay attempted network access"),
        )
        rebuild.replay(ROOT, destination / "analysis")
        rebuild_publication.build(ROOT, destination / "figures")
        manifest = json.loads((destination / "figures/manifest.json").read_text())
    return destination, manifest


def test_complete_normalized_replay_preserves_all_rows_and_holds(release):
    destination, _ = release
    original = ROOT / "results/2026-v4"
    for path in original.iterdir():
        if path.is_file():
            assert (destination / "analysis" / path.name).read_bytes() == path.read_bytes()
    panel = read_rows(original / "candidate-queries.jsonl.gz")
    assert len(panel) == len({r["contest_id"] for r in panel}) == 470
    assert sum(r["eligible"] for r in panel) == 433
    assert all("cross_fitted_expected_share_pct" not in r for r in panel)
    assert all("archived_prediction_provenance" in r for r in panel)
    assert all(not r["website"]["labels_promoted"] for r in panel)
    facts = read_rows(original / "biography-facts.jsonl.gz")
    assert all(not r["model_ready"] and not r["sensitive_identity_labels_inferred"] for r in facts)
    assert all("evidence" not in r for r in facts)
    by_id = {r["D_candidate_election_id"]: r for r in panel}
    for fact in facts:
        row = by_id[fact["candidate_election_id"]]
        assert fact["record_id"] in row["website"]["biography_record_ids"]
        assert fact["captured_before_election"] == rebuild.capture_before_cutoff(
            fact["first_capture_timestamp"]
        )
    coverage = json.loads((original / "coverage.json").read_text())
    cohorts = {r["cohort"]: r["nominees"] for r in coverage}
    assert cohorts["all_named"] == sum(
        cohorts[key]
        for key in [
            "won_two_party_comparison",
            "lost_two_party_comparison",
            "unknown_two_party_comparison",
        ]
    )


def test_common_benchmark_fits_use_identical_ids_and_independent_ols():
    panel = read_rows(ROOT / "results/2026-v4/candidate-queries.jsonl.gz")
    by_id = {r["D_candidate_election_id"]: r for r in panel}
    fits = read_rows(ROOT / "results/2026-v4/donor-fits.jsonl.gz")
    variants = {r["variant"]: r for r in fits if r["chamber"] == "house"}
    assert (
        variants["current_benchmark_common_sample"]["candidate_election_ids"]
        == (variants["previous_benchmark_common_sample"]["candidate_election_ids"])
    )
    for fit in variants.values():
        rows = [deepcopy(by_id[key]) for key in fit["candidate_election_ids"]]
        if fit["variant"] == "previous_benchmark_common_sample":
            for row in rows:
                row["presidential_D_two_party_share_pct"] = row["previous_presidential_share"]
                row["descriptive_gap_share_pp"] = (
                    row["D_two_party_share_pct"] - row["previous_presidential_share"]
                )
        lean = np.array([(r["presidential_D_two_party_share_pct"] - 50) / 10 for r in rows])
        x = np.column_stack(
            [
                np.ones(len(rows)),
                lean,
                lean**2,
                [int(r["D_incumbent"]) for r in rows],
                [int(r["R_incumbent"]) for r in rows],
                [r["donor"]["score"] / 0.5 for r in rows],
            ]
        )
        beta = np.linalg.lstsq(x, [r["descriptive_gap_share_pp"] for r in rows], rcond=None)[0]
        assert fit["estimate_share_pp"] == pytest.approx(beta[-1], abs=1e-10)
        assert fit["estimate_margin_pp"] == pytest.approx(2 * beta[-1])
        assert fit["ci_low_margin_pp"] == pytest.approx(2 * fit["ci_low_share_pp"])


def test_measurement_audit_holds_samples_controls_and_score_increments_fixed():
    panel = read_rows(ROOT / "results/2026-v4/candidate-queries.jsonl.gz")
    by_id = {r["D_candidate_election_id"]: r for r in panel}
    fits = read_rows(ROOT / "results/2026-v4/measurement-fits.jsonl.gz")
    ids = fits[0]["candidate_election_ids"]
    assert all(f["candidate_election_ids"] == ids for f in fits)
    rows = [by_id[key] for key in ids]
    assert all(r["D_incumbent"] and r["service_verified_incumbent"] for r in rows)
    lean = np.array([(r["presidential_D_two_party_share_pct"] - 50) / 10 for r in rows])
    controls = np.column_stack(
        [
            np.ones(len(rows)),
            lean,
            lean**2,
            [int(r["R_incumbent"]) for r in rows],
        ]
    )
    donor = np.array([r["donor"]["score"] / 0.5 for r in rows])
    voting = np.array([r["nokken_poole_dim1"] / 0.1 for r in rows])
    outcome = [r["descriptive_gap_share_pp"] for r in rows]
    for fit in fits:
        joint = fit["variant"].startswith("joint")
        x = (
            np.column_stack([controls, donor, voting])
            if joint
            else np.column_stack(
                [
                    controls,
                    voting if fit["variant"] == "voting" else donor,
                ]
            )
        )
        beta = np.linalg.lstsq(x, outcome, rcond=None)[0]
        index = -2 if fit["variant"] == "joint_donor" else -1
        assert fit["estimate_share_pp"] == pytest.approx(beta[index], abs=1e-10)


def test_reported_intervals_reconstruct_from_cluster_scores_and_full_state_deletions():
    by_id = {
        r["D_candidate_election_id"]: r
        for r in read_rows(ROOT / "results/2026-v4/candidate-queries.jsonl.gz")
    }
    fits = [
        r
        for name in ("donor-fits", "measurement-fits")
        for r in read_rows(ROOT / f"results/2026-v4/{name}.jsonl.gz")
        if r["chamber"] == "house" and r["status"] == "estimated"
    ]
    for fit in fits:
        rows = [by_id[key] for key in fit["candidate_election_ids"]]
        previous = fit["variant"] == "previous_benchmark_common_sample"
        baseline = np.array(
            [
                r["previous_presidential_share"]
                if previous
                else r["presidential_D_two_party_share_pct"]
                for r in rows
            ]
        )
        lean = (baseline - 50) / 10
        features = {
            "intercept": np.ones(len(rows)),
            "lean_10pp": lean,
            "lean_squared": lean**2,
            "D_incumbent": [int(r["D_incumbent"]) for r in rows],
            "R_incumbent": [int(r["R_incumbent"]) for r in rows],
            "donor_rightward_05": [r["donor"]["score"] / 0.5 for r in rows],
            "voting_rightward_01": [
                r["nokken_poole_dim1"] / 0.1 if r["nokken_poole_dim1"] is not None else 0
                for r in rows
            ],
        }
        x = np.column_stack([features[key] for key in fit["terms"]])
        y = np.array([r["D_two_party_share_pct"] for r in rows]) - baseline
        beta = np.linalg.solve(x.T @ x, x.T @ y)
        residual = y - x @ beta
        states = np.array([r["state"] for r in rows])
        groups = sorted(set(states))
        scores = [x[states == state].T @ residual[states == state] for state in groups]
        bread = np.linalg.inv(x.T @ x)
        n, k = x.shape
        g = len(groups)
        covariance = bread @ sum(np.outer(s, s) for s in scores) @ bread
        covariance *= g / (g - 1) * (n - 1) / (n - k)
        j = fit["terms"].index(fit["focal_term"])
        deleted = np.array(
            [
                np.linalg.lstsq(x[states != state], y[states != state], rcond=None)[0][j]
                for state in groups
            ]
        )
        cv3 = np.sqrt((g - 1) / g * np.sum((deleted - beta[j]) ** 2))
        width = t.ppf(0.975, g - 1) * max(np.sqrt(covariance[j, j]), cv3)
        assert fit["ci_low"] == pytest.approx(beta[j] - width, abs=1e-8)
        assert fit["ci_high"] == pytest.approx(beta[j] + width, abs=1e-8)


def test_sparse_donor_interval_and_missing_rosters_are_not_misleading():
    data = {
        "donor": read_rows(ROOT / "results/2026-v4/donor-fits.jsonl.gz"),
        "moderation": read_rows(ROOT / "results/2026-v3/analysis/moderation-fits.jsonl.gz"),
    }
    with plt.rc_context(publication.THEME):
        fig, rows, _ = rebuild_publication.donor(data)
        assert len(rows) == 5
        assert any(t.get_text() == "Low support; see CSV" for t in fig.axes[0].texts)
        assert len(fig.axes[0].containers) == 4
        assert fig.axes[0].dataLim.xmin > -20
        plt.close(fig)
        fig, _, _ = rebuild_publication.caucus(data)
        assert sum(t.get_text() == "Roster unavailable" for t in fig.axes[0].texts) == 2
        assert all("0 Blue Dogs" not in t.get_text() for t in fig.texts)
        plt.close(fig)


def test_figure_bytes_backgrounds_and_sizes_are_reproducible(release):
    destination, manifest = release
    original = ROOT / "publication/2026-v4"
    output = destination / "figures"
    for name in (*manifest["files"], "manifest.json"):
        assert (output / name).read_bytes() == (original / name).read_bytes()
    backgrounds = [
        np.array([round(v * 255) for v in to_rgb(color)] + [255], dtype=np.uint8)
        for color in publication.BACKGROUNDS.values()
    ]
    for chart in manifest["charts"]:
        with Image.open(output / chart["files"]["substack"]["png"]) as image:
            a = np.array(image.convert("RGBA"))
        with Image.open(output / chart["files"]["marginoferror"]["png"]) as image:
            b = np.array(image.convert("RGBA"))
        assert a.shape == b.shape == (1300, 2000, 4)
        mask = np.all(a == backgrounds[0], axis=2)
        assert mask.any() and (~mask).any()
        assert np.all(b[mask] == backgrounds[1])
        np.testing.assert_array_equal(a[~mask], b[~mask])


def test_existing_output_cannot_be_silently_overwritten(release, tmp_path):
    destination, _ = release
    output = destination / "analysis"
    path = output / "manifest.json"
    stamp = path.stat().st_mtime_ns
    rebuild.replay(ROOT, output)
    assert path.stat().st_mtime_ns == stamp
    staged = tmp_path / "staged"
    staged.mkdir()
    (staged / "manifest.json").write_text("different")
    before = fingerprint(path)
    with pytest.raises(ValueError, match="new output directory"):
        rebuild.persist_directory(staged, output)
    assert fingerprint(path) == before


def test_public_packages_include_entire_queries_evidence_and_embedded_download(tmp_path):
    output = tmp_path / "downloads"
    receipts = rebuild_package.build(ROOT, output)
    queries = output / "2026-v4-complete-queries.zip"
    with zipfile.ZipFile(queries) as archive:
        assert len(archive.namelist()) == len(set(archive.namelist()))
        for folder in ("results", "publication/2026-v4"):
            for path in (ROOT / folder).rglob("*"):
                if path.is_file() and path.suffix != ".zip":
                    assert archive.read(path.relative_to(ROOT).as_posix()) == path.read_bytes()
        assert ".github/skills/publication-charts/SKILL.md" in archive.namelist()
        assert "tests/test_rebuild.py" in archive.namelist()
        assert all(not name.startswith("data/raw/") for name in archive.namelist())
    with zipfile.ZipFile(output / "2026-v4-substack-figures.zip") as archive:
        assert archive.read("complete-query-set.zip") == queries.read_bytes()
        assert all(not name.startswith("marginoferror/") for name in archive.namelist())
    assert all(fingerprint(output / name) == receipt for name, receipt in receipts.items())


def test_failed_packaging_never_publishes_partial_downloads(tmp_path, monkeypatch):
    calls = []

    def fail_second_archive(path, entries):
        calls.append(path)
        if len(calls) == 2:
            raise OSError("no space left")
        path.write_bytes(b"staged archive")

    monkeypatch.setattr(rebuild_package, "write_zip", fail_second_archive)
    with pytest.raises(OSError, match="no space"):
        rebuild_package.build(ROOT, tmp_path / "downloads")
    assert not list((tmp_path / "downloads").iterdir())


def test_refined_measurement_panels_share_a_centered_scale_without_clipping_intervals():
    data = {"measurements": read_rows(ROOT / "results/2026-v4/measurement-fits.jsonl.gz")}
    with plt.rc_context(publication.THEME):
        fig, rows, _ = rebuild_publication.refined_measurements(data)
        limits = fig.axes[0].get_xlim()
        assert all(ax.get_xlim() == limits for ax in fig.axes)
        assert limits[0] == -limits[1]
        for ax in fig.axes:
            assert ax.transData.transform((0, 0))[0] == pytest.approx(
                ax.bbox.x0 + ax.bbox.width / 2
            )
        assert all(limits[0] < 2 * r["ci_low"] < 2 * r["ci_high"] < limits[1] for r in rows)
        plt.close(fig)


@pytest.mark.parametrize(
    ("key", "source", "builder", "label"),
    [
        (
            "donor",
            "results/2026-v4/donor-fits.jsonl.gz",
            rebuild_publication.refined_donor,
            "Low support; see CSV",
        ),
        (
            "moderation",
            "results/2026-v3/analysis/moderation-fits.jsonl.gz",
            rebuild_publication.refined_caucus,
            "Roster unavailable",
        ),
    ],
)
def test_refined_diagnostic_labels_are_clear_of_the_zero_line(key, source, builder, label):
    data = {key: read_rows(ROOT / source)}
    with plt.rc_context(publication.THEME):
        fig, _, _ = builder(data)
        fig.canvas.draw()
        ax = fig.axes[0]
        zero_x = ax.transData.transform((0, 0))[0]
        labels = [text for text in ax.texts if text.get_text() == label]
        assert labels
        for text in labels:
            box = text.get_window_extent(fig.canvas.get_renderer())
            assert zero_x < box.x0 < box.x1 < ax.bbox.x1
        assert len(ax.containers) == 4
        plt.close(fig)


def test_visual_revision_preserves_data_and_embeds_complete_versioned_queries(tmp_path):
    output = tmp_path / "figures"
    charts = rebuild_publication.build(ROOT, output, version="2026-v5")
    for chart in charts:
        name = chart["id"]
        assert (output / chart["data"]).read_bytes() == (
            ROOT / "publication/2026-v4" / chart["data"]
        ).read_bytes()
        if name not in ("donor-ideology", "ideology-measurement", "caucus-history"):
            for theme in publication.BACKGROUNDS:
                relative = f"{theme}/{name}.png"
                assert (output / relative).read_bytes() == (
                    ROOT / "publication/2026-v4" / relative
                ).read_bytes()
    canonical = ROOT / "publication/2026-v5"
    for path in output.rglob("*"):
        if path.is_file():
            assert path.read_bytes() == (canonical / path.relative_to(output)).read_bytes()
    downloads = tmp_path / "downloads"
    rebuild_package.build(ROOT, downloads, version="2026-v5")
    queries = downloads / "2026-v5-complete-queries.zip"
    with zipfile.ZipFile(queries) as archive:
        assert (
            archive.read("publication/2026-v5/substack/ideology-measurement.png")
            == (output / "substack/ideology-measurement.png").read_bytes()
        )
        assert "results/2026-v4/candidate-queries.jsonl.gz" in archive.namelist()
        assert "results/2026-v4/biography-facts.jsonl.gz" in archive.namelist()
        assert (
            archive.read("publication/2026-v4/substack/ideology-measurement.png")
            == (ROOT / "publication/2026-v4/substack/ideology-measurement.png").read_bytes()
        )
    with zipfile.ZipFile(downloads / "2026-v5-substack-figures.zip") as archive:
        assert archive.read("complete-query-set.zip") == queries.read_bytes()


@pytest.mark.parametrize("builder", [rebuild_publication.build, rebuild_package.build])
def test_unknown_visual_version_cannot_create_output(builder, tmp_path):
    output = tmp_path / "invalid"
    with pytest.raises(ValueError, match="Unknown figure version"):
        builder(ROOT, output, version="../changed")
    assert not output.exists()
