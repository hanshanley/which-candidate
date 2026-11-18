from copy import deepcopy
from types import SimpleNamespace

import pytest

from which_candidate.characteristics_v4 import birth_interval
from which_candidate.characteristics_v8 import acquisition_accounting
from which_candidate.characteristics_v9 import structural_eligibility
from which_candidate.characteristics_v9_controls import held_review, walker_bridge
from which_candidate.characteristics_v9_extract import (
    california_rows,
    education,
    fec_ballot_bridge,
    pamphlet_age,
    retained_reviews,
    reviewed_alias_subject,
)
from which_candidate.characteristics_v9_review import directory_page, matches_directory
from which_candidate.house_backgrounds import validate_reported_age, validate_reported_age_year


@pytest.mark.parametrize(
    "broken",
    [None, "party", "district", "state", "year", "name", "duplicate", "unretained", "fec_id"],
)
def test_filing_legal_name_bridge_requires_a_unique_retained_official_identity(broken):
    record = {
        "fec_id": "H6CA19154",
        "first": "PETER COE",
        "last": "VERBICA",
        "party": "REP",
        "state": "CA",
        "district": "19",
        "election_year": 2026,
        "chamber": "house",
    }
    candidate = {
        "name": "Peter Verbica",
        "state": "CA",
        "district": "19",
        "party": "Republican",
        "identity": {
            "status": "official_name_party_year_state",
            "fec_id": record["fec_id"],
            "official_alternatives": [record],
        },
    }
    filing = {"printed_name": "Peter Coe Verbica", "district": "19", "party": "Republican"}
    originals = [deepcopy(record)]
    if broken in {"party", "district", "state"}:
        candidate[broken] = {"party": "Democratic", "district": "20", "state": "OR"}[broken]
    elif broken == "year":
        record["election_year"] = 2024
    elif broken == "name":
        filing["printed_name"] = "Peter Different Verbica"
    elif broken == "duplicate":
        candidate["identity"]["official_alternatives"].append(deepcopy(record))
    elif broken == "unretained":
        originals = []
    elif broken == "fec_id":
        candidate["identity"]["fec_id"] = "H6CA19999"
    assert (fec_ballot_bridge(candidate, filing, originals) is not None) == (broken is None)


def test_undated_reported_age_does_not_invent_birth_or_election_age():
    validate_reported_age({"reported_age": 36, "reference_date": None})
    assert birth_interval({"reported_age": 36, "reference_date": None}) is None
    assert birth_interval({"reported_age": 36, "birth_year": 1990}) == [35, 36]


@pytest.mark.parametrize("age", [True, -1, 126, 36.0, "36"])
def test_undated_reported_age_still_requires_a_valid_literal_age(age):
    with pytest.raises(ValueError, match="Invalid undated reported age"):
        validate_reported_age({"reported_age": age, "reference_date": None})


def test_undated_reported_age_cannot_smuggle_an_invented_birth_interval():
    with pytest.raises(ValueError, match="Invalid reported-age interval"):
        validate_reported_age(
            {
                "reported_age": 36,
                "reference_date": None,
                "birth_date_interval": ["1989-01-01", "1990-12-31"],
            }
        )


def test_directory_parser_preserves_missing_versus_explicit_fields_and_source_labels():
    record = directory_page(
        "23\nSARA JACOBS\nU.S. REPRESENTATIVE, CALIFORNIA, DISTRICT 53\nDemocrat\n"
        "Ethnicity: White/Caucasian\nMilitary Service: None\nEducation:\n"
        "Columbia; Bachelor of Arts (2011)\nRepublican\nOccupation:\nPolicy advisor\nHOUSE"
    )
    assert record["fields"]["Military Service"] == "None"
    assert record["fields"]["Ethnicity"] == "White/Caucasian"
    assert "Religion" not in record["fields"]
    assert record["fields"]["Education"] == "Columbia; Bachelor of Arts (2011)"
    assert "Republican" not in record["fields"]["Education"]


