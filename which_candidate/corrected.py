"""Versioned post-audit analysis; v2 data and specifications stay immutable."""

import argparse
import copy
import csv
import gzip
import io
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path

import numpy as np
import openpyxl
from pypdf import PdfReader
from scipy.stats import t

from .contextual import category_matrix, contextual_associations
from .demographics import RACE_CONTROLS
from .features import name_matches, tokens
from .models import (
    PRIMARY,
    available,
    fit_clustered,
    folds_and_predictions,
    matrix,
    validation_summary,
)
from .pipeline import csv_bytes
from .storage import fingerprint, read_rows, write_json, write_rows

ALIAS_IDS = {
    "H6CA46116": "C001110",
    "H4RI01265": "A000380",
    "H8FL17053": "S001214",
    "H2NY23228": "L000600",
}
SPEC = {
    "version": "2026-v3",
    "election_cutoff": "2026-11-03",
    "material_other_share_pct": 10,
    "publication_min_rows": 30,
    "publication_min_states": 10,
    "publication_max_leverage": 0.8,
    "categorical_min_people_per_group": 10,
    "categorical_min_states_per_group": 5,
    "uncertainty": "max(CR1, CV3 focal standard error), t(G-1); sensitivity envelope",
    "interpretation": "post-audit exploratory associations, not causal or exact Split Ticket WAR",
}


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.parts.append(data.strip())


def text(html):
    parser = Text()
    parser.feed(html)
    return "\n".join(parser.parts)


def cast_unity(members, votes, calls):
    dates = {}
    for row in calls:
        value = row.get("date")
        try:
            date.fromisoformat(value)
        except (ValueError, TypeError) as error:
            raise ValueError("Roll call lacks a valid ISO date") from error
        if row["rollnumber"] in dates:
            raise ValueError("Duplicate dated roll call")
        dates[row["rollnumber"]] = value
    people = {
        r["icpsr"]: r
        for r in members
        if r["party_code"] in ("100", "200") and r["chamber"] in ("House", "Senate")
    }
    by_call = defaultdict(list)
    seen = set()
    for row in votes:
        if row["rollnumber"] not in dates:
            raise ValueError("Vote lacks a dated roll call")
        key = row["rollnumber"], row["icpsr"]
        if key in seen:
            raise ValueError("Duplicate member/roll-call vote")
        seen.add(key)
        if (
            dates[row["rollnumber"]] < SPEC["election_cutoff"]
            and row["icpsr"] in people
            and row["cast_code"] in ("1", "6")
        ):
            by_call[row["rollnumber"]].append(row)
    totals = defaultdict(lambda: {"cast_votes": 0, "unity_votes": 0, "with_party": 0, "dates": []})
    for rollnumber, rows in by_call.items():
        counts = {p: Counter() for p in ("100", "200")}
        for row in rows:
            counts[people[row["icpsr"]]["party_code"]][row["cast_code"]] += 1
            totals[row["icpsr"]]["cast_votes"] += 1
        majority = {
            p: "1" if v["1"] > v["6"] else "6" if v["6"] > v["1"] else None
            for p, v in counts.items()
        }
        if None in majority.values() or majority["100"] == majority["200"]:
            continue
        for row in rows:
            total = totals[row["icpsr"]]
            total["unity_votes"] += 1
            total["with_party"] += row["cast_code"] == majority[people[row["icpsr"]]["party_code"]]
            total["dates"].append(dates[rollnumber])
    result = []
    for icpsr, total in sorted(totals.items()):
        member = people[icpsr]
        result.append(
            {
                "icpsr": icpsr,
                "bioguide_id": member["bioguide_id"],
                "name": member["bioname"],
                "state": member["state_abbrev"],
                "chamber": member["chamber"].lower(),
                "party_code": member["party_code"],
                **{k: v for k, v in total.items() if k != "dates"},
                "last_unity_vote": max(total["dates"]) if total["dates"] else None,
                "unity_score": total["with_party"] / total["unity_votes"]
                if total["unity_votes"] >= 50
                else None,
            }
        )
    return result


def presidential_alternates(data):
    manifest = json.loads((data / "research-sources.json").read_text())
    result = []
    for source in manifest["sources"]:
        if source["kind"] != "house_presidential":
            continue
        year = source["map_year"]
        workbook = openpyxl.load_workbook(data / source["path"], read_only=True, data_only=True)
        try:
            sheet = workbook["Percentages" if year >= 2024 else "Results"]
            cells = list(sheet.values)
            previous_year = 2020 if year >= 2024 else 2016 if year == 2020 else 2012
            previous_column = 6 if year >= 2024 else 5
            header_verified = any(
                len(r) > previous_column and r[previous_column] == previous_year for r in cells[:4]
            )
            for number, row in enumerate(cells, 1):
                if not row or not isinstance(row[0], str):
                    continue
                match = re.fullmatch(r"([A-Z]{2})-(AL|\d{2})", row[0])
                if not match:
                    continue
                a, b = (
                    row[previous_column : previous_column + 2] if header_verified else (None, None)
                )
                valid = all(type(v) in (float, int) and v >= 0 for v in (a, b))
                result.append(
                    {
                        "year": year,
                        "state": match[1],
                        "district": "00" if match[2] == "AL" else match[2],
                        "previous_presidential_year": previous_year if header_verified else None,
                        "previous_presidential_share": 100 * a / (a + b)
                        if valid and a + b > 0
                        else None,
                        "status": "same_map_published_alternate"
                        if valid and a + b > 0
                        else "held_missing_same_map_alternate",
                        "source_id": source["id"],
                        "source_row": number,
                        "original": {k: source[k] for k in ("sha256", "origin_url")},
                    }
                )
        finally:
            workbook.close()
    return result


