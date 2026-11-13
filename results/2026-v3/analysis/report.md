# Corrected 2026 candidate analysis (v3)

**This exploratory correction supersedes v2's interpretation; v2 remains immutable.**
All 470 federal contests are retained. Native provider update dates span 2026-11-12 to 2026-11-13; acquisition was November 13, 2026. These are provisional provider totals, not certified final returns.

## What changed

Mike McGuire is a California state senator, not a federal congressional incumbent. His positive native/FEC flag is overridden by the official general-election candidate list. Other positive flags require dated federal service evidence; House aliases are corroborated by the Clerk's November 3 membership snapshot. A vote earlier in the term alone does not establish incumbency at the election.

All fresh counts retain every candidate, prior v2 counts, exact source receipt, native clock, reporting percentage and exclusion reason. Material other-party shares of at least 10%, unqualified RCV rounds and Louisiana Senate stage remain held. Independents are never relabeled Democrats.

Party defection now uses only actual cast votes before November 3 from the 119th Congress: opposing strict party majorities, cast codes 1/6, at least 50 unity votes. Absence, abstention, paired/announced votes and President rows are excluded. Full-119th ideology includes post-election votes, so ideology remains a selective 118th-Congress (2023–24) sensitivity rather than a cutoff-current measure.

## Eligibility and primary associations

Effects below are D-minus-R margin points: **one share point equals two margin points**. Outcomes subtract qualified 2024 presidential share, on the actual 2026 House map or statewide for Senate. Models adjust for lean and lean squared; incumbency also controls R incumbency. Other traits compare verified D incumbents.

| Chamber | Retained | Eligible |
| --- | ---: | ---: |
| house | 435 | 405 |
| senate | 35 | 28 |

| Chamber / characteristic | N / states | Margin estimate | Envelope | Holm p | Status |
| --- | ---: | ---: | --- | ---: | --- |
| house / incumbency | 349 / 46 | +1.53 | [-0.77, +3.82] | 0.587 | supported_exploratory |
| house / ideology | 131 / 34 | -1.62 | [-3.23, -0.02] | 0.237 | supported_exploratory |
| house / defection | 164 / 36 | +0.17 | [-0.44, +0.77] | 1.000 | supported_exploratory |
| house / age | 162 / 36 | +0.61 | [-0.22, +1.44] | 0.587 | supported_exploratory |
| house / tenure | 162 / 36 | +1.24 | [+0.09, +2.39] | 0.213 | supported_exploratory |
| house / gender | 162 / 36 | -1.30 | [-5.56, +2.97] | 1.000 | supported_exploratory |
| senate / incumbency | 22 / 22 | +3.97 | [-1.93, +9.88] | 1.000 | diagnostic_only_low_support |
| senate / ideology | 9 / 9 | +1.83 | [-7.97, +11.62] | 1.000 | diagnostic_only_low_support |
| senate / defection | 9 / 9 | +0.46 | [-2.48, +3.39] | 1.000 | diagnostic_only_low_support |
| senate / age | 9 / 9 | +1.62 | [-5.58, +8.81] | 1.000 | diagnostic_only_low_support |
| senate / tenure | 9 / 9 | +3.32 | [-10.52, +17.15] | 1.000 | diagnostic_only_low_support |
| senate / gender | 9 / 9 | held | held | held | diagnostic |

Defection is per +1 share-percentage-point of party defection; ideology per +0.1 rightward, age/tenure per +10 years, gender recorded F versus M. Pointwise sensitivity envelopes use the larger CR1/CV3 focal standard error with t(G−1). They are not simultaneous intervals or a guarantee of reliable sparse inference. Six-test Holm families are separate by chamber/year. Headline support additionally requires at least 30 rows, ten states, leverage below 0.8 and complete deletions.

## Moderation: do not force a match to the supplied article

The user supplied Lakshya Jain's *Do moderates still have an electability advantage?* (November 12, 2026), discussing approximately three points of moderation advantage and Split Ticket WAR. Our transparent structural residuals are **not exact WAR**, do not identify candidate-versus-opponent causal effects, and cannot reproduce a proprietary data set merely by matching a headline number.

We fit the lean/lean-squared/D/R-incumbency baseline outside each candidate's state, then contrast Blue Dog and CPC residual means. Uncertainty re-estimates the entire baseline/held-state pipeline after each state deletion and takes a conservative envelope with conditional cluster errors. Complete training IDs and deletion estimates are exported. Joint group regressions are separate diagnostics.

