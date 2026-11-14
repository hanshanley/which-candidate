# 2026: the replacement analysis

The primary election is **2026**, using the pinned November 12-13 provider
snapshot, not certified returns. Historical comparisons cover 2016-2024.
This is a research replacement, **not permission to republish the website**.
Rejected v2/v3 images remain byte-identical archives.

## The answer depends on the measure and benchmark

Among 151 qualified House candidates, moving 0.5 units toward the conservative
end of the historical donor scale is associated with **+3.54 points of
D-minus-R margin** (95% sensitivity interval +1.48 to +5.60). The sample has
122 incumbents and only 29 nonincumbents. This is not a general challenger
result or a causal effect of choosing a moderate nominee.

On the identical 88-candidate map-qualified sample, the estimate is **+3.22**
using the 2024 presidential benchmark (interval -0.24 to +6.68), but **+0.81**
using the 2020 benchmark (-3.47 to +5.08). Both the outcome gap and constituency-
lean controls change with the presidential benchmark. Neither is Split Ticket WAR.

### Holding candidates fixed does not make ideology measures equivalent

The audit compares the same 100 verified Democratic House incumbents in
30 states, all with donor and prior voting scores. Controls and IDs are fixed.

| Measure/increment | Separate model: margin pp | Both measures included: margin pp |
|---|---:|---:|
| Historical donor ideology, +0.5 conservative | +3.92 [1.62, 6.21] | +3.61 [1.63, 5.59] |
| Prior voting ideology, +0.1 conservative | -2.56 [-4.34, -0.78] | -2.40 [-3.92, -0.89] |

These are audit-added exploratory tests, not independent confirmation.
Different increments are not a common effect scale. Donor coalitions and
recorded congressional positions measure different things: a single
"moderation advantage" headline would conceal their opposing associations.
`results/2026-v4/measurement-fits.jsonl.gz` retains all coefficients,
covariance, sample IDs, leverage and state deletions.

The older primary 2026 House voting estimate is -1.62 margin points per
0.1 conservative voting-score units; its six-trait Holm-adjusted p is 0.237.
The original primary tests still establish no multiplicity-adjusted finding.
Adding exploratory donor tests does not turn original tests into confirmations.

The Blue Dog/CPC estimate is also not a precise premium: eight eligible
Blue Dogs versus 65 Progressive Caucus members, with a margin interval
approximately -0.73 to +17.07. These are membership groups, not PAC endorsements.
Missing 2016/2018 rosters are unavailable evidence, not zero membership.
Changing annual cohorts and benchmark vintages prevent interpreting the plot
as a test that an advantage increased or declined.

Senate donor samples are too small and/or lose identification under state
deletion. No Senate donor headline is authorized.

## Evidence acquired, not merely located

All **470 contests** remain, including 37 held election comparisons.
There are **454 named Democratic nominees**. Sixteen contests without such a
nominee remain present, not silently dropped or labeled nonincumbents.

| Named cohort | Nominees | Qualified donor score | Pre-election 2026 biography | Prior federal voting score |
|---|---:|---:|---:|---:|
| All | 454 | 192 | 273 | 151 |
| Democratic incumbents | 183 | 160 | 126 | 149 |
| Democratic nonincumbents | 249 | 32 | 147 | 2 |
| Unknown incumbency | 22 | 0 | 0 | 0 |
| D led the two-party count | 273 | 169 | 180 | 150 |
| D trailed the two-party count | 180 | 22 | 92 | 0 |
| Two-party comparison unknown | 1 | 1 | 1 | 1 |

Count leadership is not a certified race call. Outcome groups sum to 454.
Coverage and model eligibility differ: only 151 House and nine Senate
candidates enter the main donor model after comparison and incumbency holds.

### Campaign-site biographies

Acquired Hanno Hilbig's *U.S. House (2018-2026) and Senate (2002-2026)
Candidate Websites*, DOI `10.7910/DVN/BZ2JRS`, November 2026 release,
**CC BY 4.0**. Original biography facts, crosswalk, document/segment provenance,
codebook, extraction manifest, universe and on-ballot source ledger are pinned.

The full source has 138,402 fact rows; exact FEC/name/year/state/chamber/district
qualification yields **7,252 deduplicated records**. Of 274 matched nominees,
273 have a pre-election capture. The 147 nonincumbents expand coverage beyond
eight with the older CampaignView biographies, but the sources have different
periods and definitions.

Field counts mean source presence, not verified traits: education 195;
prior elected office 172; local roots 240; occupation 240; public service 244;
military service 49. Missing extraction does not mean absence of a trait.

