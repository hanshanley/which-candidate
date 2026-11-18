"""Roster-wide factual research, separate from frozen scientific eligibility."""

import argparse
import csv
import html
import json
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .characteristics_research import normalized
from .house_characteristics import TRAITS as SCIENTIFIC_TRAITS
from .house_characteristics import write_csv
from .storage import fingerprint, read_rows, write_json, write_rows

BASELINE = "data/biographical-research-baseline.json"
JOURNAL = "data/biographical-research.json"
RESULTS = "results/biographical-research"
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
)
FAMILIES = (
    "campaign",
    "ballotpedia_questionnaire",
    "official_biography",
    "local_profile",
    "university_employer_professional",
    "earlier_biography",
)
BASE_COMMIT = "a9146a6eb08288f24bdb2092e121972e44a542f8"


def load_json(path, default):
    return json.loads(path.read_text()) if path.exists() else default


def load_journals(root):
    root = Path(root)
    paths = [root / JOURNAL]
    paths.extend(
        p
        for p in sorted((root / "data").glob("biographical-research-*.json"))
        if p.name != Path(BASELINE).name
    )
    merged = {
        "documents": [],
        "searches": [],
        "completed_candidates": [],
        "withheld_documents": [],
    }
    inputs = []
    for path in paths:
        if not path.exists():
            continue
        journal = load_json(path, {})
        if not all(key in journal for key in ("documents", "searches", "completed_candidates")):
            raise ValueError(f"Missing research journal sections: {path.name}")
        for key in merged:
            merged[key].extend(journal.get(key, []))
        inputs.append(path.relative_to(root).as_posix())
    return merged, inputs


def source_key(url):
    parts = urlsplit(url)
    return (
        (parts.hostname or "").lower().removeprefix("www."),
        unquote(parts.path).rstrip("/"),
        parts.query,
    )


def query_kind(search):
    return search.get(
        "query_kind",
        "source_followup" if search.get("method") == "underlying_page_review" else "search_query",
    )


def freeze(root):
    root = Path(root)
    if (root / BASELINE).exists():
        return load_json(root / BASELINE, {})
    paths = {
        root / "results/house/candidates.jsonl.gz",
        root / "results/house/source-inputs.jsonl.gz",
        root / "audits/house-characteristics-v9-release.json",
    }
    for version in range(1, 10):
        for folder in ("results", "publication"):
            paths.update(
                p
                for p in (root / folder / f"house-characteristics-v{version}").rglob("*")
                if p.is_file()
            )
        paths.update(
            p
            for p in (root / "publication" / f"characteristics-v{version}").rglob("*")
            if p.is_file()
        )
    paths.update(p for p in (root / "data").glob("house-characteristics*") if p.is_file())
    candidates = read_rows(root / "results/house/candidates.jsonl.gz")
    if len(candidates) != 1284 or len({c["candidate_id"] for c in candidates}) != 1284:
        raise ValueError("Changed retained candidate roster")
    baseline = {
        "commit": BASE_COMMIT,
        "candidates": len(candidates),
        "democrats": sum(c["party"] == "Democratic" for c in candidates),
        "traits": list(TRAITS),
        "protected_sha256": {
            p.relative_to(root).as_posix(): fingerprint(p)["sha256"] for p in sorted(paths)
        },
    }
    write_json(root / BASELINE, baseline)
    return baseline


def verify_frozen(root, baseline):
    for name, digest in baseline["protected_sha256"].items():
        if fingerprint(Path(root) / name)["sha256"] != digest:
            raise ValueError(f"Changed protected scientific input/output: {name}")


