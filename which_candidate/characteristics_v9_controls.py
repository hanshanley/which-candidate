"""Narrow signed-FEC and positively evidenced election-control reviews."""

import csv
import re
from datetime import date

from .characteristics_research import normalized, source_text
from .house_characteristics import CUTOFF

EXPECTED_IDS = {
    "220449": {"H6LA05325", "H6LA05333"},
    "221075": {"H6SC02159", "H6SC02167"},
}
IDENTITY = ("candidate_id", "contest_id", "name", "state", "district", "party")
BRIDGE_FIELDS = ("legal_name", "committee", "filing_address", "signed_date")


def walker_bridge(candidate, incumbent, report):
    return (
        tuple(candidate[k] for k in ("candidate_id", "name", "state", "district", "party"))
        == ("220434", "Caleb Walker", "LA", "03", "Democratic")
        and incumbent["candidate_id"] == "220433"
        and incumbent["name"] == "Clay Higgins"
        and incumbent["contest_id"] == candidate["contest_id"]
        and incumbent["legislative"]["status"] == "exact_fec_service_crosswalk"
        and incumbent["legislative"]["house_incumbent"] is True
        and all(
            normalized(marker) in normalized(report)
            for marker in (
                'Caleb "With a C" Walker (D)',
                "Caleb Walker for Congress | Louisiana's 3rd District",
                "I haven't held elected office before",
                "Incumbent candidate; Higgins has represented the 3rd Congressional District since 2017",
            )
        )
    )


def register_walker(root, add, acquired, by_id, claim):
    key = "wrkf-louisiana-third-candidate-questionnaire-2026"
    if key not in acquired:
        return
    candidate = by_id["220434"]
    report = source_text((root / "artifacts/characteristics-v9" / key).read_bytes(), {})
    if not walker_bridge(candidate, by_id["220433"], report):
        raise ValueError("Unqualified Walker named-questionnaire/contest bridge")
    add(
        key,
        candidate,
        [
            claim(
                "incumbency",
                False,
                "I haven't held elected office before",
                analysis=False,
                timing="dated_pre_election_questionnaire_2026-10-20",
                reason="Explicit candidate answer denying prior elected office, in a dated "
                "LA03 general-election questionnaire that independently identifies Clay Higgins "
                "as incumbent. Native Higgins has a positive federal-service crosswalk. "
                "This establishes election nonincumbency, not an FEC match or a lifetime "
                "claim about all public employment.",
            ),
            claim(
                "prior_elected_office",
                {"reported_elected_experience": "None before this candidacy"},
                "I haven't held elected office before",
                timing="dated_pre_election_questionnaire_2026-10-20",
                reason="Explicit personal negative under the question about previously "
                "held office; not inferred from first congressional candidacy. The "
                "original before-first-House-entry comparison remains unavailable.",
            ),
            claim(
                "military",
                {"reported_service": "U.S. Army Sergeant First Class, ten years, retired"},
                "ten years as a U.S. Army Sergeant First Class",
                analysis=True,
                timing="retired_multiyear_service_documented_2026-10-20",
                reason="Explicit retired personal service in a dated pre-election answer; "
                "not inferred from veteran advocacy or an advisory role.",
            ),
            claim(
                "profession",
                {
                    "reported_careers": [
                        "U.S. Army Sergeant First Class",
                        "Sam's Club department management",
                    ]
                },
                "running the top-ranked department",
                timing="dated_pre_election_questionnaire_2026-10-20",
                reason="Multiple explicitly reported careers retained without forcing "
                "a principal historical occupational family.",
            ),
            claim(
                "other_government",
                {"reported_role": "Louisiana Task Force on Career Alignment"},
                "serving on Louisiana's Task Force on Career Alignment",
                factual=False,
                timing="dated_pre_election_questionnaire_2026-10-20",
                reason="Task-force service is explicit but does not establish paid "
                "government employment.",
            ),
        ],
        scope={
            "start": 'Caleb "With a C" Walker (D)',
            "end": "The following candidates did not respond",
        },
        kind="dated_public_broadcaster_candidate_questionnaire",
        date="2026-10-20",
    )
    filing_key = "louisiana-house-candidates-2026"
    filing = root / "artifacts/characteristics-v8" / filing_key
    records = csv.DictReader(filing.open(encoding="utf-8-sig"))
    matches = [
        (number, row)
        for number, row in enumerate(records, 2)
        if (
            row["BallotFirstName"],
            row["BallotLastName"],
            row["OfficeTitleDescription"],
            row["Party"],
            row["Election"],
        )
        == ("Caleb 'With a C'", "Walker", "3rd Congressional District", "Democrat", "11/03/2026")
    ]
    if len(matches) != 1:
        raise ValueError("Walker official ballot nickname/contest bridge is not unique")
    number, official = matches[0]
    metadata = {k: acquired[key][k] for k in ("url", "sha256", "retrieved_at")}
    items = []
    for trait, column in (("race", "Race"), ("gender", "Gender")):
        item = claim(
            trait,
            [official[column]],
            f"{column}={official[column]}",
            timing="filed_2026-08-06",
            reason="Literal official filing classification after a dated named "
            "questionnaire bridges the exact With a C ballot nickname, LA03 and party. "
            "No historical analytical race/ethnicity category inferred.",
        )
        item["v9_subject_bridge"] = metadata
        items.append(item)
    add(
        filing_key,
        candidate,
        items,
        scope={"csv_row": number},
        kind="retained_official_candidate_filing_identity_correction",
        date="2026-08-06",
        columns=[
            "Election",
            "OfficeTitle",
            "OfficeTitleDescription",
            "BallotFirstName",
            "BallotLastName",
            "Party",
            "Race",
            "Gender",
            "Filed Date",
        ],
        subject="BallotFirstName=Caleb 'With a C' | BallotLastName=Walker",
        identity_reason="Exact With a C nickname, House district and party in the "
        "official filing and dated WRKF questionnaire; full native Caleb Walker is "
        "explicitly named by WRKF. No FEC identity was invented.",
    )


