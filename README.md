# Which candidate?

Which Democratic House and Senate candidates outperform their constituencies'
partisanship, and how is that associated with ideology, legislative votes,
party loyalty, incumbency and candidate background?

This is an independent research project, not a modification of
`voter-participation`. The planned historical window is 2016-2024; 2026 belongs
in a separately labeled provisional view. Democratic-aligned independents
remain separate from Democratic nominees.

## Status

The first implementation checkpoint builds an audited returns panel from held
official FEC workbooks and the existing all-district House audit. It preserves
complete native queries, candidate rows, eligibility decisions and source
hashes. It is not yet a finding about which characteristics perform better.

The current panel retains 10,123 candidate-contest aggregates across 2,858
contests. The Senate pilot has 115 eligible descriptive presidential-benchmark
gaps; these are not cycle-adjusted candidate effects. One native accounting
mismatch remains explicitly held.

See [methodology](docs/METHODOLOGY.md), [data and qualification rules](docs/DATA.md)
and [implementation milestones](docs/ROADMAP.md).

## Run

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
.venv/bin/which-candidate import-participation --source ../voter-participation
.venv/bin/which-candidate build
.venv/bin/which-candidate verify
.venv/bin/which-candidate package
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

Imports copy verified originals into an ignored, content-addressed local cache.
Builds use that cache without network or access to the parent repository.
Complete factual queries and derived tables are retained under `data/processed/`.
No GitHub repository, website or public release is created automatically.

The complete local download is `artifacts/complete-analysis.zip`, including
original inputs, every query and exclusion, derived tables, code and tests.
Extract it to rebuild independently of `voter-participation`. For the recorded
dependency versions, install with
`.venv/bin/python -m pip install -r requirements.lock -e '.[test]'`.
Dependency installation may require network access; the subsequent data build
does not.