def validated_documents(journal, candidates):
    documents = {}
    observations = {}
    reviewed_sources = set()
    for document in journal.get("documents", []):
        key = document["id"]
        original = (document["candidate_id"], source_key(document["url"]))
        if key in documents or original in reviewed_sources:
            raise ValueError(f"Duplicate document review: {key}")
        reviewed_sources.add(original)
        candidate = candidates.get(document["candidate_id"])
        if not candidate or any(
            str(document[k]) != str(candidate[k])
            for k in ("name", "state", "district", "party", "contest_id")
        ):
            raise ValueError(f"Unqualified native identity: {key}")
        if (
            document["family"] not in FAMILIES
            or urlsplit(document["url"]).scheme not in {"https", "http"}
            or document["identity_status"] != "verified"
            or not document["identity_qualification"]
            or not document["identity_fragments"]
        ):
            raise ValueError(f"Unsupported source identity: {key}")
        text = normalized("\n".join(document["source_excerpts"]))
        if sum(len(s.split()) for s in document["source_excerpts"]) > 25:
            raise ValueError(f"Excessive retained source quotation: {key}")
        if not all(normalized(f) in text for f in document["identity_fragments"]):
            raise ValueError(f"Missing literal identity evidence: {key}")
        if not set(document["traits_reviewed"]) <= set(TRAITS):
            raise ValueError(f"Unexpected reviewed trait: {key}")
        seen = set()
        for claim in document["claims"]:
            if (
                claim["trait"] not in document["traits_reviewed"]
                or claim["trait"] in seen
                or claim["factual_status"] not in {"qualified", "partial", "conflicting"}
                or not claim["source_fragment"]
                or normalized(claim["source_fragment"]) not in text
                or not all(
                    normalized(fragment) in text
                    for fragment in claim.get("supporting_fragments", [])
                )
                or not claim["value"]
                or not claim["precision"]
                or "factual_reference_date" not in claim
            ):
                raise ValueError(f"Unsupported literal claim: {key}")
            seen.add(claim["trait"])
            observations.setdefault((candidate["candidate_id"], claim["trait"]), []).append(
                {
                    **claim,
                    "source_id": key,
                    "url": document["url"],
                    "publication_date": document["publication_date"],
                    "source_date_note": document.get("source_date_note", ""),
                    "accessed_at": document["accessed_at"],
                    "identity_qualification": document["identity_qualification"],
                    "original_bytes_acquired": document["original_bytes_acquired"],
                    "acquisition_origin": document.get(
                        "acquisition_origin", "current_public_page_review"
                    ),
                    "analytical_eligibility": "not_promoted_to_frozen_scientific_models",
                    "prediction_time_availability": "not_established_by_retrieval_date",
                }
            )
        documents[key] = document
    return documents, observations


def research_states(journal, candidates, documents):
    searches = {}
    reviews = {}
    for search in journal.get("searches", []):
        if (
            search["candidate_id"] not in candidates
            or search["family"] not in FAMILIES
            or not search["query"]
            or not search["searched_at"]
            or search["outcome"]
            not in {
                "leads_found",
                "no_qualifying_results",
                "access_failure",
                "result_mapping_not_retained",
            }
            or search["outcome"] == "leads_found"
            and not search.get("underlying_urls")
        ):
            raise ValueError("Invalid candidate-specific search")
        searches.setdefault(search["candidate_id"], []).append(search)
    for document in documents.values():
        reviews.setdefault(document["candidate_id"], []).append(document)
    completed = set()
    for completion in journal.get("completed_candidates", []):
        key = completion["candidate_id"]
        found = searches.get(key, [])
        if key not in candidates or key in completed:
            raise ValueError("Unknown or duplicate completed person")
        families = {
            r["family"]
            for r in found
            if query_kind(r) != "reconstructed_historical_description"
            and r["outcome"] != "result_mapping_not_retained"
        }
        reviewed = {t for d in reviews.get(key, []) for t in d["traits_reviewed"]}
        reviewed.update(completion.get("trait_findings", {}))
        if (
            families != set(FAMILIES)
            or reviewed != set(TRAITS)
            or completion.get("actionable_leads_remaining", True)
            or not completion.get("extraction_review")
        ):
            raise ValueError(f"Unfinished research cannot be called complete: {key}")
        for search in found:
            reviewed_urls = {d["url"] for d in reviews.get(key, [])}
            disposed = {
                url
                for url, disposition in search.get("lead_dispositions", {}).items()
                if isinstance(disposition, dict)
                and disposition.get("status")
                in {
                    "reviewed_no_requested_facts",
                    "access_failure",
                    "identity_rejected",
                    "duplicate_reviewed_original",
                }
                and disposition.get("reason")
            }
            if not set(search.get("underlying_urls", [])) <= reviewed_urls | disposed:
                raise ValueError(f"Unreviewed underlying research lead: {key}")
        completed.add(key)
    return searches, reviews, completed


