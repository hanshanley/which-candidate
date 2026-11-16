# All-candidate House information

The current research scope is the **2026 House**. The pinned November 12-13
provider queries contain 1,426 listed choices across all 435 districts:
1,284 named candidate-contest records and 142 aggregate write-in or
none-of-the-above choices. These are provisional provider returns, not a
certified list of every ballot-qualified or write-in-eligible person.

The inventory includes Republicans, other parties, losing candidates and
multiple Democrats in the same contest. The existing performance panel selects
422 Democratic candidates, a different population from the 449 Democrats
listed in these native returns. A multi-candidate contest does not acquire an
eligible D-versus-R performance outcome merely because it has an inventory row.

## What is actually supplied

Current source-qualified coverage:

| Information | All named candidates | Democrats | Republicans | Other listed parties |
| --- | ---: | ---: | ---: | ---: |
| Roster entries | 1,284 | 449 | 433 | 402 |
| Candidate-ID links | 983 | 428 | 397 | 158 |
| Campaign URLs | 703 | 373 | 315 | 15 |
| Pre-election campaign biography records | 467 | 278 | 186 | 3 |
| Historical CampaignView biography records | 87 | 34 | 53 | 0 |
| Historical campaign-site factual extractions | 184 | 95 | 89 | 0 |
| Official candidate-supplied voter-guide profiles | 30 | 11 | 8 | 11 |
| Reviewed campaign/official/directory/institution profiles (candidate records) | 601 | 166 | 173 | 262 |
| Dated Pew/CQ religion observations | 352 | 179 | 172 | 1 |
| Member-authorized or official member backgrounds | 362 | 184 | 177 | 1 |
| Positive House Historian identifications | 101 | 89 | 12 | 0 |
| Any downloadable background observations | 1,156 | 449 | 432 | 275 |
| Name-qualified historical donor scores | 370 | 192 | 178 | 0 |
| Prior federal voting scores | 293 | 149 | 143 | 1 |

Rows overlap and must not be added. **128 candidate records still lack downloadable
background observations.** An observation can be historical, machine-extracted,
candidate-supplied or an explicit unknown questionnaire response; it is not a
complete verified biography. One legacy campaign-corpus record and the separately
reviewed biographies were captured after Election Day; those observations are
retained but are not pre-election features. Native "Write-In" records remain
in the other-party denominator even
when their dated FEC registration or campaign corpus records a major party.

### November 16: targeted Democratic background research

The baseline at `c23678f` was independently recomputed from candidate profiles:
**449 Democratic records, 44 missing education, 25 missing professional history,
six overlapping gaps and 63 distinct targets**. Exact candidate/contest/name/
state/district/party identities are pinned in
`data/democratic-background-gap-baseline.json`, with the complete baseline
coverage table and frozen-analysis hashes.

All 63 targets now have reviewed source evidence or a field-specific remaining
gap. **42 education and 25 professional-history gaps were filled across 61
candidates.** This adds 84 normalized observations from 78 factual source
annotations; six additional sources supply identity/gap context only. There are
81 new distinct acquisition receipts, not 81 newly covered people. All Democrats
already had some acquired background: newly covered people is **zero**.

| Democratic field | Available | Missing |
| --- | ---: | ---: |
| Education | 447 | 2 |
| Professional/career history | 449 | 0 |
| Prior office | 211 | 238 |
| Military service | 79 | 370 |

These are field-availability counts, not counts of complete biographies, paid
jobs, completed degrees, nonservice or never having held office. Kristi Burke
(TN-01) and Melissa McDonough (TX-38) retain unknown personal academic education
after contextual source review. McDonough's professional designations, sons'
education and campaign manager's degrees are not substituted for her academic
history. Burke's beauty-industry work does not establish a match to a Kentucky
instructor or unrelated Texas/Idaho education professionals.

Mary Allen's August 2024 local profile separately supports an occupational-
therapy certification and a bachelor's program then in progress, not a completed
bachelor's. Jamie Joyce and Darden Copeland retain attendance-only college
claims. Elizabeth Lee's reported Northwestern State graduation years conflict;
both sources survive. Jen Mazzuckelli's subject-wording discrepancy is retained
without treating degree completion as disputed. Becky Stille's two reported
credentials could both be held; different credential levels alone are not a
contradiction. Hilda Solis's appointed secretaryship and Brad Meyer's civilian
Navy employment are not recoded as elected office or military service.

