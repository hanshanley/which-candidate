"""Local, separately versioned full-characteristics findings and evidence browser."""

import html
import json
import textwrap
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .house_characteristics import STATUSES, TRAITS, VERSION, write_csv
from .house_report import article
from .storage import fingerprint, read_rows, write_json

LABELS = dict(
    zip(
        TRAITS,
        (
            "Age",
            "Source-recorded gender",
            "Race",
            "Ethnicity",
            "Dated religion",
            "Education",
            "Professional family",
            "Prior elected office",
            "Other government",
            "Military service",
            "Federal incumbency",
            "House service",
            "Historical donor ideology",
            "Prior voting ideology",
            "Party defection",
        ),
    )
)
PAPER, INK, MUTED = "#F7F5F0", "#1A1A1A", "#6B6B6B"
COLORS = ("#3D6F8C", "#92B1BD", "#C89D7C", "#DDD9D0", "#AAA69E")
BLOCK_LABELS = {**LABELS, "incumbency": "Joint D/R incumbency"}


def number(value, digits=3):
    return "unavailable" if value is None else f"{value:.{digits}f}"


def charts(output, coverage, fits, *, version=VERSION):
    plt.rcParams.update(
        {
            "font.family": "DejaVu Serif",
            "font.size": 11,
            "text.color": INK,
            "axes.labelcolor": INK,
            "axes.edgecolor": "#D6D3CC",
            "xtick.color": MUTED,
            "ytick.color": INK,
            "svg.hashsalt": version,
        }
    )
    captions = []
    for chart in ("trait-coverage", "predictive-value"):
        fig, ax = plt.subplots(figsize=(12, 8), facecolor=PAPER)
        ax.set_facecolor(PAPER)
        fig.subplots_adjust(left=0.30, right=0.95, top=0.79, bottom=0.22)
        for side in ("top", "right", "left"):
            ax.spines[side].set_visible(False)
        ax.tick_params(axis="both", length=0)
        if chart == "trait-coverage":
            selected = [
                next(r for r in coverage if r["cohort"] == "democrats" and r["trait"] == trait)
                for trait in TRAITS
            ]
            y = np.arange(len(selected))
            left = np.zeros(len(selected))
            for status, color in zip(STATUSES, COLORS):
                values = np.array([r[status] for r in selected])
                ax.barh(
                    y, values, left=left, color=color, height=0.65, label=status.replace("_", " ")
                )
                left += values
            ax.set(
                yticks=y,
                yticklabels=[
                    "Education records"
                    if version != VERSION and r["trait"] == "education"
                    else LABELS[r["trait"]]
                    for r in selected
                ],
                xlim=(0, 449),
                xlabel="Democratic candidate-contest records (449 total)",
            )
            ax.set_xticks([0, 100, 200, 300, 400, 449])
            ax.invert_yaxis()
            fig.legend(
                *ax.get_legend_handles_labels(),
                loc="lower left",
                bbox_to_anchor=(0.30, 0.105),
                ncol=3,
                frameon=False,
                fontsize=10,
            )
            title = "A biography is not a complete trait record"
            subtitle = "2026 House Democrats. Source observations, uncertainty and analytical values are distinct."
            note = (
                "Qualified values follow explicit successor rules, not universal verification. "
                "Positive military listings do not establish nonservice. Identity unknowns are never reference groups."
            )
            if version != VERSION:
                subtitle = "2026 House Democrats. Factual qualification is not analytical or contrast eligibility."
                note = (
                    "Qualified = explicit factual observation, not necessarily completed attainment, "
                    "election-day employment or an estimable contrast. Analytical counts are reported separately."
                )
        else:
            selected = [r for r in fits if r["status"] == "estimated"]
            y = np.arange(len(selected))
            for i, row in enumerate(selected):
                p = row["prediction"]
                gain = p["MAE_gain_share_pp"]
                if gain is None:
                    continue
                complete = p["complete"]
                if complete:
                    ax.plot([p["gain_ci_low"], p["gain_ci_high"]], [i, i], color="#C85A3D", lw=1.5)
                ax.plot(
                    gain,
                    i,
                    "o",
                    ms=5,
                    color="#C85A3D",
                    markerfacecolor="#C85A3D" if complete else PAPER,
                )
                label = (
                    f"n={p.get('population_candidates', row['n'])}, "
                    f"{p.get('population_states', row['state_clusters'])} states"
                )
                if not complete:
                    label += " *"
                ax.text(
                    1.02,
                    i,
                    label,
                    transform=ax.get_yaxis_transform(),
                    va="center",
                    fontsize=9,
                    clip_on=False,
                )
            ax.set(
                yticks=y,
                yticklabels=[
                    "Race (historical classifications)"
                    if version
                    in {
                        "house-characteristics-v7",
                        "house-characteristics-v8",
                        "house-characteristics-v9",
                    }
                    and r["trait"] == "race"
                    else "Historical Latino indicator"
                    if version
                    in {
                        "house-characteristics-v7",
                        "house-characteristics-v8",
                        "house-characteristics-v9",
                    }
                    and r["trait"] == "ethnicity"
                    else "Race (historical CAWP women)"
                    if version
                    in {
                        "house-characteristics-v3",
                        "house-characteristics-v4",
                        "house-characteristics-v5",
                        "house-characteristics-v6",
                    }
                    and r["trait"] == "race"
                    else BLOCK_LABELS[r["trait"]]
                    for r in selected
                ],
                xlabel="Baseline MAE minus trait-model MAE (vote-share pp)",
            )
            ax.axvline(0, color=MUTED, lw=1)
            ax.grid(axis="x", color="#D6D3CC", alpha=0.55)
            ax.set_axisbelow(True)
            ax.invert_yaxis()
            fig.subplots_adjust(right=0.77)
            title = "Do traits improve held-out predictions?"
            subtitle = "Each pair uses identical candidates. Different rows are not a common-sample trait ranking."
            note = (
                "Positive = lower error. 95% pointwise intervals refit the full state-held-out/person-purged pipeline. "
                "* Open dots: incomplete folds or deletion refits; diagnostic only. Provisional returns, not causal effects."
            )
            if version in {
                "house-characteristics-v3",
                "house-characteristics-v4",
                "house-characteristics-v5",
                "house-characteristics-v6",
            }:
                note += (
                    " Race compares explicit historical Black/White classifications "
                    "among CAWP women, not all candidates."
                )
            elif version in {
                "house-characteristics-v7",
                "house-characteristics-v8",
                "house-characteristics-v9",
            }:
                note += (
                    " Race and Latino-indicator comparisons use restricted historical "
                    "source-classified populations, not all nominees."
                )
        fig.text(0.055, 0.925, title, size=21, weight="bold")
        fig.text(0.055, 0.85, "\n".join(textwrap.wrap(subtitle, 110)), size=11, color=MUTED)
        fig.text(0.055, 0.035, "\n".join(textwrap.wrap(note, 125)), size=9, color=MUTED)
        for suffix in ("png", "svg"):
            fig.savefig(
                output / f"{chart}.{suffix}",
                dpi=160,
                metadata={"Date": None} if suffix == "svg" else {"Software": version},
            )
        plt.close(fig)
        captions.append({"id": chart, "title": title, "alt": f"{title}. {subtitle} {note}"})
    write_json(output / "captions.json", captions)
    return captions


