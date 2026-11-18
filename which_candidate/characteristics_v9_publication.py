"""V9 findings with acquisition, qualification and prediction kept separate."""

from .characteristics_publication import LABELS


def report(summary, fits, terms, coverage, sources, research):
    lines = [
        "# Candidate characteristics: recovered evidence, explicit limits",
        "",
        "## Scope and substantive progress",
        "",
        "This local successor preserves V1-V8 and all 1,284 native candidate-contest records. "
        "The Democratic denominator remains 449, with 405 performance-eligible comparisons. "
        "No website is deployed. The fifteen traits are retained whether estimable or not.",
        "",
        f"V8-to-V9 first evidence fills **{summary['newly_informed_candidate_trait_fields']} fields "
        f"across {summary['newly_informed_candidates']} candidates**, all parties combined. "
        f"Of these, {summary['first_evidence_retained_original_fields']} fields come from "
        "newly reviewed extraction of already acquired originals, not new downloads. "
        "Previously reported but unqualified fields, supplementary citations and identity-only "
        "filings are not counted as first evidence.",
        "",
        f"Two signed-filing reviews and one dated questionnaire resolve "
        f"{summary['resolved_incumbency_controls']} Democratic incumbency controls; "
        f"{summary['D_unknown_incumbency_after']} remain held. "
        f"{len(summary['control_unlocked_contests'])} performance-eligible contests gain "
        "complete controls. These changes are separate from newly measured background traits.",
        "",
        "## Every trait: V8 to V9",
        "",
        "All coverage counts below use 449 Democrats, not only fitted candidates. "
        "'No factual value' includes unknown, held and structurally inapplicable cases; it is "
        "not a negative category. Explicit structural inapplicability is separately counted. "
        "Factual descriptions need not meet timing, coding or comparison-support rules.",
        "",
        "| Trait | Factual V8→V9 | Analytical V8→V9 | Fit V8→V9 | Full-fit predictions | No factual value | Unknown status | Structural | First facts |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in summary["trait_progress"]:
        lines.append(
            f"| {LABELS[r['trait']]} | {r['factual_before']}→{r['factual_after']} | "
            f"{r['analytical_before']}→{r['analytical_after']} | "
            f"{r['fitted_before']}→{r['fitted_after']} | "
            f"{r['prediction_supported']}/{r['prediction_target']} | "
            f"{r['no_qualified_factual_value']} | {r['unknown_after']} | "
            f"{r['structurally_inapplicable']} | {r['newly_informed_candidates']} |"
        )
    lines += [
        "",
        "A 0/0 prediction count means an unavailable contrast, not successful prediction. "
        "The complete progress CSV separately reports new factual qualifications, retained "
        "reported-field qualifications, timing/coding holds and identity/conflict holds.",
        "",
        "| First-evidence population | Fixed V8 incumbency | Candidates | Fields |",
        "| --- | --- | ---: | ---: |",
    ]
    for r in summary["first_evidence_groups"]:
        lines.append(
            f"| {r['party']} | {r['baseline_incumbency_group']} | "
            f"{r['candidates']} | {r['fields']} |"
        )
    lines += [
        "",
        "## Evidence acquisition versus qualification",
        "",
        "The exact retained Louisiana product was the November 3, 2026 Candidate Inquiry "
        "House export, election 344, offices 70195-70200: 39 filing rows with Race and Gender "
        "columns. Its 41 V8 first fields are not new V9 gains. Source-defined filing labels "
        "are not silently pooled with historical race/ethnicity classifications.",
        "",
        "California's August 27 certified list supplies 104 congressional candidates across "
        "52 districts and candidate-submitted ballot designations. The reusable parser preserves "
        "page, district, party, exact wording and office designations. A designation is not "
        "a complete verified career. Unresolved printed/native name variants remain held.",
        "",
        "Retained national campaign originals were revisited for concrete missed education, "
        "dated age, public self-description and career passages, rather than redownloaded en masse. "
        "A resolved HTTP redirect plus the named homepage's direct same-host biography link "
        "repairs Kelly Esti's previously rejected biography. Dated credentials, a documented "
        "Navy role and an explicit own description are distinct claims. A role interval is "
        "not represented as the person's complete military career.",
        "",
        "Three additional Alaska statements were recovered from URL stems embedded as table "
        "text rather than HTML links: Begich, Hill and McDermott. Hafner's retained statement "
        "was not reacquired. Ages without a specified reference day are conservative intervals "
        "for November 3, not invented birthdays or exact election ages. Completed but undated "
        "credentials remain distinct from analytical attainment. Candidate-paid statements "
        "carry the publisher's express nonverification disclaimer.",
        "",
        "Kaylee Peterson's undated reported age is retained without assigning a birth interval: "
        "a retrieval date does not establish when a biography's age was written.",
        "",
        "Oklahoma's candidate book and federal filing packet, North Carolina's candidate-list "
        "definitions, West Virginia's blank announcement form, South Carolina's filing portal "
        "and Alaska's publication index were acquired as distinct products. Blank forms and "
        "indexes establish schemas or discovery paths, not candidate answers or complete "
        "national demographic coverage.",
        "",
        "South Carolina's ordinary General 2026 selector was followed through its declared "
        "House query, public candidate-detail link and signed filing. The inspected SICPP "
        "form supplies identity, office and party, not background/demographic questions. "
        "The 2021 Phone2Action/KnowWho freshman directory and publisher's field manual were "
        "also acquired. Printed military 'None' has unresolved missing-value semantics and "
        "does not establish nonservice through 2026. A conflicting Mrvan birth date is "
        "retained as a conflict, not converted to age. The complete source-review export "
        "records literal historical fields, verified 2021-term overlap and these holds.",
        "",
        "The 278 previously unused originals have a by-source disposition export. It "
        "distinguishes accepted extraction corrections, identity holds, bounded excerpt "
        "reviews and documents without the original markers; it does not claim exhaustive "
        "full-body semantic review or prove that further public evidence is unavailable.",
        "",
        "| Source family | Requests | Acquired | Failed | Evidence hashes | Claims | First fields |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in summary["source_family_outcomes"]:
        lines.append(
            f"| {r['family']} | {r['requests']} | {r['acquired_requests']} | "
            f"{r['failed_requests']} | {r['evidence_hashes']} | {r['observations']} | "
            f"{r['first_evidence_fields']} |"
        )
    lines += [
        "",
        "Family first-field counts can overlap; only the distinct total above is additive. "
        "Source hashes are not independent observations. A successful download without "
        "qualified claims adds no coverage.",
        "",
        "## Challengers and other nonincumbents",
        "",
        "Groups are fixed at V8 so identity resolutions do not move the goalposts. "
        "The following table covers performance-eligible Democrats. The complete all-party "
        "download includes outcome-ineligible candidates and unresolved incumbency groups.",
        "",
        "| Trait | Fixed group | Candidates | Factual V8→V9 | Analytical V8→V9 | First fields | Fit | Predictions |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in summary["party_and_incumbency_coverage"]:
        if r["party"] == "Democratic" and r["performance_eligible"]:
            lines.append(
                f"| {LABELS[r['trait']]} | {r['baseline_incumbency_group']} | {r['candidates']} | "
                f"{r['factual_before']}→{r['factual_after']} | "
                f"{r['analysis_before']}→{r['analysis_after']} | {r['first_evidence_fields']} | "
                f"{r['fitted_after']} | {r['full_fit_prediction_supported']} |"
            )
    lines += [
        "",
        "## What the analyses support",
        "",
        "The outcome is Democratic two-party House share minus the map-qualified presidential "
        "Democratic share, in share percentage points, not margin points. Models retain lean, "
        "lean squared and the specified D/R incumbency controls. The fifteen-test Holm family "
        "includes unavailable blocks at p=1. Categories need ten candidates in three states; "
        "fits need thirty candidates in ten states. No coefficient-driven acquisition or "
        "significance-seeking model search was introduced.",
        "",
        "Association estimates are observational and source-selected, not the effect of replacing "
        "a nominee. New descriptive identity facts do not extend the restricted historical "
        "author-coded contrasts. Unchanged numerical signatures are reused; changed populations "
        "are recomputed under the same specifications.",
        "",
        "| Trait | Fit n | States | Holm p | Matched prediction n | MAE gain, share pp | Gain interval |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for fit in fits:
        if fit["status"] != "estimated":
            continue
        prediction = fit["prediction"]
        gain = prediction.get("MAE_gain_share_pp")
        low, high = prediction.get("gain_ci_low"), prediction.get("gain_ci_high")
        interval = (
            f"[{low:.3f}, {high:.3f}]" if low is not None and high is not None else "unsupported"
        )
        lines.append(
            f"| {LABELS[fit['trait']]} | {fit['n']} | {fit['state_clusters']} | "
            f"{fit['holm_pvalue']:.6g} | {prediction.get('paired_candidates', 0)} | "
            f"{gain:.3f} | {interval} |"
            if gain is not None
            else f"| {LABELS[fit['trait']]} | {fit['n']} | {fit['state_clusters']} | "
            f"{fit['holm_pvalue']:.6g} | 0 | unavailable | unsupported |"
        )
    lines += [
        "",
        "Positive MAE gain means lower held-out error. Matched prediction populations may be "
        "smaller than association or full-fit prediction populations. Only complete outer "
        "state-deletion pipelines support the displayed uncertainty; association significance "
        "does not establish predictive improvement.",
        "",
        "| Focal association | Estimate, share pp | Pointwise 95% interval | n |",
        "| --- | ---: | --- | ---: |",
    ]
    for term in terms:
        if term["focal"]:
            lines.append(
                f"| {LABELS[term['trait']]}: {term['term']} | {term['estimate_share_pp']:.3f} | "
                f"[{term['ci_low']:.3f}, {term['ci_high']:.3f}] | {term['n']} |"
            )
    lines += [
        "",
        "## Restricted historical Latino result",
        "",
        "The frozen source-defined association concerns 89 linked historical officeholders "
        "in 27 states: 83 incumbents and six nonincumbents, not all 449 Democratic candidates. "
        "The author-coded Latino indicator is distinct from newly acquired candidate "
        "self-descriptions. Its comparison support, state counts, overlaps with other measured "
        "fields, exact included candidates and exclusions are downloadable in "
        "`historical-latino-population.json`. Existing competitive, source and state-deletion "
        "checks remain in the complete sensitivity/deletion files, including unsuccessful checks. "
        "The 89-person association and 87-person restricted prediction uncertainty population "
        "must not be conflated. Selection and missingness limit transport; the association "
        "is neither causal nor a demonstrated predictive gain.",
        "",
        "## Controls, structural eligibility and prediction failures",
        "",
        "For Antonio Wilson/LA05 and Zyon Khalifa/SC02, both signed FEC statements share the "
        "filed legal name, principal campaign committee, filing address and signing date. "
        "Both IDs remain in the review. Their retained explicit election classifications agree. "
        "This is not a classification based merely on matching names or agreeing flags, and "
        "does not independently verify lifetime nonservice. Only Khalifa was performance-eligible. "
        "Caleb Walker/LA03's dated personal answer denies previous elected office, while "
        "the report and retained service crosswalk positively identify Higgins as incumbent. "
        "This resolves Walker's election nonincumbency without creating an FEC match. "
        "The exact ballot nickname also bridges his retained Louisiana filing. Walker and "
        "Wilson are performance-ineligible; only Khalifa adds a complete-control contest.",
        "",
        "The lagged voting measure is 118th-Congress Nokken-Poole ideology, not current campaign "
        "ideology. A unique verified crosswalk plus the Clerk's explicit zero-prior-Congresses "
        "and 119th-Congress swearing-in establishes structural inapplicability for qualifying "
        "first entrants. Missing rows alone do not. Other unknown or unresolved service "
        "populations stay explicit; neither ideology nor party unity is filled with zero.",
        "",
        "Religion retains the V8 row-specific training-estimability rule. IA03 is the only "
        "Republican-incumbent-opponent configuration in the fitted religion population; "
        "holding out Iowa leaves that nuisance coefficient unsupported. IA02 is supported. "
        "IA03 is not silently dropped or assigned an extrapolated coefficient, and complete "
        "full-population uncertainty is not claimed.",
        "",
        "## Unsupported comparisons and remaining prerequisites",
        "",
        "Office, paid-government-employment and military contrasts still require comparable "
        "explicit evidence on both sides under the existing definitions and support thresholds. "
        "The single retained military negative is not a veteran and is insufficient. "
        "No prior elected office, no government employment and no military service are "
        "different claims. Blanks, N/A, omitted service, private corporate boards, relatives' "
        "careers and absence from databases supply no negative category.",
        "",
        "Remaining factual gaps need named, explicit original evidence; analytical gaps may "
        "instead need credential completion, career meaning, pre-election timing or source-compatible "
        "comparison support. Future Caucus's aggregate methods mix concrete dates with graduation-based "
        "age estimates; no compatible candidate-level microdata was acquired or inferred. "
        "Unresolved aliases require stronger native-person bridges, not relaxed name matching. "
        "The complete per-candidate queues identify present statuses, not proof that no "
        "additional public evidence exists.",
        "",
        "## Complete research files",
        "",
        "The browser below retains every candidate and links claim provenance. Figures have "
        "complete plotted CSVs; fitted samples, folds, unsupported predictions, exclusions, "
        "source receipts and all-party fixed-V8 breakdowns accompany them. "
        "The complete query bundle must include permitted originals and extraction/analysis code, "
        "not metadata alone. Research reproduction and acquisition are separate: offline "
        "reconstruction must use the pinned originals, never refreshed web content.",
        "",
        "```bash",
        ".venv/bin/python -m which_candidate.characteristics_v9_acquisition --acquire --audit-cached",
        ".venv/bin/python -m which_candidate.characteristics_v9_extract",
        ".venv/bin/python -m which_candidate.characteristics_v9_review",
        ".venv/bin/python -m which_candidate.characteristics_research --offline",
        ".venv/bin/python -m which_candidate.characteristics_v9",
        "```",
    ]
    return "\n".join(lines) + "\n"