The source audit rejected unsupported proposed details as well as identity
matches: for example, the refreshed Erik Osberg campaign page did not contain
the proposed school/graduation-year wording. Only his separately supported
Hamline degree was accepted. Twenty-two identity-match rejection records remain
in `data/democratic-background-research.json`; grouped namesakes are not
misreported as an independently enumerated person count. Nineteen native
education-source retries succeeded and eight failed; the failures are retained,
not evidence of no education. Saved provider excerpts are explicitly labeled,
not passed off as native HTML. Allen's newly found profile was separately
downloaded and hashed.

The standardized all-449 table is
`results/house-study/democratic-candidate-traits.csv` / `.jsonl.gz`. It retains
literal values, exact identities, source URLs/dates/qualifications, supporting
evidence, explicit review metadata and unknown/conflicting claims. Generic
`prior_office` is not automatically elected office. Compensation, degree level,
subject, dates and completion remain unknown unless explicitly supported.
Source-specific remaining details and failed attempts survive in the research
registry and `targeted_background_research` column. The separate
`democratic-background-audit.json` enumerates gains and all remaining fields.
The browser displays and exports these traits; both complete downloads contain
the tables, registry, normalized evidence, code and tests.

The evidence-only build checks all 154 pinned committed analysis/figure files;
104 additional ignored historical snapshot copies are also checked when locally
present, but are not a fresh-clone dependency. No analysis is refitted, no frozen
sample changes and no website is deployed.

### Participation context is not candidate background

The local candidate browser separately exposes the source-pinned
[voter-participation supplement](PARTICIPATION_CONTEXT.md): 6,596 aggregate
observations in 48 jurisdictions and 51 coverage decisions. Official
Hawaii/Wyoming candidate counts confirm existing values; three Maine snapshots
retain initial, frozen-provider and later RCV major-party counts separately.
There are 23 result-category/snapshot records across four districts, including
seven nonperson/unassigned categories. Sixteen observations link to 12 named
candidate records, not 12 newly covered biographies. Missing final categories
remain unknown.

Statewide observations and source-region counts are not allocated to districts.
Demographic cells do not describe the candidate or establish individual voting
behavior. Different modes, geographic levels, groups and snapshots are not
additive. All records remain model-ineligible, leaving the 1,156 covered / 128
uncovered background accounting and all field-gap counts unchanged.

### Correction to the previous inventory

The previous join allowed missing target FEC IDs to match missing source IDs.
That assigned unrelated historical biographies to **42 candidates**. Acquisition,
selection and inventory joins now all reject absent IDs. All accepted links were
rebuilt; missing identifiers cannot inherit another person's background.
The old prose also overstated the actual old historical count by one: it said
130, while the old saved rows contained 129, of which 42 were invalid.
The corrected historical count is **87**, not 130. Earlier coverage claims of
592 combined biographies should not be used.

The held historical search contains 244 CampaignView profiles; only 87 candidates
have a currently qualified nonempty biography from 2024 or earlier. Historical
issue headings, years, lengths and hashes are supplied, not copyrighted campaign
text. These pointers do not count as downloadable factual background in the
current coverage denominator unless another source actually supplies observations.

`results/house/candidates.csv` is the readable candidate-level table.
`candidates.jsonl.gz` adds every match decision, source row, campaign URL,
dated legislative crosswalk, donor-score decision and biography-record key.
`biography-facts.jsonl.gz` supplies factual extraction values and provenance for
education, occupation, military service, elected office, public service and
local roots, including separately flagged historical election years.
**`background-observations.csv` supplies the actual field values**, candidate
keys, source years, observation dates, page/record references and qualifications
in a readable long table. Repeated years and sources are not independent people.
Captures on or after November 3 are not pre-election features.
Entire campaign pages are not redistributed. Reviewed fields include short
supporting fragments alongside factual paraphrases and source receipts.

`all-choices.jsonl.gz` retains the full native roster, including aggregate
choices and unverified provider flags. `missing-information.csv` keeps every
candidate with a missing requested field; it is not an exclusion list.
`coverage.json` provides machine-generated denominators by listed party group.
`source-inputs.jsonl.gz` contains the complete normalized inputs used by the
join, including alternatives rather than just successful matches.

