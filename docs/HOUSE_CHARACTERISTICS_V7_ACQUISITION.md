# V7 acquisition and qualification log

Baseline: `02b37ca0093cd75f084c501816b2f61616f38d90` (V6).
All fifteen traits and 1,284 native candidate-contest records remain in the
19,260-cell queue, including 449 Democrats and 405 eligible comparisons.
The baseline JSON protects V1-V6 outputs, historical claims and native identity.
No new effect estimates were examined before the V7 specification.

## Source-family decisions

Priority is unknown fields, nonincumbents and missing comparison groups, not
the number of downloadable pages. Lublin's complete winner tables rank ahead
of individual incumbent biographies because their explicit classifications
could add missing race and Latino-indicator groups. They cover historical
winners, not all current challengers. Full-name/state discovery is insufficient:
retain the accepted/rejected independent person-link decisions.

The House ZIP supplies 2,175 election-winner records for 2012-2020. The state
ZIP supplies 22,245 records for 2011-2020 in 33 states. Both original archives
and their included codebooks were acquired once, hashed and cached. Blank
Latino indicators in the state table remain unknown; House/state districts
and historical parties never replace native 2026 contest fields.

CongressData's retained deposit had 1,045 columns. Following the public R
package's actual data/codebook URLs acquired a different 1,229-column FST
deposit with 67,661 member-years. It was read with R 4.5.2/fst 0.9.8 in an
isolated local runtime, without installing R system-wide. The separate FST
codebook has 1,012 variable rows and does not document every newer column;
the retained PDF supplies additional provenance. Actual values take precedence
over an abbreviated description: `MILITARY="No military service mentioned"`
does not establish nonservice. Independently matched historical positive
service records add no eligible military fields beyond V6. Degree-or-equivalent
and broad pre-Congress experience indicators do not establish the missing
specific credential, occupation or office-before-2026 reference classifications.
Do not count downloading this deposit as newly usable candidate observations.

CAWP's database page and FAQ were acquired as discovery/method materials.
Both visibly linked public JSON and CSV exports redirected to missing batch
resources (404). The Ballotpedia survey-completion original returned 403.
Neither failures nor downloaded method pages are candidate evidence.
Current/historical congressional identity JSON and Pew's January 2, 2025
named-member material were already retained; they are not new acquisition.

The complete Minnesota 2019 legislative manual was acquired. Matt Little's
covered credential, attorney occupation and prior office already qualify in
V6, so do not register redundant claims. New original Gronli university and
local-newspaper interviews supply a completed BS, a dated government job,
occupational history and reported-age bounds. The 2011 Nevada biography
adds explicitly historical church membership, not verified 2026 affiliation.
Its numeric PDF glyph encoding is decoded explicitly and fragment-validated.
The 2022 Nevada biography and Michigan historical directory were already held.

The persisted `data/house-characteristics-v7-congressdata-audit.json` records
the actual reader version, selected variables, 67,661 member-years and military
code frequencies. Its candidate-level companion retains every independently
linked person reviewed, including omissions that cannot qualify nonservice.
There are no newly eligible Democratic military positives in that review.

## Measured V7 outcome

The five evidence-yielding originals yield 620 observations across 205 candidates
and 617 fields. First evidence reaches 334 fields across 203 candidates.
Democrats account for 113 candidates, 344 observations and 341 fields; 166
fields gain first evidence. Nine source-covered Democrats are nonincumbents.
This is not representative challenger coverage: 312 Democratic source-informed
fields are in the incumbent group and only 29 in the nonincumbent group.

Restricted historical race analytical values increase 54→122 and the historical
author-coded Latino indicator becomes available for 112 Democrats. Education
increases 206→207. One mixed Black/Asian record moves from the earlier CAWP
question to a hold under V7's preregistered unmixed comparison; its identities
remain factual. Therefore 183 newly analytical fields correspond to a net gain
of 182 after that hold. Dueñas's retained-evidence orthographic resolution adds
one incumbency value, 438→439, but no eligible performance sample. Ten holds remain.

