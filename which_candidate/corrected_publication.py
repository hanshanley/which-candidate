"""Evidence-led corrected figures and complete, network-independent replay packages."""

import argparse
import json
import tempfile
import textwrap
from collections import Counter
from pathlib import Path

import matplotlib.pyplot as plt

from .demographics import RACE_CONTROLS
from .models import available
from .pipeline import csv_bytes, verify_output
from .publication import (
    ACCENT,
    BLUE,
    INK,
    MUTED,
    THEME,
    export_chart,
    tidy,
    write_zip,
)
from .storage import fingerprint, read_rows, write_json

LABELS = {
    "incumbency": "Democratic incumbent",
    "ideology": "118th ideology (+0.1 rightward)",
    "defection": "Cutoff defection (+1 pp)",
    "age": "Age (+10 years)",
    "tenure": "Federal tenure (+10 years)",
    "gender": "Source-recorded F versus M",
}
CLOCK = "Fresh provider counts acquired November 13, 2026. Native clocks retained; not certified."


def frame(title, subtitle, source, height=7.8):
    fig = plt.figure(figsize=(12.8, height), dpi=200)
    fig.text(0.055, 0.955, title, fontsize=21, weight="bold", va="top")
    fig.text(0.055, 0.886, textwrap.fill(subtitle, 116), fontsize=11.5, color=MUTED, va="top")
    fig.text(0.055, 0.117, CLOCK, fontsize=9, color=MUTED)
    fig.text(
        0.055,
        0.038,
        textwrap.fill(source, 164),
        fontsize=8.5,
        color=MUTED,
        style="italic",
        va="bottom",
    )
    return fig


def flat(row):
    return {k: v for k, v in row.items() if not isinstance(v, (dict, list))}


def dot(ax, row, y, color=ACCENT, scale=2, hollow=False):
    estimate, low, high = (row.get(k) for k in ("estimate_share_pp", "ci_low", "ci_high"))
    if any(v is None for v in (estimate, low, high)):
        return
    ax.errorbar(
        scale * estimate,
        y,
        xerr=[[scale * (estimate - low)], [scale * (high - estimate)]],
        fmt="o",
        color=color,
        markerfacecolor="none" if hollow else color,
        markersize=6,
        linewidth=1.5,
        capsize=3,
    )


def forest(ax, labels, xlabel="Association with D-minus-R margin (pp)"):
    ax.axvline(0, color=MUTED, linewidth=0.8)
    ax.set_yticks(range(len(labels)), labels)
    ax.set_ylim(len(labels) - 0.4, -0.8)
    ax.set_xlabel(xlabel, fontsize=11, labelpad=12)
    tidy(ax)


def traits(data):
    records = [
        r
        for r in data["trait-fits"]
        if r["year"] == 2026 and r["chamber"] == "house" and r["variant"] == "primary"
    ]
    if any(r.get("holm_pvalue", 1) < 0.05 for r in records):
        raise ValueError("Review the headline: a corrected result now clears Holm")
    senate = [
        r
        for r in data["trait-fits"]
        if r["year"] == 2026 and r["chamber"] == "senate" and r["variant"] == "primary"
    ]
    fig = frame(
        "2026 House: none clears the six-test correction",
        "Corrected incumbency and cutoff-only voting evidence. Pointwise sensitivity envelopes "
        "are shown, not simultaneous confidence intervals or causal candidate effects.",
        "Outcome: congressional minus 2024 presidential share on the 2026 map; lean-adjusted. "
        "Except incumbency, verified D incumbents only. Envelopes use max(CR1, CV3) with t(G-1). "
        "Senate slopes are held from headline inference: "
        f"{next(r['n'] for r in senate if r['model'] == 'incumbency')} incumbency cases, "
        f"{next(r['n'] for r in senate if r['model'] == 'ideology')} ideology cases.",
    )
    ax = fig.add_axes((0.285, 0.27, 0.40, 0.49))
    for i, row in enumerate(records):
        dot(ax, row, i, hollow=row.get("publication_status") != "supported_exploratory")
        estimate = row.get("estimate_margin_pp")
        p = row.get("holm_pvalue")
        ax.text(
            1.06,
            i,
            f"{estimate:+.2f} margin pp\nN={row['n']}; "
            f"{row['state_clusters']} states; Holm p={p:.3f}",
            transform=ax.get_yaxis_transform(),
            va="center",
            fontsize=10,
        )
    forest(ax, [LABELS[r["model"]] for r in records])
    return (
        fig,
        [flat(r) for r in records],
        (
            "Six exploratory primary House associations, not interchangeable measures of moderation. "
            "The ideology score is from the 118th Congress (2023–24); defection uses actual cast votes "
            "before November 3, 2026, from the 119th. One share point equals two margin points. "
            "Sparse Senate estimates remain in the complete download, not as headline slopes."
        ),
    )


