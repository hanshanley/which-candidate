"""Register reviewed original statements without promoting undated claims."""

import csv
import json
import re
import shutil
from pathlib import Path

from .characteristics_research import normalized, reviewed_claims, source_text
from .characteristics_v7_extract import IDENTITY
from .characteristics_v8_batch import WORK
from .characteristics_v8_guides import oregon_statement, washington_statement
from .storage import fingerprint, read_rows, write_json

NATIONAL_REVIEW = "data/house-characteristics-v8-national-review.json"
GUIDE_PROFESSION = {
    "221006": "legal",
    "221362": "legal",
    "221360": "healthcare",
    "221361": "business",
    "221352": "business",
}
GOVERNMENT_GUIDES = {
    "221002": "US Dept. of Agriculture Rural Policy Advisor (2010-2016)",
    "221362": "Prosecutor, City of Seattle, 1993-1995",
    "221346": "Former Director of Washington’s Department of Revenue",
    "221357": "Regional Safety & Risk Management: Washington Labor & Industries",
    "221354": "I joined the State Department In Iraq",
    "221355": "Foreign Service Officer (diplomat), U.S. Department of State",
}
MILITARY_GUIDES = {
    "221006": "Colonel, U.S. Air Force (retired)",
    "221359": "US Marines 2011 to 2014 Honorable Discharge",
    "221353": "24 year Air Force career",
    "221350": "Retired U.S. Navy Captain with 31 years of service",
}
EXPLICIT_NEGATIVE_GUIDES = {"221359", "221361", "221349", "221353"}
NON_PUBLIC_OFFICE_GUIDES = {"221363", "221347", "221357", "221365", "221355"}


def credential_code(text):
    text = ";".join(
        part
        for part in text.split(";")
        if not re.search(
            r"\b(?:candidate|pursuing|coursework|attended|student|expected|in.progress)\b",
            part,
            re.I,
        )
    )
    for code, pattern in (
        ("doctoral_or_professional", r"\b(?:Ph\.?D\.?|M\.?D\.?|J\.?D\.?|Doctorate|Doctor of)\b"),
        ("masters", r"\b(?:M\.?B\.?A\.?|M\.?P\.?A\.?|M\.?A\.?|M\.?S\.?|master[’']?s degree)\b"),
        ("bachelors", r"\b(?:B\.?A\.?|B\.?S\.?|Bachelor[’']?s?|Bachelor of)\b"),
        ("associate", r"\b(?:A\.?A\.?S\.?|A\.?A\.?|associate degree)\b"),
    ):
        if re.search(pattern, text, re.I):
            return code
    return None


def claim(trait, value, fragment, *, analysis=None, factual=True, reason, timing):
    return {
        "trait": trait,
        "value": value,
        "fragment": fragment,
        "qualification": reason,
        "v8_review": {
            "factual_qualified": factual,
            "analysis_value": analysis,
            "reason": reason,
            "factual_timing": timing,
            "prospective_availability": "not_established_by_retrospective_retrieval",
        },
    }


