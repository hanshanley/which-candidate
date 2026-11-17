"""Audited historical-person joins and literal, row-scoped V7 registration."""

import csv
import io
import json
import re
import shutil
import unicodedata
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path

from .benchmarks import STATE_NAMES
from .characteristics_research import normalized, reviewed_claims, source_text
from .storage import fingerprint, read_rows, write_json

IDENTITY = ("candidate_id", "contest_id", "name", "state", "district", "party")
SPECS = {
    "lublin-house-2023": "Replication US House.csv",
    "lublin-state-2023": "Replication State Leg.csv",
}
COLUMNS = [
    "state",
    "eyear",
    "body",
    "district",
    "win_name",
    "party",
    "race",
    "white",
    "black",
    "latino",
    "asian",
    "ethnicity",
]


def name_key(value):
    value = "".join(c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c))
    if "," in value:
        last, first = value.split(",", 1)
        value = f"{first} {last}"
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def member_names(member):
    name = member["name"]
    first, last = name["first"], name["last"]
    return {
        name_key(value)
        for value in (
            f"{first} {last}",
            f"{first} {name.get('middle', '')} {last}",
            f"{name.get('nickname', first)} {last}",
            name.get("official_full", f"{first} {last}"),
        )
    }


def district_key(value):
    return str(int(value)) if str(value).isdigit() else "0" if value == "AL" else str(value)


def dated_house_link(member, record):
    when = date(int(record["eyear"]) + 1, 1, 4).isoformat()
    return name_key(record["win_name"]) in member_names(member) and any(
        t["type"] == "rep"
        and t["state"] == record["state"].upper()
        and district_key(t["district"]) == district_key(record["district"])
        and t["start"] <= when < t["end"]
        for t in member["terms"]
    )


def claim(trait, value, fragment, analysis=None, *, reason):
    return {
        "trait": trait,
        "value": value,
        "fragment": fragment,
        "qualification": reason,
        "v7_review": {
            "factual_qualified": True,
            "analysis_value": analysis,
            "reason": reason,
            "prospective_availability": "not_established_by_retrospective_retrieval",
        },
    }


def classification_claims(records, fragment):
    races = {r["race"].casefold().strip() for r in records if r["race"].strip()}
    indicators = {r["latino"] for r in records if r["latino"]}
    race = next(iter(races)) if len(races) == 1 else None
    binary = race.title() if race in {"white", "black"} else None
    claims = (
        [
            claim(
                "race",
                [records[-1]["race"]],
                fragment,
                binary,
                reason="Literal historical Lublin winner classification; independently linked person. "
                "Only concordant unmixed Black/White records enter the restricted comparison; "
                "not universal 2026 self-identification.",
            )
        ]
        if records[-1]["race"].strip()
        else []
    )
    if records[-1]["latino"] in {"0", "1"}:
        indicator = int(records[-1]["latino"])
        claims.append(
            claim(
                "ethnicity",
                {"source_latino_indicator": indicator, "detailed_origin": records[-1]["ethnicity"]},
                fragment,
                f"historical_Latino_{indicator}" if len(indicators) == 1 else None,
                reason="Explicit author-coded Latino 0/1 indicator, not inferred from race; "
                "historical winner population, not current universal ethnic self-identification. "
                "The detailed-origin column is preserved separately.",
            )
        )
    elif records[-1]["ethnicity"].strip():
        claims.append(
            claim(
                "ethnicity",
                {
                    "source_latino_value": records[-1]["latino"],
                    "detailed_origin": records[-1]["ethnicity"],
                },
                fragment,
                reason="Historical source-recorded origins/indicators preserved; missing or "
                "discordant indicator values do not supply a binary comparison.",
            )
        )
    return claims


def retained_members(root):
    ledger = json.loads((root / "data/research-sources.json").read_text())
    members = {}
    for source in ledger["sources"]:
        if source["id"] in {"legislators_current", "legislators_historical"}:
            for member in json.loads((root / "data" / source["path"]).read_text()):
                members[member["id"]["bioguide"]] = member
    return members