def caucus_history(data):
    records = [
        r
        for r in data["moderation-fits"]
        if r["comparison"] == "blue_dog_vs_cpc"
        and r["method"] == "cross_fitted_structural"
        and r["variant"] == "lean_incumbency"
        and r["year"] >= 2020
    ]
    fig = frame(
        "A moderation advantage is not precisely established",
        "Blue Dog minus Progressive Caucus structural performance, in margin points. "
        "The 2026 point estimate is larger—not evidence of a smaller advantage.",
        "House incumbent nominees only, including losers; overlapping memberships excluded. "
        "Blue Dog rosters are retrospective full-Congress lists; CPC rosters are pre-election "
        "archives. State-held-out lean/incumbency baseline; full-pipeline state-deletion "
        "sensitivity envelopes. Not Split Ticket WAR or a test of change between years.",
    )
    ax = fig.add_axes((0.15, 0.27, 0.48, 0.49))
    for i, row in enumerate(records):
        sparse = row.get("publication_status") != "supported_exploratory"
        dot(ax, row, i, color=ACCENT if row["year"] == 2026 else BLUE, hollow=sparse)
        support = row["group_support"]
        ax.text(
            1.05,
            i,
            f"Blue {support['blue']['people']} / CPC {support['reference']['people']}\n"
            + ("Sparse: diagnostic only" if sparse else "Exploratory; envelope includes zero"),
            transform=ax.get_yaxis_transform(),
            va="center",
            fontsize=10,
        )
    forest(ax, [str(r["year"]) for r in records], "Blue Dog minus CPC residual margin (pp)")
    return (
        fig,
        [
            {
                **flat(r),
                "blue_people": r["group_support"]["blue"]["people"],
                "cpc_people": r["group_support"]["reference"]["people"],
            }
            for r in records
        ],
        (
            "Hollow dots fail the minimum of ten people and five states in each group. "
            "Only eight qualifying Blue Dogs support the full 2026 contrast. Qualified CPC archives "
            "start in 2020, so 2016/2018 CPC contrasts are held, not reconstructed from today's roster. "
            "These differing cohorts and benchmark vintages cannot establish a historical trend."
        ),
    )


def caucus_sensitivity(data):
    records = [
        r
        for r in data["moderation-fits"]
        if r["year"] == 2026
        and r["comparison"] == "blue_dog_vs_cpc"
        and r["method"] == "cross_fitted_structural"
    ]
    labels = {
        "lean_incumbency": "All qualified baseline rows",
        "lean_incumbency_same_swing_sample": "Same-map subset, no swing",
        "same_map_swing": "Same-map subset, add swing",
    }
    fig = frame(
        "Missing benchmark coverage changes the comparison",
        "Separate the effect of dropping candidates from the effect of adding presidential swing. "
        "The two subset fits use exactly the same candidates and baseline training races.",
        "Full baseline: presidential lean, lean squared, D/R incumbency. Added swing: 2024 "
        "minus qualified 2020 presidential share on the actual 2026 map. Missing changed-map "
        "cells are never imputed. All three 2026 caucus contrasts remain sparse diagnostics.",
    )
    ax = fig.add_axes((0.30, 0.31, 0.36, 0.43))
    for i, row in enumerate(records):
        dot(ax, row, i, hollow=True, color=ACCENT if i == 0 else BLUE)
        support = row["group_support"]
        ax.text(
            1.06,
            i,
            f"{row['estimate_margin_pp']:+.2f} margin pp\n"
            f"Blue {support['blue']['people']} / CPC {support['reference']['people']}",
            transform=ax.get_yaxis_transform(),
            va="center",
            fontsize=10,
        )
    forest(ax, [labels[r["variant"]] for r in records], "Blue Dog minus CPC residual margin (pp)")
    return (
        fig,
        [flat(r) for r in records],
        (
            "The same-map subset does not represent the full caucuses. Read its no-swing estimate "
            "against its swing-adjusted estimate, not against the full-sample estimate, to isolate "
            "the added control. Neither these residuals nor the separate joint regressions are "
            "a replication of the article's proprietary WAR estimates."
        ),
    )


