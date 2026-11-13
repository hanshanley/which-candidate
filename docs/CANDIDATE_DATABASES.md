# Candidate database expansion: research hold

The website analysis is withdrawn. This investigation expands the evidence
behind the **2026** candidate universe; it is not a new election model, approval
to republish, or a claim that the missing-characteristic problem is solved.
Frozen v2/v3 outputs remain unchanged.

## What was actually acquired

| Source | Acquired contents | Actual overlap with 2026 study |
| --- | --- | --- |
| Stanford DIME v4 | Complete 479,502-row recipient/candidate file, activity through 2024, and codebook | 210 exact candidate FEC IDs; 209 usable historical donor scores |
| CampaignView | Complete 3,655-record index and all 144 matching detailed profiles | 141 distinct candidates with historical campaign biographies |
| Hilbig candidate websites | Complete 9,848-row collection-attempt roster | 571 matching candidate-year attempts; 187 candidates have a recorded capture |
| Rutgers CAWP | Complete 939-row 2026 women-candidate CSV and its explanatory page | 194 unique contextual matches requiring identity review |
| CAWP individual winner tables | Two public House/Senate embedded tables with 42 individual records | 35 contextual Democratic-nominee race observations, winner-only and retrospectively acquired |
| Existing Pew/CQ lists | Reused five pinned congressional religion lists and congressional identity crosswalks | 167 candidates have at least one dated positive religion observation |
| Direct self-descriptions | Two pinned campaign/personal biographies, plus two reviewed CampaignView biographies | Four separately qualified religion observations; not a representative sample |

These are **contests/candidate-election observations**, not an assertion that
every candidate is a unique person across offices. Acquisitions were completed
November 13, 2026. A source's activity year, publication date, retrieval date,
and election being studied are different clocks.

Every retained source has a byte count and SHA-256 pin in
`data/candidate-database-sources.json` or `data/research-sources.json`.
An adopted existing download uses its file modification time and explicitly
records that clock basis; it does not invent an original HTTP retrieval time.
There are no recorded unresolved HTTP failures in the acquired-source manifest.
This does not mean every investigated outside database was accessible.

## Coverage, including the hard cases

| Cohort | Contests | Historical donor score | Historical campaign bio | Website capture recorded |
| --- | ---: | ---: | ---: | ---: |
| Entire retained universe | 470 | 209 | 141 | 187 |
| Named Democratic candidates | 454 | 209 | 141 | 187 |
| Known federal incumbents | 183 | 177 | 133 | 167 |
| Known non-incumbents | 249 | 32 | 8 | 20 |
| Named two-party winners | 273 | 186 | 135 | 172 |
| Named two-party losers | 180 | 22 | 5 | 14 |
| v3-eligible comparisons | 433 | 200 | 133 | 178 |
| House v3-eligible comparisons | 405 | 190 | 133 | 168 |
| Senate v3-eligible comparisons | 28 | 10 | 0 | 10 |

The remaining 38 contests have unknown incumbency; 22 have a named Democrat.
Sixteen contests lack a named Democrat. Those contests must not become
"winning Democrats" through a default boolean. One named candidate additionally
lacks a usable two-party outcome. All are retained and separately grouped.

The new data do **not** solve selective coverage. Only 32 of 249 known
non-incumbents have exact-ID donor scores, and only eight have CampaignView
biographies. The winner/loser contrast is substantial. Do not fit a complete-case
model and describe it as a result about all Democratic nominees.

There are 151 available prior voting scores across all retained contests, and
132 in the v3-eligible House cohort. These are **field-availability counts**,
not the earlier 131-person primary ideology-model sample, which has additional
complete-case requirements. Sixty donor scores occur where no prior voting
score is present; these are different measures, not 60 interchangeable additions
to a voting-score regression.

## Distinct meanings of "ideology"

**Prior congressional voting.** The 118th Congress ran from 2023 to 2024.
The old field is Voteview's Congress-specific first-dimension Nokken-Poole
estimate, scaled in the existing model per 0.1 rightward increment. It is not a
2026 campaign-position score, not a percent of votes against Democrats, and
not available to every challenger. Current-Congress party unity is a different
measure, with its own cutoff and denominator.

