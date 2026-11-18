# Comprehensive biographical research: unfinished

This additive pass retains all 1,284 candidates, prioritizing the 449 Democrats
and known nonincumbents. It does not replace V9 or claim comprehensive collection
because a missing field has an analytical disposition. The current counts are in
`results/biographical-research/summary.json`; the fifteen-trait before/after table
is `results/biographical-research/trait-progress.csv`.

Open `publication/biographical-research/report.html` locally. Its static,
no-JavaScript candidate browser exposes accepted facts, partial evidence,
conflicts, qualifications, source passages, original links and search provenance.
No website deployment is part of this work.

## What counts as research

Campaign-page retrieval is complete as a transport operation, not a person-level
research pass. Each candidate's ten background traits are reviewed together:
age, gender, race, ethnicity, religion, education, profession, prior elected
office, other government employment and military service.

The six source families are campaign biographies, Ballotpedia/questionnaires,
official biographies, substantive local profiles, university/employer/professional
biographies and earlier public biographies. Exact executed queries are distinct
from underlying-page follow-ups and reconstructed historical search descriptions.
An executed query whose results cannot be mapped is explicitly identified; it
cannot establish completion. Snippets alone do not qualify evidence.

The candidate-trait ledger distinguishes qualified, partial, conflicting,
identity-uncertain, timing/analytical exclusions, access failures, documented
unsuccessful searches, unresearched and structurally inapplicable cases.
Completion requires all ten traits and six families to have received a genuine
pass, with actionable leads resolved or specifically blocked. Unknown facts may
remain after a completed search; unsearched candidates are not unavailable.

Explicit identity evidence is required for sensitive background traits. School
attendance is not a degree. Internships, volunteering and advisory or union roles
do not establish paid government employment. First candidacy does not establish
no previous office. Omission, blanks and database absence do not establish
nonservice. Birth years, dated ages and intervals retain their actual precision.
Source publication, fact reference and observation dates remain separate.

## Canonical inputs and outputs

Curated `data/biographical-research*.json` journals contain accepted documents,
literal short passages, identity bridges, coded claims, actual queries, source
holds, qualifications and remaining leads. Their raw metadata is retained in
full. `data/biographical-retrievals.json` records resumable transport and cached
original pointers. Its pointers are not a promise that those originals are
redistributable or included in a public archive.

`data/biographical-research-baseline.json` pins 468 historical files, including
the scientific results and native identities. Each factual rebuild checks them.
New factual claims never silently enter a historical association or prediction.
Fitted and prediction-supported counts therefore remain explicitly unchanged.

Generated files under `results/biographical-research/` include the complete
19,260-cell CSV and compressed JSONL ledger, all-candidate research status,
remaining queue, party/incumbency breakdowns, fifteen-trait progress, provenance
and checksummed manifest. First evidence in a previously unknown field, newly
qualified existing evidence, supplementary evidence and retained-original
re-extraction are distinct. These are not interchangeable acquisition gains.

## Commands

From the repository root, with the locked environment already available:

```sh
.venv/bin/python -m which_candidate.biographical_research
.venv/bin/ruff check which_candidate/biographical_*.py tests/test_biographical*.py
.venv/bin/ruff format --check which_candidate/biographical_*.py tests/test_biographical*.py
.venv/bin/pytest -q tests/test_biographical_research.py tests/test_biographical_package.py
```

Transport resume, normally unnecessary after the recorded roster-wide run:

```sh
.venv/bin/python -m which_candidate.biographical_acquisition --workers 4
```

This reuses prior receipts and hashes, does not repeat unchanged downloads, and
does not search new biographical families or complete candidate research.
Person-level searches and reading are curated in the journals, not fabricated
by an automated query generator.

Build the **separate additive complete download**, then extract and verify it:

```sh
.venv/bin/python -m which_candidate.biographical_package --verify-offline
```

The input `downloads/complete-queries.zip` must be the frozen V9 archive with
SHA-256 `78447a60c4c1bda80714d6984a706ba7db9dce31bae04fe4fd5526b6aac1aa64`.
See `docs/DOWNLOADS.md` for its release-asset retrieval instructions. `--base`
accepts another local path with exactly that hash. The existing V9 downloads
are never replaced.

The output is `downloads/biographical-research-complete.zip`, with size, hash,
member count, protected-file verification and offline replay results recorded in
`audits/biographical-research-package.json`. It contains the complete permitted
V9 package plus all curated research journals and queries, new code/tests,
documentation, numerical ledgers and the current factual report. It is not a
metadata-only download. Large ZIPs are excluded from Git blobs.

The separately tagged **unfinished research checkpoint** is a GitHub prerelease,
not a new scientific version or a declaration that the roster pass is complete.
Retrieve its full archive into a checkout with no existing file of that name:

```sh
gh release download biographical-research-2026-11-18 \
  --repo hanshanley/which-candidate --dir downloads \
  --pattern biographical-research-complete.zip
```

The tag preserves that checkpoint's counts and inputs. Current `main` can contain
subsequent acquisition; its journals and report need not match an older tagged
archive. Rebuild a current archive rather than treating an old receipt as current.

Verify an already downloaded research archive without rebuilding its package:

```sh
.venv/bin/python -m which_candidate.biographical_package \
  --verify-existing downloads/biographical-research-complete.zip
```

Verification extracts to an isolated temporary directory, imports the extracted
code, disables Python networking and child processes, rebuilds every factual
output, and compares all manifest hashes and the manifest bytes. It also checks
all protected scientific files. Dependencies must already be installed; this
verification does not download them.

Alternatively extract the archive, create an environment using
`requirements.lock`, and run `python -m which_candidate.biographical_research`
from the extracted root. The full curated inputs are sufficient to reconstruct
the coded factual outputs without network access.

## Limits of replay and remaining acquisition

Offline coded-output reconstruction is **not** independent re-extraction of
unretained web originals. Newly reviewed copyrighted news and campaign pages
are not redistributed wholesale. The package retains bounded source passages,
structured facts, dates, URLs, queries and decisions; revisit originals only
where access and reuse rules permit. A public URL or a hash is not an acquired
original. Historical V9 permitted originals remain included unchanged.

The remaining queue is operational work, not a declaration that all unresolved
facts are externally unavailable. Continue person-level acquisition through the
roster, review extraction failures and concrete remaining leads, and rebuild
this checkpoint after substantive batches. New analytical specifications would
require separate scientific qualification and validation; this factual pass
does not manufacture new association claims.