def guide_claims(draft, candidate):
    fields = draft["fields"]
    key = candidate["candidate_id"]
    education = fields.get("Education", fields.get("Educational Background"))
    profession = fields.get("Other Professional Experience", fields.get("Occupational Background"))
    office = fields.get("Elected Experience", fields.get("Prior Governmental Experience"))
    result = []
    if education:
        code = credential_code(education)
        result.append(
            claim(
                "education",
                {"reported_credential_category": code, "field": education},
                education,
                analysis=code,
                reason="Explicit candidate-submitted education field in a pre-election 2026 "
                "official pamphlet. Only a named degree level supplies completed-credential "
                "coding; attendance, unlevelled degrees and schools remain separate. "
                "Not independently verified highest attainment.",
                timing="2026_general_election_candidate_statement",
            )
        )
    if profession:
        result.append(
            claim(
                "profession",
                {"history": profession},
                profession,
                analysis=GUIDE_PROFESSION.get(key),
                reason="Literal candidate-submitted occupational field. Only a reviewed "
                "unambiguous existing professional family is coded; mixed/undefined roles "
                "are retained without forcing a principal family.",
                timing="2026_general_election_candidate_statement",
            )
        )
    if office:
        negative = key in EXPLICIT_NEGATIVE_GUIDES
        public = key not in NON_PUBLIC_OFFICE_GUIDES
        # Oregon's broad field is not a no-office or no-employment question.
        fragment = office if draft["state"] == "WA" else office.split(" I pledge", 1)[0]
        if draft["state"] == "OR":
            fragment = {
                "221002": "Oregon State Representative (1997-2003)",
                "221005": "State Representative",
                "221009": "Oregon State Representative",
            }.get(key, "")
            public = bool(fragment)
        if fragment:
            result.append(
                claim(
                    "prior_elected_office",
                    {
                        "history": fragment,
                        "explicit_negative": negative,
                        "question": "Elected Experience"
                        if draft["state"] == "WA"
                        else "Prior Governmental Experience",
                        "time_reference": "before_2026-11-03",
                    },
                    fragment,
                    factual=public,
                    reason="Explicit no-prior-elected-office answer; scoped candidate report, "
                    "not inferred from blank biographies or no previous congressional campaign."
                    if negative
                    else "Explicit public elected-office history before the 2026 election."
                    if public
                    else "Party positions, student offices and unsuccessful candidacies do not "
                    "establish public elected service or an explicit no-office answer.",
                    timing="before_2026-11-03_as_reported_in_official_election_statement",
                )
            )
    for trait, table in (("other_government", GOVERNMENT_GUIDES), ("military", MILITARY_GUIDES)):
        if key in table:
            result.append(
                claim(
                    trait,
                    True if trait == "military" else {"history": table[key]},
                    table[key],
                    analysis=True if trait == "military" else None,
                    reason="Explicit candidate-submitted military service before the election; "
                    "not inferred from a spouse, a military school, or veteran advocacy."
                    if trait == "military"
                    else "Explicit named government job in the candidate's occupational history; "
                    "not an elected or advisory position. Negative reference remains unavailable.",
                    timing="2026_general_election_candidate_statement",
                )
            )
    if key == "221354":
        result.append(
            claim(
                "religion",
                {"church_membership": "St. Augustine’s Parish"},
                "Active member St. Augustine’s Parish",
                reason="Explicit church membership "
                "in the pre-election pamphlet; a denomination is not inferred from the parish name.",
                timing="2026_general_election_candidate_statement",
            )
        )
    if key == "221352":
        result.append(
            claim(
                "religion",
                ["Christian"],
                "I am Amanda McKinney, a Wife, Mother, Christian",
                analysis="other_christian",
                reason="Explicit dated-election candidate self-description; "
                "Christian is not silently recoded Protestant.",
                timing="2026_general_election_candidate_statement",
            )
        )
    return result


def national_claims(entries, key=""):
    result = []
    for trait, fragment, value in entries:
        analysis, factual = None, True
        timing = "undated_biography_retrieved_retrospectively"
        reason = "Literal named-candidate original campaign biography; reported history "
        reason += "is retained separately from pre-election analytical qualification."
        if trait == "age":
            timing = f"explicit_birth_year_{value['birth_year']}_not_an_invented_birthday"
        elif trait == "education" and value.get("reference_year", 9999) < 2026:
            analysis = value.get("reported_credential_category")
            timing = f"explicit_completed_credential_{value['reference_year']}"
        elif trait == "military":
            # A multi-year completed service history necessarily includes service
            # before the cutoff; bare veteran labels do not establish its date.
            if (
                re.search(r"\b(?:seven|15|16|20|22|24|34|35)[- ]years?\b", fragment, re.I)
                or "January 2017" in fragment
                or any(
                    1900 <= int(start) < int(end) < 2026
                    for start, end in re.findall(r"\b(\d{4})[–-](\d{4})\b", fragment)
                )
            ):
                analysis = True
                timing = "explicit_historical_service_year_or_multi_year_completed_duration"
            reason += " Bare veteran labels retain unknown service timing."
        elif trait == "religion":
            factual = "reported_community_activity" not in value
            reason += (
                " No dated affiliation value is invented; church volunteering is not membership."
            )
        elif trait == "other_government":
            factual = not any(
                word in json.dumps(value).casefold()
                for word in ("require clarification", "see source context")
            )
            reason += " Employer/role ambiguity remains held; no advisory position is promoted."
        elif trait == "profession":
            analysis = {
                "campaign-219731-bio1": "healthcare",
                "campaign-219780-bio1": "healthcare",
                "campaign-220192-bio1": "legal",
                "campaign-220369-bio1": "legal",
                "campaign-221198-home": "legal",
            }.get(key)
            if analysis:
                timing = "explicit_completed_decade_or_longer_occupational_history"
                reason += " Explicit long historical work in one existing family supplies pre-cutoff meaning."
        result.append(
            claim(
                trait,
                value,
                fragment,
                analysis=analysis,
                factual=factual,
                reason=reason,
                timing=timing,
            )
        )
    return result


