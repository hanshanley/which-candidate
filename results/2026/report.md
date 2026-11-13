# Which Democrats did better in 2026?

**2026 is the primary election outcome.** Earlier elections are training data and backtests, not the answer to this question. These results use held, provisional provider counts, not certified final returns or a live November 13 tally.

## Outcome and coverage

The outcome is Democratic two-party vote share minus the constituency's 2024 presidential Democratic two-party share. House benchmarks are The Downballot's **2026-map** calculations, not old district numbers carried forward. Senate benchmarks use official statewide FEC presidential returns. One share point equals two D-minus-R margin points.

| Chamber | 2026 contests retained | Eligible comparisons | Identified Democrats |
|---|---:|---:|---:|
| House | 435 | 408 | 175 |
| Senate | 35 | 29 | 11 |

Retained provider update clocks range from **2026-11-07T12:29:37.528Z** to **2026-11-08T01:41:35.472Z**. Acquisition time is not the counting clock; different contests need not be equally complete. Certification and final-count completion remain unverified.

Senate counts are native **statewide** totals preserved in the complete source audit, not sums of county units. Florida and Ohio special seats are separately identified in contest IDs. Independent/nonpartisan candidates remain separate from Democrats. Unqualified Alaska/Maine ranked-choice rounds, Louisiana stages, missing/ambiguous major-party nominees and zero-reported major-party counts are held, not ranked.

## Characteristics associated with 2026 performance

Each model adjusts for constituency partisan lean and lean squared, separately by chamber. Incumbency models also control Republican incumbency. All other traits are compared **among verified same-chamber Democratic incumbents**, not all nominees. These are associations, not causal candidate-selection effects.

| Chamber | Comparison | Share-point association | Pointwise 95% interval | N | States | Holm p |
|---|---|---:|---|---:|---:|---:|
| House | Democratic incumbent versus nonincumbent | +0.15 | [-1.22, +1.51] | 349 | 46 | 1.000 |
| House | +0.1 rightward Nokken-Poole | -0.68 | [-1.41, +0.04] | 131 | 33 | 0.389 |
| House | +5 pp party defection | +0.35 | [-1.26, +1.95] | 130 | 33 | 1.000 |
| House | +10 years of age | +0.00 | [-0.65, +0.66] | 163 | 35 | 1.000 |
| House | +10 years of chamber service | +0.46 | [-0.18, +1.10] | 163 | 35 | 0.779 |
| House | Source-recorded F versus M | -0.19 | [-2.20, +1.82] | 163 | 35 | 1.000 |
| Senate | Democratic incumbent versus nonincumbent | +3.42 | [-1.40, +8.23] | 23 | 23 | 0.930 |
| Senate | +0.1 rightward Nokken-Poole | +0.93 | [-2.57, +4.42] | 9 | 9 | 1.000 |
| Senate | +5 pp party defection | -15.55 | [-45.98, +14.87] | 9 | 9 | 1.000 |
| Senate | +10 years of age | +0.72 | [-2.32, +3.76] | 9 | 9 | 1.000 |
| Senate | +10 years of chamber service | +1.60 | [-2.15, +5.35] | 9 | 9 | 1.000 |
| Senate | Source-recorded F versus M | Held: rank_deficient_or_ill_conditioned | — | 9 | 9 | — |

No primary comparison passes the six-test-per-chamber Holm threshold. That is not evidence that every trait has zero effect.

Ideology is prior-completed-Congress Nokken-Poole, not a categorical moderate/progressive label. Party defection concerns party-unity roll calls, not every bipartisan vote. For 2026 these use the 118th Congress, not voting records after the election. Retrieved score vintages are retrospective.

## Religion, race and constituency composition

See `religion-race-report.md` for Catholic, Protestant, Jewish, Muslim, atheist and other explicit religion categories; race and Hispanic origin are separate. Unknown identity is never treated as White, non-Hispanic or Protestant. Sparse or unidentified contrasts remain held rather than being imputed.

Census ACS 2024 race/Hispanic population composition supplies state controls and district controls only outside the ten states with Census-reported 2026 map changes. Those ten states' district composition models are held. These are total-population shares, not voters or CVAP. **Census does not collect religion.** The acquired 2016/2018 congregation estimates do not qualify as 2026 district religious composition; no such adjustment is claimed.

## Historical-to-2026 validation

The following retrospective replays train only on earlier elections and exclude the test state and every identified test person. They are not forecasts actually issued before Election Day. Census contextual variables do not enter these prediction models.

| Chamber | Model | 2026 predictions | MAE (share pp) | Improvement over same-sample baseline |
|---|---|---:|---:|---:|
| House | age | 163 | 6.52 | -0.02 |
| House | born_in_state | 135 | 6.72 | +0.25 |
| House | defection | 130 | 6.43 | -0.02 |
| House | gender | 163 | 6.58 | -0.08 |
| House | ideology | 131 | 6.41 | +0.03 |
| House | incumbency | 349 | 6.92 | +0.38 |
| House | tenure | 163 | 6.50 | -0.00 |
| Senate | age | 9 | 5.66 | -0.39 |
| Senate | born_in_state | 8 | 4.67 | -0.05 |
| Senate | defection | 9 | 4.79 | +0.23 |
| Senate | gender | 9 | 4.93 | +0.34 |
| Senate | ideology | 9 | 5.16 | -0.08 |
| Senate | incumbency | 23 | 7.66 | -0.02 |
| Senate | tenure | 9 | 5.38 | -0.12 |

## Complete queries and reproducibility

`2026-candidate-results.csv` retains every 2026 contest, including exclusions and exact reasons. `2026-model-fits.jsonl.gz` retains every fit and hold; `2026-model-terms.csv` contains coefficients, uncertainty and multiplicity adjustment. Full evidence, source receipts, contextual queries, fold membership, predictions and historical backtests are retained. The immutable private replay archive includes selected source bytes and code; source redistribution restrictions still apply.
