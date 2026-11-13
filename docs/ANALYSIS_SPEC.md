# Frozen analysis specification

The original historical specification was written before calculating its
coefficients. The user subsequently clarified that **2026 is the primary
outcome**, not a future extension. Primary associations now fit 2026 alone.
Historical 2016-2024 outcomes supply training/backtests, with the original
2016-2022/2024 comparison retained separately. No historical coefficient is
presented as a 2026 finding, and no retrospective replay is called a genuinely
prospective forecast.

## Population and benchmarks

Retain every congressional contest and every D/R candidate feature query,
including exclusions and unmatched people. The main sample requires one named
nominee from each major party, usable counts and a qualified constituency
benchmark. Senate uses FEC state presidential returns. House uses Daily Kos
Elections/The Downballot's explicitly election-map-specific calculated district
results, not certified district presidential compilations or an independent
boundary audit. Use 2016 presidential results for 2016/2018, 2020 for 2020/2022,
and 2024 for 2024/2026. The 2026 House benchmark is the separately published
2026-map workbook, never the 2024 district map. Published 2016/2018 percentage rounding remains.

Do not treat incumbent/party columns in district benchmark workbooks as
historical features. Source status, map year and exact rows accompany benchmarks.
2024 House counts are the frozen official-Clerk factual queries. New 2024
Senate counts are independently parsed from the complete held Clerk report.
The 2026 House audit and 35-race Senate statewide control audit are provisional,
derived factual queries, not original provider JSON or certified final results.
Senate counts select native statewide totals, not county sums. FL/OH special
seats have distinct contest IDs and statewide benchmarks; they are not pooled
with a second regular contest in the same state. Positive-count failures,
unresolved runoff/RCV stages, independents and ambiguous accounting remain
visible but outside the main D/R sample.

## Features

Use FEC candidate IDs plus name/state consistency checks to crosswalk legislators.
For 2024, first anchor return names to the FEC general-ballot roster by
state/chamber/district; its IDs and incumbent flags cover challengers and losers.
For 2026, uniquely match actual return nominees to the official FEC candidate
master by name/state/chamber/district/party. Its I/C/O marker is a recorded
incumbency field, not evidence that every registered candidate appeared on a
ballot. Blank and ambiguous matches remain unknown. Retain the complete master.
All ambiguous joins remain unresolved. A unique source-documented name match
also requires state/chamber and dated-service anchors; it is labeled separately
when the FEC ID is missing from the crosswalk. First-name prefix variants require
at least three matching letters and uniqueness within the anchored scope.
Native incumbent flags are explicitly distinguished from dated-service checks.
For resolved people, dated same-chamber service takes precedence; disagreements
are retained in full, not erased. Unresolved people retain native source flags.
Today's membership cannot establish historical incumbency.

Legislative features use the previous completed Congress: 113, 114, 115, 116 and
117 respectively for elections 2016 through 2024, and **118 for 2026**.
Nokken-Poole first dimension
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

Main 2026 adjusted associations are separate OLS models of raw gap on the same
lean/cycle controls plus the focal feature. Incumbency includes both D and R
incumbent indicators. In the single-year primary fit no redundant cycle dummy
is added. Current-year cross-fits train on other states' 2026 counts; earlier-year
prediction replays train strictly before 2026. The incumbent-record models additionally compare:

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

Run chronological, state-held-out predictions for 2018, 2020, 2022, the historical
2024 slice, and the primary 2026 slice. Each training set uses only earlier elections, excludes the entire
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

## User-directed categorical and constituency-context extension

This exploratory extension was specified after the original results and before
estimating the new category/context coefficients. Preserve the six original
tests and their interpretation. Do not rank religions or races causally.

Religion categories retain Catholic, Protestant, Jewish, Muslim, atheist,
agnostic, unaffiliated, Hindu, Buddhist, Orthodox, LDS, Unitarian Universalist,
humanist, other Christian, Christian-unspecified, other, multiple and unknown.
Do not equate unaffiliated or humanist with atheist. Explicit denominations map
to Protestant; unspecified Christian does not. A church attendance/membership
statement alone and "raised Lutheran" do not establish current religion.
Prefer the pre-election Pew/CQ questionnaire snapshot for this new categorical
feature, using the dated directory field only when no matched Pew response
exists. Preserve the old directory literal and binary supplemental fields
unchanged. Refused/unknown questionnaire responses stay unknown, not a
directory-imputed faith. Match unique documented names within state/chamber and
dated service, not district numbers that may have changed.