Sources are the held official FEC candidate master, congress-legislators,
Voteview, Stanford DIME v4 and Hanno Hilbig et al.'s openly licensed campaign
website corpus (doi:10.7910/DVN/BZ2JRS, CC BY 4.0), plus dated member-authorized
congressional directories, Pew/CQ office questionnaires and official House
Historian tables.
Original URL/hash receipts and exact record references accompany the normalized
inputs. FEC registration records also contain primary losers and inactive
committees: the provider election roster, not the FEC file, sets the denominator.

The additional acquisition downloaded all **22 Oregon pamphlet editions** and
**four Alaska House candidate statements**, pinned by hash and PDF page.
Oregon structured occupation, work-history and education fields are extracted
without campaign statements. Alaska factual summaries were reviewed against the
candidate-supplied PDFs. Regional duplicates are consolidated while retaining
every page reference. Not every listed Oregon candidate submitted a usable
profile. Publication dates for individual voter-guide statements are not fully
verified; these new fields remain model-ineligible.

The follow-up acquired Utah's complete **118-page official pamphlet** and its
amended candidate certification. It adds 14 usable structured profiles, including
11 previously uncovered candidates, and 66 observations. Party and district are
checked against the certification before joining a guide profile to a candidate.
The Utah-stage long table contained **27,875 observations for 617 candidates**.
Utah contributes occupation, city of residence, literal years-of-residence
responses, reported age and campaign websites, not inferred religion or ideology.
Reported age is not converted into age at Election Day; years of residence are
not presumed to mean years in the district.

Four Utah pages explicitly say no profile was submitted. Two additional profiles
have no usable structured background fields; their narrative statements are not
silently treated as empty submissions or copied wholesale. All six dispositions
and their page/hash references are supplied in
`data/house-official-profile-dispositions.json` and the normalized inputs.
No failed submission or website-only profile counts as background coverage.
The [source search](CANDIDATE_DATABASES.md) and
`data/house-source-search.json` distinguish acquired guides from nationwide
services requiring approved access.

Ballotpedia's bulk request returned an empty HTTP 202 response. The public
Wikidata query endpoint returned HTTP 403. Neither was bypassed, acquired as a
usable candidate database, or counted as background evidence. Source receipts
record actual successes and failures rather than treating a catalog as data.

### Initial November 15 campaign and previous-office acquisition

The follow-up attempted all 117 uncovered candidates with held campaign URLs,
then acquired independently located biographies for Clyde Jones, Scott Wiener
and Hilda Solis. Its 131 unique original HTML snapshots are pinned locally;
downloads, errors and redirects are retained in `data/candidate-acquisition.json`.
An HTTP 200 response is not proof of a usable biography or the correct subject:
one Luke Bronin URL redirected to a restaurant, and several pages were empty,
script-only or nonbiographical. None of those pages was promoted to evidence.

`data/candidate-reviewed-backgrounds.json` supplies **122 anchored fields for
66 candidates**, including 34 Democrats, 31 Republicans and one listed write-in.
These are new acquisitions, not imported vendor catalogs. Fifty of those
candidates lacked a held education/career/service summary; 16 already had a
member/incoming summary but no long-table observations. Those 16 are not claimed
as people for whom the project previously knew nothing.

Each accepted field has supporting fragments, a source hash and retrieval time.
Cache reconstruction verifies the original bytes and anchors; the normalized
inputs make the public replay independent of live websites and local originals.
The strict join checks candidate ID, contest ID, name, state, district and party.
Campaign credentials remain self-reported, separately labeled from biographies
published by an office. Attendance and enrollment are not completed degrees.
Family members' military service, service as a diplomat, and attendance at a
military academy do not establish the candidate's military service.

That pass's long table contained **27,997 observations for 683 candidates**.
Its remaining 601 gaps included 85 Democrats, 130 Republicans and 386 candidates
listed under other parties or write-ins. These were long-table coverage gaps,
not proof that no public information exists. All newly reviewed records are
post-election acquisitions with unverified publication dates; they remain
descriptive/model-ineligible and do not enlarge any frozen model sample.

Optional new acquisition uses `python -m which_candidate.candidate_acquisition`;
the held campaign URLs and explicit `data/candidate-source-leads.json` drive it.
Previously attempted URLs are not silently retried. Reproducible research uses
the normalized inputs, not this live acquisition command.

### Original 601-person ledger: search adequacy withdrawn

