# Evidence qualification and honest predictive validation

Exploratory `house-characteristics-v2` follows the completed source-family review and a written pre-fit amendment. V1 and earlier outputs remain frozen.

Retained: **1,284 candidate-contest records**, **449 Democrats**, **405 qualified performance comparisons and all **15 testing-family blocks**. Outcome holds and unknown opponent incumbency are unchanged.

## Measured evidence progress

Newly acquired observations: **0**; newly covered people: **0**. This release reviews held evidence, rather than counting a repeated education/career collection as discovery. Newly factually qualified existing fields: **258** (all parties); newly analytically eligible fields: **18**. The complete identity-level changes are in `qualification-changes.csv`.

Factual qualification records what an explicit source supports, not independent verification. An education record may support attendance without identifying completed attainment. A profession need not establish paid work. Positive identities and positive service histories do not by themselves establish reference groups or estimable contrasts.

## Democratic coverage: factual versus analytical

| Trait | V1 qualified | V2 factual qualified | V2 analytical field | Reported | Uncertain | Unknown | Inapplicable |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Age | 191 | 258 | 191 | 3 | 0 | 188 | 0 |
| Source-recorded gender | 184 | 184 | 184 | 0 | 0 | 265 | 0 |
| Race | 0 | 58 | 0 | 0 | 0 | 391 | 0 |
| Ethnicity | 0 | 37 | 0 | 0 | 0 | 412 | 0 |
| Dated religion | 163 | 167 | 163 | 0 | 0 | 282 | 0 |
| Education records (attainment separate) | 173 | 199 | 182 | 143 | 105 | 2 | 0 |
| Professional family | 84 | 118 | 85 | 201 | 130 | 0 | 0 |
| Prior elected office | 0 | 13 | 0 | 196 | 47 | 193 | 0 |
| Other government | 0 | 11 | 0 | 1 | 258 | 179 | 0 |
| Military service | 17 | 17 | 17 | 18 | 45 | 369 | 0 |
| Federal incumbency | 410 | 412 | 412 | 0 | 0 | 37 | 0 |
| House service | 181 | 183 | 183 | 0 | 0 | 37 | 229 |
| Historical donor ideology | 192 | 192 | 192 | 18 | 0 | 239 | 0 |
| Prior voting ideology | 146 | 148 | 148 | 0 | 0 | 37 | 264 |
| Party defection | 180 | 182 | 182 | 0 | 0 | 38 | 229 |

The statuses describe factual/coding review; analytical eligibility is a separate column. Exact age and bounded birth-year reports are not interchangeable. The main age model uses exact years; the separate age-band sensitivity includes a birth-year interval only when the whole interval lies within one band. No midpoint or birthday is imputed. Historical religious labels stay dated, while fifteen questionnaire refusals/nonresponses are unknown affiliation, not nonreligion.

Source-family review includes held institutional biographies, prior-office pages, candidate-supplied questionnaires, ballot designations and endorsing-organization accounts, plus the eleven official candidate profiles. Each selected profile has an exact identity and hash in the review seal. Other campaign/directory profiles are not blanket-approved. Claim dates and coding, not campaign/official status alone, determine analytical eligibility. Retrospective observations remain prospectively ineligible.

The existing exact FEC/person/service bridges resolve Bill Keating and Tom Suozzi as federal incumbents in a v2-only overlay. The other 37 Democratic holds remain. Keating's unknown Republican-incumbency control is not fabricated. Years of service and available pre-election voting measures follow the exact person bridge.

## Every declared hypothesis and matched prediction comparison

| Block | Association n / states | Holm p (15) | Restricted predictive n / full n | MAE gain [95% interval], share pp |
| --- | ---: | ---: | ---: | --- |
| Age | 148 / 36 | 1.000000 | 146 / 148 | -0.003 [-0.049, 0.043] |
| Source-recorded gender | 142 / 35 | 1.000000 | 141 / 142 | -0.033 [-0.161, 0.095] |
| Race | 0 / 0 | 1.000000 | unavailable | no supported contrast |
| Ethnicity | 0 / 0 | 1.000000 | unavailable | no supported contrast |
| Dated religion | 116 / 33 | 1.000000 | 116 / 116 | -0.042 [-0.153, 0.068] |
| Education | 142 / 34 | 1.000000 | 141 / 142 | -0.080 [-0.258, 0.099] |
| Professional family | 63 / 27 | 1.000000 | 62 / 63 | -0.230 [-0.618, 0.157] |
| Prior elected office | 0 / 0 | 1.000000 | unavailable | no supported contrast |
| Other government | 0 / 0 | 1.000000 | unavailable | no supported contrast |
| Military service | 0 / 0 | 1.000000 | unavailable | no supported contrast |
| Joint D/R incumbency | 350 / 46 | 0.000037 | 350 / 350 | 0.073 [-0.019, 0.165] |
| House service | 141 / 35 | 1.000000 | 141 / 141 | -0.027 [-0.109, 0.055] |
| Historical donor ideology | 151 / 39 | 0.008573 | 151 / 151 | 0.022 [-0.103, 0.146] |
| Prior voting ideology | 116 / 32 | 0.198136 | 116 / 116 | 0.068 [-0.118, 0.255] |
| Party defection | 141 / 35 | 1.000000 | 141 / 141 | -0.027 [-0.213, 0.159] |

Blocks clearing the declared Holm correction: Joint D/R incumbency, Historical donor ideology. Completed predictive comparisons whose pointwise improvement interval is wholly positive: none.

