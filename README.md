# Which candidate?

Which Democratic House candidates outperform their districts'
partisanship, and how is that associated with ideology, legislative votes,
party loyalty, incumbency and candidate background?

This is an independent research project, not a modification of
`voter-participation`. **The primary outcome is the 2026 election.** Earlier
elections (2016-2024) are training data and historical backtests. The 2026
provider counts are provisional, not certified final returns. Democratic-aligned independents
remain separate from Democratic nominees.

## Status

**Current full-trait successor:** read the
[complete characteristics report](results/house-characteristics-v6/report.md)
or open **`publication/characteristics-v6/report.html`** locally. It covers all
fifteen requested trait blocks, with separate coverage for 1,284 candidates,
449 Democrats and 405 eligible Democratic performance comparisons. The
[reviewed dataset and methods](docs/HOUSE_CHARACTERISTICS.md) distinguish
qualified, dated/reported, uncertain, unknown and inapplicable values.

V6 completes two requirements-led acquisition loops: **eight new evidence-yielding
originals, 36 observations, nine Democrats and 28 candidate-trait fields**.
Nine previously unknown fields across six candidates receive first observations.
New factual qualification is separate from **14 newly analytical fields**:
age 196→197, religion 168→170, education 201→206, profession 96→100,
positive military 22→23 and incumbency 437→438. One held FEC classification
is newly qualified through Williams's literal broadcast alias, not counted as
a new PBS classification. Eleven Democratic incumbency holds remain.

Six affected blocks are recomputed and nine input-identical V5 blocks reused.
**No new trait block becomes estimable.** New broad Christian descriptions are
not inferred Protestant labels; AAPI self-descriptions do not expand the
historical CAWP contrast; family origins do not qualify ethnic identity.
No negative office/government/military reference was acquired. All 823 earlier
normalized claims and 381 protected historical files, including V1-V5, remain
unchanged. See the [complete V5→V6 table](results/house-characteristics-v6/v5-v6-trait-progress.csv)
and fixed-baseline incumbent/nonincumbent coverage. No website deployment.

The [V6 validation receipt](audits/house-characteristics-v6-validation.json)
records **434 passing tests**, independent reconstruction of eleven associations
and 1,730 matched predictions, responsive/no-JavaScript browser checks, and
network-denied complete-download replay without historical raw caches.
Joint D/R incumbency and selective historical donor ideology retain their
Holm-qualified associations; no matched predictive-gain interval is wholly
above zero. Unsupported contrasts and full-population failures remain visible.

### Frozen V5 acquisition checkpoint

V5 acquires **27 observations from ten evidence-yielding originals**, covering
**ten Democrats and 23 candidate-trait fields**. Seven previously unknown fields
across six candidates gain first observations; other observations supply missing
precision, credentials, historical timing or corroboration. Democratic analytical
coverage changes: age 193→196, education 197→201, profession 95→96 and federal
incumbency 432→437. New official FEC campaign-name links resolve five controls,
not independent federal-service verification; twelve Democratic holds remain.
An undated explicit religious description adds factual but not analytical coverage.
All V1–V4 outputs and 796 earlier reviewed claims are preserved.

There are **13 additional Democratic analytical fields but zero newly estimable
trait blocks**. Source coverage and analytical support are different milestones.
Eleven input-identical blocks are reused and four affected blocks recomputed.
Full-cohort failures remain visible: restricted matched prediction does not
validate unsupported candidates. The complete fifteen-trait before/after table
and incumbent/challenger breakdowns accompany the report.

Historical donor ideology and the **joint D/R-incumbency block** clear the
declared fifteen-block Holm correction; the Democratic-incumbent coefficient
alone does not. No completed matched-sample prediction comparison establishes
improvement with a 95% interval wholly above zero. Ethnicity, prior elected
office, other government experience and military contrasts remain unavailable,
not null findings. Missing identities/service never supply negative reference
groups. Race retains only the restricted historical CAWP Black-versus-White
women comparison, not an all-candidate effect. Donor and voting ideology are
distinct measures and cohorts.

