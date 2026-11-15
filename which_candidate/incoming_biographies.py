"""Acquire and normalize reviewed biographies for provisional incoming House members."""

import argparse
import csv
import hashlib
import json
import re
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data/raw/incoming-members-20261114"
OUTPUT = ROOT / "data/incoming-member-biographies.json"
SOURCES_OUTPUT = ROOT / "data/incoming-member-biography-sources.json"
ROSTER = ROOT / "results/members/house-120-seats.csv"
MEMBER_PROFILES = ROOT / "data/house-member-profiles.json"
INCOMING_CLASSES = {
    "returning_former_House_member",
    "new_to_current_House; prior_federal_service_not_fully_resolved",
}


def education(institution, credential=None, status="completed", literal=None):
    return {
        "institution": institution,
        "credential": credential,
        "completion_status": status,
        "literal": literal or " ".join(x for x in (institution, credential) if x),
    }


# These are deliberately finite, reviewed source specifications rather than promoted
# machine extractions. Verification fragments must occur in the acquired primary page.
REVIEWED_SPECS = [
    {
        "candidate_id": "219986",
        "state": "CO",
        "district": "04",
        "name": "Eileen Laubacher",
        "url": "https://www.eileenforcolorado.com/about",
        "anchors": ["Eileen Laubacher", "Colorado's 4th Congressional District"],
        "verify": ["graduated from the United States Naval Academy in 1990"],
        "fields": {
            "education": [
                education(
                    "United States Naval Academy",
                    "graduate",
                    literal="Graduated from the United States Naval Academy in 1990",
                )
            ],
            "military_service": [
                "Served in the United States Navy for 34 years; retired in October 2024"
            ],
            "professional_history": [
                "Navy intelligence officer",
                "Senior Defense Official and Defense Attaché in India",
                "National Security Council senior director for South Asia",
            ],
        },
        "support": {
            "education": ["graduated from the United States Naval Academy in 1990"],
            "military_service": [
                "served in the United States Navy for 34 years",
                "retired from the Navy in October 2024",
            ],
            "professional_history": [
                "intelligence officer",
                "Senior Defense Official and Defense Attache",
                "Senior Director for South Asia",
            ],
        },
    },
    {
        "candidate_id": "219990",
        "state": "CO",
        "district": "05",
        "name": "Jessica Killin",
        "url": "https://www.killinforcolorado.com/about",
        "anchors": ["Jessica Killin"],
        "verify": ["law degree at Georgetown"],
        "fields": {
            "education": [
                education(
                    "Georgetown",
                    "law degree",
                    literal="Earned a law degree at Georgetown",
                )
            ]
        },
        "support": {"education": ["earned her law degree at Georgetown"]},
    },
    {
        "candidate_id": "220006",
        "state": "CO",
        "district": "08",
        "name": "Manny Rutinel",
        "url": "https://www.mannyforcolorado.com/meetmanny",
        "anchors": ["Meet Manny"],
        "verify": ["Yale Law School", "Johns Hopkins University"],
        "fields": {
            "education": [
                education("Yale Law School", "law degree"),
                education("Johns Hopkins University", "master's in economics"),
                education(
                    "community college",
                    "associate's degree",
                    literal="Earned an associate's degree; institution not stated on source page",
                ),
            ]
        },
        "support": {
            "education": [
                "receive my Associate’s degree",
                "graduated with Bachelor’s degrees in Microbiology and Economics",
                "Master’s in Economics from Johns Hopkins University",
                "law degree from Yale Law School",
            ]
        },
    },
    {
        "candidate_id": "220139",
        "state": "FL",
        "district": "24",
        "name": "Oliver Gilbert",
        "url": "https://olivergilbert.vote/about/",
        "anchors": ["Oliver Gilbert"],
        "verify": ["Florida A&M", "University of Miami"],
        "fields": {
            "education": [
                education("Florida A&M University", status="source_reports_attendance"),
                education("University of Miami School of Law", "law degree"),
            ],
            "prior_office": ["Mayor of Miami Gardens", "Miami-Dade County commissioner"],
        },
    },
    {
        "candidate_id": "220189",
        "state": "GA",
        "district": "10",
        "name": "Houston Gaines",
        "url": "https://houstongaines.com/about",
        "anchors": ["Houston Gaines"],
        "verify": ["University of Georgia"],
        "fields": {
            "education": [
                education(
                    "University of Georgia",
                    status="source_reports_attendance",
                    literal="Attended the University of Georgia; source also identifies him as student body president",
                )
            ],
            "prior_office": [
                "State House since 2019, representing Barrow, Clarke, Jackson, and Oconee counties"
            ],
        },
        "support": {
            "education": [
                "University of Georgia’s 40 Under 40",
                "While at UGA",
                "student body president",
            ],
            "prior_office": ["served in the State House since 2019"],
        },
    },
    {
        "candidate_id": "220344",
        "state": "IA",
        "district": "01",
        "name": "Christina Bohannan",
        "url": "https://bohannanforcongress.com/about/",
        "anchors": ["Christina Bohannan"],
        "verify": ["Environmental Engineering", "law school"],
        "fields": {
            "education": [
                education(
                    "institution not stated",
                    status="graduated; credential_not_stated",
                    literal="Graduated first in her law-school class",
                ),
                education(
                    "unidentified institution",
                    "degree in environmental engineering",
                    literal="Source reports a degree in environmental engineering without naming the institution in the reviewed passage",
                ),
            ],
            "prior_office": ["Iowa House of Representatives"],
        },
        "support": {
            "education": [
                "degree in Environmental Engineering",
                "went to law school, where I graduated first in my class",
            ],
            "prior_office": ["serve in the Iowa House of Representatives"],
        },
    },
    {
        "candidate_id": "220351",
        "state": "IA",
        "district": "03",
        "name": "Sarah Trone Garriott",
        "url": "https://sarahforiowa.com/about",
        "anchors": ["Sarah Trone Garriott"],
        "verify": ["Harvard Divinity School"],
        "fields": {
            "education": [
                education(
                    "Harvard Divinity School",
                    status="association_reported; completion_not_stated",
                    literal="Her journey continued at Harvard Divinity School",
                )
            ],
            "prior_office": ["State Senator"],
        },
        "support": {
            "education": ["journey continued at Harvard Divinity School"],
            "prior_office": ["State Senator"],
        },
    },
    {
        "candidate_id": "220269",
        "state": "IL",
        "district": "04",
        "name": "Patty Garcia",
        "url": "https://pattyforillinois.com/meet",
        "anchors": ["Patty Garcia"],
        "verify": ["PhD", "Education Policy", "University of Illinois"],
        "fields": {
            "education": [
                education(
                    "University of Illinois Urbana-Champaign",
                    "PhD in education policy",
                )
            ]
        },
        "support": {
            "education": [
                "PhD",
                "Education Policy",
                "University of Illinois Urbana-Champaign",
            ]
        },
    },
    {
        "candidate_id": "220469",
        "state": "ME",
        "district": "02",
        "name": "Paul LePage",
        "url": "https://lepageforcongress.com/meet-paul",
        "anchors": ["Paul LePage"],
        "verify": ["Husson", "BS in Business Administration", "University of Maine"],
        "fields": {
            "education": [
                education("Husson", "BS in business administration"),
                education("University of Maine", "MBA"),
            ],
            "prior_office": ["Governor of Maine", "Mayor of Waterville"],
            "professional_history": [
                "Leadership roles in lumber and paper mills",
                "Turnaround advisor",
                "General manager of Marden's",
            ],
        },
        "support": {
            "education": [
                "attending college at Husson",
                "graduated with a BS in Business Administration",
                "MBA, Masters in Business, from the University of Maine",
            ],
            "prior_office": ["Mayor of Waterville", "Governor of Maine"],
            "professional_history": [
                "leadership for lumber and paper mills",
                "turnaround advisor",
                "General Manager of Marden’s",
            ],
        },
    },
    {
        "candidate_id": "220516",
        "state": "MI",
        "district": "04",
        "name": "Sean McCann",
        "url": "https://seanmccannforcongress.com/about",
        "anchors": ["Sean McCann"],
        "verify": ["Western Michigan University"],
        "fields": {
            "education": [
                education(
                    "Western Michigan University",
                    status="source_reports_attendance",
                    literal="Attended Western Michigan University",
                )
            ],
            "prior_office": ["State Representative", "State Senator in Southwest Michigan"],
        },
        "support": {
            "education": ["attended Western Michigan University"],
            "prior_office": ["State Representative", "serves as a State Senator"],
        },
    },
    {
        "candidate_id": "220549",
        "state": "MI",
        "district": "11",
        "name": "Jeremy Moss",
        "url": "https://votejeremymoss.com/about",
        "anchors": ["Jeremy Moss"],
        "verify": ["Michigan State University"],
        "fields": {
            "education": [
                education(
                    "Michigan State University",
                    status="source_reports_study",
                    literal="Studied at Michigan State University",
                )
            ],
            "prior_office": ["Michigan Senate", "Michigan House of Representatives"],
        },
        "support": {
            "education": ["study at Michigan State University"],
            "prior_office": ["leadership in both the State House and Senate"],
        },
    },
    {
        "candidate_id": "220921",
        "state": "NC",
        "district": "09",
        "name": "Richard Ojeda",
        "url": "https://ojedafornc.com/about-richard-ojeda/",
        "anchors": ["Richard Ojeda"],
        "verify": ["West Virginia State University"],
        "fields": {
            "education": [education("West Virginia State University", "degree; field not stated")],
            "military_service": ["Retired U.S. Army officer and combat veteran"],
            "prior_office": ["West Virginia Senate"],
        },
    },
    {
        "candidate_id": "220925",
        "state": "NC",
        "district": "11",
        "name": "Jamie Ager",
        "url": "https://agerforcongress.com/about",
        "anchors": ["Jamie Ager"],
        "verify": ["Warren Wilson College", "Environmental Studies", "History"],
        "fields": {
            "education": [
                education(
                    "Warren Wilson College",
                    "degrees in environmental studies and history",
                )
            ],
            "professional_history": [
                "Fourth-generation farmer and entrepreneur",
                "Co-built Hickory Nut Gap, a sustainable meat company",
            ],
        },
        "support": {
            "education": [
                "earned degrees from Warren Wilson College",
                "Environmental Studies",
                "History",
            ],
            "professional_history": [
                "fourth-generation farmer, entrepreneur",
                "built Hickory Nut Gap, a sustainable meat company",
            ],
        },
    },
    {
        "candidate_id": "220931",
        "state": "NC",
        "district": "13",
        "name": "Paul Barringer",
        "url": "https://paulbarringer.com/about",
        "anchors": ["Paul Barringer"],
        "verify": ["Davidson College", "UNC", "Princeton"],
        "fields": {
            "education": [
                education(
                    "Davidson College",
                    status="association_reported; completion_not_stated",
                ),
                education(
                    "UNC law school",
                    status="association_reported; completion_not_stated",
                ),
                education(
                    "School of Public and International Affairs at Princeton University",
                    status="association_reported; completion_not_stated",
                ),
            ]
        },
        "support": {
            "education": [
                "product of Lee County public schools",
                "Davidson College",
                "UNC law school",
                "School of Public and International Affairs at Princeton University",
            ]
        },
    },
    {
        "candidate_id": "220933",
        "state": "NC",
        "district": "14",
        "name": "Lakesha Womack",
        "url": "https://www.womack4nc14.com/bio",
        "anchors": ["Lakesha Womack"],
        "verify": ["Vanderbilt University", "Political Science"],
        "fields": {
            "education": [
                education("Vanderbilt University", "degree in political science"),
                education(
                    "Vanderbilt Law School",
                    "Master of Legal Studies",
                    status="enrolled_or_pursuing",
                    literal="Pursuing a Master of Legal Studies at Vanderbilt Law School",
                ),
            ]
        },
        "support": {
            "education": [
                "Vanderbilt University",
                "earned a degree in Political Science",
                "Vanderbilt Law School",
                "pursuing a Master of Legal Studies",
            ]
        },
    },
    {
        "candidate_id": "220774",
        "state": "NH",
        "district": "01",
        "name": "Stefany Shaheen",
        "url": "https://stefanyshaheen.com/meet-stefany",
        "anchors": ["Stefany Shaheen"],
        "verify": ["Fairfield University", "Kennedy School", "Sloan"],
        "fields": {
            "education": [
                education("Fairfield University", "graduate"),
                education(
                    "Harvard Kennedy School",
                    status="source_describes_as_alumna",
                ),
                education(
                    "MIT Sloan School of Management",
                    status="source_describes_as_alumna",
                ),
            ]
        },
    },
    {
        "candidate_id": "221073",
        "state": "SC",
        "district": "01",
        "name": "Nancy Lacore",
        "url": "https://www.nancylacore.com/about",
        "anchors": ["Nancy Lacore"],
        "verify": ["College of the Holy Cross", "ROTC"],
        "fields": {
            "education": [
                education(
                    "College of the Holy Cross",
                    status="source_reports_attendance",
                    literal="Attended the College of the Holy Cross on an ROTC scholarship",
                )
            ],
            "military_service": ["U.S. Navy Reserve service"],
        },
    },
    {
        "candidate_id": "221182",
        "state": "TN",
        "district": "06",
        "name": "Johnny Garrett",
        "url": "https://johnnygarrettforcongress.com/meet-johnny/",
        "anchors": ["Johnny Garrett"],
        "verify": ["University of Tennessee", "Nashville School of Law"],
        "fields": {
            "education": [
                education("University of Tennessee at Knoxville", "BS in general business"),
                education("Nashville School of Law", "JD"),
            ],
            "prior_office": ["State Representative"],
        },
        "support": {
            "education": [
                "University of Tennessee at Knoxville",
                "obtained a B.S. degree in General Business",
                "Nashville School of Law",
                "earned his J.D. from the Nashville School of Law",
            ],
            "prior_office": ["State Representative"],
        },
    },
    {
        "candidate_id": "140482",
        "state": "TX",
        "district": "22",
        "name": "Trever Nehls",
        "url": "https://www.trevernehlsforcongress.com/about/",
        "anchors": ["Trever Nehls"],
        "verify": ["University of Wisconsin", "Central Michigan University", "Army War College"],
        "fields": {
            "education": [
                education(
                    "University of Wisconsin–Platteville",
                    "bachelor's in criminal justice and corrections",
                ),
                education("Central Michigan University", "master's in public administration"),
                education("U.S. Army War College", "master's in strategic studies"),
            ],
            "military_service": [
                "More than 33 years in the U.S. Army Reserve, including deployments to Iraq, Afghanistan, and Kuwait"
            ],
        },
        "support": {
            "education": [
                "U.S. Army War College",
                "master’s degree in Military Strategic Studies",
                "Central Michigan University",
                "master’s degree in Public Administration",
                "University of Wisconsin–Platteville",
                "bachelor’s degree in Criminal Justice and Corrections",
            ],
            "military_service": [
                "more than 33 years of service in the U.S. Army Reserve",
                "led troops in Iraq and Afghanistan",
                "additional deployment to Kuwait",
            ],
        },
    },
    {
        "candidate_id": "221133",
        "state": "TX",
        "district": "23",
        "name": "Katy Padilla Stout",
        "url": "https://www.katyforcongress.com/about-katy",
        "anchors": ["Katy Padilla Stout"],
        "verify": ["University of Texas", "South Texas College of Law"],
        "fields": {
            "education": [
                education("University of Texas at Austin", "bachelor's in education"),
                education("South Texas College of Law", "law degree"),
            ]
        },
    },
    {
        "candidate_id": "221144",
        "state": "TX",
        "district": "33",
        "name": "Colin Allred",
        "url": "https://www.colinallred.com/about/",
        "anchors": ["Colin Allred"],
        "verify": ["Baylor University", "Berkeley"],
        "fields": {
            "education": [
                education("Baylor University", "BA"),
                education("University of California, Berkeley School of Law", "JD"),
            ],
            "prior_office": ["U.S. House of Representatives"],
            "professional_history": ["Civil-rights attorney", "NFL player"],
        },
    },
    {
        "candidate_id": "221191",
        "state": "UT",
        "district": "01",
        "name": "Ben McAdams",
        "url": "https://benmcadamsforcongress.com/about/",
        "anchors": ["Ben McAdams"],
        "verify": ["University of Utah", "Columbia Law School"],
        "fields": {
            "education": [
                education("University of Utah", "graduate"),
                education("Columbia Law School", "JD"),
            ],
            "prior_office": [
                "U.S. House of Representatives",
                "Mayor of Salt Lake County",
                "Utah Senate",
            ],
        },
    },
    {
        "candidate_id": "221269",
        "state": "WI",
        "district": "03",
        "name": "Rebecca Cooke",
        "url": "https://cookeforwisconsin.com/meet-rebecca-cooke-2026/",
        "anchors": ["Rebecca Cooke"],
        "verify": ["University of St. Thomas"],
        "fields": {
            "education": [education("University of St. Thomas", "degree; field not stated")],
            "professional_history": ["Small-business owner and nonprofit leader"],
        },
    },
]

