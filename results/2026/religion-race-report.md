# Religion, race and constituency composition

Exploratory extension, specified after the original six-feature results. All estimates below are among verified Democratic incumbents, not all nominees. The primary outcome is 2026; 2016-2024 counts are historical context, not fitted here. These are aggregate observational associations, not causal effects or evidence about individual religious/racial groups' votes.

## Religion categories and Census-adjusted comparisons

Pew/CQ office-questionnaire snapshots expand the optional authorized directory fields. Catholic, Protestant, Jewish, Muslim, atheist, agnostic, unaffiliated and other identities remain distinct. Humanist is not atheist; unknown/refused is never unaffiliated. Denominations are retained in the evidence. Unspecified Christian is not automatically Protestant.

| Chamber | Category vs Protestant | Variant | Share-point association | Pointwise 95% CI | N | Holm p |
|---|---|---|---:|---|---:|---:|
| house | catholic | lean_only | +1.02 | [-1.07, +3.10] | 72 | 1.000 |
| house | catholic | census_adjusted | +1.34 | [-0.24, +2.92] | 72 | 0.839 |
| house | jewish | lean_only | -1.03 | [-3.58, +1.52] | 50 | 1.000 |
| house | jewish | census_adjusted | +0.34 | [-1.27, +1.95] | 50 | 1.000 |
| house | muslim | lean_only | -1.05 | [-4.80, +2.70] | 45 | 1.000 |
| house | muslim | census_adjusted | +1.70 | [+0.06, +3.34] | 45 | 0.432 |
| senate | catholic | lean_only | +4.02 | [-2.30, +10.35] | 8 | 0.176 |

Census-adjusted models add Black, Asian, Indigenous, NHPI, other-race, multiracial and Hispanic population shares to presidential lean, lean-squared and cycle. White is the omitted race component; Hispanic origin overlaps race. These ACS five-year estimates describe residents, not eligible voters. They are retrospective controls and never enter forward forecasts. For 2026, 2024 ACS is joined only to states and Census-reported unchanged district maps; all ten reported map-change states are held from district composition models. The 2021 ACS file still uses the 116th map: North Carolina 2020 is explicitly held.

## Religious constituency context is not Census religion

The Census does not collect religious affiliation. The separately attributed Setzler district religiosity v2 sensitivity uses 2010 RCMS congregation adherence apportioned from counties on 2016/2018 maps only. Split-county uniformity is an approximation. Pennsylvania 2018 is held pending independent map qualification. No old-map religious estimates are carried into 2020-2026. Consequently no district-religion-adjusted 2026 estimate is claimed. The restricted religious context models control Catholic, evangelical, mainline and other adherence shares alongside Census race/Hispanic composition. 'Other' includes Black Protestants, LDS and Jehovah's Witnesses; no-congregation is **not atheist or unaffiliated**. Jewish/Muslim/atheist constituency shares are unavailable, not zero.

| Chamber | Matching-share interaction | Share-point change per +10 pp population | Pointwise 95% CI | N |
|---|---|---:|---|---:|
| house | asian_or_pacific_islander vs black | -1.44 | [-5.64, +2.76] | 29 |

Interaction main effects are evaluated at the sample's mean matching share, retained in each fit. These are exploratory ecological associations, not individual voter effects. Pointwise intervals are nominal; Holm p-values cover estimated extension focal/interaction tests per chamber.

## Race and Hispanic origin: evidence before comparison

Explicit member-authorized identity statements and positive House Historian 119th-Congress group records qualify; Historian classifications are not labeled self-reports. The latter supplement 2026 only and do not enter forecasts. Its Asian/Pacific Islander umbrella remains combined unless narrower explicit evidence exists; its matching Census share is Asian plus NHPI. Names, photographs, religion, birthplace and caucus membership never supply race. Multiple races and Hispanic origin are separate fields. Missing race never becomes White, and missing Hispanic origin never becomes non-Hispanic. Sparse statements may not support a White comparison or any race coefficient. The pipeline retains these as explicit holds rather than inventing a racial ranking.

