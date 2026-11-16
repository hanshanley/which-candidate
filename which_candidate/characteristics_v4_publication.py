"""V4 measured acquisition and supported-population findings, local publication only."""

from .characteristics_publication import BLOCK_LABELS, LABELS, number


def block_label(trait):
    return "Historical CAWP Black/White women" if trait == "race" else BLOCK_LABELS[trait]


def report(summary, fits, terms, coverage, sources, research):
    a = summary["acquisition"]
    lines = [
        "# Candidate characteristics: V4 new-source successor",
        "",
        "**V1–V3 remain frozen. No website deployment.** V4 asks the same fifteen-block "
        "question about Democratic House performance relative to district partisanship. "
        "All 449 Democrats and 405 eligible performance comparisons remain; native returns "
        "are the provisional November 12–13 snapshot, not certified final outcomes. "
        "These observational associations are not causal nominee-replacement effects.",
        "",
        "## Actual acquisition versus qualification",
        "",
        f"**{a['new_document_hashes']} evidence-yielding new originals; "
        f"{summary['newly_acquired_observations']} source observations; "
        f"{summary['new_source_candidates']} Democratic candidates; "
        f"{summary['new_source_candidate_trait_fields']} candidate-by-trait fields.** "
        f"Only {summary['newly_informed_candidate_trait_fields']} previously unknown fields "
        f"across {summary['newly_informed_candidates']} candidates gain first observations; "
        "the rest add precision, missing coding/timing requirements or corroboration. "
        "A new observation is not automatically a newly discovered fact or an analytical value.",
        "",
        f"The separate held-FEC review newly qualifies "
        f"{summary['existing_observations_newly_qualified']} existing fields "
        f"({summary['existing_D_fields_newly_qualified']} Democratic). "
        "Those are not new-source acquisitions. Exact name/person-contest review and the "
        "official Ford/Harvie alias bridges resolve election controls without changing "
        "verified federal-service flags. Multiple IDs and unsupported aliases remain held.",
        "",
        f"Democratic analytical fields increase by "
        f"**{summary['newly_analysis_eligible_D_fields']}**; unresolved Democratic incumbency "
        f"falls from **{summary['D_unknown_incumbency_before']} to "
        f"{summary['D_unknown_incumbency_after']}**. Newly estimable primary trait blocks: "
        + (", ".join(summary["newly_estimable_contrasts"]) or "**none**")
        + ". Positive service values do not create an estimable service-versus-nonservice contrast.",
        "",
        "The eleven originals include complete Michigan manual chapters and historical "
        "legislator table, the Michigan general-election questionnaire, California's "
        "2019–2020 handbook, Iowa's 2025–2026 register, official Pennsylvania/Indiana "
        "biographies, a dated NPR interview and the complete post-election LCV guide. "
        "Large guides were retrieved once, joined to exact people and reviewed by subject "
        "section. Downloaded shells, unused guides and failed requests do not count as evidence. "
        "The full registry records those dispositions rather than hiding them.",
        "",
        "## V3 → V4: every requested trait",
        "",
        "All counts below concern the complete Democratic inventory, except fitted samples, "
        "which additionally require outcome, controls, category and geographic support. "
        "Source counts are distinct evidence-document hashes per trait, not additive across traits. "
        "Newly informed means first observation of a previously unknown cell, not merely a new source.",
        "",
        "| Trait | Sources / observations | Source-covered / first-informed candidates | Factual V3→V4 | Analytical V3→V4 | Fit n V3→V4 | Remaining limitation |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for r in summary["trait_progress"]:
        lines.append(
            f"| {LABELS[r['trait']]} | {r['new_evidence_source_hashes']} / "
            f"{r['new_observations']} | {r['source_informed_candidates']} / "
            f"{r['newly_informed_candidates']} | {r['factual_before']}→{r['factual_after']} | "
            f"{r['analytical_before']}→{r['analytical_after']} | "
            f"{r['fitted_before']}→{r['fitted_after']} | {r['remaining_limitations']} |"
        )
    lines += [
        "",
        "Exact fields and baseline incumbent/nonincumbent/unresolved breakdowns, separately "
        "for eligible and ineligible candidates, are in `acquisition-field-changes.csv` "
        "and `coverage-by-incumbency.csv`. The machine-readable complete table is "
        "`v3-v4-trait-progress.csv`. No unchanged trait is presented as newly researched.",
        "",
        "### Coverage beyond incumbents",
        "",
        "Among the 405 eligible performance comparisons, the frozen baseline strata contain "
        "166 incumbents, 229 nonincumbents and 10 unresolved cases. Groups stay fixed for "
        "this before/after comparison, even when held-FEC review resolves an unknown.",
        "",
        "| Analytical trait | Incumbents V3→V4 | Nonincumbents V3→V4 | Unresolved V3→V4 |",
        "| --- | ---: | ---: | ---: |",
    ]
    for trait in ("age", "religion", "education", "profession", "military"):
        counts = {
            r["baseline_incumbency_group"]: f"{r['before_analysis']}→{r['after_analysis']}"
            for r in summary["coverage_by_incumbency"]
            if r["trait"] == trait and r["performance_eligible"]
        }
        lines.append(
            f"| {LABELS[trait]} | {counts['incumbent']} | {counts['nonincumbent']} | "
            f"{counts['unknown_incumbency']} |"
        )
    lines += [
        "",
        "The one newly exact age belongs to an outcome-ineligible candidate: exact-age "
        "coverage does not expand among the 405 eligible comparisons. Its fitted sample "
        "grows through resolved election controls instead. Military values are supported "
        "positives, not an estimable service-versus-nonservice contrast.",
        "",
        "### What qualified, and what did not",
        "",
        "The dated directories and questionnaires explicitly identify completed credentials "
        "and historical jobs. Broad Christian remains other Christian, not inferred Protestant. "
        "Clergy descriptions support religious affiliation but not an education occupation. "
        "Lindsay James's separate explicit adjunct-faculty history supports educational work. "
        "Mixed legal/teaching careers remain ambiguous; nonprofit executives, engineers, "
        "organizers and clergy are not forced into the four occupation families.",
        "",
        "Birth years and month/year claims retain defensible age intervals; no invented day "
        "or midpoint is used. Michigan's historical gender field is excluded because its "
        "methods allow inference from names/photos/pronouns. Its default January 1 birthdays "
        "are not used. Subject-scoped extraction prevents a neighboring biography's degree "
        "or military service from qualifying another candidate.",
        "",
        "The CAWP codebook confirms explicit source identity labels, not non-Hispanic "
        "complements. The held historical Asian American/Pacific Islander group has six "
        "Democrats across four states; MENA has two and Native American/Native Alaskan one. "
        "These fail the unchanged ten-candidate category gate. Race therefore retains "
        "**historical CAWP Black-versus-White women**, not all Democratic racial groups. "
        "All five rejected V3 cross-contest transfers remain protected.",
        "",
        "New office histories explicitly mean **before November 3, 2026**, not before "
        "first House entry. Positive office/government/service histories are retained "
        "without inferring never-served references from silence. Advisory councils, relatives "
        "and veterans' advocacy are not paid government employment or military service. "
        "The post-election LCV population is selected; its long prior service and explicitly "
        "earlier credentials support retrospective facts, not prospective availability. "
        "Original branch wording remains source-reported, not independently verified.",
        "",
        "The alternative positive-office question was also checked, not assumed unavailable "
        "merely because nonservice references are missing. Among the 17 consistently timed "
        "new histories, 11 record state office, nine local office and two federal office; "
        "five state/local histories overlap. The single-recorded-category groups are only "
        "six state, four local and two federal, below the ten-candidate gate. A missing "
        "second category is not proof of exclusive lifetime service. "
        "`positive-office-category-support.json` preserves the literal histories and "
        "observation IDs. This bounded support assessment is not an all-candidate office test.",
        "",
        "## Associations and identical-sample predictive comparisons",
        "",
        "| Block | Association n / states | Holm p (15) | Restricted predictive n | MAE gain [95% interval], share pp |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for fit in fits:
        p = fit.get("prediction")
        gain = (
            f"{number(p['MAE_gain_share_pp'])} [{number(p['gain_ci_low'])}, {number(p['gain_ci_high'])}]"
            if p and p["complete"]
            else "diagnostic only"
            if p
            else "unavailable"
        )
        lines.append(
            f"| {block_label(fit['trait'])} | {fit['n']} / {fit['state_clusters']} | "
            f"{number(fit['holm_pvalue'], 6)} | {p['paired_candidates'] if p else '—'} | {gain} |"
        )
    lines += [
        "",
        "Blocks clearing the fixed fifteen-block Holm correction: "
        + (", ".join(BLOCK_LABELS[t] for t in summary["holm_below_005"]) or "none")
        + ".",
        "",
        "Joint D/R incumbency is distinct from the Democratic incumbent coefficient. "
        "The donor association applies to a selective donor-linked cohort, not universal "
        "moderation. Share percentage points are half D-minus-R margin points. "
        "No observational coefficient identifies the effect of replacing a nominee.",
        "",
        "### Focal terms",
        "",
        "Age and House service are per ten years; donor ideology per 0.5 units; prior "
        "voting ideology per 0.1 units; party defection per five percentage points. "
        "Categorical reference groups appear in the term labels. These are pointwise "
        "coefficient intervals, not a second multiplicity-adjusted findings family.",
        "",
        "| Block / term | Share pp [pointwise 95% CI] |",
        "| --- | ---: |",
    ]
    for term in terms:
        if term["focal"]:
            lines.append(
                f"| {block_label(term['trait'])} / `{term['term']}` | "
                f"{number(term['estimate_share_pp'])} [{number(term['ci_low'])}, "
                f"{number(term['ci_high'])}] |"
            )
    lines += [
        "",
        "## Validation, reuse and limits",
        "",
        "Recomputed blocks: " + ", ".join(summary["recomputed_blocks"]) + ". "
        "Input-identical V3 blocks reused: " + ", ".join(summary["reused_blocks"]) + ". "
        "`numerical-input-reuse.json` records both numerical-input hashes. Selection "
        "decisions and the full-family correction are refreshed even for reused blocks. "
        "The numerical contract and support gates are unchanged.",
        "",
        "State-held-out/person-purged folds retain training-only preprocessing and identical "
        "baseline/augmented samples. Restricted prediction requires joint D/R-incumbency "
        "strata in at least three states. Full-population failures are exported separately "
        "and are not validated by a restricted interval. Complete outer-state-deletion "
        "pipelines are required for prediction-gain intervals; unsupported intervals remain absent.",
        "",
        f"The separate whole-interval age-band sensitivity uses "
        f"{summary['age_band_sensitivity']['n']} candidates. Exact age and affiliation "
        "remain overwhelmingly incumbent documented despite the new challenger evidence. "
        "This bounded batch does not complete universal trait research.",
        "",
        "## Complete local deliverables",
        "",
        "Both complete downloads contain every frozen release, normalized evidence, "
        "supporting fragments, source receipts, all candidate/trait/selection/fold/deletion "
        "tables, code, tests and replay inputs. Raw large/restricted originals are not "
        "silently represented as redistributed; preserved normalized claims support offline "
        "replay without requiring absent historical raw caches. The figure bundle embeds "
        "the exact complete-query ZIP. No metadata-only replacement.",
        "",
        "Replay: `python -m which_candidate.house_project --evidence-only`. "
        "Local report and browser only; **no website deployment**.",
        "",
    ]
    return "\n".join(lines)