def record_coverage(data):
    panel = data["candidate-queries"]
    rows = []
    for year in (2016, 2018, 2020, 2022, 2024, 2026):
        all_rows = [r for r in panel if r["year"] == year and r["chamber"] == "house"]
        for model in ("eligible", "incumbency", "ideology", "defection"):
            count = sum(
                r["eligible"] if model == "eligible" else available(r, model) for r in all_rows
            )
            rows.append({"year": year, "measure": model, "candidates": count})
    fig = frame(
        "Voting records describe a selective slice of nominees",
        "House coverage, 2016–2026. New federal members can have current-term votes without "
        "a prior-Congress ideology score; challengers are not assigned zero ideology.",
        "Eligibility includes named positive D/R nominees, qualified maps and accounting/stage "
        "holds. Incumbency requires known D/R service status. Ideology is prior-Congress; "
        "2026 defection is cutoff-only current-Congress, unlike historical lagged records.",
    )
    ax = fig.add_axes((0.12, 0.27, 0.72, 0.47))
    labels = {
        "eligible": "Eligible contests",
        "incumbency": "Known D/R incumbency",
        "ideology": "Prior-Congress ideology",
        "defection": "Party-vote record",
    }
    for measure, color, marker in zip(labels, (INK, MUTED, BLUE, ACCENT), ("o", "s", "D", "^")):
        values = [r for r in rows if r["measure"] == measure]
        ax.plot(
            [r["year"] for r in values],
            [r["candidates"] for r in values],
            color=color,
            marker=marker,
            label=labels[measure],
            linewidth=1.4,
        )
    ax.set_ylim(0, 450)
    ax.set_ylabel("Candidates / contests")
    ax.legend(frameon=False, fontsize=10, ncol=2, loc="lower left")
    tidy(ax, "y")
    ax.set_xticks((2016, 2018, 2020, 2022, 2024, 2026))
    return (
        fig,
        rows,
        (
            "Retained is not eligible, eligible is not biography-covered, and current-term coverage "
            "is not prior-term coverage. Candidate-specific denominators and cast-vote dates are "
            "included in the complete query package."
        ),
    )


def benchmark_sensitivity(data):
    records = [
        r
        for r in data["trait-fits"]
        if r["chamber"] == "house"
        and r["year"] in (2024, 2026)
        and r["model"] in ("ideology", "defection")
        and r["variant"] in ("primary_same_alternate_sample", "alternate_presidential_same_sample")
    ]
    fig = frame(
        "The presidential benchmark can change the answer",
        "Same candidates, same geography, different published presidential vintage. "
        "The benchmark also enters the lean controls, not only the outcome subtraction.",
        "House incumbents with both map-qualified benchmarks. Original benchmark: 2024 "
        "presidential share. Alternate: 2020 presidential share on the same election-year map. "
        "Ideology: +0.1 rightward; defection: +1 pp. Exploratory sensitivity envelopes.",
    )
    ax = fig.add_axes((0.28, 0.27, 0.49, 0.48))
    labels = []
    for i, (year, model) in enumerate(
        (y, m) for y in (2024, 2026) for m in ("ideology", "defection")
    ):
        labels.append(f"{year} · {model} " + ("(+0.1)" if model == "ideology" else "(+1 pp)"))
        for row in records:
            if (row["year"], row["model"]) != (year, model):
                continue
            alternate = row["variant"] == "alternate_presidential_same_sample"
            dot(ax, row, i + (0.13 if alternate else -0.13), color=ACCENT if alternate else BLUE)
    forest(ax, labels)
    ax.plot([], [], "o", color=BLUE, label="2024 benchmark")
    ax.plot([], [], "o", color=ACCENT, label="2020 benchmark")
    ax.legend(frameon=False, fontsize=10, loc="upper right")
    return (
        fig,
        [flat(r) for r in records],
        (
            "Every pair uses identical candidate-election IDs. Sign changes are benchmark "
            "sensitivity, not proof that either score causes stronger electoral performance. "
            "No unqualified district cells are filled across redistricting."
        ),
    )


