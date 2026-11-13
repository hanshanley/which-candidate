# Candidate returns: first research checkpoint

**These are audited inputs, not conclusions about which kinds of Democrats do better.**

| Year | Chamber | Candidate rows | Contests | Descriptive-share eligible |
|---|---|---:|---:|---:|
| 2016 | house | 1354 | 438 | 354 |
| 2016 | president | 820 | 50 | 50 |
| 2016 | senate | 213 | 34 | 32 |
| 2018 | house | 1345 | 439 | 374 |
| 2018 | senate | 195 | 35 | 29 |
| 2020 | house | 1325 | 435 | 382 |
| 2020 | president | 565 | 50 | 48 |
| 2020 | senate | 202 | 35 | 27 |
| 2022 | house | 1271 | 436 | 382 |
| 2022 | senate | 192 | 36 | 28 |
| 2024 | house | 1241 | 435 | 390 |
| 2026 | house | 1400 | 435 | 408 |

Retained 21,380 complete selected native FEC rows.
1,971 contests reconcile to a supplied native contest-total reference; 1 mismatches are explicitly held.

The Senate pilot has 115 qualified descriptive presidential-benchmark gaps. These are not cycle-adjusted overperformance, forecasts, or causal candidate effects. Missing or excluded contests remain in the full query tables.

## Remaining qualification

- Historical FEC congressional coverage currently stops at 2022.
- 2024 and provisional 2026 House rows are imported from the complete participation audit.
- This base returns stage excludes supplemental Senate outcomes; the analysis stage imports 2024/2026.
- House district benchmarks and map qualifications are added in the analysis stage.
- Senate presidential gaps are descriptive, not cycle-adjusted candidate effects.
- Candidate identities, legislative features and biographies are added in the analysis stage.

The 2026 House source is a held provider snapshot, not certified final returns. No new source acquisition or certification is implied by importing it.

## Complete tables

- `native-fec-rows.jsonl.gz`: every nonempty selected worksheet row and its cells.
- `fec-row-decisions.jsonl.gz`: every non-header row's import disposition.
- `candidate-returns.jsonl.gz` and `.csv`: every selected candidate aggregate.
- `contests.jsonl.gz` and `.csv`: every contest, accounting result and exclusion.
- `senate-benchmarks.jsonl.gz` and `.csv`: every Senate pilot decision, including holds.
- `house-audit.json`: full unchanged previous/current all-district factual query.
- `manifest.json`: exact source/code/output checksums.
