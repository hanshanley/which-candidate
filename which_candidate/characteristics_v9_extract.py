"""Reviewed extraction corrections and jurisdiction-specific filing adapters."""

import json
import re
import shutil
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from pypdf import PdfReader

from .characteristics_research import normalized, reviewed_claims, source_text
from .characteristics_v7 import orthographic
from .characteristics_v8_campaigns import BiographyLinks
from .characteristics_v8_extract import claim as previous_claim
from .characteristics_v9_acquisition import WORK
from .characteristics_v9_controls import register_walker
from .characteristics_v9_retained import additional_reviews
from .storage import fingerprint, read_rows, write_json

IDENTITY = ("candidate_id", "contest_id", "name", "state", "district", "party")
ACQUISITIONS = "data/house-characteristics-v9-acquisitions.json"


def claim(trait, value, fragment, **kwargs):
    kwargs.setdefault("timing", "undated_candidate_report")
    result = previous_claim(trait, value, fragment, **kwargs)
    result["v9_review"] = result.pop("v8_review")
    return result


def education(fragment, category=None, year=None):
    return claim(
        "education",
        {"reported_education": fragment, "completed_credential": category, "reference_year": year},
        fragment,
        analysis=category if year else None,
        reason="Literal candidate-authored education statement; attendance and unspecified "
        "degrees are not assigned a completed attainment category. Undated credentials remain "
        "factual reports rather than automatically pre-election analytical values.",
        timing=f"completed_{year}" if year else "undated_candidate_report",
    )


def pamphlet_age(age, fragment):
    return claim(
        "age",
        {
            "reported_age": age,
            "reference_year": 2026,
            "birth_date_interval": [f"{2025 - age}-01-02", f"{2026 - age}-12-31"],
        },
        fragment,
        timing="2026_pamphlet_age_reference_day_unspecified",
        reason="Literal 2026 pamphlet age without a specified reference day. Conservative "
        "birth interval covers an age reported anywhere in 2026; no birthday or exact "
        "November 3 age is invented.",
    )


def reviewed_alias_subject(candidate, text, attempt, bridge, body):
    if (
        attempt.get("candidate_id") != candidate["candidate_id"]
        or bridge.get("candidate_id") != candidate["candidate_id"]
    ):
        return None
    identity = (candidate["candidate_id"], candidate["name"])
    if identity == ("220468", "Matthew Dunlap"):
        evidence = normalized(source_text(body, {"text_scope": {"page": 20}}))
        if all(
            normalized(marker) in evidence
            for marker in ("Matthew Dunlap", "Matt Dunlap", "Old Town", "University of Maine")
        ) and all(
            normalized(marker) in normalized(text)
            for marker in ("Matt Dunlap", "Old Town", "University of Maine")
        ):
            return "Matt Dunlap"
    if identity == ("220853", "Michael DeCillis"):
        evidence = normalized(source_text(body, {}))
        origin = bridge.get("resolved_url", bridge["url"])
        target = attempt.get("resolved_url", attempt["url"])
        links = BiographyLinks()
        links.feed(body.decode(errors="replace"))
        if (
            all(
                normalized(marker) in evidence
                for marker in ("Michael DeCillis", "Mike DeCillis", "Nicole Malliotakis")
            )
            and urlsplit(origin).netloc == urlsplit(target).netloc
            and target in {urljoin(origin, href) for href, _ in links.links}
            and "mike decillis" in normalized(text)
        ):
            return "Mike DeCillis"
    if identity == ("220677", "Brian Miller"):
        evidence = normalized(source_text(body, {"text_scope": {"page": 10}}))
        domain = urlsplit(attempt.get("resolved_url", attempt["url"])).netloc
        if (
            all(
                normalized(marker) in evidence
                for marker in (
                    "Brian J. Miller",
                    "Eastern Congressional District",
                    "Location: Helena",
                )
            )
            and domain in re.sub(r"\s+", "", evidence)
            and all(
                marker in normalized(text)
                for marker in ("more about me", "second congressional district", "patricia cotter")
            )
        ):
            return "More about me"
    linked_subjects = {
        ("220661", "Missi Hesketh"): ("Meet Missi", "Missi was born", "teaching for 22 years"),
        ("220833", "Patrick Halpin"): ("Pat Halpin", "County Legislature", "County Executive"),
        ("220950", "Jen Mazzuckelli"): (
            "Of the People",
            "My Journey",
            "Ohio's 2nd Congressional District",
        ),
        ("220977", "Jerrad Christian"): (
            "My Life Story",
            "join the US Navy",
            "Ohio’s 12th Congressional district",
        ),
    }
    if identity in linked_subjects:
        evidence = normalized(source_text(body, {}))
        origin = bridge.get("resolved_url", bridge["url"])
        target = attempt.get("resolved_url", attempt["url"])
        links = BiographyLinks()
        links.feed(body.decode(errors="replace"))
        markers = linked_subjects[identity]
        if (
            normalized(candidate["name"]) in evidence
            and urlsplit(origin).netloc == urlsplit(target).netloc
            and target in {urljoin(origin, href) for href, _ in links.links}
            and all(normalized(marker) in normalized(text) for marker in markers)
        ):
            return markers[0]
    return None


