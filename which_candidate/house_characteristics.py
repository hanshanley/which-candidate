"""Separately versioned, field-qualified full House characteristics successor."""

import argparse
import csv
import hashlib
import io
import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

import numpy as np
from scipy.stats import f, t

from .house_validation import error_metrics, person_key
from .models import fit_clustered
from .storage import fingerprint, json_bytes, read_rows, write_json, write_rows

VERSION = "house-characteristics-v1"
OUT = f"results/{VERSION}"
SPEC = "docs/HOUSE_CHARACTERISTICS_V1_SPEC.md"
CUTOFF = date(2026, 11, 3)
TRAITS = (
    "age",
    "gender",
    "race",
    "ethnicity",
    "religion",
    "education",
    "profession",
    "prior_elected_office",
    "other_government",
    "military",
    "incumbency",
    "house_service",
    "donor_ideology",
    "voting_ideology",
    "party_unity",
)
STATUSES = ("qualified", "dated_reported", "uncertain", "unknown", "inapplicable")
INCUMBENT_ONLY = {"house_service", "voting_ideology", "party_unity"}
SCALES = {
    "age": 10,
    "house_service": 10,
    "donor_ideology": 0.5,
    "voting_ideology": 0.1,
    "party_unity": 0.05,
}
DEGREES = {
    "A.A.": "associate",
    "A.S.": "associate",
    "A.A.S.": "associate",
    "B.A.": "bachelors",
    "B.S.": "bachelors",
    "B.B.A.": "bachelors",
    "B.F.A.": "bachelors",
    "B.S.E.": "bachelors",
    "B.S.B.A.": "bachelors",
    "M.A.": "masters",
    "M.S.": "masters",
    "M.B.A.": "masters",
    "M.P.A.": "masters",
    "M.P.P.": "masters",
    "M.Ed.": "masters",
    "M.F.A.": "masters",
    "M.S.W.": "masters",
    "J.D.": "doctoral_or_professional",
    "M.D.": "doctoral_or_professional",
    "Ph.D.": "doctoral_or_professional",
    "D.O.": "doctoral_or_professional",
    "D.D.S.": "doctoral_or_professional",
    "Ed.D.": "doctoral_or_professional",
    "A.B.": "bachelors",
    "B.S.N.": "bachelors",
    "B.S.F.S.": "bachelors",
    "M.Phil.": "masters",
    "M.Div.": "masters",
    "M.P.M.": "masters",
    "M.S.N.": "masters",
    "M.P.H.": "masters",
    "M.I.A.": "masters",
    "M.E.M.": "masters",
    "Ed.M.": "masters",
    "Master of Education": "masters",
}
LEVELS = ("associate", "bachelors", "masters", "doctoral_or_professional")
OCCUPATIONS = {
    "legal": r"(?:^|;)\s*(?:(?:assistant|deputy|city|district|public interest|environmental)"
    r"\s+)*(?:U\.S\.\s+)?(?:lawyer|attorney|prosecutor|judge)\b",
    "education": r"\b(?:teacher|professor|educator|school principal|school superintendent)\b",
    "business": r"\b(?:business owner|businessman|businesswoman|entrepreneur|banker|"
    r"business executive|small business owner|real estate broker)\b",
    "healthcare": r"\b(?:physician|surgeon|nurse|dentist|psychologist|pharmacist|"
    r"pediatrician|occupational therapist|medical director)\b",
}


def key(row):
    return row["contest_id"], str(row["candidate_id"])


def service_years(terms):
    """Union actual pre-cutoff House intervals; do not count gaps or overlap twice."""
    intervals = sorted(
        (date.fromisoformat(r["start"]), min(date.fromisoformat(r["end"]), CUTOFF))
        for r in terms
        if r["type"] == "rep" and r["start"] < CUTOFF.isoformat()
    )
    merged = []
    for start, end in intervals:
        if end <= start:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return sum((end - start).days for start, end in merged) / 365.2425


def directory_codes(profile):
    """Propose only closed, source-literal codes for subsequent recorded review."""
    fields = profile["fields"]
    credentials = []
    for clause in fields.get("education", "").split(";"):
        clause = clause.strip()
        for degree, level in DEGREES.items():
            if re.search(
                r"(?<![A-Za-z.])" + re.escape(degree) + r"(?=[,\s])", clause
            ) and not re.search(
                r"\b(?:honorary|honoris|attended|incomplete|candidate)\b", clause, re.I
            ):
                credentials.append({"degree": degree, "level": level, "fragment": clause})
    families = [
        family
        for family, pattern in OCCUPATIONS.items()
        if re.search(pattern, fields.get("professional_history", ""), re.I)
    ]
    return {
        "credentials": credentials,
        "education": max((r["level"] for r in credentials), key=LEVELS.index, default=None),
        "profession": families[0] if len(families) == 1 else None,
        "reported_professional_families": families,
        "employment_relationship": "not_established_by_occupational_family_code",
    }


def sources(root):
    candidates = read_rows(root / "results/house/candidates.jsonl.gz")
    panel = read_rows(root / "results/house-study/candidate-comparisons.jsonl.gz")
    inputs = read_rows(root / "results/house/source-inputs.jsonl.gz")[0]
    return candidates, panel, inputs