HISTORIAN_SPECS = [
    {
        "candidate_id": "219724",
        "state": "AL",
        "district": "01",
        "name": "Jerry Carl",
        "url": "https://history.house.gov/People/Listing/C/CARL,-Jerry-L--(C001054)/",
        "anchors": ["CARL, Jerry L.", "June 17, 1958"],
        "verify": ["Lake City Community College"],
        "fields": {
            "date_of_birth": "1958-06-17",
            "education": [
                education(
                    "Lake City Community College",
                    status="attended",
                    literal="Attended Lake City Community College",
                )
            ],
            "professional_history": ["Business owner", "Entrepreneur", "Sales representative"],
            "prior_office": ["Mobile County commissioner", "U.S. House of Representatives"],
        },
        "support": {
            "date_of_birth": ["June 17, 1958"],
            "education": ["attended Lake City Community College"],
            "professional_history": ["business owner", "entrepreneur", "sales representative"],
            "prior_office": [
                "commissioner, Mobile County",
                "elected as a Republican to the One Hundred Seventeenth",
            ],
        },
    },
    {
        "candidate_id": "219929",
        "state": "CA",
        "district": "38",
        "name": "Hilda Solis",
        "url": "https://history.house.gov/People/Detail/22566",
        "anchors": ["SOLIS, Hilda L.", "October 20, 1957"],
        "verify": ["California Polytechnic University", "University of Southern California"],
        "fields": {
            "date_of_birth": "1957-10-20",
            "education": [
                education("California Polytechnic University, Pomona", "BA"),
                education("University of Southern California", "MA"),
            ],
            "prior_office": [
                "U.S. House of Representatives",
                "U.S. Secretary of Labor",
                "California Senate",
                "California Assembly",
                "Los Angeles County Board of Supervisors",
            ],
        },
        "support": {
            "date_of_birth": ["October 20, 1957"],
            "education": [
                "B.A., California Polytechnic University",
                "M.A., University of Southern California",
            ],
            "prior_office": [
                "California state assembly",
                "California state senate",
                "Secretary of Labor",
                "Los Angeles County",
                "elected as a Democrat to the One Hundred Seventh",
            ],
        },
    },
    {
        "candidate_id": "220279",
        "state": "IL",
        "district": "08",
        "name": "Melissa Bean",
        "url": "https://history.house.gov/People/Listing/B/BEAN,-Melissa-L--(B001253)/",
        "anchors": ["BEAN, Melissa L.", "January 22, 1962"],
        "verify": ["Oakton Community College", "Roosevelt University"],
        "fields": {
            "date_of_birth": "1962-01-22",
            "education": [
                education("Oakton Community College", "AA"),
                education("Roosevelt University", "BA"),
            ],
            "professional_history": ["Consultant", "Businesswoman"],
            "prior_office": ["U.S. House of Representatives"],
        },
        "support": {
            "date_of_birth": ["January 22, 1962"],
            "education": [
                "A.A., Oakton Community College",
                "B.A., Roosevelt University",
            ],
            "professional_history": ["consultant", "businesswoman"],
            "prior_office": ["elected as a Democrat to the One Hundred Ninth Congress"],
        },
    },
    {
        "candidate_id": "221144",
        "state": "TX",
        "district": "33",
        "name": "Colin Allred",
        "url": "https://history.house.gov/People/Listing/A/ALLRED,-Colin-(A000376)/",
        "anchors": ["ALLRED, Colin", "April 15, 1983"],
        "verify": ["Baylor University", "University of California, Berkeley"],
        "fields": {
            "date_of_birth": "1983-04-15",
            "education": [
                education("Baylor University", "BA"),
                education("University of California, Berkeley", "JD"),
            ],
            "professional_history": [
                "Professional athlete",
                "Nonprofit executive",
                "Lawyer",
            ],
            "prior_office": ["U.S. House of Representatives"],
        },
        "support": {
            "date_of_birth": ["April 15, 1983"],
            "education": [
                "B.A., Baylor University",
                "J.D., University of California, Berkeley",
            ],
            "professional_history": [
                "professional athlete",
                "nonprofit executive",
                "lawyer",
            ],
            "prior_office": ["elected as a Democrat to the One Hundred Sixteenth"],
        },
    },
    {
        "candidate_id": "221191",
        "state": "UT",
        "district": "01",
        "name": "Ben McAdams",
        "url": "https://history.house.gov/People/Listing/M/MCADAMS,-Ben-(M001209)/",
        "anchors": ["MCADAMS, Ben", "December 5, 1974"],
        "verify": ["University of Utah", "Columbia University"],
        "fields": {
            "date_of_birth": "1974-12-05",
            "education": [
                education("University of Utah", "BA"),
                education("Columbia University", "JD"),
            ],
            "professional_history": ["Lawyer", "Adjunct professor"],
            "prior_office": [
                "U.S. House of Representatives",
                "Mayor of Salt Lake County",
                "Utah Senate",
            ],
        },
        "support": {
            "date_of_birth": ["December 5, 1974"],
            "education": ["B.A., University of Utah", "J.D., Columbia University"],
            "professional_history": ["lawyer", "adjunct professor"],
            "prior_office": [
                "Utah state senate",
                "Mayor of Salt Lake County",
                "elected as a Democrat to the One Hundred Sixteenth",
            ],
        },
    },
    {
        "candidate_id": "221201",
        "state": "VA",
        "district": "02",
        "name": "Elaine Luria",
        "url": "https://history.house.gov/People/Detail/25769805224",
        "anchors": ["LURIA, Elaine", "August 15, 1975"],
        "verify": ["United States Naval Academy", "Old Dominion University"],
        "fields": {
            "date_of_birth": "1975-08-15",
            "education": [
                education("United States Naval Academy", "BS"),
                education(
                    "United States Naval Nuclear Power School",
                    status="attended",
                    literal="Attended United States Naval Nuclear Power School",
                ),
                education("Old Dominion University", "MS"),
            ],
            "military_service": ["United States Navy, 1997–2017"],
            "professional_history": ["Small-business owner"],
            "prior_office": ["U.S. House of Representatives"],
        },
        "support": {
            "date_of_birth": ["August 15, 1975"],
            "education": [
                "B.S., United States Naval Academy",
                "attended United States Naval Nuclear Power School",
                "M.S., Old Dominion University",
            ],
            "military_service": ["United States Navy, 1997-2017"],
            "professional_history": ["small business owner"],
            "prior_office": ["elected as a Democrat to the One Hundred Sixteenth"],
        },
    },
]


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def visible_text(raw):
    parser = VisibleText()
    parser.feed(raw.decode("utf-8", "replace"))
    return " ".join(" ".join(parser.parts).split())


