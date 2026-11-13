# State polling context, not district candidate expectations

This compilation supports the reopened **2026** research. It does not supply
a verified 50-state current generic ballot, replace the frozen analysis, or
approve website republication.

## What was acquired

| Original packet | Field dates in 2026 | Population / n | Construct | D / R | Raw D-minus-R |
| --- | --- | --- | --- | --- | --- |
| Siena, New York, released October 28 | October 19-22 | Likely voters / 807 | Generic congressional vote intention, Q6 | 54 / 39 | +15 pp |
| Marist, Michigan, released September 30 | September 24-27 | Registered voters / 1,235 | Generic congressional vote intention, USCNGS01 | 53 / 44 | +9 pp |
| Quinnipiac, Pennsylvania, released October 7 | October 1-5 | Likely voters / 1,159 | Preferred party to control the House, Q2 | 54 / 39 | +15 pp |

Exact original packet/release URLs, bytes, SHA-256 hashes and acquisition-clock
basis are in `data/generic-ballot-sources.json`. These were published before
Election Day but acquired retrospectively on November 13. Dates/populations
are not silently pooled. All 50 states appear in the coverage file, with
unacquired states explicitly empty.

The parser checks actual question wording, party order and statewide totals.
It does not use a headline, named-candidate question or demographic subgroup.
Siena's generic normalized D share is 58.06%; Marist's is 54.64%.
Quinnipiac gets a separately named normalized **control-preference** field,
never a generic vote-intention share.

The difference matters even if a release or index calls both questions a
"generic ballot." Preference for House control is not the same response
construct as intended congressional vote.

## What these observations do not establish

A statewide House preference is not a prediction for every district. Nor is
it a candidate-free Senate counterfactual. The complete 470-contest query
output therefore keeps expected candidate vote share and WAR null.
Missing polls are not zero, and Pennsylvania is not included in the NY/MI
generic vote-intention coverage.

The published single-proportion MOEs are not confidence intervals for the
D-minus-R margin, two-party normalization or candidate residual. The residual
100 minus rounded D and R percentages is labeled accordingly; it need not
equal the sum of separately rounded minor response categories.

The official [CES download catalog](https://tischcollege.tufts.edu/research-faculty/research-centers/cooperative-election-study/data-downloads)
was checked: it lists 2025 and earlier datasets, not an acquired 2026 release.
Historical named-candidate vote-choice data are a possible backtest resource,
not current state generic-ballot observations. Quinnipiac NY/CT releases and
national polling were reviewed but not presented as additional qualifying
state generic-vote observations.

## Reproduce and inspect

```bash
.venv/bin/python -m which_candidate.generic_ballot acquire
.venv/bin/python -m which_candidate.generic_ballot build
.venv/bin/pytest -q tests/test_generic_ballot.py
.venv/bin/python -m which_candidate.source_milestone verify
```

`results/2026-poll-context/` contains all three observations, all 470 context
queries, the complete state-coverage ledger and source receipts. Acquisition
and replay are separate; changed pinned bytes stop the build.

The [complete source-query download](../downloads/2026-source-complete-queries.zip)
contains these full outputs, code, tests and provenance, not just metadata.
Whole original PDFs stay in the local cache unless redistribution is qualified.
See [candidate-source documentation](CANDIDATE_DATABASES.md) for the local-only
raw-source replay archive and publication gates.