The preserved v1 follow-up added **12 reviewed observations for seven already-covered
candidates**, including seven first-recorded trait fields and three newly
qualified birthdays: **zero newly covered people**. All 28,981 earlier observations
and frozen analyses are preserved; that historical total was **28,993**. Three official
biography sources are explicitly retained public-index extracts, not original
PDF downloads. The browser, receipts, uncertainties and both complete downloads
include the successor. **No website deployment.**
The [v1 validation receipt](audits/house-characteristics-v1-validation.json)
records the full tests, independent numerical checks, browser checks and
network-denied complete-download replay.
The [v2 validation receipt](audits/house-characteristics-v2-validation.json)
records 399 passing tests, independent numerical reproduction, responsive/no-JS
browser checks and network-denied replay with all 187 protected files unchanged.
The [V4 validation receipt](audits/house-characteristics-v4-validation.json)
records 421 passing tests, independent reproduction of eleven associations and
1,709 matched predictions, desktop/mobile/no-JS browser checks, and exact
network-denied replay. All 275 protected files, including V1–V3, are unchanged.
The [V5 validation receipt](audits/house-characteristics-v5-validation.json)
records 425 passing tests, independent reproduction of eleven associations and
1,720 matched predictions, responsive/no-JS browser checks and network-denied
complete-download replay. All 328 protected files, including V1-V4, are unchanged.

### Earlier frozen House findings and research history

**Start with the [House findings report](results/house-study/report.md).** For the
complete local reading experience, open **`publication/report.html`** after
cloning or extracting either current download. It combines the findings, ten
figures, and a searchable source-linked browser: all 1,284 election candidates,
all 435 sitting seats, and all 435 provisional incoming seats. Filter by state,
party or population, inspect profiles, and download the filtered rows as CSV.
The report and figures work offline; only opening external source links needs
network access. No website has been redeployed.

The report brings the six characteristic comparisons into one table, with
uncertainty and multiple-comparison correction. None clears the six-test Holm
correction. A separate state-and-person-held-out diagnostic covers 405 qualified
House comparisons; it is retrospective, not a forward forecast or a causal
candidate ranking. New biographies remain descriptive rather than silently
becoming model inputs.

Eight matched-sample comparisons now test whether traits improve predictions
beyond district lean. **None has a pointwise 95% interval wholly above zero
improvement.** The joint five-trait incumbent model changes held-out MAE from
2.722 to 2.881 vote-share points among 131 candidates; this is not a causal
candidate ranking. All paired predictions, folds, full-pipeline state deletions
and selection diagnostics are downloadable.

Profiles expose the **28,993 acquired observations for 1,156 candidate records**, including
losing candidates, with actual values, dates, source receipts and qualifications.
Search includes these values; individual evidence CSVs preserve their review
status. **The earlier claim of an adequate completed search is withdrawn**:
first-name-only Bible, banking and furniture results were failed discovery.
The correction adds **240 newly covered records and fills 636 candidate-by-field
gaps** since `c0fa188`; 204 already-covered candidates gained fields. These are
different counts, not complete biographies. The frozen original 601-person
ledger and separate 701-person discovery/field-gap repair queue preserve the
old attempts and distinguish sourced facts, reviewed gaps and inadequate searches.

The [targeted Democratic research audit](results/house-study/democratic-background-audit.json)
recomputed **449 records, 44 education gaps and 25 professional-history gaps**,
with six overlapping records: 63 targets. This pass fills **42 education and
25 professional-history gaps across 61 candidates**, adding 84 observations,
not newly covered people. **Two education gaps remain: Kristi Burke and Melissa
McDonough.** All 449 records have the standardized
[trait CSV](results/house-study/democratic-candidate-traits.csv) and
[JSONL](results/house-study/democratic-candidate-traits.jsonl.gz), including values,
source qualifications, review/completion/relationship status and unresolved
fields. Twenty-two identity-match rejection records are retained. Field presence
is not a complete biography or verification of every credential.

The [participation supplement](docs/PARTICIPATION_CONTEXT.md) imports **6,596
source-defined aggregate observations across 48 jurisdictions**, plus 51
coverage decisions and 23 House result-category/snapshot records across four
districts. Sixteen result observations link to 12 existing candidate records.
The browser shows statewide counts, definitions, source dates, receipts and
separately labeled Maine RCV snapshots. These are **not new biographies or
district turnout**; background coverage, frozen outcomes and all trait models
are unchanged. The source vintages differ: the November 15 import is not a
fresh simultaneous collection. Complete normalized inputs and queries are in
both downloads; replay does not require the sibling project.

