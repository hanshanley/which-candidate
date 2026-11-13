from collections import defaultdict

import numpy as np

from .demographics import RACE_CONTROLS, RACES, RELIGIONS
from .models import fit_clustered


def group_counts(rows, field, group):
    sample = [r for r in rows if r.get(field) == group]
    return {
        "rows": len(sample),
        "people": len({r["person_group"] for r in sample}),
        "states": len({r["state"] for r in sample}),
    }


def supported(count):
    return count["people"] >= 3 and count["states"] >= 3


def category_matrix(rows, field, group, variant, center=None, cycles=None):
    cycles = sorted({r["year"] for r in rows}) if cycles is None else cycles
    names = ["intercept", "lean_10pp", "lean_squared"]
    names.extend(f"cycle_{year}" for year in cycles[1:])
    focal = f"{field}_{group}"
    names.append(focal)
    census = variant != "lean_only"
    if census:
        names.extend(f"population_{g}_10pp" for g in RACE_CONTROLS)
    religious = variant in ("religion_context", "religion_interaction")
    if religious:
        names.extend(
            f"congregation_{g}_10pp" for g in ("Catholic", "EvanProt", "MainProt", "Other")
        )
    matching = None
    if variant == "population_interaction" and field == "race_category":
        matching = group
    elif variant == "population_interaction" and field == "hispanic_origin":
        matching = "hispanic"
    elif variant == "religion_interaction" and group == "catholic":
        matching = "Catholic"
    if matching:
        if center is None:
            center = (
                float(
                    np.mean(
                        [
                            r[
                                "constituency_religion_shares_pct"
                                if religious
                                else "constituency_race_shares_pct"
                            ][matching]
                            for r in rows
                        ]
                    )
                )
                if rows
                else 0
            )
        names.append(f"{focal}_x_matching_share_10pp")
    values = []
    for row in rows:
        lean = (row["presidential_D_two_party_share_pct"] - 50) / 10
        values_row = [1, lean, lean**2]
        values_row.extend(int(row["year"] == y) for y in cycles[1:])
        indicator = int(row[field] == group)
        values_row.append(indicator)
        if census:
            values_row.extend(row["constituency_race_shares_pct"][g] / 10 for g in RACE_CONTROLS)
        if religious:
            values_row.extend(
                row["constituency_religion_shares_pct"][g] / 10
                for g in ("Catholic", "EvanProt", "MainProt", "Other")
            )
        if matching:
            share = row[
                "constituency_religion_shares_pct" if religious else "constituency_race_shares_pct"
            ][matching]
            values_row.append(indicator * (share - center) / 10)
        values.append(values_row)
    return np.asarray(values, dtype=float).reshape((len(rows), len(names))), names, center