def normalized(value):
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def receipt(source_id, url, path, raw, retrieved_at):
    return {
        "id": source_id,
        "url": url,
        "path": str(path.relative_to(ROOT)),
        "retrieved_at": retrieved_at,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "qualification": "retrieved_after_election; descriptive_only; model_ineligible",
        "source_kind": (
            "official_house_historian"
            if source_id.startswith("incoming-historian-")
            else "primary_candidate_biography"
        ),
    }


def source_specs():
    return [
        *((f"incoming-primary-{spec['candidate_id']}", spec) for spec in REVIEWED_SPECS),
        *((f"incoming-historian-{spec['candidate_id']}", spec) for spec in HISTORIAN_SPECS),
    ]


def acquire(timeout=25):
    CACHE.mkdir(parents=True, exist_ok=True)
    sources, failures = [], []
    for source_id, spec in source_specs():
        path = CACHE / f"{source_id}.html"
        try:
            request = Request(
                spec["url"],
                headers={"User-Agent": "which-candidate public research/1.0"},
            )
            with urlopen(request, timeout=timeout) as response:
                raw = response.read()
            retrieved_at = datetime.now(timezone.utc).isoformat()
            path.write_bytes(raw)
            sources.append(receipt(source_id, spec["url"], path, raw, retrieved_at))
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            failures.append(
                {
                    "id": source_id,
                    "url": spec["url"],
                    "error": f"{type(exc).__name__}: {exc}",
                    "disposition": "not_bypassed",
                }
            )
    return sources, failures


