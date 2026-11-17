"""Subject-bounded official guide discovery; drafts are not qualified claims."""

import json
import re
from pathlib import Path

from pypdf import PdfReader

from .characteristics_research import normalized
from .characteristics_v8_batch import WORK
from .storage import read_rows, write_json

OR_FIELDS = (
    "Occupation",
    "Occupational Background",
    "Educational Background",
    "Prior Governmental Experience",
)
WA_FIELDS = (
    "Elected Experience",
    "Other Professional Experience",
    "Education",
    "Community Service",
    "Statement",
    "Contact",
)


def oregon_statement(text):
    text = " ".join(text.split())
    header = re.search(
        r"US Representative, (\d+)(?:st|nd|rd|th) District "
        r"(.+?) (Democrat|Republican|Independent|Pacific Green)\b(.*?) Occupation:",
        text,
    )
    if not header:
        return None
    fields = {}
    for label, following in zip(OR_FIELDS, OR_FIELDS[1:]):
        match = re.search(rf"{label}: (.*?) {following}:", text)
        if not match:
            return None
        fields[label] = match[1]
    # The last field has no explicit closing label. Retain the full remainder
    # as a reading aid; only manually selected literal history enters evidence.
    fields[OR_FIELDS[-1]] = text.split(f"{OR_FIELDS[-1]}:", 1)[1].strip()
    return {
        "district": f"{int(header[1]):02}",
        "printed_name": header[2],
        "printed_party": header[3],
        "fields": fields,
    }


def washington_statement(text):
    heading = re.search(r"United States Representative\s*\|\s*District (\d+)\s*\|.*?term", text)
    if not heading or "Elected Experience" not in text:
        return None
    before_fields = text[heading.end() :].split("Elected Experience", 1)[0].strip()
    parties = list(re.finditer(r"\(Prefers (Democratic|Republican) Party\)", text))
    if len(parties) != 1:
        return None
    party = parties[0]
    # Some PDFs store the surname after Contact rather than next to the first
    # name. Do not search the statement body for arbitrary candidate mentions.
    if party.start() < text.index("Elected Experience"):
        name = before_fields.split("(Prefers", 1)[0].strip()
    else:
        suffix = text[: party.start()].rstrip().splitlines()[-1].strip()
        name = f"{before_fields} {suffix}"
    fields = {}
    for label, following in zip(WA_FIELDS, WA_FIELDS[1:]):
        match = re.search(rf"{label}\s+(.*?)\s+{following}\b", text, re.S)
        if not match:
            return None
        fields[label] = " ".join(match[1].split())
    return {
        "district": f"{int(heading[1]):02}",
        "printed_name": " ".join(name.split()),
        "printed_party": party[1],
        "fields": fields,
    }


def discover(root):
    root = Path(root)
    work = root / WORK
    receipts = json.loads((work / "retrievals.json").read_text())
    candidates = read_rows(root / "results/house/candidates.jsonl.gz")
    drafts, seen = [], set()
    for receipt in receipts:
        key = receipt["id"]
        if receipt["status"] != "acquired":
            continue
        state = "OR" if key.startswith("oregon-book") else "WA"
        if not key.startswith(("oregon-book", "washington-edition")):
            continue
        parser = oregon_statement if state == "OR" else washington_statement
        for page, source in enumerate(PdfReader(work / key).pages, 1):
            text = source.extract_text() or ""
            statement = parser(text)
            if not statement:
                continue
            fingerprint = (
                state,
                normalized(statement["printed_name"]),
                json.dumps(statement["fields"], sort_keys=True),
            )
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            matches = [
                c
                for c in candidates
                if c["state"] == state
                and c["district"] == statement["district"]
                and c["party"].startswith(statement["printed_party"])
                and normalized(c["name"]) == normalized(statement["printed_name"])
            ]
            drafts.append(
                {
                    **statement,
                    "source_id": key,
                    "page": page,
                    "state": state,
                    "native_matches": [c["candidate_id"] for c in matches],
                    "qualification": "unreviewed_discovery_not_evidence",
                }
            )
    write_json(work / "guide-reading.json", drafts)
    return drafts


if __name__ == "__main__":
    print(json.dumps(discover(Path(__file__).resolve().parents[1]), indent=2))