def words(value):
    return re.findall(r"\w+", value.casefold())


def held_review(candidates, previous, panel, inputs):
    old = {(r["candidate_id"], r["trait"]): r for r in previous}
    reviews = []
    for candidate in candidates:
        cid = candidate["candidate_id"]
        expected = EXPECTED_IDS.get(cid)
        if not expected or old[(cid, "incumbency")]["analysis_eligible"]:
            continue
        observations = [
            o
            for o in inputs["reviewed_characteristic_observations"]
            if o["candidate_id"] == cid
            and o["source_id"].startswith("v9-")
            and o.get("v9_identity_bridge")
        ]
        if len(observations) != 2:
            continue
        bridges = [o["v9_identity_bridge"] for o in observations]
        if (
            {b.get("fec_id") for b in bridges} != expected
            or any(len({b.get(k) for b in bridges}) != 1 for k in BRIDGE_FIELDS)
            or any(not bridges[0].get(k) for k in BRIDGE_FIELDS)
            or len({o["receipt"]["sha256"] for o in observations}) != 2
        ):
            continue
        try:
            signed = date.fromisoformat(bridges[0]["signed_date"])
        except ValueError:
            continue
        if signed > CUTOFF or signed.year != 2026:
            continue
        if any(
            o["trait"] != "incumbency"
            or o["source_kind"] != "signed_FEC_statement_of_candidacy"
            or o["review_status"] != "fragment_and_identity_reviewed"
            or o["publication_date"] != b["signed_date"]
            or any(o[k] != candidate[k] for k in IDENTITY)
            or not {b["committee"], b["filing_address"], b["fec_id"]}.issubset(
                o.get("identity_support", [])
            )
            or b.get("evidence_role") != "identity_only_retained_FEC_classification"
            or o["v9_review"]["factual_qualified"]
            or o["v9_review"]["analysis_value"] is not None
            for o, b in zip(observations, bridges)
        ):
            continue
        native = words(candidate["name"])
        matches = [
            r
            for r in inputs["fec"]
            if r["chamber"] == "house"
            and r["election_year"] == 2026
            and r["state"] == candidate["state"]
            and r["district"] == candidate["district"]
            and r["party"] in {"DEM", "DFL"}
            and words(r["first"])[:1] == native[:1]
            and words(r["last"]) == native[-1:]
        ]
        if (
            candidate["party"] != "Democratic"
            or {r["fec_id"] for r in matches} != expected
            or any(words(r["name"]) != words(bridges[0]["legal_name"]) for r in matches)
            or any(type(r["incumbent"]) is not bool for r in matches)
            or len({r["incumbent"] for r in matches}) != 1
        ):
            continue
        reviews.append(
            {
                **{k: candidate[k] for k in IDENTITY},
                "trait": "incumbency",
                "value": matches[0]["incumbent"],
                "held_records": matches,
                "new_acquisition": False,
                "identity_bridge": [o["source_id"] for o in observations],
                "signed_source_sha256": [o["receipt"]["sha256"] for o in observations],
                "retained_fec_ids": sorted(expected),
                "qualification": "Both signed Form 2 originals identify the same legal name, "
                "principal committee, filing address and signing date for this party/House "
                "contest. Both FEC IDs retained; consistent explicit election classification, "
                "not independent federal-service verification or a lifetime nonservice claim.",
            }
        )
    return reviews