## What changed in validation

V1 age produced 147/147 predictions, but deleting Michigan then holding out Virginia (or the reverse) left no Republican-incumbent training cases. V1 gender produced 132/141 predictions: holding out Texas removed its sole nonincumbent, Colin Allred. These were genuine unsupported designs, not proof of no trait effect or a reason to relax rank checks.

V2 retains full-cohort diagnostics in `full-population-folds.jsonl.gz`. Its separate predictive population contains only joint D/R-incumbency strata represented in at least three states, selected without outcomes and frozen before deletion refits. Both models use exactly the same candidates and hold out states and repeated people. Exactly redundant nuisance terms are reparameterized using training data only, and the same relationship must hold in every test row. This also repairs the complementary D/R-incumbent nuisance columns exposed in education after the unsupported open-seat stratum is removed. An unseen test stratum is still rejected. Focal rank and conditioning checks remain enforced.

The displayed intervals therefore validate a **narrower supported population**, not the full association cohort. Full-population intervals remain unavailable where support is inadequate. The prediction/deletion ledgers identify every excluded ID. Intervals require every supported-population fold and every full-pipeline state deletion to succeed. They are pointwise exploratory intervals, not a second multiplicity-adjusted discovery family.

### Bounded-age and coding sensitivities

The separately labelled age-band sensitivity uses 197 candidates in 40 states; its exploratory omnibus p is 0.3232. The bands are under 40, 40-59 and 60 or older. Entire intervals must fit one band. This is not the primary exact-age test and is not compared with its different sample as if the two were identical. Education/profession sensitivities exclude newly qualified analytical values while retaining the v2 service controls; competitive-lean and incumbent-only fits are also retained in `sensitivity.csv`.

## Estimated terms and interpretation

| Block / term | Association, share pp [pointwise 95% CI] |
| --- | ---: |
| Age / `age` | 0.159 [-0.197, 0.515] |
| Source-recorded gender / `gender:M_vs_F` | 0.956 [-0.972, 2.884] |
| Dated religion / `religion:jewish_vs_catholic` | -2.031 [-4.124, 0.062] |
| Dated religion / `religion:protestant_vs_catholic` | -0.628 [-2.585, 1.329] |
| Education / `education:doctoral_or_professional_vs_bachelors` | 0.322 [-1.875, 2.519] |
| Education / `education:masters_vs_bachelors` | -0.128 [-1.125, 0.868] |
| Professional family / `profession:education_vs_business` | -0.991 [-3.388, 1.406] |
| Professional family / `profession:legal_vs_business` | 0.052 [-3.392, 3.497] |
| Joint D/R incumbency / `D_incumbent` | 0.743 [-0.319, 1.806] |
| Joint D/R incumbency / `R_incumbent` | -1.764 [-2.577, -0.952] |
| House service / `house_service` | 0.516 [-0.074, 1.106] |
| Historical donor ideology / `donor_ideology` | 1.771 [0.812, 2.731] |
| Prior voting ideology / `voting_ideology` | -0.942 [-1.691, -0.194] |
| Party defection / `defection_5pp` | 0.632 [-0.522, 1.785] |

Primary age/service increments are ten years; donor ideology is +0.5 rightward, prior voting ideology +0.1 rightward, and defection +5 percentage points. The joint D/R-incumbency test is not the Democratic-incumbent coefficient alone. Donor and voting ideology are distinct constructs in different selective samples; neither is a universal moderation score or a causal nominee-replacement effect.

Race, ethnicity, military, elected-office and other-government comparisons remain unavailable without complete reference classifications or explicit negative histories. They remain in the testing family with p=1. There are no newly estimable trait blocks from merely qualifying positive evidence. Unknowns are not reference categories.

## Remaining limitations and research dispositions

Undated or changeable employment stays descriptive. Attendance, unspecified degrees and Becky Stille's conflicting attainment accounts remain unresolved for completed attainment. Jen Mazzuckelli's subject-wording discrepancy is retained while agreeing completed degree levels can be coded. Source-reported gender preserves its definition, not inferred sex or independently verified self-identification.

No reviewed held questionnaire supplied a reliable never-served reference for military/government/elected history. Ray Pooley's nonresponse is not nonservice. The Opelika Lee McInnis employee namesake and partisan Ace Parsi no-office claim are rejected; AmeriCorps is not military service. Earlier attribution/religious-parent/endorser rejections remain preserved. A bounded external discovery pass found the Mental Health Now candidate-signature index, but direct requests failed; it was not ingested or counted as acquired evidence. No universal research-completion claim.

Missingness remains selective. `selection.csv`, `sensitivity.csv`, the full-cohort folds, qualification changes and remaining gaps disclose each cohort and exclusion. Models use the held provisional two-party presidential-share gap, lean and lean squared, and known D/R incumbency. One share point is two D-minus-R margin points. Do not compare different trait cohorts as though they were identical candidates.

## Complete data and offline replay

The v2 table uses `baseline_trait_row` as a 1-based reference into the immutable v1 JSONL for unchanged literals/receipts. Both full tables and the held normalized inputs are included in both complete downloads; the figure ZIP embeds the exact complete-query ZIP. This is lossless relational storage, not a metadata-only download. The browser resolves the full literal/source records locally.

Replay with `python -m which_candidate.house_project --evidence-only`. It refreshes v2 and current evidence without rebuilding v1 or earlier analyses. `HOUSE_CHARACTERISTICS_V2_SPEC.md` is the pre-fit amendment. No website deployment.
