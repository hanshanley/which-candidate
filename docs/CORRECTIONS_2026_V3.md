# Post-audit 2026 correction specification

This is an **exploratory amendment after inspecting v2**, not a newly
preregistered confirmatory analysis. Preserve all bytes in `results/2026/`
and `publication/2026-v2/`; retain the original audit.

## Evidence

Pin all 435 House and 35 federal Senate native endpoints. Keep every selected
candidate row, minor party, write-in, old v2 count, native clock, reporting
percentage and exclusion. County/map objects are outside this district/state
total query. Hold test/stage/date/round failures. Require identifiable positive
D/R nominees, qualified presidential benchmarks and less than 10% other-party
share. AK/ME final RCV rounds and Louisiana Senate stage remain unqualified.
Independent is never relabeled D.

Native/FEC positive incumbency is not proof of federal service. California's
general-election list identifies Mike McGuire as a state senator (page 4).
Dated federal terms and the Clerk's November 3, 2026 membership XML corroborate
actual incumbents. Earlier votes alone are insufficient. Publish aliases,
selected Clerk member rows and unresolved holds.

119th-Congress voting features include only dates strictly before November 3,
actual cast codes 1/6 and opposing strict D/R majorities. Exclude tied party
votes, absences, paired/announced votes and President rows. Require 50 unity
votes; preserve cast/unity/with-party denominators. This is cast-only cutoff
unity, not exact Voteview aggregate unity. Full-119th ideology includes
post-election roll calls; retain 118th Nokken-Poole ideology as explicitly lagged.

## Models, units and inference

Primary outcome: congressional D two-party share minus qualified 2024
presidential D share on the actual 2026 map/state. One share point is **two
D-minus-R margin points**. Fit chambers/years separately with lean and lean
squared; incumbency additionally controls R incumbency. Other primary traits
compare verified D incumbents. Defection is per +1 pp, ideology per +0.1
rightward, age/tenure per ten years, gender source-recorded F versus M.

Report CR1 and leave-state CV3. Pointwise sensitivity envelopes use the larger
focal standard error and t(G-1); they are not simultaneous or a cure for sparse
inference. Promoted traits require 30 rows, ten states, leverage below 0.8 and
complete deletions. Categorical groups require ten people/five states each.
Sparse estimates remain downloadable diagnostics, not headline advantages.

Six-test Holm families are separate by chamber/year for primary traits.
Identity, moderation and specification searches are exploratory. Retain
competitive 40-60% lean, state effects, joint records, prior unity and material
other-party sensitivities. Alternate presidential fits use identical candidates
and published returns on the same map; never fill changed-map cells.

## Moderation

Keep continuous ideology, caucus membership and PAC listings distinct.
Blue Dog rosters are retrospective full-Congress lists published November 10,
2026; CPC has pre-election archives qualified from 2020 onward. Join actual
general nominees, including losers, excluding overlapping memberships.
Different vintages/cohorts/maps prevent a clean historical trend test.

Fit lean/lean-squared/D/R-incumbency baselines outside each state, then contrast
Blue Dog/CPC mean residuals. Refit the entire held-state pipeline after each
state deletion; envelope its uncertainty with conditional CR1/CV3. Export all
training IDs, group samples and deletions. Separate joint group regressions
remain diagnostics. This is **not exact Split Ticket WAR or a causal
nominee-replacement effect**.

Show the full sample, the same-map subset without presidential swing and that
identical subset with swing. Separate sample loss from adding the control.
Justice Democrats has an archived pre-election candidate list. Blue Dog PAC's
endorsement page is empty even in the archive: current candidate-page listings
with earlier CMS dates are only a **PAC-listed proxy**, vulnerable to
deletions/survivorship, not a complete archived endorsement roster.

Lakshya Jain's supplied November 12, 2026 article motivates investigation, not
a numerical target. A different share-point residual cannot be relabeled WAR
to reproduce its approximate three-point claim. Methodological reference:
https://split-ticket.org/2025/08/15/deconstructing-war/

## Identity, validation and publication

Coverage includes all eligible D nominees, not only documented winners.
Lean-only identity pairs no longer require Census coverage; adjusted pairs
still need map-compatible resident-population controls. Unknown is not a
negative race/religion category. Census does not collect religion; compatible
2026 district religious composition remains unqualified.

Chronological validation consistently uses prior-completed-Congress records
and excludes target years, states and identified target people. Report absolute
MAE, RMSE and signed bias alongside same-sample paired lifts. State bootstrap
intervals resample fixed prediction pairs, are explicitly conditional and
omit refitting uncertainty; they do not establish calibrated forecasts.

New immutable outputs are `results/2026-v3/` and `publication/2026-v3/`.
Every figure has complete plotted CSVs, PNG/SVG variants, captions and hashes.
Both ZIPs include complete normalized selected queries, legislative tables,
model samples/exclusions, residual/deletion/fold records, receipts, code/tests,
methods and lockfile. Restricted original workbooks/website bodies stay local;
normalized factual inputs support a network-disabled public replay.
