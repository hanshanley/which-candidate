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
| Candidate-ID links | 962 | 425 | 390 | 147 |
| Campaign URLs | 678 | 368 | 310 | 0 |
| Pre-election biography records | 462 | 277 | 185 | 0 |
| Additional historical biographies | 130 | 47 | 83 | 0 |
| Name-qualified historical donor scores | 370 | 192 | 178 | 0 |
| Prior federal voting scores | 282 | 145 | 137 | 0 |

The historical search acquired/verified 244 CampaignView profiles without
endpoint failures. Of these, 130 candidates have a qualified nonempty biography
from 2024 or earlier; the other profiles are not automatically biographies.
These 130 lacked the current pre-election biography records, so 592 candidates
have one of those two forms of biographical evidence. CampaignView, like the
website corpus, only covers the two major parties in its acquired index.
The historical issue headings, years, content lengths and hashes are supplied;
copyrighted campaign text is not copied into public downloads.

`results/house/candidates.csv` is the readable candidate-level table.
`candidates.jsonl.gz` adds every match decision, source row, campaign URL,
dated legislative crosswalk, donor-score decision and biography-record key.
`biography-facts.jsonl.gz` supplies factual extraction values and provenance for
education, occupation, military service, elected office, public service and
local roots. Captures on or after November 3 are not pre-election features.
Raw evidence quotations and entire campaign pages are not redistributed.

`all-choices.jsonl.gz` retains the full native roster, including aggregate
choices and unverified provider flags. `missing-information.csv` keeps every
candidate with a missing requested field; it is not an exclusion list.
`coverage.json` provides machine-generated denominators by listed party group.
`source-inputs.jsonl.gz` contains the complete normalized inputs used by the
join, including alternatives rather than just successful matches.

Sources are the held official FEC candidate master, congress-legislators,
Voteview, Stanford DIME v4 and Hanno Hilbig et al.'s openly licensed campaign
website corpus (doi:10.7910/DVN/BZ2JRS, CC BY 4.0).
Original URL/hash receipts and exact record references accompany the normalized
inputs. FEC registration records also contain primary losers and inactive
committees: the provider election roster, not the FEC file, sets the denominator.

## Qualification and critique

Candidate links require compatible year, House office, state, party and name.
Official-ID matches may use documented congressional name aliases. A stable
FEC person ID can survive a district move; conflicting registration districts
are disclosed rather than used as current electoral geography. Without an
official ID match, a publisher-based link additionally requires the current
district and is labeled separately. Conflicting and ambiguous alternatives
remain held. There is no name-only national person merge.

The website corpus covers Democrats and Republicans, **not all parties**.
Consequently zero third-party biography coverage is a source limitation, never
evidence of no experience. Historical donor scores describe funding coalitions
through 2024, not 2026 positions. Prior federal voting covers the 118th Congress
(2023-2024), not newcomers or current campaign positions. Unknown incumbency is
null, not a false provider flag promoted into a service classification.

Machine biography extraction is not verified trait coding: a sentence about
someone's relative can be assigned to the candidate, and public-service labels
can include unrelated activities. Every extracted fact remains review-required
and model-ineligible. Religion and race/ethnicity are not inferred or coded in
this new all-candidate inventory; selective historical identity evidence remains
in the original research queries. No missing identity supplies a reference group.

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
