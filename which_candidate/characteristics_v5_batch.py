"""Acquire once and register only literally reviewed V5 subject evidence."""

import argparse
import concurrent.futures
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .storage import fingerprint, write_json

SOURCES = {
    "il-bluebook-legislators-2025": {
        "url": "https://www.ilsos.gov/content/dam/publications/illinois-bluebook/2025-26/legislators-portraits-and-biographies.pdf",
        "expected_candidates": ["La Shawn Ford"],
        "potential_fields": ["age", "education", "profession", "prior_elected_office"],
    },
    "il-bluebook-congress-2025": {
        "url": "https://www.ilsos.gov/content/dam/publications/illinois-bluebook/2025-26/119th-illinois-congressional-delegation.pdf",
        "expected_candidates": ["Exact Illinois delegation matches only"],
        "potential_fields": ["education", "profession"],
    },
    "il-biss-oral-history-2015": {
        "url": "https://presidentlincoln.illinois.gov/Resources/18d77672-f639-4f83-822a-efb36d0a9f51/Biss.pdf",
        "expected_candidates": ["Daniel K. Biss"],
        "potential_fields": ["age", "education", "profession", "prior_elected_office"],
    },
    "tn-bluebook-house-2023": {
        "url": "https://publications.tnsosfiles.com/pub/blue_book/23-24/23-24_House.pdf",
        "expected_candidates": ["Justin Pearson"],
        "potential_fields": ["age", "religion", "prior_elected_office"],
    },
    "tn-pearson-114": {
        "url": "https://wapp.capitol.tn.gov/apps/LegislatorInfo/Member?district=H86&ga=114",
        "expected_candidates": ["Justin Pearson"],
        "potential_fields": ["age", "religion", "prior_elected_office"],
    },
    "md-manual-boafo": {
        "url": "https://msa.maryland.gov/msa/mdmanual/06hse/html/msa18393.html",
        "expected_candidates": ["Adrian Boafo"],
        "potential_fields": [
            "age",
            "education",
            "profession",
            "prior_elected_office",
            "other_government",
        ],
    },
    "nv-benitez-thompson-2022": {
        "url": "https://archive.leg.state.nv.us/Session/Legislator/Benitez-Thompson149.pdf",
        "expected_candidates": ["Teresa Benitez-Thompson"],
        "potential_fields": ["age", "education", "profession", "prior_elected_office"],
    },
    "navy-lacore-2025": {
        "url": "https://www.navy.mil/Leadership/Flag-Officer-Biographies/Search/Article/2236442/vice-admiral-nancy-s-lacore/",
        "expected_candidates": ["Nancy Lacore"],
        "potential_fields": ["education", "military"],
    },
    "navy-laubacher-2024": {
        "url": "https://www.navy.mil/DesktopModules/ArticleCS/Print.aspx?Article=2236454&ModuleId=708&PortalId=1",
        "expected_candidates": ["Eileen Laubacher"],
        "potential_fields": ["education", "military", "other_government"],
    },
    "senate-lacore-testimony-2025": {
        "url": "https://www.appropriations.senate.gov/imo/media/doc/Vice%20Admiral%20Nancy%20S.%20Lacore%20Testimony.pdf",
        "expected_candidates": ["Nancy Lacore"],
        "potential_fields": ["education", "military"],
    },
}
for _key, _candidate, _fec in (
    ("mcinnis", "Lee McInnis", "H6AL03199"),
    ("williams", "Drew Williams", "H6KY01169"),
    ("pooley", "Ray Pooley", "H6MI09245"),
    ("johnson", "Jake Johnson", "H6MN01190"),
    ("bradstock", "Alan Bradstock", "H6PA14200"),
    ("perriello", "Tom Perriello", "H8VA05106"),
    ("parsi", "Ace Parsi", "H6WV02150"),
):
    SOURCES[f"fec-{_key}-2026"] = {
        "url": f"https://www.fec.gov/data/candidate/{_fec}/?cycle=2026",
        "expected_candidates": [_candidate],
        "potential_fields": ["incumbency"],
    }