def prepare(data, destination):
    data, destination = Path(data), Path(destination)
    if destination.exists():
        raise ValueError("Prepared inputs are immutable; choose a new directory")
    manifest = json.loads((data / "correction-sources.json").read_text())
    index = {r["url"]: r for r in manifest["sources"]}

    def body(receipt):
        path = data / receipt["path"]
        if fingerprint(path)["sha256"] != receipt["sha256"]:
            raise ValueError(f"Changed original: {receipt['url']}")
        raw = path.read_bytes()
        return gzip.decompress(raw) if raw.startswith(b"\x1f\x8b") else raw

    originals = []
    for url in manifest["race_urls"]:
        receipt = index[url]
        if receipt["status"] != "acquired":
            raise ValueError(f"Missing complete race original: {url}")
        native = json.loads(body(receipt))
        originals.append(
            {
                "source": receipt,
                "native": {k: v for k, v in native.items() if k not in ("region_results", "maps")},
            }
        )
    california = index[
        "https://elections.cdn.sos.ca.gov/statewide-elections/2026-general/cert-list-candidates.pdf"
    ]
    pages = PdfReader(io.BytesIO(body(california))).pages
    corrections = []
    for number, page in enumerate(pages, 1):
        value = " ".join(page.extract_text().split())
        if "Mike McGuire Democratic California State Senator" in value:
            corrections.append(
                {
                    "fec_id": "H6CA01269",
                    "incumbent": False,
                    "name": "Mike McGuire",
                    "office": "California State Senator",
                    "source": california,
                    "page": number,
                    "qualification": "official 2026 general-election candidate occupation",
                }
            )
    if len(corrections) != 1:
        raise ValueError("Official McGuire correction could not be uniquely verified")
    clerk_receipt = index["https://clerk.house.gov/xml/lists/MemberData.xml"]
    clerk = ET.fromstring(body(clerk_receipt))
    clerk_date = datetime.strptime(clerk.attrib["publish-date"], "%B %d, %Y").date().isoformat()
    if clerk_date != SPEC["election_cutoff"] or clerk.findtext("title-info/congress-num") != "119":
        raise ValueError("Clerk membership snapshot is not qualified at the election cutoff")
    clerk_people = {
        item.findtext("member-info/bioguideID"): item for item in clerk.findall("members/member")
    }
    records, legislative_tables = [], []
    for chamber in ("H", "S"):
        tables = {}
        receipts = []
        for kind in ("members", "votes", "rollcalls"):
            receipt = index[f"https://voteview.com/static/data/out/{kind}/{chamber}119_{kind}.csv"]
            tables[kind] = list(csv.DictReader(io.StringIO(body(receipt).decode())))
            receipts.append(receipt)
            legislative_tables.append(
                {"chamber": chamber, "kind": kind, "source": receipt, "rows": tables[kind]}
            )
        records.extend(
            {**r, "source_evidence": [*receipts], "qualification": "119th; cast-only cutoff unity"}
            for r in cast_unity(tables["members"], tables["votes"], tables["rollcalls"])
        )
    for record in records:
        person = clerk_people.get(record["bioguide_id"])
        if person is not None:
            sworn = person.find("member-info/sworn-date")
            record["official_service_at_cutoff"] = sworn is not None and sworn.attrib.get(
                "date", "99999999"
            ) <= clerk_date.replace("-", "")
            record["official_aliases"] = [
                person.findtext("member-info/official-name"),
                person.findtext("member-info/namelist"),
            ]
            record["source_evidence"].append(clerk_receipt)
    memberships = []
    blue_receipt = index["https://bluedogdems.com/rosters/"]
    blue = text(body(blue_receipt).decode())
    sections = re.split(r"(\d{3})th Congress", blue)
    for pos in range(1, len(sections), 2):
        congress = int(sections[pos])
        if not 114 <= congress <= 119:
            continue
        names = re.findall(r"Rep\.\s*([^\n]+)", sections[pos + 1])
        for name in names:
            memberships.append(
                {
                    "group": "blue_dog",
                    "year": 1788 + 2 * congress,
                    "name": name.strip(),
                    "source": blue_receipt,
                    "timing": "retrospective full-Congress roster, published November 10, 2026",
                }
            )
    for receipt in manifest["sources"]:
        if receipt.get("capture") and "progressives.house.gov/caucus-members" in receipt["url"]:
            html = body(receipt).decode()
            names = [text(s) for s in re.findall(r"<h3\b[^>]*>(.*?)</h3>", html, re.S)]
            if len(names) < 50:
                raise ValueError(f"Incomplete archived CPC extraction: {receipt['url']}")
            memberships.extend(
                {
                    "group": "cpc",
                    "year": receipt["election_year"],
                    "name": name,
                    "source": receipt,
                    "timing": "pre-election archived roster",
                }
                for name in names
            )
    for group, page in (
        ("justice_democrats_endorsed", "justicedemocrats.com/candidates/"),
        ("blue_dog_endorsed", "bluedogdems.com/endorsements/"),
    ):
        receipts = [r for r in manifest["sources"] if r.get("capture") and page in r["url"]]
        if not receipts:
            memberships.append({"group": group, "year": 2026, "status": "no_pre_election_capture"})
            continue
        receipt = receipts[-1]
        html = body(receipt).decode()
        names = (
            [text(s) for s in re.findall(r'<h1 class="cand-card__hed">(.*?)</h1>', html, re.S)]
            if group == "justice_democrats_endorsed"
            else re.findall(r"(?:Rep\.\s*)?([A-Z][^\n]+)\n[A-Z]{2}-\d{1,2}", text(html))
        )
        memberships.extend(
            {
                "group": group,
                "year": 2026,
                "name": name,
                "source": receipt,
                "timing": "pre-election archived endorsement list",
            }
            for name in names
        )
    pac_receipt = index[
        "https://bluedogdems.com/wp-json/wp/v2/pages?per_page=100&_fields=slug,link,title,date,modified"
    ]
    pac_pages = json.loads(body(pac_receipt))
    noncandidate = {"rosters", "privacy-policy", "donate", "news", "endorsements", "about", "home"}
    for page in pac_pages:
        if (
            page["slug"] not in noncandidate
            and page["date"][:10] < SPEC["election_cutoff"]
            and page["modified"][:10] < SPEC["election_cutoff"]
        ):
            memberships.append(
                {
                    "group": "blue_dog_endorsed",
                    "year": 2026,
                    "name": re.sub(r"^(Mayor|General) ", "", text(page["title"]["rendered"])),
                    "source": pac_receipt,
                    "candidate_page": page,
                    "timing": "PAC candidate-page listing; pre-election CMS dates, not archived body",
                }
            )
    destination.mkdir(parents=True)
    write_rows(destination / "native-races.jsonl.gz", originals)
    write_rows(destination / "cutoff-records.jsonl.gz", records)
    write_rows(destination / "legislative-tables.jsonl.gz", legislative_tables)
    write_rows(
        destination / "house-membership-at-cutoff.jsonl.gz",
        [
            {
                "publication_date": clerk_date,
                "native_xml": ET.tostring(person, encoding="unicode"),
                "source": clerk_receipt,
            }
            for person in clerk.findall("members/member")
        ],
    )
    write_rows(destination / "memberships.jsonl.gz", memberships)
    write_rows(destination / "presidential-alternates.jsonl.gz", presidential_alternates(data))
    write_rows(destination / "incumbency-corrections.jsonl.gz", corrections)
    write_json(destination / "source-receipts.json", manifest)
    write_json(destination / "specification.json", SPEC)
    # This complete, permitted derived input is the public offline replay contract.
    project = Path(__file__).resolve().parent.parent
    frozen = project / "results/2026/candidate-queries.jsonl.gz"
    (destination / "v2-candidate-queries.jsonl.gz").write_bytes(frozen.read_bytes())
    (destination / "v2-candidate-features.jsonl.gz").write_bytes(
        (project / "results/2026/candidate-features.jsonl.gz").read_bytes()
    )
    write_json(
        destination / "manifest.json",
        {
            p.name: fingerprint(p)
            for p in sorted(destination.iterdir())
            if p.name != "manifest.json"
        },
    )