def birth_year_interval(literal):
    if not re.fullmatch(r"(?:18|19|20)\d{2}(?:/(?:18|19|20)\d{2})?", literal):
        return None
    years = [int(y) for y in literal.split("/")]
    if max(years) > CUTOFF.year:
        return None
    return [CUTOFF.year - max(years) - 1, CUTOFF.year - min(years)]


def records(root, *, reviewed=False):
    candidates, panel, inputs = sources(root)
    outcomes = {r["contest_id"]: r for r in panel}
    people = {r["id"]["bioguide"]: r for r in inputs["people"]}
    votes = {
        r["bioguide_id"]: r for r in inputs["current_voting_records"] if r["chamber"] == "house"
    }
    decisions_path = root / "data/house-characteristics-review.json"
    decisions = json.loads(decisions_path.read_text()) if reviewed else {"records": []}
    approved = {tuple(r["identity_key"]): r for r in decisions["records"]}
    observation_path = root / "results/house/background-observations.csv"
    observation_receipt = fingerprint(observation_path)
    inherited = defaultdict(list)
    with observation_path.open() as stream:
        for index, row in enumerate(csv.DictReader(stream), start=2):
            inherited[key(row)].append(
                {
                    "field": row["field"],
                    "value": json.loads(row["value"]),
                    "qualification": row["qualification"],
                    "source_kind": row["source_kind"],
                    "observation_date": row["observation_date"] or None,
                    "csv_row": index,
                }
            )
    incoming = {}
    partial_births = {}
    incoming_path = root / "results/members/house-120-seats.csv"
    incoming_receipt = fingerprint(incoming_path)
    with incoming_path.open() as stream:
        for index, row in enumerate(csv.DictReader(stream), start=2):
            if row["candidate_id"]:
                matches = [
                    c
                    for c in candidates
                    if all(
                        c[k] == row[k]
                        for k in ("candidate_id", "name", "state", "district", "party")
                    )
                ]
                if len(matches) != 1:
                    raise ValueError("Unqualified incoming birthday identity")
                incoming[key(matches[0])] = json.loads(row["reviewed_biography_evidence"] or "[]")
                if row["reported_birth_year_literal"]:
                    partial_births[key(matches[0])] = {
                        "birth_year_literal": row["reported_birth_year_literal"],
                        "birth_literal": row["wikipedia_birth_literal"],
                        "age_years_bounds_on_election_day": birth_year_interval(
                            row["reported_birth_year_literal"]
                        ),
                        "url": row["wikipedia_url"],
                        "table": "results/members/house-120-seats.csv",
                        "csv_row": index,
                        "table_receipt": incoming_receipt,
                        "qualification": "Inherited secondary birth report; exact date unqualified.",
                    }
    fields = {
        "education": {"education"},
        "profession": {
            "professional_history",
            "occupation",
            "occupational_background",
            "business_experience",
        },
        "prior_elected_office": {"prior_office", "elected_office_experience"},
        "other_government": {"public_service_experience", "governmental_experience"},
        "military": {"military_service"},
    }
    result = []
    for candidate in candidates:
        outcome = outcomes[candidate["contest_id"]]
        selected = candidate["selected_democratic_analysis_candidate"]
        background, leg = candidate["background"], candidate["legislative"]
        bioguide = leg.get("bioguide_id")
        person = people.get(bioguide)
        incumbent = outcome.get("D_incumbent") if selected else leg.get("house_incumbent")
        profiles = background["official_member_profiles"]
        profile = next(
            (
                r
                for r in profiles
                if r["source_kind"] == "official_congressional_directory"
                and (r["evidence"].get("publication_date") or "9999") < CUTOFF.isoformat()
            ),
            None,
        )
        approval = approved.get(key(candidate))
        codes = None
        if approval:
            if approval["review_status"] != "reviewed":
                raise ValueError("Unreviewed characteristic proposal")
            if (
                not profile
                or approval["profile_sha256"] != hashlib.sha256(json_bytes(profile)).hexdigest()
            ):
                raise ValueError(f"Changed reviewed profile: {key(candidate)}")
            if approval["name"] != candidate["name"] or approval["party"] != candidate["party"]:
                raise ValueError("Reviewed characteristic identity mismatch")
            codes = approval["codes"]
            if codes != directory_codes(profile):
                raise ValueError("Changed reviewed characteristic coding")
        for trait in TRAITS:
            value, literal, evidence = None, None, []
            status, reason = "unknown", "No qualified value in normalized sources."
            if trait in {"age", "gender"}:
                field = "age_at_election" if trait == "age" else "source_recorded_gender"
                value = leg.get(field)
                if value is not None:
                    status = "qualified"
                    literal = person.get("bio", {}) if person else value
                    evidence = [leg["evidence"]]
                    reason = (
                        "Exact birth-date crosswalk; age on 2026-11-03."
                        if trait == "age"
                        else "Literal crosswalk gender, retrospectively retrieved; "
                        "not inferred sex or verified self-identification."
                    )
                elif trait == "age":
                    reported = [
                        p["fields"]["reported_age"]
                        for p in background["official_candidate_profiles"]
                        if p["fields"].get("reported_age")
                    ]
                    if reported:
                        literal, status = reported, "dated_reported"
                        reason = "Reported age without a qualified exact birth date."
                    additional = [
                        p
                        for p in incoming.get(key(candidate), [])
                        if p["fields"].get("date_of_birth")
                    ]
                    if additional:
                        literal, evidence, status = additional, additional, "dated_reported"
                        reason = (
                            "Already-held incoming biography birth claim; secondary reports "
                            "are retained without automatic analytical promotion."
                        )
                        primary = [
                            p for p in additional if p["source_kind"] == "official_house_historian"
                        ]
                        dates = {p["fields"]["date_of_birth"] for p in primary}
                        if len(dates) == 1:
                            birth = date.fromisoformat(next(iter(dates)))
                            value = (
                                CUTOFF.year
                                - birth.year
                                - ((CUTOFF.month, CUTOFF.day) < (birth.month, birth.day))
                            )
                            status, reason = (
                                "qualified",
                                (
                                    "Exact immutable birthday in an already-reviewed official "
                                    "House Historian biography; successor-only field decision."
                                ),
                            )
                        elif len(dates) > 1:
                            status, reason = "uncertain", "Conflicting primary-source birthdays."
                    partial = partial_births.get(key(candidate))
                    if partial:
                        literal = {"birth_claims": literal, "partial_birth_report": partial}
                        evidence.append(partial)
                        if status == "unknown":
                            status, reason = (
                                "dated_reported",
                                "Secondary birth-year report supplies an age interval, not an "
                                "exact birthday or qualified analytical age.",
                            )
            elif trait in {"race", "ethnicity"}:
                observations = [
                    r
                    for r in background["official_historian_observations"]
                    if (r["identity_group"] == "hispanic") == (trait == "ethnicity")
                ]
                if observations:
                    status, literal, evidence = "dated_reported", observations, observations
                    reason = (
                        "Explicit positive third-party Historian classifications only; "
                        "not a complete race/ethnicity response or negative labels."
                    )
            elif trait == "religion":
                observations = [
                    r
                    for r in background["dated_religion_observations"]
                    if r.get("publication_date") and r["publication_date"] < CUTOFF.isoformat()
                ]
                current = [r for r in observations if r.get("election_year") == 2026]
                if observations:
                    literal, evidence, status = observations, observations, "dated_reported"
                    reason = "Historical reported affiliation; not verified current religion."
                categories = {r["religion_category"] for r in current}
                if len(categories) == 1 and "unknown" not in categories:
                    value, status = next(iter(categories)), "qualified"
                    reason = (
                        "2025-01-02 Pew/CQ office-questionnaire snapshot for 119th Congress; "
                        "analytical variable is dated reported affiliation, not current faith."
                    )
                elif len(categories) > 1:
                    status, reason = "uncertain", "Conflicting same-vintage religion categories."
            elif trait in {
                "education",
                "profession",
                "prior_elected_office",
                "other_government",
                "military",
            }:
                field = {
                    "education": "education",
                    "profession": "professional_history",
                    "prior_elected_office": "prior_office",
                    "other_government": "public_service_experience",
                    "military": "military_service",
                }[trait]
                observations = [
                    {
                        "value": p["fields"][field],
                        "evidence": p.get("evidence"),
                        "source_kind": p.get("source_kind"),
                    }
                    for p in [
                        *background["reviewed_candidate_profiles"],
                        *profiles,
                        *background["official_candidate_profiles"],
                    ]
                    if p["fields"].get(field)
                ]
                if trait == "prior_elected_office" and profile:
                    observations.append(
                        {
                            "value": profile["fields"].get("election_history"),
                            "evidence": profile["evidence"],
                            "source_kind": profile["source_kind"],
                        }
                    )
                if observations:
                    literal, evidence, status = observations, observations, "dated_reported"
                    reason = (
                        "Source-reported history retained; no inferred nonservice, "
                        "paid status, elected status or completed attainment."
                    )
                if codes and trait in {"education", "profession"} and codes[trait]:
                    value, status = codes[trait], "qualified"
                    evidence = [profile["evidence"]]
                    literal = {
                        "source_text": profile["fields"].get(field),
                        "reviewed_coding": codes,
                    }
                    reason = (
                        "Reviewed pre-election Directory degree list; highest documented "
                        "completed credential, not guaranteed highest actual attainment."
                        if trait == "education"
                        else "Reviewed single explicit occupational family in pre-election "
                        "Directory career section; not inferred paid employment."
                    )
                if trait == "military":
                    clerk = [
                        p
                        for p in profiles
                        if p["source_kind"] == "official_Clerk_positive_veteran_roster"
                        and (p["evidence"].get("publication_date") or "9999") < CUTOFF.isoformat()
                    ]
                    if clerk:
                        value, status, evidence = True, "qualified", [p["evidence"] for p in clerk]
                        reason = (
                            "Explicit dated official Clerk positive service listing; "
                            "missing candidates are not negative service cases."
                        )
                    elif candidate["name"] == "Lois Frankel" and observations:
                        status, reason = (
                            "uncertain",
                            (
                                "Suspected adjacent-biography military extraction; attribution withheld. "
                                "See data/house-characteristics-rejections.json; no nonservice inferred."
                            ),
                        )
            elif trait == "incumbency":
                if incumbent is not None:
                    value, literal, status = incumbent, incumbent, "qualified"
                    evidence = (
                        outcome.get("feature_evidence", []) if selected else [leg["evidence"]]
                    )
                    reason = "Dated federal service-qualified incumbency; native flag not used."
            elif trait == "house_service":
                if person and incumbent is True:
                    value, status = service_years(person["terms"]), "qualified"
                    literal, evidence = person["terms"], [person["evidence"]]
                    reason = "Union of actual pre-election House intervals; gaps excluded."
                elif incumbent is False:
                    status, reason = "inapplicable", "Incumbent-only House-service comparison."
            elif trait == "donor_ideology":
                donor = candidate["donor"]
                qualified = (
                    outcome.get("donor", {}).get("qualified")
                    if selected
                    else (donor.get("status") == "exact_fec_state_party_unique_person")
                )
                if donor.get("score") is not None:
                    value, literal, evidence = donor["score"], donor, [donor]
                    status = "qualified" if qualified else "dated_reported"
                    reason = (
                        "Exact-ID historical DIME score through 2024; retrospective, "
                        "not 2026 donations, voting ideology or campaign positions."
                    )
            else:
                if incumbent is False:
                    status, reason = (
                        "inapplicable",
                        "Verified nonincumbent; incumbent-record estimand.",
                    )
                elif incumbent is True:
                    record = (
                        leg.get("prior_voting_record")
                        if trait == "voting_ideology"
                        else votes.get(bioguide)
                    )
                    field = "nokken_poole_dim1" if trait == "voting_ideology" else "unity_score"
                    if record and record.get(field) not in (None, ""):
                        value, literal, evidence = float(record[field]), record, [record]
                        status = "qualified"
                        reason = (
                            "118th-Congress Nokken-Poole first dimension, not career NOMINATE."
                            if trait == "voting_ideology"
                            else "119th-Congress cast-only unity votes before election; "
                            "denominator, with-party count and last date retained."
                        )
                    elif (
                        trait == "voting_ideology"
                        and person
                        and not any(
                            term["type"] == "rep"
                            and term["start"] < "2025-01-03"
                            and term["end"] > "2023-01-03"
                            for term in person["terms"]
                        )
                    ):
                        status, reason = "inapplicable", "No 118th-Congress House service."
            new_observations = [
                r
                for r in inputs.get("reviewed_characteristic_observations", [])
                if key(r) == key(candidate) and r["trait"] == trait
            ]
            if new_observations:
                literal = {"existing": literal, "additional": new_observations}
                evidence = [*evidence, *new_observations]
                status = status if status == "qualified" else "dated_reported"
                reason += (
                    " Additional exact-context reviewed source; its qualification is retained."
                )
                if trait == "age":
                    birthdays = {r["value"] for r in new_observations}
                    if person and person.get("bio", {}).get("birthday"):
                        birthdays.add(person["bio"]["birthday"])
                    birthdays.update(
                        p["fields"]["date_of_birth"]
                        for p in incoming.get(key(candidate), [])
                        if p["source_kind"] == "official_house_historian"
                        and p["fields"].get("date_of_birth")
                    )
                    if len(birthdays) == 1:
                        birth = date.fromisoformat(next(iter(birthdays)))
                        value = (
                            CUTOFF.year
                            - birth.year
                            - ((CUTOFF.month, CUTOFF.day) < (birth.month, birth.day))
                        )
                        status, reason = (
                            "qualified",
                            "Reviewed exact historical birthday; Election Day age.",
                        )
                    else:
                        status, value, reason = "uncertain", None, "Conflicting exact birthdays."
            retained = [
                o for o in inherited[key(candidate)] if o["field"] in fields.get(trait, set())
            ]
            if retained:
                literal = {"reviewed_or_reported": literal, "inherited_source_values": retained}
                evidence.append(
                    {
                        "observation_table": "results/house/background-observations.csv",
                        "table_sha256": observation_receipt["sha256"],
                        "csv_rows": [o["csv_row"] for o in retained],
                        "qualification": "Inherited observations are not silently recoded as facts.",
                    }
                )
                if status == "unknown":
                    status, reason = (
                        "uncertain",
                        (
                            "Existing extracted source values retained; candidate subject, field "
                            "meaning, timing or coding needs review. Not a qualified trait value."
                        ),
                    )
            result.append(
                {
                    **{
                        k: candidate[k]
                        for k in (
                            "candidate_id",
                            "contest_id",
                            "name",
                            "state",
                            "district",
                            "party",
                        )
                    },
                    "trait": trait,
                    "status": status,
                    "value": value,
                    "source_recorded_value": literal,
                    "uncertainty": {
                        "status": status,
                        "age_years_interval": (
                            [value, value]
                            if status == "qualified"
                            else partial_births.get(key(candidate), {}).get(
                                "age_years_bounds_on_election_day"
                            )
                        )
                        if trait == "age"
                        else None,
                    },
                    "evidence": evidence,
                    "review_status": "explicit_successor_rule"
                    if status == "qualified"
                    else "retained_without_analytical_promotion",
                    "eligibility_reason": reason,
                    "field_eligible": status == "qualified",
                    "performance_eligible": bool(selected and outcome["eligible"]),
                    "district_presidential_D_share_pct": outcome.get(
                        "presidential_D_two_party_share_pct"
                    ),
                    "performance_gap_share_pp": outcome.get("descriptive_gap_share_pp")
                    if selected and outcome["eligible"]
                    else None,
                    "D_incumbency_control": outcome["D_incumbent"] if selected else None,
                    "R_incumbency_control": outcome["R_incumbent"] if selected else None,
                    "retrospective_acquisition": True,
                    "prospective_model_eligible": False,
                    "cutoff": CUTOFF.isoformat(),
                }
            )
    return result, candidates, panel


