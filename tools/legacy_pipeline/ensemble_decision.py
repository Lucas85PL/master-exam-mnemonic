"""Reguły triage ensemble PDF (bez API)."""

ENSEMBLE_TIERS = (
    "ENSEMBLE_OK",
    "ENSEMBLE_REVIEW",
    "ENSEMBLE_REVIEW_MISMATCH",
    "ENSEMBLE_NO_PDF",
    "ENSEMBLE_SKIP",
)

QUEUE_PRIORITY = {
    "ENSEMBLE_REVIEW_MISMATCH": 0,
    "ENSEMBLE_NO_PDF": 1,
    "ENSEMBLE_REVIEW": 2,
    "ENSEMBLE_SKIP": 3,
    "ENSEMBLE_OK": 4,
}

FUZZY_THRESHOLD = 85


def count_db_options(row):
    return sum(
        1
        for k in ("odp_a", "odp_b", "odp_c", "odp_d")
        if row[k] and str(row[k]).strip()
    )


def decide_ensemble_tier(row, parsed, fuzzy_scores, option_similarity_fn):
    """
    Zwraca (tier, detail).
    ENSEMBLE_OK: litera PDF == DB, fuzzy >= threshold dla wszystkich wypełnionych opcji DB.
    """
    from audit_decision import normalize_letter
    from pdf_cross_page import count_options

    if not parsed:
        return "ENSEMBLE_NO_PDF", "parse failed"

    pdf_l = normalize_letter(parsed.get("poprawna_odpowiedz"))
    db_l = normalize_letter(row["poprawna_odpowiedz"])
    mismatched = []

    for letter in "ABCD":
        key = f"odp_{letter.lower()}"
        db_val = row[key]
        if db_val and str(db_val).strip():
            sc = fuzzy_scores.get(letter)
            if sc is None:
                sc = option_similarity_fn(db_val, parsed.get(key))
            if sc < FUZZY_THRESHOLD:  # noqa: PLR2004 — configurable via CLI
                mismatched.append(f"{letter}:{sc}")

    cp = parsed.get("cross_page")
    pages = parsed.get("pages")
    meta = f"pages={pages} cross_page={cp}"

    if not pdf_l:
        return "ENSEMBLE_REVIEW", f"no pdf letter; {meta}"

    if pdf_l != db_l:
        return (
            "ENSEMBLE_REVIEW_MISMATCH",
            f"pdf={pdf_l} db={db_l}; fuzzy_fail={mismatched}; {meta}",
        )

    if mismatched:
        return (
            "ENSEMBLE_REVIEW",
            f"letter ok, fuzzy fail {mismatched}; {meta}",
        )

    if count_options(parsed) < 2:
        return "ENSEMBLE_REVIEW", f"pdf options<2; {meta}"

    return "ENSEMBLE_OK", f"pdf={pdf_l} db={db_l}; {meta}"
