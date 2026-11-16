"""Standardize descriptive Democratic candidate evidence without creating model features."""

import json
from pathlib import Path

from .candidate_research import background_field_coverage
from .storage import fingerprint, write_json, write_rows

IDENTITY = ("candidate_id", "contest_id", "name", "state", "district", "party")
UNKNOWN = {
    "",
    "unknown",
    "n/a",
    "not available",
    "not provided",
    "no response",
    "no response provided",
    "none provided",
    "refused",
    "declined",
}
PROFESSIONAL_FIELDS = {
    "professional_history",
    "occupation",
    "occupational_background",
    "business_experience",
}
ELECTED_OFFICE_FIELDS = {"elected_office_experience"}
GOVERNMENT_FIELDS = {"prior_office", "governmental_experience", "public_service_experience"}
VOLUNTEER_FIELDS = {"volunteer_experience", "unpaid_service"}


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from _strings(item)


def _unknown(value):
    values = list(_strings(value))
    return not values or all(item.strip().casefold() in UNKNOWN for item in values)


def _explicit_status(observation, keys, allowed, default):
    evidence = observation.get("evidence")
    for container in (
        observation.get("value"),
        evidence,
        evidence.get("field_review") if isinstance(evidence, dict) else None,
    ):
        if not isinstance(container, dict):
            continue
        for key in keys:
            value = container.get(key)
            if isinstance(value, str) and value in allowed:
                return value
    return default


def _source_urls(value):
    return sorted(
        {
            text
            for text in _strings(value)
            if text.startswith("https://") or text.startswith("http://")
        }
    )


def standardize_observation(observation):
    """Classify only explicit source fields and metadata, never biographical prose."""
    field = observation["field"]
    if field == "education":
        trait = "education"
        detail = {
            "completion_status": _explicit_status(
                observation,
                ("completion_status", "degree_status"),
                {
                    "degree_earned",
                    "certificate_earned",
                    "attendance_only",
                    "completion_unknown",
                    "conflicting",
                },
                "completion_unknown",
            )
        }
    elif field in PROFESSIONAL_FIELDS:
        trait = "professional_history"
        detail = {
            "relationship_status": _explicit_status(
                observation,
                ("relationship_status", "employment_status", "remuneration_status"),
                {
                    "paid_employment",
                    "self_employment",
                    "unpaid_or_volunteer",
                    "relationship_unknown",
                    "conflicting",
                },
                "relationship_unknown",
            )
        }
    elif field in VOLUNTEER_FIELDS:
        trait = "volunteer_or_unpaid_service"
        detail = {"relationship_status": "unpaid_or_volunteer"}
    elif field in ELECTED_OFFICE_FIELDS:
        trait = "elected_office"
        detail = {"office_status": "elected_office_reported"}
    elif field in GOVERNMENT_FIELDS:
        trait = "government_or_public_service"
        detail = {"office_status": "elected_or_employment_status_unknown"}
    elif field == "military_service":
        trait = "military_service"
        detail = {
            "service_status": (
                "service_unknown"
                if _unknown(observation.get("value"))
                else "military_service_reported"
            )
        }
    else:
        trait = "other_background_evidence"
        detail = {}
    explicit = _explicit_status(
        observation,
        ("claim_status", "review_status"),
        {"supported", "unknown", "conflicting", "review_required"},
        None,
    )
    claim_status = explicit or ("unknown" if _unknown(observation.get("value")) else "reported")
    return {
        "trait": trait,
        "claim_status": claim_status,
        **detail,
        "raw_field": field,
        "raw_value": observation.get("value"),
        "source_kind": observation.get("source_kind"),
        "source_year": observation.get("source_year"),
        "observation_date": observation.get("observation_date"),
        "qualification": observation.get("qualification"),
        "source_urls": _source_urls(observation.get("evidence")),
        "evidence": observation.get("evidence"),
        "model_ready": False,
    }


def democratic_trait_rows(profiles, expected_population=449):
    rows = []
    identities = set()
    for profile in profiles:
        if profile["party"] != "Democratic":
            continue
        identity = tuple(profile[key] for key in IDENTITY[:2])
        if identity in identities:
            raise ValueError(f"Duplicate Democratic candidate-contest identity: {identity}")
        identities.add(identity)
        observations = profile.get("acquired_background_observations", [])
        claims = [standardize_observation(row) for row in observations]
        coverage = background_field_coverage(observations)
        statuses = {row["claim_status"] for row in claims}
        rows.append(
            {
                **{key: profile[key] for key in IDENTITY},
                "observation_count": len(observations),
                **coverage,
                "review_status": (
                    "contains_explicit_conflict"
                    if "conflicting" in statuses
                    else "review_required"
                    if "review_required" in statuses
                    or any(
                        any(
                            marker in str(row.get("qualification", "")).casefold()
                            for marker in (
                                "require_review",
                                "requires_review",
                                "unreviewed",
                                "machine_extracted",
                            )
                        )
                        for row in observations
                    )
                    else "evidence_available"
                    if claims
                    else "no_observations"
                ),
                "unknown_claim_count": sum(row["claim_status"] == "unknown" for row in claims),
                "conflicting_claim_count": sum(
                    row["claim_status"] == "conflicting" for row in claims
                ),
                "standardized_claims": claims,
                "source_qualifications": sorted(
                    {str(row["qualification"]) for row in observations if row.get("qualification")}
                ),
                "source_urls": sorted({url for claim in claims for url in claim["source_urls"]}),
                "member_or_incoming_background": {
                    key: profile.get(key)
                    for key in (
                        "date_of_birth",
                        "education",
                        "professional_history",
                        "military_service",
                        "religion_literal",
                        "religion_status",
                    )
                },
                "member_or_incoming_background_evidence": profile.get("background_evidence", []),
                "machine_biography_fields_unreviewed": profile.get(
                    "machine_biography_fields_unreviewed", []
                ),
                "background_research": profile.get("background_research"),
                "background_discovery_repair": profile.get("background_discovery_repair"),
                "targeted_background_research": profile.get("democratic_background_research"),
                "campaign_websites": profile.get("campaign_websites", []),
                "participation_source_context": profile.get("participation_source_context"),
                "descriptive_only": True,
                "model_ready": False,
            }
        )
    rows.sort(key=lambda row: (row["state"], row["district"], row["name"], row["candidate_id"]))
    if expected_population is not None and len(rows) != expected_population:
        raise ValueError(
            f"Expected {expected_population} Democratic candidate-contest records, found {len(rows)}"
        )
    return rows