@pytest.mark.parametrize("broken", [None, "state", "district", "party", "term", "surname"])
def test_directory_identity_uses_actual_2021_term_not_current_district(broken):
    record = {
        "printed_name": "SARA JACOBS",
        "state": "CA",
        "district_2021": 53,
        "party_2021": "Democrat",
    }
    person = {
        "name": {"first": "Sara", "last": "Jacobs"},
        "terms": [
            {
                "type": "rep",
                "state": "CA",
                "district": 53,
                "party": "Democrat",
                "start": "2021-01-03",
                "end": "2023-01-03",
            },
            {
                "type": "rep",
                "state": "CA",
                "district": 51,
                "party": "Democrat",
                "start": "2025-01-03",
                "end": "2027-01-03",
            },
        ],
    }
    if broken in {"state", "district", "party"}:
        person["terms"][0][broken] = {"state": "NY", "district": 51, "party": "Republican"}[broken]
    elif broken == "term":
        person["terms"][0]["start"] = "2021-03-01"
    elif broken == "surname":
        person["name"]["last"] = "Jacobson"
    assert matches_directory(record, person) is (broken is None)


def test_retained_birth_month_does_not_invent_birthday():
    claims = retained_reviews()["campaign-219928-bio1"]
    age = next(c for c in claims if c["trait"] == "age")
    assert age["value"] == {"birth_year": 1998, "birth_month": 9}
    assert birth_interval(age["value"]) == [28, 28]
    advisory = next(c for c in claims if c["trait"] == "other_government")
    assert not advisory["v9_review"]["factual_qualified"]
    assert advisory["v9_review"]["analysis_value"] is None


def test_undated_attendance_and_completed_credentials_are_distinct():
    attendance = education("I attended college")
    undated = education("I earned a masters degree", "masters")
    dated = education("I earned a masters degree in 2020", "masters", 2020)
    assert attendance["value"]["completed_credential"] is None
    assert attendance["v9_review"]["analysis_value"] is None
    assert undated["value"]["completed_credential"] == "masters"
    assert undated["v9_review"]["analysis_value"] is None
    assert dated["v9_review"]["analysis_value"] == "masters"
    assert "v8_review" not in dated


def test_pamphlet_age_without_reference_day_is_not_exact_election_age():
    observation = pamphlet_age(57, "Age: 57")
    validate_reported_age_year(observation["value"])
    assert birth_interval(observation["value"]) == [56, 58]
    assert observation["v9_review"]["analysis_value"] is None
    invalid = deepcopy(observation["value"])
    invalid["birth_date_interval"][0] = "1969-01-01"
    with pytest.raises(ValueError, match="conservative"):
        validate_reported_age_year(invalid)


@pytest.mark.parametrize("broken", [None, "full_name", "link", "host", "candidate"])
def test_decillis_alias_requires_both_names_and_direct_same_host_link(broken):
    candidate = {"candidate_id": "220853", "name": "Michael DeCillis"}
    attempt = {"candidate_id": "220853", "url": "https://campaign.example/about"}
    bridge = {"candidate_id": "220853", "url": "https://campaign.example/news"}
    body = b'Michael DeCillis, Mike DeCillis, Nicole Malliotakis <a href="/about">About</a>'
    if broken == "full_name":
        body = body.replace(b"Michael", b"Another")
    elif broken == "link":
        body = body.replace(b"/about", b"/unrelated")
    elif broken == "host":
        bridge["url"] = "https://other.example/news"
    elif broken == "candidate":
        bridge["candidate_id"] = "other"
    result = reviewed_alias_subject(candidate, "About Mike DeCillis", attempt, bridge, body)
    assert result == ("Mike DeCillis" if broken is None else None)


