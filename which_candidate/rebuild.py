"""Broader, source-qualified 2026 evidence and retrospective donor comparisons."""

import argparse
import csv
import hashlib
import json
import math
import shutil
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pyarrow.parquet as pq

from .corrected import robust_fit, same_name
from .pipeline import csv_bytes
from .storage import fingerprint, read_rows, write_json, write_rows

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path("data/raw/rebuild-20261113")
CUTOFF = "20261103000000"
TABULAR = {
    "shor-1993-2022.tab": (
        "shor-original.dta",
        "20de5f97feb680deac01262ae0e54bb7effe747533ee871aef8a390c9b93beec",
    ),
    "c3-2018.tab": (
        "c3-original.dta",
        "486f46761a459f2b0ebd3e31f43332e6337469c7f766aaf40e2977ccc9a3e7c6",
    ),
}
SOURCES = {
    "shor": (
        "10.7910/DVN/SGOQ7G",
        "CC BY-NC-SA 4.0",
        {
            10853698: "shor-1993-2022.tab",
            10853699: "shor-codebook.pdf",
        },
    ),
    "characteristics": (
        "10.7910/DVN/VHAPHV",
        "CC0 1.0",
        {
            4641443: "c3-2018.tab",
            4724697: "c3-codebook.pdf",
        },
    ),
    "websites": (
        "10.7910/DVN/BZ2JRS",
        "CC BY 4.0",
        {
            14428619: "websites-readme.md",
            14428620: "biography-facts.parquet",
            14428621: "candidate-crosswalk.csv",
            14428623: "extraction-codebook.md",
            14428624: "extraction-documents.parquet",
            14428625: "extraction-manifest.json",
            14428626: "extraction-segments.parquet",
            14428627: "extraction-status.csv",
            14428629: "candidate-year-provenance.csv",
            14428630: "candidate-year-universe.csv",
            14428634: "on-ballot-2026-sources.csv",
        },
    ),
}


def fetch(url, path):
    if not path.exists():
        request = urllib.request.Request(url, headers={"User-Agent": "which-candidate-research"})
        with urllib.request.urlopen(request, timeout=180) as response:
            body = response.read()
        path.write_bytes(body)


def source_receipts(cache, acquire=False):
    """Verify publisher checksums, not just locally computed hashes."""
    cache = Path(cache)
    if acquire:
        cache.mkdir(parents=True, exist_ok=True)
    receipts = []
    for source, (doi, license_name, files) in SOURCES.items():
        catalog = cache / f"{source}-catalog.json"
        catalog_url = (
            f"https://dataverse.harvard.edu/api/datasets/:persistentId/?persistentId=doi:{doi}"
        )
        if acquire:
            fetch(catalog_url, catalog)
        version = json.loads(catalog.read_text())["data"]["latestVersion"]
        entries = {entry["dataFile"]["id"]: entry for entry in version["files"]}
        receipts.append(
            {
                "file": catalog.name,
                **fingerprint(catalog),
                "url": catalog_url,
                "doi": doi,
                "license": license_name,
                "role": "publisher_catalog",
                "version": version.get("versionNumber"),
                "release_time": version.get("releaseTime"),
            }
        )
        for ident, name in files.items():
            entry = entries[ident]
            if entry.get("restricted"):
                raise ValueError(f"Restricted source: {name}")
            metadata = entry["dataFile"]
            path = cache / name
            url = f"https://dataverse.harvard.edu/api/access/datafile/{ident}"
            if acquire:
                fetch(url, path)
            body = path.read_bytes()
            checksum = metadata["checksum"]
            algorithm = checksum["type"].lower().replace("-", "")
            checksum_body = body
            checksum_scope = "download"
            if name in TABULAR:
                original_name, tab_hash = TABULAR[name]
                original = cache / original_name
                if acquire:
                    fetch(url + "?format=original", original)
                checksum_body = original.read_bytes()
                if (
                    len(checksum_body) != metadata["originalFileSize"]
                    or fingerprint(path)["sha256"] != tab_hash
                ):
                    raise ValueError(f"Changed original or transformed tabular source: {name}")
                checksum_scope = "original_stata_not_transformed_tsv"
                receipts.append(
                    {
                        "file": original_name,
                        **fingerprint(original),
                        "url": url + "?format=original",
                        "doi": doi,
                        "license": license_name,
                        "publisher_file_id": ident,
                        "publisher_checksum": checksum,
                        "role": "original_uploaded_format",
                    }
                )
            if len(body) != metadata["filesize"] or (
                hashlib.new(algorithm, checksum_body).hexdigest().lower()
                != checksum["value"].lower()
            ):
                raise ValueError(f"Publisher checksum mismatch: {name}")
            receipts.append(
                {
                    "file": name,
                    **fingerprint(path),
                    "url": url,
                    "doi": doi,
                    "license": license_name,
                    "publisher_file_id": ident,
                    "publisher_filename": metadata["filename"],
                    "publisher_checksum": checksum,
                    "publisher_checksum_scope": checksum_scope,
                    "role": "publisher_tabular_transform" if name in TABULAR else "original",
                }
            )
    return receipts


