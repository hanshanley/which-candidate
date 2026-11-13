import shutil
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .sources import load_sources
from .storage import confined, fingerprint, write_json

SHEETS = {
    2016: "1VfkHtzBTP5gf4jAu8tcVQgsBJ1IDvXEHjuMqYlOgYbA",
    2018: "1zLNAuRqPauss00HDz4XbTH2HqsCzMe0pR8QmD1K8jk8",
    2020: "1XbUXnI9OyfAuhP5P3vWtMuGc5UJlrhXbzZo3AwMuHtk",
    2022: "1CKngqOp8fzU22JOlypoxNsxL6KSAH920Whc-rd7ebuM",
    2024: "1ng1i_Dm_RMDnEvauH44pgE6JCUsapcuu8F2pCfeLWFo",
}


def source_specs():
    specs = [
        {
            "id": f"legislators_{group}",
            "kind": "legislators",
            "origin_url": (
                f"https://unitedstates.github.io/congress-legislators/legislators-{group}.json"
            ),
            "suffix": ".json",
            "attribution": "unitedstates/congress-legislators, CC0",
        }
        for group in ("current", "historical")
    ]
    for kind, url in (
        ("voteview_members", "https://voteview.com/static/data/out/members/HSall_members.csv"),
        (
            "voteview_unity",
            "https://voteview.com/static/articles/party_unity_scores/party_unity_by_member.csv",
        ),
    ):
        specs.append(
            {
                "id": kind,
                "kind": kind,
                "origin_url": url,
                "suffix": ".csv",
                "attribution": "Lewis et al., Voteview: Congressional Roll-Call Votes Database",
            }
        )
    for year, sheet in SHEETS.items():
        specs.append(
            {
                "id": f"house_presidential_map_{year}",
                "kind": "house_presidential",
                "map_year": year,
                "presidential_year": year if year % 4 == 0 else year - 2,
                "origin_url": f"https://docs.google.com/spreadsheets/d/{sheet}/export?format=xlsx",
                "catalog_url": "https://www.the-downballot.com/p/data",
                "map_evidence_url": (
                    "https://www.the-downballot.com/p/the-downballots-calculations-of-presidential"
                ),
                "suffix": ".xlsx",
                "attribution": "Daily Kos Elections / The Downballot; calculated district results",
                "source_status": "publisher_calculated_election_map_specific_estimates",
            }
        )
    specs.append(
        {
            "id": "fec_nominees_2024",
            "kind": "fec_nominees_2024",
            "origin_url": "https://www.fec.gov/documents/5548/2024congressgecands.xlsx",
            "suffix": ".xlsx",
            "attribution": "Federal Election Commission, 2024 general-election ballot roster",
        }
    )
    for year, publication in (
        (2016, "2016-02-12"),
        (2018, "2018-07-27"),
        (2020, "2020-07-22"),
        (2022, "2022-10-26"),
        (2024, "2024-04-25"),
    ):
        specs.append(
            {
                "id": f"congressional_directory_{year}",
                "kind": "congressional_directory",
                "election_year": year,
                "publication_date": publication,
                "origin_url": (
                    f"https://www.govinfo.gov/content/pkg/CDIR-{publication}/"
                    f"pdf/CDIR-{publication}.pdf"
                ),
                "suffix": ".pdf",
                "attribution": "Joint Committee on Printing / US Government Publishing Office",
            }
        )
    for election, vintage, congress in (
        (2016, 2016, 115),
        (2018, 2018, 116),
        (2020, 2021, 117),
        (2022, 2022, 118),
        (2024, 2024, 119),
    ):
        for level in ("040", "500"):
            for table in ("B02001", "B03002"):
                suffix = ".csv.gz" if vintage <= 2018 else ".csv.zip"
                specs.append(
                    {
                        "id": f"acs_{vintage}_{level}_{table}",
                        "kind": "acs_composition",
                        "election_year": election,
                        "acs_year": vintage,
                        "map_congress": congress,
                        "summary_level": level,
                        "table": table,
                        "origin_url": (
                            "https://www2.census.gov/programs-surveys/acs/replicate_estimates/"
                            f"{vintage}/data/5-year/{level}/{table}{suffix}"
                        ),
                        "suffix": suffix,
                        "attribution": "US Census Bureau, ACS five-year variance replicate estimates",
                        "timing": "retrospective_context_not_available_for_forward_prediction",
                    }
                )
    for year, publication, url in (
        (
            2018,
            "2017-01-19",
            "https://assets.pewresearch.org/wp-content/uploads/sites/11/2017/01/19161723/Member-affiliations-for-web.pdf",
        ),
        (
            2020,
            "2019-01-03",
            "https://www.pewresearch.org/religion/wp-content/uploads/sites/7/2019/01/Detailed-tables-NUMBER-CHECK-COMPLETE-1-3.pdf",
        ),
        (
            2022,
            "2021-01-04",
            "https://www.pewresearch.org/wp-content/uploads/sites/20/2021/01/01.04.21_faith_on_the_hill_detailed.table_.update.pdf",
        ),
        (
            2024,
            "2023-01-03",
            "https://www.pewresearch.org/religion/wp-content/uploads/sites/7/2022/12/PF_2023.01.03_congress_LIST.pdf",
        ),
    ):
        specs.append(
            {
                "id": f"pew_member_religion_{year}",
                "kind": "pew_member_religion",
                "election_year": year,
                "publication_date": publication,
                "origin_url": url,
                "suffix": ".pdf",
                "attribution": "Pew Research Center, Faith on the Hill; CQ office questionnaires",
            }
        )
    specs.append(
        {
            "id": "district_religiosity_v2",
            "kind": "district_religiosity",
            "origin_url": (
                "https://marksetzler.org/Congressional_District_Religiosity_Dataset/"
                "ReligEstimatesByCD_07_22_2018.csv"
            ),
            "suffix": ".csv",
            "attribution": "Mark Setzler, Congressional District Religiosity Dataset, Version 2",
            "qualification": (
                "2010_RCMS_congregation_adherence; county_population_apportionment;"
                " not_Census_religion_or_individual_self_identification"
            ),
        }
    )
    return specs