**Donation-received ideology.** DIME's `recipient.cfscore.dyn` estimates a
cycle-specific ideological position using donation-received patterns and donor
scores. Higher scores are more conservative on that scale. It is not a
legislative voting record or a causal measure of moderation.

The join uses `Cand.ID`, the FEC **candidate** identifier, not `FEC.ID`, which
identifies a committee. Qualification requires the exact ID, state, Democratic
party code, candidate recipient type, an integer cycle no later than 2024,
one Bonica person ID, and a finite, non-conflicting latest-cycle score. An absent
latest score does not silently fall back to an older score. Giver counts remain
available for a future prespecified support threshold.
The complete matched source rows retain the original fields for audit, including
DIME's automatically inferred gender column. That column is not used as a
candidate identity feature.

Seventeen exact-ID matches need name/alias review. All imported scores are
marked `model_ready: false`: this is coverage acquisition, not model approval.
The file was obtained after the 2026 election and is not a verified historical
as-of vintage. Its old-year records cannot automatically be used as genuinely
prospective historical predictors.

**Campaign issues.** CampaignView biographies/platforms cover 2018, 2020 and
2022. Hilbig's roster covers House 2018-2024 and Senate 2002-2024. The roster
confirms collection attempts, not that this project acquired the underlying
archived text or that it is usable. Topic attention is not policy stance;
neither source supplies a validated, current 2026 ideology score.

## Religion: actual evidence and a confirmed matching problem

The old identity routine unnecessarily gated demographic evidence on current
incumbency and the target chamber. Person-level religious evidence can remain
relevant after retirement or a House-to-Senate candidacy, even though
chamber-specific voting scores must stay separate.

The new observation table resolves existing Bioguide identities against **all**
held, pre-election Pew/CQ observations in the candidate's state, without
requiring the same chamber. It recovers dated positive evidence for five
candidates whose v3 religion label is unknown:

| Candidate | Last positive held observation | Literal source category |
| --- | --- | --- |
| Colin Allred | January 3, 2023 | Methodist |
| Ben McAdams | January 3, 2019 | Mormon |
| Elaine Luria | January 4, 2021 | Jewish |
| Chris Pappas | January 2, 2025, while serving in the House | Orthodox |
| Sherrod Brown | January 3, 2023 | Lutheran |

Every source observation, including nonresponses and changes, is preserved.
Older evidence is **not** silently carried forward as a current affiliation.
The new table does not change frozen v3 classifications or reuse House
ideology as Senate ideology.

A separate, explicitly nonrepresentative four-person review records:

- Lou Correa: explicit Catholic congregation membership in a 2022-labelled
  campaign biography; a historical affiliation.
- Vanessa Enoch: explicit Christian self-description in a 2022-labelled
  biography; **Christian, unspecified**, not automatically Protestant.
- James Talarico: explicit Presbyterian religious-role self-description in his
  own campaign biography.
- Adam Hamilton: his own biography describes his founding/pastoral role at a
  United Methodist congregation; this records clergy affiliation, not a claim
  to know every private belief.

The last two pages were acquired after Election Day and have no verified
pre-election publication timestamp. All four observations are therefore
excluded as pre-election predictors. A year label on CampaignView is not an
archival timestamp. Quotes are short, checked against pinned originals, and
accompanied by the original URL and source hash.

There remain 292 named candidates with unknown v3 religion and 400 with unknown
v3 race. These are **unchanged v3-label counts**, not counts after adjudicating
the new observations. The complete identity-review queue has 404 candidates,
not just prominent winners.

## Cross-office identity leads: not accepted joins

Searching the complete donor file also finds 57 candidate contests with
plausible alternate-ID records, including 51 known non-incumbents and 15 Senate
contests. Examples include state-office histories and new federal FEC IDs for
Mary Peltola, Chris Pappas, James Talarico and Abdul El-Sayed.

These are name/state/party research leads, not verified identities. They are
exported in full with source rows, original candidate IDs, Bonica IDs, cycles
and scores. None is automatically substituted into the accepted score.
Verification requires an independent crosswalk or documented office/career
bridge, and examination of homonyms, party changes and duplicate identities.
The 139 federal seat/FEC-prefix inconsistencies in the original donor file
may include legitimate cross-office careers; they are not all presumed errors.

## Race, ethnicity and constituency context