def acquire(root, *, version="v5", sources=SOURCES):
    root = Path(root)
    work = root / f"artifacts/characteristics-{version}"
    work.mkdir(parents=True, exist_ok=True)
    output = work / "retrievals.json"
    old = json.loads(output.read_text()) if output.exists() else []
    known = {r["id"]: r for r in old}

    def fetch(item):
        key, source = item
        path = work / key
        if key in known:
            if known[key]["status"] == "acquired":
                assert fingerprint(path) == {k: known[key][k] for k in ("bytes", "sha256")}, key
                return known[key]
            if "HTTP/2 stream" not in known[key].get("error", ""):
                return known[key]
        result = subprocess.run(
            [
                "curl",
                "--http1.1",
                "--location",
                "--fail",
                "--silent",
                "--show-error",
                "--connect-timeout",
                "20",
                "--max-time",
                "90",
                "--output",
                str(path),
                "--write-out",
                "%{url_effective}",
                source["url"],
            ],
            capture_output=True,
            text=True,
        )
        return {
            "id": key,
            **source,
            "resolved_url": result.stdout,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "retrieval_method": "original_download_curl_TLS_verified",
            "status": "acquired" if result.returncode == 0 else "failed_attempt_not_evidence",
            **(fingerprint(path) if result.returncode == 0 else {}),
            **({"error": result.stderr} if result.returncode else {}),
            **({"previous_attempts": [known[key]]} if key in known else {}),
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(fetch, sources.items()))
    write_json(output, results)
    return results


def claim(trait, value, fragment, *, analytical=None, reason):
    return {
        "trait": trait,
        "value": value,
        "fragment": fragment,
        "qualification": reason,
        "v5_review": {
            "factual_qualified": True,
            "analysis_value": analytical,
            "reason": reason,
            "prospective_availability": "not_established_by_post_election_retrieval",
        },
    }


def degree(level, fragment):
    return claim(
        "education",
        level,
        fragment,
        analytical=level,
        reason="Explicit completed credential, not attendance. Historical source or explicit "
        "completion date establishes the pre-election fact; retrospective retrieval is separate.",
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
        "first House entry. No never-held-office reference is inferred.",
    )