def exact_date(birth_literal):
    if not birth_literal:
        return None
    matches = re.findall(r"(?<!\d)(\d{4}-\d{2}-\d{2})(?!\d)", birth_literal)
    if len(set(matches)) != 1:
        return None
    try:
        return date.fromisoformat(matches[0]).isoformat()
    except ValueError:
        return None


def incoming_rows():
    with ROSTER.open(newline="") as handle:
        return [
            row for row in csv.DictReader(handle) if row["entry_classification"] in INCOMING_CLASSES
        ]


def identity_index(rows):
    result = {}
    for row in rows:
        candidate_id = row["candidate_id"]
        if not candidate_id or candidate_id in result:
            raise ValueError("Incoming candidate IDs must be present and unique")
        result[candidate_id] = row
    return result


def qualify_identity(spec, row):
    expected = (row["state"], row["district"], normalized(row["name"]))
    observed = (spec["state"], spec["district"], normalized(spec["name"]))
    if observed != expected:
        raise ValueError(
            f"Identity mismatch for {spec['candidate_id']}: expected {expected}, got {observed}"
        )
    return "candidate_id_exact; provisional_winner_context; same_state_district_and_normalized_name"


def source_profiles(rows, acquired_sources):
    by_id = {source["id"]: source for source in acquired_sources}
    profiles = []
    for source_id, spec in source_specs():
        source = by_id.get(source_id)
        if not source:
            continue
        raw = (ROOT / source["path"]).read_bytes()
        text = normalized(visible_text(raw))
        if not any(normalized(anchor) in text for anchor in spec["anchors"]):
            continue
        if not all(normalized(fragment) in text for fragment in spec["verify"]):
            continue
        support = spec.get("support", {})
        if set(support) != set(spec["fields"]):
            raise ValueError(f"Every normalized field requires support checks: {source_id}")
        missing = {
            field: [fragment for fragment in fragments if normalized(fragment) not in text]
            for field, fragments in support.items()
        }
        missing = {field: fragments for field, fragments in missing.items() if fragments}
        if missing:
            raise ValueError(f"Cached source does not support {source_id}: {missing}")
        row = rows[spec["candidate_id"]]
        profiles.append(
            {
                "candidate_id": spec["candidate_id"],
                "state": spec["state"],
                "district": spec["district"],
                "name": spec["name"],
                "fields": spec["fields"],
                "evidence": source,
                "field_audit": {
                    field: {
                        "status": "explicit_in_cached_source",
                        "support_fragment_sha256": [
                            hashlib.sha256(normalized(fragment).encode()).hexdigest()
                            for fragment in fragments
                        ],
                    }
                    for field, fragments in support.items()
                },
                "identity_qualification": qualify_identity(spec, row),
                "model_ready": False,
                "source_kind": source["source_kind"],
            }
        )
    return profiles