def coverage(rows):
    result = []
    for cohort, selected in (
        ("all_named", rows),
        ("democrats", [r for r in rows if r["party"] == "Democratic"]),
        ("eligible_democrats", [r for r in rows if r["performance_eligible"]]),
    ):
        for trait in TRAITS:
            subset = [r for r in selected if r["trait"] == trait]
            counts = Counter(r["status"] for r in subset)
            result.append(
                {
                    "cohort": cohort,
                    "trait": trait,
                    "candidates": len(subset),
                    **{s: counts[s] for s in STATUSES},
                }
            )
    return result


def write_csv(path, rows):
    columns = list(dict.fromkeys(k for r in rows for k in r))
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(
        {
            k: json.dumps(v, sort_keys=True) if isinstance(v, (list, dict)) else v
            for k, v in r.items()
        }
        for r in rows
    )
    path.write_text(stream.getvalue())


def audit(root):
    output = root / OUT
    output.mkdir(parents=True, exist_ok=True)
    if (output / "initial-audit.json").exists():
        return json.loads((output / "initial-audit.json").read_text())
    rows, _, _ = records(root)
    write_csv(output / "initial-coverage.csv", coverage(rows))
    write_json(
        output / "initial-audit.json",
        {
            "version": VERSION,
            "before_new_review": True,
            "inputs": {
                name: fingerprint(root / name)
                for name in (
                    "results/house/candidates.jsonl.gz",
                    "results/house/source-inputs.jsonl.gz",
                    "results/house-study/candidate-comparisons.jsonl.gz",
                )
            },
            "coverage": coverage(rows),
        },
    )


