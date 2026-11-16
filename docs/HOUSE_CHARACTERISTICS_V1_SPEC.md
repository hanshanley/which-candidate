# Full House characteristics successor: exploratory specification

This specification precedes the successor fits. It follows inspection of earlier
results and is **exploratory**, not a preregistration or a new confirmatory test.
The version is `house-characteristics-v1`. Earlier analyses and figure bytes are
preserved. The population is candidate-contest records, not verified unique people.

## Population, timing and outcome

Retain every named record and every contest hold in the existing inventory.
Analyze the selected Democratic nominee only where the frozen comparison is
eligible. Use Democratic two-party share minus the map-qualified presidential
Democratic two-party share, in percentage points. One share point equals two
D-minus-R margin points. These are provisional held returns, not certified totals.

The cutoff is November 3, 2026. Retrieval after that date does not itself make an
immutable birth fact or an explicitly dated earlier credential post-election.
Conversely, retrospective biography acquisition does not establish that an
undated, changeable claim held before the cutoff. Every promoted field requires
an explicit, reproducible eligibility decision; old descriptive flags stay false.

## Complete trait inventory and coding

Audit age, source-recorded gender, race, ethnicity, religion, education,
professional background, prior elected office, other government experience,
military service, federal incumbency, congressional service, historical donation
ideology, prior congressional voting ideology and current party unity separately.
Race and ethnicity are separate fields within the requested identity block.

Five exclusive audit statuses are qualified analytical value, dated/source-reported
observation needing qualification, conflicting/uncertain, unknown and structurally
inapplicable. A source receipt is not a reviewed analytical value.

* Age: completed years on Election Day from an exact, qualified birth date.
  A birth year alone supplies an interval, never an invented birthday.
* Gender: retain the crosswalk's literal `gender` and definition, not an inferred
  sex, pronoun-based classification or a claim of self-identification.
* Race/ethnicity: retain explicit positive classifications and their report type;
  allow multiple identities. An absent Historian listing is not White, non-Hispanic
  or a negative classification. Incomplete positive-only classifications do not
  supply the complete category set needed for a reference-category model.
* Religion: retain literal affiliation, publication/observation date and whether
  self-description, questionnaire or third-party report. A dated questionnaire
  model measures that historical reported affiliation, not verified current faith.
  Do not combine incompatible vintages or infer nonreligion from an empty field.
* Education: highest **documented completed** academic credential in a reviewed
  source, not a guarantee of highest actual attainment. Attendance and certificates
  are separate. A degree must be explicitly earned or use the official Directory's
  degree-list convention in a pre-cutoff publication. No degree from an employer,
  occupational title, school attendance or honorary award alone.
* Professional background: source-reported occupational family in the official
  Directory's factual career section, not degree-derived occupation or inferred
  paid employment. Mixed families are retained and withheld from the primary
  single-family comparison. Staff employment is not elected office.
* Prior elected office and other government experience: separate positive facts;
  missing history is not confirmed absence. Do not equate appointed office or
  staff employment with election. A positive-only inventory cannot support a
  served-versus-never-served contrast.
* Military: explicit service only, distinguishing reserves and civilian work.
  Missing military history is not nonservice. Require documented negative cases
  before a service-versus-nonservice comparison.
* Incumbency: use the frozen, dated service-qualified D/R flags; retain unknowns.
* Service: union actual House service intervals ending at the cutoff; overlapping
  intervals are counted once and breaks are excluded. This is House, not Senate,
  service. Restrict its performance comparison to verified Democratic incumbents.
* Donor ideology: exact-ID qualified historical DIME dynamic recipient score,
  through 2024 activity. It is not 2026 donations or voting ideology.
* Voting ideology: Congress-specific 118th-Congress Nokken-Poole first dimension,
  not full-career NOMINATE. Restrict to verified Democratic House incumbents.
* Unity: actual 119th-Congress party-unity roll calls before the election, with
  cast-vote denominator and last-vote date. New House members can have current
  unity but no prior-Congress ideology. No record is not zero or perfect unity.

The initial audit is frozen before new review/research. The reviewed table retains
both source availability and analytical eligibility, qualification reasons,
identity, receipt references and uncertainty. Descriptive acquisitions remain
model-ineligible unless this successor records a specific field-level decision.

## Primary testing family and support

Declare **15 primary trait/block hypotheses**, including unsupported hypotheses.
Unavailable hypotheses receive p=1 for the Holm family; do not shrink the family
after observing support or results. Age is per decade, House service per decade,
donor ideology per 0.5 rightward units, voting ideology per 0.1 rightward units,
and defection per five percentage points. Other supported traits are categorical
omnibus tests. Report all estimated terms and pointwise 95% state-cluster intervals.

Every model controls centered district presidential lean and lean squared.
Except for the incumbency block, include D/R incumbency in both baseline and
augmented models on exactly the same known-incumbency cohort. Drop cohort-constant
nuisance terms, never constant focal terms. Incumbency adds D and R flags jointly.
Never use an identity unknown or an absent positive classification as a reference.
Categorical levels require at least ten candidates in three states. Rare levels
are explicitly excluded, not silently merged into a substantive reference.
Require at least 30 candidates, ten states, full rank and acceptable conditioning.

Use cluster-sandwich OLS with finite-state correction and t intervals. For a
multi-term block use a cluster-robust Wald F test with state-cluster denominator
degrees of freedom. These are observational associations, not causal nominee
replacement effects. Collinearity and sparse support suppress results.

## Prediction, sensitivity and selection

Compare baseline and augmented predictions on identical complete-case candidates.
Hold out each entire state and purge all held-out people from training using the
existing stable person grouping, Bioguide/FEC identity and exact candidate key.
Require training rank/support for both models. Save all train/test IDs and people.
Do not silently remove failed folds. Predictive intervals require complete folds
and complete delete-one-state **full-pipeline** refits; otherwise label diagnostic.
Positive MAE gain favors the trait; pointwise predictive intervals are not another
multiplicity-adjusted discovery claim. Never compare gains across different
cohorts as a common-sample ranking.

For each block report included/excluded IDs, states, incumbency, lean bands and
provisional winning/losing status. Compare available and missing cohorts without
claiming missing-at-random. Report competitive 40-60 lean sensitivity and deletion
influence, and a stricter source/coding sensitivity where a genuine alternative
exists. Sparse-category and unresolved-coding exclusions remain explicit.
No all-trait joint complete-case model is primary. Unsupported fields remain
visible with reasons and bounded research dispositions, rather than forced fits.

## Release and replay

Create separate result and publication directories. Include code, input hashes,
source/review decisions, coverage, cohort decisions, predictions, folds, deletion
results, null/unavailable findings and runnable normalized-input replay in both
complete downloads. Preserve all prior normalized evidence and frozen results.
Validate tests, Ruff, changed browser views and network-disabled extracted replay.
Commit and push as Hans Hanley, verify remote main, and do not deploy the website.