def wikipedia_profiles(rows):
    data = json.loads(MEMBER_PROFILES.read_text())
    profiles = []
    for item in data["incoming_wikipedia_rows"]:
        candidate = next(
            (
                row
                for row in rows.values()
                if row["state"] == item["state"]
                and row["district"] == item["district"]
                and normalized(row["name"]) == normalized(item["name"])
            ),
            None,
        )
        if not candidate or not item.get("profile_evidence"):
            continue
        fields = {}
        infobox = item.get("infobox_fields", {})
        birth_literal = infobox.get("birth_literal")
        if birth_literal:
            fields["birth_literal"] = birth_literal
            dob = exact_date(birth_literal)
            if dob:
                fields["date_of_birth"] = dob
        elif item.get("birth_year_literal"):
            fields["birth_literal"] = item["birth_year_literal"]
        if infobox.get("education"):
            fields["education_literal"] = infobox["education"]
        if infobox.get("occupation"):
            fields["professional_history"] = [infobox["occupation"]]
        if infobox.get("military_service"):
            fields["military_service"] = [infobox["military_service"]]
        if item.get("prior_background"):
            fields["prior_office_or_background_literal"] = item["prior_background"]
        profiles.append(
            {
                "candidate_id": candidate["candidate_id"],
                "state": candidate["state"],
                "district": candidate["district"],
                "name": candidate["name"],
                "fields": fields,
                "evidence": {
                    **item["profile_evidence"],
                    "source_kind": "secondary_wikipedia",
                },
                "field_audit": {
                    field: {"status": "parsed_from_secondary_infobox_or_roster"} for field in fields
                },
                "identity_qualification": (
                    "candidate_id_from_native_winner_context; same_state_district_and_name; "
                    "district-qualified Wikipedia roster link"
                ),
                "model_ready": False,
                "source_kind": "secondary_wikipedia",
            }
        )
    return profiles