def proposal(root):
    candidates, _, _ = sources(root)
    result = []
    for candidate in candidates:
        for profile in candidate["background"]["official_member_profiles"]:
            if profile["source_kind"] != "official_congressional_directory":
                continue
            result.append(
                {
                    "identity_key": list(key(candidate)),
                    "name": candidate["name"],
                    "party": candidate["party"],
                    "profile_sha256": hashlib.sha256(json_bytes(profile)).hexdigest(),
                    "codes": directory_codes(profile),
                    "education_literal": profile["fields"].get("education"),
                    "profession_literal": profile["fields"].get("professional_history"),
                    "review_status": "proposal_requires_review",
                }
            )
    return result


def designs(rows, trait, levels=None):
    lean = np.array([(r["presidential_D_two_party_share_pct"] - 50) / 10 for r in rows])
    cols, names = [np.ones(len(rows)), lean, lean**2], ["intercept", "lean_10pp", "lean_squared"]
    if trait != "incumbency":
        for name in ("D_incumbent", "R_incumbent"):
            values = np.array([int(r[name]) for r in rows])
            if len(values) and np.ptp(values):
                cols.append(values)
                names.append(name)
    base = np.column_stack(cols)
    focal, terms = [], []
    if trait == "incumbency":
        for name in ("D_incumbent", "R_incumbent"):
            focal.append([int(r[name]) for r in rows])
            terms.append(name)
    elif trait in SCALES and levels is None:
        values = [r["_value"] for r in rows]
        focal.append(
            [
                (1 - v) / SCALES[trait] if trait == "party_unity" else v / SCALES[trait]
                for v in values
            ]
        )
        terms.append("defection_5pp" if trait == "party_unity" else trait)
    else:
        for level in levels[1:]:
            focal.append([int(r["_value"] == level) for r in rows])
            terms.append(f"{trait}:{level}_vs_{levels[0]}")
    return base, np.column_stack([*cols, *focal]), names, terms