def alaska_reviews():
    return {
        "alaska-begich-uncovered-statement-2026": (
            "219754",
            "Nick Begich",
            [
                pamphlet_age(48, "Age: 48"),
                education("Baylor University (BBA), Indiana University (MBA)", "masters"),
                claim(
                    "profession",
                    {
                        "current_occupation": "U.S. Representative (AK)",
                        "reported_history": "Founder and Previous Executive Chairman, Farshore Partners (2006-2024); "
                        "Ford Motor Company Product Marketing Manager, Technology Manager (2002-2004)",
                    },
                    "Occupation: U.S. Representative (AK)",
                    reason="Current office and dated business history remain distinct; "
                    "not automatically one historical occupational family.",
                ),
                claim(
                    "prior_elected_office",
                    {"reported_office": "U.S. Representative (AK)"},
                    "Political and Government Positions:",
                    reason="Named federal office is retained separately from party and nonprofit positions; "
                    "not a before-first-House-entry history.",
                ),
                claim(
                    "religion",
                    {"reported_congregational_membership": "ACF Church"},
                    "American Legion, ACF Church",
                    reason="Explicit candidate-listed church membership, not automatic Protestant "
                    "classification or a dated historical-questionnaire affiliation.",
                ),
            ],
        ),
        "alaska-hill-uncovered-statement-2026": (
            "219757",
            "Bill Hill",
            [
                pamphlet_age(57, "Age: 57"),
                education("University of Phoenix - Masters, Education Administration", "masters"),
                claim(
                    "race",
                    {"self_description": "Dena’ina Athabascan"},
                    "I’m Dena’ina Athabascan and a working man",
                    reason="Explicit first-person Indigenous self-description; not an extension "
                    "of the restricted historical Black/White contrast.",
                ),
                claim(
                    "gender",
                    {"self_description": "man"},
                    "I’m Dena’ina Athabascan and a working man",
                    reason="Explicit first-person description, not inferred from a name or photograph.",
                ),
                claim(
                    "profession",
                    {
                        "current_occupation": "Commercial Fisherman",
                        "reported_careers": [
                            "teacher",
                            "principal",
                            "superintendent",
                            "construction worker",
                            "commercial fisherman",
                        ],
                    },
                    "Occupation: Commercial Fisherman",
                    reason="Current occupation and multiple reported careers preserved; "
                    "no forced principal occupational family.",
                ),
                claim(
                    "other_government",
                    {
                        "employment_history": "Superintendent, Bristol Bay School District (2013-2023); "
                        "Student Services Director, Lake and Peninsula School District (2009-2013)"
                    },
                    "Superintendent, Bristol Bay School District (2013-2023)",
                    timing="documented_employment_2013-2023",
                    reason="Explicit dated school-district employment; not inferred from "
                    "village-corporation board membership.",
                ),
            ],
        ),
        "alaska-mcdermott-uncovered-statement-2026": (
            "219756",
            "James C. McDermott",
            [
                pamphlet_age(68, "Age: 68"),
                education("M.S. in Business Organizational Management", "masters"),
                claim(
                    "profession",
                    {
                        "current_occupation": "Writer",
                        "reported_careers": [
                            "writer",
                            "instructor",
                            "college recruiter",
                            "warehouse foreman",
                        ],
                    },
                    "Occupation: Writer",
                    reason="Current writing occupation and several other careers retained "
                    "without forcing one historical family.",
                ),
                claim(
                    "military",
                    {"reported_service": "U.S. Air Force, 22 1/2 years; retired Master Sergeant"},
                    "22 1/2 years in the U.S. Air Force and retired as a Master Sergeant.",
                    timing="reported_retired_service_exact_dates_unspecified",
                    reason="Explicit personal service, not inferred from American Legion "
                    "membership; exact service dates remain unspecified.",
                ),
                claim(
                    "other_government",
                    {"reported_employment": "Warehouse Foreman Anchorage School District"},
                    "Warehouse Foreman Anchorage School District",
                    reason="Explicit school-district job, distinct from an unspecified "
                    "election-commission appointment; employment dates remain unknown.",
                ),
            ],
        ),
    }