Rebuild the complete current project from pinned normalized inputs:

```bash
python -m pip install -e '.[test]'
python -m which_candidate.house_project --evidence-only
```

Use the existing environment or the pinned dependency instructions below.
The build requires no new source acquisition and refreshes the same current
outputs and complete downloads. The [project audit](audits/house-project.md)
records the findings, repairs, validation and remaining limitations.
To ingest newly reviewed evidence without reconstructing missing historical raw
caches, use `python -m which_candidate.reviewed_backgrounds`, then
`python -m which_candidate.candidate_discovery --finalize` and
`python -m which_candidate.candidate_research --finalize`, then
`python -m which_candidate.house_project --evidence-only`.
Only new or changed profiles require pinned originals; unchanged normalized
evidence is preserved. The evidence-only path refreshes participation dependencies,
coverage, the local browser and both complete downloads without refitting earlier
frozen analyses or redrawing their figures. The separately versioned full-trait
successor is rebuilt. See the [research workflow](docs/HOUSE_CANDIDATES.md#incremental-evidence-ingestion-and-replay).

**Current scope: House only.** The [complete candidate inventory](results/house/candidates.csv)
accounts for **1,284 named candidate-contest records in all 435 districts**, including Republicans,
other parties, losers and multiple candidates from the same party. Another 142
aggregate write-in/none-of-the-above choices are retained separately, not invented
as people. This is the pinned November 12-13 provider roster, not a certified
ballot-access census or a claim that every person has complete trait data.
In particular, 88 unresolved New Jersey write-in identities have explicit roster
holds; a name written on a ballot does not by itself identify a campaigning person.

The [House information audit](docs/HOUSE_CANDIDATES.md) describes the actual source
coverage and unresolved fields. All current figures are House-only. Older
House/Senate analysis snapshots remain unchanged for provenance.

The readable [background observations](results/house/background-observations.csv)
contain factual/source-reported fields for **1,156 candidate records**, not all 1,284.
They include dated religion records and newly acquired official voter-guide
profiles and anchored campaign/previous-office biographies. **128 records still
lack these observations**, including no Democrats, one Republican and 127
other-party/write-in candidates. The [601-person disposition table](results/house-study/research-dispositions.csv)
preserves the original queue, including people now covered. The separate
[field audit](results/house-study/background-field-coverage.csv) covers all 1,284:
296 lack acquired education information, 194 professional-history information,
897 prior-office information and 1,085 military-service information. Professional
history can include explicitly unpaid roles; it does not universally establish
paid employment. Missing service is not
nonservice, and one observed field is not a complete biography. A null-ID matching
bug that assigned 42 unrelated historical biographies has been corrected; the
audit documents the withdrawn counts and remaining coverage gaps.

The [discovery correction table](results/house-study/discovery-repair-dispositions.csv)
also includes already-covered candidates missing education or employment.
All 45 previously uncovered major-party candidates were revisited: 44 gained
observations; T.P. Nykoriak remains a reviewed source-specific gap. His campaign's
Ukraine travel and veteran policies do not establish military service, and
unsuccessful candidacies are not officeholding. The remaining other-party
discovery pass retains source-specific gaps and unresolved identities, not an
exhaustive-search claim. All 88 discoveries still flagged inadequate concern
unresolved New Jersey write-in identities. Among already-covered repair targets,
133 still lack an original education/professional-history target field.

The [full House roster](results/members/house-119-seats.csv) now accounts for
**all 435 voting seats: 433 named occupants and two explicit vacancies** in the
Clerk snapshot dated November 3, 2026, retrieved November 13. Six nonvoting
delegate/Resident Commissioner seats are separate. All 433 occupants have age,
birth, education, career, service and cutoff-only voting information; 411 have
substantive reported religion observations, 17 have unknown/refused responses
and five lack acquired qualified disclosure. Dated statements are not verified
current beliefs.

The [incoming House table](results/members/house-120-seats.csv) separately retains
all 435 seats for the Congress scheduled to begin **January 3, 2027**. The pinned
provider reports 426 provisional winners: 319 continuing members, six returning
former members and 101 others; nine seats remain unresolved. Every reported
winner has an existing biography or a secondary reported prior-background
summary, **not universally complete education, religion or exact birth dates**.
The latest reviewed source pass reduces incoming structured-education gaps from
75 to **56** and exact-birth-date gaps from 101 to **80**. Those are **19 and 21
newly filled gaps**, respectively, not the larger count of overlapping source
records. The remaining fields are explicitly listed in the incoming gap ledger.
The [coverage audit](results/members/coverage.json) reports actual availability.
Newcomers do not inherit invented federal votes. The acquired CongressData
deposit adds 1,045 native historical variables for 368 matched members, through
2024, with source years and a separately qualified codebook.

The older [incumbent-candidate dataset](results/house/incumbents.csv) covers
**360 qualified election candidates**, not the whole House, with age,
education, birthplace, career history, service and
pre-election voting records for every row. It includes 340 substantive dated or
public religious self-descriptions, 16 explicit unknown/refused responses and
four unresolved disclosures; dated statements are not verified current beliefs.
The [incumbent audit](results/house/incumbent-coverage.json) separates current
2025-2026 voting from prior 2023-2024 ideology and historical donor scores.
The [source investigation](docs/CANDIDATE_DATABASES.md) also distinguishes acquired
official biographies and guides from nationwide services requiring approved access.

**Website publication is withdrawn pending further candidate research.** The
gallery and its links were removed from The Margin of Error. Historical analysis
data remain under `results/`; superseded plots are available only in Git history.

The old label **"118th ideology" means a Nokken-Poole score estimated from
2023-2024 congressional votes**. It covers returning legislators, not all 2026
candidates, and is not their current campaign position. Donation-based ideology,
issue positions, and voting-based ideology need separate definitions and samples.
The [source-expansion investigation](docs/CANDIDATE_DATABASES.md) reopens the
challenger, losing-candidate, religion and race coverage gaps.

The earlier reopened-source milestone retains all 470 contests. Its
[complete research queries](downloads/2026-source-complete-queries.zip) contain
candidate-source coverage, review queues, individual CAWP observations, caucus
attrition and [separately classified state polling](docs/STATE_POLL_CONTEXT.md).
The user has authorized a replacement analysis and new figures. Website
publication remains withdrawn; this does not authorize redeployment.

There is **one current chart set in [`publication/`](publication/)**, with no
versioned copies of rejected graphics. Its manifest records the analysis inputs
and withdrawn website status. The reusable
[`publication-charts` skill](.github/skills/publication-charts/SKILL.md) encodes
the editorial style and required rendered-image review, with a personal copy
installed for future projects.

An [independent identity review](docs/CANDIDATE_IDENTITY_REVIEW.md) corroborates
four donor-name aliases and cross-office ID bridges for two candidates,
retaining all 470 contests and every unresolved lead. Its complete replay
download includes both openly licensed crosswalk originals; no new scores
are promoted into the election models.

**The [current figures](docs/PUBLICATION.md)** use the unchanged
[2026-v4 analysis](docs/REBUILD_2026_V4.md):
ten House figures, including the six-trait and predictive-value comparisons, plus the expanded
all-party House information inventory and local report. The integrated
`results/house-study/` outputs recompute current comparisons with full-rank
state-deletion checks and add held-out diagnostics; frozen analysis snapshots
remain unchanged. Expanded biography coverage is not silently promoted into
new verified model traits.

**The answer depends on the measure and benchmark.** The selected House donor
association falls from +3.22 to +0.81 margin points when the presidential
benchmark changes on identical candidates. Donor and voting ideology have
opposite associations even on the same 100 incumbents. This does not establish
a universal moderation premium.

See the [critique and repairs](audits/2026-v4/critical-review.md),
[complete queries](downloads/complete-queries.zip) and
[Substack bundle](downloads/substack-figures.zip).

**The archived corrected release is [2026-v3](results/2026-v3/analysis/report.md).**
It supersedes v2's interpretation while preserving its historical analysis data. Fresh native
queries acquired November 13 retain all 435 House and 35 Senate races, with
405 House and 28 Senate comparisons eligible. Counts remain provisional.
Federal incumbency is corrected; unity uses actual pre-election 119th-Congress
votes. Prior-118th ideology remains explicitly lagged.

Blue Dog/CPC structural comparisons include historical cohorts, full-pipeline
state-deletion uncertainty and identical-sample benchmark sensitivities.
They are not exact Split Ticket WAR. Sparse 2026 evidence does not establish
a precise moderation advantage or its decline. See the
[post-audit specification](docs/CORRECTIONS_2026_V3.md) and
[original audit](audits/2026-v2/critical-review.md).

### Archived v2 status

The implemented analysis combines audited returns, election-map presidential
benchmarks, dated candidate identities, lagged Voteview records and authorized
official biographies. It fits chamber-specific **2026** associations and
chronological, state/person-held-out validation through 2026. The current snapshot
retains all 435 House and 35 Senate contests, with 408 House and 29 Senate
comparisons eligible for analysis.

No primary 2026 trait comparison passes the six-test-per-chamber Holm threshold.
The historical incumbency finding must not be presented as a 2026 result. These
are observational comparisons, not causal nominee-replacement effects.

Religion categories and documented race/ethnicity have separate exploratory
models adjusted for Census constituency composition. Complete Census tables,
Pew religion lists and official positive identity records are pinned. Census does not
collect religious affiliation: religious context requires a separate, explicitly
qualified source. Unknown identities are never inferred from names or photos.
Changed 2026 district maps are held from old-map Census controls. Compatible
2026 district religious composition and comprehensive nominee identity coverage
remain gaps; no missing identity is assigned to a reference group.

See [methodology](docs/METHODOLOGY.md), [data and qualification rules](docs/DATA.md)
and [implementation milestones](docs/ROADMAP.md).

## Run

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/which-candidate import-participation --source ../voter-participation
.venv/bin/which-candidate acquire-research
.venv/bin/which-candidate import-2024 --source ../voter-participation
.venv/bin/which-candidate import-2026 --source ../voter-participation
.venv/bin/which-candidate build --output artifacts/returns-2026-v1
.venv/bin/which-candidate analyze
.venv/bin/which-candidate verify --output artifacts/analysis-2026-v1
.venv/bin/which-candidate package-analysis
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

Imports copy verified originals into an ignored, content-addressed local cache.
Builds use that cache without network or access to the parent repository.
Complete factual queries and derived tables are retained under `data/processed/`.
The GitHub repository is public. Raw caches and private replay archives are
excluded from Git; source acquisition does not publish an update automatically.

The complete 2026 local download is `artifacts/which-candidate-2026-v1.zip`, including
original inputs, every query and exclusion, derived tables, code and tests.
Extract it to rebuild independently of `voter-participation`. For the recorded
dependency versions, install with
`.venv/bin/python -m pip install -r requirements.lock -e '.[test]'`.
Dependency installation may require network access; the subsequent data build
does not.

The archived v2 report, categorical comparisons and **complete derived
analysis queries** are copied into `results/2026/` for repository readers,
including held fits, evidence, fold membership and predictions. The private
local replay archive additionally contains the original source bytes. Restricted
whole workbooks are not uploaded to GitHub.

## Publication figures

The current [eight-figure research set](publication/) has separate
Substack/Margin of Error PNG/SVG versions, CSVs, captions and alt text:
seat baselines, donor sensitivity, same-candidate ideology measurements,
voting/incumbency/caucus history and evidence coverage.
These are repository research assets, **not a live website gallery**.

```bash
.venv/bin/python -m which_candidate.rebuild replay --output replay-analysis
.venv/bin/python -m which_candidate.rebuild_publication
.venv/bin/python -m which_candidate.rebuild_package
```

The complete download includes all 470 contests and every evidence row, hold
and fitted sample, not just metadata. Extract it to replay without the parent
project or raw website narratives; see the [publication guide](docs/PUBLICATION.md).

Both builders refresh the same destinations after successful generation:
`publication/`, `downloads/complete-queries.zip`, and
`downloads/substack-figures.zip`. Unchanged files are reused; obsolete plots are
removed from the managed theme/data folders. No old plot sets are bundled.
The Substack ZIP embeds the exact complete-query ZIP.

The two themes use warm-paper Substack (`#F7F5F0`) and website-paper Margin of
Error (`#F2EFE7`) backgrounds. All other decoded PNG pixels and dimensions match.
Git history retains earlier graphics; the checkout contains only the current set.
No website deployment or Substack publication is performed.
