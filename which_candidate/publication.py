"""2026-first publication figures, with exploratory annual historical comparisons."""

import argparse
import importlib.metadata
import json
import shutil
import tempfile
import textwrap
import zipfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import to_rgb
from matplotlib.lines import Line2D
from matplotlib.text import Text
from matplotlib.ticker import MaxNLocator
from PIL import Image
from scipy.stats import t

from .models import PRIMARY, associations, available, matrix
from .pipeline import csv_bytes, verify_output
from .storage import fingerprint, read_rows, write_json, write_rows

BACKGROUNDS = {"substack": "#F7F5F0", "marginoferror": "#F2EFE7"}
INK, MUTED, GRID = "#1A1A1A", "#6B6B6B", "#D6D3CC"
ACCENT, BLUE = "#C85A3D", "#3D6F8C"
STYLE_REFERENCE = {
    "repository": "hanshanley/uk_decline",
    "revision": "52e55bca2126be88b2feacd78d4b038667994cf4",
    "path": "vizstyle/__init__.py",
}
YEARS = (2016, 2018, 2020, 2022, 2024, 2026)
LABELS = {
    "incumbency": "Democratic incumbent",
    "ideology": "Rightward ideology (+0.1)",
    "defection": "Party defection (+5 pp)",
    "age": "Age (+10 years)",
    "tenure": "Chamber tenure (+10 years)",
    "gender": "Recorded F versus M",
    "born_in_state": "Born in state (exploratory)",
}
CLOCK_NOTE = "2026 provisional counts: November 7-8 snapshot. Not certified final results."
THEME = {
    "figure.facecolor": BACKGROUNDS["substack"],
    "axes.facecolor": BACKGROUNDS["substack"],
    "savefig.facecolor": BACKGROUNDS["substack"],
    "font.family": "serif",
    "font.serif": ["DejaVu Serif"],
    "font.size": 12,
    "text.color": INK,
    "axes.labelcolor": INK,
    "axes.edgecolor": GRID,
    "axes.linewidth": 0.8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "xtick.major.size": 0,
    "ytick.major.size": 0,
    "grid.color": GRID,
    "grid.alpha": 0.6,
    "grid.linewidth": 0.5,
    "text.parse_math": False,
    "svg.hashsalt": "which-candidate-publication-v1",
}


def chart_frame(title, subtitle, source, height=7.5):
    fig = plt.figure(figsize=(11.8, height), dpi=200)
    fig.text(0.055, 0.95, title, fontsize=21, weight="bold", va="top")
    fig.text(0.055, 0.885, textwrap.fill(subtitle, 112), fontsize=11.5, color=MUTED, va="top")
    fig.text(0.055, 0.115, CLOCK_NOTE, fontsize=9.5, color=MUTED)
    fig.text(
        0.055,
        0.045,
        textwrap.fill(source, 150),
        fontsize=8.7,
        color=MUTED,
        style="italic",
        va="bottom",
    )
    return fig


def tidy(ax, axis="x"):
    ax.grid(axis=axis)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.xaxis.set_major_locator(MaxNLocator(5))
    ax.tick_params(pad=8, labelsize=10.5)


def check_layout(fig):
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    bounds = fig.bbox
    outside_ticks = set()
    for ax in fig.axes:
        for labels, limits, coordinate in (
            (ax.get_xticklabels(), ax.get_xlim(), 0),
            (ax.get_yticklabels(), ax.get_ylim(), 1),
        ):
            for label in labels:
                if not min(limits) <= label.get_position()[coordinate] <= max(limits):
                    outside_ticks.add(id(label))
    for text in fig.findobj(Text):
        if not text.get_visible() or not text.get_text() or id(text) in outside_ticks:
            continue
        box = text.get_window_extent(renderer)
        if box.x0 < -1 or box.y0 < -1 or box.x1 > bounds.x1 + 1 or box.y1 > bounds.y1 + 1:
            raise ValueError(f"Clipped publication text: {text.get_text()!r}")
    title, subtitle = fig.texts[:2]
    if title.get_window_extent(renderer).overlaps(subtitle.get_window_extent(renderer)):
        raise ValueError("Publication title overlaps subtitle")
    for ax in fig.axes:
        for label in (ax.xaxis.label, ax.yaxis.label):
            if not label.get_text():
                continue
            for other in fig.axes:
                if other is ax:
                    continue
                for text in other.findobj(Text):
                    if not text.get_visible() or not text.get_text() or id(text) in outside_ticks:
                        continue
                    if label.get_window_extent(renderer).overlaps(text.get_window_extent(renderer)):
                        raise ValueError(f"Overlapping subplot labels: {label.get_text()!r}")


