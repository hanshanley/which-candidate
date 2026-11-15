# Participation source context

The November 15, 2026 intake reads selected public normalized data from the
sibling `hanshanley/voter-participation` project. It does not collect new voter
records, replace the frozen analysis, or add candidate backgrounds.

## What was imported

| Output | Observations and scope |
| --- | --- |
| `aggregate-observations.csv` / `.jsonl.gz` | 6,596 source-defined rows across 48 jurisdictions: 6,450 early/mail, 135 aggregate demographic cells, eight reporting observations and three reviewed state observations |
| `state-context.csv` / `.jsonl.gz` | 51 state/DC coverage decisions, available statewide facts, demographic cells and counts of separate regional rows |
| `house-source-results.csv` / `.jsonl.gz` | 23 result-category/snapshot observations across HI-01, HI-02, WY-00 and ME-02 |
| `summary.json` / `manifest.json` | Measured counts, qualifications and complete input/output fingerprints |

These files are under `results/participation/`. Sixteen House observations
uniquely match 12 existing candidate-contest records; seven aggregate/unassigned
categories are deliberately not people. Matching requires the exact general
election contest, state, district and party, compatible name, and a unique
target/source decision. Matching does not independently verify every roster
identity.

The ten named Hawaii/Wyoming official counts equal the frozen candidate counts.
Maine retains three distinct snapshots: native initial counts quoted in a
later release, the accepted provider snapshot, and later reported RCV major-party
counts. The latter report does not supply final other/blank categories; these
remain null, not zero. Raw differences are not voter transfers or comparable
electoral swings. The unavailable full tabulation remains an access stop.

## Provenance and limitations

`data/participation-source-inputs.json` contains six complete normalized public
inputs. Each entry preserves its source-relative path, original file byte/hash
receipt, normalized JSON byte/hash receipt, and data. Rows retain exact JSON
pointers, original definitions, source URLs, dates and available publisher
receipts. Count-update, publication, retrieval and import times remain distinct;
unknown clocks are not filled from another date.

The source checkout was dirty at import. Its local HEAD was
`792e3d91609f7ee929c35b5ec15c13710db94be8`; the selected file pins, not that commit,
identify the imported content. The sibling worktree was not modified.
Different retained source vintages are not a fresh simultaneous November 15
count. Replay validates the normalized public facts, not a new extraction of
unavailable publisher originals. Private publisher HTML is not included.

The source's `ballots` values become `reported_count`, preserving their literal
definition rather than asserting unique voters. Modes, statewide/regional
geographies, editions and demographic dimensions can overlap and must not be
summed. Source-region names are not qualified district geography. No analytical
turnout percentage, district allocation or individual behavior is inferred.
All records are `model_ready: false`.

The candidate browser attaches a state context ID and any matched House
snapshots; expanding a profile shows actual statewide values and receipts.
Filtered profile CSVs export this reference and the House snapshot records.
The complete downloads include all regional rows, demographic cells, source
inputs, code, tests and documentation.

This intake adds **zero candidate background observations and zero newly
covered biographies**. Coverage remains 1,156 of 1,284 named candidate records;
128 remain uncovered. Missing fields remain education 338, professional history
219, prior office 897 and military service 1,086. Frozen trait inputs, outcomes,
analysis samples and all ten figures are unchanged.

## Supported import and replay

Ordinary replay requires neither network access, historical raw caches nor
the sibling checkout:

```bash
python -m which_candidate.house_project
```

An explicit future refresh reads the six configured source paths, validates
their contracts and pins a new normalized packet:

```bash
python -m which_candidate.participation_context --import-from ../voter-participation
python -m which_candidate.house_project
```

The import timestamp changes only during explicit import. Newly changed inputs
require a full rebuild; stale context inputs or outputs fail validation.
Neither command deploys the website.