def frozen_support(root):
    path = Path(root) / ("results/house-characteristics-v9/coverage-by-party-and-incumbency.csv")
    support = defaultdict(Counter)
    if path.exists():
        with path.open(newline="") as stream:
            for row in csv.DictReader(stream):
                group = row["baseline_incumbency_group"].replace("unknown_incumbency", "unresolved")
                for party in ("all", row["party"]):
                    for inc in ("all", group):
                        cell = support[(row["trait"], party, inc)]
                        cell["fitted_unchanged"] += int(row["fitted_after"])
                        cell["prediction_supported_unchanged"] += int(
                            row["full_fit_prediction_supported"]
                        )
    return support


def trait_counts(cells):
    return {
        "denominator": len(cells),
        "factual_before": sum(r["baseline_factual_qualified"] for r in cells),
        "factual_after": sum(r["factual_qualified"] for r in cells),
        "analytical_eligible_unchanged": sum(r["baseline_analytical_eligible"] for r in cells),
        "unknown_without_new_evidence": sum(
            r["baseline_status"] == "unknown" and not r["new_claims"] for r in cells
        ),
        "without_qualified_factual_value": sum(
            not r["factual_qualified"] and r["factual_status"] != "structural_inapplicability"
            for r in cells
        ),
        "conflicting_fields": sum(r["factual_status"] == "conflicting_evidence" for r in cells),
        "fields_with_unresolved_detail_conflicts": sum(
            bool(r["unresolved_detail_conflicts"]) for r in cells
        ),
        "structurally_inapplicable": sum(
            r["factual_status"] == "structural_inapplicability" for r in cells
        ),
        "held_source_fields": sum(bool(r["held_source_leads"]) for r in cells),
        "first_evidence_fields": sum(r["new_first_evidence"] for r in cells),
        "first_evidence_including_retained_original": sum(
            r["new_first_evidence"]
            and any(
                c["acquisition_origin"] == "retained_source_reextracted" for c in r["new_claims"]
            )
            for r in cells
        ),
        "first_qualified_fields": sum(r["first_qualified_factual_value"] for r in cells),
        "previous_reports_newly_qualified": sum(
            r["reported_evidence_newly_qualified"] for r in cells
        ),
        "supplementary_evidence_fields": sum(
            bool(r["new_claims"]) and not r["new_first_evidence"] for r in cells
        ),
        "partial_or_imprecise_fields": sum(r["partial_evidence"] for r in cells),
    }