def primary_records(fits, terms, chamber):
    focal = {r["model"]: r for r in terms if r["chamber"] == chamber and r["primary_focal"]}
    selected = {
        r["model"]: r for r in fits if r["chamber"] == chamber and r["variant"] == "primary"
    }
    return [
        {
            "model": model,
            "comparison": LABELS[model],
            "status": selected[model]["status"],
            "n": selected[model]["n"],
            "state_clusters": selected[model]["state_clusters"],
            **focal.get(model, {}),
        }
        for model in PRIMARY
    ]


def trait_chart(fits, terms, chamber):
    records = primary_records(fits, terms, chamber)
    fig = chart_frame(
        f"{chamber.title()} 2026: no clear candidate-type advantage",
        "Adjusted associations with Democratic vote share. None of the six primary comparisons "
        "passes the chamber's Holm correction; intervals below are pointwise.",
        "Sources: held 2026 returns, FEC, The Downballot (2026 maps), Voteview, "
        "congress-legislators. State-clustered 95% intervals. Except incumbency, "
        "verified Democratic incumbents only; not causal.",
    )
    ax = fig.add_axes((0.31, 0.25, 0.43, 0.51))
    for index, row in enumerate(records):
        y = 5 - index
        if row["status"] == "estimated":
            value, low, high = (row[k] for k in ("estimate_share_pp", "ci_low", "ci_high"))
            ax.errorbar(
                value,
                y,
                xerr=[[value - low], [high - value]],
                fmt="o",
                color=ACCENT,
                markersize=6,
                capsize=3,
                linewidth=1.6,
            )
            label = (
                f"{value:+.2f} [{low:+.2f}, {high:+.2f}]\n"
                f"N={row['n']}; {row['state_clusters']} states\n"
                f"Holm p={row['holm_pvalue']:.3f}"
            )
        else:
            ax.text(
                0.04,
                y,
                "Not estimable",
                transform=ax.get_yaxis_transform(),
                fontsize=11,
                color=MUTED,
                va="center",
            )
            label = f"N={row['n']}; {row['state_clusters']} states\nRank-deficient fit"
        ax.text(1.06, y, label, transform=ax.get_yaxis_transform(), va="center", fontsize=10)
    ax.text(
        1.06, 1.045, "Estimate [95% interval]", transform=ax.transAxes, color=MUTED, fontsize=10
    )
    ax.axvline(0, color=MUTED, linewidth=0.9, zorder=0)
    ax.set_yticks(range(6), [LABELS[m] for m in reversed(PRIMARY)])
    ax.set_ylim(-0.6, 5.6)
    ax.margins(x=0.12)
    ax.set_xlabel("Association with Democratic share (pp)", labelpad=12, fontsize=11)
    tidy(ax)
    caption = (
        f"{chamber.title()} 2026 associations adjust for presidential lean and lean squared; "
        "the incumbency model additionally controls Republican incumbency. All other traits "
        "compare verified Democratic incumbents. One share point equals two D-minus-R margin "
        "points. Senate record comparisons have only nine candidates. A held fit is not zero."
    )
    return fig, records, caption


def adjusted_record_data(panel, fit):
    by_id = {r["D_candidate_election_id"]: r for r in panel}
    ids = fit["candidate_election_ids"]
    if (
        fit["status"] != "estimated"
        or len(ids) != fit["n"]
        or len(set(ids)) != len(ids)
        or any(i not in by_id for i in ids)
    ):
        raise ValueError("Record chart requires the exact estimated fit sample")
    rows = [by_id[i] for i in ids]
    if not rows or any(
        r["year"] != 2026 or r["chamber"] != fit["chamber"] or not available(r, fit["model"])
        for r in rows
    ):
        raise ValueError("Record chart must contain only the frozen 2026 fit sample")
    x, names = matrix(rows, fit["model"], cycles=[2026])
    if names != fit["terms"]:
        raise ValueError("Saved fit terms disagree with chart design")
    focal = names.index(PRIMARY[fit["model"]][0])
    beta = np.asarray(fit["coefficients"])
    covariance = np.asarray(fit["covariance"])
    controls = x.copy()
    controls[:, focal] = 0
    center = controls.mean(axis=0)
    observed = np.asarray([r["descriptive_gap_share_pp"] for r in rows])
    adjusted = observed - (controls - center) @ beta
    scale = 0.1 if fit["model"] == "ideology" else 5
    points = [
        {
            "kind": "candidate",
            "model": fit["model"],
            "candidate_election_id": row["D_candidate_election_id"],
            "name": row["D_name"],
            "state": row["state"],
            "x": float(x[i, focal] * scale),
            "adjusted_gap_share_pp": float(adjusted[i]),
            "raw_gap_share_pp": float(observed[i]),
        }
        for i, row in enumerate(rows)
    ]
    grid = np.linspace(x[:, focal].min(), x[:, focal].max(), 100)
    design = np.tile(center, (len(grid), 1))
    design[:, focal] = grid
    mean = design @ beta
    error = np.sqrt(np.maximum(np.einsum("ij,jk,ik->i", design, covariance, design), 0))
    critical = t.ppf(0.975, fit["state_clusters"] - 1)
    lines = [
        {
            "kind": "fitted_mean",
            "model": fit["model"],
            "x": float(z * scale),
            "adjusted_gap_share_pp": float(value),
            "ci_low": float(value - critical * se),
            "ci_high": float(value + critical * se),
        }
        for z, value, se in zip(grid, mean, error)
    ]
    return points + lines


