# Which Democrats outperformed? Historical candidate analysis

## Findings

The table reports **adjusted associations**, not causal effects of replacing a nominee. Development elections are **2016–2022**; **2024 is held out**. Positive estimates mean higher Democratic two-party vote share after constituency lean and election-cycle adjustment. One share point equals two D-minus-R margin points.

**Incumbency is the strongest recurring pattern:** Democratic incumbents are associated with **+2.94 share points in the House** and **+3.11 in the Senate**. The Senate estimate is much less precise and does not pass the six-test Holm correction. Adding incumbency improves the held-out 2024 predictions in both chambers.

**No broad moderation or party-defection advantage is established.** Both primary ideology and party-defection intervals include zero in both chambers. House tenure has a positive adjusted association, but adding it worsens 2024 predictive error. The source-recorded gender comparison does not survive multiplicity adjustment. These results do not justify a causal candidate-selection rule.

| Chamber | Comparison | Share-point association | Pointwise 95% interval | N | State clusters | Holm p |
|---|---|---:|---|---:|---:|---:|
| House | Democratic incumbent versus nonincumbent | +2.94 | [+1.97, +3.92] | 1492 | 49 | <0.001 |
| House | +0.1 rightward Nokken-Poole | -0.27 | [-0.72, +0.17] | 497 | 36 | 0.494 |
| House | +5 pp party defection | -0.22 | [-0.97, +0.52] | 492 | 36 | 0.546 |
| House | +10 years of age | +0.22 | [-0.10, +0.54] | 592 | 40 | 0.494 |
| House | +10 years of chamber service | +0.68 | [+0.37, +0.98] | 592 | 40 | <0.001 |
| House | Source-recorded F versus M | -0.60 | [-1.16, -0.04] | 592 | 40 | 0.151 |
| Senate | Democratic incumbent versus nonincumbent | +3.11 | [+0.66, +5.56] | 115 | 48 | 0.085 |
| Senate | +0.1 rightward Nokken-Poole | +0.27 | [-0.50, +1.05] | 45 | 29 | 1.000 |
| Senate | +5 pp party defection | -0.28 | [-1.02, +0.45] | 44 | 28 | 1.000 |
| Senate | +10 years of age | -1.16 | [-2.55, +0.23] | 46 | 30 | 0.487 |
| Senate | +10 years of chamber service | -0.75 | [-2.19, +0.68] | 46 | 30 | 1.000 |
| Senate | Source-recorded F versus M | -1.02 | [-3.45, +1.41] | 46 | 30 | 1.000 |

Incumbency comparisons include D and R incumbent indicators. All other comparisons are **among verified same-chamber Democratic incumbents**, separately adjusted, not all Democratic nominees. Ideology is continuous: rightward is not a categorical moderate/progressive label. Defection is disagreement with one's party on party-unity votes, not a measure of every bipartisan vote. Age, tenure and source-recorded gender are not mutually adjusted demographic effects. Pointwise intervals are not simultaneous; Holm p-values adjust the six primary focal-feature tests per chamber.

## Supplemental birthplace and religion comparisons

Complete pre-election official Congressional Directory editions provide biographies furnished or authorized by member offices. These two hypotheses were specified **after the initial six-feature run, before extracting biography fields or viewing their coefficients**. They are supplemental, not added retroactively to the original confirmatory family. Compare only verified Democratic incumbents with explicit fields; unknown religion is never nonreligion and unknown birthplace is never out-of-state.

| Chamber | Comparison | Share-point association | Pointwise 95% interval | N | Nominal p |
|---|---|---:|---|---:|---:|
| House | Born in represented state versus explicitly elsewhere | +1.26 | [+0.57, +1.96] | 398 | <0.001 |
| House | Explicitly Catholic versus other reported religion | +0.96 | [-0.91, +2.83] | 186 | 0.301 |
| Senate | Born in represented state versus explicitly elsewhere | +0.40 | [-3.03, +3.82] | 33 | 0.812 |
| Senate | Explicitly Catholic versus other reported religion | -2.39 | [-9.81, +5.02] | 12 | 0.488 |

These pointwise results are **not corrected across supplemental/sensitivity tests**. Birthplace is not residence or other local ties. Optional religion disclosure creates an especially selected sample; the Catholic-versus-other-explicit-report contrast does not compare all religions or all nominees. Inspect held-out errors below before interpreting a positive in-sample association as useful prediction. Complete literal fields, source pages, publication dates and unknowns are retained.

## Locked 2024 validation

Every prediction trains on **earlier elections only**, excluding the entire target state and identified repeated target people. Both models use identical training/test rows. Baseline controls constituency lean and presidential-versus-midterm status. It cannot know the held-out national electoral environment. Positive MAE improvement means candidate features improved prediction; negative means they worsened it.