FEC_BRIDGES = {
    "219755": ("fec-hafner-2026", "ERIC, HAFNER", "ERIC HAFNER FOR CONGRESS", True),
    "220431": ("fec-day-2026", "DAY, JOHN DAVID", "COMMITEE TO ELECT JOHN DAY", True),
    "220436": ("fec-cable-2026", "CABLE, CONRAD ROBERTS", "COMMITTEE TO ELECT CONRAD CABLE", False),
    "220437": (
        "fec-gromlich-form-2025",
        "Gromlich, Matthew",
        "COMMITTEE TO ELECT MATT GROMLICH",
        False,
    ),
    "220448": ("fec-moore-2026", "MOORE, PATRICIA ANN", "PAT MOORE FOR CONGRESS", True),
    "220454": ("fec-forbes-2026", "FORBES, PATRICK WAYNE", "COMMITTEE TO ELECT PAT FORBES", True),
    "221041": (
        "fec-bradstock-committee-form-2025",
        "Bradstock, David, Alan",
        "bradstockforcongress.com",
        False,
    ),
}


def institutional_claims(root, acquired, candidates, add, decisions):
    key = "church-guides-colorado-elpaso-2026"
    if key in acquired:
        identity = "Exact native full candidate name, party and CO House District 5 in "
        identity += "the candidate's own 2026 general-election response heading."
        for cid, page, claims in (
            (
                "219990",
                19,
                [
                    claim(
                        "military",
                        True,
                        "Military Background: US Army Veteran",
                        analysis=True,
                        reason="Explicit own-service veteran answer in the pre-election "
                        "2026 general-election candidate questionnaire.",
                        timing="2026_general_election_candidate_questionnaire",
                    ),
                    claim(
                        "profession",
                        {"history": "public servant"},
                        "Occupation/Vocation: Public Servant",
                        reason="Candidate's wording does not establish a paid government "
                        "job or one principal historical occupational family.",
                        timing="2026_general_election_candidate_questionnaire",
                    ),
                ],
            ),
            (
                "219991",
                24,
                [
                    claim(
                        "profession",
                        {"history": "contract design engineer"},
                        "Occupation/Vocation: Contract Design Engineer",
                        reason="Explicit occupation outside the four existing families; "
                        "not recoded to obtain analytical support.",
                        timing="2026_general_election_candidate_questionnaire",
                    ),
                ],
            ),
            (
                "219992",
                28,
                [
                    claim(
                        "profession",
                        {"history": "salesperson and small-business owner"},
                        "My professional experience as a small -business owner",
                        analysis="business",
                        reason="Literal authored business-ownership experience; native "
                        "CO05 contest linkage is independent of rejected historical "
                        "cross-contest transfers.",
                        timing="2026_general_election_candidate_questionnaire",
                    ),
                ],
            ),
        ):
            add(key, candidates[cid], claims, scope={"page": page}, identity=identity)
    key = "tennessee-unicoi-guide-2026"
    if key in acquired:
        add(
            key,
            candidates["221173"],
            [
                claim(
                    "military",
                    False,
                    "Military Background: No Military Background.",
                    analysis=False,
                    reason="Explicit negative in the named respondent's Military Background "
                    "field, alongside her substantive authored answers in the November 2026 "
                    "guide. Not inferred from a missing response, biography omission or "
                    "the publisher's religious views; retained histories supply no conflict.",
                    timing="2026_general_election_candidate_questionnaire",
                ),
                claim(
                    "profession",
                    {
                        "history": "self-employed artist, small business owner and community organizer"
                    },
                    "As a self-employed artist and small business owner",
                    reason="Literal authored occupational description; mixed artist/business/"
                    "organizing work is not forced into one historical principal family.",
                    timing="2026_general_election_candidate_questionnaire",
                ),
            ],
            scope={"page": 11},
            identity="Exact full native candidate name, Democratic TN House District 1 "
            "in the page heading, substantive answers and candidate email domain agreeing "
            "with the native campaign. Contact details are not analytical fields.",
        )
    key = "maryland-legislative-roster-2025"
    if key in acquired:
        add(
            key,
            candidates["220484"],
            [
                claim(
                    "age",
                    "1994-05-10",
                    "Born in Arlington, Virginia, May 10, 1994.",
                    reason="Exact birth date in the official 2025 legislative roster; "
                    "not a year interval or an invented birthday.",
                    timing="official_2025_session_roster",
                ),
                claim(
                    "education",
                    {"reported_credential_category": "masters", "reference_year": 2019},
                    "American University, Kogod School of Business, M.B.A., 2019.",
                    analysis="masters",
                    reason="Explicit completed MBA and year in the official 2025 roster.",
                    timing="completed_2019_reported_in_2025_roster",
                ),
                claim(
                    "prior_elected_office",
                    {
                        "history": "Maryland House since 2023; Bowie council 2019-2022",
                        "time_reference": "before_2026-11-03",
                    },
                    "City of Bowie, Mayor Pro Tem and District 3 Council Member, 2019-2022",
                    reason="Dated public elected-office history before the 2026 election, "
                    "not before first House entry.",
                    timing="official_2025_session_roster",
                ),
            ],
            scope={"page": 42, "start": "ADRIAN BOAFO", "end": "CHRISTOPHER ERIC BOUCHAT"},
            identity="Exact full native name, Democratic Maryland subject, and independently "
            "retained campaign biography's Maryland House, Bowie and university continuity. "
            "No new nickname or historical-party transfer.",
        )
    key = "boafo-archived-manual-2024"
    if key in acquired:
        add(
            key,
            candidates["220484"],
            [
                claim(
                    "other_government",
                    {
                        "history": "National Press Assistant, U.S. Representative Ruben Kihuen, 2017-18"
                    },
                    "National Press Assistant, U.S. Representative Ruben Kihuen, "
                    "4th Congressional District, Nevada, 2017-18.",
                    reason="Dated congressional staff job in the archived official 2024 manual. "
                    "Campaign management and corporate government affairs are not counted as "
                    "government employment.",
                    timing="employment_2017-2018_in_archived_2024_manual",
                ),
            ],
            subject_fragments=["ADRIAN A. BOAFO", "Mayor Pro Tem, City of Bowie, 2019-22."],
            identity="Official full name with middle initial independently bridged through the "
            "2025 official roster and retained native campaign's same elected Bowie/Maryland "
            "career and university history. Current contest identity remains unchanged.",
        )
    key = "ryerse-authored-interview-2026"
    if key in acquired:
        add(
            key,
            candidates["219846"],
            [
                claim(
                    "religion",
                    ["Christian"],
                    "Rob, do you consider yourself Christian? Yes. Yes, okay.",
                    analysis="other_christian",
                    reason="Candidate's affirmative response at 14:51 in a dated named "
                    "interview, corroborated by his own person-of-faith statement at 26:02. "
                    "The subsequent non-Christian statement is the host's, not the candidate's. "
                    "Generic Christian is not recoded Protestant.",
                    timing="interview_published_2026-02-02",
                ),
            ],
            publication_date="2026-02-02",
            identity="Named Arkansas 3 candidate and direct native campaign link in the episode "
            "description. Speaker 2 is introduced as Ryerse; host and guest statements separated.",
        )
    key = "nones-national-table-2026"
    if key not in acquired:
        return
    table = list(csv.reader((root / WORK / key).open(encoding="utf-8-sig")))
    if table[1][0] != "Last Updated: 11/16/26":
        raise ValueError("Unreviewed national religion-table vintage")
    previous = {
        r["candidate_id"]: r
        for r in read_rows(root / "results/house-characteristics-v7/candidate-traits.jsonl.gz")
        if r["trait"] == "religion"
    }
    for index, row in enumerate(table[:-1]):
        if len(row) != 9 or not re.fullmatch(r"(D|Independent)-[A-Z]{2} \(District \d+\)", row[2]):
            continue
        party, state, district = re.fullmatch(
            r"(D|Independent)-([A-Z]{2}) \(District (\d+)\)", row[2]
        ).groups()
        name = row[3].removeprefix("State Rep. ")
        matches = [
            c
            for c in candidates.values()
            if c["name"] == name
            and c["state"] == state
            and c["district"] == f"{int(district):02}"
            and (c["party"] == "Democratic") == (party == "D")
        ]
        label = row[6].strip('"')
        useful = (
            len(matches) == 1
            and not previous[matches[0]["candidate_id"]]["factual_qualified"]
            and label.casefold() != "scientist"
        )
        decisions.append(
            {
                "source_id": key,
                "csv_row": index + 1,
                "printed_name": row[3],
                "accepted": useful,
                "reason": "Explicit post-election religion report for an unknown field"
                if useful
                else "Already known, unmatched or Scientist is not an affiliation.",
            }
        )
        if not useful:
            continue
        add(
            key,
            matches[0],
            [
                claim(
                    "religion",
                    [label],
                    label,
                    reason="Explicit named affiliation label in the complete public national "
                    "table updated November 16, 2026. A dated third-party report, not inferred "
                    "from endorsement/caucus membership and not a pre-election value.",
                    timing="table_updated_2026-11-16_after_election",
                )
            ],
            scope={"start": ",".join(row[2:5]), "end": ",".join(table[index + 1][2:5])},
            publication_date="2026-11-16",
            identity="Exact full native name, House state/district and Democratic versus "
            "independent party in the national table; historical caucus rows excluded.",
        )