def identity_coverage(data):
    panel = [
        r
        for r in data["candidate-queries"]
        if r["year"] == 2026 and r["chamber"] == "house" and r["eligible"]
    ]
    rows = []
    fig = frame(
        "Unknown identity is the largest evidence gap",
        f"Documented categories across all {len(panel)} eligible 2026 House Democratic nominees. "
        "Unknowns are never recoded as White, non-Hispanic, Protestant or atheist.",
        "Sources: pinned public identity evidence, Pew/Historian and map-compatible ACS "
        "population controls. Census describes residents, not voters, and does not collect "
        "religion. No qualified 2026 district religious-composition control is claimed.",
        height=8.5,
    )
    for position, (field, title) in enumerate(
        (("religion_category", "Religion"), ("race_category", "Race / ethnicity"))
    ):
        counts = Counter(r.get(field) or "unknown" for r in panel)
        ordered = sorted(counts, key=lambda k: (-counts[k], k))
        ax = fig.add_axes((0.20 + position * 0.45, 0.26, 0.26, 0.49))
        values = [counts[k] for k in ordered]
        ax.barh(
            range(len(ordered)),
            values,
            color=[MUTED if k == "unknown" else BLUE for k in ordered],
            height=0.60,
        )
        ax.set_yticks(range(len(ordered)), [k.replace("_", " ") for k in ordered])
        ax.invert_yaxis()
        ax.set_xlim(0, max(values) * 1.16)
        ax.set_title(title, fontsize=13, loc="left", pad=14)
        ax.set_xlabel("Documented nominees", fontsize=10)
        for i, (category, count) in enumerate(zip(ordered, values)):
            ax.text(count + max(values) * 0.025, i, str(count), va="center", fontsize=10)
            rows.append(
                {
                    "field": field,
                    "category": category,
                    "candidates": count,
                    "denominator": len(panel),
                    "share_pct": 100 * count / len(panel),
                }
            )
        tidy(ax)
    census = sum(
        all(k in r.get("constituency_race_shares_pct", {}) for k in RACE_CONTROLS) for r in panel
    )
    return (
        fig,
        rows,
        (
            f"Only {census} of {len(panel)} eligible House races have the required compatible "
            "resident-population controls. Identity fits and exact pair support are downloadable; "
            "small Muslim, Asian/Pacific Islander and other groups are not promoted to headline "
            "advantages. Absent atheist or other labels means missing positive evidence, not zero "
            "atheist candidates. Categories are documented source classifications, not inferred identities."
        ),
    )


def predictive_error(data):
    rows = [r for r in data["validation"] if r["year"] == 2026 and r["chamber"] == "house"]
    fig = frame(
        "Small feature lifts do not make calibrated forecasts",
        "2026 chronological, state-and-person-held-out replay. Show absolute error as well as "
        "the paired lift; uncertainty below resamples fixed predictions, not model refits.",
        "All validation years use prior-completed-Congress voting features. Training excludes "
        "the target year, state and identified target people. Outcomes are provisional "
        "share gaps, not margin points. Positive MAE lift means lower feature-model error.",
        height=8.4,
    )
    left = fig.add_axes((0.22, 0.27, 0.28, 0.49))
    right = fig.add_axes((0.57, 0.27, 0.23, 0.49))
    for i, row in enumerate(rows):
        left.plot([row["baseline_mae"], row["feature_mae"]], [i, i], color=MUTED, linewidth=1)
        left.plot(row["baseline_mae"], i, "o", color=BLUE)
        left.plot(row["feature_mae"], i, "o", color=ACCENT)
        value = row["mae_improvement"]
        low, high = row["conditional_paired_mae_lift_ci"]
        right.errorbar(
            value,
            i,
            xerr=[[value - low], [high - value]],
            fmt="o",
            color=ACCENT,
            capsize=3,
            markersize=5,
        )
        right.text(
            1.08,
            i,
            f"Bias {row['baseline_bias']:+.1f}\n→ {row['feature_bias']:+.1f} pp",
            transform=right.get_yaxis_transform(),
            va="center",
            fontsize=9,
        )
    forest(left, [r["model"].replace("_", " ").title() for r in rows], "Absolute MAE (D-share pp)")
    forest(right, [""] * len(rows), "Paired MAE lift (D-share pp)")
    left.set_xlim(left=max(0, left.get_xlim()[0]))
    left.plot([], [], "o", color=BLUE, label="Baseline")
    left.plot([], [], "o", color=ACCENT, label="Feature")
    left.legend(frameon=False, fontsize=10, loc="lower left")
    return (
        fig,
        [
            {
                **flat(r),
                "lift_ci_low": r["conditional_paired_mae_lift_ci"][0],
                "lift_ci_high": r["conditional_paired_mae_lift_ci"][1],
            }
            for r in rows
        ],
        (
            "Each feature uses its own same-sample baseline; differing rows are not a model ranking. "
            "Bias is observed minus predicted gap (positive means underprediction). "
            "This is a retrospective replay, not an actual "
            "pre-election forecast. Fixed-prediction intervals omit model-refitting uncertainty."
        ),
    )