| Chamber | Feature | 2024 N | Baseline MAE | Feature MAE | Improvement |
|---|---|---:|---:|---:|---:|
| House | age | 167 | 1.82 | 1.83 | -0.01 |
| House | born_in_state | 140 | 1.78 | 1.74 | +0.04 |
| House | defection | 133 | 1.82 | 1.75 | +0.07 |
| House | gender | 167 | 1.82 | 1.87 | -0.05 |
| House | ideology | 133 | 1.81 | 1.82 | -0.01 |
| House | incumbency | 389 | 2.16 | 1.86 | +0.31 |
| House | religion | 49 | 2.04 | 2.10 | -0.06 |
| House | tenure | 167 | 1.82 | 1.89 | -0.07 |
| Senate | age | 14 | 2.35 | 2.39 | -0.04 |
| Senate | born_in_state | 7 | 2.04 | 2.05 | -0.02 |
| Senate | defection | 14 | 2.27 | 3.06 | -0.79 |
| Senate | gender | 14 | 2.35 | 2.46 | -0.11 |
| Senate | ideology | 14 | 2.25 | 2.36 | -0.11 |
| Senate | incumbency | 30 | 3.27 | 2.66 | +0.61 |
| Senate | religion | 3 | 1.64 | 3.49 | -1.86 |
| Senate | tenure | 14 | 2.35 | 2.40 | -0.05 |

`validation.csv` includes all 2018/2020/2022/2024 chronological backtests, RMSE, signed error and explicitly retrospective, within-cycle-centered error. A favorable in-sample coefficient is not proof of a generally better candidate-selection rule.

## Coverage

| Year | Chamber | All contests | Eligible D/R benchmark comparisons |
|---|---|---:|---:|
| 2016 | house | 438 | 354 |
| 2016 | senate | 34 | 32 |
| 2018 | house | 439 | 374 |
| 2018 | senate | 35 | 29 |
| 2020 | house | 435 | 382 |
| 2020 | senate | 35 | 26 |
| 2022 | house | 436 | 382 |
| 2022 | senate | 36 | 28 |
| 2024 | house | 435 | 390 |
| 2024 | senate | 35 | 30 |

**13 Democratic source-incumbency/dated-service disagreements** are retained; dated same-chamber terms take precedence for resolved people. Full win/loss/unknown-outcome coverage is in `coverage.csv`. Members have better biographical coverage than losing challengers; the report does not pretend otherwise. Excluded contests and provisional 2026 rows remain in the complete candidate-query download.

## What remains unanswered

**The categorical religion/race and Census-composition extension is in `religion-race-report.md`.** Its explicitly supplemental results do not replace the original six tests above. Race coverage remains evidence-limited; unknowns are not White. **Military service, occupation, education, issue-specific positions and attendance are not measured here.** No inference from names, photos, party, current residence or missing records fills those fields. The sources used do not supply a qualified all-nominee panel, particularly for losers. The crosswalk's recorded gender field is not a verified self-identification panel.

This analysis cannot establish a causal moderation or party-defection advantage. Candidate selection, district fit, opponent quality, retirement, fundraising and unobserved campaign conditions can confound associations. Legislative comparisons condition on having survived into office and on reelection; first-term incumbents often lack the deliberately lagged record. Repeated people and constituencies are covered conservatively by state-held-out validation and state-clustered inference. Senate samples are small. No 2026 outcome contributes to estimation.

## Audits and sensitivities

`model-fits.jsonl.gz` and `model-terms.csv` include the prespecified joint ideology/defection model, ideology-by-lean interaction, competitive 40–60% constituencies, linear-only lean and separate-cycle estimates, including models that could not be estimated. Main models never use 2024 to select a specification. `alternate-2024-benchmarks.csv` shows how validation gaps change when the same 2024 map uses its recalculated 2020 presidential vote instead of 2024.

One small-Senate ideology-by-lean interaction is nominally significant (see the complete term table). Its positive interaction indicates a more rightward association in *bluer*, not redder, constituencies. It is one of many uncorrected sensitivity tests, is not independently validated, and does not establish a general moderation advantage. Competitive-seat and joint ideology/defection results likewise do not establish a broad advantage. Sparse cycle-specific Senate fits remain holds.

House presidential baselines are Daily Kos Elections/The Downballot's calculated election-map-specific estimates, **not certified district presidential compilations or independently audited boundaries**. Published 2016/2018 rounding remains. Senate uses official FEC state returns. 2024 Senate data come from the official Clerk report; special scopes and independent-led races are not mixed into D/R estimates. Full-career NOMINATE is never used. Voteview Nokken-Poole and party-unity features use only a completed Congress before each election, but are retrieved retrospective estimates, not archived prospective score vintages.

## Reproducibility

See `docs/ANALYSIS_SPEC.md` for the frozen estimands, formulas and units. `candidate-queries.csv` retains every contest; `candidate-features.csv` retains all named D/R feature queries, including losers and exclusions. Complete source originals remain in the private content-addressed cache. Every feature, benchmark, match, exclusion, fitted term, fold and prediction is downloadable with exact source rows and checksums. Builds are network-free. The private local replay package is not permission to redistribute source spreadsheets; The Downballot requests attribution and no reproduction of entire workbooks.
