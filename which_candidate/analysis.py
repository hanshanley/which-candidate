import importlib.metadata
import re
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path

from .benchmarks import clerk_senate_2024, district_presidential, presidential_2024
from .features import FeatureSources
from .models import PRIMARY, SUPPLEMENTAL, associations, folds_and_predictions, validation_summary
from .pipeline import code_receipts, csv_bytes, verify_output
from .sources import load_sources
from .storage import confined, fingerprint, read_rows, write_json, write_rows


def analysis_recipe(data_dir, returns, project):
    return {
        "returns_manifest": fingerprint(returns / "manifest.json"),
        "source_manifests": {
            name: fingerprint(data_dir / name)
            for name in (
                "sources.json",
                "research-sources.json",
                "supplemental-returns-sources.json",
            )
        },
        "code": code_receipts(),
        "specification": fingerprint(project / "docs/ANALYSIS_SPEC.md"),
        "dependency_lock": fingerprint(project / "requirements.lock"),
        "libraries": {
            name: importlib.metadata.version(name)
            for name in ("numpy", "scipy", "matplotlib", "pypdf", "openpyxl")
        },
    }


def candidate_queries(contests, candidates, features, district_benchmarks, state_benchmarks):
    by_id = {r["candidate_election_id"]: r for r in features}
    candidate_by_id = {r["candidate_election_id"]: r for r in candidates}
    by_contest = defaultdict(list)
    for candidate in candidates:
        by_contest[candidate["contest_id"]].append(candidate)
    districts = {(r["map_year"], r["state"], r["district"]): r for r in district_benchmarks}
    states = {(r["year"], r["state"]): r for r in state_benchmarks}
    result = []
    for contest in contests:
        if contest["chamber"] not in ("house", "senate"):
            continue
        year, chamber, state = contest["year"], contest["chamber"], contest["state"]
        d_id = contest["D_candidate_election_id"]
        d = by_id.get(d_id, {})
        opponent = [
            r
            for r in by_contest[contest["contest_id"]]
            if r["party_group"] == "R" and r["named_candidate"]
        ]
        r = by_id.get(opponent[0]["candidate_election_id"], {}) if len(opponent) == 1 else {}
        presidential_year = year if year % 4 == 0 else year - 2
        district = "00" if contest["district"] == "AL" else contest["district"]
        full_term = re.fullmatch(r"(\d{2})-FULLTERM", district)
        if full_term:
            district = full_term.group(1)
        benchmark = (
            districts.get((year, state, district))
            if chamber == "house"
            else states.get((presidential_year, state))
        )
        reasons = list(contest["exclusion_reasons"])
        if year > 2024:
            reasons.append("provisional_2026_not_in_historical_analysis")
        p = benchmark.get("presidential_D_two_party_share_pct") if benchmark else None
        if p is None:
            reasons.append("qualified_map_or_state_presidential_benchmark_missing")
        eligible = not reasons
        gap = contest["D_two_party_share_pct"] - p if eligible else None
        result.append(
            {
                **contest,
                "D_name": candidate_by_id.get(d_id, {}).get("name"),
                "R_name": opponent[0]["name"] if len(opponent) == 1 else None,
                "R_candidate_election_id": opponent[0]["candidate_election_id"]
                if len(opponent) == 1
                else None,
                "person_group": d.get("person_group", f"unresolved:{contest['contest_id']}"),
                "bioguide_id": d.get("bioguide_id"),
                "D_fec_id": d.get("fec_id"),
                "identity_status": d.get("identity_status", "no_unique_D_nominee"),
                "D_incumbent": d.get("incumbent"),
                "R_incumbent": r.get("incumbent"),
                "service_verified_incumbent": d.get("service_verified_incumbent"),
                "incumbency_conflict": d.get("incumbency_conflict", False),
                "nokken_poole_dim1": d.get("nokken_poole_dim1"),
                "party_unity_score": d.get("party_unity_score"),
                "party_unity_votes": d.get("party_unity_votes"),
                "lagged_congress": d.get("lagged_congress"),
                "age_years": d.get("age_years"),
                "chamber_tenure_years": d.get("chamber_tenure_years"),
                "source_recorded_gender": d.get("source_recorded_gender"),
                "born_in_state": d.get("born_in_state"),
                "birth_state": d.get("birth_state"),
                "religion": d.get("religion"),
                "reported_catholic": d.get("reported_catholic"),
                "feature_evidence": d.get("feature_evidence", []),
                "presidential_year": presidential_year,
                "benchmark_district": district if chamber == "house" else None,
                "presidential_D_two_party_share_pct": p,
                "benchmark_evidence": benchmark,
                "eligible": eligible,
                "analysis_exclusion_reasons": sorted(set(reasons)),
                "descriptive_gap_share_pp": gap,
                "won_two_party_comparison": contest["D_two_party_share_pct"] > 50
                if contest["D_two_party_share_pct"] is not None
                else None,
            }
        )
    return result