def retained_reviews():
    return {
        "campaign-219735-bio1": [
            claim(
                "race",
                {"reported_race": ["African-American"]},
                "After being elected the first African-American on Pelham City Council",
                reason="Explicit named candidate's own campaign classification; not a proxy or "
                "an extension of the restricted historical Black/White estimand.",
            )
        ],
        "campaign-219790-bio1": [
            claim(
                "gender",
                {"reported_gender": "woman"},
                "Bernadette would bring a working-class woman’s voice to Congress",
                reason="Explicit candidate-authored description, not inference from a name or image.",
            )
        ],
        "campaign-219871-home": [
            claim(
                "race",
                {"reported_race": ["Asian American"]},
                "she would make history as the first Asian American to represent San Francisco in Congress",
                reason="Classification explicitly reproduced on the named candidate's campaign; "
                "no historical race contrast assigned.",
            )
        ],
        "campaign-219877-bio1": [
            claim(
                "ethnicity",
                {"reported_ethnicity": ["Latina"]},
                "A Latina Leader & Working Mom",
                reason="Explicit own-campaign description; not pooled with historical author-coded ethnicity.",
            )
        ],
        "campaign-220967-bio1": [
            claim(
                "religion",
                {"reported_affiliation": "Christian minister"},
                "Enoch is a Christian Minister and the first woman Deacon in her 105+ year-old church.",
                reason="Explicit own-campaign affiliation; generic Christian is not automatically Protestant.",
            )
        ],
        "campaign-140485-home": [
            education(
                "He holds degrees from Tarrant County College, Texas Tech University "
                "(graduating Summa Cum Laude), and the University of Texas at Arlington."
            )
        ],
        "campaign-140491-bio1": [
            education("After graduating from Leander High School in 1998", year=1998)
        ],
        "campaign-205780-home": [
            education("A graduate of Mississippi College and the Columbia University School of Law")
        ],
        "campaign-219895-bio1": [
            education(
                "Randy became the first in his family to earn a Ph.D.", "doctoral_or_professional"
            )
        ],
        "campaign-219910-bio1": [
            education(
                "a Master’s Degree in Organizational Leadership from Woodbury University", "masters"
            )
        ],
        "campaign-219928-bio1": [
            education("I attended Santa Monica College for Political Science"),
            claim(
                "age",
                {"birth_year": 1998, "birth_month": 9},
                "Sep 1998 Sam was born",
                reason="Explicit birth month and year on the native campaign's life timeline; "
                "no day invented. All possible September birthdays imply age 28 on November 3, 2026.",
                timing="explicit_birth_month_and_year",
            ),
            claim(
                "other_government",
                {
                    "history": "appointed to Santa Monica Public Safety Reform & Oversight Commission, January 2021"
                },
                "Jan 2021 Appointed to Santa Monica's Public Safety Reform & Oversight Commission",
                factual=False,
                reason="Explicit appointed commission role, not evidence of paid government employment.",
                timing="appointed_2021_not_paid_employment_evidence",
            ),
        ],
        "campaign-220083-bio1": [education("After graduating from college")],
        "campaign-220086-bio1": [
            education("earned a Juris Doctorate", "doctoral_or_professional"),
            claim(
                "other_government",
                {
                    "history": "U.S. Environmental Protection Agency federal service and political appointment"
                },
                "began her Federal service career at the U.S. Environmental Protection Agency",
                reason="Explicit federal employment, not inferred from advocacy, a fellowship "
                "or private-sector federal contracting.",
            ),
        ],
        "campaign-220117-home": [
            education(
                "After earning his bachelor's and master's degrees from Georgetown University",
                "masters",
            )
        ],
        "campaign-220172-bio1": [
            education(
                "Amanda holds a B.A. in American Studies from the University of California, Berkeley",
                "bachelors",
            )
        ],
        "campaign-220184-home": [
            education(
                "2021 Georgia State University College of Law Juris Doctor, summa cum laude",
                "doctoral_or_professional",
                2021,
            )
        ],
        "campaign-220455-bio1": [
            education("earning a Bachelor of Arts in History in 2009", "bachelors", 2009),
            claim(
                "other_government",
                {
                    "history": "Department of Defense Morale, Welfare, and Recreation Recreational Specialist and Supervisor, 2003-2010"
                },
                "from 2003 to 2010-- working with the United States Department of Defense",
                reason="Explicit dated civilian federal job; work with military members is "
                "not personal military service.",
                timing="employment_2003-2010",
            ),
        ],
        "campaign-220468-home": [
            education("He is a proud graduate of the University of Maine"),
            claim(
                "profession",
                {"reported_careers": ["dishwasher", "bartender", "fur-trapper", "State Auditor"]},
                "worked as a dishwasher, bartender, and fur-trapper",
                reason="Multiple historical jobs and current public role retained without "
                "forcing a single principal occupation.",
            ),
            claim(
                "religion",
                {
                    "reported_church_role": "assistant to the treasurer of his local Episcopal Church"
                },
                "assistant to the treasurer of his local Episcopal Church",
                factual=False,
                reason="Explicit church role retained, but a role alone is not an explicit "
                "personal belief or affiliation statement and does not qualify a religion category.",
            ),
        ],
        "campaign-220646-bio1": [
            education("attaining a Master's degree as a Presidential Scholar", "masters"),
        ],
        "campaign-220677-bio1": [
            education("I graduated from University of Montana Law School in 2007", year=2007),
            claim(
                "other_government",
                {
                    "history": "Montana Supreme Court clerk, three years between 2007 graduation and September 2010 private practice"
                },
                "I clerked at the Montana Supreme Court for three years under Justice Patricia Cotter.",
                reason="Explicit dated judicial clerkship, distinct from later private legal practice.",
                timing="clerkship_after_2007_before_September_2010",
            ),
            claim(
                "age",
                {"birth_year": 1972},
                "I was born in Cleveland, Ohio in 1972",
                timing="explicit_birth_year_exact_day_unknown",
                reason="Explicit birth year, not an invented birthday or exact election age.",
            ),
            claim(
                "profession",
                {"reported_careers": ["bus driver", "judicial clerk", "civil trial attorney"]},
                "I became a partner at that firm in 2014",
                timing="dated_career_history_1998-2014_and_later",
                reason="Multiple explicitly reported jobs and dated legal career retained "
                "without forcing one historical principal profession.",
            ),
        ],
        "campaign-220811-home": [
            education(
                "she earned her M.B.A., with honors, from the University of Pennsylvania’s Wharton School of Business",
                "masters",
            )
        ],
        "campaign-220853-bio1": [
            education("earned his Juris Doctorate", "doctoral_or_professional"),
            education("completed a Masters in Education from Hunter College", "masters"),
            claim(
                "profession",
                {"reported_careers": ["paramedic", "police officer", "attorney", "teacher"]},
                "a NYPD officer, serving for a decade",
                reason="Multiple explicitly reported careers, not a forced single principal profession.",
            ),
            claim(
                "other_government",
                {
                    "reported_employment": [
                        "NYPD officer",
                        "Chief of Staff and Director of Legislation in the New York State Assembly",
                        "New York City District 75 teacher",
                    ]
                },
                "serving as Chief of Staff and Director of Legislation in the New York State Assembly",
                reason="Explicit government jobs distinguished from volunteer EMT service; "
                "undated employment is not a complete pre-entry employment history.",
            ),
        ],
        "campaign-220859-bio1": [
            education("a PhD student at CUNY"),
            claim(
                "ethnicity",
                {"reported_ethnicity": ["Dominican"]},
                "Darializa is a working-class Dominican New Yorker",
                reason="Explicit description on the fully named candidate's own biography; "
                "not inferred from her relatives or extended to historical analytical codes.",
            ),
        ],
        "campaign-220915-bio1": [
            education(
                "earn her PhD in Social Work at Morgan State University", "doctoral_or_professional"
            )
        ],
        "campaign-220917-bio1": [
            education("I earned my high school diploma through homeschooling")
        ],
        "campaign-220925-bio1": [
            education("earned degrees from Warren Wilson College in Environmental Studies")
        ],
        "campaign-220982-bio1": [
            education(
                "a Master’s in Theology and Religious Studies from John Carroll University in 2022",
                "masters",
                2022,
            )
        ],
        "campaign-221045-bio1": [
            education(
                "I continued my education at ITT Technical Institute and took additional classes at Youngstown State University"
            )
        ],
        "campaign-221121-bio1": [
            education("Bobby studied political science before pursuing a music career")
        ],
        "campaign-221146-bio1": [
            education("Johnny Garcia is a proud graduate of Memorial High School")
        ],
        "campaign-221175-bio1": [education("While getting her doctorate in Civil Engineering")],
        "campaign-221195-home": [education("He went on to earn a PhD", "doctoral_or_professional")],
        "campaign-221249-bio1": [
            education(
                "I studied political science and commerce and cheered for the Mountaineers at West Virginia University"
            )
        ],
        "campaign-42478026-bio1": [
            education(
                "DOCTOR OF PHILOSOPHY (PhD) PUBLIC POLICY & POLICY ANALYSIS | WALDEN UNIVERSITY | 2018",
                "doctoral_or_professional",
                2018,
            ),
            claim(
                "race",
                {"reported_race": ["Black"]},
                "the first and only Black Nuclear Operator during my service period on the vessel",
                reason="Explicit first-person racial self-description; not a historical author code.",
            ),
            claim(
                "military",
                {
                    "served": True,
                    "branch": "United States Navy",
                    "documented_role_interval": "1999-2002",
                    "complete_service_dates": None,
                },
                "NUCLEAR TRAINED SAILOR UNITED STATES NAVY | 1999-2002",
                analysis=True,
                timing="documented_Navy_role_1999-2002",
                reason="Explicit pre-election naval role establishes positive service. "
                "This role interval is not asserted to delimit the whole Navy career: "
                "the same biography also reports active service during 2006 studies.",
            ),
        ],
    }