def records_chart(panel, fits):
    fig = chart_frame(
        "Voting records give no decisive 2026 signal",
        "House Democratic incumbents, after centering partisan controls. The plotted slopes "
        "are the saved 2026 models, not new unadjusted fits.",
        "Sources: held 2026 House returns, The Downballot, Voteview 118th Congress. "
        "Bands: state-clustered 95% intervals for the fitted mean, not prediction intervals. "
        "Not causal; score vintages are retrospective.",
    )
    data = []
    for index, (model, label) in enumerate(
        (
            ("ideology", "Nokken-Poole ideology (rightward →)"),
            ("defection", "Party defection on unity votes (%)"),
        )
    ):
        fit = next(
            r
            for r in fits
            if r["chamber"] == "house" and r["model"] == model and r["variant"] == "primary"
        )
        records = adjusted_record_data(panel, fit)
        data.extend(records)
        points = [r for r in records if r["kind"] == "candidate"]
        line = [r for r in records if r["kind"] == "fitted_mean"]
        ax = fig.add_axes((0.10 + index * 0.48, 0.25, 0.35, 0.48))
        ax.scatter(
            [r["x"] for r in points],
            [r["adjusted_gap_share_pp"] for r in points],
            color=BLUE,
            alpha=0.65,
            s=17,
            linewidths=0,
        )
        ax.fill_between(
            [r["x"] for r in line],
            [r["ci_low"] for r in line],
            [r["ci_high"] for r in line],
            color=ACCENT,
            alpha=0.15,
        )
        ax.plot(
            [r["x"] for r in line],
            [r["adjusted_gap_share_pp"] for r in line],
            color=ACCENT,
            linewidth=2,
        )
        ax.axhline(0, color=MUTED, linewidth=0.7)
        ax.set_title(f"{model.title()} · N={fit['n']}", loc="left", fontsize=13, pad=15)
        ax.set_xlabel(label, labelpad=12, fontsize=10.5)
        ax.set_ylabel("Lean-adjusted gap (share pp)", fontsize=10.5, labelpad=8)
        tidy(ax, "y")
    return (
        fig,
        data,
        (
            "Each point is a candidate's presidential-benchmark gap after subtracting the "
            "saved model's lean-control contribution relative to its sample mean. Lines hold "
            "those controls at their sample means. Each panel retains its exact saved sample. "
            "Neither slope passes the primary six-test Holm correction."
        ),
    )


def identity_chart(terms):
    records = [
        r
        for r in terms
        if r["chamber"] == "house" and r["focal"] and r["variant"] == "census_adjusted"
    ]
    labels = {
        ("religion_category", "catholic"): "Catholic vs Protestant",
        ("religion_category", "jewish"): "Jewish vs Protestant",
        ("religion_category", "muslim"): "Muslim vs Protestant",
        ("race_category", "asian_or_pacific_islander"): "Asian/Pacific Islander\nvs Black",
    }
    if {(r["field"], r["category"]) for r in records} != set(labels):
        raise ValueError("Identity contrasts changed; review the publication selection")
    records.sort(key=lambda r: list(labels).index((r["field"], r["category"])))
    fig = chart_frame(
        "Identity comparisons remain inconclusive in 2026",
        "Four estimable House contrasts with Census race/Hispanic population controls. "
        "None passes the exploratory extension's Holm correction.",
        "Sources: Pew/CQ, House Historian, Census ACS 2024, held 2026 returns and The Downballot. "
        "Pointwise state-clustered 95% intervals. Census does not collect religion; "
        "no district-religion adjustment is claimed.",
    )
    ax = fig.add_axes((0.33, 0.25, 0.41, 0.50))
    for index, row in enumerate(records):
        value, low, high = (row[k] for k in ("estimate_share_pp", "ci_low", "ci_high"))
        ax.errorbar(
            value,
            3 - index,
            xerr=[[value - low], [high - value]],
            fmt="o",
            color=ACCENT,
            markersize=6,
            capsize=3,
            linewidth=1.6,
        )
        ax.text(
            1.06,
            3 - index,
            f"{value:+.2f} [{low:+.2f}, {high:+.2f}]\n"
            f"N={row['n']}; Holm p={row['holm_pvalue']:.3f}",
            transform=ax.get_yaxis_transform(),
            va="center",
            fontsize=10,
        )
    ax.set_yticks(range(4), [labels[(r["field"], r["category"])] for r in reversed(records)])
    ax.set_ylim(-0.6, 3.6)
    ax.axvline(0, color=MUTED, linewidth=0.9)
    ax.margins(x=0.12)
    ax.set_xlabel("Association with Democratic share (pp)", fontsize=11, labelpad=12)
    tidy(ax)
    return (
        fig,
        records,
        (
            "Selected documented Democratic incumbents only, on compatible district maps. "
            "The race comparison is Asian/Pacific Islander versus Black, not White versus minority "
            "or all nominees. There is no qualified atheist comparison. ACS controls describe "
            "residents, not voters; compatible 2026 district religious composition is unavailable. "
            "The nominal Muslim interval excludes zero but does not survive multiplicity correction."
        ),
    )