def supplemental_claims(root, acquired, candidates, add, decisions):
    for cid, (key, legal, committee, classification) in FEC_BRIDGES.items():
        if key not in acquired:
            continue
        item = claim(
            "incumbency",
            False,
            committee,
            factual=False,
            reason="Official FEC legal-name to explicitly named principal-committee bridge. "
            "Retained election classification still requires a unique person-contest match; "
            "this is not independently verified lifetime federal nonservice.",
            timing="2026_election_candidate_or_committee_filing",
        )
        item["v8_identity_bridge"] = {"legal_name": legal, "committee": committee}
        item["v8_review"]["evidence_role"] = "identity_only_retained_FEC_classification"
        add(
            key,
            candidates[cid],
            [item],
            subject_fragments=[legal, committee],
            identity="Explicit FEC authorizing candidate/principal campaign committee, same "
            "2026 House state/district/party, and full native name or its native quoted nickname.",
        )
    if "alaska-hafner-statement-2026" in acquired:
        add(
            "alaska-hafner-statement-2026",
            candidates["219755"],
            [
                claim(
                    "education",
                    {
                        "credential_description": "criminal-justice graduate; "
                        "specific credential level unspecified; other listed courses are not degrees"
                    },
                    "FORMAL EDUCATION: Denver College Criminal Justice GRADUATE",
                    reason="Candidate-submitted official 2026 statement. Graduate wording without "
                    "a credential level does not support a bachelor/master/doctorate code.",
                    timing="2026_general_election_candidate_statement",
                ),
            ],
            identity="Full candidate subject and registered Democratic party in the official Alaska statement.",
        )
    if "bradstock-wesa-survey-2026" in acquired:
        items = [
            claim(
                "education",
                {"reported_credential_category": "masters"},
                "B.A., Washington & Jefferson College; M.S., Troy State University",
                analysis="masters",
                reason="Explicit credential list in a dated pre-election "
                "named-candidate voter guide; not an invented degree from attendance.",
                timing="published_2026-10-05",
            ),
            claim(
                "military",
                True,
                "former U.S. Army helicopter pilot",
                analysis=True,
                reason="Explicit own former military service in a dated pre-election profile.",
                timing="published_2026-10-05",
            ),
            claim(
                "other_government",
                {
                    "history": "FBI Special Agent; later federal contractor "
                    "is not itself government employment"
                },
                "FBI Special Agent",
                reason="Explicit federal employee role, distinguished from subsequent contracting.",
                timing="published_2026-10-05",
            ),
            claim(
                "profession",
                {"history": "military, FBI, financial advisor and consultant; mixed"},
                "financial advisor and consultant",
                reason="Mixed occupational histories retained "
                "without forcing one existing principal family.",
                timing="published_2026-10-05",
            ),
        ]
        add(
            "bradstock-wesa-survey-2026",
            candidates["221041"],
            items,
            scope={"start": "Alan Bradstock Photo courtesy", "end": "WESA Candidate Survey"},
            publication_date="2026-10-05",
            identity="Full named Pennsylvania 14 Democratic candidate "
            "in WESA's dated election guide; opponent section excluded.",
        )
    path = root / WORK / "louisiana-house-candidates-2026"
    if not path.exists():
        return
    columns = [
        "Election",
        "OfficeTitle",
        "OfficeTitleDescription",
        "BallotFirstName",
        "BallotLastName",
        "BallotSuffix",
        "Party",
        "Race",
        "Gender",
        "Filed Date",
    ]

    def quoted_name(value):
        return normalized(re.sub(r"""['"]([^'"]+)['"]""", r'"\1"', value))

    for number, row in enumerate(csv.DictReader(path.open(encoding="utf-8-sig")), 2):
        district_number = re.match(r"\d+", row["OfficeTitleDescription"])
        district = f"{int(district_number[0]):02}"
        printed = row["BallotFirstName"] + " " + row["BallotLastName"]
        matches = [
            c
            for c in candidates.values()
            if c["state"] == "LA"
            and c["district"] == district
            and c["party"].startswith(row["Party"])
            and quoted_name(c["name"]) == quoted_name(printed)
        ]
        if len(matches) != 1:
            decisions.append(
                {
                    "source_id": "louisiana-house-candidates-2026",
                    "csv_row": number,
                    "printed_name": printed,
                    "accepted": False,
                    "reason": "No unique full-token native name/district/party match.",
                }
            )
            continue
        items = [
            claim(
                trait,
                [row[column]],
                f"{column}={row[column]}",
                reason="Explicit official candidate-filing classification. The source's "
                "Race/Gender field is retained literally, not inferred or treated as "
                "proof of a compatible historical author-classification comparison.",
                timing=f"filed_{row['Filed Date']}",
            )
            for trait, column in (("race", "Race"), ("gender", "Gender"))
            if row[column]
        ]
        add(
            "louisiana-house-candidates-2026",
            matches[0],
            items,
            scope={"csv_row": number},
            format="csv",
            columns=columns,
            subject_fragments=[
                f"BallotFirstName={row['BallotFirstName']} | BallotLastName={row['BallotLastName']}"
            ],
            identity="Exact official filing full tokens, House district and party; quote glyphs "
            "only normalized. Unmatched nicknames/middle initials remain held.",
        )