def fit(rows, trait, levels):
    base, augmented, names, focal = designs(rows, trait, levels)
    y = np.array([r["descriptive_gap_share_pp"] for r in rows])
    states = sorted({r["state"] for r in rows})
    if len(rows) < 30 or len(states) < 10 or not focal:
        return {
            "status": "insufficient_support",
            "n": len(rows),
            "state_clusters": len(states),
            "terms": names + focal,
        }
    result = fit_clustered(augmented, y, [r["state"] for r in rows])
    result["terms"], result["focal_terms"] = names + focal, focal
    if result["status"] == "estimated":
        q = len(focal)
        beta = np.array(result["coefficients"][-q:])
        cov = np.array(result["covariance"])[-q:, -q:]
        if np.linalg.matrix_rank(cov) < q:
            result["status"] = "singular_focal_covariance"
        else:
            statistic = max(0.0, float(beta @ np.linalg.solve(cov, beta) / q))
            result["omnibus_pvalue"] = float(f.sf(statistic, q, len(states) - 1))
    return result


def paired(rows, trait, levels):
    base, augmented, names, focal = designs(rows, trait, levels)
    y = np.array([r["descriptive_gap_share_pp"] for r in rows])
    predictions, folds = [], []
    for state in sorted({r["state"] for r in rows}):
        test = [i for i, r in enumerate(rows) if r["state"] == state]
        people = {person_key(rows[i]) for i in test}
        train = [
            i for i, r in enumerate(rows) if r["state"] != state and person_key(r) not in people
        ]
        supported = (
            len(train) > augmented.shape[1] + 3
            and len({rows[i]["state"] for i in train}) >= 8
            and all(
                np.linalg.matrix_rank(x[train]) == x.shape[1] and np.linalg.cond(x[train]) < 1e10
                for x in (base, augmented)
            )
        )
        folds.append(
            {
                "trait": trait,
                "held_out_state": state,
                "status": "estimated" if supported else "failed",
                "training_ids": [rows[i]["D_candidate_election_id"] for i in train],
                "test_ids": [rows[i]["D_candidate_election_id"] for i in test],
                "training_people": sorted({person_key(rows[i]) for i in train}),
                "test_people": sorted(people),
                "baseline_terms": names,
                "augmented_terms": names + focal,
            }
        )
        if not supported:
            continue
        betas = [np.linalg.lstsq(x[train], y[train], rcond=None)[0] for x in (base, augmented)]
        for i in test:
            errors = [float(y[i] - x[i] @ b) for x, b in zip((base, augmented), betas)]
            predictions.append(
                {
                    "trait": trait,
                    "candidate_election_id": rows[i]["D_candidate_election_id"],
                    "contest_id": rows[i]["contest_id"],
                    "state": state,
                    "name": rows[i]["D_name"],
                    "baseline_error_share_pp": errors[0],
                    "augmented_error_share_pp": errors[1],
                }
            )
    return predictions, folds


