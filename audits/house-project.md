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

`publication/report.html` connects the findings, ten figures and source-linked
profile browsing. It includes all election candidates, all 435 sitting seats
and all 435 provisional incoming seats, including vacancies and unresolved
seats. Filtering, pagination and CSV export work locally. There are no external
script/font dependencies, and input text is escaped rather than executed.
The report is bundled with both complete downloads; the withdrawn website is
not redeployed.

## Substantive completion follow-up

A second audit found that acquired evidence was not fully connected to the
browser: losing candidates could have factual values in the long table while
profiles showed only extracted field names. The browser now exposes every one
of the 27,875 observations available at that release on its exact
candidate/contest, including actual
values, observation dates, qualification, model eligibility and available
original/archive receipts. Search includes those values and individual evidence
downloads retain the receipts. This is repaired access to existing acquisition,
not inflated coverage or promotion of unreviewed facts.

Association models also did not establish incremental predictive value.
An amendment fixed eight comparisons before their results were examined.
Both models use identical complete-case training/test cohorts, exclude held
states and repeated held-out people, and pass design-support checks. Intervals
rerun the entire paired pipeline after removing each state. Rank loss or missing
folds suppress intervals instead of supplying zero gains.

None of the eight pointwise intervals lies wholly above zero improvement.
Adding D/R incumbency lowers MAE by 0.076 share points on 349 candidates;
prior voting ideology lowers it by 0.009 on 131. The joint five-record model
increases MAE from 2.722 to 2.881 on 131 incumbent candidates. These are different
cohorts, not ranked candidate types. Both donor models control known D/R
incumbency. Complete paired predictions, folds, state-deletion diagnostics and
selection tables by incumbency, district lean and native winner flag are retained.
The native flag's absence is not a certified loss.

The new figure uses share-point error gains, not doubled margin-point
coefficients. The existing nine figures remain byte-identical. The result is
limited added predictive information in these selected samples, not proof that
candidate characteristics never matter or a forward forecast.

## Candidate acquisition continuation

A verified analysis/publication milestone did not finish candidate research.
The November 15 continuation attempted 117 uncovered candidates with held
campaign URLs and three independently located campaign/previous-office sources.
It pins 131 distinct HTML originals and preserves every retrieval outcome.
Successful downloads are not automatically background coverage.

Reviewed facts add 122 observations for 66 previously uncovered long-table
candidates: 34 Democrats, 31 Republicans and one listed write-in. Fifty lacked
held education/career/service summaries; 16 already had member/incoming summaries
and are not counted as people with wholly new information. The resulting long
table contains 27,997 observations for 683 people; 601 remain uncovered,
including 85 Democrats and 130 Republicans.

Supporting fragments are checked against exact original hashes. The join rejects
candidate/contest/name/state/district/party conflicts. Alternate URLs returning
identical bytes retain their separate retrieval receipts. A restaurant redirect
is excluded, parental/spousal military service is not assigned to a candidate,
and Foreign Service work is not military service. Degree completion is not
inferred from attendance, enrollment or an unspecified credential.

The added records are descriptive, retrieved after the election, with unknown
publication dates. They do not alter the fixed model samples or research
snapshots. This is measured acquisition progress, not universal biography
completion; access failures and remaining gaps are retained.

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

## Original missing-person ledger: superseded search adequacy

The next request froze the actual missing-person population before further
acquisition: 1,284 named candidates, 683 covered and 601 uncovered. It did not
mistake the broader missing-field table for a person queue. All 601 now have
one exact-context sourced/gap disposition. Direct acquisition attempted 405
of these people; the other 196 had no safely contextualized lead after the
recorded directory and individual search pass. Broad searches sometimes
returned irrelevant first-name hits, so this is not an exhaustive-search claim.

