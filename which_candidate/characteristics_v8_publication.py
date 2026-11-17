"""Self-contained V8 acquisition, selection and analytical findings."""

from .characteristics_publication import LABELS


def report(summary, fits, terms, coverage, sources, research):
    lines = [
        "# Candidate backgrounds: national evidence, selective inference",
        "",
        "## What this release establishes",
        "",
        "All 1,284 native candidate-contest records and all fifteen traits remain visible, "
        "including 449 Democrats and 405 eligible Democratic performance comparisons. "
        "V1–V7 remain frozen. This is a local research product; no website was deployed.",
        "",
        f"New qualified first evidence fills **{summary['newly_informed_candidate_trait_fields']} "
        f"candidate–trait fields for {summary['newly_informed_candidates']} candidates** across parties. "
        "A first-evidence field must previously have been unknown and now have qualified factual "
        "evidence. Downloaded pages, rejected proxies, supplements and identity-only observations "
        "are not interchangeable with those gains.",
        "",
        f"Retained FEC evidence qualifies {summary['existing_D_fields_newly_qualified']} Democratic "
        f"incumbency controls; {summary['D_unknown_incumbency_after']} remain held. "
        f"{len(summary['control_unlocked_contests'])} eligible contests gain both controls. "
        "Control unlocks are not new background facts.",
        "",
        "## V7 → V8: every trait",
        "",
        "Factual coverage includes supported descriptive histories even when their timing, "
        "credential level or occupational meaning cannot supply an analytical value. "
        "Unknown means no qualified factual value, not a negative classification. "
        "All factual and analytical counts below use the full 449-Democrat denominator.",
        "",
        "| Trait | New source hashes | Claims | First facts | Factual V7→V8 | Analytical V7→V8 | Fit V7→V8 | Full-fit predictions | Unknown |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in summary["trait_progress"]:
        lines.append(
            f"| {LABELS[r['trait']]} | {r['new_evidence_source_hashes']} | {r['new_observations']} | "
            f"{r['newly_informed_candidates']} | {r['factual_before']}→{r['factual_after']} | "
            f"{r['analytical_before']}→{r['analytical_after']} | "
            f"{r['fitted_before']}→{r['fitted_after']} | "
            f"{r['prediction_supported']}/{r['prediction_target']} | {r['unknown_after']} |"
        )
    lines += [
        "",
        "Source hashes are unique within each trait and can recur across traits. They are "
        "not independent documents to sum. Identity-only claims are included in claim totals "
        "but excluded from first facts. The complete progression CSV separates retained-evidence "
        "qualification and newly qualified factual fields.",
        "",
        "| First-evidence population | Fixed V7 group | Candidates | Fields |",
        "| --- | --- | ---: | ---: |",
    ]
    for r in summary["first_evidence_groups"]:
        lines.append(
            f"| {r['party']} | {r['baseline_incumbency_group']} | "
            f"{r['candidates']} | {r['fields']} |"
        )
    lines += [
        "",
        "## Coverage beyond incumbents",
        "",
        "Fixed V7 groups prevent resolutions from moving candidates between comparison populations. "
        "The table reports eligible Democrats only. The downloadable all-party table also retains "
        "every outcome-ineligible record and its factual and analytical counts.",
        "",
        "| Trait | Group | Candidates | Factual V7→V8 | Analytical V7→V8 | First evidence | Fit | Predictions |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in summary["party_and_incumbency_coverage"]:
        if r["party"] == "Democratic" and r["performance_eligible"]:
            lines.append(
                f"| {LABELS[r['trait']]} | {r['baseline_incumbency_group']} | {r['candidates']} | "
                f"{r['factual_before']}→{r['factual_after']} | {r['analysis_before']}→"
                f"{r['analysis_after']} | {r['first_evidence_fields']} | "
                f"{r['fitted_after']} | {r['full_fit_prediction_supported']} |"
            )
    lines += [
        "",
        "## What was actually acquired and how it qualifies",
        "",
        "Successive batches acquired Oregon and Washington official candidate pamphlets, "
        "national roster-linked campaign originals, Alaska's candidate statement, Louisiana's "
        "complete 39-row statewide House filing export, FEC candidate/committee filings and "
        "a dated WESA candidate guide. Subsequent batches added the complete official 2025 "
        "Maryland legislative roster, an archived 2024 state biography, a dated candidate "
        "interview, a complete public nonreligious-candidate table and Tennessee/Colorado "
        "candidate-authored guide responses. The Colorado statewide edition covers statewide "
        "offices; its El Paso edition supplies House responses. Chattanooga's November "
        "general guide covers state offices, not this House cohort. These inspected "
        "nonoverlaps add no candidate facts. "
        "Repeated county statements and duplicate claims are "
        "deduplicated. Existing V7 Lublin archives are retained, not new acquisition.",
        "",
        "| Source family | Requests | Acquired | Unique hashes | Failed | Retained | Claims | First fields |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in summary["source_family_outcomes"]:
        lines.append(
            f"| {r['family']} | {r['requests']} | {r['acquired_requests']} | "
            f"{r['unique_acquired_hashes']} | {r['failed_requests']} | "
            f"{r['retained_existing_requests']} | {r['observations']} | "
            f"{r['first_evidence_fields']} |"
        )
    lines += [
        "",
        "Requests, hashes and qualified fields measure different things. Family first-field "
        "counts can overlap; the distinct total and candidate populations appear above. "
        "A downloaded index, blocked response or unchanged retained original adds no trait value.",
        "",
        "The national affiliation table explicitly reports a November 16, 2026 update. Its "
        "new named reports are factual post-election observations, not pre-election model "
        "values. Most listed House candidates already had retained V3 evidence; Scientist, "
        "endorsement and caucus membership are not affiliation codes. Navy biographies and "
        "the targeted VOTE411 page could not be acquired; snippets supplied no registered claims.",
        "",
        "Candidate-submitted pamphlets preserve exact question labels and wording; they are "
        "not independently verified biographies. National campaign pages without a factual "
        "date establish reported history, not automatic pre-election analytical qualification. "
        "Completed dated credentials are distinct from attendance, in-progress degrees and "
        "unlevelled 'law degree' or 'graduate' wording. Mixed professions remain held.",
        "",
        "Louisiana's explicit Race/Gender filing labels remain source classifications. "
        "'Hispanic' in its Race field is not reinterpreted as a general ethnicity measure. "
        "They are not pooled into the frozen historical author-classified race estimand. "
        "Only selected filing columns are used; addresses and contact details are unnecessary.",
        "",
        "The filed Bradstock committee statement explicitly connects the legal candidate to "
        "the native candidate's campaign website. Other reviewed FEC bridges use named "
        "authorized committees, full legal names, native quoted nicknames and the same contest. "
        "Multiple FEC IDs for Wilson/Khalifa are not selected merely because statuses agree.",
        "",
        "Four explicit Washington Elected Experience negatives are scoped no-prior-elected-office "
        "claims. They do not mean no government employment or no military service and do not "
        "meet the unchanged ten-candidate/three-state category gate. Before-election histories "
        "are not before-first-House-entry histories. Blank, N/A, party/student positions, "
        "military-school attendance, spouses' service and church volunteering supply no invented "
        "negative, employment, veteran or affiliation values. A later Tennessee questionnaire "
        "does supply one explicit no-military-background response; this is not enough for "
        "the unchanged ten-candidate/three-state category gate. Office/government/military "
        "contrasts remain unavailable; one blocked trait did not halt other acquisition.",
        "",
        "## Associations are not candidate effects",
        "",
        "Outcome: Democratic two-party House share minus the map-qualified presidential "
        "Democratic share, in share percentage points, not margin points. Existing models adjust "
        "for constituency lean, lean squared and the specified incumbency controls. "
        "The fifteen-test Holm family retains unavailable blocks at p=1. Categories require "
        "ten candidates in three states; fits require thirty candidates in ten states. "
        "No new model family or significance-seeking contrast was introduced.",
        "",
        "Three blocks clear Holm correction: joint D/R incumbency, historical donor ideology "
        "and the restricted historical Latino indicator. The Democratic-incumbent coefficient "
        "alone does not establish an advantage. Higher donor CFscore is associated with "
        "better performance in its selective donor-linked sample, not proof that changing "
        "a nominee's ideology changes votes. No matched predictive-gain interval excludes zero.",
        "",
        "| Trait / existing contrast | Adjusted association, share pp | Pointwise 95% interval | n |",
        "| --- | ---: | --- | ---: |",
    ]
    for r in terms:
        if r["focal"]:
            lines.append(
                f"| {LABELS[r['trait']]} / {r['term']} | {r['estimate_share_pp']:.3f} | "
                f"[{r['ci_low']:.3f}, {r['ci_high']:.3f}] | {r['n']} |"
            )
    lines += [
        "",
        "Continuous contrasts are per ten years of age/House service, 0.5 donor-score units, "
        "0.1 prior-voting-score units and five percentage points of party defection. Category "
        "names specify the reference. These pointwise coefficient intervals are not "
        "multiplicity-adjusted; Holm below applies to each entire trait block, including the "
        "joint incumbency block. Different traits use different selected populations.",
        "",
        "| Trait | Fit n | States | Holm p | Restricted prediction n | MAE gain, share pp | Gain interval |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for r in fits:
        p = r.get("prediction", {})
        gain = p.get("MAE_gain_share_pp")
        lo, hi = p.get("gain_ci_low"), p.get("gain_ci_high")
        interval = f"[{lo:.3f}, {hi:.3f}]" if lo is not None and hi is not None else "unavailable"
        lines.append(
            f"| {LABELS[r['trait']]} | {r['n']} | {r['state_clusters']} | "
            f"{r['holm_pvalue']:.5g} | {p.get('paired_candidates', 0)} | "
            f"{f'{gain:.3f}' if gain is not None else 'unavailable'} | {interval} |"
        )
    lines += [
        "",
        "Prediction uses state-held-out/person-purged folds, training-only preprocessing, "
        "matched baseline/augmented samples and full outer-deletion uncertainty. "
        "Restricted validation is not full-population predictive support.",
        "",
        "## Religion: corrected software, retained failure",
        "",
        "On the frozen V7 religion association population, training-only nuisance estimability "
        "corrects 121/123 full-fit predictions to 122/123. The Iowa-2 row is estimable from "
        "training data; Iowa-3 has an unseen opponent-incumbency stratum and stays unsupported. "
        "No test outcome determines the reduction, no unknown control is imputed and the "
        "123-candidate target is not silently narrowed. Current-release counts appear above; "
        "full-population fold files retain exact row failures. Earlier fits remain immutable.",
        "",
        "## Restricted historical Latino indicator",
        "",
        "The frozen V7 association covers 89 candidates in 27 states: 83 incumbents and only "
        "six nonincumbents, with no unresolved incumbency. It does not represent all nominees. "
        "Its +4.932 share-pp adjusted association (95% interval 2.841–7.023; Holm p≈0.000701) "
        "uses explicit historical author-coded 0/1 values and independently linked people. "
        "Zeros are not inferred from White labels or missing records. The restricted paired "
        "prediction population is 87; its MAE-gain interval [−0.420, 1.117] includes zero. "
        "Association evidence is not predictive improvement or a causal nomination effect.",
        "",
        "`historical-latino-population.json` exports every included candidate, state counts, "
        "incumbent/challenger composition, overlap with all other fields, exclusion counts "
        "and the already specified competitive/source sensitivities. The preserved "
        "state-deletion files provide existing influence checks; no new model search was run.",
        "",
        "## Remaining limitations by trait",
        "",
    ]
    for r in summary["trait_progress"]:
        lines.append(f"- **{LABELS[r['trait']]}:** {r['remaining_limitations']}")
    lines += [
        "",
        "## Browser, provenance and reproducibility",
        "",
        "The all-candidate browser below works without JavaScript; expand cells for original "
        "source links and qualification. Sources retain literal fragments, hashes, retrieval "
        "methods/dates, factual timing, identity decisions and native candidate-contest keys. "
        "Five rejected cross-contest transfers and all frozen releases remain preserved.",
        "",
        "Figures are alongside this report. Complete result tables, observations, source "
        "receipts, exclusions, folds and queries are in the complete-query download; the "
        "Substack download includes that exact complete archive, not metadata alone. "
        "Run `python -m which_candidate.house_project --evidence-only` from an installed "
        "checkout or extracted complete download for the offline reconstruction. "
        "See `docs/HOUSE_CHARACTERISTICS_V8_ACQUISITION.md` for source-family outcomes, "
        "remaining evidence dependencies and exact development/acceptance commands.",
        "",
    ]
    return "\n".join(lines)