@pytest.mark.parametrize("missing", [None, "Matthew Dunlap", "Old Town", "University of Maine"])
def test_dunlap_alias_requires_official_name_and_biographical_anchors(monkeypatch, missing):
    from which_candidate import characteristics_v9_extract as extraction

    text = "Matthew Dunlap, Matt Dunlap, Old Town, University of Maine"
    if missing:
        text = text.replace(missing, "")
    monkeypatch.setattr(extraction, "source_text", lambda *_: text)
    candidate = {"candidate_id": "220468", "name": "Matthew Dunlap"}
    result = reviewed_alias_subject(
        candidate,
        "Matt Dunlap from Old Town, University of Maine",
        {"candidate_id": "220468"},
        {"candidate_id": "220468"},
        b"official PDF",
    )
    assert result == ("Matt Dunlap" if missing is None else None)


@pytest.mark.parametrize("broken", [None, "domain", "district", "career"])
def test_miller_first_person_bridge_requires_named_questionnaire_and_native_domain(
    monkeypatch, broken
):
    from which_candidate import characteristics_v9_extract as extraction

    evidence = (
        "Brian J. Miller, Eastern Congressional District, Location: Helena, "
        "www. miller4congress.com"
    )
    text = "More about me: Second Congressional District, Patricia Cotter"
    if broken == "domain":
        evidence = evidence.replace("miller4congress.com", "different.example")
    elif broken == "district":
        evidence = evidence.replace("Eastern Congressional District", "Other district")
    elif broken == "career":
        text = text.replace("Patricia Cotter", "Another judge")
    monkeypatch.setattr(extraction, "source_text", lambda *_: evidence)
    candidate = {"candidate_id": "220677", "name": "Brian Miller"}
    result = reviewed_alias_subject(
        candidate,
        text,
        {"candidate_id": "220677", "url": "https://www.miller4congress.com/about"},
        {"candidate_id": "220677"},
        b"questionnaire PDF",
    )
    assert result == ("More about me" if broken is None else None)


@pytest.mark.parametrize(
    ("candidate_id", "full_name", "subject", "markers"),
    [
        ("220661", "Missi Hesketh", "Meet Missi", "Missi was born; teaching for 22 years"),
        ("220833", "Patrick Halpin", "Pat Halpin", "County Legislature; County Executive"),
        (
            "220950",
            "Jen Mazzuckelli",
            "Of the People",
            "My Journey; Ohio's 2nd Congressional District",
        ),
        (
            "220977",
            "Jerrad Christian",
            "My Life Story",
            "join the US Navy; Ohio’s 12th Congressional district",
        ),
    ],
)
@pytest.mark.parametrize("broken", [None, "name", "link", "host", "candidate", "career"])
def test_native_homepage_bridge_requires_direct_link_name_and_subject(
    candidate_id, full_name, subject, markers, broken
):
    candidate = {"candidate_id": candidate_id, "name": full_name}
    attempt = {"candidate_id": candidate_id, "url": "https://campaign.example/about"}
    bridge = {"candidate_id": candidate_id, "url": "https://campaign.example/"}
    body = f'{full_name} for Congress <a href="/about">Biography</a>'.encode()
    text = f"{subject}: {markers}"
    if broken == "name":
        body = body.replace(full_name.encode(), b"Another person")
    elif broken == "link":
        body = body.replace(b"/about", b"/elsewhere")
    elif broken == "host":
        bridge["url"] = "https://other.example/"
    elif broken == "candidate":
        bridge["candidate_id"] = "other"
    elif broken == "career":
        text = subject
    result = reviewed_alias_subject(candidate, text, attempt, bridge, body)
    assert result == (subject if broken is None else None)