def csv_rows(path, delimiter=","):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream, delimiter=delimiter))


def district(value):
    if value in ("AL", "00", "", None):
        return 0
    return int(float(value))


def qualify_website(candidate, records):
    if not candidate.get("D_fec_id") or not candidate.get("D_name"):
        return None
    matches = [
        r
        for r in records
        if r["year"] == "2026"
        and r["party"] == "D"
        and r["state"] == candidate["state"]
        and r["office"] == candidate["chamber"]
        and r["cand_id"] == candidate.get("D_fec_id")
        and same_name(candidate.get("D_name") or "", r["candidate"])
        and (
            candidate["chamber"] == "senate"
            or district(r["district"]) == district(candidate["district"])
        )
    ]
    return matches[0] if len(matches) == 1 else None


def valid_capture(value):
    if not isinstance(value, str) or len(value) != 14 or not value.isascii() or not value.isdigit():
        return False
    try:
        datetime.strptime(value, "%Y%m%d%H%M%S")
    except ValueError:
        return False
    return value >= "20000101000000"


def capture_before_cutoff(value):
    return valid_capture(value) and value < CUTOFF


def unique_facts(facts, documents):
    """Choose the earliest document per candidate-record key, never count copies."""
    selected = {}
    for fact in facts:
        document = documents.get(fact["parent_document_id"])
        if not document or document["candidate_cycle_id"] != fact["candidate_cycle_id"]:
            raise ValueError("Missing or conflicting biography document")
        key = (fact["candidate_cycle_id"], fact["candidate_record_key"])
        order = (
            (
                document["first_capture_timestamp"]
                if valid_capture(document.get("first_capture_timestamp"))
                else "99999999999999"
            ),
            fact["parent_document_id"],
            fact["record_id"],
        )
        if key not in selected or order < selected[key][0]:
            selected[key] = (order, fact, document)
    return [(v[1], v[2]) for _, v in sorted(selected.items())]


def donor_decision(query, min_givers=0):
    value = query["dime"]
    reasons = []
    if value["status"] != "exact_fec_state_party_unique_person":
        reasons.append(value["status"])
    if value.get("name_screen") != "consistent":
        reasons.append("name_not_independently_qualified_in_this_specification")
    score = value.get("score")
    if type(score) not in (int, float) or not math.isfinite(score):
        reasons.append("missing_or_invalid_score")
    cycle = value.get("cycle")
    if type(cycle) is not int or not 1980 <= cycle <= 2024 or cycle % 2:
        reasons.append("score_cycle_not_qualified")
    counts = []
    for count in value.get("giver_counts", []):
        try:
            count = float(count)
            if math.isfinite(count):
                counts.append(count)
        except (ValueError, TypeError):
            pass
    if min_givers and (not counts or min(counts) < min_givers):
        reasons.append("insufficient_reported_givers")
    return {
        "qualified": not reasons,
        "reasons": sorted(set(reasons)),
        "score": score if not reasons else None,
        "cycle": cycle,
        "source_rows": value.get("source_rows", []),
        "min_reported_givers": min(counts) if counts else None,
        "measure": "recipient.cfscore.dyn",
        "interpretation": "historical_donor_ideology; retrospective_not_prospective",
    }


