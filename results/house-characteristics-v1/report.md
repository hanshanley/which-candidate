# The full candidate-characteristics question

Exploratory successor `house-characteristics-v1`, specified after earlier results but before these fits. Earlier analyses are preserved, not refitted or overwritten.

## What the evidence supports

The inventory contains **1,284 candidate-contest records**, including **449 Democrats** and **405 qualified Democratic performance comparisons. Ten trait blocks support association estimates; five do not supply defensible contrasts.

Historical donor ideology and the **joint Democratic/Republican-incumbency block** clear the declared 15-block Holm correction. The latter is not a test of the Democratic-incumbent coefficient alone. No completed paired prediction comparison has a pointwise 95% improvement interval wholly above zero.

The performance outcome is Democratic two-party share minus the map-qualified presidential Democratic share, adjusted for district lean and lean squared. Coefficients below are vote-share percentage points, not margin points; multiply by two for D-minus-R margin. These are associations in selective cohorts, not causal effects of changing a nominee or individual-level voting behavior.

## Every declared block

| Block | Included candidates / states | Omnibus p | Holm p (15 blocks) | Paired MAE gain [95% interval] |
| --- | ---: | ---: | ---: | --- |
| Age | 147 / 36 | 0.336221 | 1.000000 | Diagnostic only (147/147 predictions) |
| Source-recorded gender | 141 / 35 | 0.307322 | 1.000000 | Diagnostic only (132/141 predictions) |
| Race | 0 / 0 | unavailable | 1.000000 | Unavailable: no qualified contrast |
| Ethnicity | 0 / 0 | unavailable | 1.000000 | Unavailable: no qualified contrast |
| Dated religion | 115 / 33 | 0.105297 | 1.000000 | -0.038 [-0.147, 0.072] |
| Education | 134 / 34 | 0.853599 | 1.000000 | -0.095 [-0.315, 0.125] |
| Professional family | 61 / 26 | 0.581584 | 1.000000 | -0.231 [-0.633, 0.170] |
| Prior elected office | 0 / 0 | unavailable | 1.000000 | Unavailable: no qualified contrast |
| Other government | 0 / 0 | unavailable | 1.000000 | Unavailable: no qualified contrast |
| Military service | 0 / 0 | unavailable | 1.000000 | Unavailable: no qualified contrast |
| Joint D/R incumbency | 349 / 46 | 0.000003 | 0.000049 | 0.076 [-0.019, 0.171] |
| House service | 140 / 35 | 0.085571 | 1.000000 | -0.026 [-0.109, 0.056] |
| Historical donor ideology | 151 / 39 | 0.000612 | 0.008573 | 0.022 [-0.103, 0.146] |
| Prior voting ideology | 115 / 32 | 0.016106 | 0.209373 | 0.065 [-0.123, 0.253] |
| Party defection | 140 / 35 | 0.258457 | 1.000000 | -0.020 [-0.199, 0.160] |

Unsupported race/ethnicity models have explicit positive identities but no complete reference classification. Prior elected office, other government work and military service lack reviewed negative cases. Missing history is not nonservice. Their unavailable hypotheses remain in the correction family with p=1.

## Estimated characteristic contrasts

| Block / term | Association, share pp [pointwise 95% CI] |
| --- | ---: |
| Age / `age` | 0.169 [-0.183, 0.521] |
| Source-recorded gender / `gender:M_vs_F` | 0.980 [-0.942, 2.903] |
| Dated religion / `religion:jewish_vs_catholic` | -2.088 [-4.172, -0.005] |
| Dated religion / `religion:protestant_vs_catholic` | -0.680 [-2.611, 1.251] |
| Education / `education:doctoral_or_professional_vs_bachelors` | 0.573 [-1.761, 2.907] |
| Education / `education:masters_vs_bachelors` | 0.032 [-1.143, 1.208] |
| Professional family / `profession:education_vs_business` | -1.009 [-3.408, 1.391] |
| Professional family / `profession:legal_vs_business` | 0.102 [-3.363, 3.566] |
| Joint D/R incumbency / `D_incumbent` | 0.763 [-0.308, 1.835] |
| Joint D/R incumbency / `R_incumbent` | -1.771 [-2.588, -0.954] |
| House service / `house_service` | 0.516 [-0.076, 1.108] |
| Historical donor ideology / `donor_ideology` | 1.771 [0.812, 2.731] |
| Prior voting ideology / `voting_ideology` | -0.933 [-1.681, -0.185] |
| Party defection / `defection_5pp` | 0.650 [-0.499, 1.798] |

Age and service increments are ten years; donor ideology is +0.5 rightward units; prior voting ideology is +0.1 rightward units; defection is +5 percentage points. Categorical terms state the reference explicitly. Male/female are literal source `gender` codes, not inferred sex or independently verified self-identifications. Education is the highest documented completed credential, not guaranteed maximum attainment. Profession is one recognized reported family, not proof of paid employment or an exhaustive career.

The positive donor-score association and negative prior-voting-score association are not interchangeable evidence for or against 'moderation': these are different constructs, increments and cohorts. Only donor ideology clears the 15-block correction. The separate Democratic-incumbent contrast includes zero; Republican incumbency is associated with lower Democratic performance. Neither establishes nominee-replacement effects.

## Actual Democratic coverage