def contextual_associations(panel, target_year=2026):
    fits, terms, counts = [], [], []
    for chamber in ("house", "senate"):
        eligible = [
            r
            for r in panel
            if r["chamber"] == chamber
            and r["eligible"]
            and r["year"] == target_year
            and r.get("D_incumbent") is True
            and r.get("service_verified_incumbent") is True
        ]
        for field, categories, reference in (
            ("religion_category", RELIGIONS, "protestant"),
            ("race_category", RACES, "white"),
            ("hispanic_origin", (True, False, None), False),
        ):
            for phase, rows in (
                (f"primary_{target_year}", eligible),
                (
                    "historical_2016_2024",
                    [
                        r
                        for r in panel
                        if r["chamber"] == chamber
                        and r["eligible"]
                        and r["year"] <= 2024
                        and r.get("D_incumbent") is True
                        and r.get("service_verified_incumbent") is True
                    ],
                ),
            ):
                for group in categories:
                    counts.append(
                        {
                            "chamber": chamber,
                            "phase": phase,
                            "field": field,
                            "category": group,
                            **group_counts(rows, field, group),
                        }
                    )
            references = [reference]
            if field == "race_category":
                references.append("black")
            for comparator in references:
                for group in categories:
                    if group in (comparator, "unknown", None):
                        continue
                    pair = [r for r in eligible if r.get(field) in (group, comparator)]
                    pair = [
                        r
                        for r in pair
                        if all(
                            g in r.get("constituency_race_shares_pct", {}) for g in RACE_CONTROLS
                        )
                    ]
                    variants = ["lean_only", "census_adjusted"]
                    if (
                        field == "race_category" and group not in ("other", "multiracial")
                    ) or field == "hispanic_origin":
                        variants.append("population_interaction")
                    if field == "religion_category":
                        variants.extend(("religion_sample_census", "religion_context"))
                        if group == "catholic":
                            variants.append("religion_interaction")
                    for variant in variants:
                        rows = [
                            r
                            for r in pair
                            if variant == "lean_only"
                            or all(
                                g in r.get("constituency_race_shares_pct", {})
                                for g in RACE_CONTROLS
                            )
                        ]
                        if variant in (
                            "religion_sample_census",
                            "religion_context",
                            "religion_interaction",
                        ):
                            rows = [r for r in rows if r.get("constituency_religion_shares_pct")]
                        support = {g: group_counts(rows, field, g) for g in (comparator, group)}
                        x, names, center = category_matrix(rows, field, group, variant)
                        model_id = f"{chamber}:{field}:{group}_vs_{comparator}:{variant}"
                        common = {
                            "model_id": model_id,
                            "chamber": chamber,
                            "field": field,
                            "category": group,
                            "reference": comparator,
                            "variant": variant,
                            "target_year": target_year,
                            "terms": names,
                            "group_support": support,
                            "interaction_center_population_pct": center,
                            "candidate_election_ids": [r["D_candidate_election_id"] for r in rows],
                            "n": len(rows),
                        }
                        if not all(supported(v) for v in support.values()):
                            fits.append(
                                {**common, "status": "insufficient_documented_group_support"}
                            )
                            continue
                        fit = fit_clustered(
                            x,
                            np.array([r["descriptive_gap_share_pp"] for r in rows]),
                            [r["state"] for r in rows],
                        )
                        fits.append({**common, **fit})
                        if fit["status"] != "estimated":
                            continue
                        for index, name in enumerate(names):
                            terms.append(
                                {
                                    "model_id": model_id,
                                    "chamber": chamber,
                                    "field": field,
                                    "category": group,
                                    "reference": comparator,
                                    "variant": variant,
                                    "target_year": target_year,
                                    "term": name,
                                    "focal": name.startswith(field),
                                    "estimate_share_pp": fit["coefficients"][index],
                                    "ci_low": fit["ci_low"][index],
                                    "ci_high": fit["ci_high"][index],
                                    "pvalue": fit["pvalues"][index],
                                    "holm_pvalue": None,
                                    "n": len(rows),
                                    "state_clusters": fit["state_clusters"],
                                }
                            )
        focal = [r for r in terms if r["chamber"] == chamber and r["focal"]]
        previous = 0
        for rank, row in enumerate(sorted(focal, key=lambda r: r["pvalue"])):
            previous = max(previous, min(1.0, row["pvalue"] * (len(focal) - rank)))
            row["holm_pvalue"] = previous
    return fits, terms, counts