def donor_design(rows, controls=True):
    lean = np.array([(r["presidential_D_two_party_share_pct"] - 50) / 10 for r in rows])
    columns = [np.ones(len(rows)), lean, lean**2]
    names = ["intercept", "lean_10pp", "lean_squared"]
    if controls:
        for key in ("D_incumbent", "R_incumbent"):
            values = np.array([int(r[key]) for r in rows])
            if len(values) and np.linalg.matrix_rank(
                np.column_stack([*columns, values])
            ) > np.linalg.matrix_rank(np.column_stack(columns)):
                columns.append(values)
                names.append(key)
    columns.append(np.array([r["donor"]["score"] / 0.5 for r in rows]))
    return np.column_stack(columns), [*names, "donor_rightward_05"]


def checked_fit(rows, x, names, focal):
    result = robust_fit(rows, x, names, focal)
    full_rank = all(
        np.linalg.matrix_rank(x[[r["state"] != state for r in rows]]) == x.shape[1]
        for state in {r["state"] for r in rows}
    )
    if not full_rank:
        result["publication_status"] = "diagnostic_only_rank_loss_on_state_deletion"
        result["ci_low"] = result["ci_high"] = None
    return {**result, "full_rank_state_deletions": full_rank}


def donor_fits(panel):
    fits = []
    for chamber in ("house", "senate"):
        sample = [
            r
            for r in panel
            if r["chamber"] == chamber
            and r["eligible"]
            and r["donor"]["qualified"]
            and type(r["D_incumbent"]) is bool
            and type(r["R_incumbent"]) is bool
        ]
        alternate = [r for r in sample if r.get("previous_presidential_share") is not None]
        variants = {
            "all_qualified": sample,
            "democratic_incumbents": [r for r in sample if r["D_incumbent"]],
            "democratic_nonincumbents": [r for r in sample if not r["D_incumbent"]],
            "at_least_100_givers": [
                r for r in sample if (r["donor"]["min_reported_givers"] or 0) >= 100
            ],
            "competitive_40_60": [
                r for r in sample if 40 <= r["presidential_D_two_party_share_pct"] <= 60
            ],
            "current_benchmark_common_sample": alternate,
            "previous_benchmark_common_sample": [
                {
                    **r,
                    "presidential_D_two_party_share_pct": r["previous_presidential_share"],
                    "descriptive_gap_share_pp": r["D_two_party_share_pct"]
                    - r["previous_presidential_share"],
                }
                for r in alternate
            ],
        }
        for variant, rows in variants.items():
            if not rows:
                fits.append(
                    {
                        "chamber": chamber,
                        "variant": variant,
                        "status": "no_observations",
                        "n": 0,
                        "state_clusters": 0,
                        "candidate_election_ids": [],
                        "publication_status": "diagnostic_only_low_support",
                    }
                )
                continue
            x, names = donor_design(rows)
            result = checked_fit(rows, x, names, "donor_rightward_05")
            fits.append(
                {
                    "chamber": chamber,
                    "year": 2026,
                    "variant": variant,
                    "estimand": "selected_sample_association_per_0.5_donor_score; not_policy_effect",
                    **result,
                    "ci_low_share_pp": result.get("ci_low"),
                    "ci_high_share_pp": result.get("ci_high"),
                    "ci_low_margin_pp": (
                        2 * result["ci_low"] if result.get("ci_low") is not None else None
                    ),
                    "ci_high_margin_pp": (
                        2 * result["ci_high"] if result.get("ci_high") is not None else None
                    ),
                }
            )
    return fits