The queue was recomputed from
`results/house-study/candidate-profiles.jsonl.gz`, selecting only candidates
with empty `acquired_background_observations`: **1,284 named candidates, 683
covered, 601 uncovered**. `data/candidate-research-queue.json` freezes those
601 identities and the baseline profile fingerprint. `missing-information.csv`
is not this queue: it also includes partially covered people.

Every queued person had a directory check, a saved individual search
request/result receipt and a disposition in
`data/candidate-research-dispositions.json`. Major-party research preceded the
other parties and named write-ins. Direct source acquisition reached **405 of
the 601**; the other 196 had no safely contextualized biography lead in this
bounded pass. Many searches returned irrelevant first-name matches. Those were
**failed discovery, not adequate candidate searches**. Merely saving the receipts
did not establish an adequate completed research pass; that interpretation is
withdrawn. The original attempts remain as history and the correction below
supersedes their research-adequacy labels.

Reviewed evidence newly covers **233 people: 77 Democrats, 93 Republicans and
63 other-party/write-in candidates**, adding **309 observations**. The annotation
registry at that milestone contained 324 source profiles for 299 distinct people and 431
anchored fields, including the preceding 66-person pass. These overlapping
source/profile counts must not be substituted for newly covered people.
That milestone's long table had **28,306 observations for 916 people**.

| Final outcome for the frozen queue | People |
| --- | ---: |
| Sourced observations, still partial biographies | 233 |
| No contextual biography located in this bounded pass | 196 |
| Captured directory/page without qualifying background | 140 |
| Reviewed pages/claims with no accepted facts or unresolved identity | 29 |
| Located sources inaccessible in the recorded attempts | 3 |
| Total documented outcomes | 601 |

At that milestone, the **368 uncovered people** comprised eight Democrats, 37 Republicans
and 323 others. Neither a provider's About page, a campaign shell, a search
snippet, a downloaded PDF nor an ambiguous military anecdote counts as reviewed
background. Tisha Benoit's professional page remains held for insufficient
campaign identity corroboration. Adam Ortiz's ambiguous Army account is not
promoted to service evidence. The legitimate Luke Bronin campaign biography is
distinct from the earlier restaurant redirect.

Vote-USA provided both campaign URL leads and factual questionnaire sections.
Its directory may compile campaign information rather than receive it directly;
those secondary paraphrases are labeled separately from candidate-supplied
answers. Official previous-office biographies, official California candidate
statements/ballot-designation records, campaign pages and professional-institution
biographies supplement the directory. Browser-rendered snapshots are identified
as public DOM captures, not original HTTP response bytes. No paid export was
purchased and no access denial was bypassed.

### Discovery and missing-field repair

The correction froze `c0fa188` coverage separately in
`data/candidate-discovery-baseline.json`: 1,284 candidates, 916 covered and
368 uncovered. The 701-person `data/candidate-discovery-repair.json` queue adds
333 already-covered candidates who lacked education or employment. The original
601-person queue is preserved, not redefined.

Current normalized coverage is **28,981 observations for 1,156 candidate records**.
Compared with `c0fa188`, **240 records newly have observations**, while **636
candidate-by-field gaps** were filled: education 284, professional history 324,
prior office 12 and military service 16. **204 previously covered candidates** gained
fields; 133 previously covered repair targets still lack at least one original
education/employment target. Multiple sources for one person do not inflate
the person count.

All 45 previously uncovered Democrats/Republicans were revisited, yielding 44
newly covered people. T.P. (Taras P.) Nykoriak remains a reviewed gap: his pinned
campaign and contextual profiles did not establish the four requested categories.
Ukraine travel and veteran-policy positions are not military service, and
candidacies are not offices held. Exact-context source-backed gap receipts
remain separate from factual annotations.

Remaining uncovered records are **zero Democrats, one Republican and 127
other-party/write-in entries**. Of these, 88 New Jersey write-in entries retain
roster identity holds and remain explicitly flagged as inadequate discovery;
the other 40 have reviewed source-specific gaps, not proof
that a complete public biography does not exist. A failed guessed URL, blocked
search, irrelevant result or directory shell cannot establish that absence.
All 601 original queue records have accounting dispositions; this does not
mean all source discovery succeeded. That original 683-covered baseline has
gained 473 covered records.

The denominator counts named candidate-contest records, not 1,284 independently
identified living people. The identity holds preserve the exact roster context
and vote receipt without assigning a famous namesake's credentials or claiming
the person campaigned. The local browser and filtered downloads expose the holds.