Code race/ethnicity from explicit member-authorized identity statements or
positive Office of the House Historian group records,
never from names, photographs, religion, caucus membership or absence from a
minority list. Preserve multiple races and Hispanic ethnicity separately.
Unknown race is not White; unknown Hispanic origin is not non-Hispanic.
Authorized first-person/biographical claims such as "first African American
elected ..." qualify only when they clearly describe the member. Retain the
literal clause and page. No White-versus-minority or Hispanic-versus-non-Hispanic
coefficient is possible without both explicitly documented groups.
After the first 2026 provisional run exposed sparse biography coverage,
119th-Congress Historian records were added for 2026 only. Label them as
published classifications, not self-reports; absence supplies no negative
identity. Keep the Asian/Pacific Islander umbrella combined unless narrower
explicit evidence exists, and use Asian plus NHPI population shares for its
matching-share interaction. Combine overlapping documented racial groups as
multiracial; Hispanic origin remains separate. These additions never enter
historical-to-2026 forecasts.

Use complete Census ACS five-year B02001 (race alone and multiracial) and
B03002 (Hispanic origin, any race) population tables. Preserve estimates,
margins of error and all 80 replicate estimates in the cached originals.
Extract all selected state/district population rows with source row numbers.
Validate race totals, percentages, duplicate keys and congressional map labels.
The 2016, 2018, 2022 and 2024 releases identify the 115th, 116th, 118th and
119th maps. The 2021 five-year files still identify the 116th map: use them for
2020 only outside North Carolina, where the 2020 election map changed.
Never reuse the 116th-map NC values for 2020. State Senate geography is stable.
These are retrospective population controls, not election-day counts of voters
or CVAP. Publications after the election must not enter forward forecasts.
For 2026 use 2024 ACS state composition. House district controls require pinned
Census evidence of unchanged 119th-to-120th maps: hold Alabama, California,
Florida, Louisiana, Missouri, North Carolina, Ohio, Tennessee, Texas and Utah.
This is a conservative reported-map qualification, not an independent geometry
audit. Hold all 2026 district composition when that evidence is absent.

The Census does not collect religious affiliation. The Setzler district
religiosity v2 dataset supplies a separately labeled 2010 RCMS
congregation-adherence sensitivity on its 2016/2018 maps only. It apportions
split-county populations and assumes within-county uniform adherence; it is
not exact district self-identification. "Other" includes Black Protestants,
LDS and Jehovah's Witnesses; no-congregation does not mean atheist,
agnostic or unaffiliated. Do not create individual Jewish/Muslim/atheist
constituent shares or a complete Protestant share from these columns.
Exclude Pennsylvania 2018 unless the new court map is independently qualified.
No carry-forward of old-map religion estimates to 2020/2022/2024/2026.

Fit pairwise category contrasts among verified Democratic incumbents, House
and Senate separately, on eligible **2026** elections. Religion contrasts use
Protestant as the prespecified reference; race contrasts use explicitly White
as reference, and if unavailable additionally report known-group contrasts
against explicitly Black with their selected-population limitation.
For each pair, require at least three distinct identified people and three
states per group, at least eight state clusters overall and the existing rank,
condition-number and residual-row checks. Preserve every unestimable category
as an explicit hold, including zero-observation atheist categories.

Compare lean/quadratic/cycle adjustment with the same sample plus Census
Black, Asian, Indigenous, NHPI, other-race, multiracial and Hispanic shares
(White share is the omitted race component). A focal identity-by-corresponding
constituent-share interaction is exploratory when its population share is
actually measured. Hispanic origin is separate from race. Report both
main effects and interactions: the main effect is at the sample's mean share,
not at zero population. No atheist-by-unaffiliated proxy interaction.
For religion context, use available Catholic, evangelical, mainline and other
congregation shares on the identical restricted sample. Only Catholic has an
exactly corresponding tradition field for a matched-share interaction.

All extension inference is exploratory, with nominal pointwise intervals and
Holm p-values across estimated focal/interaction terms per chamber. Category
counts, distinct people/states, excluded map joins, exact fitted terms,
covariance and sample membership remain downloadable. Do not silently drop
rare categories into a large "other" comparator. The earlier forecasts remain
unchanged; no prospective claim is made for these retrospective context fits.
