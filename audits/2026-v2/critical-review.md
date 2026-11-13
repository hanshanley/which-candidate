# Critical review of the 2026-v2 candidate analysis

Reviewed November 13, 2026. **The current evidence does not establish which
types of Democratic nominees performed better in 2026.** The calculations
reproduce, but an actual incumbency error, selective coverage, weak support,
benchmark sensitivity and provisional counts limit the substantive conclusions.
The existing release should not support candidate-selection recommendations.

This is a critique, not a corrected release. Nothing in `results/2026/` or
`publication/2026-v2/` was overwritten. All sensitivities below are diagnostic,
post-publication checks, not new prespecified tests or replacement findings.
Effects and errors use Democratic **share percentage points**, not
D-minus-R margin points.

## What was independently checked

Run from the repository root:

```sh
.venv/bin/python audits/2026-v2/audit.py
```

The script uses its own design reconstruction and pseudoinverse-based
state-cluster covariance calculation, not the production fitting functions.
It reproduces coefficients, covariance matrices, p-values and pointwise intervals for
257 saved fits, counting repeated 2026 fits in the historical export. It checks
the annual primary and contextual Holm adjustments and all 1,030 CSV rows across the nine
figures, including held comparisons, scatter points and fitted-mean bands.
It verifies state/person-group separation in all 1,981 stored folds and earlier
training years in forward folds; 325 forward folds target 2026.

`audit-results.json` contains the diagnostics, exact deletion estimates,
sample counts, calibration metrics and SHA-256 receipts for all 120 frozen
analysis/publication files. The script confirms their bytes are unchanged.
Existing analysis and publication tests also pass: 39 tests.

These are internal consistency checks, not an independent recount, validation
of every candidate identity, or proof that historical source vintages were
actually available before each election.

## 1. Confirmed error: a state senator is a congressional incumbent in the data

Mike McGuire, the Democratic nominee in California's 1st District, is marked
`D_incumbent=True`, while opponent James Gallagher is also marked incumbent.
McGuire has no verified congressional service in the frozen feature record.
California's official November 3, 2026 candidate list, issued August 27, calls
him a California State Senator and Gallagher a United States Representative.
The House Clerk records Gallagher's June 10, 2026 oath.

The upstream FEC page itself labels McGuire an incumbent. The error is accepting
that field as verified federal incumbency, not incorrectly transcribing it.
`which_candidate/features.py:296` initializes the native flag; the unresolved
person returns at line 318 before dated-service verification can override it.
The main incumbency model and the geography figure accept this flag.

Correcting only this case, retaining the exact model and sample, changes the
House incumbency association from **+0.15 to +0.35 pp**. The sensitivity interval
is [-0.94, +1.64], so it does not create a significant result. Nevertheless,
the coding path needs correction and an audit of other unresolved native flags.
Other unresolved positive flags are not automatically errors.

Primary-source URLs, including the FEC record and official California list, are
preserved under `external_primary_sources` in the audit JSON.

## 2. Most comparisons do not represent all Democratic nominees

There are 408 eligible House and 29 eligible Senate nominees. The main House
ideology comparison includes **131** candidates; its Senate counterpart includes
**nine**. Apart from the incumbency model, the primary traits describe selected,
verified same-chamber incumbents rather than challengers and all nominees.

Among 163 verified eligible House incumbents, 32 lack ideology; **31 of those
32 have under two years of chamber service**. Missingness systematically removes
newer members rather than randomly thinning the sample. Their absence matters
for interpreting a study of successful candidate types.

The 2026 voting features describe the **118th Congress, 2023-2024**, not voting
in the 119th Congress during 2025-2026. This is a conservative completed-Congress
lag, not a coding error, but it does not answer which current-term voting
choices were associated with 2026 performance.

The background traits are separate regressions, not jointly adjusted estimates
that isolate age, tenure, gender and ideology from one another. State clustering
changes uncertainty, not omitted-variable bias. For example, adding state fixed
effects on the same House sample changes the gender coefficient from -0.19 to
+0.93 pp; this is a sensitivity, not a replacement significance claim.

## 3. Senate record estimates are weakly supported and badly scaled

Nine observations cannot sustain strong comparative claims. The ideology
coefficient changes from **+0.93 to -0.94 pp** when Oregon is omitted. The tenure
coefficient changes from **+1.60 to -1.50 pp** when Rhode Island is omitted.
Massachusetts has observation leverage above 0.93 in both fits.

The Senate defection model reports **-15.55 pp for a five-percentage-point
increase in defection**, but observed defection ranges only from **0.19% to
1.52%**. The reported contrast is approximately 3.8 times the entire observed
range. It is an algebraically valid rescaling of a linear slope, not an
observed five-point comparison.

Its published interval is already [-45.98, +14.87]. A delete-state CV3
jackknife sensitivity widens it to [-58.95, +27.84]. Passing an eight-cluster
minimum is not evidence that these fits support reliable substantive inference.

## 4. Identity contrasts have sparse groups and missing reference populations

The adjusted Muslim-versus-Protestant comparison has **three Muslim candidates
and 42 Protestants**, fitting 11 parameters to 45 observations. Its nominal
published interval [+0.06, +3.34] becomes **[-0.66, +4.06]** under the CV3
jackknife sensitivity. The original contrast already failed Holm correction;
there was never a multiplicity-adjusted Muslim advantage.