def california_rows(path):
    """Return literal federal candidate entries, retaining page and district boundaries."""
    result = []
    district = None
    for number, page in enumerate(PdfReader(path).pages, 1):
        lines = [line.strip() for line in (page.extract_text() or "").splitlines() if line.strip()]
        index = 0
        while index < len(lines):
            line = lines[index]
            header = re.fullmatch(r"United States Representative District (\d+)", line)
            if header:
                district = f"{int(header[1]):02d}"
            elif re.match(r"State (?:Senate|Assembly) District ", line):
                district = None
            elif district:
                candidate = re.fullmatch(
                    r"(.+?)\s+(Democratic|Republican|No Party Preference|Green|Libertarian)", line
                )
                if candidate:
                    designation = lines[index + 1] if index + 1 < len(lines) else ""
                    if re.match(
                        r"(?:United States Representative District|General Election|Page \d)",
                        designation,
                    ):
                        raise ValueError(f"Missing California designation on page {number}")
                    result.append(
                        {
                            "printed_name": candidate[1],
                            "party": candidate[2],
                            "district": district,
                            "page": number,
                            "designation": designation,
                        }
                    )
                    index += 1
            index += 1
    if len(result) != 104 or len({r["district"] for r in result}) != 52:
        raise ValueError("Incomplete California congressional candidate list")
    return result