def measurement_fits(panel):
    """Distinguish metrics without confusing different candidate samples."""
    rows = [
        r
        for r in panel
        if r["chamber"] == "house"
        and r["eligible"]
        and r["donor"]["qualified"]
        and r["D_incumbent"] is True
        and type(r["R_incumbent"]) is bool
        and r["service_verified_incumbent"]
        and r["nokken_poole_dim1"] is not None
    ]
    if not rows:
        return []
    x, names = donor_design(rows)
    voting = np.array([r["nokken_poole_dim1"] / 0.1 for r in rows])
    joint = np.column_stack([x, voting])
    joint_names = [*names, "voting_rightward_01"]
    specifications = (
        ("donor", x, names, names[-1]),
        (
            "voting",
            np.column_stack([x[:, :-1], voting]),
            [*names[:-1], "voting_rightward_01"],
            "voting_rightward_01",
        ),
        ("joint_donor", joint, joint_names, names[-1]),
        ("joint_voting", joint, joint_names, "voting_rightward_01"),
    )
    return [
        {
            "year": 2026,
            "chamber": "house",
            "variant": label,
            "interpretation": "exploratory_measurement_audit; not_confirmatory",
            **checked_fit(rows, design, terms, focal),
        }
        for label, design, terms, focal in specifications
    ]


def historical_leads(candidate, shor, c3):
    name = candidate.get("D_name") or ""
    matches = []
    for source, rows, party in (
        ("shor", shor.get(candidate["state"], []), "D"),
        ("c3", c3.get(candidate["state"], []), "Democratic"),
    ):
        for row_number, row in rows:
            if row["party"] == party and same_name(name, row.get("name", row.get("fullname"))):
                matches.append(
                    {
                        "source": source,
                        "source_row": row_number,
                        "source_person_id": row.get("u_id", row.get("id")),
                        "source_name": row.get("name", row.get("fullname")),
                        "state": candidate["state"],
                        "identity_verified": False,
                        "model_ready": False,
                        "status": "same_state_party_name_lead_requires_independent_career_bridge",
                        "vintage": "1993-2022 career score"
                        if source == "shor"
                        else "2018 candidacy",
                        "source_license": SOURCES[
                            "shor" if source == "shor" else "characteristics"
                        ][1],
                    }
                )
    return matches


