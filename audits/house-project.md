# House project audit and repairs

## What was incomplete

The project had substantial source acquisition and separate analysis snapshots,
but no single current House report connecting the question, all six main trait
comparisons, the meaning of performance, biography coverage and complete data.
The current figures emphasized ideology without a single view of the remaining
characteristics. CSV availability alone was not a usable full-project interface.

The incumbent-member census and election-candidate population were also easy to
confuse. A complete 435-seat member roster does not supply complete biographies
for every challenger or losing candidate, nor does it justify treating missing
service evidence as verified nonincumbency. Unknown incumbency is retained rather
than forced to false to enlarge the comparison sample.

## Repairs

`results/house-study/` now retains all 435 House contests and all 1,284 named
candidate records, with 405 eligible comparisons and 30 held contests. It
recomputes six exploratory characteristic models using the previously qualified
features, conservative state-cluster/delete-one-state intervals, full-rank
deletion checks and fixed six-test Holm correction. Competitive-seat and
identical-sample 2020/2024 benchmark sensitivities are downloadable.

The six-trait summary does not establish a universal winning candidate type.
None clears Holm correction. The same-person ideology comparisons remain
important: donor and prior-voting scores have opposite associations, and donor
estimates are sensitive to the presidential benchmark. Neither is a universal
moderation premium.

The new retrospective benchmark excludes the target state and all repeated
person identities from training. It uses district lean and lean squared,
without absorbing incumbency or background. Across 405 candidates in 47 folds,
presidential-baseline MAE is 7.48 share points and state-held-out MAE is 2.56;
signed held-out bias is +0.02. This measures within-cycle adjustment, not forward
forecast skill. Residuals are not causal candidate effects or exact WAR.

`publication/report.html` connects the findings, nine figures and source-linked
profile browsing. It includes all election candidates, all 435 sitting seats
and all 435 provisional incoming seats, including vacancies and unresolved
seats. Filtering, pagination and CSV export work locally. There are no external
script/font dependencies, and input text is escaped rather than executed.
The report is bundled with both complete downloads; the withdrawn website is
not redeployed.

## Incoming biography source audit

The new finite, reviewed source pass preserves primary office/campaign sources
separately from secondary Wikipedia evidence. Source corrections removed an
unsupported University of Florida/law-degree attribution, weakened unsupported
credential claims to association-only, retained attendance/enrollment versus
completion, and tightened military/career wording.

Coverage is compared with the committed `fdd8417` baseline, not total overlapping
records: structured-education gaps fell from 75 to 56 (**19 newly covered
candidates**); exact-birth-date gaps fell from 101 to 80 (**21 newly covered**).
The acquisition initially reported 50 education gaps filled; that was an
overstatement counting already-covered candidates and is withdrawn here.
All observations retain identity context and pinned evidence. Newly attached
fields remain descriptive/model-ineligible. Existing source observations are
not overwritten; multiple records remain in the long evidence table.

## Validation contract

Focused tests check independent one-percentage-point defection contrasts,
share-to-margin interval conversion, identical alternate-benchmark samples,
fixed six-test correction, state/person training isolation, all-candidate and
all-contest retention, source-preserving biography integration and deterministic
replay. Current chart tests check both backgrounds and exact rendered bytes.

The release receipt in `audits/publication.json` records actual full-suite,
formatting, browser and network-disabled extracted-replay outcomes. Do not treat
this validation contract itself as evidence that those checks have passed.

## Remaining limitations

The November 12-13 provider snapshot is provisional, not certified. The Clerk
roster is dated November 3 and was retrieved November 13, not a live membership
count. There are 433 occupants and two vacancies, not 435 sitting people.
Nine incoming seats lack a unique provider winner. The 56 education and 80
exact-DOB gaps remain explicit. Newcomers without federal service have no
invented voting record. Religion disclosures are dated observations; missing
military or identity evidence is not nonservice or a negative reference group.
Challenger/loser trait coverage remains selective, and unreviewed campaign facts
cannot support all-nominee education/career models. Frozen historical research
is preserved rather than rewritten by the new exploratory study.