def definitions():
    yield (
        "il-biss-oral-history-2015",
        "2015-09-28 interview; accessioned 2015-12-16",
        "220281",
        2,
        "Senator Daniel Biss, Illinois Statecraft",
        "This interview details",
        [
            claim(
                "age",
                {"birth_year": 1977, "birth_month": 8},
                "Daniel Biss was born in August 1977",
                reason="Explicit birth month/year gives exact election age 49 without an invented birthday.",
            ),
            degree("bachelors", "earned a BA from Harvard University in Mathematics in 1998"),
            degree(
                "doctoral_or_professional",
                "He earned a PhD from the Massachusetts Institute of Technology in 2002",
            ),
            claim(
                "profession",
                "University of Chicago mathematics teacher, 2002-2008",
                "Daniel taught mathematics at the University of Chicago from 2002 to 2008",
                analytical="education",
                reason="Explicit dated teaching employment supports "
                "the declared historical education family, not current primary employment.",
            ),
            office(
                "he was elected to the Illinois House of Representatives in 2010",
                "Illinois House elected 2010; subsequently state senate by 2015",
                ["state"],
            ),
        ],
    )
    yield (
        "tn-pearson-114",
        "Undated retrieved profile; requested 114th session, body also mentions 115th",
        "221188",
        None,
        "Representative Justin J. Pearson",
        "Bills Sponsored",
        [
            claim(
                "age",
                "1995-01-07",
                "Born January 7, 1995",
                reason="Explicit immutable birthday; retrospective source timing does not change the birth fact.",
            ),
            claim(
                "religion",
                "Liberation Christianity",
                "Liberation Christianity",
                reason="Explicit source-recorded religious description at retrieval. Undated live "
                "profile is not evidence that affiliation held at the November 3 election; no analytical code.",
            ),
            office(
                "House member of the 113th through 115th General Assemblies",
                "Tennessee House service beginning in the 113th General Assembly, 2023-2024; "
                "future-session portion is not used as pre-election service",
                ["state"],
            ),
        ],
    )
    yield (
        "md-manual-boafo",
        "Undated live manual; footer copyright January 28, 2026 is not publication proof",
        "220484",
        None,
        "ADRIAN A. BOAFO",
        "Senate House of Delegates General Assembly",
        [
            claim(
                "age",
                "1994-05-10",
                "Born in Arlington, Virginia, May 10, 1994",
                reason="Explicit immutable birthday, retrospectively acquired.",
            ),
            degree("bachelors", "University of Baltimore, B.A. (government & public policy), 2016"),
            degree("masters", "The American University, M.B.A., 2019"),
            claim(
                "profession",
                "Oracle government affairs director from 2021",
                "Senior Director of Government Affairs, Oracle Corporation, 2021-",
                reason="Explicit occupation and start year; corporate employer and MBA do not "
                "establish a business-management occupation in the fixed four-family taxonomy.",
            ),
            office(
                "Member, City Council, District 3, City of Bowie, 2019-22",
                "Bowie council and mayor pro tem 2019-2022; Maryland House from January 11, 2023",
                ["local", "state"],
            ),
            claim(
                "other_government",
                {
                    "history": "National Press Assistant to Representative Ruben Kihuen, 2017-2018",
                    "time_reference": "before_2026-11-03",
                    "elected_office_excluded": True,
                },
                "National Press Assistant, U.S. Representative Ruben Kihuen, 4th Congressional District, Nevada, 2017-18",
                reason="Explicit dated non-elected congressional staff employment. Not an elected "
                "office or an inference from caucus membership; no negative reference.",
            ),
        ],
    )
    yield (
        "nv-benitez-thompson-2022",
        "2022-12 revision",
        "220715",
        1,
        "Legislative Biography",
        None,
        [
            claim(
                "age",
                {"birth_year": 1978},
                "Born: 1978",
                reason="Birth year supports ages 47-48 at election, not an exact birthday or midpoint.",
            ),
            degree("bachelors", "University of Nevada, Reno, B.A."),
            degree("masters", "University of Michigan, Ann Arbor, M.S.W."),
            claim(
                "profession",
                "Licensed social worker",
                "Licensed Social Worker",
                reason="Explicit licensed occupation in a historical directory. Social work alone "
                "does not establish clinical healthcare practice or another declared family.",
            ),
            office(
                "November 2010 to November 2022",
                "Nevada Assembly November 2010-November 2022",
                ["state"],
            ),
        ],
    )
    yield (
        "senate-lacore-testimony-2025",
        "2025-05-22 Senate testimony",
        "221073",
        3,
        "Vice Admiral Nancy S. Lacore",
        None,
        [
            degree("bachelors", "College of the Holy Cross, where she earned a Bachelor of Arts"),
            degree("masters", "She earned a Master of Arts from San Diego State Univer sity"),
            claim(
                "military",
                True,
                "She affiliated with the Navy Reserve (NR) in 2000",
                analytical=True,
                reason="Explicit historical Navy Reserve service, not a "
                "negative inference for anyone else. Does not enable a nonservice comparison.",
            ),
        ],
    )
    for key, cid, name, committee, state_district in (
        (
            "mcinnis",
            "219729",
            "MCINNIS, VICTOR LEE",
            "LEEMCINNIS4ALABAMA",
            "Alabama House District 3",
        ),
        (
            "pooley",
            "220538",
            "POOLEY, STEVEN RAYMOND",
            "COMMITTEE TO ELECT RAY POOLEY",
            "Michigan House District 9",
        ),
        (
            "johnson",
            "220596",
            "JOHNSON, JACOB",
            "JAKE JOHNSON FOR CONGRESS",
            "Minnesota House District 1",
        ),
        (
            "perriello",
            "221215",
            "PERRIELLO, THOMAS",
            "TOM PERRIELLO FOR CONGRESS",
            "Virginia House District 5",
        ),
        (
            "parsi",
            "221251",
            "PARSI, AHSAN",
            "ACE PARSI FOR CONGRESS",
            "West Virginia House District 2",
        ),
    ):
        yield (
            f"fec-{key}-2026",
            "Undated FEC live 2026-election profile, retrieved retrospectively",
            cid,
            None,
            name,
            "Spending by others to support or oppose This tab",
            [
                claim(
                    "incumbency",
                    False,
                    f"Seat: {state_district} Type of candidacy: Challenger",
                    analytical=False,
                    reason=f"FEC's 2026 House person/party/district classification explicitly says "
                    f"Challenger. The same candidate page authorizes {committee}, directly linking "
                    "the filed legal name to the native campaign name. Retrospective election "
                    "classification, not independent federal service or lifetime nonservice verification.",
                )
            ],
        )