def build(root=ROOT, output=None, cache=None):
    root = Path(root)
    output = Path(output) if output else root / "results/2026-v4"
    cache = Path(cache) if cache else root / CACHE
    receipts = source_receipts(cache)
    output.mkdir(parents=True, exist_ok=True)
    receipt_path = output / "source-receipts.json"
    if receipt_path.exists() and json.loads(receipt_path.read_text()) != receipts:
        raise ValueError("Changed original sources require a new version")
    panel = [
        r
        for r in read_rows(root / "results/2026-v3/analysis/candidate-queries.jsonl.gz")
        if r["year"] == 2026
    ]
    queries = {
        r["contest_id"]: r
        for r in read_rows(root / "results/2026-source-expansion/candidate-queries.jsonl.gz")
    }
    if len(panel) != 470 or len(queries) != 470 or len({r["contest_id"] for r in panel}) != 470:
        raise ValueError("Rebuild requires the complete unique 470-contest universe")
    universe = csv_rows(cache / "candidate-year-universe.csv")
    by_id = defaultdict(list)
    for row in universe:
        by_id[row["cand_id"]].append(row)
    documents = {
        r["parent_document_id"]: r
        for r in pq.read_table(cache / "extraction-documents.parquet").to_pylist()
    }
    if len(documents) != 38216:
        raise ValueError("Biography document universe changed or contains duplicate IDs")
    all_facts = pq.read_table(cache / "biography-facts.parquet").to_pylist()
    if len({r["record_id"] for r in all_facts}) != len(all_facts):
        raise ValueError("Duplicate biography record IDs")
    grouped = defaultdict(list)
    for fact, doc in unique_facts(all_facts, documents):
        grouped[fact["candidate_cycle_id"]].append((fact, doc))
    shor, c3 = defaultdict(list), defaultdict(list)
    for name, target in (("shor-1993-2022.tab", shor), ("c3-2018.tab", c3)):
        for number, row in enumerate(csv_rows(cache / name, "\t"), 2):
            target[row.get("st", row.get("state"))].append((number, row))
    facts, leads = [], []
    for row in panel:
        legacy_keys = (
            "cross_fitted_expected_share_pct",
            "cross_fitted_overperformance_share_pp",
            "eligible_adjusted_overperformance",
            "adjusted_overperformance_hold",
        )
        row["archived_prediction_provenance"] = {
            "status": "inherited_legacy_fields_not_recomputed_or_used_in_v4",
            "values": {key: row.pop(key) for key in legacy_keys if key in row},
        }
        source_query = queries[row["contest_id"]]
        if source_query["candidate_election_id"] != row["D_candidate_election_id"]:
            raise ValueError("Candidate/source query identity mismatch")
        row["donor"] = donor_decision(source_query)
        row["donor_model_holds"] = [
            reason
            for reason, held in (
                ("election_comparison_ineligible", not row["eligible"]),
                ("donor_identity_or_vintage_unqualified", not row["donor"]["qualified"]),
                ("unknown_democratic_incumbency", type(row["D_incumbent"]) is not bool),
                ("unknown_republican_incumbency", type(row["R_incumbent"]) is not bool),
            )
            if held
        ]
        match = qualify_website(row, by_id.get(row.get("D_fec_id"), []))
        biography = []
        if match:
            for fact, doc in grouped[match["candidate_cycle_id"]]:
                if (
                    doc["year"] != 2026
                    or doc["state"] != row["state"]
                    or doc["office"] != row["chamber"]
                    or doc["party"] != "democrat"
                ):
                    raise ValueError("Biography document context conflicts with matched candidate")
                item = {
                    k: fact[k]
                    for k in (
                        "record_id",
                        "candidate_record_key",
                        "parent_document_id",
                        "segment_id",
                        "field",
                        "value",
                        "relationship",
                        "evidence_parent_start_char",
                        "evidence_parent_end_char",
                        "evidence_alignment_method",
                    )
                }
                item.update(
                    {
                        "contest_id": row["contest_id"],
                        "candidate_cycle_id": match["candidate_cycle_id"],
                        "candidate_election_id": row["D_candidate_election_id"],
                        "first_capture_timestamp": doc["first_capture_timestamp"],
                        "last_capture_timestamp": doc["last_capture_timestamp"],
                        "captured_before_election": capture_before_cutoff(
                            doc["first_capture_timestamp"]
                        ),
                        "original_urls": doc["original_urls"],
                        "wayback_urls": doc["wayback_urls"],
                        "source_text_sha256": doc["extraction_source_text_sha256"],
                        "evidence_sha256": hashlib.sha256(fact["evidence"].encode()).hexdigest(),
                        "route_source": doc["route_source"],
                        "model_ready": False,
                        "review_status": "machine_extracted; subject_and_field_require_review",
                        "sensitive_identity_labels_inferred": False,
                    }
                )
                biography.append(item)
                facts.append(item)
        row["website"] = {
            "candidate_cycle_id": match["candidate_cycle_id"] if match else None,
            "status": "exact_fec_name_context" if match else "no_unique_qualified_match",
            "biography_record_ids": [f["record_id"] for f in biography],
            "pre_election_record_ids": [
                f["record_id"] for f in biography if f["captured_before_election"]
            ],
            "pre_election_fields": sorted(
                {f["field"] for f in biography if f["captured_before_election"]}
            ),
            "labels_promoted": False,
        }
        row["historical_candidate_leads"] = historical_leads(row, shor, c3)
        leads.extend(
            {"contest_id": row["contest_id"], **lead} for lead in row["historical_candidate_leads"]
        )
    return write_analysis(root, output, panel, facts, leads, receipts)


def persist_directory(staged, output):
    """Keep a verified output immutable, including on an identical replay."""
    expected = {p.relative_to(staged): fingerprint(p) for p in staged.rglob("*") if p.is_file()}
    existing = {p.relative_to(output): fingerprint(p) for p in output.rglob("*") if p.is_file()}
    if existing:
        if existing != expected:
            raise ValueError("Changed outputs require a new output directory")
        return
    for relative in expected:
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(staged / relative, target)


def write_analysis(root, output, panel, facts, leads, receipts):
    with TemporaryDirectory(prefix="which-candidate-analysis-") as directory:
        staged = Path(directory)
        result = _write_analysis(root, staged, panel, facts, leads, receipts)
        persist_directory(staged, output)
    return result