def third_party(data):
    fig = frame(
        "A two-party shortcut can answer the wrong question",
        "Keep every named candidate and the full vote denominator. Alaska House and Montana "
        "Senate are held from the main characteristic fits; independents stay independent.",
        "Pinned native provider candidate totals, not a final ranked-choice redistribution. "
        "Alaska requires a qualified final RCV round. A material other-party share (at least "
        "10%) holds a race from the primary D-versus-R analysis.",
        height=8.3,
    )
    rows = []
    for i, (state, chamber) in enumerate((("AK", "house"), ("MT", "senate"))):
        query = next(
            r
            for r in data["candidate-queries"]
            if r["year"] == 2026 and r["state"] == state and r["chamber"] == chamber
        )
        native = query["native_evidence"]["native"]
        candidates = sorted(native["candidates"], key=lambda c: (-c["votes"], c["name"]))
        total = sum(c["votes"] for c in candidates)
        ax = fig.add_axes((0.20 + i * 0.45, 0.28, 0.26, 0.46))
        values = [100 * c["votes"] / total for c in candidates]
        ax.barh(
            range(len(candidates)),
            values,
            color=[
                BLUE
                if c["party"].lower().startswith("democrat")
                else ACCENT
                if c["party"].lower() == "republican"
                else MUTED
                for c in candidates
            ],
            height=0.6,
        )
        ax.set_yticks(range(len(candidates)), [c["name"] for c in candidates])
        ax.invert_yaxis()
        ax.set_xlim(0, 75)
        ax.set_title(f"{state} {chamber.title()} · held", fontsize=13, loc="left", pad=14)
        ax.set_xlabel("Share of all candidate votes (%)", fontsize=10)
        for j, (candidate, value) in enumerate(zip(candidates, values)):
            ax.text(value + 1, j, f"{value:.1f}%", fontsize=10, va="center")
            rows.append(
                {
                    "state": state,
                    "chamber": chamber,
                    **candidate,
                    "all_candidate_votes": total,
                    "all_candidate_share_pct": value,
                    "primary_eligible": query["eligible"],
                }
            )
        tidy(ax)
    return (
        fig,
        rows,
        (
            "Bill Hill is an independent, not the Democratic nominee. The downloaded query retains "
            "every minor-party/write-in candidate and the old frozen counts as well as the fresh "
            "native counts. Excluding these cases does not erase them from the evidence."
        ),
    )


def source_clocks(data):
    native_rows = [r for r in data["candidate-queries"] if r["year"] == 2026]
    rows = []
    fig = frame(
        "A fresh download is not a certified final count",
        "All 435 House and 35 Senate contests are retained. Native update dates and provider "
        "reporting percentages describe the source snapshot—not legal finality.",
        "470 complete federal race endpoint payloads pinned by SHA-256. County/map objects "
        "are outside this statewide/district-total query; every selected candidate row is "
        "preserved. Source receipts include the exact URLs, access clock and native clocks.",
    )

    def reporting_bucket(row):
        value = row.get("percent_reporting")
        if type(value) not in (int, float) or not 0 <= value <= 100:
            return "Unknown / invalid"
        if value == 100:
            return "100%"
        if value >= 90:
            return "90 to <100%"
        if value >= 75:
            return "75 to <90%"
        if value >= 50:
            return "50 to <75%"
        return "Below 50%"

    groups = (
        ("Native update date", lambda r: r["native_evidence"]["native"]["last_updated"][:10]),
        (
            "Provider reporting (%)",
            reporting_bucket,
        ),
    )
    for i, (title, key) in enumerate(groups):
        counts = Counter(key(r) for r in native_rows)
        labels = sorted(counts)
        ax = fig.add_axes((0.19 + i * 0.44, 0.27, 0.28, 0.49))
        ax.barh(range(len(labels)), [counts[k] for k in labels], color=BLUE, height=0.6)
        ax.set_yticks(range(len(labels)), labels)
        ax.invert_yaxis()
        ax.set_xlim(0, max(counts.values()) * 1.16)
        ax.set_title(title, fontsize=12, loc="left", pad=14)
        ax.set_xlabel("Retained contests")
        for j, label in enumerate(labels):
            ax.text(counts[label] + 3, j, str(counts[label]), va="center", fontsize=10)
            rows.append({"measure": title, "category": label, "contests": counts[label]})
        tidy(ax)
    return (
        fig,
        rows,
        (
            "The normalized replay retains all 470 selected native race/candidate queries and "
            "their reporting metadata. Reporting of 100% is not a certification assertion. "
            "Stage, identity, RCV, accounting and material-third-party holds remain explicit."
        ),
    )