@pytest.mark.parametrize(
    "broken", [None, "native_id", "party", "district", "contest", "service", "answer", "incumbent"]
)
def test_walker_control_requires_explicit_personal_negative_and_positive_incumbent(broken):
    candidate = {
        "candidate_id": "220434",
        "name": "Caleb Walker",
        "state": "LA",
        "district": "03",
        "party": "Democratic",
        "contest_id": "LA03",
    }
    incumbent = {
        "candidate_id": "220433",
        "name": "Clay Higgins",
        "contest_id": "LA03",
        "legislative": {"status": "exact_fec_service_crosswalk", "house_incumbent": True},
    }
    report = (
        'Caleb "With a C" Walker (D). Caleb Walker for Congress | Louisiana\'s 3rd District. '
        "I haven't held elected office before. Incumbent candidate; Higgins has represented "
        "the 3rd Congressional District since 2017"
    )
    if broken == "native_id":
        candidate["candidate_id"] = "other"
    elif broken == "party":
        candidate["party"] = "Republican"
    elif broken == "district":
        candidate["district"] = "05"
    elif broken == "contest":
        incumbent["contest_id"] = "LA05"
    elif broken == "service":
        incumbent["legislative"]["house_incumbent"] = None
    elif broken == "answer":
        report = report.replace(
            "I haven't held elected office before", "My first congressional race"
        )
    elif broken == "incumbent":
        report = report.replace("Incumbent candidate; Higgins", "Candidate; Higgins")
    assert walker_bridge(candidate, incumbent, report) is (broken is None)


@pytest.mark.parametrize(
    ("prior", "sworn", "verified", "inapplicable"),
    [
        ("0", "20250103", True, True),
        ("1", "20250103", True, False),
        ("0", "20240103", True, False),
        ("0", "20250103", False, False),
    ],
)
def test_structural_eligibility_requires_explicit_first_congress_evidence(
    prior, sworn, verified, inapplicable
):
    row = {
        "candidate_id": "native",
        "name": "Candidate",
        "trait": "voting_ideology",
        "analysis_eligible": False,
        "factual_qualified": False,
        "status": "unknown",
        "eligibility_reason": "No retained voting record.",
    }
    candidates = [
        {
            "candidate_id": "native",
            "legislative": {
                "bioguide_id": "B000001",
                "status": "exact_fec_service_crosswalk" if verified else "unresolved",
            },
        }
    ]
    inputs = {
        "clerk_members": [
            {
                "native_xml": f"<member><member-info><bioguideID>B000001</bioguideID>"
                f"<prior-congress>{prior}</prior-congress><sworn-date date='{sworn}'/>"
                "</member-info></member>",
                "source": {"id": "pinned-clerk-original"},
            }
        ]
    }
    structural_eligibility([row], candidates, inputs)
    assert (row["status"] == "inapplicable") is inapplicable
    assert not row["analysis_eligible"]
    assert not row["factual_qualified"]


def duplicate_person_fixture():
    candidate = {
        "candidate_id": "221075",
        "contest_id": "SC02",
        "name": "Zyon Khalifa",
        "state": "SC",
        "district": "02",
        "party": "Democratic",
    }
    previous = [
        {
            **candidate,
            "trait": "incumbency",
            "analysis_eligible": False,
            "analysis_value": None,
            "factual_qualified": False,
            "status": "unknown",
            "performance_eligible": True,
        }
    ]
    inputs = {"fec": [], "reviewed_characteristic_observations": []}
    for i, fec_id in enumerate(("H6SC02159", "H6SC02167")):
        inputs["fec"].append(
            {
                "fec_id": fec_id,
                "chamber": "house",
                "election_year": 2026,
                "state": "SC",
                "district": "02",
                "party": "DEM",
                "first": "ZYON DESHON",
                "last": "KHALIFA",
                "name": "KHALIFA, ZYON DESHON",
                "incumbent": False,
            }
        )
        inputs["reviewed_characteristic_observations"].append(
            {
                **candidate,
                "trait": "incumbency",
                "source_id": f"v9-signed-{i}",
                "source_kind": "signed_FEC_statement_of_candidacy",
                "review_status": "fragment_and_identity_reviewed",
                "publication_date": "2026-06-06",
                "receipt": {"sha256": str(i) * 64},
                "identity_support": ["Principal committee", "Same filed address", fec_id],
                "v9_review": {"factual_qualified": False, "analysis_value": None},
                "v9_identity_bridge": {
                    "legal_name": "Khalifa, Zyon, Deshon",
                    "committee": "Principal committee",
                    "filing_address": "Same filed address",
                    "signed_date": "2026-06-06",
                    "fec_id": fec_id,
                    "evidence_role": "identity_only_retained_FEC_classification",
                },
            }
        )
    return candidate, previous, inputs