def build(root):
    root = Path(root)
    baseline = freeze(root)
    verify_frozen(root, baseline)
    candidates = {
        r["candidate_id"]: r for r in read_rows(root / "results/house/candidates.jsonl.gz")
    }
    old = {
        (r["candidate_id"], r["trait"]): r
        for r in read_rows(root / "results/house-characteristics-v9/candidate-traits.jsonl.gz")
    }
    journal, journal_inputs = load_journals(root)
    documents, observations = validated_documents(journal, candidates)
    searches, reviews, completed = research_states(journal, candidates, documents)
    held = {}
    for document in journal["withheld_documents"]:
        if document["candidate_id"] not in candidates or not document["reason"]:
            raise ValueError("Invalid withheld source lead")
        for trait in document["traits_pending_verification"]:
            if trait not in TRAITS:
                raise ValueError("Invalid withheld source trait")
            held.setdefault((document["candidate_id"], trait), []).append(
                {
                    "source_id": document["id"],
                    "url": document["url"],
                    "status": document["status"],
                    "reason": document["reason"],
                }
            )
    rows = []
    profiles = []
    for key, candidate in candidates.items():
        inc = old[(key, "incumbency")]
        group = (
            "unresolved"
            if not inc["analysis_eligible"]
            else "incumbent"
            if inc["analysis_value"]
            else "nonincumbent"
        )
        state = (
            "completed"
            if key in completed
            else "in_progress"
            if key in searches or key in reviews
            else "not_yet_researched"
        )
        profile = {
            k: candidate[k] for k in ("candidate_id", "name", "state", "district", "party")
        } | {
            "incumbency_group": group,
            "research_status": state,
            "families_searched": sorted(
                {
                    r["family"]
                    for r in searches.get(key, [])
                    if query_kind(r) != "reconstructed_historical_description"
                    and r["outcome"] != "result_mapping_not_retained"
                }
            ),
            "documents_reviewed": len(reviews.get(key, [])),
            "campaign_websites": candidate["campaign_websites"],
        }
        profiles.append(profile)
        for trait in SCIENTIFIC_TRAITS:
            previous = old[(key, trait)]
            claims = observations.get((key, trait), [])
            qualified = any(c["factual_status"] == "qualified" for c in claims)
            conflict = any(c["factual_status"] == "conflicting" for c in claims)
            fact_status = (
                "conflicting_evidence"
                if conflict
                else "qualified_value"
                if previous["factual_qualified"] or qualified
                else "partial_or_imprecise_evidence"
                if claims or previous["status"] == "dated_reported"
                else "structural_inapplicability"
                if previous["status"] == "inapplicable"
                else "unresolved_retained_evidence"
                if previous["status"] == "uncertain"
                else "no_qualifying_evidence_after_documented_search"
                if key in completed
                else "not_yet_researched"
                if state == "not_yet_researched"
                else "unresolved_search_in_progress"
            )
            rows.append(
                profile
                | {
                    "trait": trait,
                    "factual_status": fact_status,
                    "baseline_status": previous["status"],
                    "baseline_factual_qualified": previous["factual_qualified"],
                    "baseline_value": previous["value"],
                    "baseline_source_recorded_value": previous["source_recorded_value"],
                    "baseline_evidence": previous["evidence"],
                    "baseline_uncertainty": previous["uncertainty"],
                    "baseline_timing_status": previous["timing_status"],
                    "baseline_coding_status": previous["coding_status"],
                    "factual_qualified": not conflict
                    and (previous["factual_qualified"] or qualified),
                    "partial_evidence": any(c["factual_status"] == "partial" for c in claims),
                    "baseline_analytical_eligible": previous["analysis_eligible"],
                    "analytical_timing_exclusion": not previous["analysis_eligible"],
                    "analytical_exclusion_reason": previous["eligibility_reason"],
                    "new_claims": claims,
                    "unresolved_detail_conflicts": [
                        c["unresolved_details"] for c in claims if c.get("unresolved_details")
                    ],
                    "held_source_leads": held.get((key, trait), []),
                    "new_first_evidence": previous["status"] == "unknown" and bool(claims),
                    "first_qualified_factual_value": previous["status"] == "unknown"
                    and qualified
                    and not conflict,
                    "reported_evidence_newly_qualified": previous["status"] != "unknown"
                    and not previous["factual_qualified"]
                    and qualified
                    and not conflict,
                    "candidate_has_source_access_failure": any(
                        s["outcome"] == "access_failure" for s in searches.get(key, [])
                    ),
                    "trait_reviewed_in_documents": any(
                        trait in d["traits_reviewed"] for d in reviews.get(key, [])
                    ),
                }
            )
    profiles.sort(
        key=lambda r: (
            r["party"] != "Democratic",
            {"nonincumbent": 0, "unresolved": 1, "incumbent": 2}[r["incumbency_group"]],
            r["state"],
            r["name"],
        )
    )
    groups = []
    trait_groups = []
    support = frozen_support(root)
    for party in ("all", *sorted({r["party"] for r in profiles})):
        for inc in ("all", "incumbent", "nonincumbent", "unresolved"):
            selected = [
                p
                for p in profiles
                if (party == "all" or p["party"] == party)
                and (inc == "all" or p["incumbency_group"] == inc)
            ]
            ids = {p["candidate_id"] for p in selected}
            cells = [r for r in rows if r["candidate_id"] in ids]
            groups.append(
                {
                    "party": party,
                    "incumbency_group": inc,
                    "candidates": len(selected),
                    "completed_pass": sum(p["research_status"] == "completed" for p in selected),
                    "in_progress": sum(p["research_status"] == "in_progress" for p in selected),
                    "not_yet_researched": sum(
                        p["research_status"] == "not_yet_researched" for p in selected
                    ),
                    "documents_reviewed": sum(p["documents_reviewed"] for p in selected),
                    "first_evidence_fields": sum(r["new_first_evidence"] for r in cells),
                    "first_qualified_fields": sum(
                        r["first_qualified_factual_value"] for r in cells
                    ),
                }
            )
            for trait in SCIENTIFIC_TRAITS:
                trait_cells = [r for r in cells if r["trait"] == trait]
                trait_groups.append(
                    {
                        "party": party,
                        "incumbency_group": inc,
                        "trait": trait,
                        **trait_counts(trait_cells),
                        "fitted_unchanged": support[(trait, party, inc)]["fitted_unchanged"],
                        "prediction_supported_unchanged": support[(trait, party, inc)][
                            "prediction_supported_unchanged"
                        ],
                    }
                )
    progress = [
        r
        for r in trait_groups
        if r["party"] in {"all", "Democratic"} and r["incumbency_group"] == "all"
    ]
    output = root / RESULTS
    output.mkdir(parents=True, exist_ok=True)
    write_rows(output / "candidate-trait-ledger.jsonl.gz", rows)
    write_csv(
        output / "candidate-trait-ledger.csv",
        [
            {
                k: json.dumps(v, sort_keys=True) if isinstance(v, (dict, list)) else v
                for k, v in r.items()
            }
            for r in rows
        ],
    )
    write_csv(output / "candidate-research-status.csv", profiles)
    write_csv(
        output / "remaining-research-queue.csv",
        [
            profile
            | {
                "source_families_not_searched": json.dumps(
                    sorted(set(FAMILIES) - set(profile["families_searched"]))
                ),
                "background_traits_without_qualified_values": json.dumps(
                    [
                        r["trait"]
                        for r in rows
                        if r["candidate_id"] == profile["candidate_id"]
                        and r["trait"] in TRAITS
                        and not r["factual_qualified"]
                    ]
                ),
            }
            for profile in profiles
            if profile["research_status"] != "completed"
        ],
    )
    write_csv(output / "coverage-by-party-and-incumbency.csv", groups)
    write_csv(output / "trait-coverage-by-party-and-incumbency.csv", trait_groups)
    write_csv(output / "trait-progress.csv", progress)
    write_json(output / "source-provenance.json", journal)
    summary = {
        "baseline_commit": BASE_COMMIT,
        "candidates": len(candidates),
        "trait_cells": len(rows),
        "research_status": dict(Counter(p["research_status"] for p in profiles)),
        "documents_reviewed": len(documents),
        "withheld_source_records": len(journal["withheld_documents"]),
        "new_claims": sum(len(r["new_claims"]) for r in rows),
        "first_evidence_fields": sum(r["new_first_evidence"] for r in rows),
        "first_qualified_fields": sum(r["first_qualified_factual_value"] for r in rows),
        "acquisition_complete": len(completed) == len(candidates),
        "frozen_models_changed": False,
    }
    write_json(output / "summary.json", summary)
    render(root, rows, profiles, summary, progress)
    write_json(
        output / "manifest.json",
        {
            "inputs": {
                name: fingerprint(root / name)
                for name in (
                    BASELINE,
                    *journal_inputs,
                    "results/house-characteristics-v9/candidate-traits.jsonl.gz",
                    "results/house-characteristics-v9/coverage-by-party-and-incumbency.csv",
                    "which_candidate/biographical_research.py",
                    "which_candidate/biographical_acquisition.py",
                )
                if (root / name).exists()
            },
            "files": {
                p.relative_to(root).as_posix(): fingerprint(p)
                for p in (
                    *output.iterdir(),
                    root / "publication/biographical-research/report.html",
                )
                if p.is_file() and p.name != "manifest.json"
            },
        },
    )
    return summary