BUILDERS = (
    ("house-characteristics", traits),
    ("moderation-history", caucus_history),
    ("moderation-sensitivity", caucus_sensitivity),
    ("voting-record-coverage", record_coverage),
    ("benchmark-sensitivity", benchmark_sensitivity),
    ("identity-coverage", identity_coverage),
    ("predictive-error", predictive_error),
    ("third-party-holds", third_party),
    ("source-clocks", source_clocks),
)


def build(inputs, analysis, output):
    inputs, analysis, output = map(lambda p: Path(p).resolve(), (inputs, analysis, output))
    for folder in (inputs, analysis):
        for name, receipt in json.loads((folder / "manifest.json").read_text()).items():
            if fingerprint(folder / name) != receipt:
                raise ValueError(f"Changed pinned publication input: {name}")
    root = Path(__file__).resolve().parents[1]
    package = {
        p.relative_to(root).as_posix(): p
        for folder in ("which_candidate", "tests", "docs", "results/2026", "audits/2026-v3")
        for p in (root / folder).rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    }
    package.update({n: root / n for n in ("pyproject.toml", "requirements.lock", "README.md")})
    recipe = {
        "inputs": fingerprint(inputs / "manifest.json"),
        "analysis": fingerprint(analysis / "manifest.json"),
        "package": {n: fingerprint(p) for n, p in sorted(package.items())},
        "renderer": fingerprint(Path(__file__)),
        "version": "2026-v3",
    }
    if output.exists():
        manifest = verify_output(output)
        if manifest["recipe"] != recipe:
            raise ValueError("Changed corrected publication requires a new version")
        return manifest
    data = {
        name: read_rows(analysis / f"{name}.jsonl.gz")
        for name in ("candidate-queries", "trait-fits", "moderation-fits", "validation")
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".corrected-figures-", dir=output.parent) as temp:
        destination = Path(temp)
        (destination / "plot-data").mkdir()
        charts = []
        with plt.rc_context({**THEME, "svg.hashsalt": "which-candidate-2026-v3"}):
            for name, builder in BUILDERS:
                fig, rows, caption = builder(data)
                (destination / "plot-data" / f"{name}.csv").write_bytes(csv_bytes(rows))
                charts.append(
                    {
                        "id": name,
                        "title": fig.texts[0].get_text(),
                        "caption": caption,
                        "alt": fig.texts[0].get_text() + ". " + caption,
                        "plotted_records": len(rows),
                        "data": f"plot-data/{name}.csv",
                        "files": export_chart(fig, destination, name),
                    }
                )
        write_json(destination / "captions.json", charts)
        entries = dict(package)
        for folder, label in ((inputs, "inputs"), (analysis, "analysis")):
            entries.update(
                {f"results/2026-v3/{label}/{p.name}": p for p in folder.iterdir() if p.is_file()}
            )
        for p in destination.rglob("*"):
            if p.is_file():
                entries[f"publication/2026-v3/{p.relative_to(destination).as_posix()}"] = p
        write_zip(destination / "complete-query-set.zip", entries)
        substack = {p.name: p for p in (destination / "substack").iterdir()}
        substack.update({f"plot-data/{p.name}": p for p in (destination / "plot-data").iterdir()})
        substack["captions.json"] = destination / "captions.json"
        substack["complete-query-set.zip"] = destination / "complete-query-set.zip"
        write_zip(destination / "substack-figures.zip", substack)
        manifest = {
            "schema": "which_candidate.publication.v3",
            "target_year": 2026,
            "provisional": True,
            "supersedes": "2026-v2",
            "recipe": recipe,
            "comparison_years": [2016, 2018, 2020, 2022, 2024, 2026],
            "charts": charts,
            "downloads": {"queries": "complete-query-set.zip", "substack": "substack-figures.zip"},
            "files": {
                p.relative_to(destination).as_posix(): fingerprint(p)
                for p in sorted(destination.rglob("*"))
                if p.is_file()
            },
        }
        write_json(destination / "manifest.json", manifest)
        destination.rename(output)
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--analysis", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build(args.inputs, args.analysis, args.output)
    print(f"Built {len(result['charts'])} corrected figures and complete downloads")
