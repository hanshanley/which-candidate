# V8: national evidence, qualification and supported results

Baseline: `08339cadd6a895de29d8418c22ee337aa7e7a50a` (V7), independently
verified against local HEAD and remote main before implementation. The 489
protected historical files, all V1-V7 results, 1,284 native candidate-contest
identities and five rejected cross-contest transfers are preserved. No website
deployment is part of this release.

## What changed

Successive source-family batches register 325 claims, 176 candidate-source
records and 136 distinct document IDs, informing 320 candidate-trait cells
for 160 candidates. These are not 325 independent documents or first facts.
Qualified first evidence fills **65 previously unknown fields for 43 people**:
16 fields for 14 known Democratic nonincumbents, twelve for six Democrats whose
V7 incumbency was unresolved, and 37 fields across the other parties.
No first-informed candidate was a known V7 incumbent.
Separately, one Libertarian acquires a first normalized background observation;
that person-level source-presence measure is not the 43-person first-field count.

Already reported but unqualified fields are separate from unknown fields.
For example, education and profession gain many factual qualifications but
no first-evidence fields among Democrats. The table
`acquisition-field-changes.csv` records the exact distinction. There are forty
newly analytical all-party fields, including 27 Democratic fields. These totals
include seven retained-evidence incumbency requalifications, not seven more
acquired traits.

The full fifteen-trait comparison is
`results/house-characteristics-v8/v7-v8-trait-progress.csv`; the self-contained
report prints it, including cohort denominator, unknown count, factual and
analytical eligibility, fit and full-fit prediction support. Party, fixed-V7
incumbency and outcome-eligibility breakdowns are in
`coverage-by-party-and-incumbency.csv`. Models target Democrats; other parties'
evidence coverage is retained but they do not have Democratic association fits.

## Source-family execution and marginal results

`source-family-outcomes.csv` reports every attempted family, including failures,
retained originals, unique acquired hashes, registered claims, first fields
and analytical qualification. Family first-field counts can overlap; sixty-five
is the distinct total. The acquisition ledger preserves URLs, UTC retrieval
times, bounded attempts, resolved URLs, cached-original paths and SHA256 hashes.

1. Official Oregon and Washington editions were acquired once per relevant
   source and candidate statements deduplicated across editions. Their thirteen
   registered claims give three new analytical fields, not thirteen first facts.
   Four explicit Washington **Elected Experience: None** answers remain scoped
   office negatives; broader governmental-experience fields are not substitutes.
2. The national roster-linked campaign sweep attempted 373 pages and acquired
   359 (347 unique hashes), with fourteen failures. It covered 187 candidate
   leads in 43 states. Reviewed originals yield 169 claims and eight first fields;
   downloaded navigation shells and undated prose are not automatically eligible
   analytical records. Additional source pages supplied credentials, service
   dates and occupational meaning rather than simply renaming old observations.
3. Alaska's official candidate statements and other official statements yield
   71 claims and ten family-level first fields. Louisiana's complete 39-row
   House filing export supplies 48 literal race/gender classifications and
   41 first fields. Its source-defined Race field, including Hispanic labels,
   is not silently converted to the historical race/ethnicity estimands.
   Unnecessary contact/address fields are not analytical data.
4. FEC candidate/committee filings supply seven literal identity bridges to
   retained classifications. These qualify seven controls, not seven first
   background fields or independent service histories. Only PA14 gains both
   outcome controls; the incumbency fit rises 373→374.
5. Complete Maryland 2025 roster and archived 2024 legislative biographies,
   a dated candidate interview and national affiliation table were then reviewed.
   Boafo's supported birthday, MBA and jobs are new sources but largely
   corroborate already known values. Ryerse's Christian statement is his own,
   not the host's adjacent non-Christian statement. The public affiliation
   table says **updated November 16, 2026**: its two new named factual reports
   remain post-election holds. Existing CFE and V7 Lublin originals are not new
   acquisition. Scientist, endorsement, caucus membership and church volunteering
   are not religion categories.
6. Additional Tennessee and Colorado complete candidate guides were acquired
   through their public indexes. Burke explicitly answers **Military Background:
   No Military Background**; positive retained histories were checked for
   conflict. Colorado's El Paso guide adds literal House service/occupation
   answers; its statewide edition covers statewide offices. Chattanooga's
   November guide covers state offices rather than this House cohort.
   These inspected nonoverlaps and duplicate statements add no trait claims.
   The guide network still supplies only one Democratic military negative.
   The candidates' words are not independent verification or religious
   identification by virtue of the publisher.
7. Navy/Navy Reserve originals and a targeted VOTE411 page could not be acquired.
   Those failures are recorded; no search snippet is registered as evidence.
   Questionnaire indexes are discovery products, not complete nominee rosters
   or proof of answered background questions.

