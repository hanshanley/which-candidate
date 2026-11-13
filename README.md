# Which candidate?

Which Democratic House and Senate candidates outperform their constituencies'
partisanship, and how is that associated with ideology, legislative votes,
party loyalty, incumbency and candidate background?

This is an independent research project, not a modification of
`voter-participation`. The historical window is 2016-2024; 2026 belongs
in a separately labeled provisional view. Democratic-aligned independents
remain separate from Democratic nominees.

## Status

The implemented analysis combines audited returns, election-map presidential
benchmarks, dated candidate identities, lagged Voteview records and authorized
official biographies. It fits chamber-specific associations for 2016-2022 and
chronological, state/person-held-out validation through 2024. The analysis
retains 1,607 eligible development comparisons and 420 eligible 2024 comparisons.

Preliminary results identify incumbency as the strongest recurring association.
They do not establish a broad moderation or party-defection advantage. These
are observational comparisons, not causal nominee-replacement effects.

**In progress:** expanded religion categories and race/ethnicity comparisons,
adjusted for constituency composition. Complete Census racial/Hispanic-origin
tables and Pew member-religion lists are acquired and pinned. Census does not
collect religious affiliation: religious context requires a separate, explicitly
qualified source. Unknown identities are never inferred from names or photos.
The expanded models and final analysis release are not complete yet.

See [methodology](docs/METHODOLOGY.md), [data and qualification rules](docs/DATA.md)
and [implementation milestones](docs/ROADMAP.md).

## Run

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/which-candidate import-participation --source ../voter-participation
.venv/bin/which-candidate build
.venv/bin/which-candidate acquire-research
.venv/bin/which-candidate import-2024 --source ../voter-participation
.venv/bin/which-candidate build --output data/returns-v2
.venv/bin/which-candidate analyze
.venv/bin/which-candidate verify
.venv/bin/which-candidate package
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

Imports copy verified originals into an ignored, content-addressed local cache.
Builds use that cache without network or access to the parent repository.
Complete factual queries and derived tables are retained under `data/processed/`.
The GitHub repository is private. Raw caches and private replay archives are
excluded from Git; no website or public data release is created automatically.

The complete local download is `artifacts/complete-analysis.zip`, including
original inputs, every query and exclusion, derived tables, code and tests.
Extract it to rebuild independently of `voter-participation`. For the recorded
dependency versions, install with
`.venv/bin/python -m pip install -r requirements.lock -e '.[test]'`.
Dependency installation may require network access; the subsequent data build
does not.