def coverage_chart(counts):
    records = [r for r in counts if r["chamber"] == "house" and r["phase"] == "primary_2026"]
    fig = chart_frame(
        "Missing identity evidence limits the 2026 comparison",
        "Eligible, verified House Democratic incumbents. Unknown is not White, "
        "non-Hispanic, Protestant or atheist; Hispanic origin is separate from race.",
        "Sources: candidate-linked Pew/CQ questionnaires, authorized biographies and positive "
        "House Historian 119th-Congress records. Zero means no documented observation in this "
        "sample, not absence of that identity in Congress.",
        height=9.5,
    )
    names = {
        "unitarian_universalist": "Unitarian Univ.",
        "christian_unspecified": "Christian (unspec.)",
        "other_christian": "Other Christian",
        "lds": "Latter-day Saint",
        "asian_or_pacific_islander": "Asian/Pac. Islander",
        "native_american": "Native American",
        "nhpi": "Native Hawaiian/PI",
        True: "Hispanic",
        False: "Explicit non-Hispanic",
        None: "Unknown",
    }
    for field, rect, title in (
        ("religion_category", (0.23, 0.24, 0.24, 0.53), "Religion"),
        ("race_category", (0.73, 0.47, 0.21, 0.30), "Race"),
        ("hispanic_origin", (0.73, 0.23, 0.21, 0.13), "Hispanic origin"),
    ):
        rows = [r for r in records if r["field"] == field]
        ax = fig.add_axes(rect)
        n = len(rows)
        for i, row in enumerate(rows):
            unknown = row["category"] in ("unknown", None)
            ax.barh(n - 1 - i, row["rows"], height=0.58, color=GRID if unknown else BLUE)
            ax.text(
                row["rows"] + 1.5,
                n - 1 - i,
                str(row["rows"]),
                va="center",
                fontsize=10,
                color=MUTED if unknown else INK,
            )
        labels = [
            names.get(r["category"], str(r["category"]).replace("_", " ").capitalize())
            for r in reversed(rows)
        ]
        ax.set_yticks(range(n), labels)
        ax.set_ylim(-0.6, n - 0.4)
        ax.set_xlim(0, max(r["rows"] for r in rows) * 1.23)
        ax.set_title(
            f"{title} · N={sum(r['rows'] for r in rows)}", loc="left", fontsize=12.5, pad=12
        )
        ax.set_xlabel("Candidates", fontsize=10)
        tidy(ax)
        ax.tick_params(axis="y", labelsize=9.5)
    return (
        fig,
        records,
        (
            "All religion and race categories are shown, including zeros. Counts are 2026 "
            "candidate observations, not estimates of Congress's overall composition. Positive "
            "Historian group lists do not identify everyone outside those groups. Unknown "
            "Hispanic origin never supplies a non-Hispanic comparison group."
        ),
    )


