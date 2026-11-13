import re
from bisect import bisect_right

from pypdf import PdfReader

from .benchmarks import STATE_NAMES

HEADER = re.compile(
    r"(?m)^[ \t]*([A-ZÀ-ÖØ-Þ][A-Za-zÀ-ÖØ-öø-ÿ .,'()\u2019\u2018\u2013-]{3,100}),\s*"
    r"(Democrat|Republican|Independent|Democratic-Farmer-Labor),\s*of\s+([^;]{2,140});"
)
FOREIGN_COUNTRIES = (
    "Japan",
    "Germany",
    "West Germany",
    "East Germany",
    "France",
    "Canada",
    "Mexico",
    "Cuba",
    "India",
    "Pakistan",
    "Taiwan",
    "China",
    "South Korea",
    "South Vietnam",
    "Vietnam",
    "Thailand",
    "Philippines",
    "Somalia",
    "Ethiopia",
    "Nigeria",
    "Dominican Republic",
    "Ecuador",
    "Peru",
    "Guatemala",
    "El Salvador",
    "United Kingdom",
    "England",
    "Scotland",
    "Ireland",
    "Poland",
    "Ukraine",
    "Soviet Union",
    "Israel",
    "Iran",
)

RACE_LABELS = {
    "white": "white",
    "black": "black",
    "african american": "black",
    "asian american": "asian",
    "native american": "native_american",
    "american indian": "native_american",
    "native hawaiian": "nhpi",
    "pacific islander": "nhpi",
}


def authorized_identity(body):
    races, hispanic, evidence = set(), None, []
    for clause in body.split(";"):
        clause = " ".join(clause.split()).strip()
        normalized = clause.casefold().replace("-", " ")
        explicit = re.fullmatch(r"(?:race|racial identity):\s*(.+)", normalized)
        ethnicity = re.fullmatch(r"(?:ethnicity|hispanic origin):\s*(.+)", normalized)
        if explicit:
            labels = re.split(r"\s+(?:and|&)\s+|,\s*", explicit[1])
            if all(label in RACE_LABELS for label in labels):
                races.update(RACE_LABELS[label] for label in labels)
                evidence.append(clause)
        if ethnicity and ethnicity[1] in ("hispanic", "latino", "latina", "non hispanic"):
            hispanic = ethnicity[1] != "non hispanic"
            evidence.append(clause)
        claim = re.match(
            r"^(?:(?:the|became the|elected as the|elected the|was the) )?"
            r"(?:first|second|third|only) (?:woman |female |male )?"
            r"(african american|black|asian american|native american|american indian|"
            r"native hawaiian|pacific islander|white|hispanic|latino|latina)\b"
            r"(?=.{0,100}\b(?:elected|represent|serve|member|senator|woman|man|mayor)\b)",
            normalized,
        )
        if claim and not re.search(r"\b(?:caucus|wife|husband|daughter|son)\b", normalized):
            if claim[1] in ("hispanic", "latino", "latina"):
                hispanic = True
            else:
                races.add(RACE_LABELS[claim[1]])
            evidence.append(clause)
    return {
        "races": sorted(races),
        "hispanic_origin": hispanic,
        "racial_identity_evidence": evidence,
    }


def birth_state(clause):
    states = {
        **STATE_NAMES,
        "DC": "DISTRICT OF COLUMBIA",
        "PR": "PUERTO RICO",
        "AS": "AMERICAN SAMOA",
        "GU": "GUAM",
        "VI": "U.S. VIRGIN ISLANDS",
        "MP": "NORTHERN MARIANA ISLANDS",
    }
    # A city sharing a state's name (Michigan City, for example) is not a state.
    for part in clause.split(",")[1:]:
        value = part.strip().upper().rstrip(".")
        for code, full in states.items():
            if value in (code, ".".join(code)) or (value == full and code != "GA"):
                return code
    for part in clause.split(",")[1:]:
        if part.strip().rstrip(".").casefold() in {c.casefold() for c in FOREIGN_COUNTRIES}:
            return "FOREIGN"
    return None


def biography_entries(pages, spec):
    offsets, text = [], ""
    for page in pages:
        offsets.append(len(text))
        text += page + "\n"
    matches, result = list(HEADER.finditer(text)), []
    for index, match in enumerate(matches):
        location = re.sub(r"[^A-Z]", "", match[3].split(",")[-1].upper())
        state = next(
            (
                code
                for code, full in STATE_NAMES.items()
                if location in (code, re.sub(r"[^A-Z]", "", full))
            ),
            None,
        )
        if not state:
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = re.sub(r"[-\u2010\u2013]\s*\n\s*(?=[a-z])", "", text[match.end() : end])
        body = " ".join(body.split())
        born = re.search(r"\bborn\s+([^;]{1,220});", body)
        religion = re.search(r"\breligion:\s*([^;]{1,160});", body)
        literal = born[1] if born else None
        result.append(
            {
                "name": match[1].strip(),
                "state": state,
                "party_literal": match[2],
                "birth_clause": literal,
                "birth_state": birth_state(literal) if literal else None,
                "religion": religion[1] if religion else None,
                "source_id": spec["id"],
                "source_page": bisect_right(offsets, match.start()),
                "publication_date": spec["publication_date"],
                "election_year": spec["election_year"],
                "qualification": "member_office_furnished_or_authorized; explicit_fields_only",
                **authorized_identity(body),
            }
        )
    return result


def read_directory(path, spec):
    reader, pages, boundary = PdfReader(path), [], False
    wyoming = False
    for page in reader.pages:
        text = page.extract_text()
        if wyoming and not re.search(r"\bWYOMING\b", text[:160]):
            boundary = True
            break
        pages.append(text)
        wyoming |= bool(re.search(r"\bWYOMING\b", text[:160])) and len(pages) > 30
    frontmatter = " ".join(" ".join(pages[:30]).split()).casefold()
    if "furnished or authorized" not in frontmatter:
        raise ValueError(f"Directory lacks member authorization evidence: {spec['id']}")
    rows = biography_entries(pages, spec)
    if not boundary or {r["state"] for r in rows} != set(STATE_NAMES):
        raise ValueError(f"Directory biography scope is incomplete: {spec['id']}")
    return rows
