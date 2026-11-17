"""Acquire new source-family batches once; literal reviewed claims follow retrieval."""

import json
from pathlib import Path

from .characteristics_v5_batch import acquire as acquire_previous
from .characteristics_v5_batch import claim as previous_claim
from .storage import write_json

SOURCES = {
    "rns-faith-races-2026": {
        "url": "https://religionnews.com/2026/10/13/ahead-of-election-day-here-are-the-races-to-where/",
        "expected_candidates": [
            "Robb Ryerse",
            "Anna Golladay",
            "Chris Jones",
            "Frederick Haynes III",
        ],
        "potential_fields": ["religion", "profession"],
    },
    "rutgers-scientists-2022": {
        "url": "https://eagleton.rutgers.edu/wp-content/uploads/2025/03/Scientists-in-State-Politics-Resource.pdf",
        "expected_candidates": ["Jasmine Clark"],
        "potential_fields": ["age", "education", "profession", "prior_elected_office"],
    },
    "harvard-aapi-candidates-2026": {
        "url": "https://haaaa.sigs.harvard.edu/article.html?aid=569",
        "expected_candidates": ["Dan Koh", "Pia Dandiya"],
        "potential_fields": ["education", "race", "ethnicity", "other_government"],
    },
    "yale-bronin-2024": {
        "url": "https://law.yale.edu/yls-today/news/lessons-leadership-qa-luke-bronin",
        "expected_candidates": ["Luke Bronin"],
        "potential_fields": [
            "education",
            "profession",
            "military",
            "other_government",
            "prior_elected_office",
        ],
    },
    "creighton-medicine-2023": {
        "url": "https://www.creighton.edu/sites/default/files/2023-2024-medicine.pdf",
        "expected_candidates": ["Amish Shah"],
        "potential_fields": ["education", "profession"],
    },
    "pbs-fancy-farm-2025": {
        "url": "https://www.pbs.org/video/fancy-farm-2025-hdLQuC/",
        "expected_candidates": ["Drew Williams", "James Comer"],
        "potential_fields": ["incumbency", "education", "profession"],
    },
    "golladay-statements-2026": {
        "url": "https://annagolladay.com/public-statements/",
        "expected_candidates": ["Anna Golladay"],
        "potential_fields": ["religion", "profession"],
    },
    "wa-general-east-2024": {
        "url": "https://www.sos.wa.gov/sites/default/files/2024-09/Voters%20Pamphlet%202024%20-%20Edition%2001%20-%20Adams%2C%20Yakima%20-%20English.pdf",
        "expected_candidates": ["Carmela Conroy"],
        "potential_fields": ["education", "profession", "other_government"],
    },
    "sojourners-christian-candidates-2026": {
        "url": "https://www.sojo.net/articles/news/live-how-progressive-christian-candidates-are-faring",
        "expected_candidates": ["Robb Ryerse", "Anna Golladay", "Frederick Haynes III"],
        "potential_fields": ["religion", "profession"],
    },
    "convergence-chaplaincy-2026": {
        "url": "https://convergencecolab.org/p/protest-action-chaplaincy-winter26",
        "expected_candidates": ["Anna Golladay"],
        "potential_fields": ["religion", "profession"],
    },
}


def acquire(root):
    return acquire_previous(root, version="v6", sources=SOURCES)


def claim(trait, value, fragment, *, analytical=None, reason, qualified=True):
    result = previous_claim(trait, value, fragment, analytical=analytical, reason=reason)
    result["v6_review"] = result.pop("v5_review")
    result["v6_review"]["factual_qualified"] = qualified
    return result


def degree(level, fragment):
    return claim(
        "education",
        level,
        fragment,
        analytical=level,
        reason="Explicit completed credential in a dated historical source or with an explicit "
        "graduation year; not attendance or an honorary degree.",
    )


def office(fragment, history, categories):
    return claim(
        "prior_elected_office",
        {
            "history": history,
            "supported_categories": categories,
            "time_reference": "before_2026-11-03",
            "not_equivalent_to": "office_before_first_House_entry",
        },
        fragment,
        reason="Explicit positive elected-office history before the 2026 election, not before "
        "first House entry. No missing or unlisted office is coded as never served.",
    )