def validate(payload):
    rows = identity_index(incoming_rows())
    source_ids = {source["id"] for source in payload["sources"]}
    if len(source_ids) != len(payload["sources"]):
        raise ValueError("Duplicate source IDs")
    for profile in payload["profiles"]:
        row = rows.get(profile["candidate_id"])
        if not row:
            raise ValueError(f"Unknown incoming candidate {profile['candidate_id']}")
        qualify_identity(profile, row)
        if profile["model_ready"] is not False:
            raise ValueError("Incoming biography evidence must remain model-ineligible")
        if profile.get("source_kind") not in {
            "official_house_historian",
            "primary_candidate_biography",
            "secondary_wikipedia",
        }:
            raise ValueError(
                "Biography source kind must distinguish primary and secondary evidence"
            )
        if set(profile["field_audit"]) != set(profile["fields"]):
            raise ValueError("Every normalized field requires a field audit")
        dob = profile["fields"].get("date_of_birth")
        if dob:
            date.fromisoformat(dob)
            if len(dob) != 10:
                raise ValueError("DOB must be exact ISO format")
            if (
                profile["source_kind"] == "secondary_wikipedia"
                and exact_date(profile["fields"].get("birth_literal")) != dob
            ):
                raise ValueError("Secondary exact DOB must occur explicitly in its birth literal")
        for item in profile["fields"].get("education", []):
            if item["completion_status"] == "completed" and not item.get("credential"):
                raise ValueError("Completed education requires a stated credential")
        evidence = profile["evidence"]
        if evidence.get("source_kind") != profile["source_kind"]:
            raise ValueError("Profile and evidence source kinds must agree")
        if evidence["id"].startswith("incoming-"):
            if evidence["id"] not in source_ids:
                raise ValueError("Profile references an absent acquired source")
            raw = (ROOT / evidence["path"]).read_bytes()
            if hashlib.sha256(raw).hexdigest() != evidence["sha256"]:
                raise ValueError("Pinned source checksum mismatch")
    return payload