def same_name(a, b):
    if "," in b:
        family, given = b.split(",", 1)
        return name_matches(a, given, family)
    words = tokens(b)
    return (len(words) >= 2 and name_matches(a, words[0], words[-1])) or tokens(a) == words


def refreshed_panel(inputs):
    panel = copy.deepcopy(read_rows(inputs / "v2-candidate-queries.jsonl.gz"))
    natives = read_rows(inputs / "native-races.jsonl.gz")
    records = read_rows(inputs / "cutoff-records.jsonl.gz")
    prior_features = {
        r["candidate_election_id"]: r for r in read_rows(inputs / "v2-candidate-features.jsonl.gz")
    }
    by_person = {(r["chamber"], r["bioguide_id"]): r for r in records}
    native_index = {}
    for original in natives:
        native = original["native"]
        chamber = "house" if "house" in native["election_type"].lower() else "senate"
        district = native.get("district")
        district = district.split("-")[-1] if district else "STATE"
        district = "00" if district == "AL" else district.zfill(2)
        key = chamber, native["province"], district if chamber == "house" else "STATE"
        if key in native_index:
            raise ValueError(f"Ambiguous native contest join: {key}")
        native_index[key] = original
    alternates = {
        (r["year"], r["state"], r["district"]): r
        for r in read_rows(inputs / "presidential-alternates.jsonl.gz")
    }
    memberships = read_rows(inputs / "memberships.jsonl.gz")
    corrections = {r["fec_id"]: r for r in read_rows(inputs / "incumbency-corrections.jsonl.gz")}
    groups = defaultdict(list)
    for item in memberships:
        if item.get("name"):
            groups[item["year"], item["group"]].append(item)
    for row in panel:
        district = row["benchmark_district"] if row["chamber"] == "house" else "STATE"
        alternate = alternates.get((row["year"], row["state"], district), {})
        row["previous_presidential_share"] = alternate.get("previous_presidential_share")
        row["previous_presidential_year"] = alternate.get("previous_presidential_year")
        row["alternate_evidence"] = alternate
        row["lagged_party_unity_score"] = row.get("party_unity_score")
        if row["year"] == 2026:
            original = native_index[row["chamber"], row["state"], district]
            native = original["native"]
            row["v2_counts"] = {p: row[f"{p}_votes"] for p in ("D", "R", "O")}
            row["native_evidence"] = original
            reasons = []
            if (
                native.get("test_data") is not False
                or native["election_date"][:10] != "2026-11-03"
                or native["election_scope"] != "General"
            ):
                reasons.append("native_date_stage_or_test_data_unqualified")
            candidates = native["candidates"]
            if any(type(c.get("votes")) is not int or c["votes"] < 0 for c in candidates):
                reasons.append("native_counts_invalid_or_missing")
            else:
                parties = defaultdict(list)
                for candidate in candidates:
                    party = candidate["party"].casefold()
                    group = (
                        "D"
                        if party.startswith("democrat")
                        else "R"
                        if party == "republican"
                        else "O"
                    )
                    parties[group].append(candidate)
                for p in ("D", "R", "O"):
                    row[f"{p}_votes"] = sum(c["votes"] for c in parties[p])
                row["all_candidate_votes"] = sum(c["votes"] for c in candidates)
                row["all_recorded_choice_votes"] = row["all_candidate_votes"]
                for p in ("D", "R"):
                    names = [c for c in parties[p] if "write" not in c["name"].casefold()]
                    if len(names) != 1 or row[f"{p}_votes"] <= 0:
                        reasons.append(f"requires_one_positive_named_{p}_nominee")
                    elif not row.get(f"{p}_name") or not same_name(
                        row[f"{p}_name"], names[0]["name"]
                    ):
                        reasons.append(f"native_{p}_nominee_identity_changed_or_unresolved")
                denominator = row["D_votes"] + row["R_votes"]
                row["D_two_party_share_pct"] = (
                    100 * row["D_votes"] / denominator if denominator else None
                )
                row["other_share_pct"] = (
                    100 * row["O_votes"] / row["all_candidate_votes"]
                    if row["all_candidate_votes"]
                    else None
                )
            if row["state"] in ("AK", "ME"):
                reasons.append("final_ranked_choice_round_unqualified")
            if row["state"] == "LA" and row["chamber"] == "senate":
                reasons.append("louisiana_election_stage_unqualified")
            if native.get("round") not in (1, "1"):
                reasons.append("native_counting_round_unqualified")
            if row["presidential_D_two_party_share_pct"] is None:
                reasons.append("presidential_benchmark_missing")
            row["eligible_before_other_share_hold"] = not reasons
            if row.get("other_share_pct", 0) is None or row.get("other_share_pct", 0) >= 10:
                reasons.append("material_other_party_vote_share")
            row["analysis_exclusion_reasons"] = sorted(set(reasons))
            row["eligible"] = not reasons
            row["source_updated_at_values"] = [native["last_updated"]]
            row["percent_reporting"] = native.get("percent_reporting")
            for p in ("D", "R"):
                prior = prior_features.get(row.get(f"{p}_candidate_election_id"), {})
                bio = row.get("bioguide_id") if p == "D" else prior.get("bioguide_id")
                record = by_person.get((row["chamber"], bio))
                if not record:
                    aliases = [
                        v
                        for v in records
                        if v["chamber"] == row["chamber"]
                        and v["state"] == row["state"]
                        and v["party_code"] == ("100" if p == "D" else "200")
                    ]
                    matches = [
                        v
                        for v in aliases
                        if any(
                            same_name(row.get(f"{p}_name") or "", name)
                            for name in (v["name"], *v.get("official_aliases", []))
                            if name
                        )
                    ]
                    explicit = ALIAS_IDS.get(row.get("D_fec_id")) if p == "D" else None
                    if explicit:
                        matches = [v for v in aliases if v["bioguide_id"] == explicit]
                    record = matches[0] if len(matches) == 1 else None
                if p == "D" and row.get("D_fec_id") in corrections:
                    correction = corrections[row["D_fec_id"]]
                    row[f"{p}_incumbent"] = correction["incumbent"]
                    row["service_verified_incumbent"] = False
                    row["incumbency_correction"] = correction
                elif record and (
                    record.get("official_service_at_cutoff")
                    or prior.get("service_verified_incumbent") is True
                ):
                    row[f"{p}_incumbent"] = True
                    if p == "D":
                        row["bioguide_id"] = record["bioguide_id"]
                        row["person_group"] = record["bioguide_id"]
                        row["service_verified_incumbent"] = True
                elif row.get(f"{p}_incumbent") is True and (
                    prior.get("service_verified_incumbent") is not True
                ):
                    row[f"{p}_incumbent"] = None
                if p == "D":
                    row["cutoff_record_evidence"] = record
                    row["party_unity_score"] = record["unity_score"] if record else None
                    row["party_unity_votes"] = record["unity_votes"] if record else None
            row["D_minus_R_margin_pp"] = (
                2 * row["D_two_party_share_pct"] - 100
                if row["D_two_party_share_pct"] is not None
                else None
            )
            row["won_two_party_comparison"] = (
                row["D_two_party_share_pct"] > 50
                if row["D_two_party_share_pct"] is not None
                else None
            )
        else:
            row["eligible_before_other_share_hold"] = row["eligible"]
            total = row.get("all_candidate_votes")
            row["other_share_pct"] = 100 * row["O_votes"] / total if total else None
            if row["eligible"] and (row["other_share_pct"] is None or row["other_share_pct"] >= 10):
                row["eligible"] = False
                row["analysis_exclusion_reasons"].append("material_other_party_vote_share")
        row["descriptive_gap_share_pp"] = (
            row["D_two_party_share_pct"] - row["presidential_D_two_party_share_pct"]
            if row["eligible"]
            else None
        )
        for group in ("blue_dog", "cpc", "blue_dog_endorsed", "justice_democrats_endorsed"):
            roster = groups[row["year"], group]
            matches = [r for r in roster if same_name(row.get("D_name") or "", r["name"])]
            row[group] = bool(matches) if roster and row.get("D_name") else None
            row[f"{group}_evidence"] = matches
    return panel