The acquired CAWP CSV is useful for current candidate-roster checks, including
losing candidates. Its actual columns contain **no race or religion field**.
It is a women-candidate source, not a complete all-gender nominee universe.
Absence is not a male label; contextual name/state/office/district matches are
not automatically promoted to stable-ID identities.

The separately acquired individual winner embeds **do** contain a racial
identification field. They are parsed as data, without executing embedded
scripts or accessing hidden endpoints. All 42 source rows are retained in
`cawp-reported-race-source-rows.jsonl.gz`, including unmatched and Republican
records. The 35 contextual Democratic matches preserve literal multiple
identities rather than forcing exclusive categories. They are source-reported
classifications, not independently verified personal self-reports, and remain
unpromoted. Winner-only evidence must not become an all-nominee race comparison.

Use explicit, dated public identification or appropriately qualified official
positive evidence. Preserve multiple identities and separate Hispanic origin
from racial categories. Do not infer identity from photos, surnames, parental
origin, religious advocacy, a school's name, or missingness. A historical CAWP
report used White imputation in some cases; that rule is not adopted here.

Existing Census composition controls describe **residents**, not voters.
Census does not collect religion. Compatible 2026 constituency religion
composition remains unresolved and must use separately documented sources.
Old-map district religious estimates cannot silently become 2026 map controls.

## Additional databases investigated

| Source | Actual disposition | Appropriate next use |
| --- | --- | --- |
| Vote Smart CandidateBio | Official schema identifies a religion field; bulk API needs approved access. No key or complete dataset acquired. | Seek legitimate approved access; do not claim measured coverage. |
| Candidate Characteristics Cooperative | 2018 DOI located; actual data/schema not acquired. | Acquire an authorized copy and audit field-coding practices, especially inferred demographic labels. |
| Shor-McCarty | Newer individual-level catalog identified; data not acquired. Author's public data page also documents an older 1993-2020 release. | Obtain the documented vintage, resolve state-legislator IDs, keep its scale distinct. |
| Hilbig full website corpus | Public roster acquired; full text/panels not acquired. | Acquire permitted text with source URLs, capture dates and quality flags; use pre-election variants. |
| KnowWho Candidate Data Service | A 2026 primary report documents an existing candidate service; commercial/permissioned access not acquired. | Establish actual fields and terms; do not assume religion is supplied. |
| Reflective Democracy / Who Leads Us | Site under construction/password-protected. | Use an authorized public historical release or request access; no bypass. |
| Candidates in American General Elections | Historical results catalog identified, not an all-characteristics file. | Historical roster reconciliation, not a substitute for biographies. |

Blocked access is recorded, not treated as proof that the data do not exist.
No purchases, registrations, outreach or access-control workarounds were made.

## Reproduce the coverage build

From the project root, after the existing dependency installation:

```bash
.venv/bin/python -m which_candidate.candidate_databases acquire
.venv/bin/python -m which_candidate.candidate_databases build
.venv/bin/pytest -q tests/test_candidate_databases.py
.venv/bin/ruff check which_candidate/candidate_databases.py tests/test_candidate_databases.py
.venv/bin/ruff format --check which_candidate/candidate_databases.py tests/test_candidate_databases.py
```

`acquire` performs network access; `build` verifies and reads held sources only.
The five Pew lists and congressional crosswalks use the existing pinned research
cache. Source hash/size mismatches stop replay. The full parsed 2026 input
universe, original query archive, annotations and source manifests are
fingerprinted in `coverage.json`.

All 470 evidence queries, complete matched original donor rows, matched
CampaignView index rows, all CAWP source rows, website attempts, cross-office
leads, identity-review rows, dated observations and receipts are retained under
`results/2026-source-expansion/`. There is no metadata-only substitute download.
Raw CampaignView narratives remain local until redistribution terms are
established; the public outputs retain text hashes/counts, not full narratives.

### Complete downloads and broader verification

The [complete-query download](../downloads/2026-source-complete-queries.zip)
also includes all 470 polling-context queries, frozen input queries, fitted
membership sample IDs, source rows, code, tests, documentation and receipts.
It is not a metadata-only package. The public ZIP omits whole raw biographies,
codebooks and other originals whose redistribution has not been established.
It must not be described as a self-contained raw-source replay.

