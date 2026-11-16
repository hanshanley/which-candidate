"""Register the bounded, literally reviewed V4 source-family acquisition batch."""

import json
import shutil
from pathlib import Path

from .characteristics_research import normalized, reviewed_claims, source_text
from .storage import fingerprint, read_rows, write_json


def claim(trait, value, fragment, *, analytical=None, reason="", qualified=True):
    return {
        "trait": trait,
        "value": value,
        "fragment": fragment,
        "qualification": reason
        or "Literal source-recorded fact; factual qualification and analytical coding are separately reviewed.",
        "v4_review": {
            "factual_qualified": qualified,
            "analysis_value": analytical,
            "reason": reason,
            "prospective_availability": "not_established_by_post_election_retrieval",
        },
    }


def education(level, fragment):
    return claim(
        "education",
        level,
        fragment,
        analytical=level,
        reason="Explicit completed credential in a dated pre-election directory or questionnaire; "
        "highest supported credential, not proof of total lifetime attainment.",
    )


def profession(value, fragment, *, code=None):
    return claim(
        "profession",
        value,
        fragment,
        analytical=code,
        reason=(
            "Explicit historical occupation before the election in a dated source; "
            "one supported family in the existing four-family definition, not current primary employment."
            if code
            else "Explicit career history retained; mixed supported families or occupation outside "
            "the four declared families prevents a unique analytical code."
        ),
    )


def office(fragment, description):
    return claim(
        "prior_elected_office",
        {
            "history": description,
            "time_reference": "before_2026-11-03",
            "not_equivalent_to": "office_before_first_House_entry",
        },
        fragment,
        reason="Positive office history before the 2026 cutoff; no explicit never-held-office "
        "reference. Not mixed with the different before-first-House-entry variable.",
    )


def government(fragment, description):
    return claim(
        "other_government",
        {
            "history": description,
            "time_reference": "before_2026-11-03",
            "elected_office_excluded": True,
        },
        fragment,
        reason="Explicit non-elected governmental role; no supported never-served reference. "
        "Advisory membership alone is not paid government employment.",
    )


def religion(value, fragment):
    return claim(
        "religion",
        value,
        fragment,
        analytical=value,
        reason="Explicit affiliation or clergy self-description in a dated source; "
        "not inferred from upbringing, relatives, endorsements or a surname.",
    )


def birthday(value, fragment):
    return claim(
        "age",
        value,
        fragment,
        analytical=value,
        reason="Exact immutable birth fact, retrospectively acquired; no invented birthday.",
    )


def military(fragment):
    return claim(
        "military",
        True,
        fragment,
        analytical=True,
        reason="Explicit multiyear prior military service establishes a pre-election positive; "
        "branch wording remains source-reported. No inference of nonservice for anyone else "
        "and no available service-versus-nonservice comparison.",
    )