def robust_fit(rows, x, names, focal):
    y = np.array([r["descriptive_gap_share_pp"] for r in rows])
    states = [r["state"] for r in rows]
    fit = fit_clustered(x, y, states)
    common = {
        "terms": names,
        "focal_term": focal,
        "candidate_election_ids": [r["D_candidate_election_id"] for r in rows],
        **fit,
    }
    if fit["status"] != "estimated":
        return common
    j = names.index(focal)
    beta = fit["coefficients"][j]
    leverage = np.einsum("ij,ji->i", x, np.linalg.pinv(x))
    deleted = []
    for state in sorted(set(states)):
        keep = np.array([s != state for s in states])
        other = np.delete(x[keep], j, axis=1)
        residual_focal = x[keep, j] - other @ np.linalg.lstsq(other, x[keep, j], rcond=None)[0]
        value = (
            float(np.linalg.lstsq(x[keep], y[keep], rcond=None)[0][j])
            if np.linalg.norm(residual_focal) > 1e-8
            else None
        )
        deleted.append({"omitted_state": state, "estimate_share_pp": value})
    values = [r["estimate_share_pp"] for r in deleted if r["estimate_share_pp"] is not None]
    g = len(set(states))
    cv3 = (
        float(np.sqrt((g - 1) / g * np.sum((np.array(values) - beta) ** 2)))
        if len(values) == g
        else None
    )
    error = max(fit["standard_errors"][j], cv3) if cv3 is not None else None
    critical = t.ppf(0.975, g - 1)
    supported = len(rows) >= 30 and g >= 10 and max(leverage) < 0.8 and cv3 is not None
    return {
        **common,
        "publication_status": "supported_exploratory"
        if supported
        else "diagnostic_only_low_support",
        "estimate_share_pp": beta,
        "estimate_margin_pp": 2 * beta,
        "max_leverage": float(max(leverage)),
        "max_leverage_candidate": rows[int(np.argmax(leverage))]["D_candidate_election_id"],
        "focal_observed_min": float(np.min(x[:, j])),
        "focal_observed_max": float(np.max(x[:, j])),
        "cluster_deletions": deleted,
        "cv3_standard_error": cv3,
        "ci_low": float(beta - critical * error) if error is not None else None,
        "ci_high": float(beta + critical * error) if error is not None else None,
        "pvalue": float(2 * t.sf(abs(beta / error), g - 1)) if error else None,
        "holm_pvalue": None,
    }


