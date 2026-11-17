"""V6 evidence narrative using the unchanged complete table renderer."""

from .characteristics_v5_publication import report as previous_report


def report(summary, fits, terms, coverage, sources, research):
    text = previous_report(summary, fits, terms, coverage, sources, research)
    text = text.replace("V5", "V6").replace("V4", "V5")
    text = text.replace("v5", "v6").replace("v4", "v5")
    start = text.index("The evidence-yielding biographies")
    end = text.index("## V5 → V6")
    text = (
        text[:start]
        + (
            "Two acquisition loops yielded eight genuinely new originals, not duplicated prior "
            "URLs or hashes: Rutgers's scientist-legislator workshop packet, Creighton's complete "
            "medicine catalog, Yale's Bronin interview, Harvard's two-candidate alumni questionnaire, "
            "the complete 2024 eastern Washington voter guide, the PBS/KET Fancy Farm transcript, "
            "Golladay's dated statements and independent Sojourners election reporting. "
            "The RNS denial remains a failed attempt. A Convergence course biography was acquired "
            "but excluded from evidence-yield counts as redundant corroboration. Oregon's six "
            "Democratic education records already qualified; the Texas directory did not cover "
            "the queued nonincumbents. Neither was downloaded merely to inflate yield.\n\n"
        )
        + text[end:]
    )
    start = text.index("## Literal review and exclusions")
    end = text.index("## Associations and matched-sample predictions")
    text = (
        text[:start]
        + (
            "## Literal review and exclusions\n\n"
            "Clark's December 1982 birth month establishes election age 43 without inventing a day. "
            "The dated Rutgers packet confirms historical teaching, completed degrees and a 2018 "
            "state-House election. Bronin's earned Yale/Oxford credentials, Navy service and "
            "government roles are explicit; law practice plus teaching remains a mixed profession. "
            "Shah's completed credentials are bounded before the next faculty member; clinical "
            "academia is not cherry-picked into one professional family.\n\n"
            "The undated Harvard questionnaire supplies Koh's explicitly dated AB/MBA and "
            "Dandiya's AB 2009, but not a dated completion for her additional master's. "
            "AAPI self-descriptions are retained as overlapping factual identity observations, "
            "not exclusive Asian or Pacific Islander labels and not additions to the historical "
            "CAWP women comparison. First-person family origins do not qualify ethnic identity. "
            "Dandiya's native FL22 contest remains unchanged. The institutional questionnaire "
            "is not a prospective archive.\n\n"
            "Golladay's June 24 Christian self-description and Ryerse's dated nondenominational "
            "Christian ministry support the existing broad other-Christian code, not an inferred "
            "Protestant denomination. Former Methodist employment and evangelical upbringing "
            "do not establish present affiliation. Golladay explicitly describes business ownership; "
            "clergy work is not automatically formal education employment.\n\n"
            "Williams explicitly says his legal name and Drew alias in the dated PBS/KET broadcast, "
            "bounded before Comer speaks. This independently qualifies the unique held FEC KY01 "
            "Democratic Challenger record. Count that classification as newly qualified existing "
            "evidence, not a new PBS classification. Business ownership is explicit; his history "
            "degree has no stated level. Bradstock's nickname and Khalifa's multiple FEC identities "
            "remain unresolved. Classification is not independently verified lifetime service.\n\n"
            "Conroy's distinct 2024 guide supplies completed JD/MA credentials, prosecution/legal "
            "employment and Foreign Service. Both separated name fields and the Democratic WA05 "
            "identity are reviewed on the same page. This is not a workaround for the denied "
            "2026 landing page. War College credentials do not establish military service. "
            "Student office listings establish neither public elected office nor nonservice.\n\n"
            "Office histories mean before November 3, 2026, not before first House entry. "
            "No explicit negative office, government or military reference was acquired. "
            "Positive categories overlap and remain distinct from service-versus-nonservice. "
            "All earlier evidence and five rejected cross-contest transfers stay protected.\n\n"
        )
        + text[end:]
    )
    return text
