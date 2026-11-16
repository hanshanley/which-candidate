"""V2 findings without substituting evidence coverage for analytical support."""

from .characteristics_publication import BLOCK_LABELS, LABELS, number
from .house_characteristics import STATUSES


def report(summary, fits, terms, coverage, sources, research):
    lines = [
        "# Evidence qualification and honest predictive validation",
        "",
        "Exploratory `house-characteristics-v2` follows the completed source-family "
        "review and a written pre-fit amendment. V1 and earlier outputs remain frozen.",
        "",
        f"Retained: **{summary['candidate_records']:,} candidate-contest records**, "
        f"**{summary['democrats']} Democrats**, **{summary['eligible_democrats']} "
        "qualified performance comparisons and all **15 testing-family blocks**. "
        "Outcome holds and unknown opponent incumbency are unchanged.",
        "",
        "## Measured evidence progress",
        "",
        f"Newly acquired observations: **{summary['newly_acquired_observations']}**; newly "
        f"covered people: **{summary['newly_covered_people']}**. This release reviews held "
        "evidence, rather than counting a repeated education/career collection as discovery. "
        f"Newly factually qualified existing fields: **{summary['newly_qualified_existing_fields']}** "
        f"(all parties); newly analytically eligible fields: **{summary['newly_analysis_eligible_fields']}**. "
        "The complete identity-level changes are in `qualification-changes.csv`.",
        "",
        "Factual qualification records what an explicit source supports, not independent "
        "verification. An education record may support attendance without identifying completed "
        "attainment. A profession need not establish paid work. Positive identities and positive "
        "service histories do not by themselves establish reference groups or estimable contrasts.",
        "",
        "## Democratic coverage: factual versus analytical",
        "",
        "| Trait | V1 qualified | V2 factual qualified | V2 analytical field | Reported | Uncertain | Unknown | Inapplicable |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    before = {r["trait"]: r for r in summary["before_coverage"] if r["cohort"] == "democrats"}
    for r in coverage:
        if r["cohort"] == "democrats":
            lines.append(
                f"| {'Education records (attainment separate)' if r['trait'] == 'education' else LABELS[r['trait']]} | {before[r['trait']]['qualified']} | "
                f"{r['factual_qualified']} | {r['analysis_eligible']} | "
                + " | ".join(str(r[s]) for s in STATUSES[1:])
                + " |"
            )
    lines += [
        "",
        "The statuses describe factual/coding review; analytical eligibility is a separate "
        "column. Exact age and bounded birth-year reports are not interchangeable. The main "
        "age model uses exact years; the separate age-band sensitivity includes a birth-year "
        "interval only when the whole interval lies within one band. No midpoint or birthday "
        "is imputed. Historical religious labels stay dated, while fifteen questionnaire "
        "refusals/nonresponses are unknown affiliation, not nonreligion.",
        "",
        "Source-family review includes held institutional biographies, prior-office pages, "
        "candidate-supplied questionnaires, ballot designations and endorsing-organization "
        "accounts, plus the eleven official candidate profiles. Each selected profile has "
        "an exact identity and hash in the review seal. Other campaign/directory profiles "
        "are not blanket-approved. Claim dates and coding, not campaign/official status alone, "
        "determine analytical eligibility. Retrospective observations remain prospectively ineligible.",
        "",
        "The existing exact FEC/person/service bridges resolve Bill Keating and Tom Suozzi "
        "as federal incumbents in a v2-only overlay. The other 37 Democratic holds remain. "
        "Keating's unknown Republican-incumbency control is not fabricated. Years of service "
        "and available pre-election voting measures follow the exact person bridge.",
        "",
        "## Every declared hypothesis and matched prediction comparison",
        "",
        "| Block | Association n / states | Holm p (15) | Restricted predictive n / full n | MAE gain [95% interval], share pp |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for fit in fits:
        prediction = fit.get("prediction")
        n = f"{prediction['population_candidates']} / {fit['n']}" if prediction else "unavailable"
        gain = (
            f"{number(prediction['MAE_gain_share_pp'])} "
            f"[{number(prediction['gain_ci_low'])}, {number(prediction['gain_ci_high'])}]"
            if prediction and prediction["complete"]
            else "diagnostic only"
            if prediction
            else "no supported contrast"
        )
        lines.append(
            f"| {BLOCK_LABELS[fit['trait']]} | {fit['n']} / {fit['state_clusters']} | "
            f"{number(fit['holm_pvalue'], 6)} | {n} | {gain} |"
        )
    significant = [BLOCK_LABELS[t] for t in summary["holm_below_005"]]
    improved = [
        BLOCK_LABELS[r["trait"]]
        for r in fits
        if r.get("prediction", {}).get("gain_ci_low") is not None
        and r["prediction"]["gain_ci_low"] > 0
    ]
    lines += [
        "",
        "Blocks clearing the declared Holm correction: "
        + (", ".join(significant) if significant else "none")
        + ". "
        "Completed predictive comparisons whose pointwise improvement interval is wholly "
        "positive: " + (", ".join(improved) if improved else "none") + ".",
        "",
        "## What changed in validation",
        "",
        "V1 age produced 147/147 predictions, but deleting Michigan then holding out Virginia "
        "(or the reverse) left no Republican-incumbent training cases. V1 gender produced "
        "132/141 predictions: holding out Texas removed its sole nonincumbent, Colin Allred. "
        "These were genuine unsupported designs, not proof of no trait effect or a reason "
        "to relax rank checks.",
        "",
        "V2 retains full-cohort diagnostics in `full-population-folds.jsonl.gz`. Its separate "
        "predictive population contains only joint D/R-incumbency strata represented in "
        "at least three states, selected without outcomes and frozen before deletion refits. "
        "Both models use exactly the same candidates and hold out states and repeated people. "
        "Exactly redundant nuisance terms are reparameterized using training data only, "
        "and the same relationship must hold in every test row. This also repairs the "
        "complementary D/R-incumbent nuisance columns exposed in education after the "
        "unsupported open-seat stratum is removed. An unseen test stratum is still "
        "rejected. Focal rank and conditioning checks remain enforced.",
        "",
        "The displayed intervals therefore validate a **narrower supported population**, not "
        "the full association cohort. Full-population intervals remain unavailable where "
        "support is inadequate. The prediction/deletion ledgers identify every excluded ID. "
        "Intervals require every supported-population fold and every full-pipeline state "
        "deletion to succeed. They are pointwise exploratory intervals, not a second "
        "multiplicity-adjusted discovery family.",
        "",
        "### Bounded-age and coding sensitivities",
        "",
        f"The separately labelled age-band sensitivity uses {summary['age_band_sensitivity']['n']} "
        f"candidates in {summary['age_band_sensitivity']['state_clusters']} states; "
        f"its exploratory omnibus p is {number(summary['age_band_sensitivity'].get('omnibus_pvalue'), 4)}. "
        "The bands are under 40, 40-59 and 60 or older. Entire intervals must fit one band. "
        "This is not the primary exact-age test and is not compared with its different "
        "sample as if the two were identical. Education/profession sensitivities exclude "
        "newly qualified analytical values while retaining the v2 service controls; "
        "competitive-lean and incumbent-only fits are also retained in `sensitivity.csv`.",
        "",
        "## Estimated terms and interpretation",
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
        "Primary age/service increments are ten years; donor ideology is +0.5 rightward, "
        "prior voting ideology +0.1 rightward, and defection +5 percentage points. "
        "The joint D/R-incumbency test is not the Democratic-incumbent coefficient alone. "
        "Donor and voting ideology are distinct constructs in different selective samples; "
        "neither is a universal moderation score or a causal nominee-replacement effect.",
        "",
        "Race, ethnicity, military, elected-office and other-government comparisons remain "
        "unavailable without complete reference classifications or explicit negative histories. "
        "They remain in the testing family with p=1. There are no newly estimable trait blocks "
        "from merely qualifying positive evidence. Unknowns are not reference categories.",
        "",
        "## Remaining limitations and research dispositions",
        "",
        "Undated or changeable employment stays descriptive. Attendance, unspecified degrees "
        "and Becky Stille's conflicting attainment accounts remain unresolved for completed "
        "attainment. Jen Mazzuckelli's subject-wording discrepancy is retained while agreeing "
        "completed degree levels can be coded. Source-reported gender preserves its definition, "
        "not inferred sex or independently verified self-identification.",
        "",
        "No reviewed held questionnaire supplied a reliable never-served reference for "
        "military/government/elected history. Ray Pooley's nonresponse is not nonservice. "
        "The Opelika Lee McInnis employee namesake and partisan Ace Parsi no-office claim "
        "are rejected; AmeriCorps is not military service. Earlier attribution/religious-parent/"
        "endorser rejections remain preserved. A bounded external discovery pass found the "
        "Mental Health Now candidate-signature index, but direct requests failed; it was "
        "not ingested or counted as acquired evidence. No universal research-completion claim.",
        "",
        "Missingness remains selective. `selection.csv`, `sensitivity.csv`, the full-cohort "
        "folds, qualification changes and remaining gaps disclose each cohort and exclusion. "
        "Models use the held provisional two-party presidential-share gap, lean and lean "
        "squared, and known D/R incumbency. One share point is two D-minus-R margin points. "
        "Do not compare different trait cohorts as though they were identical candidates.",
        "",
        "## Complete data and offline replay",
        "",
        "The v2 table uses `baseline_trait_row` as a 1-based reference into the immutable v1 "
        "JSONL for unchanged literals/receipts. Both full tables and the held normalized inputs "
        "are included in both complete downloads; the figure ZIP embeds the exact complete-query "
        "ZIP. This is lossless relational storage, not a metadata-only download. The browser "
        "resolves the full literal/source records locally.",
        "",
        "Replay with `python -m which_candidate.house_project --evidence-only`. It refreshes "
        "v2 and current evidence without rebuilding v1 or earlier analyses. "
        "`HOUSE_CHARACTERISTICS_V2_SPEC.md` is the pre-fit amendment. No website deployment.",
        "",
    ]
    return "\n".join(lines)