def register(root):
    root = Path(root)
    work = root / WORK
    candidates = {
        c["candidate_id"]: c for c in read_rows(root / "results/house/candidates.jsonl.gz")
    }
    journal_path = root / "data/house-characteristics-research.json"
    receipts_path = root / "data/house-characteristics-receipts.json"
    journal, receipts = json.loads(journal_path.read_text()), json.loads(receipts_path.read_text())
    cache = root / "data/raw/house-characteristics-v1"
    attempts = json.loads((work / "retrievals.json").read_text())
    attempts += json.loads((work / "campaign-retrievals.json").read_text())
    acquired = {r["id"]: r for r in attempts if r["status"] == "acquired"}
    sources, documents, decisions, seen = [], {}, [], set()

    def add(
        key,
        candidate,
        claims,
        scope=None,
        identity=None,
        *,
        subject_fragments=None,
        format=None,
        columns=None,
        publication_date=None,
    ):
        attempt = acquired[key]
        original = root / attempt.get("cached_path", f"{WORK}/{key}")
        if fingerprint(original) != {k: attempt[k] for k in ("bytes", "sha256")}:
            raise ValueError(f"Changed original: {key}")
        document = f"v8-{key}"
        source = {
            **{k: candidate[k] for k in IDENTITY},
            "id": f"{document}-{candidate['candidate_id']}",
            "document_id": document,
            "kind": "candidate_submitted_official_election_pamphlet"
            if scope and "page" in scope
            else "original_roster_linked_campaign_biography",
            "url": attempt["url"],
            "publication_date": publication_date,
            "publication_date_precision": "day" if publication_date else "unspecified",
            "factual_reference": "2026_general_election_statement"
            if scope
            else "field_specific_historical_dates_or_undated_report_as_retrieved",
            "text_scope": scope or {},
            "identity_qualification": identity,
            "claims": claims,
        }
        source["kind"] = {
            "identity-filings": "official_FEC_candidate_committee_identity_bridge",
            "official-filings": "official_candidate_filing_classifications",
            "national-questionnaires": "dated_named_candidate_voter_guide",
            "official-legislative-biography": "official_legislative_biography",
            "national-interviews": "dated_named_candidate_interview",
            "religion-discovery": "dated_explicit_affiliation_compilation",
        }.get(attempt.get("family"), source["kind"])
        if not (scope and "page" in scope and attempt.get("family") == "official-voter-guides"):
            source["factual_reference"] = "per_claim_factual_timing_not_retrieval_date"
        if format:
            source["format"] = format
        if columns:
            source["columns"] = columns
        text = source_text(original.read_bytes(), source)
        name = normalized(candidate["name"])
        alternatives = [
            name,
            normalized(
                " ".join(part for part in candidate["name"].split() if len(part.rstrip(".")) != 1)
            ),
        ]
        printed = next((name for name in alternatives if name in normalized(text)), None)
        if subject_fragments:
            if any(normalized(fragment) not in normalized(text) for fragment in subject_fragments):
                raise ValueError(f"Unsupported explicit subject bridge: {key}")
            printed = subject_fragments[0]
            for item in claims:
                item.setdefault("identity_support", []).extend(subject_fragments)
        if not printed:
            decisions.append(
                {
                    "source_id": key,
                    "candidate_id": candidate["candidate_id"],
                    "accepted": False,
                    "reason": "No literal candidate subject bridge",
                }
            )
            return
        source["identity_fragment"] = printed
        receipt = {
            "id": source["id"],
            "url": attempt["url"],
            "resolved_url": attempt["resolved_url"],
            "retrieved_at": attempt["retrieved_at"],
            "retrieval_method": attempt["retrieval_method"],
            "original_bytes_acquired": True,
            **{k: attempt[k] for k in ("bytes", "sha256")},
        }
        unique = []
        for item in claims:
            signature = (
                candidate["candidate_id"],
                item["trait"],
                normalized(item["fragment"]),
                json.dumps(item["value"], sort_keys=True),
            )
            if signature not in seen:
                unique.append(item)
                seen.add(signature)
        source["claims"] = unique
        if not unique:
            return
        reviewed_claims(source, receipt, text)
        destination = cache / document
        if destination.exists() and fingerprint(destination) != fingerprint(original):
            raise ValueError(f"Changed shared original: {document}")
        if not destination.exists():
            shutil.copyfile(original, destination)
        sources.append(source)
        documents[document] = {"id": document, **{k: v for k, v in receipt.items() if k != "id"}}
        receipts["sources"] = [r for r in receipts["sources"] if r["id"] != source["id"]]
        receipts["sources"].append({**receipt, "status": "acquired_pending_review"})
        decisions.append(
            {
                "source_id": key,
                "candidate_id": candidate["candidate_id"],
                "accepted": True,
                "reason": identity,
            }
        )

    for draft in json.loads((work / "guide-reading.json").read_text()):
        if len(draft["native_matches"]) != 1:
            decisions.append(
                {
                    "source_id": draft["source_id"],
                    "printed_name": draft["printed_name"],
                    "accepted": False,
                    "reason": "Printed/native name discrepancy; not silently bridged",
                }
            )
            continue
        candidate = candidates[draft["native_matches"][0]]
        original = root / WORK / draft["source_id"]
        # Reparse the hashed original rather than trusting a discovery draft.
        from pypdf import PdfReader

        page = PdfReader(original).pages[draft["page"] - 1].extract_text() or ""
        parser = oregon_statement if draft["state"] == "OR" else washington_statement
        statement = parser(page)
        if (
            not statement
            or normalized(statement["printed_name"]) != normalized(candidate["name"])
            or statement["district"] != candidate["district"]
            or not candidate["party"].startswith(statement["printed_party"])
            or statement["fields"] != draft["fields"]
        ):
            raise ValueError(f"Changed guide subject/fields: {draft['source_id']}:{draft['page']}")
        heading = candidate["name"].split()
        fragments = [heading[0], heading[-1]]
        add(
            draft["source_id"],
            candidate,
            guide_claims(draft, candidate),
            scope={"page": draft["page"]},
            subject_fragments=fragments,
            identity="Official 2026 candidate heading, printed state/district/party and "
            "literal native name; first/surname PDF reading order checked by the subject parser.",
        )
    reviews = json.loads((root / NATIONAL_REVIEW).read_text())["sources"]
    for key, entries in json.loads(
        (root / "data/house-characteristics-v8-followup-review.json").read_text()
    )["sources"].items():
        reviews.setdefault(key, []).extend(entries)
    for key, entries in reviews.items():
        attempt = acquired[key]
        candidate = candidates[attempt["candidate_id"]]
        nickname = re.search(r'"([^"]+)"', candidate["name"])
        fragments = [nickname[1] + " " + candidate["name"].split()[-1]] if nickname else None
        add(
            key,
            candidate,
            national_claims(entries, key),
            subject_fragments=fragments,
            identity="Native candidate's roster-linked campaign URL, original named biography "
            "and same current House campaign; no historical cross-contest transfer.",
        )
    supplemental_claims(root, acquired, candidates, add, decisions)
    institutional_claims(root, acquired, candidates, add, decisions)
    journal["sources"] = [s for s in journal["sources"] if not s["id"].startswith("v8-")] + sources
    receipts["sources"] = [
        r
        for r in receipts["sources"]
        if not r["id"].startswith("v8-") or r["id"] in {s["id"] for s in sources}
    ]
    write_json(journal_path, journal)
    write_json(receipts_path, receipts)
    write_json(root / "data/house-characteristics-v8-identity-decisions.json", decisions)
    result = {
        "documents": list(documents.values()),
        "sources": sources,
        "new_acquired_claims": sum(len(s["claims"]) for s in sources),
        "new_document_hashes": len({d["sha256"] for d in documents.values()}),
        "discovery_dispositions": attempts,
        "source_population": "Official OR/WA congressional statements and nationally "
        "roster-linked Democratic nonincumbent campaign biographies; not universal coverage.",
        "qualification": "Undated credentials/affiliations remain factual reports, not "
        "automatically pre-election analytical values; service omissions never become negatives.",
    }
    write_json(root / "data/house-characteristics-v8-acquisitions.json", result)
    return {
        "sources": len(sources),
        "documents": len(documents),
        "claims": result["new_acquired_claims"],
    }


if __name__ == "__main__":
    print(json.dumps(register(Path(__file__).resolve().parents[1]), indent=2))
