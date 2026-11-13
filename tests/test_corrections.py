from pathlib import Path

import numpy as np
import pytest
from scipy.stats import t

from which_candidate.corrected import (
    cast_unity,
    cross_fitted_values,
    robust_fit,
    same_name,
    validation_metrics,
)
from which_candidate.features import FeatureSources, name_matches


@pytest.mark.parametrize("native,expected", [(True, None), (False, False), (None, None)])
def test_unverified_native_positive_is_not_federal_incumbency(native, expected):
    sources = FeatureSources.__new__(FeatureSources)
    sources.people = {}
    sources.resolve = lambda row: {
        "native_incumbent": native,
        "bioguide_id": None,
        "roster_evidence": [],
    }
    row = {
        "candidate_election_id": "2026:house:CA:01:D",
        "year": 2026,
        "chamber": "house",
        "state": "CA",
        "party_group": "D",
        "name": "Mike McGuire",
        "election_date": "2026-11-03",
    }
    result = sources.features(row)
    assert result["incumbent"] is expected
    assert result["service_verified_incumbent"] is None


def test_federal_name_aliases_preserve_initial_and_familiar_middle_name():
    assert name_matches("Greg Steube", "W. Greg", "Steube")
    assert name_matches("W. Greg Steube", "W. Greg", "Steube")
    assert not name_matches("Greg Smith", "W. Greg", "Steube")
    assert same_name("Greg Steube", "STEUBE, W. Greg")
    assert same_name("Nick Langworthy", "LANGWORTHY, Nick")


def unity_example():
    members = [
        {
            "icpsr": str(i),
            "bioguide_id": f"B{i:06}",
            "party_code": "100" if i < 3 else "200",
            "bioname": f"MEMBER, Person{i}",
            "state_abbrev": "CA",
            "chamber": "House",
        }
        for i in range(1, 6)
    ]
    members.append({**members[-1], "icpsr": "99", "chamber": "President"})
    calls = [{"rollnumber": str(i), "date": "2026-10-30"} for i in range(1, 51)]
    calls.append({"rollnumber": "51", "date": "2026-11-04"})
    votes = [
        {
            "rollnumber": call["rollnumber"],
            "icpsr": member["icpsr"],
            "cast_code": "1" if member["icpsr"] in ("1", "2", "5", "99") else "6",
        }
        for call in calls
        for member in members
    ]
    return members, votes, calls


def test_cutoff_unity_excludes_postelection_and_presidential_positions():
    members, votes, calls = unity_example()
    result = {r["icpsr"]: r for r in cast_unity(members, votes, calls)}
    assert "99" not in result
    assert result["1"]["cast_votes"] == 50
    assert result["1"]["unity_votes"] == 50
    assert result["1"]["unity_score"] == 1
    assert result["5"]["unity_score"] == 0
    assert result["5"]["last_unity_vote"] == "2026-10-30"


def test_absence_is_not_a_defection_and_tied_parties_are_held():
    members, votes, calls = unity_example()
    for vote in votes:
        if vote["icpsr"] == "5":
            vote["cast_code"] = "9"
    result = {r["icpsr"]: r for r in cast_unity(members, votes, calls)}
    assert "5" not in result
    assert result["1"]["unity_votes"] == 50
    for vote in votes:
        if vote["icpsr"] == "4":
            vote["cast_code"] = "1"
    result = {r["icpsr"]: r for r in cast_unity(members, votes, calls)}
    assert result["1"]["unity_votes"] == 0
    assert result["1"]["unity_score"] is None


def test_duplicate_votes_fail_closed():
    members, votes, calls = unity_example()
    with pytest.raises(ValueError, match="Duplicate"):
        cast_unity(members, [*votes, votes[0]], calls)


def test_missing_or_duplicate_rollcall_dates_fail_closed():
    members, votes, calls = unity_example()
    with pytest.raises(ValueError, match="Duplicate"):
        cast_unity(members, votes, [*calls, calls[0]])
    calls[0]["date"] = ""
    with pytest.raises(ValueError, match="valid ISO date"):
        cast_unity(members, votes, calls)


def numerical_example(extreme=False):
    rng = np.random.default_rng(50)
    x = np.column_stack((np.ones(40), rng.normal(size=40)))
    if extreme:
        x[-1, 1] = 500
    states = [f"S{i // 2:02}" for i in range(40)]
    y = 1 + 0.7 * x[:, 1] + np.repeat(rng.normal(size=20), 2)
    rows = [
        {"state": state, "descriptive_gap_share_pp": float(v), "D_candidate_election_id": str(i)}
        for i, (state, v) in enumerate(zip(states, y))
    ]
    return rows, x, y, states


def test_cv3_and_sensitivity_envelope_are_independently_reproduced():
    rows, x, y, states = numerical_example()
    fit = robust_fit(rows, x, ["intercept", "trait"], "trait")
    beta = np.linalg.lstsq(x, y, rcond=None)[0][1]
    estimates = []
    for state in sorted(set(states)):
        keep = np.array([s != state for s in states])
        estimates.append(np.linalg.lstsq(x[keep], y[keep], rcond=None)[0][1])
    cv3 = np.sqrt(19 / 20 * np.sum((np.array(estimates) - beta) ** 2))
    se = max(cv3, fit["standard_errors"][1])
    assert fit["estimate_share_pp"] == pytest.approx(beta)
    assert fit["estimate_margin_pp"] == pytest.approx(2 * beta)
    assert fit["cv3_standard_error"] == pytest.approx(cv3)
    assert fit["ci_low"] == pytest.approx(beta - t.ppf(0.975, 19) * se)
    assert fit["publication_status"] == "supported_exploratory"