def _write_analysis(root, output, panel, facts, leads, receipts):
    output.mkdir(parents=True, exist_ok=True)
    receipt_path = output / "source-receipts.json"
    fits = donor_fits(panel)
    named = [r for r in panel if r.get("D_name")]
    cohorts = {
        "all_named": named,
        "democratic_incumbents": [r for r in named if r["D_incumbent"] is True],
        "democratic_nonincumbents": [r for r in named if r["D_incumbent"] is False],
        "unknown_incumbency": [r for r in named if r["D_incumbent"] is None],
        "won_two_party_comparison": [r for r in named if r["won_two_party_comparison"] is True],
        "lost_two_party_comparison": [r for r in named if r["won_two_party_comparison"] is False],
        "unknown_two_party_comparison": [r for r in named if r["won_two_party_comparison"] is None],
    }
    coverage = [
        {
            "cohort": cohort,
            "nominees": len(rows),
            "donor_score": sum(r["donor"]["qualified"] for r in rows),
            "pre_election_biography": sum(
                bool(r["website"]["pre_election_record_ids"]) for r in rows
            ),
            "any_2026_biography": sum(bool(r["website"]["biography_record_ids"]) for r in rows),
            "prior_federal_voting_score": sum(r["nokken_poole_dim1"] is not None for r in rows),
            "field_counts": dict(
                Counter(field for r in rows for field in r["website"]["pre_election_fields"])
            ),
        }
        for cohort, rows in cohorts.items()
    ]
    write_json(receipt_path, receipts)
    write_rows(output / "candidate-queries.jsonl.gz", panel)
    write_rows(output / "biography-facts.jsonl.gz", facts)
    write_rows(output / "historical-candidate-leads.jsonl.gz", leads)
    write_rows(output / "donor-fits.jsonl.gz", fits)
    write_rows(output / "measurement-fits.jsonl.gz", measurement_fits(panel))
    write_json(output / "coverage.json", coverage)
    scalar_fits = [
        {k: v for k, v in fit.items() if not isinstance(v, (list, dict))} for fit in fits
    ]
    (output / "donor-fits.csv").write_bytes(csv_bytes(scalar_fits))
    write_json(
        output / "manifest.json",
        {
            "target_year": 2026,
            "status": "retrospective_provisional",
            "contest_count": 470,
            "biography_facts": len(facts),
            "sources": fingerprint(receipt_path),
            "inputs": {
                name: fingerprint(root / name)
                for name in (
                    "results/2026-v3/analysis/candidate-queries.jsonl.gz",
                    "results/2026-source-expansion/candidate-queries.jsonl.gz",
                )
            },
            "files": {
                p.name: fingerprint(p)
                for p in sorted(output.iterdir())
                if p.is_file() and p.name != "manifest.json"
            },
        },
    )
    return {"coverage": coverage, "facts": len(facts), "historical_leads": len(leads)}


def replay(root=ROOT, output=None):
    """Recompute all v4 fits and coverage from complete, checksum-verified queries."""
    root = Path(root)
    inputs = root / "results/2026-v4"
    output = Path(output) if output else root / "artifacts/replay-v4"
    manifest = json.loads((inputs / "manifest.json").read_text())
    for name, receipt in manifest["files"].items():
        if fingerprint(inputs / name) != receipt:
            raise ValueError(f"Changed normalized replay input: {name}")
    for name, receipt in manifest["inputs"].items():
        if fingerprint(root / name) != receipt:
            raise ValueError(f"Changed upstream replay input: {name}")
    return write_analysis(
        root,
        output,
        read_rows(inputs / "candidate-queries.jsonl.gz"),
        read_rows(inputs / "biography-facts.jsonl.gz"),
        read_rows(inputs / "historical-candidate-leads.jsonl.gz"),
        json.loads((inputs / "source-receipts.json").read_text()),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("acquire", "build", "replay"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--cache", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    cache = args.cache or args.root / CACHE
    result = (
        source_receipts(cache, acquire=True)
        if args.command == "acquire"
        else replay(args.root, args.output)
        if args.command == "replay"
        else build(args.root, args.output, cache)
    )
    print(json.dumps(result, indent=2))