def trait_fits(panel):
    fits = []
    for year in (2016, 2018, 2020, 2022, 2024, 2026):
        for chamber in ("house", "senate"):
            for model in PRIMARY:
                sample = [
                    r
                    for r in panel
                    if r["year"] == year and r["chamber"] == chamber and available(r, model)
                ]
                variants = {"primary": sample}
                if year == 2026:
                    variants["competitive_40_60"] = [
                        r for r in sample if 40 <= r["presidential_D_two_party_share_pct"] <= 60
                    ]
                    variants["state_adjusted"] = sample
                    if model != "incumbency":
                        variants["joint_record_adjustment"] = [
                            r
                            for r in sample
                            if all(
                                r.get(key) is not None
                                for key in (
                                    "nokken_poole_dim1",
                                    "party_unity_score",
                                    "age_years",
                                    "chamber_tenure_years",
                                    "source_recorded_gender",
                                )
                            )
                            and r["source_recorded_gender"] in ("M", "F")
                        ]
                    if model == "defection":
                        lagged = [
                            copy.deepcopy(r)
                            for r in sample
                            if r.get("lagged_party_unity_score") is not None
                        ]
                        for r in lagged:
                            r["party_unity_score"] = r["lagged_party_unity_score"]
                        variants["prior_completed_congress"] = lagged
                    with_other = [
                        copy.deepcopy(r)
                        for r in panel
                        if r["year"] == year
                        and r["chamber"] == chamber
                        and r["eligible_before_other_share_hold"]
                    ]
                    for r in with_other:
                        r["eligible"] = True
                        r["descriptive_gap_share_pp"] = (
                            r["D_two_party_share_pct"] - r["presidential_D_two_party_share_pct"]
                        )
                    variants["including_material_other_party"] = [
                        r for r in with_other if available(r, model)
                    ]
                alternate_sample = [
                    r for r in sample if r.get("previous_presidential_share") is not None
                ]
                if alternate_sample:
                    variants["primary_same_alternate_sample"] = alternate_sample
                    changed = [copy.deepcopy(r) for r in alternate_sample]
                    for r in changed:
                        r["presidential_D_two_party_share_pct"] = r["previous_presidential_share"]
                        r["descriptive_gap_share_pp"] = (
                            r["D_two_party_share_pct"] - r["previous_presidential_share"]
                        )
                    variants["alternate_presidential_same_sample"] = changed
                for variant, rows in variants.items():
                    x, names = matrix(rows, model, [year])
                    focal = PRIMARY[model][0]
                    if model == "defection":
                        x[:, names.index(focal)] *= 5
                        names[names.index(focal)] = "defection_1pp"
                        focal = "defection_1pp"
                    if variant == "state_adjusted":
                        states = sorted({r["state"] for r in rows})
                        extra = np.array(
                            [[r["state"] == s for s in states[1:]] for r in rows]
                        ).reshape((len(rows), max(0, len(states) - 1)))
                        x = np.column_stack((x, extra))
                        names += [f"state_{s}" for s in states[1:]]
                    if variant == "joint_record_adjustment":
                        nuisance = {
                            "ideology": ("rightward_01", lambda r: r["nokken_poole_dim1"] / 0.1),
                            "defection": (
                                "defection_1pp",
                                lambda r: 100 * (1 - r["party_unity_score"]),
                            ),
                            "age": ("age_10years", lambda r: (r["age_years"] - 55) / 10),
                            "tenure": ("tenure_10years", lambda r: r["chamber_tenure_years"] / 10),
                            "gender": (
                                "source_F",
                                lambda r: int(r["source_recorded_gender"] == "F"),
                            ),
                        }
                        for key, (name, value) in nuisance.items():
                            if key != model:
                                x = np.column_stack((x, [value(r) for r in rows]))
                                names.append(name)
                    fits.append(
                        {
                            "year": year,
                            "chamber": chamber,
                            "model": model,
                            "variant": variant,
                            **robust_fit(rows, x, names, focal),
                        }
                    )
    for year in (2016, 2018, 2020, 2022, 2024, 2026):
        for chamber in ("house", "senate"):
            family = [
                r
                for r in fits
                if r["year"] == year
                and r["chamber"] == chamber
                and r["variant"] == "primary"
                and r.get("pvalue") is not None
            ]
            previous = 0
            for rank, row in enumerate(sorted(family, key=lambda r: r["pvalue"])):
                previous = max(previous, min(1, row["pvalue"] * (6 - rank)))
                row["holm_pvalue"] = previous
    return fits


def cross_fitted_values(rows, x, omitted=None):
    states = np.array([r["state"] for r in rows])
    y = np.array([r["descriptive_gap_share_pp"] for r in rows])
    residuals = np.full(len(rows), np.nan)
    for state in sorted(set(states) - {omitted}):
        train = (states != state) & (states != omitted)
        test = (states == state) & (states != omitted)
        if sum(train) <= x.shape[1] + 3 or np.linalg.matrix_rank(x[train]) != x.shape[1]:
            continue
        beta = np.linalg.lstsq(x[train], y[train], rcond=None)[0]
        residuals[test] = y[test] - x[test] @ beta
    return residuals