| Trait | Qualified | Dated/reported | Uncertain | Unknown | Inapplicable |
| --- | ---: | ---: | ---: | ---: | ---: |
| Age | 191 | 70 | 0 | 188 | 0 |
| Source-recorded gender | 184 | 0 | 0 | 265 | 0 |
| Race | 0 | 58 | 0 | 391 | 0 |
| Ethnicity | 0 | 37 | 0 | 412 | 0 |
| Dated religion | 163 | 19 | 0 | 267 | 0 |
| Education | 173 | 170 | 104 | 2 | 0 |
| Professional family | 84 | 230 | 135 | 0 | 0 |
| Prior elected office | 0 | 203 | 50 | 196 | 0 |
| Other government | 0 | 1 | 263 | 185 | 0 |
| Military service | 17 | 18 | 45 | 369 | 0 |
| Federal incumbency | 410 | 0 | 0 | 39 | 0 |
| House service | 181 | 0 | 0 | 39 | 229 |
| Historical donor ideology | 192 | 18 | 0 | 239 | 0 |
| Prior voting ideology | 146 | 0 | 0 | 39 | 264 |
| Party defection | 180 | 0 | 0 | 40 | 229 |

The complete coverage CSV separately includes all 1,284 records and the 405 eligible Democratic nominees. Qualified field counts exceed some fitted samples: unknown D/R incumbency controls, outcome holds and sparse categories remain excluded. One observed degree or profession is not a complete biography. Education's two no-observation gaps remain Kristi Burke and Melissa McDonough; unreviewed extracted values are separately uncertain, not completed research.

## Research and provenance

Twelve new reviewed observations cover seven already-covered candidates: seven first-recorded trait fields, three newly qualified birthdays and two additional office/government observations. Newly covered people: **zero**. All 28,981 earlier observations and normalized collections are preserved; the current total is 28,993. Partial/secondary birth reports already held are not counted as newly discovered birth fields. The complete comparison is in `data/house-characteristics-baseline.json`.

This bounded follow-up reviewed 7 acquired sources or explicit rendered extracts from 8 exact-context leads. 3 use preserved public-index extracts of official Michigan biographies after direct PDF requests failed. Their hashes identify the retained extracts, **not original PDFs**; the failed requests remain in the receipts. Other receipts distinguish downloaded originals. A request failure or irrelevant search is never a negative trait value.

Three exact historical birthdays come from those official extracts. Four additional Democratic birth dates already held in official House Historian profiles receive explicit successor-only age decisions. Secondary incoming-member birthday claims stay descriptive. Religion retains literal historical questionnaire, third-party and self-description records; Jain heritage is not recoded as current membership. Navajo tribal identification and Mexican-/Indian-American self-descriptions are retained without inferred census race or negative ethnicity.

All 179 Democratic Directory education/career sections have recorded literal coding reviews. The source-defined Clerk veteran roster supplies positive service values only. Existing machine-extracted values remain visible with row-level references and uncertain coding; they are not silently promoted. All old descriptive `model_ready` flags stay false. Successor field eligibility is explicit and retrospective, never a prospective-model qualification.

An apparent adjacent-biography military section in Lois Frankel's normalized profile is withheld pending original-page review; it is not asserted as her service or proof of nonservice. A Sean McCann photographer/podcaster namesake is rejected. Parent-only religious descriptions and an endorser's Navajo identity are not candidate identities. Earlier rejection records remain unchanged.

The frozen initial audit predates code reconciliation: its race/ethnicity source counts overlap and it omitted some inherited extracted observations. It is retained as history, not used to claim discovery gains. The final coverage/table correct these definitions. Newly standardized analytical fields are not newly researched people.

## Selection, uncertainty and limitations

Each trait has its own complete-case cohort. Baseline and augmented predictions use identical candidates within each row, holding out entire states and purging the held-out people from training. Unknown incumbency is not zero. Legislative measures require verified incumbents; no voting record is not zero ideology or perfect unity. Incomplete folds/deletion fits have no predictive interval and are diagnostic only.

Selection summaries report state coverage, incumbency, district-lean bands, provisional leading status and every exclusion. Missingness is selective, particularly for winners and incumbents; no missing-at-random claim is made. Competitive-district, verified-incumbent, credential-coding and state-deletion sensitivities are downloadable. Sparse categories are not merged into reference groups. Categorical and source uncertainty limits scope even when a numerical association is estimable.

The source catalog resolves 4,007 URL/hash receipts. Inherited missing retrieval dates are explicitly unknown, not invented. Full supporting values and qualifications are in the candidate-by-trait CSV/JSONL and referenced normalized observation table. Remaining gaps have source-review dispositions; this was a bounded research pass, not an exhaustive search or universal biography completion.

## Files and replay

`coverage.csv`, `candidate-traits.csv`, `source-receipts.json`, `fits.csv`, `terms.csv`, `predictions.csv`, `folds.jsonl.gz`, `state-deletions.csv`, `selection.csv`, `selection-summary.csv`, `sensitivity.csv` and `remaining-gaps.csv` are complete queries, not metadata-only downloads. Both current ZIPs include this successor; the figure package contains the exact complete-query ZIP.

Replay with `python -m which_candidate.house_project --evidence-only`. This refreshes evidence and the successor without refitting earlier frozen analyses. Original historical HTML/PDF caches are not required. No website deployment is performed.