| Chamber | Race comparison | Variant | Share-point association | Pointwise 95% CI | N |
|---|---|---|---:|---|---:|
| house | asian_or_pacific_islander vs black | lean_only | +0.64 | [-4.57, +5.85] | 29 |
| house | asian_or_pacific_islander vs black | census_adjusted | -1.06 | [-2.91, +0.79] | 29 |
| house | asian_or_pacific_islander vs black | population_interaction | -0.62 | [-2.58, +1.34] | 29 |

Known-group comparisons against Black, if estimable, apply only to that selected documented subset; they do not represent White-versus-minority or all nominees.

## Complete category counts

Counts are candidate-election observations, not unique people. Every category appears even when absent. A category contrast requires at least three distinct people and three states in each group, eight clusters overall and an identified fit.

| Phase | Chamber | Field | Category | Rows | People | States |
|---|---|---|---|---:|---:|---:|
| primary_2026 | house | religion_category | catholic | 52 | 52 | 18 |
| primary_2026 | house | religion_category | protestant | 63 | 63 | 27 |
| primary_2026 | house | religion_category | jewish | 16 | 16 | 11 |
| primary_2026 | house | religion_category | muslim | 3 | 3 | 3 |
| primary_2026 | house | religion_category | atheist | 0 | 0 | 0 |
| primary_2026 | house | religion_category | agnostic | 0 | 0 | 0 |
| primary_2026 | house | religion_category | unaffiliated | 2 | 2 | 2 |
| primary_2026 | house | religion_category | hindu | 2 | 2 | 2 |
| primary_2026 | house | religion_category | buddhist | 2 | 2 | 2 |
| primary_2026 | house | religion_category | orthodox | 1 | 1 | 1 |
| primary_2026 | house | religion_category | lds | 0 | 0 | 0 |
| primary_2026 | house | religion_category | unitarian_universalist | 3 | 3 | 2 |
| primary_2026 | house | religion_category | humanist | 1 | 1 | 1 |
| primary_2026 | house | religion_category | christian_unspecified | 0 | 0 | 0 |
| primary_2026 | house | religion_category | other_christian | 0 | 0 | 0 |
| primary_2026 | house | religion_category | other | 0 | 0 | 0 |
| primary_2026 | house | religion_category | multiple | 0 | 0 | 0 |
| primary_2026 | house | religion_category | unknown | 18 | 18 | 15 |
| historical_2016_2024 | house | religion_category | catholic | 227 | 94 | 23 |
| historical_2016_2024 | house | religion_category | protestant | 274 | 112 | 33 |
| historical_2016_2024 | house | religion_category | jewish | 71 | 29 | 18 |
| historical_2016_2024 | house | religion_category | muslim | 10 | 3 | 3 |
| historical_2016_2024 | house | religion_category | atheist | 0 | 0 | 0 |
| historical_2016_2024 | house | religion_category | agnostic | 0 | 0 | 0 |
| historical_2016_2024 | house | religion_category | unaffiliated | 0 | 0 | 0 |
| historical_2016_2024 | house | religion_category | hindu | 8 | 3 | 3 |
| historical_2016_2024 | house | religion_category | buddhist | 3 | 1 | 1 |
| historical_2016_2024 | house | religion_category | orthodox | 8 | 3 | 3 |
| historical_2016_2024 | house | religion_category | lds | 1 | 1 | 1 |
| historical_2016_2024 | house | religion_category | unitarian_universalist | 10 | 4 | 2 |
| historical_2016_2024 | house | religion_category | humanist | 1 | 1 | 1 |
| historical_2016_2024 | house | religion_category | christian_unspecified | 6 | 6 | 5 |
| historical_2016_2024 | house | religion_category | other_christian | 0 | 0 | 0 |
| historical_2016_2024 | house | religion_category | other | 0 | 0 | 0 |
| historical_2016_2024 | house | religion_category | multiple | 0 | 0 | 0 |
| historical_2016_2024 | house | religion_category | unknown | 140 | 117 | 33 |
| primary_2026 | house | race_category | white | 0 | 0 | 0 |
| primary_2026 | house | race_category | black | 37 | 37 | 21 |
| primary_2026 | house | race_category | asian | 0 | 0 | 0 |
| primary_2026 | house | race_category | native_american | 0 | 0 | 0 |
| primary_2026 | house | race_category | nhpi | 0 | 0 | 0 |
| primary_2026 | house | race_category | asian_or_pacific_islander | 11 | 11 | 5 |
| primary_2026 | house | race_category | multiracial | 2 | 2 | 2 |
| primary_2026 | house | race_category | other | 0 | 0 | 0 |
| primary_2026 | house | race_category | unknown | 113 | 113 | 29 |
| historical_2016_2024 | house | race_category | white | 0 | 0 | 0 |
| historical_2016_2024 | house | race_category | black | 5 | 1 | 1 |
| historical_2016_2024 | house | race_category | asian | 0 | 0 | 0 |
| historical_2016_2024 | house | race_category | native_american | 1 | 1 | 1 |
| historical_2016_2024 | house | race_category | nhpi | 0 | 0 | 0 |
| historical_2016_2024 | house | race_category | asian_or_pacific_islander | 0 | 0 | 0 |
| historical_2016_2024 | house | race_category | multiracial | 0 | 0 | 0 |
| historical_2016_2024 | house | race_category | other | 0 | 0 | 0 |
| historical_2016_2024 | house | race_category | unknown | 753 | 281 | 41 |
| primary_2026 | house | hispanic_origin | True | 31 | 31 | 11 |
| primary_2026 | house | hispanic_origin | False | 0 | 0 | 0 |
| primary_2026 | house | hispanic_origin | None | 132 | 132 | 35 |
| historical_2016_2024 | house | hispanic_origin | True | 0 | 0 | 0 |
| historical_2016_2024 | house | hispanic_origin | False | 0 | 0 | 0 |
| historical_2016_2024 | house | hispanic_origin | None | 759 | 283 | 41 |
| primary_2026 | senate | religion_category | catholic | 3 | 3 | 3 |
| primary_2026 | senate | religion_category | protestant | 5 | 5 | 5 |
| primary_2026 | senate | religion_category | jewish | 1 | 1 | 1 |
| primary_2026 | senate | religion_category | muslim | 0 | 0 | 0 |
| primary_2026 | senate | religion_category | atheist | 0 | 0 | 0 |
| primary_2026 | senate | religion_category | agnostic | 0 | 0 | 0 |
| primary_2026 | senate | religion_category | unaffiliated | 0 | 0 | 0 |
| primary_2026 | senate | religion_category | hindu | 0 | 0 | 0 |
| primary_2026 | senate | religion_category | buddhist | 0 | 0 | 0 |
| primary_2026 | senate | religion_category | orthodox | 0 | 0 | 0 |
| primary_2026 | senate | religion_category | lds | 0 | 0 | 0 |
| primary_2026 | senate | religion_category | unitarian_universalist | 0 | 0 | 0 |
| primary_2026 | senate | religion_category | humanist | 0 | 0 | 0 |
| primary_2026 | senate | religion_category | christian_unspecified | 0 | 0 | 0 |
| primary_2026 | senate | religion_category | other_christian | 0 | 0 | 0 |
| primary_2026 | senate | religion_category | other | 0 | 0 | 0 |
| primary_2026 | senate | religion_category | multiple | 0 | 0 | 0 |
| primary_2026 | senate | religion_category | unknown | 0 | 0 | 0 |
| historical_2016_2024 | senate | religion_category | catholic | 18 | 14 | 13 |
| historical_2016_2024 | senate | religion_category | protestant | 23 | 17 | 15 |
| historical_2016_2024 | senate | religion_category | jewish | 4 | 4 | 4 |
| historical_2016_2024 | senate | religion_category | muslim | 0 | 0 | 0 |
| historical_2016_2024 | senate | religion_category | atheist | 0 | 0 | 0 |
| historical_2016_2024 | senate | religion_category | agnostic | 0 | 0 | 0 |
| historical_2016_2024 | senate | religion_category | unaffiliated | 0 | 0 | 0 |
| historical_2016_2024 | senate | religion_category | hindu | 0 | 0 | 0 |
| historical_2016_2024 | senate | religion_category | buddhist | 2 | 1 | 1 |
| historical_2016_2024 | senate | religion_category | orthodox | 0 | 0 | 0 |
| historical_2016_2024 | senate | religion_category | lds | 0 | 0 | 0 |
| historical_2016_2024 | senate | religion_category | unitarian_universalist | 0 | 0 | 0 |
| historical_2016_2024 | senate | religion_category | humanist | 0 | 0 | 0 |
| historical_2016_2024 | senate | religion_category | christian_unspecified | 0 | 0 | 0 |
| historical_2016_2024 | senate | religion_category | other_christian | 0 | 0 | 0 |
| historical_2016_2024 | senate | religion_category | other | 0 | 0 | 0 |
| historical_2016_2024 | senate | religion_category | multiple | 0 | 0 | 0 |
| historical_2016_2024 | senate | religion_category | unknown | 13 | 11 | 11 |
| primary_2026 | senate | race_category | white | 0 | 0 | 0 |
| primary_2026 | senate | race_category | black | 1 | 1 | 1 |
| primary_2026 | senate | race_category | asian | 0 | 0 | 0 |
| primary_2026 | senate | race_category | native_american | 0 | 0 | 0 |
| primary_2026 | senate | race_category | nhpi | 0 | 0 | 0 |
| primary_2026 | senate | race_category | asian_or_pacific_islander | 0 | 0 | 0 |
| primary_2026 | senate | race_category | multiracial | 0 | 0 | 0 |
| primary_2026 | senate | race_category | other | 0 | 0 | 0 |
| primary_2026 | senate | race_category | unknown | 8 | 8 | 8 |
| historical_2016_2024 | senate | race_category | white | 0 | 0 | 0 |
| historical_2016_2024 | senate | race_category | black | 0 | 0 | 0 |
| historical_2016_2024 | senate | race_category | asian | 0 | 0 | 0 |
| historical_2016_2024 | senate | race_category | native_american | 0 | 0 | 0 |
| historical_2016_2024 | senate | race_category | nhpi | 0 | 0 | 0 |
| historical_2016_2024 | senate | race_category | asian_or_pacific_islander | 0 | 0 | 0 |
| historical_2016_2024 | senate | race_category | multiracial | 0 | 0 | 0 |
| historical_2016_2024 | senate | race_category | other | 0 | 0 | 0 |
| historical_2016_2024 | senate | race_category | unknown | 60 | 44 | 30 |
| primary_2026 | senate | hispanic_origin | True | 1 | 1 | 1 |
| primary_2026 | senate | hispanic_origin | False | 0 | 0 | 0 |
| primary_2026 | senate | hispanic_origin | None | 8 | 8 | 8 |
| historical_2016_2024 | senate | hispanic_origin | True | 0 | 0 | 0 |
| historical_2016_2024 | senate | hispanic_origin | False | 0 | 0 | 0 |
| historical_2016_2024 | senate | hispanic_origin | None | 60 | 44 | 30 |

Complete fit dispositions: {'estimated': 10, 'insufficient_documented_group_support': 201, 'insufficient_rows_or_state_clusters': 1}. All attempted contrasts, including zero-observation atheist categories and unavailable religion contexts, are in `contextual-model-fits.jsonl.gz`. Complete population tables, member evidence, matches, unknowns, group support, fit membership and covariance are retained, not metadata-only downloads.