Race fits expand 45→99; education 163→164. The new historical Latino-indicator
fit uses 89 candidates/27 states, not all 449 Democrats. Its +4.93 share-pp
association [2.84, 7.02] clears fifteen-test Holm correction (p=0.000701).
Its restricted held-out predictions cover 87 candidates and their gain interval
includes zero; all 89 full-cohort predictions are separately exported without
claiming a full-cohort uncertainty interval. Religion's full-cohort failure
remains 121/123. No matched predictive-gain interval excludes zero.

Age, gender, dated-current religion, profession, positive military, House service,
donor ideology, voting ideology and party unity analytical counts do not increase.
New reported age is a bound, new church membership is historical, and explicit
design/marketing does not establish the narrower business-owner family.
Office/government/military contrasts remain unavailable without explicit negative
references or defensible mutually exclusive alternative histories. Three affected
blocks are recomputed; twelve input-identical blocks are reused.

## The eleven Democratic incumbency holds

| Candidate | Actual retained-evidence cause |
|---|---|
| 219755 Eric Hafner, AK AL | At-large 00 notation plus inverted FEC name `ERIC, HAFNER`; another Florida filing does not resolve identity. |
| 219910 Angélica María Dueñas, CA29 | Unique matching FEC full tokens differ only by diacritics; reusable orthographic normalization is justified. |
| 220431 John Day, LA03 | FEC `DAY, JOHN DAVID`; omitted middle name needs an independent bridge. |
| 220434 Caleb Walker, LA03 | No corresponding candidate in the held 2026 district FEC records. |
| 220436 Conrad Cable, LA04 | FEC `CABLE, CONRAD ROBERTS`; omitted middle name needs a literal bridge. |
| 220437 Matt Gromlich, LA04 | FEC `GROMLICH, MATTHEW`; nickname bridge missing. |
| 220448 Patricia "Pat" Moore, LA05 | FEC `MOORE, PATRICIA ANN`; nickname/middle-name bridge missing. |
| 220449 Antonio Wilson, LA05 | Two distinct FEC candidate IDs; agreement in status does not establish a unique identity. |
| 220454 Patrick "Pat" Forbes, LA06 | FEC `FORBES, PATRICK WAYNE`; nickname/middle-name bridge missing. |
| 221041 Alan Bradstock, PA14 | FEC `BRADSTOCK, DAVID ALAN`; preferred middle-name bridge missing. |
| 221075 Zyon Khalifa, SC02 | Two candidate IDs and omitted middle name; ambiguity retained. |

Only Bradstock and Khalifa are performance-eligible. Resolving other holds
must not manufacture outcome eligibility. Election classification is separate
from independently verified federal service and House tenure.

## Reproduction and accounting

From the repository root:

```sh
.venv/bin/python -m which_candidate.characteristics_v7_acquisition
.venv/bin/python -m which_candidate.characteristics_v7_batch
Rscript scripts/characteristics-v7-congressdata.R \
  artifacts/characteristics-v7/congressdata-current-data \
  artifacts/characteristics-v7/congressdata-current-codebook \
  artifacts/characteristics-v7
.venv/bin/python -m which_candidate.characteristics_v7_extract
.venv/bin/python -m which_candidate.characteristics_v7_source_audit
.venv/bin/python -m which_candidate.characteristics_research --offline
.venv/bin/python -m which_candidate.house_project --evidence-only
.venv/bin/python scripts/validate-characteristics-v7.py
.venv/bin/pytest -q
.venv/bin/ruff check which_candidate tests scripts
```

R/fst are optional acquisition readers, not dependencies of normalized-evidence
or numerical replay. Source outcomes, content hashes, independent identity
decisions and every literal registered claim are retained in the V7 acquisition
JSON and normalized input snapshot. Successful originals are reused by hash;
failed attempts are not silently retried. Downloads are not deployment.
