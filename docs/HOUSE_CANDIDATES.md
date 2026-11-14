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
| Dated Pew/CQ religion observations | 352 | 179 | 172 | 1 |
| Member-authorized or official member backgrounds | 362 | 184 | 177 | 1 |
| Positive House Historian identifications | 101 | 89 | 12 | 0 |
| Any downloadable background observations | 617 | 330 | 272 | 15 |
| Name-qualified historical donor scores | 370 | 192 | 178 | 0 |
| Prior federal voting scores | 293 | 149 | 143 | 1 |

Rows overlap and must not be added. **667 candidates still lack downloadable
background observations.** An observation can be historical, machine-extracted,
candidate-supplied or an explicit unknown questionnaire response; it is not a
complete verified biography. One candidate's current campaign facts were captured
only after Election Day; those observations are retained but are not pre-election
features. Native "Write-In" records remain in the other-party denominator even
when their dated FEC registration or campaign corpus records a major party.

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
617-person denominator unless another source actually supplies observations.

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
Raw evidence quotations and entire campaign pages are not redistributed.

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
The current long table contains **27,875 observations for 617 candidates**.
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

## Every qualified incumbent

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