def validation_chart(validation):
    models = list(PRIMARY) + ["born_in_state"]
    records = [r for r in validation if r["year"] == 2026 and r["model"] in models]
    if len(records) != 2 * len(models):
        raise ValueError("Validation chart coverage changed")
    fig = chart_frame(
        "Trait records add little predictive lift for 2026",
        "Earlier-election training, with the test state and identified test people excluded. "
        "Positive bars mean lower mean absolute error than the same-sample baseline.",
        "Sources: chronological held-out predictions from the frozen analysis. Baseline minus "
        "feature MAE, in share pp; bars are descriptive, not confidence intervals. "
        "Retrospective replay, not an actual pre-election forecast.",
    )
    limit = max(abs(r["mae_improvement"]) for r in records) * 1.5
    for index, chamber in enumerate(("house", "senate")):
        ax = fig.add_axes((0.30 + index * 0.36, 0.25, 0.27, 0.49))
        sample = {r["model"]: r for r in records if r["chamber"] == chamber}
        for i, model in enumerate(models):
            row = sample[model]
            value = row["mae_improvement"]
            ax.barh(6 - i, value, height=0.5, color=ACCENT if value >= 0 else BLUE)
            ax.text(
                value + (0.012 if value >= 0 else -0.012),
                6 - i,
                f"{value:+.2f}",
                va="center",
                ha="left" if value >= 0 else "right",
                fontsize=10,
            )
        ax.set_xlim(-limit, limit)
        ax.axvline(0, color=MUTED, linewidth=0.8)
        ax.set_yticks(range(7), [LABELS[m] for m in reversed(models)] if index == 0 else [])
        ax.set_ylim(-0.7, 6.7)
        ax.set_title(chamber.title(), loc="left", fontsize=13, pad=16)
        ax.set_xlabel("MAE improvement (share pp)", fontsize=10.5, labelpad=12)
        tidy(ax)
    return (
        fig,
        records,
        (
            "Each feature is compared with a baseline on its own identical held-out candidates, "
            "not on a common sample across features. House samples range from 130 to 349; Senate "
            "samples from 8 to 23. Birth in state is exploratory. Small error differences are not "
            "a statistical test that one nominee type is better."
        ),
    )


def geography_chart(panel):
    records = [
        {
            "candidate_election_id": r["D_candidate_election_id"],
            "chamber": r["chamber"],
            "state": r["state"],
            "name": r["D_name"],
            "D_incumbent": r["D_incumbent"],
            "presidential_D_two_party_share_pct": r["presidential_D_two_party_share_pct"],
            "D_two_party_share_pct": r["D_two_party_share_pct"],
        }
        for r in panel
        if r["year"] == 2026 and r["eligible"]
    ]
    fig = chart_frame(
        "2026: partisan geography sets the starting point",
        "Democratic 2026 two-party share against the constituency's 2024 presidential share. "
        "The diagonal marks equal shares, not a 2026 forecast.",
        "Sources: held 2026 returns; The Downballot presidential results on 2026 House maps; "
        "FEC statewide presidential returns. Every qualified contest is shown. "
        "Democratic-aligned independents are not recoded as Democrats.",
    )
    groups = (
        (True, "Democratic incumbent", ACCENT),
        (False, "Nonincumbent Democrat", BLUE),
        (None, "Unresolved status", MUTED),
    )
    for index, chamber in enumerate(("house", "senate")):
        ax = fig.add_axes((0.10 + index * 0.48, 0.25, 0.35, 0.45))
        sample = [r for r in records if r["chamber"] == chamber]
        ax.plot((0, 100), (0, 100), color=MUTED, linewidth=0.9, linestyle="--")
        for status, label, color in groups:
            rows = [r for r in sample if r["D_incumbent"] is status]
            ax.scatter(
                [r["presidential_D_two_party_share_pct"] for r in rows],
                [r["D_two_party_share_pct"] for r in rows],
                s=21,
                color=color,
                alpha=0.72,
                label=label,
                linewidths=0,
            )
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 100)
        ax.set_title(f"{chamber.title()} · N={len(sample)}", loc="left", fontsize=13, pad=12)
        ax.set_xlabel("2024 presidential Democratic share (%)", fontsize=10.2, labelpad=12)
        ax.set_ylabel("2026 Democratic share (%)", fontsize=10.5)
        tidy(ax, "both")
        ax.set_aspect("equal", adjustable="box")
    handles, labels = fig.axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="upper left",
        bbox_to_anchor=(0.075, 0.82),
        ncol=3,
        frameon=False,
        fontsize=10,
        columnspacing=2,
    )
    return (
        fig,
        records,
        (
            "All 408 eligible House and 29 Senate comparisons, including unresolved incumbency. "
            "This is a descriptive benchmark comparison, not a causal model or evidence that "
            "two elections had identical electorates. House benchmarks use 2026 district maps; "
            "unqualified rounds and absent major-party nominees remain outside the plot."
        ),
    )