def render(root, rows, profiles, summary, progress):
    output = root / "publication/biographical-research"
    output.mkdir(parents=True, exist_ok=True)

    def esc(value):
        return html.escape(str(value), quote=True)

    by_candidate = {}
    for row in rows:
        by_candidate.setdefault(row["candidate_id"], []).append(row)
    body = [
        '<!doctype html><html lang="en"><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>Candidate biographical research</title>",
        "<style>body{font:16px/1.5 system-ui;max-width:76rem;margin:auto;padding:1rem}"
        "table{border-collapse:collapse;width:100%}td,th{padding:.4rem;text-align:left;"
        "vertical-align:top;border-bottom:1px solid #ccc}details{margin:.5rem 0}"
        "a,td,p{overflow-wrap:anywhere}.scroll{overflow-x:auto}</style>",
        "<h1>Candidate-by-candidate biographical research</h1>",
        "<p><strong>Acquisition is unfinished.</strong> Downloading a page, a missing database "
        "row or an existing analytical disposition is not a completed research pass. "
        "Factual evidence, precision, timing and model eligibility are separate.</p>",
        "<p>The fifteen scientific traits are retained, but this pass researches ten "
        "background traits. New claims are not promoted into frozen scientific models. "
        "A known narrow fact does not resolve every biographical detail. Dated age and "
        "birth-year evidence can remain partial; institutional affiliation is not inferred "
        "religious identity. Partial and detail-conflict flags can coexist with a qualified "
        "narrow fact. Unsearched people remain unsearched.</p>",
        "<p>Search provenance distinguishes executed search strings, underlying-page "
        "follow-ups and reconstructed historical descriptions. Reconstructed descriptions "
        "do not establish that a source family was searched and cannot complete a pass. "
        "Retained-original re-extraction is identified separately from current page review; "
        "neither implies that the original source was newly acquired.</p>",
        f"<p>{summary['candidates']:,} candidates; {summary['documents_reviewed']} documents "
        f"reviewed; {summary['first_evidence_fields']} previously unknown fields with new "
        f"evidence, of which {summary['first_qualified_fields']} now have a qualified value. "
        f"Research passes: {summary['research_status'].get('completed', 0):,} completed; "
        f"{summary['research_status'].get('in_progress', 0):,} in progress; "
        f"{summary['research_status'].get('not_yet_researched', 0):,} not yet researched. "
        "A completed research pass can still leave unknown facts.</p>",
        '<p><a href="../characteristics-v9/report.html">Frozen scientific report</a> | '
        '<a href="../../results/biographical-research/candidate-trait-ledger.csv">'
        "Complete research ledger</a> | "
        '<a href="../../results/biographical-research/source-provenance.json">'
        "Searches and source passages</a> | "
        '<a href="../../docs/BIOGRAPHICAL_RESEARCH.md">'
        "Complete download and reproduction instructions</a></p>",
        '<p><a href="../../results/biographical-research/'
        'trait-coverage-by-party-and-incumbency.csv">All fifteen traits by party and '
        "known/unresolved incumbency</a>. Incumbency is never inferred from missing rows. "
        "Fitted and prediction-supported counts below are unchanged V9 scientific samples, "
        "not newly eligible people.</p>",
        "<h2>Factual progress</h2><p>First evidence includes accepted partial or conflicting "
        "claims, not just qualified values. Retained-original contributions identify fields "
        "with at least one re-extracted claim and can overlap current-page evidence. "
        "Qualifying an already reported fact is not acquisition of a previously unknown "
        'field.</p><div class="scroll"><table>'
        "<tr><th>Population</th><th>Trait</th><th>Cohort</th><th>Before</th><th>After</th>"
        "<th>Analytical</th><th>Fitted</th><th>Prediction supported</th>"
        "<th>First evidence</th><th>Retained original contributed</th>"
        "<th>First qualified</th><th>Existing report newly qualified</th><th>Partial</th>"
        "<th>Without qualified value</th><th>Conflicting</th><th>Inapplicable</th></tr>",
    ]
    for row in progress:
        body.append(
            "<tr>"
            + "".join(
                f"<td>{esc(row[k])}</td>"
                for k in (
                    "party",
                    "trait",
                    "denominator",
                    "factual_before",
                    "factual_after",
                    "analytical_eligible_unchanged",
                    "fitted_unchanged",
                    "prediction_supported_unchanged",
                    "first_evidence_fields",
                    "first_evidence_including_retained_original",
                    "first_qualified_fields",
                    "previous_reports_newly_qualified",
                    "partial_or_imprecise_fields",
                    "without_qualified_factual_value",
                    "conflicting_fields",
                    "structurally_inapplicable",
                )
            )
            + "</tr>"
        )
    body.append("</table></div><h2>All retained candidates</h2>")
    for candidate in profiles:
        body.append(
            f'<details id="candidate-{esc(candidate["candidate_id"])}"><summary>'
            f"{esc(candidate['name'])} ({esc(candidate['party'])}, "
            f"{esc(candidate['state'])} {esc(candidate['district'])}) "
            f"— {esc(candidate['research_status'])}</summary>"
        )
        for row in by_candidate[candidate["candidate_id"]]:
            body.append(f"<h3>{esc(row['trait'])}</h3><p>{esc(row['factual_status'])}</p>")
            if row["unresolved_detail_conflicts"]:
                body.append(
                    "<p><strong>Unresolved detail conflicts:</strong> "
                    f"{esc(json.dumps(row['unresolved_detail_conflicts']))}</p>"
                )
            for lead in row["held_source_leads"]:
                body.append(
                    f"<p><strong>Held, not qualified evidence:</strong> "
                    f'<a href="{esc(lead["url"])}">Source lead</a>: {esc(lead["reason"])}</p>'
                )
            if row["baseline_factual_qualified"]:
                body.append(
                    f"<p>Previously qualified: {esc(json.dumps(row['baseline_value']))}. "
                    "The unchanged scientific ledger retains its original evidence and "
                    "analytical qualifications.</p>"
                )
            for claim in row["new_claims"]:
                body.append(
                    f"<p>{esc(json.dumps(claim['value'], ensure_ascii=False))} "
                    f"[{esc(claim['precision'])}]. "
                    f'<a href="{esc(claim["url"])}">Source</a>: '
                    f"{esc('; '.join([claim['source_fragment'], *claim.get('supporting_fragments', [])]))}. "
                    f"Reference date: {esc(claim['factual_reference_date'])}; "
                    f"publication date: {esc(claim['publication_date'])}. "
                    f"{esc(claim['source_date_note'])} "
                    f"{esc(claim.get('qualification', ''))} "
                    f"Review origin: {esc(claim['acquisition_origin'])}.</p>"
                )
        body.append("</details>")
    body.append("</html>")
    (output / "report.html").write_text("\n".join(body))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    print(json.dumps(build(Path(__file__).resolve().parents[1]), indent=2))
