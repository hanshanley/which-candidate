"""Verify reviewed candidate facts against pinned pages and explicit subject context."""

import json
import re
from pathlib import Path

from pypdf import PdfReader

from .incoming_biographies import visible_text
from .storage import confined, fingerprint

FIELDS = {"education", "professional_history", "prior_office", "military_service"}
KINDS = {
    "candidate_campaign_self_report",
    "official_previous_office_biography",
    "candidate_supplied_voter_directory",
    "public_voter_directory_biography",
    "official_candidate_supplied_voter_guide",
    "official_candidate_supplied_ballot_designation",
    "party_published_candidate_biography",
    "professional_institution_biography",
    "endorsing_organization_biography",
    "news_reported_biography",
}
CONTEXT = ("candidate_id", "contest_id", "name", "state", "district", "party")


def normalized(text):
    return re.sub(r"\s+", " ", text.replace("\u2019", "'")).strip().casefold()


def reviewed_inputs(root, *, profiles=None):
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
    selected = review["profiles"] if profiles is None else profiles
    profiles, seen = [], set()
    for annotation in selected:
        if annotation.get("model_ready", False) is not False:
            raise ValueError("Retrospectively reviewed background cannot become a model feature")
        candidate = candidates[annotation["candidate_id"]]
        source_id = annotation["source_id"]
        key = (candidate["candidate_id"], candidate["contest_id"], source_id)
        if key in seen:
            raise ValueError("Duplicate reviewed candidate/source")
        seen.add(key)
        if normalized(annotation["name"]) != normalized(candidate["name"]):
            raise ValueError("Reviewed candidate has conflicting subject")
        if any(key in annotation and annotation[key] != candidate[key] for key in CONTEXT):
            raise ValueError("Reviewed annotation has conflicting candidate context")
        if source_id not in candidate["source_ids"]:
            raise ValueError("Reviewed source belongs to a different candidate")
        source = sources[source_id]
        path = confined(root, source["path"])
        if not path.is_relative_to(confined(root, "data/raw/candidate-backgrounds-20261115")):
            raise ValueError("Reviewed original is outside the candidate source cache")
        if fingerprint(path) != {key: source[key] for key in ("bytes", "sha256")}:
            raise ValueError("Reviewed candidate original changed")
        pages = annotation.get("pdf_pages")
        if source.get("media_type") == "application/pdf":
            reader = PdfReader(path)
            if not pages or not all(
                type(page) is int and 1 <= page <= len(reader.pages) for page in pages
            ):
                raise ValueError("Reviewed PDF requires explicit valid page references")
            text = normalized(" ".join(reader.pages[page - 1].extract_text() for page in pages))
        else:
            if pages is not None:
                raise ValueError("PDF page references require a PDF source")
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
                "qualification": annotation.get("qualification", review["qualification"]),
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
                    **({"pdf_pages": pages} if pages is not None else {}),
                    **{
                        key: source[key]
                        for key in ("media_type", "retrieval_method", "provider_reference")
                        if key in source
                    },
                },
            }
        )
    return {"reviewed_candidate_profiles": profiles}


def ingest(root, output=None):
    """Append validated changes to pinned normalized inputs, without historical originals."""
    from .house_candidates import build
    from .storage import read_rows

    root = Path(root)
    held = root / "results/house"
    manifest = json.loads((held / "manifest.json").read_text())
    for filename in ("source-inputs.jsonl.gz", "candidates.jsonl.gz"):
        if fingerprint(held / filename) != manifest["files"][filename]:
            raise ValueError(f"Changed normalized House inputs: {filename}")
    inputs = read_rows(held / "source-inputs.jsonl.gz")[0]
    candidates = {row["candidate_id"]: row for row in read_rows(held / "candidates.jsonl.gz")}
    review = json.loads((root / "data/candidate-reviewed-backgrounds.json").read_text())
    acquisition = json.loads((root / "data/candidate-acquisition.json").read_text())
    receipts = {row["id"]: row for row in acquisition["sources"]}
    contexts = {row["candidate_id"]: row for row in acquisition["candidates"]}
    if len(receipts) != len(acquisition["sources"]) or len(contexts) != len(
        acquisition["candidates"]
    ):
        raise ValueError("Duplicate candidate or source in acquisition manifest")
    existing = {}
    for profile in inputs.get("reviewed_candidate_profiles", []):
        matched_profiles(
            candidates[profile["candidate_id"]], {"reviewed_candidate_profiles": [profile]}
        )
        key = (profile["candidate_id"], profile["evidence"]["source_id"])
        if key in existing:
            raise ValueError("Duplicate normalized reviewed profile")
        existing[key] = profile
    pending, seen = [], set()
    for annotation in review["profiles"]:
        if annotation.get("model_ready", False) is not False:
            raise ValueError("Retrospectively reviewed background cannot become a model feature")
        key = (annotation["candidate_id"], annotation["source_id"])
        if key in seen:
            raise ValueError("Duplicate reviewed candidate/source")
        seen.add(key)
        candidate = candidates[annotation["candidate_id"]]
        context = contexts[annotation["candidate_id"]]
        if any(context[field] != candidate[field] for field in CONTEXT):
            raise ValueError("Acquisition conflicts with candidate-contest context")
        if annotation["source_id"] not in context["source_ids"]:
            raise ValueError("Reviewed source belongs to a different candidate")
        previous = existing.get(key)
        receipt = receipts[annotation["source_id"]]
        unchanged = previous is not None and all(
            (
                previous["fields"] == annotation["fields"],
                previous["support"] == annotation["support"],
                previous["source_kind"]
                == annotation.get("source_kind", "candidate_campaign_self_report"),
                previous["qualification"]
                == annotation.get("qualification", review["qualification"]),
                previous["name"] == annotation["name"],
                all(
                    field not in annotation or annotation[field] == candidate[field]
                    for field in CONTEXT
                ),
                previous["evidence"].get("pdf_pages") == annotation.get("pdf_pages"),
                all(
                    previous["evidence"].get(field) == receipt.get(field)
                    for field in ("media_type", "retrieval_method", "provider_reference")
                ),
                all(
                    previous["evidence"][field] == receipt[field]
                    for field in (
                        "url",
                        "resolved_url",
                        "sha256",
                        "bytes",
                        "retrieved_at",
                        "publication_date",
                    )
                ),
            )
        )
        if not unchanged:
            pending.append(annotation)
    validated = reviewed_inputs(root, profiles=pending)["reviewed_candidate_profiles"]
    for profile in validated:
        matched_profiles(
            candidates[profile["candidate_id"]], {"reviewed_candidate_profiles": [profile]}
        )
        existing[(profile["candidate_id"], profile["evidence"]["source_id"])] = profile
    inputs["reviewed_candidate_profiles"] = list(existing.values())
    result = build(root, output=output, inputs=inputs)
    return {
        "validated_new_or_changed_profiles": len(validated),
        "preserved_normalized_profiles": len(existing) - len(validated),
        "house_manifest": result,
    }


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


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    print(json.dumps(ingest(args.root), indent=2))