def coverage_rows(panel):
    groups = defaultdict(list)
    for row in panel:
        groups[(row["year"], row["chamber"], row["won_two_party_comparison"])].append(row)
    result = []
    for (year, chamber, winner), rows in sorted(groups.items(), key=lambda item: str(item[0])):
        result.append(
            {
                "year": year,
                "chamber": chamber,
                "D_won_two_party_comparison": winner,
                "contests": len(rows),
                "eligible": sum(r["eligible"] for r in rows),
                "identified_D": sum(r["bioguide_id"] is not None for r in rows),
                "D_incumbency_observed": sum(r["D_incumbent"] is not None for r in rows),
                "D_incumbency_conflicts": sum(r["incumbency_conflict"] for r in rows),
                "lagged_ideology_observed": sum(r["nokken_poole_dim1"] is not None for r in rows),
                "party_unity_observed": sum(r["party_unity_score"] is not None for r in rows),
                "birth_state_observed": sum(r["born_in_state"] is not None for r in rows),
                "explicit_religion_observed": sum(r["religion"] is not None for r in rows),
                "race_ethnicity_observed": 0,
            }
        )
    return result


def render_report(panel, terms, validation, coverage, fits):
    focal = [r for r in terms if r["primary_focal"]]
    results = {(r["chamber"], r["model"]): r for r in focal}
    house_inc, senate_inc = (results[(c, "incumbency")] for c in ("house", "senate"))

    def pvalue(value):
        return "<0.001" if value < 0.001 else f"{value:.3f}"

    lines = [
        "# Which Democrats outperformed? Historical candidate analysis",
        "",
        "## Findings",
        "",
        "The table reports **adjusted associations**, not causal effects of replacing a nominee. "
        "Development elections are **2016–2022**; **2024 is held out**. Positive estimates "
        "mean higher Democratic two-party vote share after constituency lean and election-cycle "
        "adjustment. One share point equals two D-minus-R margin points.",
        "",
        f"**Incumbency is the strongest recurring pattern:** Democratic incumbents are "
        f"associated with **{house_inc['estimate_share_pp']:+.2f} share points in the House** "
        f"and **{senate_inc['estimate_share_pp']:+.2f} in the Senate**. The Senate estimate "
        "is much less precise and does not pass the six-test Holm correction. Adding "
        "incumbency improves the held-out 2024 predictions in both chambers.",
        "",
        "**No broad moderation or party-defection advantage is established.** Both primary "
        "ideology and party-defection intervals include zero in both chambers. House tenure "
        "has a positive adjusted association, but adding it worsens 2024 predictive error. "
        "The source-recorded gender comparison does not survive multiplicity adjustment. "
        "These results do not justify a causal candidate-selection rule.",
        "",
        "| Chamber | Comparison | Share-point association | Pointwise 95% interval | N | State clusters | Holm p |",
        "|---|---|---:|---|---:|---:|---:|",
    ]
    for row in focal:
        label = PRIMARY[row["model"]][1]
        lines.append(
            f"| {row['chamber'].title()} | {label} | {row['estimate_share_pp']:+.2f} | "
            f"[{row['ci_low']:+.2f}, {row['ci_high']:+.2f}] | {row['n']} | "
            f"{row['state_clusters']} | {pvalue(row['holm_pvalue'])} |"
        )
    lines += [
        "",
        "Incumbency comparisons include D and R incumbent indicators. All other comparisons "
        "are **among verified same-chamber Democratic incumbents**, separately adjusted, "
        "not all Democratic nominees. Ideology is continuous: rightward is not a categorical "
        "moderate/progressive label. Defection is disagreement with one's party on party-unity "
        "votes, not a measure of every bipartisan vote. Age, tenure and source-recorded gender "
        "are not mutually adjusted demographic effects. Pointwise intervals are not simultaneous; "
        "Holm p-values adjust the six primary focal-feature tests per chamber.",
        "",
        "## Supplemental birthplace and religion comparisons",
        "",
        "Complete pre-election official Congressional Directory editions provide biographies "
        "furnished or authorized by member offices. These two hypotheses were specified "
        "**after the initial six-feature run, before extracting biography fields or viewing "
        "their coefficients**. They are supplemental, not added retroactively to the original "
        "confirmatory family. Compare only verified Democratic incumbents with explicit fields; "
        "unknown religion is never nonreligion and unknown birthplace is never out-of-state.",
        "",
        "| Chamber | Comparison | Share-point association | Pointwise 95% interval | N | Nominal p |",
        "|---|---|---:|---|---:|---:|",
    ]
    for row in terms:
        if row["supplemental_focal"]:
            lines.append(
                f"| {row['chamber'].title()} | {SUPPLEMENTAL[row['model']][1]} | "
                f"{row['estimate_share_pp']:+.2f} | "
                f"[{row['ci_low']:+.2f}, {row['ci_high']:+.2f}] | {row['n']} | "
                f"{pvalue(row['pvalue'])} |"
            )
    lines += [
        "",
        "These pointwise results are **not corrected across supplemental/sensitivity tests**. "
        "Birthplace is not residence or other local ties. Optional religion disclosure creates "
        "an especially selected sample; the Catholic-versus-other-explicit-report contrast "
        "does not compare all religions or all nominees. Inspect held-out errors below before "
        "interpreting a positive in-sample association as useful prediction. Complete literal "
        "fields, source pages, publication dates and unknowns are retained.",
        "",
        "## Locked 2024 validation",
        "",
        "Every prediction trains on **earlier elections only**, excluding the entire target "
        "state and identified repeated target people. Both models use identical training/test "
        "rows. Baseline controls constituency lean and presidential-versus-midterm status. "
        "It cannot know the held-out national electoral environment. Positive MAE improvement "
        "means candidate features improved prediction; negative means they worsened it.",
        "",
        "| Chamber | Feature | 2024 N | Baseline MAE | Feature MAE | Improvement |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in validation:
        if row["year"] == 2024:
            lines.append(
                f"| {row['chamber'].title()} | {row['model']} | {row['n']} | "
                f"{row['baseline_mae']:.2f} | {row['feature_mae']:.2f} | "
                f"{row['mae_improvement']:+.2f} |"
            )
    lines += [
        "",
        "`validation.csv` includes all 2018/2020/2022/2024 chronological backtests, RMSE, "
        "signed error and explicitly retrospective, within-cycle-centered error. A favorable "
        "in-sample coefficient is not proof of a generally better candidate-selection rule.",
        "",
        "## Coverage",
        "",
        "| Year | Chamber | All contests | Eligible D/R benchmark comparisons |",
        "|---|---|---:|---:|",
    ]
    counts = defaultdict(lambda: [0, 0])
    for row in panel:
        counts[(row["year"], row["chamber"])][0] += 1
        counts[(row["year"], row["chamber"])][1] += row["eligible"]
    for (year, chamber), (count, eligible) in sorted(counts.items()):
        lines.append(f"| {year} | {chamber} | {count} | {eligible} |")
    conflicts = sum(row["D_incumbency_conflicts"] for row in coverage)
    lines += [
        "",
        f"**{conflicts} Democratic source-incumbency/dated-service disagreements** are retained; "
        "dated same-chamber terms take precedence for resolved people. Full win/loss/unknown-outcome coverage is "
        "in `coverage.csv`. Members have better biographical coverage than losing challengers; "
        "the report does not pretend otherwise. Excluded contests and provisional 2026 rows "
        "remain in the complete candidate-query download.",
        "",
        "## What remains unanswered",
        "",
        "**Race/ethnicity, military service, occupation, education, "
        "issue-specific positions and attendance are not measured here.** No inference from "
        "names, photos, party, current residence or missing records fills those fields. "
        "The sources used do not supply a qualified all-nominee panel, particularly for losers. "
        "The crosswalk's recorded gender field is not a verified self-identification panel.",
        "",
        "This analysis cannot establish a causal moderation or party-defection advantage. "
        "Candidate selection, district fit, opponent quality, retirement, fundraising and "
        "unobserved campaign conditions can confound associations. Legislative comparisons "
        "condition on having survived into office and on reelection; first-term incumbents "
        "often lack the deliberately lagged record. Repeated people and constituencies are "
        "covered conservatively by state-held-out validation and state-clustered inference. "
        "Senate samples are small. No 2026 outcome contributes to estimation.",
        "",
        "## Audits and sensitivities",
        "",
        "`model-fits.jsonl.gz` and `model-terms.csv` include the prespecified joint ideology/"
        "defection model, ideology-by-lean interaction, competitive 40–60% constituencies, "
        "linear-only lean and separate-cycle estimates, including models that could not be "
        "estimated. Main models never use 2024 to select a specification. "
        "`alternate-2024-benchmarks.csv` shows how validation gaps change when the same 2024 "
        "map uses its recalculated 2020 presidential vote instead of 2024.",
        "",
        "One small-Senate ideology-by-lean interaction is nominally significant "
        "(see the complete term table). Its positive interaction indicates a more rightward "
        "association in *bluer*, not redder, constituencies. It is one of many uncorrected "
        "sensitivity tests, is not independently validated, and does not establish a general "
        "moderation advantage. Competitive-seat and joint ideology/defection results likewise "
        "do not establish a broad advantage. Sparse cycle-specific Senate fits remain holds.",
        "",
        "House presidential baselines are Daily Kos Elections/The Downballot's calculated "
        "election-map-specific estimates, **not certified district presidential compilations "
        "or independently audited boundaries**. Published 2016/2018 rounding remains. "
        "Senate uses official FEC state returns. 2024 Senate data come from the official "
        "Clerk report; special scopes and independent-led races are not mixed into D/R estimates. "
        "Full-career NOMINATE is never used. Voteview Nokken-Poole and party-unity features "
        "use only a completed Congress before each election, but are retrieved retrospective "
        "estimates, not archived prospective score vintages.",
        "",
        "## Reproducibility",
        "",
        "See `docs/ANALYSIS_SPEC.md` for the frozen estimands, formulas and units. "
        "`candidate-queries.csv` retains every contest; `candidate-features.csv` retains "
        "all named D/R feature queries, including losers and exclusions. "
        "Complete source originals remain in the private content-addressed cache. "
        "Every feature, benchmark, match, exclusion, fitted term, fold and prediction is "
        "downloadable with exact source rows and checksums. Builds are network-free. "
        "The private local replay package is not permission to redistribute source spreadsheets; "
        "The Downballot requests attribution and no reproduction of entire workbooks.",
        "",
    ]
    return "\n".join(lines)


def render_figures(destination, terms):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator

    labels = [
        "Democratic incumbent",
        "Rightward ideology (+0.1)",
        "Party defection (+5 pp)",
        "Age (+10 years)",
        "Chamber tenure (+10 years)",
        "Source-recorded F vs M",
    ]
    with plt.rc_context(
        {"font.family": "DejaVu Sans", "font.size": 9, "svg.hashsalt": "which-candidate-v1"}
    ):
        figure, axes = plt.subplots(1, 2, figsize=(10.5, 4.7), sharey=True)
        for axis, chamber in zip(axes, ("house", "senate")):
            records = {
                r["model"]: r for r in terms if r["chamber"] == chamber and r["primary_focal"]
            }
            axis.axvline(0, color="#b4b4b4", linewidth=0.8, zorder=1)
            for index, model in enumerate(PRIMARY):
                row = records.get(model)
                if row:
                    value, low, high = (
                        row[key] for key in ("estimate_share_pp", "ci_low", "ci_high")
                    )
                    axis.errorbar(
                        value,
                        5 - index,
                        xerr=[[value - low], [high - value]],
                        fmt="o",
                        color="#34566d",
                        markersize=4,
                        capsize=2,
                        linewidth=1.1,
                        zorder=3,
                    )
            axis.set_title(chamber.title(), loc="left", fontsize=11, pad=12)
            axis.set_yticks(range(6), labels[::-1])
            axis.set_xlabel("Association with Democratic vote share (pp)")
            axis.xaxis.set_major_locator(MaxNLocator(5))
            axis.grid(axis="x", color="#ededed", linewidth=0.6)
            axis.set_axisbelow(True)
            for spine in ("top", "right", "left"):
                axis.spines[spine].set_visible(False)
            axis.spines["bottom"].set_color("#cccccc")
            axis.tick_params(axis="both", length=0)
            axis.set_ylim(-0.6, 5.6)
        figure.suptitle(
            "Adjusted candidate associations, 2016–2022", x=0.03, ha="left", fontsize=13
        )
        figure.text(
            0.03,
            0.025,
            "Pointwise state-clustered 95% intervals. Except incumbency, comparisons are among "
            "verified Democratic incumbents. Not causal.",
            fontsize=8,
            color="#555555",
        )
        figure.tight_layout(rect=(0.015, 0.07, 1, 0.94), w_pad=3)
        figure.savefig(destination / "adjusted-associations.svg", metadata={"Date": None})
        figure.savefig(
            destination / "adjusted-associations.png",
            dpi=180,
            metadata={"Software": "which-candidate"},
        )
        plt.close(figure)


def analyze(data_dir, returns, output, project=None):
    data_dir, returns, output = (Path(p).resolve() for p in (data_dir, returns, output))
    project = Path(project).resolve() if project else Path(__file__).resolve().parent.parent
    manifests = {
        name: load_sources(data_dir / name)
        for name in ("sources.json", "research-sources.json", "supplemental-returns-sources.json")
    }
    frozen = verify_output(returns)
    if frozen["recipe"]["source_manifest"] != fingerprint(data_dir / "sources.json"):
        raise ValueError("Frozen returns do not match the selected original source receipt")
    recipe = analysis_recipe(data_dir, returns, project)
    if output.exists():
        existing = verify_output(output)
        if existing["recipe"] != recipe:
            raise ValueError(
                "Changed analysis inputs, specification or code require a new output directory"
            )
        return {"status": "verified_unchanged", "output": str(output), "source_parses": 0}
    candidates = read_rows(returns / "candidate-returns.jsonl.gz")
    contests = read_rows(returns / "contests.jsonl.gz")
    district_rows, state_rows, extra_tables = [], [], {}
    for row in contests:
        if row["chamber"] == "president" and row["eligible_descriptive_two_party_share"]:
            state_rows.append(
                {
                    "year": row["year"],
                    "state": row["state"],
                    "presidential_D_two_party_share_pct": row["D_two_party_share_pct"],
                    "source_id": row["source_id"],
                    "contest_id": row["contest_id"],
                }
            )
    for spec in manifests["research-sources.json"]["sources"]:
        if spec["kind"] == "house_presidential":
            district_rows.extend(district_presidential(confined(data_dir, spec["path"]), spec))
    for spec in manifests["supplemental-returns-sources.json"]["sources"]:
        path = confined(data_dir, spec["path"])
        if spec["kind"] == "clerk_senate_2024":
            a, b, pages, native, decisions = clerk_senate_2024(path, spec)
            candidates.extend(a)
            contests.extend(b)
            extra_tables.update(
                {
                    "clerk-2024-pages": pages,
                    "clerk-2024-senate-native": native,
                    "clerk-2024-senate-decisions": decisions,
                    "clerk-2024-senate-candidates": a,
                    "clerk-2024-senate-contests": b,
                }
            )
        elif spec["kind"] == "fec_president_2024":
            extra_tables["fec-2024-state-president"] = presidential_2024(path, spec)
            state_rows.extend(extra_tables["fec-2024-state-president"])
    feature_sources = FeatureSources(manifests["research-sources.json"], data_dir)
    features = [
        feature_sources.features(row)
        for row in candidates
        if row["chamber"] in ("house", "senate")
        and row["named_candidate"]
        and row["party_group"] in ("D", "R")
    ]
    panel = candidate_queries(contests, candidates, features, district_rows, state_rows)
    fits, terms = associations(panel)
    folds, predictions = folds_and_predictions(panel)
    predicted = {
        r["candidate_election_id"]: r
        for r in predictions
        if r["kind"] == "retrospective_state_held_out"
    }
    for row in panel:
        item = predicted.get(row["D_candidate_election_id"])
        row["cross_fitted_expected_share_pct"] = item["expected_share_pct"] if item else None
        row["cross_fitted_overperformance_share_pp"] = (
            item["cross_fitted_overperformance_share_pp"] if item else None
        )
        row["retrospective_fold_id"] = item["fold_id"] if item else None
    coverage = coverage_rows(panel)
    validation = validation_summary(predictions)
    alternate = [
        {
            "contest_id": r["contest_id"],
            "D_name": r["D_name"],
            "same_year_gap_share_pp": r["descriptive_gap_share_pp"],
            "alternate_2020_gap_share_pp": r["D_two_party_share_pct"]
            - r["benchmark_evidence"]["alternate_D_two_party_share_pct"],
        }
        for r in panel
        if r["eligible"] and r["year"] == 2024 and r["chamber"] == "house"
    ]
    tables = {
        **extra_tables,
        "district-presidential-benchmarks": district_rows,
        "state-presidential-benchmarks": state_rows,
        "fec-2024-nominee-roster": feature_sources.nominees,
        "directory-biographies": feature_sources.biographies,
        "candidate-features": features,
        "candidate-queries": panel,
        "coverage": coverage,
        "model-fits": fits,
        "model-terms": terms,
        "folds": folds,
        "predictions": predictions,
        "validation": validation,
        "alternate-2024-benchmarks": alternate,
    }
    people_states = defaultdict(set)
    for row in panel:
        if (
            row["eligible"]
            and row["year"] <= 2022
            and not row["person_group"].startswith("unresolved:")
        ):
            people_states[row["person_group"]].add(row["state"])
    summary = {
        "schema": "which_candidate.analysis.v1",
        "contests_retained": len(panel),
        "eligible_2016_2022": sum(r["eligible"] and r["year"] <= 2022 for r in panel),
        "eligible_locked_2024": sum(r["eligible"] and r["year"] == 2024 for r in panel),
        "feature_queries": len(features),
        "primary_focal_estimates": [r for r in terms if r["primary_focal"]],
        "cross_state_repeated_people": {
            k: sorted(v) for k, v in people_states.items() if len(v) > 1
        },
        "all_group_folds_have_zero_person_overlap": all(
            r["candidate_group_overlap"] == 0 for r in folds
        ),
        "unsupported_characteristics": [
            "race_ethnicity",
            "military",
            "occupation",
            "education",
            "issue_votes",
            "attendance",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".analysis-", dir=output.parent) as temp:
        destination = Path(temp)
        for name, rows in tables.items():
            write_rows(destination / f"{name}.jsonl.gz", rows)
            if name in (
                "candidate-features",
                "candidate-queries",
                "coverage",
                "model-terms",
                "validation",
                "alternate-2024-benchmarks",
                "district-presidential-benchmarks",
            ):
                (destination / f"{name}.csv").write_bytes(csv_bytes(rows))
        write_json(destination / "summary.json", summary)
        (destination / "report.md").write_text(
            render_report(panel, terms, validation, coverage, fits), encoding="utf-8"
        )
        render_figures(destination, terms)
        write_json(
            destination / "manifest.json",
            {
                "schema": "which_candidate.analysis.build.v1",
                "recipe": recipe,
                "sources": manifests,
                "files": {p.name: fingerprint(p) for p in sorted(destination.iterdir())},
            },
        )
        destination.rename(output)
    return {"status": "analyzed", "output": str(output), "summary": summary}


def package_analysis(project, data_dir, returns, output, archive_path):
    project, data_dir, returns, output, archive_path = (
        Path(p).resolve() for p in (project, data_dir, returns, output, archive_path)
    )
    manifest = verify_output(output)
    if manifest["recipe"] != analysis_recipe(data_dir, returns, project):
        raise ValueError("Cannot package analysis from a different recipe")
    verify_output(returns)
    if archive_path.exists():
        raise ValueError("Refusing to overwrite an existing analysis archive")
    entries = {}
    for name in ("sources.json", "research-sources.json", "supplemental-returns-sources.json"):
        path = data_dir / name
        entries[path.relative_to(project).as_posix()] = path
        for source in load_sources(path)["sources"]:
            cached = confined(data_dir, source["path"])
            entries[cached.relative_to(project).as_posix()] = cached
    for folder in (returns, output):
        for path in folder.iterdir():
            if path.is_file():
                entries[path.relative_to(project).as_posix()] = path
    for folder in ("which_candidate", "tests", "docs"):
        for path in sorted((project / folder).rglob("*")):
            if path.is_file() and path.suffix in (".py", ".md") and "__pycache__" not in path.parts:
                entries[path.relative_to(project).as_posix()] = path
    for name in ("README.md", "pyproject.toml", "requirements.lock"):
        entries[name] = project / name
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, path in sorted(entries.items()):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    return {"archive": str(archive_path), "members": len(entries), **fingerprint(archive_path)}