def definitions():
    # Each tuple identifies one subject's bounded section, not the whole shared document.
    return [
        (
            "mi-manual-legislative",
            "2025-2026 edition",
            "220516",
            45,
            "Sean McCann was born",
            None,
            [
                claim("age", {"birth_month": 9, "birth_year": 1971}, "born September 1971"),
                education(
                    "bachelors", "Western Michigan University, Bachelor’s Degree, Political Science"
                ),
                profession(
                    "Nonprofit executive", "Vine Neighborhood Association, Executive Director"
                ),
                office(
                    "House of Representatives, Elected November 2010 and 2012",
                    "Michigan House 2010/2012; Senate 2018/2022; Kalamazoo city commission",
                ),
            ],
        ),
        (
            "mi-manual-legislative",
            "2025-2026 edition",
            "220549",
            47,
            "Jeremy Moss was born",
            None,
            [
                claim("age", {"birth_month": 6, "birth_year": 1986}, "born June 1986"),
                religion("jewish", "He is Jewish and a member of Congregation Beth Ahm"),
                education(
                    "bachelors",
                    "Michigan State University, Bachelor’s Degree, Journalism and Political Science",
                ),
                government(
                    "Representative Paul Condino, Legislative Staff",
                    "Michigan House legislative staff",
                ),
                office(
                    "House of Representatives, Elected November 2014 and 2016",
                    "Michigan House 2014/2016; Senate 2018/2022; Southfield city council",
                ),
            ],
        ),
        (
            "mi-manual-legislative",
            "2025-2026 edition",
            "220559",
            129,
            "Donavan McKinney was born",
            None,
            [
                claim("age", {"birth_month": 6, "birth_year": 1992}, "born June 1992"),
                religion("other_christian", "He is Christian."),
                education(
                    "bachelors",
                    "University of Michigan Gerald R. Ford School of Public Policy, Bachelor’s Degree, Public Policy",
                ),
                government(
                    "Michigan House of Representatives, Legislative Director",
                    "Michigan House legislative director",
                ),
                profession(
                    "Political and community work", "Climate Power, National Political Director"
                ),
                office(
                    "House of Representatives, Elected November 2022 and 2024",
                    "Michigan House 2022/2024",
                ),
            ],
        ),
        (
            "mi-manual-congressional",
            "2025-2026 edition",
            "220524",
            10,
            "Debbie Dingell was born",
            None,
            [
                birthday("1953-11-23", "born November 23, 1953"),
                education("masters", "Georgetown University, Master’s Degree, Liberal Studies"),
                profession(
                    "Foundation executive",
                    "General Motors Foundation, President and Senior Executive",
                ),
                office(
                    "U.S. House of Representatives, Elected November 2014",
                    "US House since 2014 election; no claim of office before first entry",
                ),
            ],
        ),
        (
            "mi-manual-congressional",
            "2025-2026 edition",
            "220533",
            14,
            "Kristen McDonald Rivet was born",
            None,
            [
                birthday("1970-07-11", "born July 11, 1970"),
                religion("catholic", "She is Roman Catholic."),
                education(
                    "masters",
                    "University of Michigan-Flint, Master’s Degree, Education and Public Administration",
                ),
                government(
                    "Michigan Department of Education, Chief of Staff, 2006 to 2007",
                    "Michigan education chief of staff 2006-2007",
                ),
                office(
                    "Michigan Senate, Elected November 2022",
                    "Michigan Senate 2022; Bay City commissioner 2019-2022",
                ),
            ],
        ),
        (
            "mi-manual-congressional",
            "2025-2026 edition",
            "220554",
            19,
            "Rashida Tlaib was born",
            None,
            [
                birthday("1976-07-24", "born July 24, 1976"),
                religion("muslim", "She is Muslim."),
                education("doctoral_or_professional", "Thomas Cooley Law School, Juris Doctor"),
                profession(
                    "Attorney",
                    "Sugar Law Center for Economic and Social Justice, Attorney",
                    code="legal",
                ),
                office(
                    "Michigan House of Representatives, Elected November 2008, 2010, and 2012",
                    "Michigan House 2008-2012 elections",
                ),
            ],
        ),
        (
            "mi-historical-complete",
            "historical service table; retrieval 2026-11-16",
            "220516",
            None,
            "McCann, Sean",
            "McCarthy, John",
            [
                birthday("1971-09-21", "09/21/1971"),
            ],
        ),
        (
            "mi-historical-complete",
            "historical service table; retrieval 2026-11-16",
            "220549",
            None,
            "Moss, Jeremy",
            "Moss, Joe",
            [
                birthday("1986-06-23", "06/23/1986"),
            ],
        ),
        (
            "mi-historical-complete",
            "historical service table; retrieval 2026-11-16",
            "220559",
            None,
            "McKinney, Donavan1",
            "McKinney, John",
            [
                birthday("1992-06-16", "06/16/1992"),
            ],
        ),
        (
            "mi-lwv-2026-guide",
            "2026 general-election guide",
            "220519",
            18,
            "CHRISTIAN VUKASOVICH",
            None,
            [
                education(
                    "doctoral_or_professional",
                    "Ph.D., Media and Communication, Bowling Green State University (2012)",
                ),
                profession("Educator", "Occupation / Current Position: Educator", code="education"),
            ],
        ),
        (
            "mi-lwv-2026-guide",
            "2026 general-election guide",
            "220530",
            20,
            "WILLIAM LAWRENCE",
            None,
            [
                education("bachelors", "BA in Anthropology & Sociology from Swarthmore College"),
                profession(
                    "Community organizer", "Occupation / Current Position: Community Organizer"
                ),
            ],
        ),
        (
            "mi-lwv-2026-guide",
            "2026 general-election guide",
            "220502",
            14,
            "CALLIE BARR",
            None,
            [
                education("doctoral_or_professional", "J.D. University of Michigan Law School"),
                profession(["legal", "education"], "high school English teacher"),
            ],
        ),
        (
            "ia-redbook-2025",
            "2025-2026 Iowa Official Register",
            "220351",
            53,
            "Sarah T r one Garriott",
            None,
            [
                claim("age", {"birth_year": 1978}, "Born in 1978"),
                religion(
                    "protestant",
                    "Ordained minister in Evangelical Lutheran Church in America (ELCA)",
                ),
                education("masters", "M.Div ., Lutheran School of Theology"),
                profession(
                    "ELCA minister and interfaith coordinator",
                    "Coordinator of Interfaith Engagement",
                ),
                office("Serving third term in Senate", "Iowa state senator"),
            ],
        ),
        (
            "ia-redbook-2025",
            "2025-2026 Iowa Official Register",
            "220347",
            76,
            "Lindsay James",
            "Thomas M. Jeneary",
            [
                claim("age", {"birth_year": 1980}, "Born in 1980"),
                religion("protestant", "Ordained pastor , Presbyterian Church (PCUSA)"),
                education(
                    "masters", "master ’ s degree in divinity from Fuller Theological Seminary"
                ),
                profession(
                    "Former adjunct faculty; Presbyterian pastor",
                    "Former adjunct faculty , University of Dubuque",
                    code="education",
                ),
                office("Serving fourth term in House", "Iowa state representative"),
            ],
        ),
        (
            "ca-joint-handbook-2019",
            "2019-2020 edition; 2020 revision",
            "219872",
            48,
            "WIENER, Scott",
            None,
            [
                education("doctoral_or_professional", "law degree from Harvard"),
                profession("Deputy city attorney", "Deputy City Attorney", code="legal"),
                government("Deputy City Attorney", "San Francisco deputy city attorney"),
                office(
                    "Board of Supervisors", "San Francisco supervisor; state senator elected 2016"
                ),
            ],
        ),
        (
            "ca-joint-handbook-2019",
            "2019-2020 edition; 2020 revision",
            "219965",
            44,
            "PAN, Richard",
            None,
            [
                education("doctoral_or_professional", "medical doctorate"),
                profession(
                    ["healthcare", "education"], "Pediatrician and former UC Davis educator"
                ),
                office(
                    "state Assembly in 2010 and State Senate in 2014",
                    "California senator; previously Assembly",
                ),
            ],
        ),
        (
            "ca-joint-handbook-2019",
            "2019-2020 edition; 2020 revision",
            "219903",
            246,
            "IRWIN, Jacqui",
            "JONES-SA",
            [
                education("bachelors", "Received B.S., Systems Engineering"),
                profession("Engineer", "Teledyne Systems"),
                office(
                    "Former Councilmember and May",
                    "Thousand Oaks councilmember and mayor 2004-2014",
                ),
            ],
        ),
        (
            "ca-joint-handbook-2019",
            "2019-2020 edition; 2020 revision",
            "219889",
            41,
            "McGUIRE, Mike",
            None,
            [
                claim(
                    "education",
                    "Sonoma State graduation; credential level unstated",
                    "graduated from Sonoma State",
                    reason="Explicit graduation, but no degree level in this fragment; attendance at junior college is not an associate degree.",
                ),
                office(
                    "Board of Supervisors",
                    "Local school board, city council, county supervisor and California Senate",
                ),
            ],
        ),
        (
            "ca-joint-handbook-2019",
            "2019-2020 edition; 2020 revision",
            "219914",
            240,
            "FRIEDMAN, Laura",
            None,
            [
                birthday("1966-12-03", "Born December 3, 1966"),
                education("bachelors", "Received B.A., University of Rochester"),
                profession("Small business owner", "Small Business Owner", code="business"),
                office("Former Councilmember (2009", "Glendale councilmember and mayor 2009-2014"),
            ],
        ),
        (
            "ca-joint-handbook-2019",
            "2019-2020 edition; 2020 revision",
            "219880",
            224,
            "MULLIN, Kevin",
            None,
            [
                birthday("1970-06-15", "Born June 15, 1970"),
                education("masters", "M.P .A., San Francisco State University (1998)"),
                profession(
                    "Former small business owner", "Former Small Business Owner", code="business"
                ),
                office(
                    "City Councilmember (2007",
                    "South San Francisco councilmember 2007-2012 and mayor 2010-2011",
                ),
            ],
        ),
        (
            "pa-rabb-archive",
            "undated official archive; dated historical facts",
            "221019",
            None,
            'RABB, Christopher M., "Chris,"',
            None,
            [
                birthday("1970-02-21", "February 21, 1970"),
                education(
                    "masters", "M.S., organizational dynamics, University of Pennsylvania, 2006"
                ),
                profession("Adjunct professor, Temple 2012-2016", "2012-2016", code="education"),
                government("legislative aide", "US Senate legislative aide"),
                office(
                    "2017",
                    "Pennsylvania House first service 2017, reelected through current session",
                ),
            ],
        ),
        (
            "in-ford-2020",
            "2020-05 official Senate biography",
            "220322",
            1,
            "J.D. Ford",
            None,
            [
                education("masters", "Master of Science"),
                profession("Higher education and nonprofit executive", "higher education"),
            ],
        ),
        (
            "pa-harvie-official",
            "2026 term biography; retrieved 2026-11-16",
            "221015",
            None,
            "Robert J. Harvie Jr.",
            None,
            [
                claim(
                    "education",
                    "masters",
                    "master's degree in education from Holy Family University",
                    reason="Explicit completed credential, but this undated page does not date completion "
                    "before the election. Retain factual qualification without silently waiving timing.",
                ),
                profession(
                    "Teacher for 26 years", "a career he maintained for 26 years", code="education"
                ),
                office(
                    "elected to the Board of Bucks County Commissioners in November 2019",
                    "Bucks County commissioner 2019; Falls Township supervisor 2003-2020",
                ),
            ],
        ),
        (
            "npr-clergy-2026",
            "2026-09-27",
            "221140",
            None,
            "In Dallas, Frederick Haynes",
            "Haynes recently hosted",
            [
                religion(
                    "protestant",
                    "He's led the 13,000-member Friendship-West Baptist Church for more than four decades",
                ),
                profession(
                    "Baptist pastor for four decades",
                    "He's led the 13,000-member Friendship-West Baptist Church for more than four decades",
                ),
            ],
        ),
        (
            "lcv-newmembers-2026",
            "2026-11 post-election guide",
            "221215",
            82,
            "Tom Perriello is a former Congressman",
            None,
            [
                claim(
                    "education",
                    "doctoral_or_professional",
                    "After earning his law degree",
                    analytical="doctoral_or_professional",
                    reason="Narrative explicitly places completed Yale law degree before his previous House term, not after the 2026 election.",
                ),
                government(
                    "State Department",
                    "Former diplomatic roles at State Department; envoy under Obama and Biden",
                ),
                office(
                    "before going on to win election to the U.S. House",
                    "Prior US House term, explicitly former before return; not current federal incumbency",
                ),
            ],
        ),
        (
            "lcv-newmembers-2026",
            "2026-11 post-election guide",
            "220811",
            23,
            "Rebecca Bennett spent decades",
            None,
            [
                military("serve in the armed forces for over 15 years"),
            ],
        ),
        (
            "lcv-newmembers-2026",
            "2026-11 post-election guide",
            "220870",
            32,
            "Cait Conley is a lifelong",
            None,
            [
                military("Conley served for 16 years as an active duty Army officer"),
                government(
                    "director for counterterrorism on the National Security Council under the Biden administration",
                    "Prior Biden-administration National Security Council role",
                ),
            ],
        ),
        (
            "lcv-newmembers-2026",
            "2026-11 post-election guide",
            "219990",
            43,
            "Jessica Killin is a fourth",
            None,
            [
                military("served as a captain and paratrooper in the U.S. Army"),
                claim(
                    "education",
                    "doctoral_or_professional",
                    "earn her law degree at Georgetown before working at USAA",
                    analytical="doctoral_or_professional",
                    reason="Narrative explicitly places completed law degree before work following the 2008 financial crisis.",
                ),
                government(
                    "chief of staff for former Second Gentleman Doug Emhoff",
                    "Prior congressional and executive office staff",
                ),
            ],
        ),
        (
            "lcv-newmembers-2026",
            "2026-11 post-election guide",
            "221073",
            45,
            "Nancy Lacore is a former chief",
            None,
            [
                military("35-year career in the Navy"),
            ],
        ),
        (
            "lcv-newmembers-2026",
            "2026-11 post-election guide",
            "219782",
            80,
            "Joanna Mendoza is a daughter",
            None,
            [
                military("went on to serve for 20 years"),
            ],
        ),
    ]