def annual_comparisons(panel, current_fits, current_terms):
    if {r["year"] for r in panel} != set(YEARS):
        raise ValueError("Historical comparison requires the complete 2016-2026 panel")
    if any(
        r["eligible"] and r["presidential_year"] != r["year"] - (2 if r["year"] % 4 else 0)
        for r in panel
    ):
        raise ValueError(
            "Historical presidential-benchmark vintages changed; review the comparison"
        )
    current_panel = [r for r in panel if r["year"] == 2026]
    by_id = {r["D_candidate_election_id"]: r for r in current_panel}
    for fit in current_fits:
        if fit["target_year"] != 2026 or any(
            candidate not in by_id for candidate in fit["candidate_election_ids"]
        ):
            raise ValueError("Annual comparison must preserve the frozen 2026 samples")
    fits, terms = [], []
    for year in YEARS:
        annual_fits, annual_terms = (
            (current_fits, current_terms) if year == 2026 else associations(panel, target_year=year)
        )
        for source, target in ((annual_fits, fits), (annual_terms, terms)):
            for row in source:
                target.append(
                    {
                        **row,
                        "comparison_fit_id": f"{year}:{row['model_id']}",
                        "comparison_benchmark_year": year - (2 if year % 4 else 0),
                        "comparison_benchmark_kind": "lagged" if year % 4 else "same_year",
                        "comparison_role": "primary_2026"
                        if year == 2026
                        else "exploratory_historical",
                    }
                )
    return fits, terms