def report(summary, fits, terms, coverage, sources, research):
    lines = [
        "# The full candidate-characteristics question",
        "",
        "Exploratory successor `house-characteristics-v1`, specified after earlier results "
        "but before these fits. Earlier analyses are preserved, not refitted or overwritten.",
        "",
        "## What the evidence supports",
        "",
        f"The inventory contains **{summary['candidate_records']:,} candidate-contest records**, "
        f"including **{summary['democrats']} Democrats** and **{summary['eligible_democrats']} "
        "qualified Democratic performance comparisons. Ten trait blocks support association "
        "estimates; five do not supply defensible contrasts.",
        "",
        "Historical donor ideology and the **joint Democratic/Republican-incumbency block** "
        "clear the declared 15-block Holm correction. The latter is not a test of the "
        "Democratic-incumbent coefficient alone. No completed paired prediction comparison "
        "has a pointwise 95% improvement interval wholly above zero.",
        "",
        "The performance outcome is Democratic two-party share minus the map-qualified "
        "presidential Democratic share, adjusted for district lean and lean squared. "
        "Coefficients below are vote-share percentage points, not margin points; multiply "
        "by two for D-minus-R margin. These are associations in selective cohorts, not "
        "causal effects of changing a nominee or individual-level voting behavior.",
        "",
        "## Every declared block",
        "",
        "| Block | Included candidates / states | Omnibus p | Holm p (15 blocks) | Paired MAE gain [95% interval] |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for r in fits:
        p = r.get("prediction")
        prediction = (
            f"{number(p['MAE_gain_share_pp'])} "
            f"[{number(p['gain_ci_low'])}, {number(p['gain_ci_high'])}]"
            if p and p["complete"]
            else f"Diagnostic only ({p['paired_candidates']}/{r['n']} predictions)"
            if p
            else "Unavailable: no qualified contrast"
        )
        lines.append(
            f"| {BLOCK_LABELS[r['trait']]} | {r['n']} / {r['state_clusters']} | "
            f"{number(r.get('omnibus_pvalue'), 6)} | {number(r['holm_pvalue'], 6)} | {prediction} |"
        )
    lines += [
        "",
        "Unsupported race/ethnicity models have explicit positive identities but no complete "
        "reference classification. Prior elected office, other government work and military "
        "service lack reviewed negative cases. Missing history is not nonservice. Their "
        "unavailable hypotheses remain in the correction family with p=1.",
        "",
        "## Estimated characteristic contrasts",
        "",
        "| Block / term | Association, share pp [pointwise 95% CI] |",
        "| --- | ---: |",
    ]
    for r in terms:
        if r["focal"]:
            lines.append(
                f"| {BLOCK_LABELS[r['trait']]} / `{r['term']}` | "
                f"{number(r['estimate_share_pp'])} [{number(r['ci_low'])}, {number(r['ci_high'])}] |"
            )
    lines += [
        "",
        "Age and service increments are ten years; donor ideology is +0.5 rightward units; "
        "prior voting ideology is +0.1 rightward units; defection is +5 percentage points. "
        "Categorical terms state the reference explicitly. Male/female are literal source "
        "`gender` codes, not inferred sex or independently verified self-identifications. "
        "Education is the highest documented completed credential, not guaranteed maximum attainment. "
        "Profession is one recognized reported family, not proof of paid employment or an exhaustive career.",
        "",
        "The positive donor-score association and negative prior-voting-score association "
        "are not interchangeable evidence for or against 'moderation': these are different "
        "constructs, increments and cohorts. Only donor ideology clears the 15-block correction. "
        "The separate Democratic-incumbent contrast includes zero; Republican incumbency "
        "is associated with lower Democratic performance. Neither establishes nominee-replacement effects.",
        "",
        "## Actual Democratic coverage",
        "",
        "| Trait | Qualified | Dated/reported | Uncertain | Unknown | Inapplicable |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in coverage:
        if r["cohort"] == "democrats":
            lines.append(
                "| " + " | ".join([LABELS[r["trait"]], *[str(r[s]) for s in STATUSES]]) + " |"
            )
    reviewed = [r for r in research["sources"] if r["status"] == "reviewed"]
    extracts = [r for r in reviewed if not r.get("original_bytes_acquired", True)]
    lines += [
        "",
        "The complete coverage CSV separately includes all 1,284 records and the 405 eligible "
        "Democratic nominees. Qualified field counts exceed some fitted samples: unknown D/R "
        "incumbency controls, outcome holds and sparse categories remain excluded. One observed "
        "degree or profession is not a complete biography. Education's two no-observation gaps "
        "remain Kristi Burke and Melissa McDonough; unreviewed extracted values are separately "
        "uncertain, not completed research.",
        "",
        "## Research and provenance",
        "",
        "Twelve new reviewed observations cover seven already-covered candidates: seven "
        "first-recorded trait fields, three newly qualified birthdays and two additional "
        "office/government observations. Newly covered people: **zero**. All 28,981 earlier "
        "observations and normalized collections are preserved; the current total is 28,993. "
        "Partial/secondary birth reports already held are not counted as newly discovered "
        "birth fields. The complete comparison is in `data/house-characteristics-baseline.json`.",
        "",
        f"This bounded follow-up reviewed {len(reviewed)} acquired sources or explicit rendered "
        f"extracts from {len(research['sources'])} exact-context leads. {len(extracts)} use "
        "preserved public-index extracts of official Michigan biographies after direct PDF "
        "requests failed. Their hashes identify the retained extracts, **not original PDFs**; "
        "the failed requests remain in the receipts. Other receipts distinguish downloaded "
        "originals. A request failure or irrelevant search is never a negative trait value.",
        "",
        "Three exact historical birthdays come from those official extracts. Four additional "
        "Democratic birth dates already held in official House Historian profiles receive "
        "explicit successor-only age decisions. Secondary incoming-member birthday claims stay "
        "descriptive. Religion retains literal historical questionnaire, third-party and "
        "self-description records; Jain heritage is not recoded as current membership. "
        "Navajo tribal identification and Mexican-/Indian-American self-descriptions are "
        "retained without inferred census race or negative ethnicity.",
        "",
        "All 179 Democratic Directory education/career sections have recorded literal coding "
        "reviews. The source-defined Clerk veteran roster supplies positive service values "
        "only. Existing machine-extracted values remain visible with row-level references "
        "and uncertain coding; they are not silently promoted. All old descriptive `model_ready` "
        "flags stay false. Successor field eligibility is explicit and retrospective, never "
        "a prospective-model qualification.",
        "",
        "An apparent adjacent-biography military section in Lois Frankel's normalized profile "
        "is withheld pending original-page review; it is not asserted as her service or proof "
        "of nonservice. A Sean McCann photographer/podcaster namesake is rejected. Parent-only "
        "religious descriptions and an endorser's Navajo identity are not candidate identities. "
        "Earlier rejection records remain unchanged.",
        "",
        "The frozen initial audit predates code reconciliation: its race/ethnicity source "
        "counts overlap and it omitted some inherited extracted observations. It is retained "
        "as history, not used to claim discovery gains. The final coverage/table correct these "
        "definitions. Newly standardized analytical fields are not newly researched people.",
        "",
        "## Selection, uncertainty and limitations",
        "",
        "Each trait has its own complete-case cohort. Baseline and augmented predictions use "
        "identical candidates within each row, holding out entire states and purging the held-out "
        "people from training. Unknown incumbency is not zero. Legislative measures require "
        "verified incumbents; no voting record is not zero ideology or perfect unity. "
        "Incomplete folds/deletion fits have no predictive interval and are diagnostic only.",
        "",
        "Selection summaries report state coverage, incumbency, district-lean bands, provisional "
        "leading status and every exclusion. Missingness is selective, particularly for winners "
        "and incumbents; no missing-at-random claim is made. Competitive-district, "
        "verified-incumbent, credential-coding and state-deletion sensitivities are downloadable. "
        "Sparse categories are not merged into reference groups. Categorical and source "
        "uncertainty limits scope even when a numerical association is estimable.",
        "",
        f"The source catalog resolves {len(sources):,} URL/hash receipts. Inherited missing "
        "retrieval dates are explicitly unknown, not invented. Full supporting values and "
        "qualifications are in the candidate-by-trait CSV/JSONL and referenced normalized "
        "observation table. Remaining gaps have source-review dispositions; this was a bounded "
        "research pass, not an exhaustive search or universal biography completion.",
        "",
        "## Files and replay",
        "",
        "`coverage.csv`, `candidate-traits.csv`, `source-receipts.json`, `fits.csv`, "
        "`terms.csv`, `predictions.csv`, `folds.jsonl.gz`, `state-deletions.csv`, "
        "`selection.csv`, `selection-summary.csv`, `sensitivity.csv` and `remaining-gaps.csv` "
        "are complete queries, not metadata-only downloads. Both current ZIPs include this "
        "successor; the figure package contains the exact complete-query ZIP.",
        "",
        "Replay with `python -m which_candidate.house_project --evidence-only`. This refreshes "
        "evidence and the successor without refitting earlier frozen analyses. Original "
        "historical HTML/PDF caches are not required. No website deployment is performed.",
        "",
    ]
    return "\n".join(lines)


def source_urls(value, lookup):
    found = set()
    if isinstance(value, dict):
        for k, v in value.items():
            if k in {"url", "origin_url", "resolved_url"} and isinstance(v, str):
                found.add(v)
            elif k in {"id", "source_id"} and isinstance(v, str):
                found.update(lookup.get(v, []))
            else:
                found.update(source_urls(v, lookup))
    elif isinstance(value, list):
        for v in value:
            found.update(source_urls(v, lookup))
    return {u for u in found if u.startswith(("https://", "http://"))}


def literal_preview(value):
    if isinstance(value, dict):
        preferred = [
            value.get(k)
            for k in (
                "source_text",
                "religion_literal",
                "identity_group",
                "fragment",
                "value",
                "reviewed_or_reported",
                "existing",
                "additional",
                "inherited_source_values",
                "birth_claims",
                "partial_birth_report",
                "birth_year_literal",
            )
            if value.get(k) is not None
        ]
        return "; ".join(literal_preview(v) for v in preferred)[:280]
    if isinstance(value, list):
        return "; ".join(dict.fromkeys(literal_preview(v) for v in value[:3]))[:280]
    return "" if value is None else str(value)[:280]


STYLE = """
body{margin:0;background:#f7f5f0;color:#1a1a1a;font:17px/1.6 Georgia,serif}
main{max-width:1120px;padding:35px 22px 65px;margin:auto}h1{font-size:2.4rem;line-height:1.15}
h2{margin-top:2.2em;line-height:1.25}a{color:#315d77}nav a{margin-right:20px}
p{max-width:900px}img{width:100%;height:auto}figure{margin:35px 0}
.scroll,.table-wrap{overflow:auto;max-width:100%;margin:24px 0}table{border-collapse:collapse;font-size:14px}
th,td{border-bottom:1px solid #d6d3cc;text-align:left;padding:9px;vertical-align:top}
th{position:sticky;top:0;background:#eeeae1}#candidates{min-width:2400px}
#candidates th:first-child,#candidates td:first-child{min-width:160px}
#candidates td{min-width:125px}details p{max-width:250px;white-space:normal}
summary{cursor:pointer}select,input{font:inherit;max-width:100%;padding:7px;margin:6px 12px 6px 0}
.filters{display:flex;flex-wrap:wrap;gap:8px}code{overflow-wrap:anywhere;font-size:.85em}
.muted,figcaption{color:#6b6b6b;font-size:14px}td a{display:block;overflow-wrap:anywhere}
[hidden]{display:none!important}@media(max-width:500px){main{padding:20px 14px}h1{font-size:1.8rem}}
"""
SCRIPT = """
const rows=[...document.querySelectorAll('#candidates tbody tr')];
rows.forEach((r,i)=>r.dataset.order=i);
let previousSort='';
function filter(){
 const q=document.querySelector('#search').value.toLowerCase();
 const party=document.querySelector('#party').value,state=document.querySelector('#state').value;
 let count=0;
 for(const r of rows){
  r.hidden=!!((party&&r.dataset.party!==party)||(state&&r.dataset.state!==state)||
             (q&&!r.textContent.toLowerCase().includes(q)));
  if(!r.hidden)count++;
 }
 document.querySelector('#count').textContent=count+' candidate records';
 const sort=document.querySelector('#sort').value;
 if(sort!==previousSort){
  const score=r=>r.dataset.gap===''?-Infinity:Number(r.dataset.gap);
  const ordered=[...rows].sort((a,b)=>sort==='gap'?score(b)-score(a):a.dataset.order-b.dataset.order);
  document.querySelector('#candidates tbody').append(...ordered);previousSort=sort;
 }
}
for(const id of ['search','party','state','sort'])document.querySelector('#'+id).addEventListener('input',filter);
filter();
"""


def build(root, *, version=VERSION, reporter=report, rows_override=None):
    root = Path(root)
    out = f"results/{version}"
    results = root / out
    output = root / "publication" / version.removeprefix("house-")
    output.mkdir(parents=True, exist_ok=True)
    rows = (
        rows_override
        if rows_override is not None
        else read_rows(results / "candidate-traits.jsonl.gz")
    )
    fits = read_rows(results / "fits.jsonl.gz")
    terms = read_rows(results / "terms.jsonl.gz")
    summary = json.loads((results / "summary.json").read_text())
    coverage = summary["coverage"]
    catalog = json.loads((results / "source-receipts.json").read_text())
    research = json.loads((root / "data/house-characteristics-receipts.json").read_text())
    remaining = [
        r
        for r in rows
        if r["status"] not in {"qualified", "inapplicable"}
        or version != VERSION
        and not r["field_eligible"]
        and r["status"] != "inapplicable"
    ]
    write_csv(
        results / "remaining-gaps.csv",
        [
            {
                k: r[k]
                for k in (
                    "candidate_id",
                    "contest_id",
                    "name",
                    "state",
                    "district",
                    "party",
                    "trait",
                    "status",
                    "eligibility_reason",
                )
            }
            for r in remaining
        ],
    )
    markdown = reporter(summary, fits, terms, coverage, catalog, research)
    (results / "report.md").write_text(markdown)
    captions = charts(output, coverage, fits, version=version)
    lookup = defaultdict(set)
    for receipt in catalog:
        lookup[receipt.get("id")].add(receipt["url"])
        for source_id in receipt.get("source_ids", []):
            lookup[source_id].add(receipt["url"])
    grouped = defaultdict(dict)
    for row in rows:
        grouped[(row["contest_id"], row["candidate_id"])][row["trait"]] = row
    body = []
    for _, traits in sorted(
        grouped.items(),
        key=lambda item: (
            item[1]["age"]["state"],
            item[1]["age"]["district"],
            item[1]["age"]["name"],
        ),
    ):
        person = traits["age"]
        cells = []
        for trait in TRAITS:
            row = traits[trait]
            value = row["value"]
            label = row.get(
                "display_value",
                str(value) if value is not None else row["status"].replace("_", " "),
            )
            urls = source_urls(row["evidence"], lookup)
            links = "".join(
                f'<a href="{html.escape(u, quote=True)}" rel="noopener noreferrer">Source {i}</a>'
                for i, u in enumerate(sorted(urls), start=1)
            )
            preview = literal_preview(row["source_recorded_value"])
            cells.append(
                f"<td><details><summary>{html.escape(label)}</summary>"
                f"<p><strong>{html.escape(row['status'])}</strong>: "
                f"{html.escape(row['eligibility_reason'])}</p>"
                f"<p>{html.escape(preview)}</p>{links}"
                '<a href="../../results/house-characteristics-v1/candidate-traits.csv">'
                "Complete values and receipts</a></details></td>"
            )
        body.append(
            f'<tr data-party="{html.escape(person["party"], quote=True)}" '
            f'data-state="{person["state"]}" data-gap="'
            f'{person["performance_gap_share_pp"] if person["performance_eligible"] else ""}">'
            f"<td>{html.escape(person['name'])}"
            f"<br>{person['state']}-{person['district']}<br>{html.escape(person['party'])}</td>"
            f"<td>{number(person['performance_gap_share_pp'], 2)}<br>"
            f"{'Qualified descriptive gap; not a candidate effect.' if person['performance_eligible'] else 'No qualified comparison.'}</td>"
            + "".join(cells)
            + "</tr>"
        )
    figures = "".join(
        f'<figure><img src="{c["id"]}.png" width="1920" height="1280" '
        f'alt="{html.escape(c["alt"], quote=True)}"><figcaption>'
        f"{html.escape(c['alt'])}</figcaption></figure>"
        for c in captions
    )

    def options(values):
        return "".join(
            f'<option value="{html.escape(v, quote=True)}">{html.escape(v)}</option>'
            for v in sorted(values)
        )

    render_article = article
    if version == "house-characteristics-v9":
        from .characteristics_v9_publication import article as render_article

    content = (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Full House characteristics successor</title><style>{STYLE}</style></head>"
        '<body><main><nav><a href="../report.html">Earlier frozen findings</a>'
        '<a href="#browser">All-candidate trait browser</a>'
        '<a href="../../results/house-characteristics-v1/candidate-traits.csv">Complete trait CSV</a>'
        '<a href="../../results/house-characteristics-v1/candidate-traits.jsonl.gz">Complete JSONL</a>'
        "</nav><h1>The full candidate-characteristics question</h1>"
        + render_article(markdown)
        + figures
        + '<section id="browser"><h2>Explore all 1,284 candidate records</h2>'
        "<p>Every trait is separate. Expand a cell for its qualification and source links. "
        "Reported or uncertain values are not analytical reference groups. Table scrolls "
        "horizontally; all rows and findings remain available without JavaScript.</p>"
        '<div class="filters"><label>Search <input id="search" type="search"></label>'
        '<label>Party <select id="party"><option value="">All parties</option>'
        + options({r["party"] for r in rows})
        + "</select></label>"
        '<label>State <select id="state"><option value="">All states</option>'
        + options({r["state"] for r in rows})
        + '</select></label><label>Order <select id="sort"><option value="state">State and name</option>'
        '<option value="gap">District gap, high to low</option></select></label></div>'
        '<p id="count" aria-live="polite">1,284 candidate records</p>'
        '<div class="scroll"><table id="candidates"><thead><tr><th>Candidate</th><th>District gap (share pp)</th>'
        + "".join(f"<th>{LABELS[t]}</th>" for t in TRAITS)
        + "</tr></thead><tbody>"
        + "".join(body)
        + "</tbody></table></div></section>"
        f"<script>{SCRIPT}</script></main></body></html>"
    )
    if version != VERSION:
        content = content.replace("house-characteristics-v1/", f"{version}/")
        content = content.replace(
            '<nav><a href="../report.html">',
            '<nav><a href="../characteristics-v1/report.html">Frozen v1</a>'
            '<a href="../report.html">',
        )
    if version in {"house-characteristics-v8", "house-characteristics-v9"}:
        content = content.replace(
            '<a href="../report.html">',
            "".join(
                f'<a href="../characteristics-v{i}/report.html">Frozen v{i}</a>'
                for i in range(2, int(version.rsplit("v", 1)[-1]))
            )
            + '<a href="../report.html">',
            1,
        )
    if version == "house-characteristics-v9":
        content = content.replace(
            "</style>", "pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>", 1
        )
    (output / "report.html").write_text(content)
    write_csv(output / "trait-coverage.csv", [r for r in coverage if r["cohort"] == "democrats"])
    write_csv(
        output / "predictive-value.csv",
        [
            {"trait": r["trait"], "n": r["n"], "states": r["state_clusters"], **r["prediction"]}
            for r in fits
            if r["status"] == "estimated"
        ],
    )
    write_json(
        output / "manifest.json",
        {
            "version": version,
            "website_deployed": False,
            "inputs": {
                name: fingerprint(root / name)
                for name in (
                    f"{out}/summary.json",
                    f"{out}/candidate-traits.jsonl.gz",
                    "data/house-characteristics-receipts.json",
                )
            },
            "files": {
                p.name: fingerprint(p)
                for p in sorted(output.iterdir())
                if p.is_file() and p.name != "manifest.json"
            },
        },
    )
    return {
        "publication_files": len(list(output.iterdir())),
        "remaining_trait_gaps": len(remaining),
    }
