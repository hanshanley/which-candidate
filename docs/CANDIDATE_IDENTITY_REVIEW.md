# Independent 2026 donor-identity review

This extension follows up the source-expansion review queue rather than fitting
another selective-sample election model. Website publication remains withdrawn.
The frozen v2/v3 analyses and source-expansion classifications are not changed.

## What the independent check establishes

Both current and former congressional-member crosswalks are pinned originals
from `unitedstates/congress-legislators`, licensed CC0. A target needs a unique
FEC-to-Bioguide link, agreement with any frozen Bioguide identity, and a
corroborated name and state. A source-name discrepancy is cleared only when the
literal donor-record name matches an independently recorded crosswalk name or
alias. Missing nicknames are not invented.

For alternate candidate IDs, both the target FEC ID and donor-source FEC ID
must map uniquely to the same Bioguide person. The donor-source name must also
match that person's recorded aliases. Shared names, states or donor scores
alone never establish the link.

The complete review retains **all 470 contests**, including missing nominees:

| Review | Independently corroborated | Still held |
| --- | ---: | ---: |
| Seventeen exact-ID donor-name discrepancies | 4 | 13 |
| Alternate-ID lead rows | 6 | 218 |
| Candidates with alternate-ID leads | 2 | 55 |

The four corroborated aliases are Hank Johnson, Gabe Vasquez, Jim Clyburn and
Bobby Scott. The six independently bridged source rows concern Glenn Ivey
and Chris Pappas. Source rows repeat candidates across cycles; six rows do not
mean six additional people or six newly qualified scores.
The two-candidate count means at least one independently bridged row; other
leads for the same person can still remain held.

The remaining leads are preserved, not rejected as false. Many state-office
identifiers have no entry in a congressional FEC crosswalk. These need a
different independent source or documented official career bridge.

**No new model-ready scores are created.** Identity corroboration does not
validate the donor score's vintage, support, comparability or prospective
availability. The historical DIME acquisition remains retrospective. There are
no new religion/race labels, regression fits or publication figures.

## Complete queries and replay

The complete candidate download is
[`candidate-identity-queries.jsonl.gz`](../results/2026-identity-review/candidate-identity-queries.jsonl.gz).
It includes every contest, all alias decisions and all 224 alternate-ID lead
decisions, not just successful matches. `summary.json` records complete input
fingerprints and both independent crosswalk receipts.

The [complete replay ZIP](../downloads/2026-identity-complete-replay.zip)
also includes the full input queries, matched donor rows, both CC0 crosswalk
originals, code, the focused tests and dependency lock. It replays this identity
review, not the whole original election-analysis pipeline. Whole CampaignView
narratives and other restricted originals are not included.

From the project root:

```bash
.venv/bin/python -m which_candidate.candidate_identity_review
.venv/bin/pytest -q tests/test_candidate_identity_review.py
# Create a new, exclusively written replay package:
.venv/bin/python -m which_candidate.candidate_identity_review \
  --package downloads/2026-identity-complete-replay.zip
```

The build reads local pinned originals only. Changed crosswalk bytes, duplicate
contest identities, missing contests, inconsistent target identities and
misattributed source rows fail validation. It cannot silently replace a frozen
candidate identity or promote a score into an election model.

Underlying donor records are from Adam Bonica's *Database on Ideology, Money
in Politics, and Elections*, version 4, activity through 2024, under the
Open Data Commons Attribution License 1.0. See
[`CANDIDATE_DATABASES.md`](CANDIDATE_DATABASES.md) for acquisition qualifications,
attribution and source-selection limitations.