def build(acquire_first=False):
    if acquire_first:
        acquired, failures = acquire()
    elif SOURCES_OUTPUT.exists():
        old = json.loads(SOURCES_OUTPUT.read_text())
        acquired, failures = old["sources"], old["failures"]
    else:
        acquired, failures = [], []
    acquired = [
        {
            **source,
            "source_kind": source.get("source_kind")
            or (
                "official_house_historian"
                if source["id"].startswith("incoming-historian-")
                else "primary_candidate_biography"
            ),
        }
        for source in acquired
        if source["id"].startswith("incoming-")
    ]
    rows = identity_index(incoming_rows())
    profiles = wikipedia_profiles(rows) + source_profiles(rows, acquired)
    all_sources = {source["id"]: source for source in acquired}
    for profile in profiles:
        all_sources[profile["evidence"]["id"]] = profile["evidence"]
    sources = [all_sources[source_id] for source_id in sorted(all_sources)]
    payload = {
        "profiles": profiles,
        "sources": sources,
        "failures": failures,
    }
    validate(payload)
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    SOURCES_OUTPUT.write_text(
        json.dumps({"sources": sources, "failures": failures}, indent=2, sort_keys=True) + "\n"
    )
    return payload


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("acquire", "build", "validate", "all"))
    args = parser.parse_args(argv)
    if args.command == "acquire":
        sources, failures = acquire()
        SOURCES_OUTPUT.write_text(
            json.dumps({"sources": sources, "failures": failures}, indent=2, sort_keys=True) + "\n"
        )
    elif args.command == "build":
        build()
    elif args.command == "validate":
        validate(json.loads(OUTPUT.read_text()))
    else:
        build(acquire_first=True)


if __name__ == "__main__":
    main()
