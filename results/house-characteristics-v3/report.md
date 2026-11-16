# New evidence for the full candidate-characteristics question

Exploratory **house-characteristics-v3** adds a bounded new-source acquisition batch to frozen V2. V1, V2 and earlier findings remain unchanged. The question is which Democratic House candidates outperform district partisanship, and how that performance relates to background, ideology, legislative behavior and incumbency.

All **1,284 candidate-contest records**, **449 Democrats**, **405 qualified performance comparisons** and all **fifteen primary testing-family blocks** remain. The counts are provisional November 12-13 returns, not certified final outcomes. No causal nominee-replacement effect is identified.

## Acquisition, qualification and analytical progress are different

- **5 new original document hashes**, including the CAWP methods codebook; **238 acquired factual observations**, of which **173** concern Democrats.
- New-source observations cover **119 candidates** and **238 candidate-by-trait fields**. Of these, **116 previously unknown fields** inform **83 candidates**; other observations add precision, coding support or corroboration rather than first coverage.
- The byte-identical held CAWP 2026 list is **not new acquisition**. It contributes 455 newly coded claims. **180 existing-only fields** newly qualify factually; this excludes cells also receiving new-source evidence.
- **294 additional analytical fields** (all parties), **185 Democratic fields**. Unresolved Democratic federal incumbency changes from **37 to 24**. These control resolutions come from newly coded held evidence, not new service histories.

The exact changes, including incumbent/challenger composition, are in `acquisition-field-changes.csv` and `coverage-by-incumbency.csv`. Both existing and newly acquired observations retain literal claims, historical dates, retrieval clocks, hashes and exact candidate/contest identities. **7 candidates** gain their first factually qualified trait; this is not the same as first-ever biography acquisition or candidates newly informed on a specific trait.

### Sources and factual limits

Center for American Women and Politics, Eagleton Institute of Politics, Rutgers University-New Brunswick. CAWP Congressional Women Candidates Database, 1990-2024 workbook; accessed November 16, 2026. Noncommercial research use. Race codes are source classifications: self-identification or CAWP multiple-source verification, not necessarily direct self-identification. Multiple codes are retained; unavailable is unknown. Historical classification is not a verified current identity.

New CAWP historical matches require exact 2024 full name, state, party, House office and district. Name-only matches across changed districts are held rather than transferred automatically. Explicit W and B are positive source classifications, not reference groups manufactured from missing minority fields. H is Hispanic/Latina, not a racial category or a non-Hispanic complement. Multi-codes and unknowns remain.

With Honor supplies explicit named branch/veteran labels, not inferred service from endorsement. CFE supplies actual candidate biographies and literal religious descriptions. Its religious allies are not coded nonreligious; scientist is not a religious affiliation. Current pages contain post-election updates, so these new religious/service reports do not silently become pre-election model inputs. Fred Wellman's Catholic upbringing and reported current nonreligion remain distinct.

The Minnesota legislative-library biography supplies Matt Little's explicit birthday, source-recorded Male field, completed 2014 JD, historical attorney occupation, elected mayoral history and state advisory membership. Advisory work is not presumed paid government employment. Blank religion and None Reported minority classifications remain unknown. Durational career evidence is qualified for historical profession only when it necessarily precedes Election Day; no exact job-start date is invented.

## Coverage across the complete Democratic inventory

| Trait | V2 analytical | V3 factual qualified | V3 analytical | Reported | Uncertain | Unknown | Inapplicable |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Age | 191 | 258 | 192 | 3 | 0 | 188 | 0 |
| Source-recorded gender | 184 | 296 | 296 | 0 | 0 | 153 | 0 |
| Race | 0 | 102 | 54 | 0 | 0 | 347 | 0 |
| Ethnicity | 0 | 39 | 0 | 0 | 0 | 410 | 0 |
| Dated religion | 163 | 177 | 163 | 0 | 0 | 272 | 0 |
| Education | 182 | 201 | 183 | 141 | 105 | 2 | 0 |
| Professional family | 85 | 122 | 89 | 198 | 129 | 0 | 0 |
| Prior elected office | 0 | 14 | 0 | 196 | 47 | 192 | 0 |
| Other government | 0 | 12 | 0 | 1 | 258 | 178 | 0 |
| Military service | 17 | 27 | 17 | 16 | 38 | 368 | 0 |
| Federal incumbency | 412 | 425 | 425 | 0 | 0 | 24 | 0 |
| House service | 183 | 183 | 183 | 0 | 0 | 24 | 242 |
| Historical donor ideology | 192 | 192 | 192 | 18 | 0 | 239 | 0 |
| Prior voting ideology | 148 | 148 | 148 | 0 | 0 | 24 | 277 |
| Party defection | 182 | 182 | 182 | 0 | 0 | 25 | 242 |

Factual qualification and analytical eligibility are separate. A completed attainment category, dated occupation or explicit identity may qualify without supporting a statistical contrast. All-cohort and eligible-405 coverage, group composition, selection and unresolved fields are available in complete tables.

## All fifteen associations and matched-sample predictions