def register(root):
    from .characteristics_v4_batch import register as register_reviewed

    details = {}
    for key, *_ in definitions():
        details[key] = {
            "identity_qualification": (
                "FEC legal-name page explicitly associates the native campaign-name committee "
                "with this person, 2026 House seat and party. Unique held FEC ID reviewed; "
                "unsupported aliases and duplicate IDs remain held."
                if key.startswith("fec-")
                else "Literal full subject name, independently concordant state, prior office and "
                "biographical history from the native candidate record. Middle-name omissions "
                "do not replace contest IDs; historical state-office districts are not congressional "
                "districts. No identity attribute inferred from names or photographs."
            ),
            "kind": "official_FEC_candidate_election_profile"
            if key.startswith("fec-")
            else "official_historical_biography_or_live_directory",
        }
    details["nv-benitez-thompson-2022"]["identity_fragment"] = "Teresa Benitez-Thompson"
    fec = {
        "mcinnis": ("H6AL03199", "LEEMCINNIS4ALABAMA"),
        "pooley": ("H6MI09245", "COMMITTEE TO ELECT RAY POOLEY"),
        "johnson": ("H6MN01190", "JAKE JOHNSON FOR CONGRESS"),
        "perriello": ("H8VA05106", "TOM PERRIELLO FOR CONGRESS"),
        "parsi": ("H6WV02150", "ACE PARSI FOR CONGRESS"),
    }

    def checked_definitions():
        for definition in definitions():
            key, *_, claims = definition
            if key.startswith("fec-"):
                fec_id, committee = fec[key.split("-")[1]]
                for c in claims:
                    c["identity_support"] = [
                        f"ID: {fec_id}",
                        f"Authorized campaign committees: {committee}",
                        "Election 2026",
                    ]
            yield definition

    result = register_reviewed(
        root,
        version="v5",
        definitions_fn=checked_definitions,
        source_details=details,
    )
    result["source_population"] = (
        "Bounded new official biographical originals and FEC campaign-name identity links. "
        "All retrieved after the election; no prospective availability or representative coverage claimed."
    )
    result["review_exclusions"] = [
        {
            "source": "tn-pearson-114",
            "field": "education",
            "reason": "Bowdoin College listing does not explicitly establish a completed credential.",
        },
        {
            "source": "tn-pearson-114",
            "field": "religion",
            "reason": "Explicit religious description is factual at retrieval; its election-date validity is unestablished.",
        },
        {
            "source": "md-manual-boafo",
            "field": "race_ethnicity_religion",
            "reason": "Black, Latino and associate Jewish caucus memberships are not identity classifications.",
        },
        {
            "source": "nv-benitez-thompson-2022",
            "field": "age",
            "reason": "Year only: retain 47-48 interval, not exact age.",
        },
        {
            "source": "fec-williams-2026",
            "field": "incumbency",
            "reason": "Williams for Kentucky committee does not explicitly link Drew to John Andrew. Hold preserved.",
        },
        {
            "source": "fec-bradstock-2026",
            "field": "incumbency",
            "reason": "Surname-only committee does not independently link Alan to David Alan. Hold preserved.",
        },
        {
            "source": "all",
            "field": "nonservice",
            "reason": "No explicit never-held-office, never-government or nonmilitary reference acquired.",
        },
    ]
    write_json(Path(root) / "data/house-characteristics-v5-acquisitions.json", result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--register", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(register(root) if args.register else acquire(root), indent=2))