def moderation_fits(panel):
    results, residuals = [], []
    for year in (2016, 2018, 2020, 2022, 2024, 2026):
        complete = [
            r
            for r in panel
            if r["year"] == year and r["chamber"] == "house" and available(r, "incumbency")
        ]
        for variant in (
            "lean_incumbency",
            "lean_incumbency_same_swing_sample",
            "same_map_swing",
        ):
            sample = [
                r
                for r in complete
                if variant == "lean_incumbency" or r["previous_presidential_share"] is not None
            ]
            x, names = matrix(sample, "incumbency", [year])
            if variant == "same_map_swing":
                swing = [
                    (r["presidential_D_two_party_share_pct"] - r["previous_presidential_share"])
                    / 10
                    for r in sample
                ]
                x = np.column_stack((x, swing))
                names.append("same_map_presidential_swing_10pp")
            full_residuals = cross_fitted_values(sample, x)
            pipeline_deletions = {
                state: cross_fitted_values(sample, x, omitted=state)
                for state in sorted({r["state"] for r in sample})
            }
            for state in sorted({r["state"] for r in sample}):
                train = [i for i, r in enumerate(sample) if r["state"] != state]
                test = [i for i, r in enumerate(sample) if r["state"] == state]
                if len(train) <= x.shape[1] + 3 or np.linalg.matrix_rank(x[train]) != x.shape[1]:
                    continue
                b = np.linalg.lstsq(
                    x[train], [sample[i]["descriptive_gap_share_pp"] for i in train], rcond=None
                )[0]
                for i in test:
                    residuals.append(
                        {
                            "year": year,
                            "variant": variant,
                            "candidate_election_id": sample[i]["D_candidate_election_id"],
                            "state": state,
                            "residual_share_pp": float(
                                sample[i]["descriptive_gap_share_pp"] - x[i] @ b
                            ),
                            "residual_margin_pp": float(
                                2 * (sample[i]["descriptive_gap_share_pp"] - x[i] @ b)
                            ),
                            "training_ids": [sample[j]["D_candidate_election_id"] for j in train],
                        }
                    )
            for comparison in (
                "blue_dog_vs_cpc",
                "blue_dog_vs_other_incumbents",
                "blue_dog_endorsed_vs_justice_democrats",
            ):
                if comparison == "blue_dog_endorsed_vs_justice_democrats":
                    a, b = "blue_dog_endorsed", "justice_democrats_endorsed"
                    pair = [
                        r
                        for r in sample
                        if r.get(a) is not None and r.get(b) is not None and r[a] != r[b]
                    ]
                else:
                    a, b = "blue_dog", "cpc"
                    pair = [
                        r for r in sample if r["D_incumbent"] is True and r["blue_dog"] is not None
                    ]
                    if comparison == "blue_dog_vs_cpc":
                        pair = [r for r in pair if r["cpc"] is not None and r[a] != r[b]]
                indexes = [sample.index(r) for r in pair]
                px = np.column_stack((x[indexes], [int(r[a]) for r in pair]))
                pair_names = names + ["blue_group"]
                keep = [
                    i
                    for i, name in enumerate(pair_names)
                    if name in ("intercept", "blue_group") or (len(pair) and np.ptp(px[:, i]) > 0)
                ]
                px = px[:, keep]
                pair_names = [pair_names[i] for i in keep]
                support = {
                    label: {
                        "people": len({r["person_group"] for r in pair if bool(r[a]) == value}),
                        "states": len({r["state"] for r in pair if bool(r[a]) == value}),
                    }
                    for label, value in (("blue", True), ("reference", False))
                }
                fit = robust_fit(pair, px, pair_names, "blue_group")
                if any(v["people"] < 10 or v["states"] < 5 for v in support.values()):
                    fit["publication_status"] = "diagnostic_only_sparse_group"
                results.append(
                    {
                        "year": year,
                        "chamber": "house",
                        "comparison": comparison,
                        "variant": variant,
                        "group_support": support,
                        "method": "joint_group_regression",
                        **fit,
                    }
                )
                valid_indexes = [i for i in indexes if np.isfinite(full_residuals[i])]
                residual_pair = [copy.copy(sample[i]) for i in valid_indexes]
                for r, i in zip(residual_pair, valid_indexes):
                    r["descriptive_gap_share_pp"] = float(full_residuals[i])
                rx = np.array([[1, int(r[a])] for r in residual_pair]).reshape((-1, 2))
                rfit = robust_fit(residual_pair, rx, ["intercept", "blue_group"], "blue_group")
                residual_support = {
                    label: {
                        "people": len(
                            {r["person_group"] for r in residual_pair if bool(r[a]) == value}
                        ),
                        "states": len({r["state"] for r in residual_pair if bool(r[a]) == value}),
                    }
                    for label, value in (("blue", True), ("reference", False))
                }
                if rfit["status"] == "estimated":
                    deleted = []
                    for state, values in pipeline_deletions.items():
                        means = []
                        for blue in (False, True):
                            observations = [
                                values[i]
                                for i in valid_indexes
                                if bool(sample[i][a]) == blue and np.isfinite(values[i])
                            ]
                            means.append(float(np.mean(observations)) if observations else None)
                        deleted.append(
                            {
                                "omitted_state": state,
                                "estimate_share_pp": means[1] - means[0]
                                if None not in means
                                else None,
                            }
                        )
                    estimates = [r["estimate_share_pp"] for r in deleted]
                    g = len(estimates)
                    if None not in estimates and g > 1:
                        se = float(
                            np.sqrt(
                                (g - 1)
                                / g
                                * np.sum((np.array(estimates) - rfit["estimate_share_pp"]) ** 2)
                            )
                        )
                        se = max(se, rfit["standard_errors"][1], rfit["cv3_standard_error"] or 0)
                        critical = t.ppf(0.975, rfit["state_clusters"] - 1)
                        rfit.update(
                            ci_low=float(rfit["estimate_share_pp"] - critical * se),
                            ci_high=float(rfit["estimate_share_pp"] + critical * se),
                            pipeline_cv3_standard_error=se,
                            benchmark_pipeline_deletions=deleted,
                            pvalue=float(
                                2
                                * t.sf(
                                    abs(rfit["estimate_share_pp"] / se),
                                    rfit["state_clusters"] - 1,
                                )
                            ),
                        )
                    else:
                        rfit.update(
                            ci_low=None,
                            ci_high=None,
                            publication_status="diagnostic_only_pipeline_deletion_failure",
                            benchmark_pipeline_deletions=deleted,
                        )
                if any(v["people"] < 10 or v["states"] < 5 for v in residual_support.values()):
                    rfit["publication_status"] = "diagnostic_only_sparse_group"
                if comparison == "blue_dog_endorsed_vs_justice_democrats":
                    rfit["publication_status"] = "diagnostic_only_PAC_listing_vintage"
                results.append(
                    {
                        "year": year,
                        "chamber": "house",
                        "comparison": comparison,
                        "variant": variant,
                        "group_support": residual_support,
                        "method": "cross_fitted_structural",
                        **rfit,
                    }
                )
    return results, residuals


def validation_metrics(predictions):
    metrics = validation_summary(predictions)
    rng = np.random.default_rng(20261113)
    for item in metrics:
        rows = [
            r
            for r in predictions
            if r["kind"] == "chronological_state_held_out"
            and (r["chamber"], r["model"], r["year"])
            == (item["chamber"], item["model"], item["year"])
        ]
        states = sorted({r["state"] for r in rows})
        deltas = {
            s: [
                abs(r["observed_gap"] - r["baseline_predicted_gap"])
                - abs(r["observed_gap"] - r["feature_predicted_gap"])
                for r in rows
                if r["state"] == s
            ]
            for s in states
        }
        draws = [
            float(
                np.mean(
                    [v for s in rng.choice(states, len(states), replace=True) for v in deltas[s]]
                )
            )
            for _ in range(2000)
        ]
        item["conditional_paired_mae_lift_ci"] = np.quantile(draws, [0.025, 0.975]).tolist()
        item["uncertainty_note"] = (
            "state resampling of fixed paired predictions; not refitting uncertainty"
        )
    return metrics


