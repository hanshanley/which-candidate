# Which candidate?

Which Democratic House and Senate candidates outperform their constituencies'
partisanship, and how is that associated with ideology, legislative votes,
party loyalty, incumbency and candidate background?

This is an independent research project, not a modification of
`voter-participation`. **The primary outcome is the 2026 election.** Earlier
elections (2016-2024) are training data and historical backtests. The 2026
provider counts are provisional, not certified final returns. Democratic-aligned independents
remain separate from Democratic nominees.

## Status

**Website publication is withdrawn pending further candidate research.** The
gallery and its links were removed from The Margin of Error; v2/v3 research
files and releases remain historical snapshots, not publication approval.

The old label **"118th ideology" means a Nokken-Poole score estimated from
2023-2024 congressional votes**. It covers returning legislators, not all 2026
candidates, and is not their current campaign position. Donation-based ideology,
issue positions, and voting-based ideology need separate definitions and samples.
The [source-expansion investigation](docs/CANDIDATE_DATABASES.md) reopens the
challenger, losing-candidate, religion and race coverage gaps.

The reopened source milestone retains all 470 contests. It adds independently
qualified source records, not new election fits. The
[complete research queries](downloads/2026-source-complete-queries.zip) contain
candidate-source coverage, review queues, individual CAWP observations, caucus
attrition and [separately classified state polling](docs/STATE_POLL_CONTEXT.md).
The publication hold also applies to replacement figures.

An [independent identity review](docs/CANDIDATE_IDENTITY_REVIEW.md) corroborates
four donor-name aliases and cross-office ID bridges for two candidates,
retaining all 470 contests and every unresolved lead. Its complete replay
download includes both openly licensed crosswalk originals; no new scores
are promoted into the election models.

**The corrected release is [2026-v3](results/2026-v3/analysis/report.md).**
It supersedes v2's interpretation while preserving all v2 bytes. Fresh native
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

The archived v2 report, categorical comparisons, charts and **complete derived
analysis queries** are copied into `results/2026/` for repository readers,
including held fits, evidence, fold membership and predictions. The private
local replay archive additionally contains the original source bytes. Restricted
whole workbooks are not uploaded to GitHub.

## Publication figures

The [corrected nine-figure gallery](publication/2026-v3/) includes characteristics,
caucus history and same-sample sensitivities, record/identity coverage, benchmark
sensitivity, absolute predictive error, named third-party holds and native count
clocks. Each has understated Margin of Error/Substack PNG/SVG versions,
complete plotted CSVs and explicit support/uncertainty qualifications.

Both [complete-query-set.zip](publication/2026-v3/complete-query-set.zip) and
[substack-figures.zip](publication/2026-v3/substack-figures.zip) include the complete
normalized inputs and fitted queries, not just metadata.

```bash
.venv/bin/python -m which_candidate.corrected build \
  --inputs results/2026-v3/inputs --output replay-analysis
.venv/bin/python -m which_candidate.corrected_publication \
  --inputs results/2026-v3/inputs --analysis replay-analysis --output replay-publication
```

### Archived v2 publication (superseded)

Nine figures adapt the restrained serif typography, terracotta/blue palette and
source notes from `hanshanley/uk_decline`: House and Senate characteristics,
House voting records, identity comparisons and coverage, predictive lift, and
partisan geography, plus annual House and Senate comparisons from 2016 through
2026. **2026 remains the primary result**: its saved fits and exact samples are
reused unchanged. Earlier years receive exploratory annual fits of the same
specification, not a pooled historical result relabeled as 2026. Every figure
explicitly identifies the November 7-8 provisional 2026 snapshot.

```bash
.venv/bin/python -m which_candidate.publication \
  --analysis results/2026 --output publication/2026-v2
# Optional: stage byte-verified assets into an existing local website checkout.
.venv/bin/python -m which_candidate.publication \
  --output publication/2026-v2 --stage-site ../margin_of_error
```

The committed release is [publication/2026-v2](publication/2026-v2/):

- `substack/`: warm-paper (`#F7F5F0`) PNG and vector SVG originals.
- `marginoferror/`: website-paper (`#F2EFE7`) PNG and SVG versions. PNG conversion
  changes only exact opaque background pixels; all other decoded pixels and
  dimensions are preserved.
- `plot-data/`, `captions.json`, `manifest.json`: complete plotted values,
  captions, alt text, image dimensions, input provenance and file checksums.
- `comparison/`: every annual fit, covariance, exact sample ID, term and
  within-year Holm-adjusted result, including held fits. Historical comparisons
  are exploratory: midterms use a lagged presidential benchmark, while
  presidential years use the same-year benchmark. Cohorts and maps differ;
  coefficient differences are not formal tests of change.
- [substack-figures.zip](publication/2026-v2/substack-figures.zip): upload-ready
  originals, captions, plotted data, and the complete query download.
- [complete-query-set.zip](publication/2026-v2/complete-query-set.zip): **all**
  files under `results/2026/`, including base returns, inclusion/exclusion
  decisions, features, evidence, fitted terms/covariances, predictions and fold
  membership; plus plotting data, code, tests, documentation and dependency lock.
  This is a complete derived-query release, not the restricted-source replay
  archive. Extract it and run the command above to regenerate the figures offline
  after installing the recorded dependencies.

Existing verified outputs are reused unchanged. Any changed data, code,
documentation, dependency or style recipe requires a new output directory.
The website's `/which-candidate/` gallery can embed these static figures and
downloads without JavaScript. No Substack essay is generated or published.