New sources include the supplied Gies faculty, Dawson campaign, Pericola
campaign and Rodriguez endorsing-organization biographies. Further reviewed
sources cover minor-party candidates and education gaps among already-covered
people. BallotReady public-profile observations remain directory-reported,
not official transcripts or universally candidate-submitted questionnaires.
School listing is not graduation, stale employment dates are not election-day
status, and suspect degree/occupation claims remain held. All new records are
retrospective/model-ineligible.

Additional native sources include candidate career portfolios, historical
voter guides and current campaign biographies. Self-reported training is not
necessarily a college degree; a job-seeking objective or unpaid party role is
not proof of paid employment. Andrea Townsend's housing work is separately
reported in Oregon Capital Chronicle and syndicated Statesman Journal reporting;
the Southern Oregon education administrator with the same name is not joined.
Ramon Mora's reported nursing education is not treated as an RN license.
Michelle Craig's acquired campaign and forthcoming-book pages establish neither
a completed publication nor employment/education credentials and remain a gap.

The original Idaho roster label "Sarah Zabel Peterson" is preserved for
reconciliation, not asserted as a person's name. Clearwater County's official
sample ballot (page 1) separately lists Sarah Zabel (Independent) and Kaylee
Peterson (Democratic); FEC H6ID01318 identifies Sarah Zabel in ID-01. The
independent entry's newly attached campaign-reported education, work and military
facts refer only to Sarah Zabel. Both identity originals and the source-specific
review are retained; the Minnesota school-board namesake is rejected.
All seven formerly pending lead records now have explicit source reviews,
including wrong-contest rejections, without turning directory shells or civic
motivations into credentials.

Some evidence uses explicitly labelled provider page extractions or reviewed
indexed excerpts rather than original server HTML. Those receipts retain the
method, provider reference, exact captured fragments and native access failures;
they are not independent corroboration or silently substituted full originals.
Ordinary OS-trusted HTTPS recovered several Python certificate-chain failures
with certificate verification enabled. Denied/paywalled sources were not bypassed.
The acquisition cap is 32 MiB for PDF guides and 8 MiB for HTML.

#### Remaining requested fields

`results/house-study/background-field-coverage.csv` audits all 1,284 candidates.
Aliases in older occupation/office extraction fields are included, but empty,
unknown and refused values do not count as substantive field availability.

| Requested dimension | People with acquired observations | People without |
| --- | ---: | ---: |
| Education | 988 | 296 |
| Employment/professional history | 1,090 | 194 |
| Prior office/governmental experience | 387 | 897 |
| Military service | 198 | 1,086 |

Only 57 candidate records have observations in all four dimensions; that still does not
establish complete, current or independently verified biographies. Historical
and machine-extracted fields retain their qualifications. No military section
does not mean nonservice, and no office observation does not mean never held
office. The prior-office dimension includes existing governmental-experience
extractions and should not be read as a verified elected-office count.

`results/house-study/research-dispositions.csv` supplies all 601 frozen identities,
accepted sources, failed attempts, search receipts and field gaps. The local
browser exposes these outcomes and permits searching and CSV download of them.
`discovery-repair-dispositions.csv` separately supplies all 701 correction
targets, whether previously uncovered or only missing individual fields.
Both complete downloads contain the registries, normalized evidence, tests,
code, all candidate queries and the field/disposition tables.

### Incremental evidence ingestion and replay

`data/raw/` is intentionally ignored and absent from a fresh clone. Preserve
`results/house/source-inputs.jsonl.gz`; do not reconstruct all historical inputs
from an incomplete raw cache.

For genuinely new evidence, add contextual URLs to
`data/candidate-source-leads.json`, acquire originals into the ignored cache and
record receipts in `data/candidate-acquisition.json`. Review facts into
`data/candidate-reviewed-backgrounds.json`, retaining short supporting fragments,
source type and all six identity fields: candidate ID, contest ID, name, state,
district and party. PDF annotations require explicit one-based source pages.

```bash
python -m which_candidate.candidate_acquisition
# Review material; update annotations or the gap's review_note and reviewed_source_ids.
python -m which_candidate.reviewed_backgrounds
python -m which_candidate.candidate_discovery --finalize
python -m which_candidate.candidate_research --finalize
python -m which_candidate.house_project --evidence-only
```

