"""A redesigned, readable 2026-first figure suite, separate from archived v2/v3."""

import argparse
import json
import math
import textwrap
from pathlib import Path
from tempfile import TemporaryDirectory

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator, MultipleLocator

from .pipeline import csv_bytes
from .publication import ACCENT, BLUE, GRID, INK, MUTED, THEME, export_chart
from .rebuild import persist_directory
from .storage import fingerprint, read_rows, write_json

ROOT = Path(__file__).resolve().parents[1]
YEARS = (2016, 2018, 2020, 2022, 2024, 2026)
CLOCK = "2026 counts: November 12-13 provider snapshot; provisional, not certified."
VERSIONS = ("2026-v4", "2026-v5")


def frame(title, subtitle, note, height=6.5):
    fig = plt.figure(figsize=(10, height), dpi=200)
    fig.text(0.065, 0.95, title, size=19, weight="bold", va="top")
    fig.text(0.065, 0.865, textwrap.fill(subtitle, 104), size=10.6, color=MUTED, va="top")
    fig.text(
        0.065,
        0.035,
        textwrap.fill(note + " " + CLOCK, 125),
        size=8.5,
        color=MUTED,
        va="bottom",
    )
    return fig


def tidy(ax, axis="x"):
    ax.grid(axis=axis, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.tick_params(pad=7, labelsize=10)


def interval(ax, row, y, color=ACCENT, factor=2):
    supported = row.get("publication_status") == "supported_exploratory"
    if row["status"] != "estimated" or row.get("ci_low") is None:
        return False
    value, low, high = [factor * row[key] for key in ("estimate_share_pp", "ci_low", "ci_high")]
    ax.errorbar(
        value,
        y,
        xerr=[[value - low], [high - value]],
        fmt="o",
        color=color if supported else MUTED,
        markersize=6.2,
        markerfacecolor=color if supported else "none",
        linewidth=1.5,
        capsize=3,
    )
    return True


def geography(data):
    panel = data["panel"]
    fig = frame(
        "Start with the seat, not the candidate",
        "2026 Democratic vote share versus the district or state's 2024 presidential share. "
        "Each dot is one qualified contest; the diagonal marks equal shares.",
        "Sources: pinned federal returns and map-qualified presidential benchmarks. "
        "Democratic share of the D+R vote; independents and held election rounds are not pooled.",
    )
    rows = []
    for i, chamber in enumerate(("house", "senate")):
        sample = [r for r in panel if r["chamber"] == chamber and r["eligible"]]
        ax = fig.add_axes((0.11 + i * 0.46, 0.22, 0.36, 0.51))
        ax.plot([0, 100], [0, 100], color=MUTED, linewidth=1, linestyle="--", zorder=1)
        ax.scatter(
            [r["presidential_D_two_party_share_pct"] for r in sample],
            [r["D_two_party_share_pct"] for r in sample],
            s=20 if chamber == "house" else 38,
            color=ACCENT if i == 0 else BLUE,
            alpha=0.65,
            linewidths=0,
        )
        ax.set(xlim=(10, 90), ylim=(10, 100), xlabel="2024 presidential D share (%)")
        if i == 0:
            ax.set_ylabel("2026 congressional D share (%)")
        ax.set_title(f"{chamber.title()}  |  {len(sample)} contests", loc="left", size=12, pad=13)
        ax.xaxis.set_major_locator(MultipleLocator(20))
        ax.yaxis.set_major_locator(MultipleLocator(20))
        tidy(ax, "both")
        rows.extend(
            {
                "contest_id": r["contest_id"],
                "candidate": r["D_name"],
                "chamber": chamber,
                "presidential_D_share": r["presidential_D_two_party_share_pct"],
                "congressional_D_share": r["D_two_party_share_pct"],
            }
            for r in sample
        )
    return (
        fig,
        rows,
        (
            "The diagonal is a descriptive equal-share reference, not an expected generic "
            "candidate, election forecast, national-wave adjustment or causal candidate effect. "
            "House geography uses the 2026 congressional map. All 470 contests, including "
            "the 37 held comparisons, remain in the complete candidate queries."
        ),
    )


def donor(data):
    labels = {
        "all_qualified": "All qualified candidates",
        "democratic_incumbents": "Democratic incumbents",
        "democratic_nonincumbents": "Democratic nonincumbents",
        "at_least_100_givers": "At least 100 reported givers",
        "competitive_40_60": "Competitive seats (40-60% D)",
    }
    rows = [
        r
        for variant in labels
        for r in data["donor"]
        if r["chamber"] == "house" and r["variant"] == variant
    ]
    fig = frame(
        "Donor ideology gives a selected-sample answer",
        "2026 House association with a 0.5-point more conservative historical donor score. "
        "These scores describe funding coalitions, not campaign platforms.",
        "DIME v4, activity through 2024; retrospectively acquired. Controls: district lean, "
        "lean squared and known D/R incumbency. 95% pointwise state-cluster sensitivity intervals.",
    )
    ax = fig.add_axes((0.34, 0.23, 0.42, 0.48))
    for y, row in enumerate(rows):
        if row.get("publication_status") != "supported_exploratory":
            ax.text(
                0.02,
                y,
                "Low support; see CSV",
                transform=ax.get_yaxis_transform(),
                va="center",
                size=9.4,
                color=MUTED,
            )
        elif not interval(ax, row, y):
            ax.text(
                0.02, y, "Not estimable", transform=ax.get_yaxis_transform(), va="center", size=10
            )
        fig.text(
            0.79,
            0.23 + 0.48 * (1 - (y + 0.5) / len(rows)),
            f"n = {row['n']}\n{row['state_clusters']} states",
            va="center",
            size=9.6,
            color=MUTED,
        )
    ax.set_ylim(len(rows) - 0.5, -0.5)
    ax.set_yticks(range(len(rows)), [labels[r["variant"]] for r in rows])
    ax.axvline(0, color=MUTED, linewidth=1)
    ax.set_xlabel("Association with D-minus-R margin (pp)", labelpad=12)
    tidy(ax)
    return (
        fig,
        rows,
        (
            "Every row is a separately fitted observational association. Exact FEC/state/party "
            "matches with consistent names qualify. All name discrepancies are excluded here, "
            "including four aliases corroborated in a separate identity review. "
            "The nonincumbent group is below the 30-person publication gate; its diagnostic "
            "estimate and interval are retained in the CSV, not drawn as supported evidence. "
            "Models use known incumbency for both parties. No inference "
            "extends to all challengers, and the intervals are not multiple-testing-adjusted."
        ),
    )


def donor_benchmarks(data):
    variants = (
        "all_qualified",
        "current_benchmark_common_sample",
        "previous_benchmark_common_sample",
    )
    labels = (
        "Full qualified sample\n2024 presidential benchmark",
        "Comparable-map sample\n2024 presidential benchmark",
        "Same candidates and maps\n2020 presidential benchmark",
    )
    rows = [
        next(r for r in data["donor"] if r["chamber"] == "house" and r["variant"] == variant)
        for variant in variants
    ]
    fig = frame(
        "The baseline changes the donor-ideology answer",
        "2026 House: a 0.5-point more conservative donor score. The lower two rows "
        "use exactly the same candidates, isolating the benchmark change.",
        "Outcome: congressional minus presidential D share, converted to margin points. "
        "Identical lean/incumbency specification; 95% pointwise state-cluster sensitivity intervals.",
    )
    ax = fig.add_axes((0.37, 0.25, 0.39, 0.44))
    for y, row in enumerate(rows):
        interval(ax, row, y, BLUE if y == 2 else ACCENT)
        fig.text(0.79, 0.25 + 0.44 * (1 - (y + 0.5) / 3), f"n = {row['n']}", va="center", size=10)
    ax.set(ylim=(2.5, -0.5), xlabel="Association with D-minus-R margin (pp)")
    ax.set_yticks(range(3), labels)
    ax.axvline(0, color=MUTED, linewidth=1)
    tidy(ax)
    return (
        fig,
        rows,
        (
            "The full-sample to restricted-sample change mixes attrition and specification, "
            "whereas the lower two rows isolate presidential benchmark choice on identical IDs. "
            "The 2020 benchmark is allowed only on independently qualified election maps. "
            "This sensitivity argues against treating a single positive coefficient as a "
            "universal moderation premium or Split Ticket WAR."
        ),
    )


def voting_history(data):
    fig = frame(
        "What the congressional voting record shows",
        "House: ideology uses prior-Congress votes; 2026 party defection uses votes cast "
        "before Election Day. The two measures have different increments.",
        "Voteview and pinned returns. Verified Democratic incumbents; lean-adjusted. "
        "95% pointwise sensitivity intervals; n = candidates. Not a simultaneous cross-year test.",
    )
    rows = []
    for i, (model, label) in enumerate(
        (
            ("ideology", "Voting ideology\n+0.1 more conservative"),
            ("defection", "Voting against the party\n+1 percentage point"),
        )
    ):
        sample = [
            r
            for r in data["traits"]
            if r["chamber"] == "house" and r["model"] == model and r["variant"] == "primary"
        ]
        ax = fig.add_axes((0.15 + i * 0.46, 0.23, 0.31, 0.46))
        for y, year in enumerate(YEARS):
            row = next(r for r in sample if r["year"] == year)
            interval(ax, row, y, ACCENT if year == 2026 else BLUE)
            fig.text(
                0.475 + i * 0.46,
                0.23 + 0.46 * (1 - (y + 0.5) / 6),
                f"n={row['n']}",
                size=8.6,
                va="center",
                color=MUTED,
            )
        ax.set_ylim(5.5, -0.5)
        ax.set_yticks(range(6), [str(y) for y in YEARS])
        ax.get_yticklabels()[-1].set_color(ACCENT)
        ax.get_yticklabels()[-1].set_weight("bold")
        ax.axvline(0, color=MUTED, linewidth=1)
        ax.set_title(label, size=11.4, loc="left", pad=15)
        ax.set_xlabel("D-minus-R margin association (pp)", size=9.6, labelpad=12)
        tidy(ax)
        rows.extend(sample)
    return (
        fig,
        rows,
        (
            "2026 ideology is the Congress-specific Nokken-Poole first dimension from "
            "2023-2024 votes, not DW-NOMINATE or current campaign positions. The 2026 "
            "defection rate uses qualifying recorded votes from January 2025 through "
            "November 2, 2026; older years use prior-completed-Congress records. Changing "
            "cohorts and timing prevent a formal trend interpretation. Separate increments "
            "are not a ranking of the measures. See CSV for exact sample sizes and Holm values."
        ),
    )


def measurements(data):
    sample = data["measurements"][0]
    fig = frame(
        "Same candidates, different ideology signals",
        f"2026 House: the same {sample['n']} Democratic incumbents in "
        f"{sample['state_clusters']} states. Separate models versus jointly adjusting "
        "for both measures, with the same lean controls.",
        "DIME through 2024; voting ideology from 2023-2024. Different score increments. "
        "95% pointwise state-cluster sensitivity intervals; exploratory, not causal.",
    )
    rows = []
    for i, (metric, label) in enumerate(
        (
            ("donor", "Historical donor ideology\n+0.5 more conservative"),
            ("voting", "Prior voting-record ideology\n+0.1 more conservative"),
        )
    ):
        ax = fig.add_axes((0.27 + i * 0.40, 0.29, 0.28, 0.36))
        for y, variant in enumerate((metric, f"joint_{metric}")):
            row = next(r for r in data["measurements"] if r["variant"] == variant)
            interval(ax, row, y, ACCENT if i == 0 else BLUE)
            rows.append(row)
        ax.set_ylim(1.5, -0.5)
        ax.set_yticks(range(2), ["Separate models", "Both scores included"] if i == 0 else [])
        ax.axvline(0, color=MUTED, linewidth=1)
        ax.set_title(label, loc="left", size=11.4, pad=15)
        ax.set_xlabel("D-minus-R margin association (pp)", size=9.6, labelpad=12)
        tidy(ax)
    return (
        fig,
        rows,
        (
            "An audit-added, exploratory comparison, not a prespecified confirmation. "
            "The common sample contains only verified Democratic incumbents with both scores; "
            "it is not representative of all nominees. All four models use identical candidate IDs, "
            "lean/lean-squared and available Republican-incumbency controls. Donor ideology "
            "describes historical funding coalitions; Nokken-Poole measures recorded congressional "
            "votes. Their different scales and opposing associations prohibit a single "
            "moderate/progressive ranking. Intervals are pointwise, without multiplicity adjustment."
        ),
    )


def incumbency(data):
    fig = frame(
        "Incumbency comparisons across six elections",
        "Democratic incumbents versus nonincumbents, controlling for constituency lean "
        "and Republican incumbency. 2026 is the primary election.",
        "Pinned returns and dated federal service evidence. 95% pointwise state-cluster "
        "sensitivity intervals; held or hollow results do not support headline inference.",
    )
    rows = []
    for i, chamber in enumerate(("house", "senate")):
        ax = fig.add_axes((0.15 + i * 0.46, 0.23, 0.31, 0.48))
        sample = [
            r
            for r in data["traits"]
            if r["chamber"] == chamber and r["model"] == "incumbency" and r["variant"] == "primary"
        ]
        for y, year in enumerate(YEARS):
            row = next(r for r in sample if r["year"] == year)
            if not interval(ax, row, y, ACCENT if year == 2026 else BLUE):
                ax.text(0.02, y, "Held", transform=ax.get_yaxis_transform(), va="center", size=9)
            fig.text(
                0.475 + i * 0.46,
                0.23 + 0.48 * (1 - (y + 0.5) / 6),
                f"n={row['n']}",
                size=8.6,
                va="center",
                color=MUTED,
            )
        ax.set_ylim(5.5, -0.5)
        ax.set_yticks(range(6), YEARS)
        ax.get_yticklabels()[-1].set_color(ACCENT)
        ax.get_yticklabels()[-1].set_weight("bold")
        ax.set_title(chamber.title(), loc="left", size=12, pad=13)
        ax.axvline(0, color=MUTED, linewidth=1)
        ax.set_xlabel("D-minus-R margin association (pp)", size=9.6, labelpad=12)
        tidy(ax)
        rows.extend(sample)
    return (
        fig,
        rows,
        (
            "Separate annual chamber-specific lean/lean-squared regressions; the cross-year "
            "points are not a paired-candidate or formal trend test. Presidential election "
            "years use same-year presidential benchmarks; midterms use lagged benchmarks. "
            "Senate estimates frequently have limited support. Unknown incumbency is "
            "not coded as nonincumbency. These are associations, not causal incumbency effects."
        ),
    )


def caucus(data):
    rows = [
        r
        for r in data["moderation"]
        if r["comparison"] == "blue_dog_vs_cpc"
        and r["method"] == "cross_fitted_structural"
        and r["variant"] == "lean_incumbency"
    ]
    fig = frame(
        "Caucus membership is a thin test of moderation",
        "Blue Dog minus Progressive Caucus structural residuals. Hollow points are "
        "diagnostic: at least one group falls short of the support gates.",
        "Dated membership rosters, not PAC endorsements. State-held-out residuals; "
        "95% full-pipeline deletion sensitivity intervals. This is not Split Ticket WAR.",
    )
    ax = fig.add_axes((0.20, 0.23, 0.48, 0.48))
    for y, year in enumerate(YEARS):
        row = next(r for r in rows if r["year"] == year)
        if not interval(ax, row, y, ACCENT if year == 2026 else BLUE):
            ax.text(
                0.02,
                y,
                "Roster unavailable" if row["n"] == 0 else "Held",
                transform=ax.get_yaxis_transform(),
                va="center",
                size=10,
            )
        group = row["group_support"]
        fig.text(
            0.72,
            0.23 + 0.48 * (1 - (y + 0.5) / 6),
            (
                f"{group['blue']['people']} Blue Dogs / {group['reference']['people']} CPC"
                if row["n"]
                else "No qualified roster"
            ),
            size=9.4,
            va="center",
            color=MUTED,
        )
    ax.set_ylim(5.5, -0.5)
    ax.set_yticks(range(6), YEARS)
    ax.get_yticklabels()[-1].set_color(ACCENT)
    ax.get_yticklabels()[-1].set_weight("bold")
    ax.axvline(0, color=MUTED, linewidth=1)
    ax.set_xlabel("Difference in D-minus-R margin residuals (pp)", labelpad=12)
    tidy(ax)
    return (
        fig,
        rows,
        (
            "Blue Dog/CPC groups are distinct from Blue Dog PAC/CPC PAC endorsements, "
            "New Democrats, DSA and Justice Democrats. A 2026 roster of 10 Blue Dogs "
            "leaves eight eligible nominees in this model; this does not reconcile the "
            "external chart's group of 12. Small membership cohorts, changing benchmark "
            "vintages and wide uncertainty do not establish that a moderation premium shrank."
        ),
    )


def coverage(data):
    labels = {
        "all_named": "All named nominees",
        "democratic_incumbents": "D incumbents",
        "democratic_nonincumbents": "D nonincumbents",
        "unknown_incumbency": "Incumbency unknown",
    }
    rows = [r for r in data["coverage"] if r["cohort"] in labels]
    fig = frame(
        "New biographies reach far beyond incumbents",
        "Share of named 2026 Democratic nominees with a source record. A missing record "
        "does not mean that a candidate lacks a trait or position.",
        "Biography: independently ID-matched, pre-election campaign-site captures; "
        "machine-extracted facts require review. Donor scores require consistent names.",
    )
    for i, (key, title) in enumerate(
        (
            ("pre_election_biography", "2026 biography"),
            ("donor_score", "Historical donor score"),
            ("prior_federal_voting_score", "Prior federal votes"),
        )
    ):
        ax = fig.add_axes((0.24 + i * 0.245, 0.24, 0.20, 0.45))
        for y, row in enumerate(rows):
            count, total = row[key], row["nominees"]
            percentage = 100 * count / total
            color = ACCENT if row["cohort"] == "democratic_nonincumbents" else BLUE
            ax.barh(y, percentage, height=0.42, color=color)
            ax.text(
                percentage + 3 if percentage < 60 else percentage - 3,
                y,
                f"{count}/{total}",
                va="center",
                ha="left" if percentage < 60 else "right",
                color=INK if percentage < 60 else "white",
                size=9.2,
            )
        ax.set(ylim=(3.5, -0.5), xlim=(0, 110))
        ax.set_xticks([0, 50, 100], ["0%", "50%", "100%"])
        ax.set_yticks(range(4), [labels[r["cohort"]] for r in rows] if i == 0 else [])
        ax.set_title(title, loc="left", size=10.6, pad=15)
        tidy(ax)
    return (
        fig,
        rows,
        (
            "The denominator is 454 named nominees, not 470 contests or just winners. "
            "183 incumbents, 249 nonincumbents and 22 nominees with unknown incumbency "
            "sum to that denominator. The new corpus supplies pre-election biography "
            "records for 147 nonincumbents, versus eight with the older CampaignView "
            "historical biographies; the datasets have different years and definitions. "
            "No machine-extracted biography has been promoted into a verified trait or model."
        ),
    )


BUILDERS = (
    ("seat-baseline", geography),
    ("donor-ideology", donor),
    ("donor-benchmark-sensitivity", donor_benchmarks),
    ("ideology-measurement", measurements),
    ("voting-record-history", voting_history),
    ("incumbency-history", incumbency),
    ("caucus-history", caucus),
    ("candidate-evidence", coverage),
)


def refined_diagnostics(builder, data):
    fig, rows, caption = builder(data)
    for ax in fig.axes:
        for text in ax.texts:
            if text.get_text() in ("Low support; see CSV", "Roster unavailable", "Held"):
                text.set_x(0.97)
                text.set_ha("right")
    return fig, rows, caption


def refined_donor(data):
    return refined_diagnostics(donor, data)


def refined_caucus(data):
    return refined_diagnostics(caucus, data)


def refined_measurements(data):
    fig, rows, caption = measurements(data)
    extent = max(
        1,
        math.ceil(
            1.08
            * max(
                (
                    abs(2 * row[key])
                    for row in rows
                    for key in ("ci_low", "ci_high")
                    if row.get(key) is not None
                ),
                default=1,
            )
        ),
    )
    for ax in fig.axes:
        ax.set_xlim(-extent, extent)
        ax.xaxis.set_major_locator(MaxNLocator(nbins=5, symmetric=True))
    return fig, rows, caption


def build(root=ROOT, output=None, *, version="2026-v4"):
    if version not in VERSIONS:
        raise ValueError(f"Unknown figure version: {version}")
    root = Path(root)
    output = Path(output) if output else root / "publication" / version
    with TemporaryDirectory(prefix="which-candidate-charts-") as directory:
        staged = Path(directory)
        result = _build(root, staged, version=version)
        persist_directory(staged, output)
    return result


def _build(root, output, *, version="2026-v4"):
    output.mkdir(parents=True, exist_ok=True)
    (output / "plot-data").mkdir(exist_ok=True)
    for directory in ("results/2026-v3/analysis", "results/2026-v4"):
        manifest = json.loads((root / directory / "manifest.json").read_text())
        receipts = manifest.get("files", manifest)
        for name, receipt in receipts.items():
            if fingerprint(root / directory / name) != receipt:
                raise ValueError(f"Changed pinned figure input: {directory}/{name}")
    data = {
        "panel": read_rows(root / "results/2026-v4/candidate-queries.jsonl.gz"),
        "donor": read_rows(root / "results/2026-v4/donor-fits.jsonl.gz"),
        "measurements": read_rows(root / "results/2026-v4/measurement-fits.jsonl.gz"),
        "coverage": json.loads((root / "results/2026-v4/coverage.json").read_text()),
        "traits": read_rows(root / "results/2026-v3/analysis/trait-fits.jsonl.gz"),
        "moderation": read_rows(root / "results/2026-v3/analysis/moderation-fits.jsonl.gz"),
    }
    charts = []
    refinements = (
        {
            "donor-ideology": refined_donor,
            "caucus-history": refined_caucus,
            "ideology-measurement": refined_measurements,
        }
        if version == "2026-v5"
        else {}
    )
    with plt.rc_context(
        {
            **THEME,
            "svg.hashsalt": f"which-candidate-{version.removeprefix('2026-')}",
            "font.size": 11,
        }
    ):
        for name, builder in BUILDERS:
            fig, rows, caption = refinements.get(name, builder)(data)
            scalars = [
                {k: v for k, v in row.items() if not isinstance(v, (list, dict))} for row in rows
            ]
            for row, scalar in zip(rows, scalars):
                if "estimate_share_pp" in row:
                    for key in ("estimate_share_pp", "ci_low", "ci_high"):
                        target = {
                            "estimate_share_pp": "plotted_estimate_margin_pp",
                            "ci_low": "plotted_ci_low_margin_pp",
                            "ci_high": "plotted_ci_high_margin_pp",
                        }[key]
                        scalar[target] = 2 * row[key] if row.get(key) is not None else None
                    scalar["point_drawn"] = (
                        row["status"] == "estimated"
                        and row.get("ci_low") is not None
                        and (
                            name != "donor-ideology"
                            or row.get("publication_status") == "supported_exploratory"
                        )
                    )
                    scalar["interval_level"] = 0.95
            (output / "plot-data" / f"{name}.csv").write_bytes(csv_bytes(scalars))
            charts.append(
                {
                    "id": name,
                    "title": fig.texts[0].get_text(),
                    "caption": caption,
                    "alt": fig.texts[0].get_text() + ". " + fig.texts[1].get_text() + " " + caption,
                    "plotted_records": len(rows),
                    "data": f"plot-data/{name}.csv",
                    "files": export_chart(fig, output, name),
                }
            )
    write_json(output / "captions.json", charts)
    write_json(
        output / "manifest.json",
        {
            "target_year": 2026,
            "version": version,
            "website_publication": "withdrawn",
            "historical_years": list(YEARS[:-1]),
            "charts": charts,
            "inputs": {
                name: fingerprint(root / name)
                for name in (
                    "results/2026-v3/analysis/manifest.json",
                    "results/2026-v4/manifest.json",
                )
            },
            "files": {
                p.relative_to(output).as_posix(): fingerprint(p)
                for p in sorted(output.rglob("*"))
                if p.is_file() and p.name != "manifest.json"
            },
        },
    )
    return charts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--version", choices=VERSIONS, default="2026-v4")
    args = parser.parse_args()
    print(f"Built {len(build(args.root, args.output, version=args.version))} redesigned figures")