def history_chart(fits, terms, chamber):
    records = []
    for year in YEARS:
        annual = primary_records(
            [r for r in fits if r["target_year"] == year],
            [r for r in terms if r["target_year"] == year],
            chamber,
        )
        records.extend({**r, "year": year} for r in annual)
    fig = chart_frame(
        f"{chamber.title()}: 2026 alongside five earlier elections",
        "Same model specification, different election cohorts. Terracotta highlights 2026. "
        "Filled points pass the six-test within-year Holm correction; open points do not. "
        "Intervals are pointwise 95%; N below each year is the model's sample.",
        "Sources: frozen FEC/Clerk and provisional 2026 returns, qualified district/state "
        "presidential benchmarks, Voteview and congress-legislators. Midterms use the preceding "
        "presidential election; presidential years use the same year's presidential vote.",
        height=10.6,
    )
    fig.text(
        0.025,
        0.51,
        "Association with Democratic share (pp)",
        rotation=90,
        ha="center",
        va="center",
        fontsize=11,
    )
    for index, model in enumerate(PRIMARY):
        sample = [r for r in records if r["model"] == model]
        ax = fig.add_axes((0.10 + (index % 3) * 0.30, 0.58 - (index // 3) * 0.32, 0.235, 0.19))
        for row in sample:
            year = row["year"]
            color = ACCENT if year == 2026 else BLUE
            if row["status"] != "estimated":
                ax.text(
                    year,
                    0.04,
                    "held",
                    transform=ax.get_xaxis_transform(),
                    ha="center",
                    color=color,
                    fontsize=9,
                )
                continue
            value, low, high = (row[k] for k in ("estimate_share_pp", "ci_low", "ci_high"))
            ax.errorbar(
                year,
                value,
                yerr=[[value - low], [high - value]],
                fmt="o",
                color=color,
                markerfacecolor=color if row["holm_pvalue"] < 0.05 else BACKGROUNDS["substack"],
                markersize=7 if year == 2026 else 5,
                linewidth=2 if year == 2026 else 1.1,
                capsize=3,
            )
        current = sample[-1]
        current_label = (
            f"2026: {current['estimate_share_pp']:+.2f} pp"
            if current["status"] == "estimated"
            else "2026: not estimable"
        )
        ax.set_title(f"{LABELS[model]}\n{current_label}", loc="left", fontsize=11.5, pad=13)
        ax.axhline(0, color=MUTED, linewidth=0.8)
        ax.set_xlim(2015.2, 2026.8)
        ax.margins(y=0.16)
        tidy(ax, "y")
        # Preserve the six election ticks rather than the generic numeric locator.
        ax.set_xticks(YEARS, [str(year) for year in YEARS])
        ax.tick_params(axis="both", labelsize=8.5)
        for row in sample:
            ax.text(
                row["year"],
                -0.20,
                f"N={row['n']}",
                transform=ax.get_xaxis_transform(),
                ha="center",
                va="top",
                fontsize=7.8,
                color=ACCENT if row["year"] == 2026 else MUTED,
            )
        ax.get_xticklabels()[-1].set_color(ACCENT)
        ax.get_xticklabels()[-1].set_weight("bold")
    fig.text(
        0.10,
        0.175,
        "2018 / 2022 / 2026 are midterms. Each panel has its own vertical scale. "
        "Held = insufficient or rank-deficient sample.",
        fontsize=9,
        color=MUTED,
    )
    caption = (
        f"{chamber.title()} annual associations for 2016, 2018, 2020, 2022, 2024 and 2026. "
        "The 2026 fits are reused unchanged; earlier years are exploratory annual fits with "
        "the same lean/lean-squared controls and pre-election feature rules. Except incumbency, "
        "traits compare verified Democratic incumbents. Midterms use a lagged presidential "
        "benchmark; presidential years use a same-year benchmark. Cohorts, maps and record "
        "coverage differ. These are not paired-candidate changes, a formal test of changes "
        "between years, or a correction across all historical comparisons. Held fits are not zero."
    )
    return fig, records, caption


def export_chart(fig, destination, name):
    check_layout(fig)
    files = {}
    for target, background in BACKGROUNDS.items():
        folder = destination / target
        folder.mkdir(exist_ok=True)
        png, svg = folder / f"{name}.png", folder / f"{name}.svg"
        if target == "substack":
            fig.savefig(
                png,
                dpi=200,
                facecolor=background,
                metadata={"Software": "which-candidate"},
                pil_kwargs={"compress_level": 9},
            )
        else:
            with Image.open(destination / "substack" / f"{name}.png") as image:
                pixels = np.array(image.convert("RGBA"))
            old = np.array([round(v * 255) for v in to_rgb(BACKGROUNDS["substack"])] + [255])
            new = np.array([round(v * 255) for v in to_rgb(background)] + [255])
            mask = np.all(pixels == old, axis=2)
            if not mask.any():
                raise ValueError("Missing original chart background")
            pixels[mask] = new
            Image.fromarray(pixels).save(png, compress_level=9, dpi=(200, 200))
        fig.set_facecolor(background)
        for axis in fig.axes:
            axis.set_facecolor(background)
        for line in fig.findobj(Line2D):
            face = line.get_markerfacecolor()
            if isinstance(face, str) and face.lower() == BACKGROUNDS["substack"].lower():
                line.set_markerfacecolor(background)
        fig.savefig(
            svg, facecolor=background, metadata={"Date": None, "Creator": "which-candidate"}
        )
        with Image.open(png) as image:
            width, height = image.size
        files[target] = {
            "png": png.relative_to(destination).as_posix(),
            "svg": svg.relative_to(destination).as_posix(),
            "width": width,
            "height": height,
            "background": background,
        }
    plt.close(fig)
    return files


def write_zip(path, entries):
    with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, source in sorted(entries.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, source.read_bytes())


def build_publication(analysis, output):
    analysis, output = Path(analysis).resolve(), Path(output).resolve()
    original = verify_output(analysis)
    verify_output(analysis / "returns")
    root = Path(__file__).resolve().parents[1]
    package_entries = {
        p.relative_to(root).as_posix(): p
        for folder in ("which_candidate", "tests")
        for p in (root / folder).glob("*.py")
    }
    for name in (
        "requirements.lock",
        "pyproject.toml",
        "README.md",
        "docs/ANALYSIS_SPEC.md",
        "docs/METHODOLOGY.md",
        "docs/DATA.md",
    ):
        package_entries[name] = root / name
    recipe = {
        "analysis_manifest": fingerprint(analysis / "manifest.json"),
        "analysis_files": {
            p.relative_to(analysis).as_posix(): fingerprint(p)
            for p in sorted(analysis.rglob("*"))
            if p.is_file()
        },
        "renderer": fingerprint(Path(__file__)),
        "package_inputs": {name: fingerprint(p) for name, p in sorted(package_entries.items())},
        "dependency_lock": fingerprint(root / "requirements.lock"),
        "style_reference": STYLE_REFERENCE,
        "backgrounds": BACKGROUNDS,
        "libraries": {
            n: importlib.metadata.version(n) for n in ("matplotlib", "numpy", "scipy", "Pillow")
        },
    }
    if output.exists():
        manifest = verify_output(output)
        if manifest["recipe"] != recipe:
            raise ValueError("Changed publication recipe requires a new output directory")
        return manifest
    summary = json.loads((analysis / "summary.json").read_bytes())
    if summary["primary_target_year"] != 2026:
        raise ValueError("Publication requires a 2026-primary analysis")
    panel = read_rows(analysis / "2026-candidate-results.jsonl.gz")
    if any(r["year"] != 2026 for r in panel):
        raise ValueError("Non-2026 outcome in publication panel")
    fits = read_rows(analysis / "2026-model-fits.jsonl.gz")
    terms = read_rows(analysis / "2026-model-terms.jsonl.gz")
    contextual = read_rows(analysis / "contextual-model-terms.jsonl.gz")
    if any(r["target_year"] != 2026 for r in fits + terms + contextual):
        raise ValueError("Non-2026 fit or term in publication inputs")
    counts = read_rows(analysis / "identity-category-counts.jsonl.gz")
    validation = read_rows(analysis / "validation.jsonl.gz")
    historical_panel = read_rows(analysis / "candidate-queries.jsonl.gz")
    annual_fits, annual_terms = annual_comparisons(historical_panel, fits, terms)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".figures-", dir=output.parent) as temp:
        destination = Path(temp)
        (destination / "plot-data").mkdir()
        (destination / "comparison").mkdir()
        for name, rows in (
            ("annual-model-fits", annual_fits),
            ("annual-model-terms", annual_terms),
        ):
            write_rows(destination / "comparison" / f"{name}.jsonl.gz", rows)
            (destination / "comparison" / f"{name}.csv").write_bytes(csv_bytes(rows))
        charts = []
        with plt.rc_context(THEME):
            builders = (
                ("house-characteristics", lambda: trait_chart(fits, terms, "house")),
                ("house-history", lambda: history_chart(annual_fits, annual_terms, "house")),
                ("senate-characteristics", lambda: trait_chart(fits, terms, "senate")),
                ("senate-history", lambda: history_chart(annual_fits, annual_terms, "senate")),
                ("house-voting-records", lambda: records_chart(panel, fits)),
                ("identity-comparisons", lambda: identity_chart(contextual)),
                ("identity-coverage", lambda: coverage_chart(counts)),
                ("predictive-lift", lambda: validation_chart(validation)),
                ("partisan-geography", lambda: geography_chart(panel)),
            )
            for name, build_chart in builders:
                fig, records, caption = build_chart()
                title = fig.texts[0].get_text()
                (destination / "plot-data" / f"{name}.csv").write_bytes(csv_bytes(records))
                charts.append(
                    {
                        "id": name,
                        "title": title,
                        "caption": caption,
                        "alt": f"{title}. {caption}",
                        "plotted_records": len(records),
                        "data": f"plot-data/{name}.csv",
                        "files": export_chart(fig, destination, name),
                    }
                )
        write_json(destination / "captions.json", charts)
        entries = {
            f"results/2026/{p.relative_to(analysis).as_posix()}": p
            for p in analysis.rglob("*")
            if p.is_file()
        }
        entries.update(package_entries)
        entries.update(
            {
                p.relative_to(destination).as_posix(): p
                for folder in ("plot-data", "comparison")
                for p in (destination / folder).iterdir()
            }
        )
        entries["captions.json"] = destination / "captions.json"
        write_zip(destination / "complete-query-set.zip", entries)
        substack = {
            p.relative_to(destination).as_posix(): p for p in (destination / "substack").iterdir()
        }
        substack.update(
            {
                p.relative_to(destination).as_posix(): p
                for p in (destination / "plot-data").iterdir()
            }
        )
        substack["captions.json"] = destination / "captions.json"
        substack["complete-query-set.zip"] = destination / "complete-query-set.zip"
        write_zip(destination / "substack-figures.zip", substack)
        manifest = {
            "schema": "which_candidate.publication.v1",
            "target_year": 2026,
            "provisional": True,
            "comparison_years": list(YEARS),
            "comparison_scope": (
                "Exploratory annual historical fits; frozen 2026 fits unchanged. "
                "Within-year Holm correction, not tests of between-year differences."
            ),
            "recipe": recipe,
            "charts": charts,
            "analysis_output_files": len(original["files"]),
            "downloads": {
                "queries": "complete-query-set.zip",
                "substack": "substack-figures.zip",
            },
            "files": {
                p.relative_to(destination).as_posix(): fingerprint(p)
                for p in sorted(destination.rglob("*"))
                if p.is_file()
            },
        }
        write_json(destination / "manifest.json", manifest)
        destination.rename(output)
    return manifest


def stage_site(output, site):
    output, site = Path(output).resolve(), Path(site).resolve()
    manifest = verify_output(output)
    target = site / "public/artifacts/which-candidate" / output.name
    if not (site / "astro.config.mjs").is_file():
        raise ValueError("Expected the Margin of Error Astro project")
    if target.exists():
        if verify_output(target) != manifest:
            raise ValueError("Refusing to overwrite a different website figure release")
    else:
        shutil.copytree(output, target)
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", type=Path, default=Path("results/2026"))
    parser.add_argument("--output", type=Path, default=Path("publication/2026-v2"))
    parser.add_argument("--stage-site", type=Path)
    args = parser.parse_args()
    manifest = build_publication(args.analysis, args.output)
    if args.stage_site:
        stage_site(args.output, args.stage_site)
    print(
        json.dumps(
            {
                "output": str(args.output),
                "charts": len(manifest["charts"]),
                "downloads": manifest["downloads"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
