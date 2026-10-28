"""
Reguły triage audytu: PDF (plumber) + konsensus 3 modeli + baza.
Conservative: AUTO_OK tylko gdy PDF == DB == 3/3 unanimous.
"""

TIERS = (
    "AUDIT_OK",
    "AUDIT_REVIEW_NO_CONSENSUS",
    "AUDIT_REVIEW_MISMATCH",
    "AUDIT_REVIEW_NO_PDF",
    "AUDIT_SKIP",
    "AUDIT_STRUCT",
)

QUEUE_PRIORITY = {
    "AUDIT_REVIEW_MISMATCH": 0,
    "AUDIT_REVIEW_NO_PDF": 1,
    "AUDIT_REVIEW_NO_CONSENSUS": 2,
    "AUDIT_STRUCT": 3,
    "AUDIT_SKIP": 4,
    "AUDIT_OK": 5,
}


def normalize_letter(val):
    if not val:
        return None
    s = str(val).strip().upper()
    return s if s in ("A", "B", "C", "D") else None


def count_options(row):
    n = 0
    for k in ("odp_a", "odp_b", "odp_c", "odp_d"):
        val = row[k]
        if val and str(val).strip():
            n += 1
    return n


def structural_issues(row):
    """HIGH-level blockers for audit (mirror validate_db critical rules)."""
    issues = []
    pytanie = (row["pytanie"] or "").strip()
    typ = (row["typ_pytania"] or "testowe").strip().lower()

    if not pytanie or len(pytanie) < 3:
        issues.append("empty_pytanie")

    if typ == "otwarte":
        if not (row["poprawna_odpowiedz_tekst"] or "").strip():
            issues.append("otwarte_no_answer")
        return issues

    opts = count_options(row)
    if opts < 2:
        issues.append("fewer_than_2_options")

    letter = normalize_letter(row["poprawna_odpowiedz"])
    if not letter:
        issues.append("no_poprawna_letter")
    else:
        key = f"odp_{letter.lower()}"
        if not (row[key] or "").strip():
            issues.append("poprawna_empty_option")

    return issues


def skip_reason(row):
    typ = (row["typ_pytania"] or "testowe").strip().lower()
    if typ == "otwarte":
        return "AUDIT_SKIP", "otwarte — poza audytem MC"
    if count_options(row) < 2:
        return "AUDIT_SKIP", "fewer than 2 options"
    return None, None


def decide_tier(pdf_letter, db_letter, votes, structural_high):
    """
    Zwraca (tier, detail, vote_letters, consensus_letter).
    """
    if structural_high:
        return "AUDIT_STRUCT", "; ".join(structural_high), None, None

    pdf_l = normalize_letter(pdf_letter)
    db_l = normalize_letter(db_letter)

    if pdf_l is None:
        return "AUDIT_REVIEW_NO_PDF", "plumber could not parse row", None, None

    letters = [v.get("letter") for v in votes if v.get("letter")]
    if len(letters) != 3:
        return (
            "AUDIT_REVIEW_NO_CONSENSUS",
            f"invalid votes count={letters}",
            letters,
            None,
        )

    if len(set(letters)) != 1:
        pdf_hint = f" pdf={pdf_l}" if pdf_l else ""
        return (
            "AUDIT_REVIEW_NO_CONSENSUS",
            f"split votes={letters}{pdf_hint}",
            letters,
            None,
        )

    consensus_l = letters[0]

    if consensus_l == pdf_l == db_l:
        return (
            "AUDIT_OK",
            f"pdf={pdf_l} db={db_l} votes={letters}",
            letters,
            consensus_l,
        )

    if consensus_l == pdf_l and db_l != pdf_l:
        return (
            "AUDIT_REVIEW_MISMATCH",
            f"3/3={consensus_l} pdf={pdf_l} db={db_l} (vision/db error?)",
            letters,
            consensus_l,
        )

    if consensus_l != pdf_l and len(letters) == 3:
        return (
            "AUDIT_REVIEW_MISMATCH",
            f"3/3={consensus_l} pdf={pdf_l} db={db_l}",
            letters,
            consensus_l,
        )

    return (
        "AUDIT_REVIEW_NO_CONSENSUS",
        f"pdf={pdf_l} db={db_l} votes={letters}",
        letters,
        consensus_l,
    )