```bash
.venv/bin/python -m which_candidate.generic_ballot build
.venv/bin/python -m which_candidate.source_milestone verify
.venv/bin/python -m which_candidate.source_milestone package
# Local-only complete original-source replay archive:
.venv/bin/python -m which_candidate.source_milestone package \
  --include-cache --output artifacts/2026-source-replay.zip
```

Verification checks every contest is present once, disables socket connections,
regenerates both source layers and requires identical bytes. Extract the local
archive and run the same `verify` command to check independence from the
original checkout. Raw-original ZIPs are confined to ignored `artifacts/`.
The receipt is `audits/2026-source-verification.json`.

### Explain the caucus sample instead of copying a WAR chart

`caucus-membership-decisions.jsonl.gz` retains each source roster entry, its
matched nominee, eligibility reasons and actual frozen-model participation.

| 2026 membership group | Source roster | Matched House nominees | Eligible v3 | Frozen Blue Dog/CPC model |
| --- | ---: | ---: | ---: | ---: |
| Blue Dog | 10 | 8 | 8 | 8 |
| Progressive Caucus | 101 | 79 | 73 | 65 |

Mike Thompson and Jared Golden are not matched to flagged 2026 nominees.
Eligible races can still lack the frozen model's structural support. Membership
roster timing is retrospective and retained explicitly. PAC endorsements are
different populations from membership. This accounts for our sample, not the
user-supplied chart's n=12 Blue Dogs or exact Split Ticket WAR. Its underlying
candidate dataset/model has not been acquired; it cannot validate our residuals.

### Substantive and visual gates before replacement charts

The earlier figures gave selective, uncertain comparisons too much visual
authority. A styling pass alone would not fix that. Replacement figures need
plain-language measures, exact sample sizes and missingness, separation of
observations from modeled associations, share-versus-margin units, uncertainty,
common support and identical candidate samples when comparing benchmarks.
Historical panels must disclose cohort and map changes.

Do not headline sparse identity categories, rank unlike ideology scales or call
a residual a causal nominee effect. Avoid overloaded multi-panel figures,
unexplained Congress-number labels, decorative annotations and tiny footnotes.
This source milestone does not approve new figures or website republication.

## Attribution and source references

- Bonica, Adam (2024). *Database on Ideology, Money in Politics, and Elections:
  Public Version 4.0.* Stanford University. Catalog:
  <https://data.stanford.edu/dime>. Catalog license: ODC-BY 1.0; retain attribution.
  CFscore method: Bonica (2014), "Mapping the Ideological Marketplace."
- Porter, Rachel, Colin R. Case and Sarah A. Treul. *CampaignView*:
  <https://www.campaignview.org/download>,
  <https://doi.org/10.7910/DVN/JIEAPT>.
- Hilbig, Hanno (2026). *U.S. House (2018-2024) and Senate (2002-2024) Candidate
  Websites*, version 2.0: <https://www.hannohilbig.com/candidatewebsites/>,
  <https://doi.org/10.7910/DVN/BZ2JRS>. Only the public attempt roster is imported.
- Center for American Women and Politics, Eagleton Institute of Politics,
  Rutgers University. *Women Candidates in 2026*:
  <https://cawp.rutgers.edu/data/candidates-women-candidates-2026>.
  Non-commercial reproduction requires clear visible credit and retention of
  applicable footnotes; commercial reproduction requires written permission.
  The full source rows are retained without removing their columns.
- Pew Research Center, *Faith on the Hill*, with CQ office questionnaires;
  individual publication dates and original URLs are in the reused receipts.
- Voteview measure documentation:
  <https://voteview.com/articles/data_help_members>.
- Vote Smart schema: <https://api.votesmart.org/docs/CandidateBio.html>.
- Candidate Characteristics Cooperative 2018:
  <https://doi.org/10.7910/DVN/VHAPHV>.
- Shor-McCarty newer catalog: <https://doi.org/10.7910/DVN/SGOQ7G>;
  author's data page: <https://americanlegislatures.wordpress.com/data/>.
- KnowWho use in a 2026 candidate report:
  <https://futurecaucus.org/wp-content/uploads/2026/10/On-The-Rise-2026-Digital-Report.pdf>.

Full campaign narratives, restricted commercial databases and unverified
demographic labels are not licensed for redistribution merely by being
discoverable. Website publication remains on hold.