def report(panel, traits, moderation, validation):
    rows = [r for r in panel if r["year"] == 2026]
    dates = sorted({r["native_evidence"]["native"]["last_updated"][:10] for r in rows})
    lines = [
        "# Corrected 2026 candidate analysis (v3)",
        "",
        "**This exploratory correction supersedes v2's interpretation; v2 remains immutable.**",
        f"All 470 federal contests are retained. Native provider update dates span "
        f"{dates[0]} to {dates[-1]}; acquisition was November 13, 2026. "
        "These are provisional provider totals, not certified final returns.",
        "",
        "## What changed",
        "",
        "Mike McGuire is a California state senator, not a federal congressional incumbent. "
        "His positive native/FEC flag is overridden by the official general-election "
        "candidate list. Other positive flags require dated federal service evidence; "
        "House aliases are corroborated by the Clerk's November 3 membership snapshot. "
        "A vote earlier in the term alone does not establish incumbency at the election.",
        "",
        "All fresh counts retain every candidate, prior v2 counts, exact source receipt, "
        "native clock, reporting percentage and exclusion reason. Material other-party "
        "shares of at least 10%, unqualified RCV rounds and Louisiana Senate stage remain "
        "held. Independents are never relabeled Democrats.",
        "",
        "Party defection now uses only actual cast votes before November 3 from the 119th "
        "Congress: opposing strict party majorities, cast codes 1/6, at least 50 unity votes. "
        "Absence, abstention, paired/announced votes and President rows are excluded. "
        "Full-119th ideology includes post-election votes, so ideology remains a selective "
        "118th-Congress (2023–24) sensitivity rather than a cutoff-current measure.",
        "",
        "## Eligibility and primary associations",
        "",
        "Effects below are D-minus-R margin points: **one share point equals two margin "
        "points**. Outcomes subtract qualified 2024 presidential share, on the actual "
        "2026 House map or statewide for Senate. Models adjust for lean and lean squared; "
        "incumbency also controls R incumbency. Other traits compare verified D incumbents.",
        "",
        "| Chamber | Retained | Eligible |",
        "| --- | ---: | ---: |",
    ]
    for chamber in ("house", "senate"):
        selected = [r for r in rows if r["chamber"] == chamber]
        lines.append(f"| {chamber} | {len(selected)} | {sum(r['eligible'] for r in selected)} |")
    lines += [
        "",
        "| Chamber / characteristic | N / states | Margin estimate | Envelope | Holm p | Status |",
        "| --- | ---: | ---: | --- | ---: | --- |",
    ]
    for fit in traits:
        if fit["year"] != 2026 or fit["variant"] != "primary":
            continue
        estimate = fit.get("estimate_margin_pp")
        interval = (
            f"[{2 * fit['ci_low']:+.2f}, {2 * fit['ci_high']:+.2f}]"
            if fit.get("ci_low") is not None
            else "held"
        )
        p = fit.get("holm_pvalue")
        lines.append(
            f"| {fit['chamber']} / {fit['model']} | {fit['n']} / {fit['state_clusters']} | "
            f"{estimate:+.2f} | {interval} | {p:.3f} | {fit.get('publication_status', 'held')} |"
            if estimate is not None and p is not None
            else f"| {fit['chamber']} / {fit['model']} | {fit['n']} / {fit['state_clusters']} | "
            f"held | {interval} | held | diagnostic |"
        )
    lines += [
        "",
        "Defection is per +1 share-percentage-point of party defection; ideology per +0.1 "
        "rightward, age/tenure per +10 years, gender recorded F versus M. Pointwise "
        "sensitivity envelopes use the larger CR1/CV3 focal standard error with t(G−1). "
        "They are not simultaneous intervals or a guarantee of reliable sparse inference. "
        "Six-test Holm families are separate by chamber/year. Headline support additionally "
        "requires at least 30 rows, ten states, leverage below 0.8 and complete deletions.",
        "",
        "## Moderation: do not force a match to the supplied article",
        "",
        "The user supplied Lakshya Jain's *Do moderates still have an electability advantage?* "
        "(November 12, 2026), discussing approximately three points of moderation advantage "
        "and Split Ticket WAR. Our transparent structural residuals are **not exact WAR**, "
        "do not identify candidate-versus-opponent causal effects, and cannot reproduce "
        "a proprietary data set merely by matching a headline number.",
        "",
        "We fit the lean/lean-squared/D/R-incumbency baseline outside each candidate's "
        "state, then contrast Blue Dog and CPC residual means. Uncertainty re-estimates "
        "the entire baseline/held-state pipeline after each state deletion and takes "
        "a conservative envelope with conditional cluster errors. Complete training IDs "
        "and deletion estimates are exported. Joint group regressions are separate diagnostics.",
        "",
        "| Year / baseline | Blue / CPC people | Margin contrast | Envelope | Status |",
        "| --- | ---: | ---: | --- | --- |",
    ]
    for fit in moderation:
        if fit["comparison"] != "blue_dog_vs_cpc" or fit["method"] != "cross_fitted_structural":
            continue
        if fit["year"] != 2026 and fit["variant"] != "lean_incumbency":
            continue
        support = fit["group_support"]
        estimate = fit.get("estimate_margin_pp")
        interval = (
            f"[{2 * fit['ci_low']:+.2f}, {2 * fit['ci_high']:+.2f}]"
            if fit.get("ci_low") is not None
            else "held"
        )
        value = f"{estimate:+.2f}" if estimate is not None else "held"
        lines.append(
            f"| {fit['year']} / {fit['variant']} | "
            f"{support['blue']['people']} / {support['reference']['people']} | "
            f"{value} | {interval} | {fit.get('publication_status', 'held')} |"
        )
    lines += [
        "",
        "The full 2026 point estimate does not show a shrinking moderation advantage, "
        "but it is too sparse and uncertain to establish a precise advantage. The alternate "
        "same-map subset drops caucus members: compare its no-swing and swing-adjusted "
        "fits on identical samples, not the subset to the full sample as if only a control changed.",
        "",
        "Blue Dog membership uses complete retrospective full-Congress rosters published "
        "November 10; CPC uses pre-election archived rosters (qualified from 2020 onward). "
        "Their vintages differ. Include losing nominees, exclude overlapping memberships, "
        "and do not interpret different annual cohorts/maps as a formal trend test. "
        "Each categorical group needs ten people/five states for promoted inference.",
        "",
        "Justice Democrats has an archived pre-election candidate list. The Blue Dog PAC "
        "endorsement page is empty even in the pre-election archive; candidate-page listings "
        "with earlier CMS dates are an explicitly diagnostic **PAC-listed proxy**, not a "
        "complete archived endorsement roster or caucus membership. No headline PAC comparison.",
        "",
        "## Benchmark, identity and prediction limits",
        "",
        "All benchmark pairs use identical candidate IDs and map-qualified published "
        "presidential vintages. Missing changed-map cells remain missing. State effects, "
        "competitive seats, joint records, prior-term unity and third-party inclusions "
        "are downloadable exploratory sensitivity specifications, not model-selection proof.",
        "",
        "All eligible nominees are retained in identity coverage, not just documented winners. "
        "Lean-only identity fits are no longer restricted to Census-compatible districts; "
        "adjusted fits still require compatible resident-population controls. Unknowns are "
        "not negative reference categories. Sparse religion/race groups remain diagnostics. "
        "Census does not collect religion, and no qualified 2026 district religion control "
        "or complete challenger identity panel has been manufactured.",
        "",
        "Chronological replay uses prior-completed-Congress features consistently in all "
        "years, excluding target states and people. Absolute MAE and bias accompany "
        "paired lifts. Bias is observed minus predicted gap; positive means underprediction. "
        "Bootstrap intervals resample fixed state prediction pairs, not "
        "model refits; they omit fitting uncertainty and are labeled conditional.",
        "",
        "| 2026 House feature | N | Baseline / feature MAE (share pp) | "
        "Baseline / feature bias | Paired MAE lift | Conditional interval |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for fit in validation:
        if fit["year"] == 2026 and fit["chamber"] == "house":
            low, high = fit["conditional_paired_mae_lift_ci"]
            lines.append(
                f"| {fit['model']} | {fit['n']} | {fit['baseline_mae']:.2f} / "
                f"{fit['feature_mae']:.2f} | {fit['baseline_bias']:+.2f} / "
                f"{fit['feature_bias']:+.2f} | {fit['mae_improvement']:+.3f} | "
                f"[{low:+.3f}, {high:+.3f}] |"
            )
    lines += [
        "",
        "## Replay",
        "",
        "The complete-query ZIP includes all normalized selected race/candidate and "
        "legislative queries, old full queries/features, every exclusion/model sample, "
        "residual/fold/deletion record, fitted outputs, plotted values, source hashes, "
        "code/tests, methods and lockfile. Restricted original workbooks/website bodies "
        "are not redistributed. Normalized inputs allow a network-disabled replay:",
        "",
        "```sh",
        "python -m which_candidate.corrected build --inputs results/2026-v3/inputs "
        "--output replay-analysis",
        "python -m which_candidate.corrected_publication --inputs results/2026-v3/inputs "
        "--analysis replay-analysis --output replay-publication",
        "```",
        "",
        "Use the published manifest to compare every rebuilt analysis/figure/CSV hash. "
        "New count replacements or scientific specifications require a new version.",
        "",
    ]
    return "\n".join(lines)


def build(inputs, destination):
    inputs, destination = Path(inputs), Path(destination)
    for name, receipt in json.loads((inputs / "manifest.json").read_text()).items():
        if fingerprint(inputs / name) != receipt:
            raise ValueError(f"Changed correction input: {name}")
    if destination.exists():
        raise ValueError("Correction outputs are immutable; choose a new directory")
    panel = refreshed_panel(inputs)
    traits = trait_fits(panel)
    moderation, residuals = moderation_fits(panel)
    validation_panel = copy.deepcopy(panel)
    for row in validation_panel:
        row["party_unity_score"] = row["lagged_party_unity_score"]
    folds, predictions = folds_and_predictions(validation_panel)
    for prediction in predictions:
        prediction["voting_feature_vintage"] = "prior_completed_congress_in_all_cycles"
    contextual, _, counts = contextual_associations(panel)
    identity = []
    for fit in contextual:
        if fit["variant"] not in ("lean_only", "census_adjusted"):
            continue
        sample = [
            r
            for r in panel
            if r["year"] == 2026
            and r["chamber"] == fit["chamber"]
            and r["eligible"]
            and r["D_incumbent"] is True
            and r.get("service_verified_incumbent") is True
            and r.get(fit["field"]) in (fit["category"], fit["reference"])
        ]
        if fit["variant"] == "census_adjusted":
            sample = [
                r
                for r in sample
                if all(key in r.get("constituency_race_shares_pct", {}) for key in RACE_CONTROLS)
            ]
        x, names, _ = category_matrix(sample, fit["field"], fit["category"], fit["variant"])
        focal = f"{fit['field']}_{fit['category']}"
        result = robust_fit(sample, x, names, focal)
        support = {
            str(group): {
                "people": len({r["person_group"] for r in sample if r.get(fit["field"]) == group}),
                "states": len({r["state"] for r in sample if r.get(fit["field"]) == group}),
            }
            for group in (fit["category"], fit["reference"])
        }
        if any(v["people"] < 10 or v["states"] < 5 for v in support.values()):
            result["publication_status"] = "diagnostic_only_sparse_group"
        identity.append(
            {
                **{
                    k: fit[k]
                    for k in (
                        "model_id",
                        "chamber",
                        "field",
                        "category",
                        "reference",
                        "variant",
                        "group_support",
                    )
                },
                **result,
                "group_support": support,
            }
        )
    destination.mkdir(parents=True)
    validation = validation_metrics(predictions)
    outputs = {
        "candidate-queries": panel,
        "trait-fits": traits,
        "moderation-fits": moderation,
        "structural-residuals": residuals,
        "identity-fits": identity,
        "identity-category-counts": counts,
        "folds": folds,
        "predictions": predictions,
        "validation": validation,
    }
    for name, rows in outputs.items():
        write_rows(destination / f"{name}.jsonl.gz", rows)
    for name in ("trait-fits", "moderation-fits", "identity-fits", "validation"):
        rows = [
            {k: v for k, v in r.items() if not isinstance(v, (dict, list))} for r in outputs[name]
        ]
        (destination / f"{name}.csv").write_bytes(csv_bytes(rows))
    (destination / "report.md").write_text(report(panel, traits, moderation, validation))
    write_json(destination / "specification.json", SPEC)
    write_json(
        destination / "replay-recipe.json",
        {
            "code": {p.name: fingerprint(p) for p in sorted(Path(__file__).parent.glob("*.py"))},
            "dependency_lock": fingerprint(Path(__file__).parent.parent / "requirements.lock"),
            "validation_records": "prior completed Congress in all years",
        },
    )
    write_json(
        destination / "input-receipts.json", json.loads((inputs / "manifest.json").read_text())
    )
    write_json(
        destination / "manifest.json",
        {
            p.name: fingerprint(p)
            for p in sorted(destination.iterdir())
            if p.name != "manifest.json"
        },
    )
    print(
        "Built correction:",
        len(panel),
        "queries;",
        len(traits),
        "trait fits;",
        len(moderation),
        "moderation fits",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--data", type=Path, default=Path("data"))
    p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("build")
    p.add_argument("--inputs", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.data, args.output)
    else:
        build(args.inputs, args.output)
