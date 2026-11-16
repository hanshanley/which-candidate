"""A bounded acquisition batch: primary CFE biographies and a state-library profile."""

import json
from datetime import datetime, timezone
from pathlib import Path

from .characteristics_acquisition import ACQUISITIONS
from .characteristics_research import normalized
from .corrected import text
from .storage import fingerprint, read_rows, write_json


def register(root):
    root = Path(root)
    journal_path = root / "data/house-characteristics-research.json"
    receipt_path = root / "data/house-characteristics-receipts.json"
    journal = json.loads(journal_path.read_text())
    receipts = json.loads(receipt_path.read_text())
    acquisition = json.loads((root / ACQUISITIONS).read_text())
    if any(s["id"].startswith("v3-cfe-") for s in journal["sources"]):
        raise ValueError("Additional biography batch already registered")
    people = read_rows(root / "results/house/candidates.jsonl.gz")
    cache = root / "data/raw/house-characteristics-v1"
    documents = {}
    for key, filename, url in [
        ("v3-cfe-2026", "cfe-2026.html", "https://www.cfequality.org/members/endorsements/2026"),
        ("v3-mn-little", "mn-matt-little.html", "https://www.lrl.mn.gov/legdb/fulldetail?ID=15490"),
    ]:
        path = root / "artifacts/characteristics-v3" / filename
        document = {
            "id": key,
            "url": url,
            "resolved_url": url,
            "retrieved_at": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
            "retrieval_clock_basis": "completed_curl_download_file_mtime",
            "retrieval_method": "original_download_curl_TLS_verified",
            "original_bytes_acquired": True,
            "new_document_hash": True,
            **fingerprint(path),
        }
        documents[key] = document
        (cache / key).write_bytes(path.read_bytes())
    cfe_text = normalized(text((cache / "v3-cfe-2026").read_text()))
    observations = {
        "Eric Yonce": [
            ("religion", "not religious", "Yonce is not religious."),
            (
                "profession",
                "retail management",
                "more than 20 years working as a manager in big box retail stores",
            ),
        ],
        "Kelly Esti": [
            ("religion", "non-believer", "Esti is a non-believer."),
            ("military", "veteran, branch unreported", "He is a veteran and small business owner"),
        ],
        "Ned Pillersdorf": [
            (
                "religion",
                "not affiliated with any organized religion",
                "Pillersdorf is not affiliated with any organized religion.",
            ),
            ("profession", "attorney", "Pillersdorf is an attorney who has decades of experience"),
        ],
        "Lauren Jewett": [
            ("religion", "spiritual but not religious", "Jewett is spiritual but not religious."),
            (
                "profession",
                "special education teacher",
                "a special education teacher with over 16 years in Louisiana classrooms",
            ),
        ],
        "Fred Wellman": [
            (
                "religion",
                "not religious; raised Catholic",
                "Wellman was raised Catholic and is not religious.",
            ),
            (
                "military",
                "military service with three Iraq tours",
                "his military service, which included three tours in Iraq",
            ),
            (
                "profession",
                "nonprofit executive",
                "He also served as the executive director of the Lincoln Project.",
            ),
        ],
        "Missi Hesketh": [
            ("religion", "religiously unaffiliated", "She is religiously unaffiliated."),
            (
                "prior_elected_office",
                "Mayor of Forsyth, elected 2023",
                "was elected as Mayor of Forsyth in 2023",
            ),
        ],
        "Benjamin Ambrose": [
            (
                "education",
                "MBA, Johns Hopkins; master's, Harvard",
                "he has a MBA from Johns Hopkins and a Master’s in Anthropology from Harvard.",
            ),
            (
                "military",
                "Marine infantry service, nearly 20 years",
                "served nearly 20 years as a Marine Infantryman",
            ),
            (
                "other_government",
                "federal contractor, not confirmed government employee",
                "worked in Washington DC as a contractor with the Veterans Administration and Department of Defense",
            ),
        ],
        "Jerrad Christian": [
            ("religion", "agnostic", "Christian is an agnostic."),
            ("military", "Navy veteran", "Christian is Navy veteran and software engineer"),
        ],
        "Kristi Burke": [("religion", "atheist", "Burke is an atheist.")],
        "Jonny Larsen": [
            ("religion", "atheist", "Larsen is an atheist."),
            ("military", "Marine veteran", "Larsen is a Marine veteran"),
        ],
        "Gay Valimont": [
            ("religion", "Methodist", "Valimont is a Methodist and an ally of our community.")
        ],
    }
    new_sources = []
    for name, entries in observations.items():
        (candidate,) = [c for c in people if c["name"] == name and c["party"] == "Democratic"]
        claims = []
        for trait, value, fragment in entries:
            if normalized(fragment) not in cfe_text:
                raise ValueError(f"Unverified new fragment: {name}: {fragment}")
            claims.append(
                {
                    "trait": trait,
                    "value": value,
                    "fragment": fragment,
                    "qualification": (
                        f"CFE 2026 House biography under heading {name}; state/district reviewed. "
                        "Endorsing organization report, not automatically candidate self-description. "
                        "Undated live page explicitly updated after election: observed on retrieval "
                        "date only. No pre-election analytical promotion. Religion is literal report, "
                        "not inferred from endorsement, upbringing, caucus membership or scientist."
                    ),
                }
            )
        new_sources.append(
            (candidate, "v3-cfe-2026", claims, "endorsing_organization_candidate_biography")
        )
    (candidate,) = [c for c in people if c["name"] == "Matt Little" and c["state"] == "MN"]
    new_sources.append(
        (
            candidate,
            "v3-mn-little",
            [
                {
                    "trait": "age",
                    "value": "1984-11-24",
                    "fragment": "Date of Birth: 11/24/1984",
                    "qualification": "Exact official historical legislative biography birthday; age at 2026 election is 41. Retrospectively retrieved; not prospective data.",
                },
                {
                    "trait": "gender",
                    "value": "M",
                    "fragment": "Gender: Male",
                    "qualification": "Official library's literal Gender=Male field; preserve source definition, not an inference from name, pronouns or photograph.",
                },
                {
                    "trait": "education",
                    "value": "doctoral_or_professional",
                    "fragment": "University of Minnesota, Law School; J.D.; 2014",
                    "qualification": "Explicit completed JD with 2014 year in historical legislative directory; not attendance or honorary credential.",
                },
                {
                    "trait": "profession",
                    "value": "legal",
                    "fragment": "Occupation (when first elected): Attorney",
                    "qualification": "Explicit occupation at first election, 2016, in historical legislative biography. Historical legal profession, not necessarily present paid employment.",
                },
                {
                    "trait": "prior_elected_office",
                    "value": "municipal_elected",
                    "fragment": "2012 to 2016 [Elected]",
                    "qualification": "Explicit Lakeville mayor elected service 2012-2016; positive evidence only, not a service-versus-no-service comparison.",
                },
                {
                    "trait": "other_government",
                    "value": "state_advisory_task_force",
                    "fragment": "Attorney General's Advisory Task Force on Lowering Pharmaceutical Drug Prices ; 2019 to ?",
                    "qualification": "Dated state advisory membership, 2019; no claim of paid government employment. Religion blank and None Reported minority are unknown, not negative categories.",
                },
            ],
            "official_historical_state_legislative_biography",
        )
    )
    for candidate, key, claims, kind in new_sources:
        source_id = f"{key}-{candidate['candidate_id']}"
        journal["sources"].append(
            {
                "id": source_id,
                "document_id": key,
                **{
                    k: candidate[k]
                    for k in ("candidate_id", "contest_id", "name", "state", "district", "party")
                },
                "url": documents[key]["url"],
                "publication_date": None,
                "kind": kind,
                "identity_qualification": "Exact full name, state, party and House district reviewed; official Little biography explicitly identifies the 2026 second-district candidacy.",
                "claims": claims,
            }
        )
        receipts["sources"].append(
            {
                **documents[key],
                "id": source_id,
                "status": "acquired_pending_fragment_validation",
            }
        )
    acquisition["documents"].extend(documents.values())
    acquisition["new_document_hashes"] += len(documents)
    acquisition["sources"] += len(new_sources)
    acquisition["new_acquired_claims"] += sum(len(s[2]) for s in new_sources)
    acquisition["discovery_dispositions"].extend(
        [
            {
                "source": "Nonreligious candidates public spreadsheet, November 13 update",
                "status": "downloaded_discovery_not_ingested",
                "reason": "Used to locate CFE primary biographies; caucus members include religious allies, N/A is unknown and scientist is not a religious affiliation. Conflicting district assignments rejected; no blanket nonreligion coding.",
            },
            {
                "source": "Minnesota library minority/religion fields",
                "status": "unknowns_preserved",
                "reason": "Matt Little's None Reported minority is not White/non-Hispanic; blank religion does not establish nonreligion. Unrelated legislator ID15494 was not used.",
            },
            {
                "source": "CFE Benjamin Ambrose",
                "status": "religion_coding_rejected",
                "reason": "Identifies as a scientist describes neither a religious affiliation nor confirmed nonreligion.",
            },
        ]
    )
    write_json(journal_path, journal)
    write_json(receipt_path, receipts)
    write_json(root / ACQUISITIONS, acquisition)
    return acquisition


if __name__ == "__main__":
    print(json.dumps(register(Path(__file__).resolve().parents[1]), indent=2))