The ingest command checks normalized manifest fingerprints, validates originals
and anchors only for new/changed profiles, preserves historical normalized
evidence, and calls `house_candidates.build(inputs=...)` with the merged inputs.
It refreshes the candidate outputs and manifests. Editing annotation JSON and
running `house_project` alone does **not** ingest new facts. An unchanged ingest
validates zero new profiles and requires no old originals.

Finalization reconciles the frozen queue with actual normalized observations
and acquisition receipts. For uncovered candidates, new nonempty uncredited
pages require an explicit review disposition scoped to `reviewed_source_ids`;
an old candidate note cannot silently count a newly downloaded page as reviewed.
Additional uncredited pages for already-covered candidates stay explicitly
uncredited. Downloads are never promoted automatically. Existing
unchanged source outcomes can be replayed without originals. Source outcome,
candidate-context or coverage inconsistencies fail validation.

All additions remain retrospective/descriptive and `model_ready: false`.
Frozen models, samples and historical snapshots are unchanged. Ordinary
`house_project` replay uses only committed normalized inputs; it makes no live
acquisition requests and does not deploy the website.

For the discovery repair, `candidate_discovery.record_search` preserves actual
performed contextual queries, provider references, returned leads and rejected
irrelevant hits. Generated query suggestions are not performed-search receipts.
`candidate_discovery.record_gap_review` validates a source-backed gap against
owned original hashes, exact candidate context and supporting identity fragments,
without adding factual observations. Unchanged normalized evidence and saved
gap receipts remain replayable without historical raw pages.

## Full House membership and incoming members

The previous 360-person table was an **incumbent-election-candidate subset**,
not the House membership roster. `results/members/house-119-seats.csv` now
accounts for **all 435 voting seats**: 433 named occupants, plus vacancies in
FL-20 and TX-23. Vacancies retain predecessor identifiers and source-recorded
vacate dates, never fabricated current members. The Clerk source is dated
**November 3, 2026**, retrieved November 13; these are different clocks.
`house-119-delegates.csv` separately retains six nonvoting delegate/Resident
Commissioner seats and does not inflate the 435-seat denominator.

| Information | Named voting-seat occupants with observations |
| --- | ---: |
| Age, source-recorded gender, first service, birth, education and career | 433 each |
| Cutoff-only 119th-Congress cast-vote record | 433 |
| Current party-unity score, subject to the 50-vote threshold | 431 |
| Substantive reported religion | 411 |
| Explicit unknown/refused religious response | 17 |
| No acquired qualified religious disclosure | 5 |
| Positive military-service evidence | 80 |
| Positive official Historian identity classifications | 119 |
| Prior 118th-Congress ideology | 360 |
| Historical CongressData member-year record | 362 |

Blair's official Historian biography fills birth, education and career gaps;
Crenshaw's official biography supplies his Navy SEAL career. Stable-ID
crosswalk names and published article-title aliases recover existing religion
questionnaire observations without guessing nicknames from names alone.
Of the 411 substantive religion observations, 405 are dated office responses,
two dated public self-descriptions and four undated public self-descriptions.
The five unresolved disclosures are Everton Blair, Adelita Grijalva,
Analilia Mejia, Christian Menefee and James Walkinshaw. Upbringing, an oath
and religious-liberty statements do not establish an individual's current
affiliation. A missing military section never means nonservice.

`house-120-seats.csv` is a **separate provisional incoming roster**, scheduled
to begin January 3, 2027. It retains all 435 seats, including nine without a
unique provider-reported winner. The 426 native winner flags comprise
319 continuing members, six returning former members and 101 other reported
winners whose prior federal service is not independently established.
The six returning members are Jerry Carl, Hilda Solis, Melissa Bean,
Colin Allred, Ben McAdams and Elaine Luria. Full historical Congress Legislators
crosswalks, including earlier service absent from the election panel, qualify
these joins. Bob Onder is correctly linked to his seated stable identity,
not misclassified as a first-time member. Continuing-member evidence follows
the Bioguide ID even when the district changes.

All 426 reported winners have an existing biography or a short secondary
prior-background summary. This is **not complete newcomer education, religion,
age or verified career coverage**. Wikipedia supplies 113 district-qualified
new-member rows, of which 107 join the selected provisional winners, and
34 acquired infobox profiles. Only 32 selected-winner rows have Wikipedia
education fields. Rate limits prevented further individual-page acquisition;
failures remain recorded and are not bypassed or counted as profiles.
Uncertain birth years remain literal ranges, not exact birthdays.
Infobox race/religion labels are not treated as self-identification.
Campaign extractions remain separately marked as requiring review.