The Asian/Pacific Islander-versus-Black comparison has only **four versus 25**
candidates, with 11 parameters. Jill Tokuda's observation leverage is **0.9986**.
That is a warning about design support, not proof she alone determines the
focal coefficient.

The documented House incumbent coverage includes:

| Field | Relevant support or gap |
| --- | --- |
| Religion | 52 Catholic, 63 Protestant, 16 Jewish, three Muslim; no documented atheist or agnostic observations |
| Race | 37 Black, 11 combined Asian/Pacific Islander, two multiracial; 113 unknown and no documented White reference |
| Hispanic origin | 31 positive identifications, zero explicit non-Hispanic identifications, 132 unknown |

Compatible Census-map filtering further reduces support: the 115 documented
Catholic/Protestant observations become 72 in the comparable-map analysis.
The lean-only contextual variant deliberately uses this same filtered sample.

There is **no qualified 2026 district religious-composition adjustment**.
The Census controls describe residents' racial/Hispanic composition, not
religion or the electorate. The release discloses these gaps; they are not
evidence that identities have no association, nor a comprehensive identity ranking.

The CV3 calculations delete one whole state, refit the same design and use
`(G-1)/G * sum((beta_delete - beta_full)^2)` with t(G-1) intervals. They are a
sensitivity to leverage and clustering, not a definitive inferential repair.
The methodological source is MacKinnon, Nielsen and Webb, *Cluster-robust
inference: A guide to empirical practice* (DOI in the audit JSON).

## 5. Historical coefficient changes partly reflect the benchmark definition

Presidential election years use same-year presidential benchmarks; midterms use
lagged benchmarks. Different cohorts and maps add other differences. Historical
figures disclose this, but they must not be read as clean time trends in
candidate-trait advantages.

Using the **same 133 House candidates and specification in 2024**, changing only
to the qualified 2020 presidential benchmark on those districts changes:

| House 2024 trait | Same-year 2024 benchmark | Lagged 2020 benchmark |
| --- | ---: | ---: |
| Ideology, +0.1 rightward | -0.19 | +0.32 |
| Defection, +5 pp | -0.39 | +0.46 |

Both point estimates reverse sign without changing candidates. These are
diagnostic comparisons, not evidence for the opposite political conclusion.
Comparisons with 2026 need a harmonized lagged-benchmark sensitivity and formal
cross-year tests before claiming traits became more or less advantageous.

## 6. Third-party races are not ordinary two-party comparisons

In the Montana Senate snapshot, independents/other candidates receive
**39.53% of all votes**. Independent Seth Bodnar substantially outpolls Democrat
Alani Bankhead. Computing D/(D+R) is mathematically valid, but excludes the
principal non-Republican alternative and produces a Democratic presidential gap
of -19.62 pp.

Removing only Montana changes the Senate incumbency association from **+3.42
to +2.11 pp**, without establishing significance. Keep independent candidacies
explicit; add prespecified material-third-party sensitivities rather than
silently reclassifying Bodnar as a Democrat.

## 7. Predictive-lift bars hide a large cycle-calibration failure

The House ideology replay improves MAE by just **0.031 pp**, against a baseline
MAE of **6.44 pp** and mean underprediction of **6.38 pp**. Small improvement
does not make the baseline well calibrated.

For House incumbency, MAE improves by +0.377 pp, but retrospectively centering
errors makes MAE slightly worse: **2.623 to 2.663 pp**. Much of the apparent
improvement is therefore consistent with correcting average underprediction,
not better within-cycle differentiation.

The figure faithfully plots saved same-sample errors, but omits their absolute
scale and paired uncertainty. Samples differ across traits. Retrospective
centering cannot be presented as a pre-election forecasting fix.

## 8. The 2026 results are an early count snapshot, not final results

The frozen returns have **November 7-8, 2026** clocks. This audit on November 13
does not refresh or certify them. Counting progress can differ systematically
between districts, so historical certified-versus-2026 provisional comparisons
have another source of uncertainty. Regression intervals condition on the
stored totals; they do not incorporate outstanding-ballot uncertainty.

## What remains defensible, and what should change

It remains correct that **no primary 2026 comparison passes the prespecified
six-test-per-chamber Holm correction**. The main calculations and plotted data
reproduce, major missingness is documented, the main comparisons avoid inventing
White/non-Hispanic references, and the audited folds have no recorded state or
person-group overlap.

The safe conclusion is:

> In these selected, provisional 2026 samples, the specified models do not
> establish a dependable candidate-type advantage. Several estimates are too
> weakly supported or sensitive to support generalization to Democratic nominees.

That is not a finding that traits do not matter. The ASA p-value statement
specifically warns against treating a large p-value as evidence for the null.

Before a new publication version: correct and verify incumbency; acquire a new
dated returns snapshot; restrict headlines to observed cohorts; replace the
out-of-support Senate contrast with interpretable within-support units; show
group counts, leverage and robust sensitivities; harmonize historical benchmark
sensitivities; display absolute prediction errors and calibration; and keep
unsupported identity comparisons explicitly unresolved. Preserve v2 and issue a
new scientific/publication version rather than silently replacing its files.