def register(root, *, version="v4", definitions_fn=definitions, source_details=None):
    root = Path(root)
    work = root / f"artifacts/characteristics-{version}"
    source_details = source_details or {}
    attempts = json.loads((work / "retrievals.json").read_text())
    candidates = {
        c["candidate_id"]: c for c in read_rows(root / "results/house/candidates.jsonl.gz")
    }
    journal_path = root / "data/house-characteristics-research.json"
    journal = json.loads(journal_path.read_text())
    receipts_path = root / "data/house-characteristics-receipts.json"
    receipts = json.loads(receipts_path.read_text())
    sources, documents, errors = [], {}, []
    cache = root / "data/raw/house-characteristics-v1"
    for key, publication, cid, page, start, end, claims in definitions_fn():
        candidate = candidates[cid]
        document = f"{version}-{key}"
        scope = {"start": start}
        if page:
            scope["page"] = page
        if end:
            scope["end"] = end
        source = {
            **{
                k: candidate[k]
                for k in ("candidate_id", "contest_id", "name", "state", "district", "party")
            },
            "id": f"{document}-{cid}",
            "document_id": document,
            "kind": "dated_questionnaire_or_directory"
            if key != "npr-clergy-2026"
            else "dated_published_interview",
            "publication_date": publication if publication[:4].isdigit() else None,
            "edition_or_date_note": publication,
            "text_scope": scope,
            "identity_fragment": start,
            "identity_qualification": "Literal subject name and independently concordant state/office/biography; "
            "native contest identity retained, historical office district not substituted for current House district. "
            "Rabb explicitly Chris/Christopher; Harvie explicitly Bob/Robert; Ford punctuation only; "
            "Michigan table full name and birth month/year independently agree with current manual. "
            "Retrieval after election does not establish prospective availability.",
            "claims": claims,
            **source_details.get(key, {}),
        }
        successful = [
            a for a in attempts if a["id"] == key and a["status"] in {"acquired", "ok", "success"}
        ]
        if not successful:
            errors.append(f"{key}: no successful original receipt")
            continue
        attempt = successful[-1]
        original = work / key
        receipt = {
            "id": source["id"],
            "url": attempt["url"],
            "resolved_url": attempt["url"],
            "retrieved_at": attempt["retrieved_at"],
            "retrieval_method": "original_download_curl_TLS_verified",
            "original_bytes_acquired": True,
            **fingerprint(original),
        }
        source["url"] = receipt["url"]
        try:
            scoped = source_text(original.read_bytes(), source)
            for index, c in enumerate(claims):
                if normalized(c["fragment"]) not in scoped:
                    errors.append(
                        f"{key}/{cid}:{index} absent fragment {c['fragment']!r}; section {scoped[:150]!r}"
                    )
            reviewed_claims(source, receipt, scoped)
        except ValueError as exc:
            errors.append(str(exc))
        sources.append(source)
        documents[document] = {"id": document, **{k: v for k, v in receipt.items() if k != "id"}}
        source["_receipt"] = receipt
    if errors:
        raise ValueError("\n".join(errors))
    for source in sources:
        receipt = source.pop("_receipt")
        document = source["document_id"]
        if not (cache / document).exists():
            shutil.copyfile(work / document.removeprefix(f"{version}-"), cache / document)
        receipts["sources"] = [r for r in receipts["sources"] if r["id"] != source["id"]]
        receipts["sources"].append({**receipt, "status": "acquired_pending_review"})
    journal["sources"] = [
        s for s in journal["sources"] if not s["id"].startswith(f"{version}-")
    ] + sources
    write_json(journal_path, journal)
    write_json(receipts_path, receipts)
    result = {
        "documents": list(documents.values()),
        "sources": sources,
        "new_acquired_claims": sum(len(s["claims"]) for s in sources),
        "new_document_hashes": len({d["sha256"] for d in documents.values()}),
        "discovery_dispositions": attempts,
        "source_population": "Bounded state-directory, questionnaire and published-interview acquisition; "
        "not representative or exhaustive; post-election new-member guide is selected and retrospective.",
    }
    write_json(root / f"data/house-characteristics-{version}-acquisitions.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(register(Path(__file__).resolve().parents[1]), indent=2))
