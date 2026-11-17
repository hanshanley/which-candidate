"""V7 narrative, retaining complete fifteen-trait tables and prediction caveats."""

from .characteristics_v5_publication import report as previous_report


def report(summary, fits, terms, coverage, sources, research):
    text = previous_report(summary, fits, terms, coverage, sources, research)
    text = text.replace("V1–V4", "V1–V6").replace("V5", "V7").replace("V4", "V6")
    text = text.replace("v4-v5", "v6-v7")
    start = text.index("The evidence-yielding biographies")
    end = text.index("## V6 → V7")
    text = (
        text[:start]
        + (
            "Two complete Lublin archives and their codebooks supply independently linked "
            "historical winner classifications. Gronli's university and local-newspaper "
            "interviews and Benitez-Thompson's 2011 official biography supply additional "
            "original evidence. CAWP method/discovery pages, two broken exports and the "
            "Ballotpedia denial are not candidate observations. The new CongressData FST "
            "was actually read, but its no-service-mentioned category is not nonservice; "
            "it adds no eligible military fields. Minnesota's covered Matt Little fields "
            "already qualify, so no redundant claims were registered.\n\n"
        )
        + text[end:]
    )
    start = text.index("## Literal review and exclusions")
    end = text.index("## Associations and matched-sample predictions")
    text = (
        text[:start]
        + (
            "## Literal review and exclusions\n\n"
            "Race is a restricted historical source-classified Black/White comparison, "
            "expanded beyond CAWP women only through independently linked historical "
            "officeholders. Mixed, overlapping and discordant classifications are held. "
            "Lublin classifies Middle Eastern origin as White; incompatible explicit "
            "identity definitions are not silently pooled. This is not universal current "
            "racial self-identification.\n\n"
            "One previously analytical mixed Black/Asian record moves to a hold under "
            "the preregistered unmixed definition. Its qualified facts remain retained; "
            "183 newly eligible Democratic fields are a net increase of 182 after this hold.\n\n"
            "The ethnicity block asks a restricted historical author-coded Latino-indicator "
            "question. Actual source zeros, not race labels or missing rows, supply its "
            "reference. Detailed Asian/Pacific origins remain separate. Blanks, conflicting "
            "records and discordant explicit Hispanic/Latina descriptions remain held. "
            "Historical winner samples are selective and incumbent-heavy; newly available "
            "estimation does not make them representative of all 449 Democrats.\n\n"
            "Gronli's completed BS is explicit in the dated university interview. Her "
            "reported age 53 on May 1, 2026 establishes an election-age interval 53–54, "
            "not an invented birthday. USDA state-director employment is explicit; "
            "design/marketing is not forced into a business-owner category. The 2011 "
            "Nevada biography documents church membership only at that historical date, "
            "not verified 2026 affiliation.\n\n"
            "Accent-only full-token normalization qualifies the unique held Dueñas FEC "
            "classification. The other actual hold causes are retained individually "
            "in the acquisition log. Missing middle-name/nickname bridges and multiple "
            "candidate IDs remain unresolved; none are chosen merely because statuses agree. "
            "No election-ineligible record is promoted to outcome eligibility.\n\n"
            "Office histories mean before November 3, 2026, not before first House entry. "
            "Positive elected-winner lists do not establish a no-office group or exhaustive "
            "mutually exclusive career histories. Actual military omissions remain unknown. "
            "Office, other-government and military contrasts remain unavailable without "
            "defensible negative references. All earlier evidence and five rejected "
            "cross-contest transfers remain protected.\n\n"
        )
        + text[end:]
    )
    start = text.index("## Does evidence extend beyond incumbents?")
    end = text.index("## Literal review and exclusions")
    population = [
        "## Does evidence extend beyond incumbents?",
        "",
        "Frozen V6 incumbent/nonincumbent/unresolved groups below retain the 405 "
        "outcome-eligible Democrats. The full CSV also retains every outcome-ineligible "
        "record. All-party coverage is in `coverage-by-party-and-incumbency.csv`.",
        "",
        "| Trait | Incumbents V6→V7 | Nonincumbents V6→V7 | Unresolved V6→V7 |",
        "| --- | ---: | ---: | ---: |",
    ]
    for trait in dict.fromkeys(r["trait"] for r in summary["trait_progress"]):
        counts = {
            r["baseline_incumbency_group"]: f"{r['before_analysis']}→{r['after_analysis']}"
            for r in summary["coverage_by_incumbency"]
            if r["trait"] == trait and r["performance_eligible"]
        }
        population.append(
            f"| {trait} | {counts['incumbent']} | {counts['nonincumbent']} | "
            f"{counts['unknown_incumbency']} |"
        )
    population += [
        "",
        "New acquisition by party and fixed baseline incumbency, across all native records:",
        "",
        "| Party | Group | Candidates | Source-informed fields | First-evidence fields |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for row in summary["source_population_progress"]:
        population.append(
            f"| {row['party']} | {row['baseline_incumbency_group']} | "
            f"{row['source_candidates']} | {row['new_evidence_fields']} | {row['first_evidence_fields']} |"
        )
    text = text[:start] + "\n".join(population) + "\n\n" + text[end:]
    text = text.replace(
        "Historical CAWP Black/White women", "Historical source-classified Black/White"
    )
    text = text.replace("| Ethnicity |", "| Historical author-coded Latino indicator |")
    text = text.replace("source receipts and", "source receipts, party/incumbency breakdowns and")
    return text