Quorum's snapshot explicitly dated November 12 reports 13 listed House seats
as uncalled; the provider's separate clocks and any winner flags are retained
alongside that caveat. The older article does not automatically override a
later snapshot, and neither is promoted to certification or a verified call
timestamp. Inside Elections returned HTTP 403 to acquisition: its catalog
page does not contribute invented member records.

`background-observations.csv` supplies source-qualified factual member fields
and separately labeled secondary/machine-extracted incoming evidence.
`missing-fields.csv` covers seated members; `incoming-missing-fields.csv`
retains unresolved seats, exact-birth/education/religion gaps and the
inapplicability of current federal votes for newcomers. Federal nonservice
does not become an ideology score of zero.

### Actually acquired CongressData, not only a catalog entry

The authors' openly licensed Figshare deposit was downloaded and checked against
its published checksum. Its actual file has **67,661 member-years, 1,045
variables and years 1789-2024**, rather than assuming the current website's
larger variable count applies to this deposited vintage.
`congressdata-latest.csv` retains every native column for the latest available
historical row of 368 matched people: 362 seated occupants and six returning
former members. Their source years remain explicit. No historical variable
is silently substituted for current religion, race, nonservice or ideology.

The included `congressdata-codebook.json` supplies the acquired v3 codebook text,
attribution and source receipts. **The current v3 codebook and the paper's
deposit are separate vintages**; only variables actually present in the
downloaded file are exported. Cite Grossmann, Lucas and Yoel (2025),
*Introducing CongressData and Correlates of State Policy*, Scientific Data
12:1185, DOI 10.1038/s41597-025-05495-7, and each used variable's original
source. Deposit DOI: 10.6084/m9.figshare.28146914; data license CC BY 4.0.
The codebook is distributed in the upstream GPL-3 CongressData package,
separately from that deposit. Its package declaration and full GPL text
are included in `congressdata-codebook.json`; the licenses are not conflated.
CRS's congressional profile remains useful aggregate context, not an acquired
member-level database. Vote Smart's questionnaire requires approved access;
no unauthorized access or imaginary complete questionnaire panel is claimed.

Offline reproduction of these member tables uses the included normalized data,
without R, the original caches or the optional acquisition reader:

```bash
.venv/bin/python -m which_candidate.house_members
```

Fresh acquisition additionally requires the older source caches described above
and the optional reader (`pip install -e '.[acquisition]'`, Python 3.11+):

```bash
.venv/bin/python -m which_candidate.house_members --acquire
.venv/bin/python -m which_candidate.congress_data
```

These are descriptive additions. All historical performance-model outputs
remain unchanged, and website publication remains withdrawn.

## Every qualified incumbent election candidate

`incumbents.csv` contains **360 independently qualified incumbent candidate
records**: 183 Democrats, 176 Republicans and one native No Party Preference
candidate. Each row has an actual age, source-recorded gender, first House
service date, birthplace clause, education, professional history and pre-election
voting record. These are source-qualified descriptive records, not newly
approved performance-model features.

| Information | Incumbents with observations |
| --- | ---: |
| Age, gender, service, birth clause, education, career and current cast-vote record | 360 each |
| Current party-unity score, subject to the 50-vote threshold | 359 |
| Substantive reported religious affiliation | 340 |
| Explicit unknown/refused religious response | 16 |
| No acquired qualified religious disclosure | 4 |
| Explicit positive military-service evidence | 64 |
| Positive House Historian race/ethnicity classifications | 101 |
| Prior 118th-Congress ideology | 291 |
| Qualified historical donor score | 298 |

The religion-literal availability count is 356, **not 356 known affiliations**.
Of 340 substantive observations, 334 are dated office responses, two are dated
public self-descriptions and four are undated public self-descriptions retrieved
after the election. Older questionnaire refusals remain refusals rather than
being replaced with older positive responses. The four unresolved disclosures
are Adelita Grijalva, Analilia Mejia, Christian Menefee and James Walkinshaw.
`data/incumbent-disclosure-search.json` records the searches and rejected proxies.
No missing religion or military section supplies a negative classification.