At that milestone, normalized gains were **233 people and 309 observations**, not the 258
additional source profiles. Coverage was **916 of 1,284 people**, comprising
441 Democrats, 396 Republicans and 79 other-party/write-in candidates.
The 368 remaining gaps comprise eight Democrats, 37 Republicans and 323 others.
The ledger distinguishes 196 without a contextual lead, 140 captured directories
or shells without accepted facts, 29 manually reviewed cases without qualifying
facts/identity, and three inaccessible-source cases. Downloaded pages are not
silently treated as reviewed or credited evidence.

The incremental ingest validates only changed/new profiles against original
hashes and supporting fragments, including explicit PDF pages, then merges
them with preserved normalized evidence via `house_candidates.build(inputs=...)`.
It does not reconstruct historical inputs from an absent ignored raw cache.
The next unchanged ingest validated zero profiles and preserved all 324
normalized source profiles. Historical source observations remain present.

The finalized ledger is checked against current normalized observations and
the acquisition manifest. Duplicate/omitted people, wrong candidate-contest
context, stale counts, incomplete/duplicate source outcomes and unsupported
accepted-source claims fail validation. Unreviewed nonempty pages for uncovered
candidates need source-scoped dispositions rather than automatic promotion;
extra pages for covered candidates stay uncredited. The browser, its filtered CSV,
`research-dispositions.csv` and `background-field-coverage.csv` expose the same
accounting.

At that milestone, field gaps were education 580, employment 518, prior-office/
governmental experience 909, military service 1,102, out of all 1,284 candidates.
Only 54 have observations in all four dimensions, still not necessarily
complete, current or independently verified biographies. Unknowns, secondary
paraphrases, self-reports, machine extractions and historical observations
retain their qualifications. No military/office field is not a negative label.
Retrospective additions remain model-ineligible, and frozen analysis samples
and outputs are protected by fingerprint checks.

## Discovery correction and field-gap repair

The user correctly identified that several saved searches were first-name-only
Bible, banking and furniture results. The earlier implication of an adequate
completed research pass is withdrawn. Recording an attempt and passing pipeline
tests do not establish adequate source discovery.

The repair preserves the old receipts and freezes the exact `c0fa188` profile
fingerprint and per-person field baseline. Its separate 701-person queue contains
368 people without observations and 333 already-covered people missing education
or employment. The original 601-person queue and historical normalized inputs
remain intact.

Current normalized coverage is **1,156 of 1,284 candidate records and 28,897 observations**.
Since `c0fa188`, gains are **240 newly covered records, 591 added observations and
569 filled candidate-by-field gaps**. These metrics differ: education gained 242,
professional history 299, prior office 12 and military service 16; 145 previously covered
candidates gained fields. The original 683-covered baseline has gained 473 records.
Remaining field gaps are education 338, professional history 219, prior office 897 and
military service 1,086. Only 57 records have observations in all four dimensions;
an observed field is not a complete or verified biography. The reviewed registry
contains 735 source profiles for 576 distinct candidate records, not 735 newly
covered people.

All 45 formerly uncovered major-party candidates were revisited. Forty-four
gained facts; T.P. Nykoriak remains a reviewed gap with pinned campaign/contextual
source receipts. His Detroit roots, Ukraine travel and veteran policies do not
establish education, employment, an office held or military service. No Democrats,
one Republican and 127 other-party/write-in records remain uncovered. Of these,
88 unresolved New Jersey write-in identities remain explicitly flagged for
inadequate discovery. The remaining 40 have reviewed source-specific gaps,
not exhaustive public-data absence findings. All original 601
records have accounting dispositions, which is not the same as successful
discovery. Another 192 already-covered targets still lack an original
education/professional-history target field.

The roster denominator is named candidate-contest records, not 1,284 independently
verified people. Identity holds retain roster provenance without inheriting
famous or professional namesakes' attributes. Reviewed indexed excerpts and
public-provider page extractions retain their actual method and limitations;
they are not native HTML or independent verification. Some Python certificate
failures were recovered through ordinary OS-trusted HTTPS with verification
enabled. Access restrictions were not bypassed.

