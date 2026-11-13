# Frozen analysis specification

This specification was written before calculating characteristic coefficients.
Historical development outcomes are 2016, 2018, 2020 and 2022. The 2024 cycle
is a locked, historical validation slice, not a prospectively blind experiment.
No 2026 provider snapshot enters estimation.

## Population and benchmarks

Retain every congressional contest and every D/R candidate feature query,
including exclusions and unmatched people. The main sample requires one named
nominee from each major party, usable counts and a qualified constituency
benchmark. Senate uses FEC state presidential returns. House uses Daily Kos
Elections/The Downballot's explicitly election-map-specific calculated district
results, not certified district presidential compilations or an independent
boundary audit. Use 2016 presidential results for 2016/2018, 2020 for 2020/2022,
and 2024 for validation. Published 2016/2018 percentage rounding remains.

Do not treat incumbent/party columns in district benchmark workbooks as
historical features. Source status, map year and exact rows accompany benchmarks.
2024 House counts are the frozen official-Clerk factual queries. New 2024
Senate counts are independently parsed from the complete held Clerk report.
Special elections, unresolved runoff/RCV stages, independents and ambiguous
accounting remain visible but outside the main D/R sample.

## Features

Use FEC candidate IDs plus name/state consistency checks to crosswalk legislators.
For 2024, first anchor return names to the FEC general-ballot roster by
state/chamber/district; its IDs and incumbent flags cover challengers and losers.
All ambiguous joins remain unresolved. A unique source-documented name match
also requires state/chamber and dated-service anchors; it is labeled separately
when the FEC ID is missing from the crosswalk. First-name prefix variants require
at least three matching letters and uniqueness within the anchored scope.
Native incumbent flags are explicitly distinguished from dated-service checks.
For resolved people, dated same-chamber service takes precedence; disagreements
are retained in full, not erased. Unresolved people retain native source flags.
Today's membership cannot establish historical incumbency.

Legislative features use the previous completed Congress: 113, 114, 115, 116 and
117 respectively for elections 2016 through 2024. Nokken-Poole first dimension
is Congress-specific; higher means rightward. These are current retrospective
estimates of a strictly prior-period voting record, not archived prospective
score vintages. Never substitute career NOMINATE. Party defection is one minus
the published party-unity fraction, requiring at least 50 party-unity votes.
It is not overall bipartisanship, attendance or an issue-voting score.

Incumbency comparisons use all otherwise eligible nominees with available
D/R incumbent flags. Ideology, defection, age, tenure and source-recorded gender
comparisons are restricted to verified same-chamber Democratic incumbents.
This intentionally narrow population avoids describing every challenger using
the biographical coverage of eventual winners. It does not answer which
untried challengers would win. No missing legislative score becomes zero.
Age and service duration are measured before the election; gender is the
crosswalk's recorded field, not a verified self-identification panel.
In the original six-feature phase, race/ethnicity, religion, birth-state,
military, education and occupation remain unmeasured without qualified evidence.
The later, explicitly supplemental directory investigation below adds qualified
birth-state and literal religion fields. Do not infer unsupported traits.

## Estimation

Fit House and Senate separately with equal weight per contest. The outcome is
Democratic two-party share minus the presidential two-party share, in percentage
points. A one-share-point difference equals two D-minus-R margin points.

The no-characteristics expectation is OLS gap on linear/quadratic presidential
lean and cycle indicators. Retrospective cross-fitted expectations hold out
every observation in the target state across all cycles, and also purge any
identified repeated target person. They may use other states in the same cycle;
they are therefore not forecasts. Save complete fold membership and predictions.

Main adjusted associations are separate OLS models of raw gap on the same
lean/cycle controls plus the focal feature. Incumbency includes both D and R
incumbent indicators. The incumbent-record models additionally compare:

- +0.1 Nokken-Poole rightward movement;
- +5 percentage points of party defection;
- +10 years of age;
- +10 years of same-chamber service;
- source-recorded F versus M gender, without inferring other categories.

Prespecify ideology/defection joint adjustment, an incumbent ideology-by-lean
interaction, competitive constituencies (presidential D share 40–60%),
single-cycle estimates, and linear-only lean as sensitivities. These are
observational associations, not causal nominee-replacement effects.

Use state-clustered small-sample-corrected sandwich uncertainty with Student-t
reference degrees of freedom equal to state clusters minus one. State clustering
captures repeated constituencies and most repeated people; explicitly audit
cross-state repeated identities. Report sample sizes, cluster counts, rank and
condition numbers. Do not promote rank-deficient or fewer-than-eight-cluster
fits. Pointwise 95% intervals are not multiplicity-corrected; report
Holm-adjusted p-values across the six primary focal-feature tests per chamber.
No selection of a favorite model based on validation scores.

## Data-audit corrections

The first provisional join audit found modern Voteview party codes serialized
as `100.0` versus historical `100`; both are validated as integer codes before
matching. It also found that FEC `(I)` markers can disagree with dated service,
including House members seeking Senate seats and newly elected members.
These are measurement/join corrections, not outcome-selected model changes.
The originally specified formulas, development years, validation slice,
feature units and sensitivity models are unchanged.

Explicit regular `NN-FULLTERM` House labels join the corresponding numeric
election-map district. Preserve the native label and scope. No other suffix,
especially an unexpired-term election on an older map, is stripped.

## Supplemental biography investigation

Before extracting biography fields or inspecting their coefficients, add two
explicitly supplemental (not members of the six-test confirmatory family)
comparisons among verified Democratic incumbents: born in the represented state
versus explicitly born elsewhere, and explicitly reported Catholic religion
versus other explicitly reported religion. Use only a complete official
Congressional Directory edition published before each election, and retain
the member-name anchor, page, publication date and exact short field evidence.
Directory biographies are furnished or authorized by members; only a literal
`religion:` field qualifies, never church membership outside that explicit field,
a name or ethnicity.
Unreported religion is unknown, not nonreligion or a control-group member.
Birth-state requires an unambiguous explicit state or country in the birth
clause; residence is never substituted. Preserve exact religious wording.
These analyses have additional optional-disclosure selection and do not claim
coverage of challengers. Report all missingness and do not promote sparse fits.

The directory parser retains the complete 50-state biography section, requires
member-office authorization language and all 50 state anchors, and preserves
short literal birth/religion clauses rather than unnecessary family details.
Accented names, mixed-case surnames, typographic apostrophes, explicit roster
full-name aliases and `Dr.` prefixes are documented-name normalization, not
outcome-based matching. Contradictory Steven/Stephen Corvi names in the 2024
Rhode Island sources remain unmatched rather than guessed. Born-in-state
comparisons require an explicit comma-delimited state or country; ambiguous
Georgia and cities with omitted states remain unknown. No residence inference.

## Validation and interpretation

Run chronological, state-held-out predictions for 2018, 2020, 2022 and the locked
2024 slice. Each training set uses only earlier elections, excludes the entire
target state and purges repeated target people. The forecast environment control
is presidential-versus-midterm status, not the held-out cycle's observed vote.
Report absolute MAE/RMSE and the improvement from adding candidate features to
the identical no-feature model on the identical test rows. Also report
within-cycle-centered error, clearly labeled as retrospective, not a forecast.
Unknown national environments can shift all predictions.

Retrospective state-held-out performance and forward-cycle prediction are
different tests. Strong in-sample association does not establish transferable
prediction. Save negative/null results, fold lists, every test prediction,
missingness by win/loss and source, and 2024 alternate-2020-benchmark sensitivity.
No candidate league table or individual-voter inference is warranted.