## Analysis and limitations

The fifteen-block specification, support gates, outcome, existing models and
Holm family are unchanged. Only affected numerical inputs are recomputed;
`numerical-input-reuse.json` reports reuse. The one explicit military negative
is a qualified value, not a sufficient comparison group: Democratic military
eligibility is 34, comprising 33 positives and one negative. Office, government
and military contrasts remain unavailable, not estimated null effects.

Religion's training-only nuisance-column reduction previously rejected both
Iowa rows when only the IA03 opponent-incumbency configuration was unsupported.
Row-specific estimability retains IA02 and corrects 121/123 predictions to
122/123 on the unchanged association population. IA03 is not imputed or silently
dropped. Full-population uncertainty remains unavailable; complete restricted
matched validation is a different estimand.

The historical Latino association remains 89 candidates/27 states, with
83 incumbents and six nonincumbents. Its state coverage, all included people,
sample overlap, exclusions and existing robustness checks are exported in
`historical-latino-population.json`. No all-nominee or causal interpretation
is supported. Joint D/R incumbency, historical donor ideology and this restricted
block clear Holm correction. No matched predictive-gain interval excludes zero.

## Specific remaining prerequisites

The complete 19,260-cell current matrix and four separate disposition queues
are under `results/house-characteristics-v8/remaining-*.csv`. A disposition is
not coverage. Each row retains the candidate-contest key, party, fixed baseline
incumbency, factual/analytical status, timing and actual exclusion reason.
The first three evidence queues are mutually exclusive. Missing comparison
support is a population-level flag that can overlap them; these four views are
not a partition of every candidate-trait cell.

Caleb Walker (LA03) has no matching retained FEC record; Antonio Wilson (LA05)
and Zyon Khalifa (SC02) have multiple distinct IDs without a qualified unique
person bridge. Only Khalifa remains outcome-eligible. Resolution requires
literal person/authorized-campaign evidence, not agreement among incumbent flags.

Office negatives require explicit before-November-3 office histories; four
Washington answers fail the ten-person/three-state category gate. Government
employment requires an actual non-elected job and explicit negative reference
responses, not advisory appointments or absent biographies. Military needs
additional explicit own-service negatives across at least three states.
The inspected guide network does not supply that population. Historical database
absence and blank survey fields cannot fill these reference categories.

Unknown challenger identities and affiliation require dated public
self-descriptions; birth intervals require qualified complete birth dates for
exact-age analysis. Education holds need completed credential evidence and
timing; profession holds need dated, meaningful principal occupations under
the existing families. Post-election pages do not establish pre-election facts
without independent factual timing. The per-candidate queues identify these
missing requirements rather than treating every downloaded biography as usable.
Historical member datasets cannot supply a universal challenger panel.

IA03's religion failure requires a defensible training population with the
opponent-incumbency configuration, or a separately justified methodological
amendment; it is not repaired by hiding the target or imputing a coefficient.
No such amendment is introduced here.

## Reproduction and delivery

From a checkout with the pinned environment:

```bash
python -m pip install -r requirements.lock
# Resumable acquisition/extraction, only when original caches are wanted:
python -m which_candidate.characteristics_v8_batch
python -m which_candidate.characteristics_v8_extract
python -m which_candidate.characteristics_research --offline
# Supported analysis and full local product from retained normalized inputs:
python -m which_candidate.house_project --evidence-only
# Independent numerical reconstruction:
python scripts/validate-characteristics-v8.py
# Development and integrated checks:
python -m pytest -q
python -m ruff check which_candidate tests scripts
python -m ruff format --check which_candidate tests scripts
# Extract to a previously nonexistent directory and deny networking:
python scripts/replay-characteristics-v8.py \
  --archive downloads/complete-queries.zip \
  --workdir /tmp/which-candidate-v8-replay
```

The optional browser check uses separately installed Playwright and Chromium:
`python scripts/check-characteristics-v8-browser.py`. It checks desktop/mobile,
no-JavaScript content, filters, literal source links and frozen-version navigation.

The acceptance receipt is `audits/house-characteristics-v8-validation.json`.
Report/browser: `publication/characteristics-v8/report.html`; figures and full
plotted CSV tables: `trait-coverage` and `predictive-value` in that same directory,
with PNG and SVG versions. The earlier full-project figures remain in
`publication/marginoferror/`, `publication/substack/` and `publication/plot-data/`.
The earlier root report links to V8 while frozen reports stay in place.

Both complete downloads now use GitHub release assets, not oversized Git blobs;
see `docs/DOWNLOADS.md` and `downloads/release-assets.json`. The Substack archive
contains the exact complete-query ZIP. Normalized literals, original hashes and
receipts, every frozen output, code, tests, queries and reports remain included.
Raw historical originals are not needed for the documented offline replay.
