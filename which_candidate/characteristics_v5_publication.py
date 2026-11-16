"""Measured V4-to-V5 acquisition, analytical coverage and unchanged-model results."""

from .characteristics_publication import BLOCK_LABELS, LABELS, number


def report(summary, fits, terms, coverage, sources, research):
    lines = [
        "# Candidate characteristics: V5 new-source successor",
        "",
        "**V1–V4 remain frozen. No website deployment.** The same fifteen-trait question "
        "retains all 449 Democrats and 405 eligible performance comparisons. Native returns "
        "remain the provisional November 12–13 snapshot, not certified outcomes. "
        "Observational associations are not causal nominee-replacement effects.",
        "",
        "## Measured acquisition",
        "",
        f"**{summary['acquisition']['new_document_hashes']} new evidence-yielding originals; "
        f"{summary['newly_acquired_observations']} observations; "
        f"{summary['new_source_candidates']} candidates; "
        f"{summary['new_source_candidate_trait_fields']} candidate-by-trait fields.** "
        f"First observations reach {summary['newly_informed_candidate_trait_fields']} previously "
        f"unknown fields across {summary['newly_informed_candidates']} candidates. Other new "
        "observations add precision, missing requirements or corroboration; they are not all "
        "newly discovered facts.",
        "",
        f"Newly analytical Democratic fields: **{summary['newly_analysis_eligible_D_fields']}**. "
        f"Incumbency holds: **{summary['D_unknown_incumbency_before']}→"
        f"{summary['D_unknown_incumbency_after']}**. "
        f"Existing observations newly qualified without new acquisition: "
        f"**{summary['existing_observations_newly_qualified']}**. Newly estimable trait blocks: "
        + (", ".join(summary["newly_estimable_contrasts"]) or "**none**")
        + ".",
        "",
        "The evidence-yielding biographies are the Illinois presidential-library Biss oral "
        "history, Maryland Manual Boafo profile, Nevada former-legislator biography, Tennessee "
        "Pearson profile and Senate-published Lacore testimony. Five official FEC candidate "
        "pages explicitly associate legal names with authorized campaign-name committees. "
        "This is new acquisition, not another qualification-only milestone. Failed Illinois "
        "bulk downloads and denied Tennessee/Navy sources remain acquisition failures; "
        "the independently Senate-published public testimony is its own original.",
        "",
        "## V4 → V5: all fifteen traits",
        "",
        "Distinct document hashes per trait are not additive. Factual qualification, "
        "analytical values and support-qualified fitted samples are different stages.",
        "",
        "| Trait | Sources / observations | Source-covered / first-informed candidates | Factual V4→V5 | Analytical V4→V5 | Fit n V4→V5 | Remaining limitation |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for r in summary["trait_progress"]:
        lines.append(
            f"| {LABELS[r['trait']]} | {r['new_evidence_source_hashes']} / {r['new_observations']} | "
            f"{r['source_informed_candidates']} / {r['newly_informed_candidates']} | "
            f"{r['factual_before']}→{r['factual_after']} | "
            f"{r['analytical_before']}→{r['analytical_after']} | "
            f"{r['fitted_before']}→{r['fitted_after']} | {r['remaining_limitations']} |"
        )
    lines += [
        "",
        "## Does evidence extend beyond incumbents?",
        "",
        "Frozen V4 incumbency groups are used below even when an unknown is resolved. "
        "These counts concern the 405 outcome-eligible candidates; the complete CSV also "
        "includes outcome-ineligible records and every trait.",
        "",
        "| Analytical trait | Incumbents V4→V5 | Nonincumbents V4→V5 | Unresolved V4→V5 |",
        "| --- | ---: | ---: | ---: |",
    ]
    for trait in ("age", "religion", "education", "profession", "military", "incumbency"):
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
        "## Literal review and exclusions",
        "",
        "Biss's August 1977 birth month fixes election age without inventing a day. "
        "Boafo and Pearson have explicit birthdays; Benitez-Thompson retains a year-only "
        "47–48 interval. Completed BA/BS, master's and doctorate statements qualify degrees; "
        "Pearson's Bowdoin listing alone does not establish graduation. "
        "Biss's dated mathematics teaching supports the historical education profession. "
        "Oracle government affairs is not automatically business management; licensed "
        "social work alone is not proof of clinical healthcare practice.",
        "",
        "Pearson's explicit Liberation Christianity description is factual at retrieval "
        "but remains analytically unavailable: the undated profile even mentions the "
        "future 115th General Assembly. A requested historical-session URL is not an "
        "archived historical document. No affiliation is inferred from upbringing or "
        "Black/Latino/Jewish caucus membership.",
        "",
        "FEC legal-name pages explicitly authorize Lee McInnis, Ray Pooley, Jake Johnson, "
        "Tom Perriello and Ace Parsi campaign-name committees in the matching 2026 House "
        "seat and party. These links support Challenger election classifications, not "
        "independently verified federal service. Jake Johnson's latest filing is after "
        "election day; this reconstruction is retrospective, never a prospective predictor. "
        "Surname-only Williams and Bradstock committees do not establish the needed aliases. "
        "Multiple FEC IDs and other unresolved identities remain held.",
        "",
        "Office histories mean before November 3, 2026, not before first House entry. "
        "Positive office categories and overlaps are exported separately; missing categories "
        "do not imply exclusive histories. No explicit negative office, government or "
        "military reference was acquired, so the original contrasts remain unavailable. "
        "Race remains the restricted historical CAWP Black/White women comparison; "
        "it is not generalized to all candidates. All five rejected cross-contest "
        "transfers and all earlier evidence remain protected.",
        "",
        "## Associations and matched-sample predictions",
        "",
        "| Block | Association n / states | Holm p (15) | Restricted paired n | MAE gain [95% interval], share pp |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for f in fits:
        p = f.get("prediction")
        gain = (
            f"{number(p['MAE_gain_share_pp'])} [{number(p['gain_ci_low'])}, {number(p['gain_ci_high'])}]"
            if p and p["complete"]
            else "diagnostic only"
            if p
            else "unavailable"
        )
        label = (
            "Historical CAWP Black/White women"
            if f["trait"] == "race"
            else BLOCK_LABELS[f["trait"]]
        )
        lines.append(
            f"| {label} | {f['n']} / {f['state_clusters']} | {number(f['holm_pvalue'], 6)} | "
            f"{p['paired_candidates'] if p else '—'} | {gain} |"
        )
    lines += [
        "",
        "Blocks clearing the unchanged fifteen-block Holm correction: "
        + (", ".join(BLOCK_LABELS[t] for t in summary["holm_below_005"]) or "none")
        + ".",
        "",
        "Joint D/R incumbency is not the Democratic-incumbent coefficient. Donor ideology "
        "is a selective historical donor-linked association, not universal moderation. "
        "Share percentage points are half D-minus-R margin points. "
        "No observational coefficient identifies the effect of replacing a nominee.",
        "",
        "| Focal term | Share pp [pointwise 95% CI] |",
        "| --- | ---: |",
    ]
    for t in terms:
        if t["focal"]:
            lines.append(
                f"| {LABELS[t['trait']]} / `{t['term']}` | {number(t['estimate_share_pp'])} "
                f"[{number(t['ci_low'])}, {number(t['ci_high'])}] |"
            )
    lines += [
        "",
        "## Validation and complete local deliverables",
        "",
        "Recomputed blocks: " + ", ".join(summary["recomputed_blocks"]) + ". "
        "Numerically input-identical V4 blocks reused: "
        + ", ".join(summary["reused_blocks"])
        + ". "
        "All selections and full-family Holm corrections are refreshed. No new model family "
        "or relaxed category, geographic, rank or deletion-support gate was introduced.",
        "",
        "State-held-out/person-purged validation retains identical baseline/augmented samples "
        "and training-only preprocessing. Restricted joint-incumbency support requires at least "
        "three states. Full-population failures are exported separately, not repaired by hiding "
        "them behind restricted intervals. Prediction intervals require the complete outer "
        "state-deletion pipeline; missing intervals remain missing.",
        "",
        "See `v4-v5-trait-progress.csv`, `acquisition-field-changes.csv`, "
        "`coverage-by-incumbency.csv`, selections, folds, deletions, source receipts and "
        "the acquisition registry's explicit exclusions. Both complete downloads retain all "
        "earlier frozen releases and complete permitted queries, not metadata substitutes. "
        "Normalized literal evidence supports offline replay without historical raw caches. "
        "The figure ZIP embeds the exact complete-query ZIP.",
        "",
        "Replay: `python -m which_candidate.house_project --evidence-only`. "
        "**Local report only; no website deployment.**",
        "",
    ]
    return "\n".join(lines)