def stable_member(candidate, members):
    bioguide = candidate["legislative"].get("bioguide_id")
    member = members.get(bioguide)
    fec = candidate["identity"].get("fec_id")
    if member and fec and fec in member["id"].get("fec", []):
        return member
    return None


def state_link(candidate, observations):
    fragments = []
    for observation in observations:
        if (
            observation["candidate_id"] == candidate["candidate_id"]
            and observation["trait"] == "prior_elected_office"
        ):
            fragments.append((str(observation["value"]), observation["source_id"]))
    for profile in candidate["background"].get("reviewed_candidate_profiles", []):
        for field in ("prior_elected_office", "political_experience", "professional_history"):
            support = profile.get("support", {}).get(field, [])
            support = [support] if isinstance(support, str) else support
            for fragment in support:
                fragments.append((fragment, profile["evidence"].get("source_id", "")))
    state = STATE_NAMES.get(candidate["state"], "").casefold()
    if state:
        pattern = rf"\b(?:state (?:legislat|senat|representat)|{state} (?:state |general )?(?:house|senate|assembly|legislat))"
        for fragment, source in fragments:
            if re.search(pattern, normalized(fragment)):
                return {"fragment": fragment, "retained_source_id": source}
    return None


def archive_records(path, member):
    with zipfile.ZipFile(path) as archive:
        rows = list(csv.DictReader(io.StringIO(archive.read(member).decode("utf-8-sig"))))
    return [(number, row) for number, row in enumerate(rows, 2)]


