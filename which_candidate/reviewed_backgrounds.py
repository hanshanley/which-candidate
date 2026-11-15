"""Verify reviewed candidate facts against pinned pages and explicit subject context."""

import json
import re
from pathlib import Path

from .incoming_biographies import visible_text
from .storage import confined, fingerprint

FIELDS = {"education", "professional_history", "prior_office", "military_service"}
KINDS = {"candidate_campaign_self_report", "official_previous_office_biography"}
CONTEXT = ("candidate_id", "contest_id", "name", "state", "district", "party")


def normalized(text):
    return re.sub(r"\s+", " ", text.replace("\u2019", "'")).strip().casefold()


def reviewed_inputs(root):
    root = Path(root)
    annotations = root / "data/candidate-reviewed-backgrounds.json"
    if not annotations.exists():
        return {"reviewed_candidate_profiles": []}
    review = json.loads(annotations.read_text())
    manifest = json.loads((root / "data/candidate-acquisition.json").read_text())
    candidates = {row["candidate_id"]: row for row in manifest["candidates"]}
    sources = {row["id"]: row for row in manifest["sources"]}
    if len(candidates) != len(manifest["candidates"]) or len(sources) != len(manifest["sources"]):
        raise ValueError("Duplicate candidate or source in acquisition manifest")
    profiles, seen = [], set()
    for annotation in review["profiles"]:
        candidate = candidates[annotation["candidate_id"]]
        source_id = annotation["source_id"]
        key = (candidate["candidate_id"], candidate["contest_id"], source_id)
        if key in seen:
            raise ValueError("Duplicate reviewed candidate/source")
        seen.add(key)
        if normalized(annotation["name"]) != normalized(candidate["name"]):
            raise ValueError("Reviewed candidate has conflicting subject")
        if source_id not in candidate["source_ids"]:
            raise ValueError("Reviewed source belongs to a different candidate")
        source = sources[source_id]
        path = confined(root / "data/raw/candidate-backgrounds-20261115", Path(source["path"]).name)
        if path != confined(root, source["path"]):
            raise ValueError("Reviewed original is outside the candidate source cache")
        if fingerprint(path) != {key: source[key] for key in ("bytes", "sha256")}:
            raise ValueError("Reviewed candidate original changed")
        text = normalized(visible_text(path.read_bytes()))
        fields, support = annotation["fields"], annotation["support"]
        if not fields or set(fields) - FIELDS or set(support) != set(fields):
            raise ValueError("Unsupported or unanchored reviewed background field")
        for field, values in fields.items():
            fragments = support[field]
            fragments = [fragments] if isinstance(fragments, str) else fragments
            if (
                not isinstance(values, list)
                or not values
                or not all(isinstance(value, str) and value.strip() for value in values)
                or not isinstance(fragments, list)
                or not fragments
                or not all(
                    isinstance(fragment, str) and normalized(fragment) for fragment in fragments
                )
            ):
                raise ValueError("Reviewed background requires values and supporting fragments")
            for fragment in fragments:
                if normalized(fragment) not in text:
                    raise ValueError(
                        f"Reviewed support absent from {source_id}, {field}: {fragment}"
                    )
        kind = annotation.get("source_kind", "candidate_campaign_self_report")
        if kind not in KINDS:
            raise ValueError("Unsupported reviewed background source kind")
        profiles.append(
            {
                **{key: candidate[key] for key in CONTEXT},
                "fields": fields,
                "support": support,
                "source_kind": kind,
                "model_ready": False,
                "qualification": review["qualification"],
                "evidence": {
                    "source_id": source_id,
                    **{
                        key: source[key]
                        for key in (
                            "url",
                            "resolved_url",
                            "sha256",
                            "bytes",
                            "retrieved_at",
                            "publication_date",
                        )
                    },
                },
            }
        )
    return {"reviewed_candidate_profiles": profiles}


def matched_profiles(candidate, inputs):
    result = []
    for profile in inputs.get("reviewed_candidate_profiles", []):
        if profile["candidate_id"] != candidate["candidate_id"]:
            continue
        if any(profile[key] != candidate[key] for key in CONTEXT):
            raise ValueError("Reviewed background conflicts with candidate-contest context")
        if profile.get("model_ready") is not False:
            raise ValueError("Retrospectively reviewed background cannot become a model feature")
        result.append(profile)
    return result