def analyze(
    dataset,
    panel,
    *,
    predictor=paired,
    prediction_selector=None,
    categorical_traits=(),
    strict_education=True,
):
    by_key = {(r["contest_id"], r["trait"]): r for r in dataset if r["performance_eligible"]}
    fits, terms, predictions, folds, deletions, selections, sensitivities = (
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    )
    for trait in TRAITS:
        rows, decisions = [], []
        for outcome in panel:
            if not outcome["D_candidate_election_id"]:
                continue
            observation = by_key.get((outcome["contest_id"], trait))
            reason = None
            if not outcome["eligible"]:
                reason = "outcome_hold"
            elif observation is None or not observation["field_eligible"]:
                reason = observation["status"] if observation else "no_selected_trait"
            elif outcome["D_incumbent"] is None or outcome["R_incumbent"] is None:
                reason = "unknown_D_or_R_incumbency_control"
            elif trait in INCUMBENT_ONLY and (
                outcome["D_incumbent"] is not True
                or outcome.get("service_verified_incumbent") is not True
            ):
                reason = "not_verified_D_incumbent"
            if reason is None:
                rows.append({**outcome, "_value": observation["value"]})
            decisions.append(
                {
                    "trait": trait,
                    "contest_id": outcome["contest_id"],
                    "candidate_election_id": outcome["D_candidate_election_id"],
                    "state": outcome["state"],
                    "name": outcome["D_name"],
                    "D_incumbent": outcome["D_incumbent"],
                    "lean": outcome.get("presidential_D_two_party_share_pct"),
                    "provisional_D_leads": (
                        outcome["D_votes"] > outcome["R_votes"]
                        if outcome.get("D_votes") is not None and outcome.get("R_votes") is not None
                        else None
                    ),
                    "reason": reason,
                    "included": reason is None,
                }
            )
        levels = None
        if (trait not in SCALES or trait in categorical_traits) and trait != "incumbency":
            groups = defaultdict(list)
            for row in rows:
                groups[row["_value"]].append(row)
            levels = sorted(
                level
                for level, group in groups.items()
                if len(group) >= 10 and len({r["state"] for r in group}) >= 3
            )
            rare = {r["D_candidate_election_id"] for r in rows if r["_value"] not in levels}
            rows = [r for r in rows if r["_value"] in levels]
            for decision in decisions:
                if decision["candidate_election_id"] in rare:
                    decision.update(included=False, reason="sparse_category")
            if len(levels) < 2:
                rows = []
                for decision in decisions:
                    if decision["included"]:
                        decision.update(
                            included=False, reason="fewer_than_two_supported_categories"
                        )
        selections.extend(decisions)
        result = fit(rows, trait, levels)
        result.update(
            trait=trait,
            primary_family_size=len(TRAITS),
            holm_pvalue=1.0,
            candidate_election_ids=[r["D_candidate_election_id"] for r in rows],
            states=sorted({r["state"] for r in rows}),
            reference=levels[0] if levels else None,
            exclusion_counts=dict(Counter(r["reason"] for r in decisions if not r["included"])),
        )
        if result["status"] != "estimated":
            result["unavailable_reason"] = (
                "No qualified complete contrast, sufficient categories or minimum sample/state support. "
                "Positive-only histories/identities do not establish negative reference values."
            )
            fits.append(result)
            continue
        for i, name in enumerate(result["terms"]):
            terms.append(
                {
                    "trait": trait,
                    "term": name,
                    "focal": name in result["focal_terms"],
                    "estimate_share_pp": result["coefficients"][i],
                    "ci_low": result["ci_low"][i],
                    "ci_high": result["ci_high"][i],
                    "pvalue": result["pvalues"][i],
                    "n": len(rows),
                    "state_clusters": result["state_clusters"],
                }
            )
        prediction_rows = prediction_selector(rows, trait) if prediction_selector else rows
        prediction_states = sorted({r["state"] for r in prediction_rows})
        pred, model_folds = predictor(prediction_rows, trait, levels)
        predictions.extend(pred)
        folds.extend(model_folds)
        metrics = error_metrics(pred)
        replicates = []
        for state in prediction_states:
            reduced = [r for r in prediction_rows if r["state"] != state]
            deleted, _ = predictor(reduced, trait, levels)
            complete = len(deleted) == len(reduced)
            gain = error_metrics(deleted)["MAE_gain_share_pp"] if complete else None
            deletions.append(
                {
                    "trait": trait,
                    "deleted_state": state,
                    "remaining_candidates": len(reduced),
                    "complete": complete,
                    "MAE_gain_share_pp": gain,
                }
            )
            if complete:
                replicates.append(gain)
        complete = (
            bool(prediction_rows)
            and len(pred) == len(prediction_rows)
            and len(replicates) == len(prediction_states)
        )
        width = None
        if complete:
            g = len(replicates)
            se = np.sqrt((g - 1) / g * np.sum((replicates - np.mean(replicates)) ** 2))
            width = float(t.ppf(0.975, g - 1) * se)
        result["prediction"] = {
            **metrics,
            "paired_candidates": len(pred),
            "complete": complete,
            "gain_ci_low": metrics["MAE_gain_share_pp"] - width if width is not None else None,
            "gain_ci_high": metrics["MAE_gain_share_pp"] + width if width is not None else None,
            "interval_status": "full_pipeline_state_jackknife" if complete else "diagnostic_only",
        }
        if prediction_selector:
            result["prediction"].update(
                population_candidates=len(prediction_rows),
                population_states=len(prediction_states),
                population_ids=[r["D_candidate_election_id"] for r in prediction_rows],
                excluded_ids=sorted(
                    {r["D_candidate_election_id"] for r in rows}
                    - {r["D_candidate_election_id"] for r in prediction_rows}
                ),
                population_rule="joint_D_R_incumbency_stratum_in_at_least_three_states",
            )
        competitive = [r for r in rows if 40 <= r["presidential_D_two_party_share_pct"] <= 60]
        sensitivities.append(
            {"trait": trait, "variant": "competitive_40_60", **fit(competitive, trait, levels)}
        )
        if trait in {"age", "gender", "religion", "education", "profession", "donor_ideology"}:
            sensitivities.append(
                {
                    "trait": trait,
                    "variant": "verified_incumbents_only",
                    **fit(
                        [
                            r
                            for r in rows
                            if r.get("service_verified_incumbent") is True
                            and r["D_incumbent"] is True
                        ],
                        trait,
                        levels,
                    ),
                }
            )
        if trait == "education" and strict_education:
            # Source-list degree ordering is not proof of total lifetime attainment.
            strict = [
                r
                for r in rows
                if len(
                    {
                        c["level"]
                        for c in by_key[(r["contest_id"], trait)]["source_recorded_value"][
                            "reviewed_or_reported"
                        ]["reviewed_coding"]["credentials"]
                    }
                )
                == 1
            ]
            sensitivities.append(
                {
                    "trait": trait,
                    "variant": "single_reported_credential_level",
                    **fit(strict, trait, levels),
                }
            )
        for state in result["states"]:
            sensitivities.append(
                {
                    "trait": trait,
                    "variant": "delete_state_association",
                    "deleted_state": state,
                    **fit([r for r in rows if r["state"] != state], trait, levels),
                }
            )
        fits.append(result)
    previous = 0.0
    for rank, result in enumerate(sorted(fits, key=lambda r: r.get("omnibus_pvalue", 1.0))):
        previous = max(previous, min(1.0, result.get("omnibus_pvalue", 1.0) * (len(TRAITS) - rank)))
        result["holm_pvalue"] = previous
    return fits, terms, predictions, folds, deletions, selections, sensitivities