def fec_ballot_bridge(candidate, filing, official_records):
    identity = candidate.get("identity", {})
    records = identity.get("official_alternatives", [])
    if identity.get("status") != "official_name_party_year_state" or len(records) != 1:
        return None
    record = records[0]
    if (
        record not in official_records
        or identity.get("fec_id") != record["fec_id"]
        or candidate["state"] != record["state"]
        or record["state"] != "CA"
        or candidate["district"] != record["district"]
        or record["district"] != filing["district"]
        or candidate["party"] != filing["party"]
        or record["party"] != {"Democratic": "DEM", "Republican": "REP"}.get(filing["party"])
        or record["chamber"] != "house"
        or record["election_year"] != 2026
        or normalized(f"{record['first']} {record['last']}") != normalized(filing["printed_name"])
    ):
        return None
    return record


def register(root):
    root = Path(root)
    candidates = read_rows(root / "results/house/candidates.jsonl.gz")
    by_id = {c["candidate_id"]: c for c in candidates}
    old = json.loads((root / "data/house-characteristics-v8-acquisitions.json").read_text())
    retained = {r["id"]: r for r in old["discovery_dispositions"] if r["status"] == "acquired"}
    attempts = json.loads((root / WORK / "retrievals.json").read_text())
    acquired = {r["id"]: r for r in attempts if r["status"] == "acquired"}
    journal_path = root / "data/house-characteristics-research.json"
    receipts_path = root / "data/house-characteristics-receipts.json"
    journal = json.loads(journal_path.read_text())
    receipts = json.loads(receipts_path.read_text())
    sources, documents, decisions = [], {}, []
    cache = root / "data/raw/house-characteristics-v1"

    def add(
        key,
        candidate,
        claims,
        scope=None,
        *,
        kind=None,
        date=None,
        subject=None,
        identity_reason=None,
        columns=None,
    ):
        reused = key in retained
        attempt = retained[key] if reused else acquired[key]
        original = root / attempt.get("cached_path", f"{WORK}/{key}")
        if reused and not attempt.get("cached_path"):
            original = root / "artifacts/characteristics-v8" / key
        if fingerprint(original) != {k: attempt[k] for k in ("bytes", "sha256")}:
            raise ValueError(f"Changed original: {key}")
        document = f"v9-{key}"
        source = {
            **{k: candidate[k] for k in IDENTITY},
            "id": f"{document}-{candidate['candidate_id']}",
            "document_id": document,
            "url": attempt["url"],
            "kind": kind
            or (
                "retained_native_campaign_extraction_correction"
                if reused
                else "candidate_submitted_certified_ballot_designation"
            ),
            "publication_date": date if kind else None if reused else "2026-08-27",
            "publication_date_precision": (
                "month" if date and len(date) == 7 else "year" if date and len(date) == 4 else "day"
            )
            if date or not reused and not kind
            else "unspecified",
            "identity_qualification": identity_reason
            or "Exact native campaign original URL and literal named "
            "subject; for California, exact normalized name, House district and party.",
            "text_scope": scope or {},
            "claims": claims,
            "evidence_acquisition_role": "retained_original_new_extraction"
            if reused
            else "new_original",
        }
        if columns:
            source.update(format="csv", columns=columns)
        text = source_text(original.read_bytes(), source)
        name = normalized(candidate["name"])
        alternatives = [
            name,
            normalized(" ".join(p for p in candidate["name"].split() if len(p.rstrip(".")) != 1)),
        ]
        name = next((n for n in alternatives if n in normalized(text)), None)
        explicit = {
            "220455": 'Lindsay "Rubia" Garcia',
            "219910": ("Angelica Dueñas", "Angélica Dueñas"),
            "219928": "Sam Mota",
            "220184": "Tony Kozycki",
            "220915": "Kimberly Hardy",
            "220086": "LaShonda “L.J.” Holloway",
            "205786": "Michael A. Chiaradio",
        }.get(candidate["candidate_id"])
        if explicit and not name:
            for alternative in explicit if isinstance(explicit, tuple) else (explicit,):
                if normalized(alternative) in normalized(text):
                    name = alternative
                    break
        if subject and normalized(subject) in normalized(text):
            name = subject
        bridge_key = {
            "220468": "maine-dunlap-legislative-biography-2004",
            "220853": "decillis-native-campaign-name-bridge",
            "220677": "montana-miller-authored-questionnaire-2026",
            "220661": "campaign-220661-home",
            "220833": "campaign-220833-home",
            "220950": "campaign-220950-home",
            "220977": "campaign-220977-home",
        }.get(candidate["candidate_id"])
        if not name and bridge_key and (bridge_key in acquired or bridge_key in retained):
            bridge = acquired.get(bridge_key) or retained[bridge_key]
            bridge_path = root / bridge.get("cached_path", f"{WORK}/{bridge_key}")
            if fingerprint(bridge_path) != {k: bridge[k] for k in ("bytes", "sha256")}:
                raise ValueError(f"Changed alias bridge: {bridge_key}")
            name = reviewed_alias_subject(
                candidate, text, attempt, bridge, bridge_path.read_bytes()
            )
            if name:
                metadata = {k: bridge[k] for k in ("id", "url", "sha256", "retrieved_at", "bytes")}
                source["identity_qualification"] = (
                    "Narrow native-person alias review: full legal and familiar names in "
                    "the retained supporting original; Dunlap additionally matches Old Town "
                    "and University of Maine, DeCillis has a direct same-host biography link, "
                    "Miller's named MT02 questionnaire supplies the exact native campaign domain, "
                    "and linked biographies have full-native-name homepages directly linking their "
                    "same-host biographies, with additional literal subject/career anchors."
                )
                for item in claims:
                    item["v9_subject_bridge"] = metadata
                documents[f"v9-{bridge_key}"] = metadata
        if not name and candidate["candidate_id"] == "42478026":
            bridge = retained["campaign-42478026-home"]
            bridge_path = root / bridge.get(
                "cached_path", "artifacts/characteristics-v8/campaign-42478026-home"
            )
            if fingerprint(bridge_path) != {k: bridge[k] for k in ("bytes", "sha256")}:
                raise ValueError("Changed Kelly Esti identity bridge")
            homepage = bridge_path.read_bytes()
            links = BiographyLinks()
            links.feed(homepage.decode(errors="replace"))
            bridge_url = bridge.get("resolved_url", bridge["url"])
            subject_url = attempt.get("resolved_url", attempt["url"])
            targets = {urljoin(bridge_url, u) for u, _ in links.links}
            if (
                subject_url in targets
                and urlsplit(subject_url).netloc == urlsplit(bridge_url).netloc
                and "kelly esti" in normalized(source_text(homepage, {}))
                and "about kelly" in normalized(text)
            ):
                name = "About Kelly"
                source["identity_qualification"] = (
                    "Native campaign homepage explicitly names Kelly Esti and GA08 and links "
                    "directly to this same-host About Kelly biography. Both originals hash-verified."
                )
                source["identity_bridge"] = {
                    "source_id": bridge["id"],
                    "url": bridge["url"],
                    "sha256": bridge["sha256"],
                }
        if not name:
            decisions.append(
                {
                    "source_id": key,
                    "candidate_id": candidate["candidate_id"],
                    "accepted": False,
                    "reason": "Literal subject bridge needs review",
                }
            )
            return
        source["identity_fragment"] = name
        receipt = {
            k: attempt[k]
            for k in ("url", "resolved_url", "retrieved_at", "retrieval_method", "bytes", "sha256")
        }
        receipt.update(id=source["id"], original_bytes_acquired=True)
        reviewed_claims(source, receipt, text)
        destination = cache / document
        if destination.exists() and fingerprint(destination) != fingerprint(original):
            raise ValueError(f"Changed shared original: {document}")
        if not destination.exists():
            shutil.copyfile(original, destination)
        sources.append(source)
        documents[document] = {**receipt, "id": document}
        receipts["sources"] = [r for r in receipts["sources"] if r["id"] != source["id"]]
        receipts["sources"].append({**receipt, "status": "acquired_pending_review"})
        decisions.append(
            {
                "source_id": key,
                "candidate_id": candidate["candidate_id"],
                "accepted": True,
                "role": source["evidence_acquisition_role"],
            }
        )

    reviews = retained_reviews()
    for key, claims in additional_reviews(claim, education).items():
        reviews.setdefault(key, []).extend(claims)
    for key, claims in reviews.items():
        add(key, by_id[retained[key]["candidate_id"]], claims)
    register_walker(root, add, acquired, by_id, claim)
    if "maine-dunlap-legislative-biography-2004" in acquired:
        add(
            "maine-dunlap-legislative-biography-2004",
            by_id["220468"],
            [
                claim(
                    "education",
                    {"completed_credential": "masters", "documented_by": "2004-12-01"},
                    "a master's in English",
                    analysis="masters",
                    timing="completed_by_dated_2004-12-01_legislative_record",
                    reason="Contemporaneous legislative biography explicitly reports completed "
                    "bachelor's and master's degrees. Record date is an upper completion bound, "
                    "not an invented graduation date.",
                ),
                claim(
                    "prior_elected_office",
                    {
                        "reported_office": "Maine House of Representatives",
                        "service_years_by_2004": 8,
                    },
                    "For eight years Matt Dunlap has been a member of the House of Representatives",
                    timing="documented_by_2004-12-01",
                    reason="Affirmative dated state legislative service; not a complete "
                    "before-first-House-entry history or a negative service comparison.",
                ),
                claim(
                    "profession",
                    {
                        "reported_careers": [
                            "radio co-host",
                            "columnist",
                            "journal editor",
                            "legislator",
                        ]
                    },
                    "Currently he co-hosts a radio show",
                    timing="dated_2004-12-01_historical_occupations",
                    reason="Dated historical jobs remain distinct from current occupation and "
                    "are not forced into one historical principal-profession category.",
                ),
            ],
            scope={"page": 20, "start": "Representative MILLS: Madam Chair, I nominate Matthew"},
            kind="dated_official_legislative_biography",
            date="2004-12-01",
        )
    if "montana-miller-authored-questionnaire-2026" in acquired:
        add(
            "montana-miller-authored-questionnaire-2026",
            by_id["220677"],
            [
                pamphlet_age(54, "Age: 54"),
                education("Law Degree- University of Montana (2007)", year=2007),
                claim(
                    "profession",
                    {"reported_occupation": "Attorney in civil litigation throughout Montana"},
                    "Occupation: Attorney in the practice of civil litigation",
                    timing="2026_questionnaire_reference_day_unspecified",
                    reason="Explicit authored occupation; not automatically a principal "
                    "historical profession classification.",
                ),
            ],
            scope={"page": 10, "start": "Eastern Congressional District"},
            kind="candidate_authored_professional_questionnaire",
            subject="Brian J. Miller",
            identity_reason="Named Democratic MT02 candidate questionnaire explicitly supplies "
            "the exact native campaign domain and Helena location. The same campaign biography "
            "and dated state-bar profile corroborate law school, clerkship and legal employment.",
        )
    if "montana-bar-miller-biography-2011" in acquired:
        add(
            "montana-bar-miller-biography-2011",
            by_id["220677"],
            [
                claim(
                    "education",
                    {
                        "completed_credential": "doctoral_or_professional",
                        "reported_credential": "JD, University of Montana",
                        "documented_by": "2011-02",
                    },
                    "his JD from the University of Montana",
                    analysis="doctoral_or_professional",
                    timing="completed_by_dated_2011-02_professional_biography",
                    reason="Dated professional biography explicitly reports the completed JD; "
                    "publication month is an upper completion bound, not an invented graduation date.",
                ),
                claim(
                    "other_government",
                    {
                        "reported_employment": "Three-year clerkship for Montana Supreme Court Justice Patricia Cotter"
                    },
                    "clerked for three years for Justice Patricia Cotter of the Montana Supreme Court",
                    timing="completed_by_dated_2011-02_professional_biography",
                    reason="Explicit dated judicial employment, corroborated by the candidate's "
                    "own 2007-2010 chronology; not volunteering or a complete negative history.",
                ),
            ],
            scope={
                "page": 27,
                "start": "Brian Miller received",
                "end": "Bar member Vincent Pavlish",
            },
            kind="dated_professional_association_biography",
            date="2011-02",
            identity_reason="Exact native full name with corroborating Emory BA, Montana JD, "
            "Patricia Cotter clerkship and law-firm chronology in the verified native campaign "
            "biography; named MT02 questionnaire explicitly links that campaign domain.",
        )
    for key, (cid, subject, claims) in alaska_reviews().items():
        if key in acquired:
            add(
                key,
                by_id[cid],
                claims,
                kind="candidate_submitted_official_pamphlet",
                subject=subject,
            )
    add(
        "ffrf-burke-dated-self-description",
        by_id["221173"],
        [
            claim(
                "religion",
                {"self_description": "ex-Christian/agnostic atheist"},
                "Burke, who describes herself as an “ex-Christian/agnostic atheist,”",
                analysis="unaffiliated",
                timing="dated_2026-08-20_self_description",
                reason="Dated direct self-description, not affiliation inferred from an award. "
                "Uses the existing unaffiliated category; sparse-category support remains required.",
            )
        ],
        kind="dated_published_candidate_self_description",
        date="2026-08-20",
    )
    for cid, date, subject, committee, address, forms in (
        (
            "221075",
            "2026-06-06",
            "Khalifa, Zyon, Deshon",
            "KHALIFA FOR CONGRESS",
            "252 LANIER RD.",
            (
                ("fec-khalifa-form2-june-02159", "H6SC02159"),
                ("fec-khalifa-form2-june", "H6SC02167"),
            ),
        ),
        (
            "220449",
            "2026-08-10",
            "Wilson, Antonio",
            "Committee to elect Antonio Wilson for Louisiana",
            "207 South Chestnut St.",
            (
                ("fec-wilson-form2-august-05325", "H6LA05325"),
                ("fec-wilson-form2-august-05333", "H6LA05333"),
            ),
        ),
    ):
        for key, fec_id in forms:
            item = claim(
                "incumbency",
                False,
                subject,
                factual=False,
                reason="Signed identity-only filing. Duplicate-person review is separate "
                "from the retained explicit FEC election classification.",
            )
            item["identity_support"] = [committee, address, fec_id]
            item["v9_identity_bridge"] = {
                "legal_name": subject,
                "committee": committee,
                "filing_address": address,
                "signed_date": date,
                "fec_id": fec_id,
                "evidence_role": "identity_only_retained_FEC_classification",
            }
            add(
                key,
                by_id[cid],
                [item],
                kind="signed_FEC_statement_of_candidacy",
                date=date,
                subject=subject,
            )
    previous = {
        (r["candidate_id"], r["trait"]): r
        for r in read_rows(root / "results/house-characteristics-v8/candidate-traits.jsonl.gz")
    }
    ca = california_rows(root / WORK / "california-certified-candidates-2026")
    official_records = read_rows(root / "results/house/source-inputs.jsonl.gz")[0]["fec"]
    for row in ca:
        matches = [
            c
            for c in candidates
            if c["state"] == "CA"
            and c["district"] == row["district"]
            and (
                orthographic(c["name"]) == orthographic(row["printed_name"])
                or fec_ballot_bridge(c, row, official_records) is not None
            )
            and c["party"] == row["party"]
        ]
        if len(matches) != 1:
            decisions.append({**row, "accepted": False, "reason": "No exact native identity"})
            continue
        candidate = matches[0]
        if previous[(candidate["candidate_id"], "profession")]["factual_qualified"]:
            continue
        bridge = fec_ballot_bridge(candidate, row, official_records)
        item = claim(
            "profession",
            {"ballot_designation": row["designation"]},
            row["designation"],
            reason="Literal candidate ballot designation in the August 27 certified list. "
            "May combine occupations, office or nonoccupational roles; not automatically "
            "a principal historical profession, education, religion or lifetime history.",
            timing="certified_2026-08-27_ballot_designation",
        )
        if bridge:
            item["v9_legal_name_bridge"] = {
                k: bridge[k]
                for k in (
                    "fec_id",
                    "name",
                    "state",
                    "district",
                    "party",
                    "election_year",
                    "source_id",
                    "source_row",
                )
            }
        add(
            "california-certified-candidates-2026",
            candidate,
            [item],
            scope={"page": row["page"], "start": row["printed_name"]},
            subject=row["printed_name"] if bridge else None,
            identity_reason=(
                "Exact printed legal name matches the unique retained FEC alternative "
                "of the already qualified native identity, with identical CA House "
                "district, party and 2026 election. Original FEC row retained in claim metadata."
                if bridge
                else None
            ),
        )
    journal["sources"] = [s for s in journal["sources"] if not s["id"].startswith("v9-")] + sources
    source_ids = {s["id"] for s in sources}
    receipts["sources"] = [
        r for r in receipts["sources"] if not r["id"].startswith("v9-") or r["id"] in source_ids
    ]
    write_json(journal_path, journal)
    write_json(receipts_path, receipts)
    result = {
        "documents": list(documents.values()),
        "sources": sources,
        "discovery_dispositions": attempts,
        "extraction_decisions": decisions,
        "new_acquired_claims": sum(len(s["claims"]) for s in sources),
        "coding_exclusions": [
            {
                "candidate_id": "219757",
                "trait": "prior_elected_office",
                "reason": "Village-corporation board history does not itself establish elected public office.",
            },
            {
                "candidate_id": "219756",
                "trait": "religion",
                "reason": "Admiration for Jesus does not explicitly identify a personal religious affiliation.",
            },
            {
                "candidate_id": "219754",
                "trait": "military",
                "reason": "American Legion membership is not explicit personal military service.",
            },
        ],
        "qualification": "Literal reviewed candidate statements, not independent verification. "
        "Retained-original extraction corrections are separate from newly downloaded originals.",
    }
    write_json(root / ACQUISITIONS, result)
    return {
        "sources": len(sources),
        "claims": result["new_acquired_claims"],
        "held_subjects": sum(not d["accepted"] for d in decisions),
    }


if __name__ == "__main__":
    print(json.dumps(register(Path(__file__).resolve().parents[1]), indent=2))