| Block | Association n / states | Holm p (15) | Restricted predictive n / full n | MAE gain [95% interval], share pp |
| --- | ---: | ---: | ---: | --- |
| Age | 151 / 36 | 1.000000 | 149 / 151 | -0.007 [-0.090, 0.076] |
| Source-recorded gender | 242 / 43 | 1.000000 | 242 / 242 | -0.020 [-0.070, 0.031] |
| Race | 45 / 24 | 1.000000 | 41 / 45 | -0.014 [-0.109, 0.081] |
| Ethnicity | 0 / 0 | 1.000000 | unavailable | no supported contrast |
| Dated religion | 118 / 33 | 0.377252 | 118 / 118 | -0.044 [-0.179, 0.091] |
| Education | 144 / 34 | 1.000000 | 142 / 144 | -0.084 [-0.264, 0.096] |
| Professional family | 66 / 27 | 1.000000 | 62 / 66 | -0.230 [-0.618, 0.157] |
| Prior elected office | 0 / 0 | 1.000000 | unavailable | no supported contrast |
| Other government | 0 / 0 | 1.000000 | unavailable | no supported contrast |
| Military service | 0 / 0 | 1.000000 | unavailable | no supported contrast |
| Joint D/R incumbency | 362 / 47 | 0.000145 | 362 / 362 | 0.080 [-0.014, 0.174] |
| House service | 143 / 35 | 0.434517 | 143 / 143 | -0.022 [-0.112, 0.068] |
| Historical donor ideology | 152 / 39 | 0.010674 | 152 / 152 | 0.022 [-0.107, 0.151] |
| Prior voting ideology | 117 / 32 | 0.268448 | 117 / 117 | 0.056 [-0.142, 0.254] |
| Party defection | 143 / 35 | 1.000000 | 143 / 143 | -0.038 [-0.156, 0.081] |

Blocks clearing the fixed fifteen-block Holm correction: Joint D/R incumbency, Historical donor ideology.

The newly evaluated race question compares explicitly Black versus White **historical CAWP women candidates**, not all Democratic racial groups and not a biological or causal race effect. Black/White overlap is not forced into one group; other identities remain factual observations. This source-selected, predominantly repeated-candidate sample has strong selection limitations. Ethnicity still lacks a defensible negative/reference classification. Office, government and military histories still lack a supported service-versus-nonservice contrast. Any unavailable comparison remains in the testing family with p=1.

### Estimated focal terms

| Block / term | Association, share pp [pointwise 95% CI] |
| --- | ---: |
| Age / `age` | 0.298 [-0.078, 0.675] |
| Source-recorded gender / `gender:M_vs_F` | 0.898 [-0.902, 2.697] |
| Race / `race:White_vs_Black` | -0.061 [-1.246, 1.125] |
| Dated religion / `religion:jewish_vs_catholic` | -2.332 [-4.137, -0.526] |
| Dated religion / `religion:protestant_vs_catholic` | -0.909 [-2.874, 1.056] |
| Education / `education:doctoral_or_professional_vs_bachelors` | 0.440 [-1.819, 2.698] |
| Education / `education:masters_vs_bachelors` | -0.126 [-1.126, 0.874] |
| Professional family / `profession:education_vs_business` | -1.053 [-3.484, 1.377] |
| Professional family / `profession:legal_vs_business` | 0.202 [-3.240, 3.645] |
| Joint D/R incumbency / `D_incumbent` | 1.046 [-0.069, 2.160] |
| Joint D/R incumbency / `R_incumbent` | -1.669 [-2.581, -0.756] |
| House service / `house_service` | 0.603 [0.031, 1.175] |
| Historical donor ideology / `donor_ideology` | 1.855 [0.829, 2.881] |
| Prior voting ideology / `voting_ideology` | -0.921 [-1.692, -0.151] |
| Party defection / `defection_5pp` | 0.431 [-0.758, 1.620] |

One share point equals two D-minus-R margin points. Age and service increments are ten years; donor ideology is +0.5 rightward, voting ideology +0.1 rightward, and defection +5 points. The joint D/R-incumbency block is not the Democratic incumbent coefficient alone. Donation ideology, congressional voting ideology and campaign positions remain distinct. A selective donor association is not a universal moderation advantage.

## Validation, selection and remaining gaps

V3 reuses V2's state-held-out/person-purged validation, training-only nuisance reparameterization, rank/conditioning gates and full-pipeline state-deletion uncertainty. Baseline and augmented predictions always use identical candidates. Restricted validation retains only joint D/R-incumbency strata represented in at least three states; it never validates the full association population by implication. Full-population fold failures remain exported. No unsupported interval or unseen test stratum is waived.

The separate whole-interval age-band sensitivity uses 200 candidates in 40 states. Birth-year intervals must fit wholly within a band; there is no imputed exact birthday or midpoint. Competitive, incumbent-only, coding and state-deletion sensitivities remain. Do not compare different complete-case cohorts as if they were identical candidates.

Source classification conflicts retained: **0**. Rejected cross-contest historical name matches: **5**. These are context holds, not claims that the names necessarily identify different people. Prior rejected namesakes and conflicting credentials remain preserved. CandiData added no unknown Democratic gender among exact FEC matches; uncertain demographic coding was not promoted. Future Caucus aggregate results were not counted as candidate microdata or purchased access.

This bounded batch does not finish universal trait research. Challenger evidence remains selectively missing; most age/religion/career fields still need qualified source evidence or timing, and remaining incumbent holds require official person/service bridges. Explicit positive military or office history is not confirmed nonservice for anyone else. Retrospectively retrieved evidence is never marked prospectively model-ready.

## Complete data and local replay

The V3 table retains lossless 1-based `baseline_trait_row` references into frozen V1 evidence, plus all V2 review and new V3 source facts. Both complete downloads contain the full normalized inputs, original receipt metadata, all fifteen-trait tables, selection/fold/deletion ledgers, code and historical outputs. The figure bundle embeds the exact complete-query ZIP. No metadata-only replacement.

Replay with `python -m which_candidate.house_project --evidence-only`. The V3 specification and acquisition journal document eligibility decisions. V1/V2 outputs remain byte-protected. Local report/browser only: **no website deployment**.
