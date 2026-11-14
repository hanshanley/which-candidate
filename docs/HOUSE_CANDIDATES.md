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
| Campaign URLs | 694 | 372 | 315 | 7 |
| Pre-election campaign biography records | 467 | 278 | 186 | 3 |
| Historical CampaignView biography records | 87 | 34 | 53 | 0 |
| Historical campaign-site factual extractions | 184 | 95 | 89 | 0 |
| Official candidate-supplied voter-guide profiles | 16 | 7 | 6 | 3 |
| Dated Pew/CQ religion observations | 340 | 176 | 164 | 0 |
| Member-authorized background records | 332 | 167 | 165 | 0 |
| Positive House Historian identifications | 100 | 88 | 12 | 0 |
| Any downloadable background observations | 601 | 327 | 268 | 6 |
| Name-qualified historical donor scores | 370 | 192 | 178 | 0 |
| Prior federal voting scores | 291 | 148 | 143 | 0 |

Rows overlap and must not be added. **683 candidates still lack downloadable
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
601-person denominator unless another source actually supplies observations.

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

Ballotpedia's bulk request returned an empty HTTP 202 response. The public
Wikidata query endpoint returned HTTP 403. Neither was bypassed, acquired as a
usable candidate database, or counted as background evidence. Source receipts
record actual successes and failures rather than treating a catalog as data.

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
.venv/bin/python -m which_candidate.house_candidates
.venv/bin/python -m which_candidate.rebuild_publication
.venv/bin/python -m which_candidate.rebuild_package
```

Default replay uses only the packaged normalized inputs, without network.
`--from-cache` reconstructs them from the original held source cache and verifies
publisher/source hashes. `--output` writes an independent replay directory.
The complete-query download includes every table, fact, alternative, exclusion,
input, test and current plot, not just a coverage summary.