def source_catalog(root):
    """Resolve row-level source identifiers without requiring historical raw files."""
    catalog = {}

    def visit(value):
        if isinstance(value, dict):
            if value.get("sha256") and (value.get("url") or value.get("origin_url")):
                url = value.get("url") or value["origin_url"]
                receipt = {
                    k: value[k]
                    for k in (
                        "id",
                        "url",
                        "origin_url",
                        "resolved_url",
                        "sha256",
                        "bytes",
                        "retrieved_at",
                        "acquired_at",
                        "publication_date",
                        "kind",
                        "retrieval_method",
                        "original_bytes_acquired",
                        "original_request_failure",
                    )
                    if k in value
                }
                receipt["url"] = url
                receipt["retrieval_date_status"] = (
                    "recorded"
                    if receipt.get("retrieved_at") or receipt.get("acquired_at")
                    else "unknown_in_inherited_receipt_not_reconstructed"
                )
                previous = catalog.get((url, value["sha256"]), {})
                ids = {*previous.get("source_ids", [])}
                ids.update(value[k] for k in ("id", "source_id") if isinstance(value.get(k), str))
                receipt = {**previous, **receipt}
                receipt["source_ids"] = sorted(ids)
                receipt["retrieval_date_status"] = (
                    "recorded"
                    if receipt.get("retrieved_at") or receipt.get("acquired_at")
                    else "unknown_in_inherited_receipt_not_reconstructed"
                )
                catalog[(url, value["sha256"])] = receipt
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    for path in sorted((root / "data").glob("*.json")):
        visit(json.loads(path.read_text()))
    visit(read_rows(root / "results/house/source-inputs.jsonl.gz")[0])
    return [catalog[k] for k in sorted(catalog)]