def definitions():
    yield (
        "rutgers-scientists-2022",
        "2022-12-06 workshop; posted 2025-03",
        "220195",
        5,
        "Representative Jasmine Clark, PhD",
        None,
        [
            claim(
                "age",
                {"birth_year": 1982, "birth_month": 12},
                "Dr. Jasmine Clark was born in Atlanta, GA, in December of 1982.",
                reason="Every day in December 1982 gives election age 43; no day is invented.",
            ),
            degree(
                "bachelors",
                "She received her Bachelors of Science in Biological Sciences "
                "with a concentration in microbiology from the University of Tennessee in Knoxville in 2005.",
            ),
            degree(
                "doctoral_or_professional",
                "In 2013, she received her doctoral degree from "
                "Emory University’s Laney Graduate School in microbiology and molecular genetics",
            ),
            claim(
                "profession",
                "Emory microbiology and anatomy lecturer, 2022",
                "Jasmine currently serves as a lecturer of microbiology and human anatomy and "
                "physiology at the Nell Hodgson Woodruff School of Nursing at Emory University.",
                analytical="education",
                reason="Dated teaching employment, not a medical degree or clinical practice "
                "inferred from the nursing school's name.",
            ),
            office(
                "On November 6, 2018, Jasmine Clark was elected to the Georgia State House of Representatives",
                "Georgia State House elected November 6, 2018",
                ["state"],
            ),
        ],
    )
    yield (
        "yale-bronin-2024",
        "2024-08-13; introduction updated through 2024-25",
        "220035",
        None,
        "Luke Bronin ’06 joined Yale Law School",
        "You’ve served as a leader",
        [
            degree("bachelors", "He holds a B.A. from Yale College"),
            degree("masters", "an M.Sc. from the University of Oxford"),
            degree("doctoral_or_professional", "a J.D. from Yale Law School"),
            claim(
                "profession",
                ["legal", "education"],
                "He was also a partner at the law firm Hinckley Allen",
                reason="The same bounded biography also documents law teaching in 2024-25. "
                "Both legal and education families are preserved, not cherry-picked.",
            ),
            claim(
                "military",
                True,
                "He has also served as an officer in the U.S. Navy Reserve and was a member of "
                "an anti-corruption task force during his deployment to Afghanistan from 2010 to 2011.",
                analytical=True,
                reason="Explicit historical Navy Reserve service, not an "
                "inference from employment; no nonservice reference is supplied.",
            ),
            office(
                "Bronin served as mayor of Hartford, Connecticut from 2016 to 2023.",
                "Hartford mayor 2016-2023",
                ["local"],
            ),
            claim(
                "other_government",
                {
                    "history": "Connecticut governor general counsel; Treasury deputy assistant secretary",
                    "time_reference": "before_2026-11-03",
                    "elected_office_excluded": True,
                },
                "Bronin previously served as General Counsel to former Connecticut Gov. Dannel "
                "P. Malloy, and as Deputy Assistant Secretary for Terrorist Financing and Financial "
                "Crimes at the U.S. Department of Treasury during the Obama administration.",
                reason="Explicit non-elected governmental roles; elected mayor history is separate.",
            ),
        ],
    )
    yield (
        "creighton-medicine-2023",
        "2023-2024 School of Medicine catalog",
        "219764",
        151,
        "Amish Shah, Assistant Clinical Professor of Emergency Medicine",
        "Ankit Shah,",
        [
            degree("bachelors", "B.A., Northwestern University, 1997"),
            degree(
                "doctoral_or_professional", "M.D., Northwestern University Medical School, 2001"
            ),
            degree("masters", "M.P.H., University of California, 2003"),
            claim(
                "profession",
                ["healthcare", "education"],
                "Amish Shah, Assistant Clinical Professor of Emergency Medicine (2022).",
                reason="Clinical and academic appointment retained as mixed families, not "
                "silently selected as a unique historical occupation.",
            ),
        ],
    )
    yield (
        "pbs-fancy-farm-2025",
        "2025-08-02",
        "220397",
        None,
        "I AM NOW GOING TO INTRODUCE JOHN DREW WILLIAMS.",
        "WE ARE NOW GOING TO HEAR FROM CONGRESSMAN JAMIE COMER.",
        [
            claim(
                "profession",
                "business",
                "HE IS A LIFE LONG MARSHALL COUNTY RESIDENT AND SMALL BUSINESS OWNER.",
                analytical="business",
                reason="Host explicitly identifies the same KY01 Democratic candidate as an "
                "owner; not management inferred solely from working in a family business.",
            ),
            claim(
                "education",
                "Murray State history degree; level unstated",
                "I GRADUATED FROM MURRAY STATE UNIVERSITY WITH A DEGREE IN HISTORY",
                reason="Graduation is explicit but the degree level is not; no bachelor's level invented.",
            ),
        ],
    )
    yield (
        "harvard-aapi-candidates-2026",
        "Undated 2026 nominee questionnaire; retrieval is not a publication date",
        "220135",
        None,
        "HARVARD AAPI ALUMNI Running for congress",
        None,
        [
            degree("bachelors", "Pia Dandiya (AB '09)"),
            claim(
                "education",
                "Boston University master's in education; completion date unstated",
                "She holds a B.A. in Government from Harvard and a Master’s in Education from Boston University.",
                reason="Explicit completed degree retained factually; undated page does not "
                "establish a pre-election completion date for the master's.",
            ),
            claim(
                "race",
                "AAPI; overlapping umbrella, not an exclusive race",
                "I’m passionate about helping close that gap—to bring our community’s experiences "
                "into the conversation and to be a voice for everyone I represent.",
                reason="Named candidate answers an AAPI-identity questionnaire using our community. "
                "This is not inferred from a surname, photo, parents or mere affinity-group membership. "
                "Undated umbrella self-description does not extend the historical CAWP contrast.",
            ),
            claim(
                "ethnicity",
                {"self_reported_family_origin": "parents originally from India"},
                "I was born and raised in Florida to parents originally from India.",
                qualified=False,
                reason="Literal family-origin statement is retained, not promoted to an explicit "
                "ethnic identity or non-Hispanic classification.",
            ),
            claim(
                "profession",
                "teacher and school principal; dates unstated",
                "After teaching in low-income schools, she became founding principal of a Harlem high school at 28",
                reason="Occupation is explicit; undated article and unstated birth date do not "
                "independently date this employment before the election.",
            ),
        ],
    )
    yield (
        "harvard-aapi-candidates-2026",
        "Undated 2026 nominee questionnaire; retrieval is not a publication date",
        "220751",
        None,
        "HARVARD AAPI ALUMNI Running for congress",
        None,
        [
            degree("bachelors", "Dan Koh (AB '07, MBA '11)"),
            degree("masters", "Dan Koh (AB '07, MBA '11)"),
            claim(
                "race",
                "AAPI; overlapping umbrella, not an exclusive race",
                "Asian-American representation in politics is about making sure families like mine "
                "see themselves reflected in our democracy",
                reason="Explicit first-person response in a named AAPI-identity questionnaire, "
                "not an identity inferred from family origin. Undated observation remains outside CAWP.",
            ),
            claim(
                "ethnicity",
                {"self_reported_family_origin": ["Korea", "Lebanon"]},
                "More than 70 years ago, my family came to this country from Korea and Lebanon",
                qualified=False,
                reason="Family-origin facts are preserved without manufacturing mutually exclusive "
                "ethnicity, racial categories or non-Hispanic identity.",
            ),
            claim(
                "other_government",
                {
                    "history": "Biden administration; chief of staff to Boston mayor Marty Walsh",
                    "time_reference": "before_2026-11-03",
                    "elected_office_excluded": True,
                },
                "After serving in the Biden administration and as Chief of Staff to Boston Mayor Marty Walsh",
                reason="The specifically named past administration and mayor establish historical "
                "non-elected roles, not a current office or never-held-elected-office claim.",
            ),
        ],
    )
    yield (
        "golladay-statements-2026",
        "2026-06-24",
        "221177",
        None,
        'A Statement on the coverage of the 2021 "Activist Theology" Podcast',
        "A Statement on the Passing",
        [
            claim(
                "religion",
                "other_christian",
                "That conflict between my relationship with Jesus and frustration with the institution "
                "built in His name is a tension that serious Christians often sit with.",
                analytical="other_christian",
                reason="Dated first-person Christian self-description. Former Methodist employment "
                "in 2018 does not establish a current Methodist or Protestant denomination.",
            ),
            claim(
                "profession",
                "business",
                "I am running for Congress in TN-03 as exactly what I am: a faith leader, a small business owner",
                analytical="business",
                reason="Dated explicit business ownership; clergy work is outside the four-family "
                "coding, not coded as formal education employment.",
            ),
        ],
    )
    yield (
        "wa-general-east-2024",
        "2024 general-election voter pamphlet",
        "221355",
        55,
        "Carmela",
        None,
        [
            degree(
                "masters",
                "U.S. Naval War College, M.A. (with highest distinction), National Security",
            ),
            degree("doctoral_or_professional", "University of Washington, J.D., B.A."),
            claim(
                "profession",
                "legal",
                "Deputy Prosecuting Attorney, Spokane County (four years); Legal Advisor, Nissan Motor Company Ltd. (18 months)",
                analytical="legal",
                reason="Explicit dated historical legal employment. Foreign Service is retained "
                "separately, not automatically a second business occupation.",
            ),
            claim(
                "other_government",
                {
                    "history": "24 years U.S. Foreign Service; four years Spokane deputy prosecutor",
                    "time_reference": "before_2026-11-03",
                    "elected_office_excluded": True,
                },
                "U.S. Foreign Service Officer (24 years); Deputy Prosecuting Attorney, Spokane County (four years)",
                reason="Explicit non-elected public service before 2024. Student elected roles "
                "do not establish public elected office, nor does their listing prove nonservice.",
            ),
        ],
    )
    yield (
        "sojourners-christian-candidates-2026",
        "2026-11-03; updated 2026-11-13",
        "219846",
        None,
        "Pastor Robb Ryerse: LOST",
        "Chris Jones: LOST",
        [
            claim(
                "religion",
                "other_christian",
                "Robb Ryerse and his wife Vanessa are the founding pastors of Vintage Fellowship, "
                "a nondenominational progressive church in Fayetteville, Ark.",
                analytical="other_christian",
                reason="Dated report explicitly describes the candidate's Christian ministry in "
                "the election campaign. Nondenominational is not silently coded Protestant; "
                "upbringing is not used as current affiliation. Retrospective reporting only.",
            ),
            claim(
                "profession",
                "pastor and political organizer",
                "Ryerse is also the political organizer for Vote Common Good",
                reason="Explicit historical ministry/organizing retained, outside the four "
                "declared professional families; no business or education code inferred.",
            ),
        ],
    )


