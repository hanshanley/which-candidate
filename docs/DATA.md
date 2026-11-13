# Inputs and complete outputs

`data/sources.json` pins four held FEC workbooks (2016, 2018, 2020 and 2022)
and the complete 435-district participation audit. Each receipt records the
original URL, original retrieval time, SHA-256, byte length and cache path.
Imports verify the parent receipt before copying; subsequent builds need
neither the parent repository nor a network connection.

The FEC import covers House and Senate general-election fields in the 50
states, plus presidential fields in 2016 and 2020. DC and territories are
retained in native queries but excluded from this constituency panel.
Primary-only rows remain in the native queries and disposition table.
The House audit supplies 2024 and provisional 2026 endpoints, not independent
certification, verified candidate identities or qualified district boundaries.

## Tables

| File in `data/processed/` | Contents |
|---|---|
| `native-fec-rows.jsonl.gz` | Every nonempty row of selected worksheets, with source, sheet, one-based row and native cells. The selected schemas fit within the 40 imported columns; the original workbooks are also packaged in full. |
| `fec-row-decisions.jsonl.gz` | Every non-header row, including excluded jurisdictions, primary-only candidates, combined references, accounting choices and unresolved scopes. |
| `native-contest-total-references.jsonl.gz` | Native district/state total references and separately labeled noncandidate choices. Noncandidate choices are not additional total references. |
| `candidate-returns.jsonl.gz`, `.csv` | Candidate-within-contest aggregates, literal party lines, source name aliases, votes, source-row pointers, native incumbency markers and qualification issues. These are not verified cross-election people. |
| `contests.jsonl.gz`, `.csv` | D/R/other totals, noncandidate-choice accounting, native-total comparisons, nominee counts, source status and every eligibility/exclusion decision. |
| `senate-benchmarks.jsonl.gz`, `.csv` | Every historical Senate pilot decision, including excluded contests and unavailable benchmarks. |
| `house-audit.json` | The unchanged complete imported all-district factual query. |
| `coverage.json`, `report.md` | Coverage and outstanding qualifications, not characteristic-effect findings. |
| `manifest.json` | Input-manifest, package-code and output-file checksums. |

JSONL gzip files have one complete JSON object per line. CSVs expose the union
of fields from all sources; lists and objects are JSON-encoded cells. Nulls
mean unavailable, not zero. Source-row pointers identify native evidence;
JSON pointers identify the corresponding House audit record.

## Accounting and eligibility

Fusion totals add component party lines once. Combined totals are references,
not extra votes. Unknown counts and unopposed labels are not zero. A source
FEC ID is not independent identity verification; conflicting party labels or
names are retained and held. Generic write-ins are not named nominees.
"None of These Candidates" and unnamed write-ins are accounting choices,
not invented candidates.

The 2020 Montana Green candidate rows have `#` in the general field and an
explicit native note that they were removed from the ballot by court order.
The tightly scoped import rule retains both native rows with disposition
`removed_from_general_ballot_native_note`; it neither invents zero votes nor
mistakes them for general-election candidates with unknown totals. An
unexplained `#` remains an unknown count.

The held Texas 2020 presidential worksheet has 460 more votes across its rows
than its stated state total. The five small named write-in counts
(205, 49, 36, 56 and 114) sum to its 460-vote "Scattered" row, suggesting an
overlapping subtotal. That arithmetic alone is not sufficient evidence to
silently reclassify a source row. The original data and mismatch remain visible,
and the contest is held from the benchmark pilot.

The FEC's separate official presidential summary also reports the 460
"Scattered" total. Its existence does not independently establish additive
scope for the expanded workbook:
`https://www.fec.gov/resources/cms-content/documents/2020presgeresults.pdf`.
The Texas historical presidential page returned HTTP 403 during review;
access was not bypassed.

Specials have unqualified dates rather than being silently assigned the regular
election date. Native general-election rows with later general runoffs remain
held; the importer does not mix their counts or represent the first stage as
the final result. Louisiana congressional stages and unresolved ranked-choice
rounds are held. These rules deliberately sacrifice coverage rather than
invent comparability.

## Senate pilot and future analysis

The descriptive gap is Democratic Senate two-party share minus Democratic
presidential two-party share in the same state. Presidential nominees are
identified by the documented national nominee FEC IDs, not every native D/R
label. The pilot uses 2016/2020 presidential results in those cycles and the
preceding presidential result in 2018/2022.

Units are percentage points of two-party **share**; doubling the gap gives
percentage points of D-minus-R **margin**. Midterm gaps are not cycle adjusted.
No candidate ideology, legislative votes, biographies, demographic voter
behavior or causal nominee effects are estimated at this checkpoint.

## Reproduction and packaging

An unchanged build verifies every output checksum and returns a no-parse
no-op. Changed inputs or package code require a new output directory; an
existing version is never silently overwritten.

`which-candidate package` includes the full selected cached originals, complete
native and derived queries, audit, decisions, receipts, Python code, tests,
documentation and dependency lock. It is not a metadata-only archive.
The package is local; creating it does not publish to GitHub or elsewhere.
Original source attribution and any applicable redistribution restrictions
remain in force; this project does not grant rights over upstream material.