def build(root):
    root = Path(root)
    output = root / OUT
    if not (output / "initial-audit.json").exists():
        raise ValueError("Run --audit before review and fitting")
    if not (root / SPEC).exists():
        raise ValueError("Missing pre-fit specification")
    rows, candidates, panel = records(root, reviewed=True)
    write_rows(output / "candidate-traits.jsonl.gz", rows)
    write_csv(output / "candidate-traits.csv", rows)
    write_csv(output / "coverage.csv", coverage(rows))
    write_json(output / "source-receipts.json", source_catalog(root))
    results = analyze(rows, panel)
    names = ("fits", "terms", "predictions", "folds", "state-deletions", "selection", "sensitivity")
    for name, result in zip(names, results):
        write_rows(output / f"{name}.jsonl.gz", result)
        if name != "folds":
            write_csv(output / f"{name}.csv", result)
    fits = results[0]
    selection_summary = []
    for trait in TRAITS:
        for included in (True, False):
            subset = [r for r in results[5] if r["trait"] == trait and r["included"] == included]
            leans = [r["lean"] for r in subset if r["lean"] is not None]
            selection_summary.append(
                {
                    "trait": trait,
                    "included": included,
                    "candidates": len(subset),
                    "states": len({r["state"] for r in subset}),
                    "known_D_incumbents": sum(r["D_incumbent"] is True for r in subset),
                    "unknown_D_incumbency": sum(r["D_incumbent"] is None for r in subset),
                    "provisional_D_leads": sum(r["provisional_D_leads"] is True for r in subset),
                    "mean_presidential_D_share": float(np.mean(leans)) if leans else None,
                    "lean_bands": dict(
                        Counter(
                            "below_40" if v < 40 else "40_to_60" if v <= 60 else "above_60"
                            for v in leans
                        )
                    ),
                    "reasons": dict(Counter(r["reason"] for r in subset if r["reason"])),
                }
            )
    write_csv(output / "selection-summary.csv", selection_summary)
    summary = {
        "version": VERSION,
        "candidate_records": len(candidates),
        "democrats": sum(r["party"] == "Democratic" for r in candidates),
        "eligible_democrats": sum(r["eligible"] for r in panel),
        "trait_fields": len(TRAITS),
        "primary_family_size": len(TRAITS),
        "supported_blocks": [r["trait"] for r in fits if r["status"] == "estimated"],
        "unavailable_blocks": [r["trait"] for r in fits if r["status"] != "estimated"],
        "holm_below_005": [r["trait"] for r in fits if r["holm_pvalue"] < 0.05],
        "interpretation": "Exploratory retrospective associations, not causal nominee effects.",
        "coverage": coverage(rows),
    }
    write_json(output / "summary.json", summary)
    from .characteristics_publication import build as publish_characteristics

    publish_characteristics(root)
    write_json(
        output / "manifest.json",
        {
            "version": VERSION,
            "inputs": {
                name: fingerprint(root / name)
                for name in (
                    SPEC,
                    "data/house-characteristics-review.json",
                    "results/house/candidates.jsonl.gz",
                    "results/house/source-inputs.jsonl.gz",
                    "results/house-study/candidate-comparisons.jsonl.gz",
                    "results/house/background-observations.csv",
                    "results/members/house-120-seats.csv",
                    "data/house-characteristics-research.json",
                    "data/house-characteristics-receipts.json",
                    "data/house-characteristics-rejections.json",
                    "data/house-characteristics-baseline.json",
                )
            },
            "files": {
                p.name: fingerprint(p)
                for p in sorted(output.iterdir())
                if p.is_file() and p.name != "manifest.json"
            },
        },
    )
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--propose", action="store_true")
    args = parser.parse_args()
    if args.audit:
        audit(args.root)
    elif args.propose:
        print(json.dumps(proposal(args.root), indent=2))
    else:
        print(json.dumps(build(args.root), indent=2))