def category_report(fits, terms, counts, panel):
    lines = [
        "# Religion, race and constituency composition",
        "",
        "Exploratory extension, specified after the original six-feature results. "
        "All estimates below are among verified Democratic incumbents, not all nominees. "
        "The primary outcome is 2026; 2016-2024 counts are historical context, not fitted here. "
        "These are aggregate observational associations, not causal effects or evidence "
        "about individual religious/racial groups' votes.",
        "",
        "## Religion categories and Census-adjusted comparisons",
        "",
        "Pew/CQ office-questionnaire snapshots expand the optional authorized directory "
        "fields. Catholic, Protestant, Jewish, Muslim, atheist, agnostic, unaffiliated and "
        "other identities remain distinct. Humanist is not atheist; unknown/refused is "
        "never unaffiliated. Denominations are retained in the evidence. Unspecified "
        "Christian is not automatically Protestant.",
        "",
        "| Chamber | Category vs Protestant | Variant | Share-point association | Pointwise 95% CI | N | Holm p |",
        "|---|---|---|---:|---|---:|---:|",
    ]
    for row in terms:
        if (
            row["field"] == "religion_category"
            and row["focal"]
            and "_x_matching_" not in row["term"]
        ):
            lines.append(
                f"| {row['chamber']} | {row['category']} | {row['variant']} | "
                f"{row['estimate_share_pp']:+.2f} | [{row['ci_low']:+.2f}, {row['ci_high']:+.2f}] | "
                f"{row['n']} | {row['holm_pvalue']:.3f} |"
            )
    lines += [
        "",
        "Census-adjusted models add Black, Asian, Indigenous, NHPI, other-race, multiracial "
        "and Hispanic population shares to presidential lean, lean-squared and cycle. "
        "White is the omitted race component; Hispanic origin overlaps race. These ACS "
        "five-year estimates describe residents, not eligible voters. They are retrospective "
        "controls and never enter forward forecasts. For 2026, 2024 ACS is joined only to "
        "states and Census-reported unchanged district maps; all ten reported map-change "
        "states are held from district composition models. "
        "The 2021 ACS file still uses the 116th map: North Carolina 2020 is explicitly held.",
        "",
        "## Religious constituency context is not Census religion",
        "",
        "The Census does not collect religious affiliation. The separately attributed "
        "Setzler district religiosity v2 sensitivity uses 2010 RCMS congregation adherence "
        "apportioned from counties on 2016/2018 maps only. Split-county uniformity is an "
        "approximation. Pennsylvania 2018 is held pending independent map qualification. "
        "No old-map religious estimates are carried into 2020-2026. Consequently no "
        "district-religion-adjusted 2026 estimate is claimed. The restricted religious "
        "context models control Catholic, evangelical, mainline and other adherence shares "
        "alongside Census race/Hispanic composition. 'Other' includes Black Protestants, "
        "LDS and Jehovah's Witnesses; no-congregation is **not atheist or unaffiliated**. "
        "Jewish/Muslim/atheist constituency shares are unavailable, not zero.",
        "",
        "| Chamber | Matching-share interaction | Share-point change per +10 pp population | Pointwise 95% CI | N |",
        "|---|---|---:|---|---:|",
    ]
    for row in terms:
        if row["focal"] and "_x_matching_" in row["term"]:
            lines.append(
                f"| {row['chamber']} | {row['category']} vs {row['reference']} | "
                f"{row['estimate_share_pp']:+.2f} | [{row['ci_low']:+.2f}, {row['ci_high']:+.2f}] | "
                f"{row['n']} |"
            )
    lines += [
        "",
        "Interaction main effects are evaluated at the sample's mean matching share, "
        "retained in each fit. These are exploratory ecological associations, not individual "
        "voter effects. Pointwise intervals are nominal; Holm p-values cover estimated "
        "extension focal/interaction tests per chamber.",
        "",
        "## Race and Hispanic origin: evidence before comparison",
        "",
        "Explicit member-authorized identity statements and positive House Historian "
        "119th-Congress group records qualify; Historian classifications are not labeled "
        "self-reports. The latter supplement 2026 only and do not enter forecasts. "
        "Its Asian/Pacific Islander umbrella remains combined unless narrower explicit "
        "evidence exists; its matching Census share is Asian plus NHPI. Names, photographs, "
        "religion, birthplace and caucus membership never supply race. Multiple races and "
        "Hispanic origin are separate fields. Missing race never becomes White, and "
        "missing Hispanic origin never becomes non-Hispanic. Sparse statements may not "
        "support a White comparison or any race coefficient. The pipeline retains these "
        "as explicit holds rather than inventing a racial ranking.",
        "",
        "| Chamber | Race comparison | Variant | Share-point association | Pointwise 95% CI | N |",
        "|---|---|---|---:|---|---:|",
    ]
    for row in terms:
        if row["field"] == "race_category" and row["focal"] and "_x_matching_" not in row["term"]:
            lines.append(
                f"| {row['chamber']} | {row['category']} vs {row['reference']} | {row['variant']} | "
                f"{row['estimate_share_pp']:+.2f} | [{row['ci_low']:+.2f}, {row['ci_high']:+.2f}] | {row['n']} |"
            )
    lines += [
        "",
        "Known-group comparisons against Black, if estimable, apply only to that selected "
        "documented subset; they do not represent White-versus-minority or all nominees.",
        "",
        "## Complete category counts",
        "",
        "Counts are candidate-election observations, not unique people. Every category "
        "appears even when absent. A category contrast requires at least three distinct "
        "people and three states in each group, eight clusters overall and an identified fit.",
        "",
        "| Phase | Chamber | Field | Category | Rows | People | States |",
        "|---|---|---|---|---:|---:|---:|",
    ]
    for row in counts:
        lines.append(
            f"| {row['phase']} | {row['chamber']} | {row['field']} | {row['category']} | "
            f"{row['rows']} | {row['people']} | {row['states']} |"
        )
    statuses = defaultdict(int)
    for fit in fits:
        statuses[fit["status"]] += 1
    lines += [
        "",
        f"Complete fit dispositions: {dict(sorted(statuses.items()))}. "
        "All attempted contrasts, including zero-observation atheist categories and "
        "unavailable religion contexts, are in `contextual-model-fits.jsonl.gz`. "
        "Complete population tables, member evidence, matches, unknowns, group support, "
        "fit membership and covariance are retained, not metadata-only downloads.",
        "",
    ]
    return "\n".join(lines)