def test_high_leverage_is_diagnostic_not_a_headline():
    rows, x, _, _ = numerical_example(extreme=True)
    fit = robust_fit(rows, x, ["intercept", "trait"], "trait")
    assert fit["max_leverage"] > 0.8
    assert fit["publication_status"] == "diagnostic_only_low_support"


def test_cross_fitting_and_pipeline_deletions_never_train_on_test_state():
    rows, x, y, states = numerical_example()
    values = cross_fitted_values(rows, x)
    deleted = cross_fitted_values(rows, x, omitted="S00")
    assert np.isnan(deleted[:2]).all()
    for i, state in enumerate(states):
        keep = np.array([s != state for s in states])
        expected = y[i] - x[i] @ np.linalg.lstsq(x[keep], y[keep], rcond=None)[0]
        assert values[i] == pytest.approx(expected)
        if state != "S00":
            keep &= np.array([s != "S00" for s in states])
            expected = y[i] - x[i] @ np.linalg.lstsq(x[keep], y[keep], rcond=None)[0]
            assert deleted[i] == pytest.approx(expected)


def test_bias_sign_and_paired_lift_are_observed_minus_predicted():
    predictions = [
        {
            "kind": "chronological_state_held_out",
            "chamber": "house",
            "model": "incumbency",
            "year": 2026,
            "state": state,
            "observed_gap": 3,
            "baseline_predicted_gap": 1,
            "feature_predicted_gap": 2,
        }
        for state in ("CA", "NY", "WA")
    ]
    fit = validation_metrics(predictions)[0]
    assert fit["baseline_bias"] == 2
    assert fit["feature_bias"] == 1
    assert fit["mae_improvement"] == 1
    assert fit["conditional_paired_mae_lift_ci"] == [1, 1]


def test_coverage_axis_labels_are_actual_elections_not_decimal_years():
    import matplotlib.pyplot as plt

    from which_candidate.corrected_publication import record_coverage

    fig, _, _ = record_coverage({"candidate-queries": []})
    assert [t.get_text() for t in fig.axes[0].get_xticklabels()] == [
        "2016",
        "2018",
        "2020",
        "2022",
        "2024",
        "2026",
    ]
    plt.close(fig)


def test_frozen_v2_audit_inputs_remain_unchanged():
    import json

    from which_candidate.storage import fingerprint

    root = Path(__file__).resolve().parents[1]
    if not (root / "audits/2026-v2/audit-results.json").exists():
        pytest.skip("Repository-only v2 byte audit; offline packages verify their own manifests")
    audit = json.loads((root / "audits/2026-v2/audit-results.json").read_text())
    for name, sha256 in audit["input_sha256"].items():
        assert fingerprint(root / name)["sha256"] == sha256
    assert len(audit["input_sha256"]) == 120


def test_corrected_release_includes_complete_queries_and_all_plotted_values():
    import csv
    import zipfile

    from which_candidate.pipeline import verify_output
    from which_candidate.storage import read_rows

    root = Path(__file__).resolve().parents[1]
    publication = root / "publication/2026-v3"
    if not (publication / "manifest.json").exists():
        pytest.skip("Run after freezing the corrected publication")
    manifest = verify_output(publication)
    assert manifest["target_year"] == 2026
    assert manifest["supersedes"] == "2026-v2"
    assert len(manifest["charts"]) == 9
    with zipfile.ZipFile(publication / manifest["downloads"]["queries"]) as archive:
        for folder in ("results/2026-v3/inputs", "results/2026-v3/analysis"):
            for path in (root / folder).iterdir():
                assert archive.read(f"{folder}/{path.name}") == path.read_bytes()
        for chart in manifest["charts"]:
            with (publication / chart["data"]).open() as stream:
                assert len(list(csv.DictReader(stream))) == chart["plotted_records"]
    panel = read_rows(root / "results/2026-v3/analysis/candidate-queries.jsonl.gz")
    assert len([r for r in panel if r["year"] == 2026]) == 470
    assert sum(r["eligible"] for r in panel if r["year"] == 2026) == 433


def test_corrected_chart_background_conversion_preserves_all_other_pixels():
    import json

    from matplotlib.colors import to_rgb
    from PIL import Image

    from which_candidate.publication import BACKGROUNDS

    root = Path(__file__).resolve().parents[1]
    publication = root / "publication/2026-v3"
    if not (publication / "manifest.json").exists():
        pytest.skip("Run after freezing the corrected publication")
    manifest = json.loads((publication / "manifest.json").read_text())
    old = np.array([round(v * 255) for v in to_rgb(BACKGROUNDS["substack"])] + [255])
    new = np.array([round(v * 255) for v in to_rgb(BACKGROUNDS["marginoferror"])] + [255])
    for chart in manifest["charts"]:
        with Image.open(publication / chart["files"]["substack"]["png"]) as image:
            expected = np.array(image.convert("RGBA"))
        with Image.open(publication / chart["files"]["marginoferror"]["png"]) as image:
            actual = np.array(image.convert("RGBA"))
        mask = np.all(expected == old, axis=2)
        assert mask.any()
        expected[mask] = new
        np.testing.assert_array_equal(expected, actual)