def acquire_research(data_dir, specs=None):
    data_dir = Path(data_dir).resolve()
    manifest_path = data_dir / "research-sources.json"
    receipts = []
    if manifest_path.exists():
        manifest = load_sources(manifest_path)
        receipts = manifest["sources"]
    expected = specs if specs is not None else source_specs()
    existing = {row["id"]: row for row in receipts}
    for spec in expected:
        if spec["id"] in existing and existing[spec["id"]]["origin_url"] != spec["origin_url"]:
            raise ValueError("Source URL changed; use a new versioned manifest")
    pending = [spec for spec in expected if spec["id"] not in existing]
    if not pending:
        return {"status": "verified_existing_import", "sources": len(receipts)}
    data_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".acquisition-", dir=data_dir) as temporary:
        for spec in pending:
            path = Path(temporary) / (spec["id"] + spec["suffix"])
            request = urllib.request.Request(
                spec["origin_url"], headers={"User-Agent": "which-candidate research/0.1"}
            )
            with (
                urllib.request.urlopen(request, timeout=120) as response,
                path.open("wb") as stream,
            ):
                shutil.copyfileobj(response, stream)
            receipt = {
                **spec,
                **fingerprint(path),
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            }
            relative = f"raw/{receipt['sha256']}{spec['suffix']}"
            destination = confined(data_dir, relative)
            destination.parent.mkdir(exist_ok=True)
            if destination.exists():
                if fingerprint(destination) != fingerprint(path):
                    raise ValueError("Content-addressed research cache collision")
            else:
                shutil.copyfile(path, destination)
            receipt["path"] = relative
            receipts.append(receipt)
            write_json(
                manifest_path,
                {"schema": "which_candidate.sources.v1", "sources": receipts},
            )
            print(f"Acquired {spec['id']}: {receipt['bytes']:,} bytes", flush=True)
    write_json(
        manifest_path,
        {"schema": "which_candidate.sources.v1", "sources": receipts},
    )
    return {"status": "imported", "sources": len(receipts)}


def import_2024(source, data_dir):
    source, data_dir = Path(source).resolve(), Path(data_dir).resolve()
    destination_manifest = data_dir / "supplemental-returns-sources.json"
    if destination_manifest.exists():
        manifest = load_sources(destination_manifest)
        return {"status": "verified_existing_import", "sources": len(manifest["sources"])}
    context = source / "data/raw/context/20261104T171449Z"
    import json

    original = json.loads((context / "manifest.json").read_bytes())
    receipts = []
    for name, kind in (
        ("clerk-2024.pdf", "clerk_senate_2024"),
        ("2024presgeresults.xlsx", "fec_president_2024"),
    ):
        held = context / name
        receipt = original[name]
        if fingerprint(held) != {key: receipt[key] for key in ("bytes", "sha256")}:
            raise ValueError(f"Held 2024 original does not match receipt: {name}")
        relative = f"raw/{receipt['sha256']}{held.suffix}"
        destination = confined(data_dir, relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and fingerprint(destination) != fingerprint(held):
            raise ValueError("Content-addressed 2024 cache collision")
        shutil.copyfile(held, destination)
        receipts.append(
            {
                "id": kind,
                "kind": kind,
                "origin_url": receipt["url"],
                "original_retrieved_at": receipt["retrieved_at"],
                "path": relative,
                **fingerprint(held),
                "attribution": "Office of the Clerk / Federal Election Commission, official returns",
            }
        )
    write_json(
        destination_manifest,
        {"schema": "which_candidate.sources.v1", "sources": receipts},
    )
    return {"status": "imported", "sources": len(receipts)}
