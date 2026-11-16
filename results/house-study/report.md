# Which Democratic House candidates did better in 2026?

## The answer

Across 405 qualified House comparisons, the evidence does not establish a universal winning candidate type. None of the six primary characteristic comparisons clears the six-test Holm correction. These estimates are not proof that candidate characteristics do not matter.

A practical check compares predictions for held-out states. Comparisons with a pointwise uncertainty interval wholly above zero improvement: **0/8**. A trait can have an in-sample association without providing reliable added predictive value for other candidates. The paired results below quantify that distinction rather than selecting a favorite candidate formula.

Historical donor ideology and prior voting ideology point in opposite directions even among the same candidates. A single moderate-versus-progressive label would hide that difference. These are observational associations, not the effect of replacing one nominee with another.

## The main comparisons

Outcome: congressional minus 2024 presidential Democratic two-party share, reported here in D-minus-R margin points (twice the share-point difference). All models adjust for district lean and lean squared. Incumbency also adjusts for Republican incumbency; the other five comparisons are among verified Democratic incumbents only.

| Comparison | Adjusted margin pp [95% pointwise interval] | Candidates | States | Holm p |
| --- | ---: | ---: | ---: | ---: |
| Democratic incumbent versus nonincumbent | +1.53 [-0.77, +3.82] | 349 | 46 | 0.587 |
| Prior voting ideology: +0.1 conservative | -1.62 [-3.23, -0.02] | 131 | 34 | 0.237 |
| Party defection: +1 percentage point | +0.17 [-0.44, +0.77] | 164 | 36 | 1.000 |
| Age: +10 years | +0.61 [-0.22, +1.44] | 162 | 36 | 0.587 |
| House service: +10 years | +1.24 [+0.09, +2.39] | 162 | 36 | 0.213 |
| Source-recorded female versus male | -1.30 [-5.56, +2.97] | 162 | 36 | 1.000 |

Intervals use the larger of state-cluster CR1 and delete-one-state CV3 standard errors, with t(G-1) critical values. They are pointwise, not simultaneous intervals. Full-rank state deletions and sample/leverage support gates apply. Competitive-seat and identical-sample 2020/2024 benchmark sensitivities are in `trait-fits.csv`.

## Why raw presidential gaps are not a candidate ranking

A midterm national environment can lift or depress many candidates at once. The raw gap also depends on the presidential candidate, constituency map and election-year differences. The separate held-out benchmark learns the 2026 gap-versus-lean curve from other states, excluding the held-out candidate's person identity as well. It intentionally does not adjust away incumbency or the traits under study.

The diagnostic covers **405 candidates in 47 state-held-out folds**. Presidential-baseline mean absolute error is 7.48 share points; the held-out benchmark's is 2.56, with signed bias +0.02. These are retrospective within-cycle errors, not a forward election forecast. Individual residuals are descriptive diagnostics, not causal candidate effects or Split Ticket WAR. 0 unconstrained expected shares fall outside 0-100%; these are explicitly flagged, not silently clipped.

## Ideology depends on what is measured

- Historical donor score, all qualified: +3.54 margin points per +0.5 conservative score units [95% interval +1.48, +5.60] (n=151).
- Historical donor score, current benchmark common sample: +3.22 margin points per +0.5 conservative score units [95% interval -0.24, +6.68] (n=88).
- Historical donor score, previous benchmark common sample: +0.81 margin points per +0.5 conservative score units [95% interval -3.47, +5.08] (n=88).

The same-incumbent measurement check holds the people and controls fixed:

| Measure and model | Adjusted margin pp [95% pointwise interval] | Candidates |
| --- | ---: | ---: |
| Donor score, +0.5 conservative, separate model | +3.92 [+1.62, +6.21] | 100 |
| Prior voting, +0.1 conservative, separate model | -2.56 [-4.34, -0.78] | 100 |
| Donor score, +0.5 conservative, joint model | +3.61 [+1.63, +5.59] | 100 |
| Prior voting, +0.1 conservative, joint model | -2.40 [-3.92, -0.89] | 100 |

Donor scores describe historical funding coalitions through 2024, not 2026 platforms. Prior voting ideology comes from the 118th Congress (2023-2024). Party defection uses dated 119th-Congress votes before November 3, 2026; absence or abstention is not an opposing vote. Newcomers do not receive zero federal ideology.

## Do candidate traits improve held-out predictions?

An association is not evidence that a trait improves predictions for other candidates. Each comparison below fits a baseline and an augmented model on exactly the same people, holds out an entire state and purges the held-out people's identities from training. Positive gain means lower mean absolute error after adding the trait, in **vote-share** points, not margin points. These are retrospective 2026 diagnostics.

| Added information | Paired candidates | Baseline MAE | With traits MAE | MAE gain [95% pointwise interval] |
| --- | ---: | ---: | ---: | ---: |
| D/R incumbency | 349/349 | 2.580 | 2.504 | +0.076 [-0.019, +0.171] |
| Prior voting ideology | 131/131 | 2.722 | 2.713 | +0.009 [-0.153, +0.172] |
| Party defection | 164/164 | 2.686 | 2.716 | -0.030 [-0.108, +0.049] |
| Age | 162/162 | 2.678 | 2.664 | +0.014 [-0.060, +0.088] |
| House service | 162/162 | 2.678 | 2.676 | +0.002 [-0.094, +0.098] |
| Source-recorded gender | 162/162 | 2.678 | 2.718 | -0.040 [-0.191, +0.110] |
| Historical donor ideology | 151/151 | 2.607 | 2.585 | +0.022 [-0.103, +0.146] |
| All five incumbent-record traits | 131/131 | 2.722 | 2.881 | -0.159 [-0.405, +0.087] |

