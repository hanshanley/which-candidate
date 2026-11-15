"""Full sitting-seat and provisional incoming House profiles, not candidate-only incumbents."""

import argparse
import hashlib
import json
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

from .benchmarks import STATE_NAMES
from .corrected import same_name
from .features import FeatureSources, name_matches
from .house_backgrounds import background_observations, background_profile
from .incoming_biographies import qualify_identity
from .incumbents import CUTOFF, historian_profile, incumbent_tables
from .pipeline import csv_bytes
from .rebuild import ROOT, district
from .storage import fingerprint, read_rows, write_json

CACHE = "data/raw/house-members-20261114"
SOURCES = {
    "wikipedia-new-members": (
        "https://en.wikipedia.org/wiki/List_of_new_members_of_the_120th_United_States_Congress"
    ),
    "inside-elections-new-members": "https://insideelections.com/new-members-of-congress/",
    "quorum-new-members": (
        "https://www.quorum.us/data-driven-insights/meet-the-new-members-of-the-120th-congress/"
    ),
    "historian-B001328": "https://history.house.gov/People/Detail/36507230755",
    "crenshaw-about": "https://crenshaw.house.gov/about",
}


class Tables(HTMLParser):
    """Keep factual table cells and their links, excluding notes and nested tables."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self.depth = 0
        self.row = self.cell = None
        self.ignore = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("script", "style", "sup"):
            self.ignore += 1
        if tag == "table":
            self.depth += 1
            if self.depth == 1:
                self.tables.append({"attrs": attrs, "rows": []})
        if self.depth != 1:
            return
        if tag == "tr":
            self.row = []
            self.tables[-1]["rows"].append(self.row)
        if tag in ("th", "td") and self.row is not None:
            self.cell = {"text": "", "links": [], "attrs": attrs}
            self.row.append(self.cell)
        if self.cell is not None and not self.ignore:
            if tag == "a" and attrs.get("href"):
                self.cell["links"].append(attrs["href"])
            if tag in ("br", "li", "div"):
                self.cell["text"] += " "

    def handle_endtag(self, tag):
        if tag in ("script", "style", "sup") and self.ignore:
            self.ignore -= 1
        if tag == "table":
            self.depth -= 1
        if self.depth == 1 and tag in ("th", "td"):
            self.cell = None
        if self.depth == 1 and tag == "tr":
            self.row = self.cell = None

    def handle_data(self, data):
        if self.depth == 1 and self.cell is not None and not self.ignore:
            self.cell["text"] += data


def tables(html):
    parser = Tables()
    parser.feed(html)
    for table in parser.tables:
        for row in table["rows"]:
            for cell in row:
                cell["text"] = " ".join(cell["text"].split())
    return parser.tables


def wiki_new_members(html):
    result = []
    for table in tables(html):
        if not table["rows"]:
            continue
        headings = [c["text"] for c in table["rows"][0]]
        if "District" not in headings or "Representative" not in headings:
            continue
        for number, row in enumerate(table["rows"][1:], 2):
            if len(row) != len(headings):
                continue
            cells = dict(zip(headings, row, strict=True))
            seat = cells["District"]["text"]
            state = next(
                (s for s, name in STATE_NAMES.items() if seat.startswith(name.title() + " ")),
                None,
            )
            if not state:
                continue
            suffix = seat[len(STATE_NAMES[state]) :].strip()
            match = re.fullmatch(r"(\d+|at.large)", suffix, re.I)
            if not match:
                continue
            member = cells["Representative"]
            name = re.sub(r"\s*\((?:D|R|DFL|I)\)\s*$", "", member["text"]).strip()
            links = []
            for link in member["links"]:
                url = urljoin("https://en.wikipedia.org/wiki/", link)
                parsed = urlparse(url)
                if (
                    parsed.netloc == "en.wikipedia.org"
                    and parsed.path.startswith("/wiki/")
                    and ":" not in parsed.path.removeprefix("/wiki/")
                ):
                    links.append(url)
            party = re.search(r"\((D|R|DFL|I)\)", member["text"])
            result.append(
                {
                    "state": state,
                    "district": "AL" if not suffix.isdigit() else suffix.zfill(2),
                    "name": name,
                    "party": {
                        "D": "Democratic",
                        "DFL": "Democratic",
                        "R": "Republican",
                        "I": "Independent",
                    }.get(party[1])
                    if party
                    else None,
                    "wikipedia_url": links[0] if links else None,
                    "prior_background": cells.get("Prior background", {}).get("text"),
                    "birth_year_literal": cells.get("Birth year", {}).get("text"),
                    "source_table_row": number,
                }
            )
    keys = [(r["state"], r["district"]) for r in result]
    if not result or len(keys) != len(set(keys)):
        raise ValueError("Missing or duplicate incoming Wikipedia seat rows")
    return result


def wiki_infobox(html):
    result = {}
    allowed = {
        "Born": "birth_literal",
        "Education": "education",
        "Alma mater": "education",
        "Occupation": "occupation",
        "Profession": "occupation",
        "Branch/service": "military_service",
        "Branch": "military_service",
        "Years of service": "military_service_years",
        "Rank": "military_rank",
        "Political party": "reported_party",
    }
    for table in tables(html):
        if "infobox" not in table["attrs"].get("class", "").split():
            continue
        for row in table["rows"]:
            if len(row) == 2 and row[0]["text"] in allowed and row[1]["text"]:
                result[allowed[row[0]["text"]]] = row[1]["text"]
        break
    return result


def qualified_infobox(row, html):
    fields = wiki_infobox(html)
    expected = set(re.findall(r"\b(?:18|19|20)\d{2}\b", row.get("birth_year_literal") or ""))
    observed = set(re.findall(r"\b(?:18|19|20)\d{2}\b", fields.get("birth_literal", "")))
    if expected and observed and not expected.intersection(observed):
        return {}, "conflicting_birth_year; linked_article_held"
    return fields, "district_roster_link; secondary_report; not_self_description"


def acquire(root=ROOT):
    root = Path(root)
    cache = root / CACHE
    cache.mkdir(parents=True, exist_ok=True)
    receipt_path = root / "data/house-member-sources.json"
    prior = json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
    receipts = {r["id"]: r for r in prior.get("sources", [])}
    failures = prior.get("failures", [])

    def persist():
        write_json(receipt_path, {"sources": list(receipts.values()), "failures": failures})

    def download(key, url):
        path = cache / f"{key}.html"
        if key in receipts:
            if fingerprint(path) != {k: receipts[key][k] for k in ("bytes", "sha256")}:
                raise ValueError(f"Changed original member source: {key}")
            return path.read_text()
        if any(f["id"] == key for f in failures):
            return None
        proc = subprocess.run(
            ["curl", "--fail", "--location", "--max-time", "40", "--silent", "--show-error", url],
            capture_output=True,
        )
        if proc.returncode:
            failures.append(
                {
                    "id": key,
                    "url": url,
                    "error": proc.stderr.decode(),
                    "disposition": "not_bypassed",
                }
            )
            persist()
            return None
        path.write_bytes(proc.stdout)
        receipts[key] = {
            "id": key,
            "url": url,
            "path": str(path.relative_to(root)),
            **fingerprint(path),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "publication_date": None,
            "qualification": "retrieved_after_election; descriptive_only; model_ineligible",
        }
        persist()
        return proc.stdout.decode()

    originals = {key: download(key, url) for key, url in SOURCES.items()}
    profiles = []
    if originals["historian-B001328"]:
        profiles.append(
            {
                **historian_profile(originals["historian-B001328"], "B001328"),
                "bioguide_id": "B001328",
                "state": "GA",
                "chamber": "house",
                "evidence": receipts["historian-B001328"],
                "source_kind": "official_House_Historian_biography",
                "identity_qualification": "official_Historian_stable_bioguide_id",
                "model_ready": False,
            }
        )
    if originals["crenshaw-about"]:
        from .corrected import text

        content = text(originals["crenshaw-about"])
        if "Crenshaw" not in content or "SEAL" not in content:
            raise ValueError("Crenshaw official biography changed")
        profiles.append(
            {
                "bioguide_id": "C001120",
                "state": "TX",
                "chamber": "house",
                "fields": {"professional_history": "U.S. Navy SEAL officer; U.S. Representative"},
                "evidence": receipts["crenshaw-about"],
                "source_kind": "reviewed_official_member_biography",
                "identity_qualification": "official_member_website_matches_stable_service_identity",
                "model_ready": False,
            }
        )
    newcomers = wiki_new_members(originals["wikipedia-new-members"] or "")
    for row in newcomers:
        row["roster_evidence"] = receipts["wikipedia-new-members"]
        if not row["wikipedia_url"]:
            continue
        key = "wiki-" + hashlib.sha256(row["wikipedia_url"].encode()).hexdigest()[:16]
        html = download(key, row["wikipedia_url"])
        row["infobox_fields"], row["profile_qualification"] = (
            qualified_infobox(row, html) if html else ({}, "profile_not_acquired")
        )
        row["profile_evidence"] = receipts.get(key)
        if html:
            revision = re.search(
                r'"wgRevisionId"\s*:\s*(\d+)|Special:Redirect/revision/(\d+)', html
            )
            row["wikipedia_revision_id"] = int(revision[1] or revision[2]) if revision else None
        if not any(f["id"] == key for f in failures):
            time.sleep(1)
    candidates = read_rows(root / "results/house/candidates.jsonl.gz")
    specs = json.loads((root / "data/research-sources.json").read_text())["sources"]
    service_people = []
    for spec in specs:
        if spec["kind"] != "legislators":
            continue
        path = root / "data" / spec["path"]
        if fingerprint(path) != {k: spec[k] for k in ("bytes", "sha256")}:
            raise ValueError(f"Changed legislators original: {spec['id']}")
        service_people.extend(
            {**p, "evidence": {"source": spec, "json_pointer": f"/{i}"}}
            for i, p in enumerate(json.loads(path.read_text()))
        )
    crosswalk, retained_people = incoming_service(candidates, service_people, newcomers)
    caveats = []
    if originals["quorum-new-members"]:
        from .corrected import text

        if "accurate as of November 12, 2026" not in text(originals["quorum-new-members"]):
            raise ValueError("Quorum source no longer has the reviewed snapshot date")
        for key in (
            "ME:02",
            "MN:01",
            "TN:04",
            "LA:05",
            "LA:06",
            "AK:AL",
            "CA:04",
            "CA:23",
            "CO:04",
            "NC:03",
            "NC:05",
            "NC:07",
            "NC:10",
        ):
            caveats.append(
                {
                    "seat_id": key,
                    "status": "reported_uncalled",
                    "as_of": "2026-11-12",
                    "evidence": receipts["quorum-new-members"],
                }
            )
    write_json(
        root / "data/house-member-profiles.json",
        {
            "official_profiles": profiles,
            "incoming_wikipedia_rows": newcomers,
            "incoming_service_crosswalks": crosswalk,
            "additional_service_people": retained_people,
            "incoming_call_caveats": caveats,
            "sources": list(receipts.values()),
            "failures": failures,
        },
    )
    return {
        "official_profiles": len(profiles),
        "incoming_roster_rows": len(newcomers),
        "incoming_infoboxes": sum(bool(r.get("infobox_fields")) for r in newcomers),
        "sources": len(receipts),
        "failures": failures,
    }


def seat_key(state, value):
    return state + ":" + ("AL" if district(value) == 0 else str(district(value)).zfill(2))


def roster_name_matches(candidate, row):
    return bool(
        row
        and candidate["party"] == row.get("party")
        and (
            same_name(candidate["name"], row["name"])
            or name_matches(candidate["name"], row["name"].split()[0], row["name"].split()[-1])
        )
    )


def incoming_service(candidates, people, newcomers):
    """Resolve federal service with source-recorded IDs, aliases and state, never surname alone."""
    matcher = FeatureSources({"sources": []}, None)
    wiki = {seat_key(r["state"], r["district"]): r for r in newcomers}
    matches, retained = [], {}
    for c in candidates:
        if c["native_flags_unverified"]["winner"] is not True:
            continue
        roster = wiki.get(seat_key(c["state"], c["district"]))
        qualified = []
        for p in people:
            if not any(t["type"] == "rep" and t["state"] == c["state"] for t in p["terms"]):
                continue
            names = matcher.aliases(p)
            page_title = p["id"].get("wikipedia", "")
            if page_title:
                parts = re.sub(r"\s*\(.*\)$", "", page_title.replace("_", " ")).split()
                if len(parts) >= 2:
                    names.append((" ".join(parts[:-1]), parts[-1]))
            if not name_matches(c["name"], *names[0], names[1:]):
                continue
            fec = c["identity"].get("fec_id")
            official_id = c["legislative"].get("bioguide_id")
            linked_title = ((roster or {}).get("wikipedia_url") or "").rsplit("/", 1)[-1]
            linked_title = linked_title.replace("_", " ")
            linked = roster_name_matches(c, roster) and linked_title == page_title.replace("_", " ")
            if (
                official_id == p["id"]["bioguide"]
                or (fec and fec in p["id"].get("fec", []))
                or linked
            ):
                qualified.append(p)
            elif any(
                t["type"] == "rep"
                and t["state"] == c["state"]
                and t["start"] <= CUTOFF < t["end"]
                and {"Democrat": "Democratic"}.get(t.get("party"), t.get("party")) == c["party"]
                for t in p["terms"]
            ):
                # The public title in the stable-ID crosswalk supplies a recorded nickname.
                qualified.append(p)
        if len(qualified) > 1:
            raise ValueError(f"Ambiguous incoming service identity: {c['name']}")
        if qualified:
            p = qualified[0]
            bid = p["id"]["bioguide"]
            retained[bid] = p
            matches.append(
                {
                    "candidate_id": c["candidate_id"],
                    "bioguide_id": bid,
                    "status": "stable_service_crosswalk; state_and_recorded_name_qualified",
                    "evidence": p["evidence"],
                }
            )
    return matches, list(retained.values())


def seated_profiles(inputs, candidates, additions):
    inputs = {
        **inputs,
        "incumbent_backgrounds": {
            **inputs["incumbent_backgrounds"],
            "profiles": [
                *inputs["incumbent_backgrounds"]["profiles"],
                *additions.get("official_profiles", []),
            ],
            "aliases": [
                *inputs["incumbent_backgrounds"]["aliases"],
                *[
                    {
                        "bioguide_id": p["id"]["bioguide"],
                        "state": t["state"],
                        "name": re.sub(r"\s*\(.*\)$", "", p["id"][key].replace("_", " ")),
                    }
                    for p in inputs["people"]
                    for t in p["terms"]
                    if t["type"] == "rep" and t["start"] <= CUTOFF < t["end"]
                    for key in ("wikipedia", "ballotpedia")
                    if p["id"].get(key)
                ],
                *[
                    {
                        "bioguide_id": c["legislative"]["bioguide_id"],
                        "state": c["state"],
                        "name": c["name"],
                    }
                    for c in candidates
                    if c["legislative"].get("house_incumbent") is True
                ],
            ],
        },
    }
    by_id = defaultdict(list)
    for p in inputs["people"]:
        by_id[p["id"]["bioguide"]].append(p)
    seats, delegates, subjects = [], [], []
    for source in inputs["clerk_members"]:
        member = ET.fromstring(source["native_xml"])
        info = member.find("member-info")
        state = info.find("state").get("postal-code")
        statedistrict = member.findtext("statedistrict")
        number = statedistrict[2:]
        dist = "AL" if number == "00" else number
        bid = info.findtext("bioguideID") or None
        base = {
            "congress": 119,
            "seat_id": f"{state}:{dist}",
            "state": state,
            "district": dist,
            "roster_as_of": source["publication_date"],
            "roster_retrieved_at": source["source"]["retrieved_at"],
            "seat_status": "occupied" if bid else "vacant",
            "bioguide_id": bid,
            "name": info.findtext("official-name") or None,
            "party": {"D": "Democratic", "R": "Republican", "I": "Independent"}.get(
                info.findtext("party")
            ),
            "roster_evidence": json.dumps(source, sort_keys=True),
        }
        if state not in STATE_NAMES:
            delegates.append({**base, "seat_type": "delegate_or_resident_commissioner"})
            continue
        seats.append({**base, "seat_type": "voting"})
        if not bid:
            predecessor = member.find("predecessor-info")
            seats[-1].update(
                {
                    "vacancy_reason": info.findtext("footnote"),
                    "predecessor_bioguide_id": predecessor.findtext("pred-memindex")
                    if predecessor is not None
                    else None,
                    "predecessor_name": predecessor.findtext("pred-official-name")
                    if predecessor is not None
                    else None,
                    "vacated_on": predecessor.find("pred-vacate-date").get("date")
                    if predecessor is not None and predecessor.find("pred-vacate-date") is not None
                    else None,
                }
            )
            continue
        people = by_id[bid]
        if len(people) != 1 or not any(
            t["type"] == "rep" and t["state"] == state and t["start"] <= CUTOFF < t["end"]
            for t in people[0]["terms"]
        ):
            raise ValueError(f"Unqualified Clerk service identity: {bid}")
        person = people[0]
        born = date.fromisoformat(person["bio"]["birthday"])
        prior = [r for r in inputs["members"] if r["bioguide_id"] == bid]
        subject = {
            "candidate_id": bid,
            "contest_id": f"119:house:{state}:{dist}",
            "name": base["name"],
            "state": state,
            "district": dist,
            "party": base["party"],
            "identity": {"fec_id": None},
            "donor": {},
            "legislative": {
                "bioguide_id": bid,
                "house_incumbent": True,
                "status": "official_clerk_and_service_crosswalk",
                "age_at_election": 2026 - born.year - ((11, 3) < (born.month, born.day)),
                "source_recorded_gender": person["bio"].get("gender"),
                "prior_voting_record": prior[0] if len(prior) == 1 else None,
                "evidence": {**person["evidence"], "official_clerk": source},
            },
        }
        subject["background"] = background_profile(subject, inputs)
        subjects.append(subject)
    values, gaps, coverage = incumbent_tables(subjects, inputs)
    by_bid = {r["bioguide_id"]: r for r in values}
    for row in seats:
        if row["bioguide_id"]:
            profile = dict(by_bid[row["bioguide_id"]])
            for key in ("candidate_id", "contest_id", "fec_id", "historical_donor_score"):
                profile.pop(key)
            row.update(profile)
            row["member_id"] = row["bioguide_id"]
            row["date_of_birth"] = by_id[row["bioguide_id"]][0]["bio"]["birthday"]
            row["crosswalk_ids"] = json.dumps(by_id[row["bioguide_id"]][0]["id"], sort_keys=True)
            row["matched_election_candidate_ids"] = ";".join(
                c["candidate_id"]
                for c in candidates
                if c["legislative"].get("bioguide_id") == row["bioguide_id"]
                and c["legislative"].get("house_incumbent") is True
            )
    keys = [r["seat_id"] for r in seats]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate sitting House seats")
    if set(keys) != {seat_key(c["state"], c["district"]) for c in candidates} or len(keys) != 435:
        raise ValueError("Clerk voting-seat universe differs from the 435 election districts")
    if len({r["bioguide_id"] for r in seats if r["bioguide_id"]}) != len(subjects):
        raise ValueError("Duplicate seated House member identity")
    observations = background_observations(subjects, [])
    for row in observations:
        row["member_id"] = row.pop("candidate_id")
        row["congress"] = 119
        row.pop("contest_id")
        row["seat_id"] = seat_key(row["state"], row["district"])
    for member in seats:
        if not member["bioguide_id"]:
            continue
        for field in (
            "date_of_birth",
            "age_at_election",
            "source_recorded_gender",
            "first_house_service",
        ):
            observations.append(
                {
                    "member_id": member["member_id"],
                    "congress": 119,
                    "seat_id": member["seat_id"],
                    "state": member["state"],
                    "district": member["district"],
                    "name": member["name"],
                    "party": member["party"],
                    "field": field,
                    "value": json.dumps(member[field]),
                    "model_ready": False,
                    "source_kind": "stable_ID_service_crosswalk",
                    "evidence": member["service_evidence"],
                    "qualification": "age_at_2026_11_03; first_service_from_dated_House_terms",
                }
            )
    gaps = [
        {
            **{k: v for k, v in r.items() if k != "candidate_id"},
            "member_id": r["candidate_id"],
            "congress": 119,
            "seat_id": seat_key(r["state"], r["district"]),
        }
        for r in gaps
        if r["field"] != "historical_donor_score"
    ]
    coverage["coverage"].pop("historical_donor_score")
    coverage["scope"] = "All occupied voting House seats in the pinned Clerk roster"
    coverage["occupied_members"] = coverage.pop("candidates")
    coverage["voting_seats"] = len(seats)
    coverage["vacant_seats"] = sum(r["seat_status"] == "vacant" for r in seats)
    coverage["separate_delegate_seats"] = len(delegates)
    return seats, delegates, observations, gaps, coverage


def incoming_profiles(candidates, facts, seated, additions, inputs):
    grouped = defaultdict(list)
    for c in candidates:
        grouped[seat_key(c["state"], c["district"])].append(c)
    wiki = {
        seat_key(r["state"], r["district"]): r for r in additions.get("incoming_wikipedia_rows", [])
    }
    service = {r["candidate_id"]: r for r in additions.get("incoming_service_crosswalks", [])}
    member_index = {r["bioguide_id"]: r for r in seated if r["bioguide_id"]}
    service_people = {p["id"]["bioguide"]: p for p in inputs["people"]}
    service_people.update(
        {p["id"]["bioguide"]: p for p in additions.get("additional_service_people", [])}
    )
    caveats = {r["seat_id"]: r for r in additions.get("incoming_call_caveats", [])}
    fact_index = defaultdict(list)
    for fact in facts:
        fact_index[fact["candidate_id"]].append(fact)
    people = []
    observations = []
    for seat in seated:
        key = seat["seat_id"]
        contenders = grouped[key]
        winners = [c for c in contenders if c["native_flags_unverified"]["winner"] is True]
        selected = winners[0] if len(winners) == 1 else None
        newcomer = wiki.get(key)
        wiki_match = bool(selected and roster_name_matches(selected, newcomer))
        held = bool(selected and newcomer and not wiki_match)
        bid = (
            (
                service.get(selected["candidate_id"], {}).get("bioguide_id")
                or selected["legislative"].get("bioguide_id")
            )
            if selected
            else None
        )
        current = member_index.get(bid)
        base = {
            "congress": 120,
            "scheduled_start": "2027-01-03",
            "seat_id": key,
            "state": seat["state"],
            "district": seat["district"],
            "status": "conflicting_new_member_identity; held"
            if held
            else "provider_reported_winner; provisional_not_certified"
            if selected
            else "no_unique_provider_winner; unresolved",
            "candidate_id": selected["candidate_id"] if selected else None,
            "name": selected["name"] if selected else None,
            "party": selected["party"] if selected else None,
            "bioguide_id": bid,
            "entry_classification": (
                "continuing_House_member"
                if current
                else "returning_former_House_member"
                if bid
                else "prior_federal_service_unresolved"
                if not wiki_match
                else "new_to_current_House; prior_federal_service_not_fully_resolved"
            )
            if selected
            else None,
            "provider_evidence": json.dumps(
                [
                    {
                        "candidate_id": c["candidate_id"],
                        "winner": c["native_flags_unverified"]["winner"],
                        "source": c["source"],
                        "source_updated_at_values": c["source_updated_at_values"],
                    }
                    for c in contenders
                ],
                sort_keys=True,
            ),
            "wikipedia_roster_match": wiki_match,
            "wikipedia_roster_candidate": newcomer["name"] if newcomer else None,
            "wikipedia_roster_evidence": json.dumps(newcomer, sort_keys=True) if newcomer else None,
            "new_fields_model_ready": False,
            "earlier_call_caveat": json.dumps(caveats.get(key), sort_keys=True),
            "call_caveat_interpretation": (
                "Quorum reports uncalled as of 2026-11-12; provider snapshot is separate. "
                "No certified outcome or verified call timestamp is inferred."
            )
            if key in caveats
            else None,
            "service_crosswalk_evidence": json.dumps(
                service.get(selected["candidate_id"]) if selected else None, sort_keys=True
            ),
            "current_federal_voting_applicability": (
                "current_119th_record_available"
                if current
                else "no_current_119th_record_qualified; not_zero"
            ),
        }
        if selected:
            base["member_id"] = base["bioguide_id"] or f"candidate:{base['candidate_id']}"
            if current:
                for field in (
                    "date_of_birth",
                    "age_at_election",
                    "source_recorded_gender",
                    "birth_clause",
                    "education",
                    "professional_history",
                    "military_service",
                    "religion_literal",
                    "religion_status",
                    "cast_yea_nay_votes",
                    "party_unity_score",
                    "prior_nokken_poole_dim1",
                    "biography_evidence",
                    "religion_evidence",
                    "voting_evidence",
                    "service_evidence",
                    "crosswalk_ids",
                ):
                    base[field] = current.get(field)
                base["current_seat_id"] = current["seat_id"]
            elif bid in service_people:
                person = service_people[bid]
                base["date_of_birth"] = person["bio"].get("birthday")
                base["source_recorded_gender"] = person["bio"].get("gender")
                base["crosswalk_ids"] = json.dumps(person["id"], sort_keys=True)
                base["service_evidence"] = json.dumps(person["evidence"], sort_keys=True)
            selected_facts = fact_index[selected["candidate_id"]]
            for fact in selected_facts:
                observations.append(
                    {
                        "member_id": base["member_id"],
                        "congress": 120,
                        "seat_id": key,
                        "name": selected["name"],
                        "field": fact["field"],
                        "value": json.dumps(fact["value"], sort_keys=True),
                        "source_kind": "campaign_factual_extraction",
                        "evidence": json.dumps(fact, sort_keys=True),
                        "model_ready": False,
                    }
                )
            for field in (
                "education",
                "occupation",
                "military_service",
                "elected_office_experience",
                "public_service_experience",
                "local_roots",
            ):
                base[f"campaign_{field}_review_required"] = json.dumps(
                    sorted({str(f["value"]) for f in selected_facts if f["field"] == field})
                )
            for fact in background_observations([selected], []):
                observations.append(
                    {
                        **{
                            k: v for k, v in fact.items() if k not in ("candidate_id", "contest_id")
                        },
                        "member_id": base["member_id"],
                        "congress": 120,
                        "seat_id": key,
                    }
                )
            candidate_profile_fields = defaultdict(list)
            for profile in selected["background"].get("official_candidate_profiles", []):
                for field, value in profile["fields"].items():
                    candidate_profile_fields[field].append(value)
            for field, values in candidate_profile_fields.items():
                base[f"candidate_profile_{field}"] = json.dumps(values, sort_keys=True)
            if wiki_match:
                base["wikipedia_url"] = newcomer["wikipedia_url"]
                base["reported_prior_background"] = newcomer["prior_background"]
                base["reported_birth_year_literal"] = newcomer["birth_year_literal"]
                for field in ("prior_background", "birth_year_literal"):
                    if newcomer.get(field):
                        observations.append(
                            {
                                "member_id": base["member_id"],
                                "congress": 120,
                                "seat_id": key,
                                "name": selected["name"],
                                "field": f"reported_{field}",
                                "value": json.dumps(newcomer[field]),
                                "source_kind": "Wikipedia_new_member_roster; secondary_report",
                                "evidence": json.dumps(newcomer["roster_evidence"], sort_keys=True),
                                "model_ready": False,
                            }
                        )
                for field, value in newcomer.get("infobox_fields", {}).items():
                    base[f"wikipedia_{field}"] = value
                    observations.append(
                        {
                            "member_id": base["member_id"],
                            "congress": 120,
                            "seat_id": key,
                            "name": selected["name"],
                            "field": field,
                            "value": json.dumps(value),
                            "source_kind": "Wikipedia_infobox; secondary_report_not_self_description",
                            "evidence": json.dumps(
                                newcomer.get("profile_evidence"), sort_keys=True
                            ),
                            "model_ready": False,
                        }
                    )
        people.append(base)
    return people, observations


def reviewed_incoming_profiles(incoming, payload):
    index = {r["candidate_id"]: r for r in incoming if r.get("candidate_id")}
    observations = []
    for profile in payload["profiles"]:
        candidate_id = profile["candidate_id"]
        if candidate_id not in index:
            raise ValueError(f"Biography has no unique provisional winner: {candidate_id}")
        row = index[candidate_id]
        qualify_identity(profile, row)
        if profile["model_ready"] is not False:
            raise ValueError("New incoming biographies must remain model-ineligible")
        evidence = profile["evidence"]
        if not evidence.get("sha256") or not evidence.get("url"):
            raise ValueError("Incoming biography requires a pinned source")
        secondary = "wikipedia.org/" in evidence["url"]
        previous = json.loads(row.get("reviewed_biography_evidence") or "[]")
        previous.append(profile)
        row["reviewed_biography_evidence"] = json.dumps(previous, sort_keys=True)
        for field, value in profile["fields"].items():
            target = "education" if field == "education_literal" else field
            if target == "date_of_birth":
                date.fromisoformat(value)
                if row.get(target) and row[target] != value:
                    raise ValueError(f"Conflicting birth date for {candidate_id}")
            if target in (
                "date_of_birth",
                "education",
                "professional_history",
                "military_service",
                "prior_office",
            ) and not row.get(target):
                row[target] = (
                    json.dumps(value, sort_keys=True) if isinstance(value, list) else value
                )
            observations.append(
                {
                    "member_id": row["member_id"],
                    "congress": 120,
                    "seat_id": row["seat_id"],
                    "name": row["name"],
                    "field": field,
                    "value": json.dumps(value, sort_keys=True),
                    "source_kind": "reviewed_Wikipedia_biography; secondary"
                    if secondary
                    else "reviewed_primary_biography",
                    "evidence": json.dumps(evidence, sort_keys=True),
                    "model_ready": False,
                }
            )
    return observations


def build(root=ROOT, output=None):
    root = Path(root)
    output = Path(output) if output else root / "results/members"
    inputs = read_rows(root / "results/house/source-inputs.jsonl.gz")[0]
    candidates = read_rows(root / "results/house/candidates.jsonl.gz")
    facts = read_rows(root / "results/house/biography-facts.jsonl.gz")
    additions = json.loads((root / "data/house-member-profiles.json").read_text())
    seated, delegates, observations, gaps, coverage = seated_profiles(inputs, candidates, additions)
    incoming, incoming_observations = incoming_profiles(
        candidates, facts, seated, additions, inputs
    )
    reviewed = json.loads((root / "data/incoming-member-biographies.json").read_text())
    incoming_observations.extend(reviewed_incoming_profiles(incoming, reviewed))
    coverage["incoming"] = {
        "seats": len(incoming),
        "statuses": dict(Counter(r["status"] for r in incoming)),
        "entry_classifications": dict(
            Counter(r["entry_classification"] or "unresolved" for r in incoming)
        ),
        "wikipedia_roster_matches": sum(r["wikipedia_roster_match"] for r in incoming),
        "wikipedia_education_records": sum(bool(r.get("wikipedia_education")) for r in incoming),
        "reviewed_biography_candidates": len({r["candidate_id"] for r in reviewed["profiles"]}),
        "reviewed_biography_sources": len(reviewed["sources"]),
        "with_exact_date_of_birth": sum(bool(r.get("date_of_birth")) for r in incoming),
        "with_qualified_education": sum(
            bool(
                r.get("education")
                or r.get("wikipedia_education")
                or r.get("candidate_profile_education")
            )
            for r in incoming
        ),
        "with_core_biography_or_campaign_evidence": sum(
            bool(
                r.get("education")
                or r.get("wikipedia_education")
                or r.get("candidate_profile_education")
                or r.get("campaign_education_review_required") not in (None, "[]")
                or r.get("campaign_occupation_review_required") not in (None, "[]")
            )
            for r in incoming
        ),
        "with_existing_biography_or_reported_prior_background": sum(
            bool(r.get("education") or r.get("reported_prior_background")) for r in incoming
        ),
        "interpretation": "Provider calls are provisional, not certified members-elect. "
        "Wikipedia evidence is secondary and descriptive. Missing federal votes are not zero.",
    }
    output.mkdir(parents=True, exist_ok=True)
    files = {
        "house-119-seats.csv": csv_bytes(seated),
        "house-119-delegates.csv": csv_bytes(delegates),
        "house-120-seats.csv": csv_bytes(incoming),
        "background-observations.csv": csv_bytes([*observations, *incoming_observations]),
        "missing-fields.csv": csv_bytes(gaps),
    }
    incoming_gaps = []
    for row in incoming:
        if not row["name"]:
            incoming_gaps.append(
                {
                    "congress": 120,
                    "seat_id": row["seat_id"],
                    "field": "member_identity",
                    "status": row["status"],
                }
            )
            continue
        for field, available, status in (
            (
                "exact_date_of_birth",
                bool(row.get("date_of_birth")),
                "no_qualified_exact_date; reported_Wikipedia_birth_literal_may_be_available",
            ),
            (
                "structured_education",
                bool(
                    row.get("education")
                    or row.get("wikipedia_education")
                    or row.get("candidate_profile_education")
                ),
                "no_qualified_structured_field; any_machine_campaign_extraction_requires_review",
            ),
            (
                "religion_literal",
                bool(row.get("religion_literal"))
                and row.get("religion_status") != "explicit_unknown_or_refused",
                row.get("religion_status") or "no_qualified_disclosure",
            ),
            (
                "current_119th_voting_record",
                bool(row.get("current_seat_id")),
                "no_current_qualified_federal_record; not_zero; not_expected_for_newcomers",
            ),
        ):
            if not available:
                incoming_gaps.append(
                    {
                        "congress": 120,
                        "seat_id": row["seat_id"],
                        "member_id": row["member_id"],
                        "candidate_id": row["candidate_id"],
                        "name": row["name"],
                        "field": field,
                        "status": status,
                    }
                )
    files["incoming-missing-fields.csv"] = csv_bytes(incoming_gaps)
    historical = json.loads((root / "data/congressdata-members.json").read_text())
    target_ids = {r["bioguide_id"] for r in [*seated, *incoming] if r["bioguide_id"]}
    historical_rows = [
        {
            **r,
            "historical_source_id": historical["source"]["id"],
            "historical_source_sha256": historical["source"]["sha256"],
            "historical_model_ready": False,
            "not_current_2026_beliefs": True,
        }
        for r in historical["rows"]
        if r["bioguide"] in target_ids
    ]
    historical_ids = {r["bioguide"] for r in historical_rows}
    for row in [*seated, *incoming]:
        row["historical_congressdata_available"] = row["bioguide_id"] in historical_ids
    files["house-119-seats.csv"] = csv_bytes(seated)
    files["house-120-seats.csv"] = csv_bytes(incoming)
    files["congressdata-latest.csv"] = csv_bytes(historical_rows)
    coverage["historical_congressdata"] = {
        "source_rows": historical["source_rows"],
        "source_columns": historical["source_columns"],
        "source_years": [historical["source_year_min"], historical["source_year_max"]],
        "latest_member_rows": len(historical_rows),
        "seated_members_with_history": sum(r["historical_congressdata_available"] for r in seated),
        "interpretation": "Latest available historical member-year, all native variables. "
        "No current religion, race, nonservice or ideology inferred.",
    }
    for name, content in files.items():
        (output / name).write_bytes(content)
    write_json(output / "coverage.json", coverage)
    write_json(
        output / "congressdata-codebook.json", {k: v for k, v in historical.items() if k != "rows"}
    )
    manifest = {
        "schema": "which_candidate.house_members.v1",
        "scope": "435 voting seats, separate delegates, and provisional incoming House",
        "new_fields_model_ready": False,
        "inputs": {
            name: fingerprint(root / name)
            for name in (
                "results/house/source-inputs.jsonl.gz",
                "results/house/candidates.jsonl.gz",
                "results/house/biography-facts.jsonl.gz",
                "data/house-member-profiles.json",
                "data/congressdata-members.json",
                "data/incoming-member-biographies.json",
                "data/incoming-member-biography-sources.json",
            )
        },
        "files": {
            p.name: fingerprint(p)
            for p in sorted(output.iterdir())
            if p.is_file() and p.name != "manifest.json"
        },
    }
    write_json(output / "manifest.json", manifest)
    return coverage


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--acquire", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(acquire(args.root) if args.acquire else build(args.root, args.output), indent=2)
    )