All seven formerly pending-lead records received explicit native-source review.
Wrong-state/district directory profiles were rejected. The composite Idaho label
"Sarah Zabel Peterson" is retained for reconciliation, while the official county
ballot and FEC H6ID01318 support attributing only Sarah Zabel's self-reported
background to the Independent entry. Kaylee Peterson is a separate Democrat;
the original label is not silently rewritten and frozen analysis is unchanged.

New contextual institutional, campaign, official and voter-directory acquisitions
include the four supplied Gies, Dawson, Pericola and Rodriguez sources. Public
BallotReady fields remain directory-reported and exact-contest qualified.
Suspect college degree claims and ambiguous occupational labels are held, not
silently treated as credentials. School listing is not graduation, a candidacy
is not officeholding and a generic work/military section does not establish
military service.

Discovery tests reject the original irrelevant results, wrong districts/years,
changed snapshots, unsupported exclusions and stale person/field accounting.
New gap reviews verify owned source hashes and supporting fragments without
creating observations. The local browser and filtered CSV expose the repair
status and sources; `discovery-repair-dispositions.csv` covers all 701 targets.
The source registries and full normalized queries are included in both downloads.
This fixes discovery accountability, not the remaining evidence gaps. All new
facts stay retrospective/model-ineligible; no website deployment is authorized.

## Participation source intake

The November 15 supplement pins six selected normalized public inputs from the
dirty sibling `voter-participation` checkout, without modifying that worktree.
Per-file hashes, not its older HEAD, identify the actual imported content.
It adds 6,596 source-defined aggregate observations across 48 jurisdictions,
51 coverage decisions, and 23 House source-category/snapshot observations across
four districts. Sixteen result observations link to 12 existing candidate
records; seven nonperson/unassigned categories do not. This is zero additional
biography coverage, not 12 newly covered candidates.

Statewide, regional and aggregate demographic rows retain their native
definitions, timestamps, URLs, source receipts and normalized-input pointers.
The browser exposes these separately from candidate evidence and exports
their context IDs and matched House snapshots. Hawaii/Wyoming confirm pinned
counts; Maine's initial, provider and later RCV counts are not conflated.
Unknown final other/blank categories remain null. Source-reported counts are
not automatically unique voters, and regions are not mapped to districts.
Modes, snapshots, levels and groups are not additive.

Ordinary rebuilds read the pinned packet, not the sibling checkout or ignored
historical raw cache. Both complete downloads include it, all context outputs,
code and tests. The [intake documentation](../docs/PARTICIPATION_CONTEXT.md)
describes the supported explicit refresh and normalized-fact replay boundary.
The new receipt is `audits/participation-intake.json`; the earlier discovery
repair's release-validation hashes describe commit `6aeaa14`, not a claim that
its older browser report hash identifies this supplemented report.

Verification passed 346 tests, Ruff lint and formatting for 89 files, and
offline browser checks at 1280, 390 and 320 pixels plus readable no-JavaScript
findings and ten figures. All 117 pinned analysis files and 50 figure/plotted-data
files remain byte-identical. An extracted complete download, with networking
denied and neither historical raw cache nor sibling checkout, reproduced 112
generated files and the complete-query ZIP byte-for-byte. The figure package
embeds that exact full-query archive. No website deployment was performed.

## Validation contract

Focused tests check independent one-percentage-point defection contrasts,
share-to-margin interval conversion, identical alternate-benchmark samples,
fixed six-test correction, state/person training isolation, all-candidate and
all-contest retention, source-preserving biography integration and deterministic
replay. Current chart tests check both backgrounds and exact rendered bytes.
Added tests check a transferable synthetic signal, held-state/person target
perturbations, unsupported folds, an independently recomputed deletion, complete
candidate/contest observation attachment and unscaled predictive chart intervals.

The discovery-repair receipt in `audits/candidate-discovery-repair.json` records
the current research accounting; release verification receipts accompany it in
the same audit directory. The older `audits/publication.json` records earlier full-suite,
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
