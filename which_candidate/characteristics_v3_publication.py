"""Measured new-source progress and the full V3 research result."""

from .characteristics_publication import BLOCK_LABELS, LABELS, number
from .house_characteristics import STATUSES


def report(summary, fits, terms, coverage, sources, research):
    a = summary["acquisition"]
    lines = [
        "# New evidence for the full candidate-characteristics question",
        "",
        "Exploratory **house-characteristics-v3** adds a bounded new-source acquisition "
        "batch to frozen V2. V1, V2 and earlier findings remain unchanged. The question "
        "is which Democratic House candidates outperform district partisanship, and how "
        "that performance relates to background, ideology, legislative behavior and incumbency.",
        "",
        f"All **{summary['candidate_records']:,} candidate-contest records**, "
        f"**{summary['democrats']} Democrats**, **{summary['eligible_democrats']} qualified "
        "performance comparisons** and all **fifteen primary testing-family blocks** remain. "
        "The counts are provisional November 12-13 returns, not certified final outcomes. "
        "No causal nominee-replacement effect is identified.",
        "",
        "## Acquisition, qualification and analytical progress are different",
        "",
        f"- **{a['new_document_hashes']} new original document hashes**, including the "
        "CAWP methods codebook; "
        f"**{summary['newly_acquired_observations']} acquired factual observations**, "
        f"of which **{summary['newly_acquired_D_observations']}** concern Democrats.",
        f"- New-source observations cover **{summary['new_source_candidates']} candidates** "
        f"and **{summary['new_source_candidate_trait_fields']} candidate-by-trait fields**. "
        f"Of these, **{summary['newly_informed_candidate_trait_fields']} previously unknown "
        f"fields** inform **{summary['newly_informed_candidates']} candidates**; other "
        "observations add precision, coding support or corroboration rather than first coverage.",
        f"- The byte-identical held CAWP 2026 list is **not new acquisition**. "
        f"It contributes {a['existing_evidence_claims_newly_coded']} newly coded claims. "
        f"**{summary['existing_observations_newly_qualified']} existing-only fields** newly "
        "qualify factually; this excludes cells also receiving new-source evidence.",
        f"- **{summary['newly_analysis_eligible_fields']} additional analytical fields** "
        f"(all parties), **{summary['newly_analysis_eligible_D_fields']} Democratic fields**. "
        f"Unresolved Democratic federal incumbency changes from "
        f"**{summary['D_unknown_incumbency_before']} to {summary['D_unknown_incumbency_after']}**. "
        "These control resolutions come from newly coded held evidence, not new service histories.",
        "",
        "The exact changes, including incumbent/challenger composition, are in "
        "`acquisition-field-changes.csv` and `coverage-by-incumbency.csv`. Both existing "
        "and newly acquired observations retain literal claims, historical dates, retrieval "
        "clocks, hashes and exact candidate/contest identities. "
        f"**{summary['newly_covered_people']} candidates** gain their first factually "
        "qualified trait; this is not the same as first-ever biography acquisition or "
        "candidates newly informed on a specific trait.",
        "",
        "### Sources and factual limits",
        "",
        a["attribution"],
        "",
        "New CAWP historical matches require exact 2024 full name, state, party, House "
        "office and district. Name-only matches across changed districts are held rather "
        "than transferred automatically. Explicit W and B are positive source classifications, "
        "not reference groups manufactured from missing minority fields. H is Hispanic/Latina, "
        "not a racial category or a non-Hispanic complement. Multi-codes and unknowns remain.",
        "",
        "With Honor supplies explicit named branch/veteran labels, not inferred service "
        "from endorsement. CFE supplies actual candidate biographies and literal religious "
        "descriptions. Its religious allies are not coded nonreligious; scientist is not a "
        "religious affiliation. Current pages contain post-election updates, so these new "
        "religious/service reports do not silently become pre-election model inputs. "
        "Fred Wellman's Catholic upbringing and reported current nonreligion remain distinct.",
        "",
        "The Minnesota legislative-library biography supplies Matt Little's explicit "
        "birthday, source-recorded Male field, completed 2014 JD, historical attorney "
        "occupation, elected mayoral history and state advisory membership. Advisory work "
        "is not presumed paid government employment. Blank religion and None Reported "
        "minority classifications remain unknown. Durational career evidence is qualified "
        "for historical profession only when it necessarily precedes Election Day; no exact "
        "job-start date is invented.",
        "",
        "## Coverage across the complete Democratic inventory",
        "",
        "| Trait | V2 analytical | V3 factual qualified | V3 analytical | Reported | Uncertain | Unknown | Inapplicable |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    before = {r["trait"]: r for r in summary["before_coverage"] if r["cohort"] == "democrats"}
    for r in coverage:
        if r["cohort"] == "democrats":
            lines.append(
                f"| {LABELS[r['trait']]} | {before[r['trait']]['analysis_eligible']} | "
                f"{r['factual_qualified']} | {r['analysis_eligible']} | "
                + " | ".join(str(r[s]) for s in STATUSES[1:])
                + " |"
            )
    lines += [
        "",
        "Factual qualification and analytical eligibility are separate. A completed "
        "attainment category, dated occupation or explicit identity may qualify without "
        "supporting a statistical contrast. All-cohort and eligible-405 coverage, group "
        "composition, selection and unresolved fields are available in complete tables.",
        "",
        "## All fifteen associations and matched-sample predictions",
        "",
        "| Block | Association n / states | Holm p (15) | Restricted predictive n / full n | MAE gain [95% interval], share pp |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for f in fits:
        p = f.get("prediction")
        n = f"{p['population_candidates']} / {f['n']}" if p else "unavailable"
        gain = (
            f"{number(p['MAE_gain_share_pp'])} [{number(p['gain_ci_low'])}, {number(p['gain_ci_high'])}]"
            if p and p["complete"]
            else "diagnostic only"
            if p
            else "no supported contrast"
        )
        lines.append(
            f"| {BLOCK_LABELS[f['trait']]} | {f['n']} / {f['state_clusters']} | "
            f"{number(f['holm_pvalue'], 6)} | {n} | {gain} |"
        )
    lines += [
        "",
        "Blocks clearing the fixed fifteen-block Holm correction: "
        + (", ".join(BLOCK_LABELS[t] for t in summary["holm_below_005"]) or "none")
        + ".",
        "",
        "The newly evaluated race question compares explicitly Black versus White "
        "**historical CAWP women candidates**, not all Democratic racial groups and not "
        "a biological or causal race effect. Black/White overlap is not forced into one "
        "group; other identities remain factual observations. This source-selected, "
        "predominantly repeated-candidate sample has strong selection limitations. "
        "Ethnicity still lacks a defensible negative/reference classification. Office, "
        "government and military histories still lack a supported service-versus-nonservice "
        "contrast. Any unavailable comparison remains in the testing family with p=1.",
        "",
        "### Estimated focal terms",
        "",
        "| Block / term | Association, share pp [pointwise 95% CI] |",
        "| --- | ---: |",
    ]
    for term in terms:
        if term["focal"]:
            lines.append(
                f"| {BLOCK_LABELS[term['trait']]} / `{term['term']}` | "
                f"{number(term['estimate_share_pp'])} [{number(term['ci_low'])}, "
                f"{number(term['ci_high'])}] |"
            )
    lines += [
        "",
        "One share point equals two D-minus-R margin points. Age and service increments "
        "are ten years; donor ideology is +0.5 rightward, voting ideology +0.1 rightward, "
        "and defection +5 points. The joint D/R-incumbency block is not the Democratic "
        "incumbent coefficient alone. Donation ideology, congressional voting ideology "
        "and campaign positions remain distinct. A selective donor association is not a "
        "universal moderation advantage.",
        "",
        "## Validation, selection and remaining gaps",
        "",
        "V3 reuses V2's state-held-out/person-purged validation, training-only nuisance "
        "reparameterization, rank/conditioning gates and full-pipeline state-deletion "
        "uncertainty. Baseline and augmented predictions always use identical candidates. "
        "Restricted validation retains only joint D/R-incumbency strata represented in "
        "at least three states; it never validates the full association population by "
        "implication. Full-population fold failures remain exported. No unsupported "
        "interval or unseen test stratum is waived.",
        "",
        "The separate whole-interval age-band sensitivity uses "
        f"{summary['age_band_sensitivity']['n']} candidates in "
        f"{summary['age_band_sensitivity']['state_clusters']} states. Birth-year intervals "
        "must fit wholly within a band; there is no imputed exact birthday or midpoint. "
        "Competitive, incumbent-only, coding and state-deletion sensitivities remain. "
        "Do not compare different complete-case cohorts as if they were identical candidates.",
        "",
        f"Source classification conflicts retained: **{len(summary['source_conflicts'])}**. "
        f"Rejected cross-contest historical name matches: **{len(a['rejected_matches'])}**. "
        "These are context holds, not claims that the names necessarily identify different "
        "people. Prior rejected namesakes and conflicting credentials remain preserved. "
        "CandiData added no unknown Democratic gender among exact FEC matches; uncertain "
        "demographic coding was not promoted. Future Caucus aggregate results were not "
        "counted as candidate microdata or purchased access.",
        "",
        "This bounded batch does not finish universal trait research. Challenger evidence "
        "remains selectively missing; most age/religion/career fields still need qualified "
        "source evidence or timing, and remaining incumbent holds require official person/"
        "service bridges. Explicit positive military or office history is not confirmed "
        "nonservice for anyone else. Retrospectively retrieved evidence is never marked "
        "prospectively model-ready.",
        "",
        "## Complete data and local replay",
        "",
        "The V3 table retains lossless 1-based `baseline_trait_row` references into frozen "
        "V1 evidence, plus all V2 review and new V3 source facts. Both complete downloads "
        "contain the full normalized inputs, original receipt metadata, all fifteen-trait "
        "tables, selection/fold/deletion ledgers, code and historical outputs. The figure "
        "bundle embeds the exact complete-query ZIP. No metadata-only replacement.",
        "",
        "Replay with `python -m which_candidate.house_project --evidence-only`. The "
        "V3 specification and acquisition journal document eligibility decisions. V1/V2 "
        "outputs remain byte-protected. Local report/browser only: **no website deployment**.",
        "",
    ]
    return "\n".join(lines)