def write_trait_outputs(output, rows, csv_bytes, input_paths):
    output = Path(output)
    write_rows(output / "democratic-candidate-traits.jsonl.gz", rows)
    (output / "democratic-candidate-traits.csv").write_bytes(csv_bytes(rows))
    provenance = {
        "schema": "which_candidate.democratic_candidate_traits.v1",
        "population": len(rows),
        "identity": list(IDENTITY),
        "observation_count": sum(row["observation_count"] for row in rows),
        "model_ready": False,
        "interpretation": (
            "Retrospective descriptive evidence only. Exact source fields and explicit structured "
            "metadata are standardized; prose is not keyword-classified. Missing evidence is "
            "unknown, not a negative trait. Education does not imply completion, professional "
            "history does not imply paid employment, public service does not imply elected office, "
            "and non-military anecdotes do not imply military service."
        ),
        "inputs": {name: fingerprint(path) for name, path in input_paths.items()},
    }
    registry_path = input_paths.get("data/democratic-background-research.json")
    if registry_path:
        audit = research_audit(Path(registry_path).parent.parent, rows)
        write_json(output / "democratic-background-audit.json", audit)
        provenance["research_audit"] = {
            key: audit[key]
            for key in (
                "population",
                "targeted_candidates",
                "newly_covered_people",
                "people_with_newly_filled_fields",
                "newly_filled_fields",
                "remaining_missing_field_counts",
                "rejected_identity_match_count",
            )
        }
    write_json(output / "democratic-candidate-traits-provenance.json", provenance)
    return provenance


def research_audit(root, rows):
    root = Path(root)
    baseline = json.loads((root / "data/democratic-background-gap-baseline.json").read_text())
    registry = json.loads((root / "data/democratic-background-research.json").read_text())
    before = {
        (row["candidate_id"], row["contest_id"]): row for row in baseline["baseline_coverage"]
    }
    after = {(row["candidate_id"], row["contest_id"]): row for row in rows}
    if before.keys() != after.keys():
        raise ValueError("Democratic audit population differs from the frozen baseline")
    registered = {row["candidate_id"]: row for row in registry["candidates"]}
    if set(registered) != {row["candidate_id"] for row in baseline["candidates"]}:
        raise ValueError("Democratic audit must account for every targeted candidate")
    outcomes = []
    for candidate in baseline["candidates"]:
        identity = (candidate["candidate_id"], candidate["contest_id"])
        current = after[identity]
        research = registered[candidate["candidate_id"]]
        if any(research[key] != candidate[key] for key in IDENTITY):
            raise ValueError("Democratic research audit identity mismatch")
        remaining = sorted(
            set(candidate["target_fields"]) & set(current["remaining_background_fields"])
        )
        if remaining != research["remaining_fields"]:
            raise ValueError("Research disposition disagrees with normalized field coverage")
        outcomes.append(
            {
                **{key: candidate[key] for key in IDENTITY},
                "target_fields": candidate["target_fields"],
                "newly_filled_fields": sorted(set(candidate["target_fields"]) - set(remaining)),
                "remaining_fields": remaining,
                "limitations": research["limitations"],
                "rejected_matches": research["rejected_matches"],
            }
        )
    fields = ("education", "professional_history", "prior_office", "military_service")
    missing = {
        field: [
            {key: row[key] for key in IDENTITY}
            for row in rows
            if field in row["remaining_background_fields"]
        ]
        for field in fields
    }
    return {
        "schema": "which_candidate.democratic_background_audit.v1",
        "baseline_commit": baseline["baseline_commit"],
        "population": len(rows),
        "targeted_candidates": len(outcomes),
        "baseline_missing_education": baseline["missing_education"],
        "baseline_missing_professional_history": baseline["missing_professional_history"],
        "baseline_overlap": baseline["overlap"],
        "newly_covered_people": sum(
            int(before[key]["observation_count"]) == 0 and row["observation_count"] > 0
            for key, row in after.items()
        ),
        "people_with_newly_filled_fields": sum(
            bool(row["newly_filled_fields"]) for row in outcomes
        ),
        "newly_filled_fields": {
            field: sum(field in row["newly_filled_fields"] for row in outcomes)
            for field in ("education", "professional_history")
        },
        "remaining_missing_field_counts": {field: len(values) for field, values in missing.items()},
        "remaining_missing_fields": missing,
        "rejected_identity_match_count": sum(len(row["rejected_matches"]) for row in outcomes),
        "outcomes": outcomes,
        "model_ready": False,
        "interpretation": (
            "Field availability is not a complete biography or independent credential verification. "
            "Attendance, completion, employment relationships, dates, subject wording and conflicting "
            "claims remain source-qualified in the trait table and research registry. No models refitted."
        ),
    }