def register(root):
    from .characteristics_v4_batch import register as register_reviewed

    details = {
        key: {
            "identity_qualification": "Literal subject name and independently concordant native "
            "candidate state/office/biography; current candidate-contest key retained. "
            "Historical office districts and source mistakes do not replace native contest identity. "
            "Post-election retrieval does not establish prospective availability."
        }
        for key in SOURCES
    }
    details["pbs-fancy-farm-2025"]["identity_fragment"] = (
        "MY NAME IS JOHN ANDREW WILLIAMS, BUT YOU CAN CALL ME DREW."
    )
    details["wa-general-east-2024"]["identity_fragment"] = "Conroy (Prefers Democratic Party)"

    def reviewed_definitions():
        for definition in definitions():
            if definition[0] == "pbs-fancy-farm-2025":
                for c in definition[-1]:
                    c["identity_support"] = [
                        "MY NAME IS JOHN ANDREW WILLIAMS, BUT YOU CAN CALL ME DREW.",
                        "DREW IS THE DEMOCRATIC CANDIDATE FOR THE FIRST CONGRESSIONAL DISTRICT.",
                    ]
            yield definition

    result = register_reviewed(
        root, version="v6", definitions_fn=reviewed_definitions, source_details=details
    )
    result["source_population"] = (
        "Two requirements-led loops: dated institutional biographies, a complete historical "
        "state guide, alumni questionnaire and original broadcast/campaign/faith reporting. "
        "Selective nonincumbent acquisition, not an exhaustive or representative sample."
    )
    result["explicit_exclusions"] = [
        "RNS 403: failed attempt, no acquired observations; no retry or alternate copy.",
        "Convergence course page acquired but corroborates already stronger Golladay evidence; "
        "not counted as an evidence-yielding source.",
        "The independently dated 2024 Washington guide is not the denied 2026 landing page.",
        "Historical state-legislative districts are not substituted for native House contests.",
        "Harvard family origins do not qualify ethnic identity; AAPI is not exclusive or non-Hispanic.",
        "Drew's completed history degree has no supported degree level.",
        "Clinical academia and legal teaching retain mixed historical profession families.",
        "Former Methodist employment does not establish current denomination.",
        "War College attendance/credential is not military service.",
        "Conroy's student elected roles do not establish public office or no prior public office.",
        "No explicit negative office, government or military responses were acquired.",
    ]
    write_json(Path(root) / "data/house-characteristics-v6-acquisitions.json", result)
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--register", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(register(root) if args.register else acquire(root), indent=2))