def register(root):
    root = Path(root)
    work = root / "artifacts/characteristics-v7"
    attempts = json.loads((work / "retrievals.json").read_text())
    acquired = {r["id"]: r for r in attempts if r["status"] == "acquired"}
    candidates = read_rows(root / "results/house/candidates.jsonl.gz")
    inputs = read_rows(root / "results/house/source-inputs.jsonl.gz")[0]
    historical = [
        r
        for r in inputs["reviewed_characteristic_observations"]
        if not r["source_id"].startswith("v7-")
    ]
    members = retained_members(root)
    journal_path = root / "data/house-characteristics-research.json"
    receipts_path = root / "data/house-characteristics-receipts.json"
    journal = json.loads(journal_path.read_text())
    receipts = json.loads(receipts_path.read_text())
    sources, documents, decisions = [], {}, []
    cache = root / "data/raw/house-characteristics-v1"

    def add(key, candidate, claims, *, scope=None, identity=None, details=None, text=None):
        if not claims:
            return
        attempt = acquired[key]
        document = f"v7-{key}"
        source = {
            **{k: candidate[k] for k in IDENTITY},
            "id": f"{document}-{candidate['candidate_id']}",
            "document_id": document,
            "kind": "historical_source_classified_winner"
            if key in SPECS
            else "dated_original_biography",
            "url": attempt["url"],
            "publication_date": None,
            "publication_date_precision": "unspecified",
            "edition_or_date_note": "Archive URL upload month 2023/04 is not an exact publication "
            "date; each winner record supplies its factual election year."
            if key in SPECS
            else "See dated original and field-level timing qualification.",
            "text_scope": scope or {},
            "identity_qualification": identity,
            "claims": claims,
            **(details or {}),
        }
        receipt = {
            "id": source["id"],
            "url": attempt["url"],
            "resolved_url": attempt["url"],
            "retrieved_at": attempt["retrieved_at"],
            "retrieval_method": attempt["retrieval_method"],
            "original_bytes_acquired": True,
            **{k: attempt[k] for k in ("bytes", "sha256")},
        }
        if text is None:
            text = source_text((work / key).read_bytes(), source)
        reviewed_claims(source, receipt, text)
        sources.append(source)
        documents[document] = {"id": document, **{k: v for k, v in receipt.items() if k != "id"}}
        receipts["sources"] = [r for r in receipts["sources"] if r["id"] != source["id"]]
        receipts["sources"].append({**receipt, "status": "acquired_pending_review"})

    for key, member_name in SPECS.items():
        records = archive_records(work / key, member_name)
        by_name = defaultdict(list)
        for number, record in records:
            by_name[(record["state"].upper(), name_key(record["win_name"]))].append(
                (number, record)
            )
        for candidate in candidates:
            member = stable_member(candidate, members)
            aliases = member_names(member) if member else {name_key(candidate["name"])}
            matched = {}
            for alias in aliases:
                for number, record in by_name.get((candidate["state"], alias), []):
                    matched[number] = record
            if not matched:
                continue
            independent = None
            if key == "lublin-house-2023" and member:
                matched = {n: r for n, r in matched.items() if dated_house_link(member, r)}
                independent = {
                    "bioguide": member["id"]["bioguide"],
                    "native_fec_id": candidate["identity"]["fec_id"],
                    "rule": "FEC/Bioguide crosswalk plus full name and state/district dated House term",
                }
            elif key == "lublin-state-2023":
                independent = state_link(candidate, historical)
            accepted = bool(
                matched and independent and candidate["party"] in {"Democratic", "Republican"}
            )
            decisions.append(
                {
                    **{k: candidate[k] for k in IDENTITY},
                    "source_family": key,
                    "accepted": accepted,
                    "independent_link": independent,
                    "matched_csv_rows": sorted(matched),
                    "reason": "Independent person/service bridge"
                    if accepted
                    else "Full-name/state discovery alone or unsupported native-party identity; not qualified",
                }
            )
            if not accepted:
                continue
            number, row = max(matched.items(), key=lambda item: int(item[1]["eyear"]))
            literal = " | ".join(f"{k}={' '.join(row[k].split())}" for k in COLUMNS)
            ordered = [
                r for _, r in sorted(matched.items(), key=lambda item: int(item[1]["eyear"]))
            ]
            claims = classification_claims(ordered, literal)
            category = "federal" if key == "lublin-house-2023" else "state"
            claims.append(
                claim(
                    "prior_elected_office",
                    {
                        "history": f"{row['state'].upper()} {row['body']} election winner {row['eyear']}",
                        "supported_categories": [category],
                        "time_reference": "before_2026-11-03",
                        "not_equivalent_to": "office_before_first_House_entry",
                    },
                    literal,
                    reason="Explicit dated historical elected winner, before the 2026 election; "
                    "not proof of no other office and not an office-before-first-House-entry variable.",
                )
            )
            add(
                key,
                candidate,
                claims,
                scope={"csv_row": number},
                identity=json.dumps(independent, sort_keys=True),
                details={
                    "format": "zip_csv",
                    "member": member_name,
                    "columns": COLUMNS,
                    "identity_fragment": f"win_name={row['win_name']}",
                    "matched_historical_records": [
                        {
                            "csv_row": n,
                            "year": r["eyear"],
                            "race": r["race"],
                            "latino": r["latino"],
                            "ethnicity": r["ethnicity"],
                        }
                        for n, r in sorted(matched.items())
                    ],
                },
                text=literal,
            )

    by_id = {c["candidate_id"]: c for c in candidates}
    key = "umn-gronli-2023"
    body = source_text((work / key).read_bytes(), {})
    add(
        key,
        by_id["221167"],
        [
            claim(
                "education",
                "bachelors",
                "After graduating from the University of Minnesota in 1996",
                "bachelors",
                reason="Dated university interview explicitly says graduated; BS 1996 "
                "is identified in the introduction, not inferred from attendance.",
            ),
            claim(
                "other_government",
                {
                    "history": "USDA Rural Development South Dakota state director, appointed March 2022",
                    "time_reference": "before_2026-11-03",
                },
                "In March of 2022, I was honored to be appointed the state director of "
                "USDA Rural Development South Dakota by President Joe Biden.",
                reason="Dated 2023 institutional interview explicitly identifies USDA state-director "
                "employment, not an advisory appointment or future campaign promise.",
            ),
            claim(
                "profession",
                {
                    "history": "Design/advertising, telecommunications marketing, then USDA state director"
                },
                "working in design and advertising",
                reason="Explicit dated occupational history, retained without forcing design/marketing "
                "into the narrower business-owner/executive analytical family.",
            ),
        ],
        identity="Full named alumna plus independently concordant South Dakota USDA leadership "
        "in the native candidate's retained voter-directory answer.",
        details={"publication_date": "2023-12-21", "identity_fragment": "Nikki Gronli"},
        text=body,
    )
    key = "brookings-gronli-2026"
    add(
        key,
        by_id["221167"],
        [
            claim(
                "age",
                {
                    "reported_age": 53,
                    "reference_date": "2026-05-01",
                    "birth_date_interval": ["1972-05-02", "1973-05-01"],
                },
                "Nikki Gronli, 53",
                reason="Age 53 reported May 1, 2026 supports election age 53-54, not an exact "
                "birthday or exact election age. Dated original candidate interview.",
            ),
        ],
        identity="Full name and explicit Democratic South Dakota at-large House candidacy.",
        details={"publication_date": "2026-05-01", "identity_fragment": "Nikki Gronli"},
    )
    key = "nv-benitez-thompson-2011"
    add(
        key,
        by_id["220715"],
        [
            claim(
                "religion",
                {
                    "historical_church_membership": "Our Savior Lutheran Church",
                    "reference_year": 2011,
                },
                "Our Savior Lutheran Church",
                reason="Explicit church membership in the dated 2011 official biography. "
                "Factual historical affiliation; current 2026 affiliation is not established, "
                "so no new current analytical religion value.",
            ),
        ],
        identity="Full name, Nevada Assembly district 27 and independently retained 2022 "
        "official biography agree; native NV02 House contest remains unchanged.",
        details={
            "publication_date": "2011-01-01",
            "publication_date_precision": "year",
            "identity_fragment": "Teresa Benitez-Thompson",
            "decimal_ascii_glyphs": True,
        },
    )

    for document in documents:
        destination = cache / document
        original = work / document.removeprefix("v7-")
        if destination.exists():
            if fingerprint(destination) != fingerprint(original):
                raise ValueError(f"Changed shared original: {document}")
        else:
            shutil.copyfile(original, destination)
    journal["sources"] = [s for s in journal["sources"] if not s["id"].startswith("v7-")] + sources
    write_json(journal_path, journal)
    write_json(receipts_path, receipts)
    write_json(root / "data/house-characteristics-v7-identity-decisions.json", decisions)
    result = {
        "documents": list(documents.values()),
        "sources": sources,
        "new_acquired_claims": sum(len(s["claims"]) for s in sources),
        "new_document_hashes": len({d["sha256"] for d in documents.values()}),
        "discovery_dispositions": attempts,
        "source_population": "Independently linked historical winners plus bounded original "
        "challenger biographies; historical classifications, not universal current identities.",
        "congressdata_disposition": "New 1229-column FST acquired and read. Actual MILITARY "
        "'No military service mentioned' is not a negative; historical rank zero is not promoted. "
        "Broader degree-equivalent/career flags do not replace exact credential/occupation evidence.",
        "mn_manual_disposition": "Acquired complete 2019 manual. Matt Little's covered credential, "
        "occupation and office fields already qualify in V6; no redundant observations registered.",
    }
    write_json(root / "data/house-characteristics-v7-acquisitions.json", result)
    return {
        k: v
        for k, v in result.items()
        if k not in {"sources", "documents", "discovery_dispositions"}
    }


if __name__ == "__main__":
    print(json.dumps(register(Path(__file__).resolve().parents[1]), indent=2))