The new source set contains the verified full February 20, 2026 Congressional
Directory, eleven House Historian biographies, the Clerk's October 1, 2026
veterans list, explicit member/campaign self-descriptions and a published
interview transcript. That transcript has not been checked against the audio.
Gallagher's dated Christian self-description was manually reviewed in a rendered
archive of his official statement; direct HTML returned 403. The factual
extraction is supplied, but **no downloaded original HTML is claimed**.
Original-source receipts and this separate review qualification are retained in
`data/incumbent-background-sources.json` and
`data/incumbent-reviewed-observations.json`.

The directory parser now handles name credentials, optional punctuation and
labels split across PDF pages, without importing staff/contact sections.
Education attendance is not turned into graduation. Official source URLs and
stable Bioguide IDs qualify member biographies. Name variants recover existing
questionnaire observations only after the person identity is independently
qualified.

An independent Election Day Clerk cross-check recovers Kevin Kiley, Mark Harris
and Rob Menendez without arbitrarily resolving their absent or conflicting FEC
campaign IDs. `incumbent-cohort-audit.csv` accounts for all **441** Clerk records:
360 qualified candidate links, one held candidate label and 80 without a
matching label in the pinned returns. The held Bonnie Watson Coleman NJ-03
write-in label is not merged with NJ-12 merely from the name. Absence of a label
does not prove a member was not a candidate.

The **119th Congress is 2025-2026**. Current party unity uses only actual yea/nay
votes before November 3, 2026 on roll calls where Democratic and Republican
majorities opposed one another. Abstention is not opposition. Aisha Wahab has
a real voting record but fewer than 50 qualifying roll calls, so her unity
score is withheld, not zero. Source party codes and record qualifications are
exported: Kiley's native affiliation is No Party Preference, while the reused
voting record is Republican-coded and covers that source spell, not necessarily
every vote of the Congress. Prior 118th-Congress ideology and historical donor
scores are separate columns, not substitutes for this current voting measure.

`incumbent-missing-fields.csv` retains absent fields and explicit religion
unknowns/refusals. `incumbent-coverage.json` provides machine-generated
denominators and statuses. The detailed implementation critique and corrections
are in `audits/incumbent-backgrounds.json`. All four incumbent exports are
included in the complete downloads and deterministic offline rebuild.

## Qualification and critique

Candidate links require compatible year, House office, state, party and name.
Official-ID matches may use documented congressional name aliases, including
name titles recorded in the held crosswalk. A stable
FEC person ID can survive a district move; conflicting registration districts
are disclosed rather than used as current electoral geography. Without an
official ID match, a publisher-based link additionally requires the current
district and is labeled separately. Conflicting and ambiguous alternatives
remain held. There is no name-only national person merge.
For native "Write-In" labels only, political affiliation is unknown rather than
contradictory: an official FEC link additionally requires the exact current
district and a qualified name. It does not relabel the native choice's party.

The website corpus covers major-party campaign records, **not all parties**.
The new official voter guides add nonpartisan, Libertarian and Pacific Green
backgrounds, but other-party coverage remains especially poor. Missing evidence
never means no experience. Historical donor scores describe funding coalitions
through 2024, not 2026 positions. Prior federal voting covers the 118th Congress
(2023-2024), not newcomers or current campaign positions. Unknown incumbency is
null, not a false provider flag promoted into a service classification.

Machine biography extraction is not verified trait coding: a sentence about
someone's relative can be assigned to the candidate, and public-service labels
can include unrelated activities. Every extracted fact remains review-required
and model-ineligible. Dated religion responses, including changes and unknowns,
are retained without assigning a current verified affiliation. Positive official
Historian classifications are labeled as such, not as self-identification.
Current verified religion/race labels remain unassigned. No missing identity
supplies a reference group.

This expansion does **not** refit or broaden the existing Democratic performance
models. A complete roster is not complete background data, and the selected
donor/voting samples must not be generalized to all 1,284 people.

## Reproduce

```bash
.venv/bin/python -m which_candidate.incumbents
.venv/bin/python -m which_candidate.house_candidates --from-cache
.venv/bin/python -m which_candidate.house_candidates
.venv/bin/python -m which_candidate.rebuild_publication
.venv/bin/python -m which_candidate.rebuild_package
```

Default replay uses only the packaged normalized inputs, without network.
The incumbent acquisition command uses the network only for unheld originals;
the following `--from-cache` command verifies and integrates the held sources.
`--from-cache` reconstructs them from the original held source cache and verifies
publisher/source hashes. `--output` writes an independent replay directory.
The complete-query download includes every table, fact, alternative, exclusion,
input, test and current plot, not just a coverage summary.