The publisher used Qwen extraction and machine validation, not human verification.
Aligned quotations can still describe relatives or misclassified activities.
All 7,252 records remain **not model-ready**. No religion, race or gender labels
are inferred. Public records retain field/value, URLs, document/candidate IDs,
capture dates, quote/text hashes and character offsets without republishing
full evidence quotations or website narratives.

### Historical state-legislative sources

Acquired Boris Shor's *Individual State Legislator Shor-McCarty Ideology Data,
January 2025 Update*, DOI `10.7910/DVN/SGOQ7G`, **CC BY-NC-SA 4.0**:
original Stata file, served table and codebook. Scores end in 2022, not 2025/2026,
and are not the federal voting scale. Respect the source's noncommercial/
share-alike conditions.

Also acquired Bernard Fraga, Eric Gonzalez Juenke and Paru Shah's
*Candidate Characteristics Cooperative (C3) 2018 Data*,
DOI `10.7910/DVN/VHAPHV`, **CC0 1.0**: original Stata file, table and codebook.
Its 14,775 rows cover 2018 state-legislative candidates in 45 states, not
2026 congressional nominees. Contributor-coded racial categories are not
equivalent to this project's dated self-identification standard.

Together these supply **129 historical identity leads**. Same state/party/name
is a review lead, not an independently verified career bridge. No state score
or sensitive identity label is promoted automatically.

## Model, uncertainty and provenance

The donor outcome is congressional minus presidential Democratic two-party
share. Controls are constituency lean, lean squared and known D/R incumbency.
Redundant nuisance columns are removed without changing the model column span.
Share estimates/intervals are multiplied by two for D-minus-R margin points;
the donor export names both interval units explicitly.

DIME v4 scores are retrospectively acquired historical recipient scores,
using even election cycles through 2024, not a prospective 2026 prediction.
FEC/state/party matches require consistent names. All 17 name discrepancies
are excluded in this specification, including four aliases independently
corroborated elsewhere: not all 17 are unresolved. Cross-office leads remain
in the complete queries, not silently promoted.

Intervals use t(G-1) times the larger of CR1 and full state-deletion CV3 errors.
Full-rank deletions are required. Support requires at least 30 candidates,
ten states and maximum leverage below 0.8. Intervals are pointwise/unadjusted
and omit benchmark-estimation uncertainty. These safeguards do not establish
causal identification or calibration.

The n=29 nonincumbent diagnostic remains in full in CSV, but is not drawn as
supported evidence. Sensitivities are not independent replications. Prior
federal voting covers 2023-2024 for 2026; party defection uses qualifying votes
before November 3, 2026, not full-session leakage.

Inherited candidate predictions are nested under `archived_prediction_provenance`,
not recomputed or used in v4. Current fits use updated provisional counts.
Historical fits are unchanged. V4 does not claim a new calibrated forecaster.

## Reproduce and inspect

```bash
# Original-source verification and complete joins (requires acquired cache).
.venv/bin/python -m which_candidate.rebuild acquire
.venv/bin/python -m which_candidate.rebuild build --output new-original-build

# Public normalized-query replay, without a raw narrative corpus.
.venv/bin/python -m which_candidate.rebuild replay --output replay-analysis
.venv/bin/python -m which_candidate.rebuild_publication --output replay-figures
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

Publisher MD5 for Dataverse tabular data applies to uploaded Stata bytes, not
the served TSV. Original MD5/size and transformed SHA256/size are verified
separately. Invalid-calendar, election-day and later captures cannot qualify.

The complete-query ZIP includes every result/query directory, evidence facts,
exact samples/covariates/holds, historical leads, source receipts, eight figure
datasets/captions, code, tests, source ledgers, docs, skill and dependency lock.
The Substack ZIP embeds that exact query ZIP. Public replay recomputes fits/
coverage from verified normalized records; it does not recreate machine
extraction or independently human-verify the source coding.

Eight individually inspected charts have both Substack and Margin of Error
PNG/SVG variants, CSVs and alt text. Non-background PNG pixels are identical
across themes. Canonical files are 2000 x 1300; reduced previews are review
artifacts, not substitute analyses. See `audits/2026-v4/` for the critique
and verification evidence.

## Remaining research limits

Reviewed occupation/education/military traits, all-nominee religion/race
self-identification, independent state-career bridges, certified counts,
compatible district religion context and a complete direct 50-state
generic-ballot dataset remain unresolved. Machine extraction, census proxies,
winner-only identities and House-control-preference questions do not close
these gaps or establish that a characteristic has no association.