| Year / baseline | Blue / CPC people | Margin contrast | Envelope | Status |
| --- | ---: | ---: | --- | --- |
| 2016 / lean_incumbency | 0 / 0 | held | held | diagnostic_only_sparse_group |
| 2018 / lean_incumbency | 0 / 0 | held | held | diagnostic_only_sparse_group |
| 2020 / lean_incumbency | 22 / 72 | +2.80 | [-0.77, +6.37] | supported_exploratory |
| 2022 / lean_incumbency | 12 / 73 | +3.02 | [-1.93, +7.97] | supported_exploratory |
| 2024 / lean_incumbency | 7 / 73 | +2.27 | [-2.68, +7.22] | diagnostic_only_sparse_group |
| 2026 / lean_incumbency | 8 / 65 | +8.17 | [-0.73, +17.07] | diagnostic_only_sparse_group |
| 2026 / lean_incumbency_same_swing_sample | 3 / 40 | +0.82 | [-11.52, +13.16] | diagnostic_only_sparse_group |
| 2026 / same_map_swing | 3 / 40 | +1.47 | [-5.96, +8.91] | diagnostic_only_sparse_group |

The full 2026 point estimate does not show a shrinking moderation advantage, but it is too sparse and uncertain to establish a precise advantage. The alternate same-map subset drops caucus members: compare its no-swing and swing-adjusted fits on identical samples, not the subset to the full sample as if only a control changed.

Blue Dog membership uses complete retrospective full-Congress rosters published November 10; CPC uses pre-election archived rosters (qualified from 2020 onward). Their vintages differ. Include losing nominees, exclude overlapping memberships, and do not interpret different annual cohorts/maps as a formal trend test. Each categorical group needs ten people/five states for promoted inference.

Justice Democrats has an archived pre-election candidate list. The Blue Dog PAC endorsement page is empty even in the pre-election archive; candidate-page listings with earlier CMS dates are an explicitly diagnostic **PAC-listed proxy**, not a complete archived endorsement roster or caucus membership. No headline PAC comparison.

## Benchmark, identity and prediction limits

All benchmark pairs use identical candidate IDs and map-qualified published presidential vintages. Missing changed-map cells remain missing. State effects, competitive seats, joint records, prior-term unity and third-party inclusions are downloadable exploratory sensitivity specifications, not model-selection proof.

All eligible nominees are retained in identity coverage, not just documented winners. Lean-only identity fits are no longer restricted to Census-compatible districts; adjusted fits still require compatible resident-population controls. Unknowns are not negative reference categories. Sparse religion/race groups remain diagnostics. Census does not collect religion, and no qualified 2026 district religion control or complete challenger identity panel has been manufactured.

Chronological replay uses prior-completed-Congress features consistently in all years, excluding target states and people. Absolute MAE and bias accompany paired lifts. Bias is observed minus predicted gap; positive means underprediction. Bootstrap intervals resample fixed state prediction pairs, not model refits; they omit fitting uncertainty and are labeled conditional.

| 2026 House feature | N | Baseline / feature MAE (share pp) | Baseline / feature bias | Paired MAE lift | Conditional interval |
| --- | ---: | ---: | ---: | ---: | --- |
| age | 162 | 6.64 / 6.66 | +6.60 / +6.62 | -0.019 | [-0.050, +0.011] |
| born_in_state | 134 | 7.12 / 6.89 | +7.08 / +6.87 | +0.233 | [+0.113, +0.387] |
| defection | 130 | 6.68 / 6.71 | +6.65 / +6.67 | -0.022 | [-0.048, +0.009] |
| gender | 162 | 6.64 / 6.71 | +6.60 / +6.68 | -0.068 | [-0.194, +0.023] |
| ideology | 131 | 6.71 / 6.68 | +6.67 / +6.64 | +0.030 | [+0.006, +0.062] |
| incumbency | 349 | 7.37 / 7.01 | +7.34 / +6.97 | +0.368 | [+0.128, +0.599] |
| tenure | 162 | 6.64 / 6.65 | +6.60 / +6.61 | -0.006 | [-0.084, +0.061] |

## Replay

The complete-query ZIP includes all normalized selected race/candidate and legislative queries, old full queries/features, every exclusion/model sample, residual/fold/deletion record, fitted outputs, plotted values, source hashes, code/tests, methods and lockfile. Restricted original workbooks/website bodies are not redistributed. Normalized inputs allow a network-disabled replay:

```sh
python -m which_candidate.corrected build --inputs results/2026-v3/inputs --output replay-analysis
python -m which_candidate.corrected_publication --inputs results/2026-v3/inputs --analysis replay-analysis --output replay-publication
```

Use the published manifest to compare every rebuilt analysis/figure/CSV hash. New count replacements or scientific specifications require a new version.