def test_duplicate_person_review_retains_both_ids_and_is_not_first_trait_evidence():
    candidate, previous, inputs = duplicate_person_fixture()
    reviews = held_review([candidate], previous, [], inputs)
    assert len(reviews) == 1
    assert reviews[0]["retained_fec_ids"] == ["H6SC02159", "H6SC02167"]
    assert reviews[0]["value"] is False
    rows = [
        {
            **previous[0],
            "analysis_eligible": True,
            "analysis_value": False,
            "factual_qualified": True,
            "status": "qualified",
            "eligibility_reason": "Reviewed",
        }
    ]
    first, _, _, _ = acquisition_accounting(
        rows, previous, inputs["reviewed_characteristic_observations"], review_key="v9_review"
    )
    assert not first


@pytest.mark.parametrize(
    "defect",
    [
        "missing_form",
        "different_committee",
        "conflicting_classification",
        "wrong_contest",
        "additional_id",
        "unsupported_literal",
        "duplicate_original",
        "post_election",
    ],
)
def test_duplicate_person_review_rejects_incomplete_or_conflicting_bridges(defect):
    candidate, previous, inputs = duplicate_person_fixture()
    observations = inputs["reviewed_characteristic_observations"]
    if defect == "missing_form":
        observations.pop()
    elif defect == "different_committee":
        observations[1]["v9_identity_bridge"]["committee"] = "Different committee"
    elif defect == "conflicting_classification":
        inputs["fec"][1]["incumbent"] = True
    elif defect == "wrong_contest":
        inputs["fec"][1]["district"] = "03"
    elif defect == "additional_id":
        inputs["fec"].append({**deepcopy(inputs["fec"][0]), "fec_id": "OTHER"})
    elif defect == "unsupported_literal":
        observations[1]["identity_support"] = []
    elif defect == "duplicate_original":
        observations[1]["receipt"] = deepcopy(observations[0]["receipt"])
    elif defect == "post_election":
        for observation in observations:
            observation["v9_identity_bridge"]["signed_date"] = "2026-11-04"
            observation["publication_date"] = "2026-11-04"
    assert not held_review([candidate], previous, [], inputs)


def test_california_parser_preserves_office_labels_and_districts(monkeypatch):
    text = "\n".join(
        f"United States Representative District {i}\n"
        f"Candidate Alpha {i} Democratic\nUnited States Representative\n"
        f"Candidate Beta {i} Republican\nTeacher/Business Owner"
        for i in range(1, 53)
    )
    pages = [SimpleNamespace(extract_text=lambda: text)]
    monkeypatch.setattr(
        "which_candidate.characteristics_v9_extract.PdfReader",
        lambda path: SimpleNamespace(pages=pages),
    )
    rows = california_rows("fixture")
    assert len(rows) == 104
    assert rows[0]["designation"] == "United States Representative"
    assert rows[1]["designation"] == "Teacher/Business Owner"
    assert rows[2]["district"] == "02"
    pages[0] = SimpleNamespace(
        extract_text=lambda: text.replace(
            "Candidate Alpha 1 Democratic\nUnited States Representative\n", ""
        )
    )
    with pytest.raises(ValueError, match="Incomplete"):
        california_rows("fixture")


def test_report_commands_preserve_lines_and_escape_html():
    from which_candidate.characteristics_v9_publication import article

    rendered = article(
        "## Rebuild\n\n```bash\npython -m example \\\n  --name '<unsafe>'\n```\n\nDone."
    )
    assert "<h2>Rebuild</h2>" in rendered
    assert (
        "<pre><code>python -m example \\\n  --name &#x27;&lt;unsafe&gt;&#x27;</code></pre>"
        in rendered
    )
    assert "<p>Done.</p>" in rendered