Baselines adjust for lean and lean squared; both donor models also include known Democratic and Republican incumbency. The five individual record traits and their joint block apply only to verified Democratic incumbents. Different rows use different complete-case cohorts and must not be ranked as if they were the same population. The joint row uses all five record traits together; it is not a selected winning model.

Intervals refit **the entire paired cross-validation pipeline after deleting each state**, including both models and every remaining fold. They use the state-jackknife standard error and t(G-1) critical value. Incomplete folds/deletions suppress intervals. These intervals are exploratory and pointwise, not multiple-testing-adjusted discoveries. Neither positive gains nor retrospective calibration establish forward forecast skill or causal candidate quality. Exact predictions, fold membership and deletion diagnostics are downloadable.

The joint five-trait incumbent model changes held-out MAE from 2.722 to 2.881 share points among 131 paired candidates. That point comparison must be read with its interval and cohort restriction, not as a selected winning model.

## How selective are these comparisons?

| Information | Included out of all qualified comparisons | Coverage |
| --- | ---: | ---: |
| D/R incumbency | 349/405 | 86.2% |
| Prior voting ideology | 131/405 | 32.3% |
| Party defection | 164/405 | 40.5% |
| Age | 162/405 | 40.0% |
| House service | 162/405 | 40.0% |
| Source-recorded gender | 162/405 | 40.0% |
| Historical donor ideology | 151/405 | 37.3% |
| All five incumbent-record traits | 131/405 | 32.3% |

This is feature availability **and the model's population restriction**, not a claim that every excluded candidate lacks a biography. The complete `trait-selection.csv` splits included/excluded candidates by recorded incumbency, presidential lean and native provisional winner flag, and reports their mean lean and raw gap. Not flagged as a winner does not establish a loss. Selection can change the answer: incumbent-only voting associations cannot establish the best type of challenger.

## Who is in the project?

- All **1284 named candidates** in all 435 House districts are retained, including Republicans, other parties and losers.
- **30 contests** remain held from the main two-party comparison. Every hold is downloadable.
- The sitting roster is a different population: 435 voting seats, 433 named occupants and two vacancies in the November 3 Clerk snapshot retrieved November 13; six nonvoting seats are separate.
- The incoming roster is provisional, not certified. Continuing and returning members are separated from other reported winners.

The interactive report includes the candidate profile browser. Education, career, military and religion evidence is descriptive, with unknowns preserved. New biographies and unreviewed campaign extractions do not silently enter these models. Religion responses are dated observations, not verified current beliefs. Source files, coverage and gap ledgers are part of the complete download.
The election browser now exposes **29,686 acquired observations for 1156 candidates**, including losing candidates, rather than only listing unreviewed field names. Every observation retains its actual value, source kind/year, date, qualification and receipt. Unreviewed extractions are labeled, not presented as verified facts. Individual evidence tables and filtered profiles can both be downloaded.

The frozen missing-person research queue and its candidate-specific outcomes are downloadable in `research-dispositions.csv`. The browser shows each outcome and the fields still absent from the acquired evidence. `background-field-coverage.csv` covers all named candidates. An accepted field is not a complete biography; missing service or office is not a negative label. Search hits, empty questionnaires, failed requests and downloaded-but-unaccepted pages do not count as facts.
The targeted Democratic background pass covers all 449 records in the standardized trait download. It fills 42 education and 25 professional-history gaps, not newly covered people. 2 education gaps remain: Kristi Burke and Melissa McDonough. Attendance, degree completion, paid versus unpaid roles and conflicting source claims remain explicit. These retrospective fields do not change the frozen analyses.
The discovery correction retracts the adequacy of the earlier first-name-only searches. The separate 701-person repair queue includes already-covered people missing education or employment. Since its baseline, 240 people gained observations and 637 candidate-by-field gaps were filled. 128 people still lack observations; 88 still require adequate discovery. Individual correction outcomes are in `discovery-repair-dispositions.csv`. Documented attempts do not establish exhaustive research or complete biographies.

The voter-participation supplement adds **6,596 source-defined aggregate observations** and 23 House source-category/snapshot records across 4 districts. Statewide counts, regional early/mail rows and aggregate demographic cells retain their different source dates, definitions and receipts. Hawaii and Wyoming confirm pinned candidate counts; Maine's later RCV counts remain separate from the frozen provider snapshot. Unreported final categories remain unknown. These are not candidate backgrounds, district turnout, unique people or voter transfers. The local browser and `results/participation/` expose the context; no frozen outcome, analysis sample, trait input or biography-gap count changes.

## What remains unresolved

Counts are the pinned November 12-13 provisional provider snapshot, not certified outcomes. Most challenger/loser traits are less well documented than incumbents' traits. Education/career evidence cannot establish the association of those characteristics for all nominees while unreviewed fields remain ineligible. Race/ethnicity coverage does not provide a valid complete negative-reference group. District religious composition is unavailable. None of these absences means that a trait has no effect.

## Reproduce

Run `python -m which_candidate.house_project` from the installed project or extracted complete-query download. This rebuilds normalized analysis, candidate/member tables, this study, the current publication and complete downloads without acquiring new sources. Run `pytest -q`, `ruff check .` and `ruff format --check .` for validation. The website remains withdrawn.
