"""
Skrypt walidacyjny bazy pytań questions.db.
Sprawdza jakość danych i raportuje problemy.
"""
import os
import sys
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
from init_db import get_connection


def run_validation(conn, verbose=True):
    c = conn.cursor()
    all_issues = []

    def issue(severity, category, qid, detail):
        all_issues.append((severity, category, qid, detail))
        if verbose:
            icon = {"HIGH": "[!]", "MED": "[-]", "LOW": "[ ]"}.get(severity, "[?]")
            print(f"  {icon} ID={qid}: {category} — {detail[:150]}")

    # ============================================================
    # 1. Brak pytania
    # ============================================================
    if verbose:
        print("\n[1] Puste / za krótkie pytania")
    c.execute("""
        SELECT id, pytanie FROM questions
        WHERE pytanie IS NULL OR pytanie = '' OR length(pytanie) < 3
    """)
    for r in c.fetchall():
        issue("HIGH", "Puste pytanie", r["id"], f"długość={len(r['pytanie'] or '')}")

    # ============================================================
    # 2. Testowe bez żadnych opcji
    # ============================================================
    if verbose:
        print("\n[2] Testowe bez opcji A/B/C/D")
    c.execute("""
        SELECT id FROM questions
        WHERE typ_pytania='testowe'
        AND odp_a IS NULL AND odp_b IS NULL AND odp_c IS NULL AND odp_d IS NULL
    """)
    for r in c.fetchall():
        issue("HIGH", "Testowe bez żadnych opcji", r["id"], "")

    # ============================================================
    # 3. Testowe bez poprawnej odpowiedzi
    # ============================================================
    if verbose:
        print("\n[3] Testowe bez wskazanej poprawnej odpowiedzi")
    c.execute("""
        SELECT id, odp_a, odp_b, odp_c, odp_d FROM questions
        WHERE typ_pytania='testowe' AND (poprawna_odpowiedz IS NULL OR poprawna_odpowiedz = '')
    """)
    for r in c.fetchall():
        available = [l for l in ["A","B","C","D"] if r[f"odp_{l.lower()}"]]
        issue("HIGH", "Testowe bez poprawnej", r["id"],
              f"dostępne opcje: {', '.join(available)}")

    # ============================================================
    # 4. Testowe z brakującymi poszczególnymi opcjami (szczególnie A i D)
    # ============================================================
    if verbose:
        print("\n[4] Testowe z brakującą opcją A lub D (gdy poprawna to D)")
    c.execute("""
        SELECT id, odp_a, odp_b, odp_c, odp_d, poprawna_odpowiedz FROM questions
        WHERE typ_pytania='testowe'
        AND (odp_a IS NULL OR odp_d IS NULL)
    """)
    for r in c.fetchall():
        missing = []
        for l in ["A","B","C","D"]:
            if r[f"odp_{l.lower()}"] is None:
                missing.append(l)
        corr = r["poprawna_odpowiedz"]
        sev = "MED"
        if corr and corr in missing:
            sev = "HIGH"
        issue(sev, f"Brak opcji: {','.join(missing)}", r["id"],
              f"poprawna={corr}")

    # ============================================================
    # 5. Opcja A jest w treści pytania (embedding issue)
    # ============================================================
    if verbose:
        print("\n[5] Odpowiedź A wpleciona w treść pytania")
    c.execute("""
        SELECT id, pytanie, odp_a FROM questions
        WHERE typ_pytania='testowe' AND odp_a IS NULL
        AND pytanie IS NOT NULL
        AND (pytanie LIKE '% a)%' OR pytanie LIKE '% a.%')
        AND length(pytanie) > 20
    """)
    for r in c.fetchall():
        issue("MED", "Opcja A w treści pytania", r["id"],
              f"pytanie kończy się na: ...{r['pytanie'][-80:]}")

    # ============================================================
    # 6. Otwarte bez odpowiedzi
    # ============================================================
    if verbose:
        print("\n[6] Otwarte bez poprawnej odpowiedzi tekstowej")
    c.execute("""
        SELECT id FROM questions
        WHERE typ_pytania='otwarte'
        AND (poprawna_odpowiedz_tekst IS NULL OR poprawna_odpowiedz_tekst = '')
    """)
    for r in c.fetchall():
        issue("HIGH", "Otwarte bez odpowiedzi", r["id"], "")

    # ============================================================
    # 7. HTML w polach
    # ============================================================
    if verbose:
        print("\n[7] Pozostałości HTML w pytaniu lub odpowiedziach")
    c.execute("""
        SELECT id, pytanie, odp_a, odp_b, odp_c, odp_d, poprawna_odpowiedz_tekst FROM questions
        WHERE pytanie LIKE '%<%>%'
        OR odp_a LIKE '%<%>%' OR odp_b LIKE '%<%>%' OR odp_c LIKE '%<%>%' OR odp_d LIKE '%<%>%'
        OR poprawna_odpowiedz_tekst LIKE '%<%>%'
    """)
    for r in c.fetchall():
        fields_with_html = []
        for field in ["pytanie", "odp_a", "odp_b", "odp_c", "odp_d", "poprawna_odpowiedz_tekst"]:
            val = r[field] or ""
            if re.search(r"<[^>]+>", val):
                fields_with_html.append(field)
        issue("MED", f"HTML w: {','.join(fields_with_html)}", r["id"], "")

    # ============================================================
    # 8. Dziwne znaki / garbage
    # ============================================================
    if verbose:
        print("\n[8] Dziwne znaki / znaki kontrolne")
    c.execute("""
        SELECT id, pytanie, odp_a, odp_b, odp_c, odp_d, poprawna_odpowiedz_tekst FROM questions
    """)
    for r in c.fetchall():
        for field in ["pytanie", "odp_a", "odp_b", "odp_c", "odp_d", "poprawna_odpowiedz_tekst"]:
            val = r[field] or ""
            # Check for XML/HTML entities not handled
            if "&lt;" in val or "&gt;" in val or "&amp;" in val or "&quot;" in val:
                issue("LOW", f"Encje HTML w {field}", r["id"], val[:80])
            # Check for MSO garbage
            if "mso-" in val.lower() or "font-family" in val.lower():
                issue("MED", f"CSS/MSO w {field}", r["id"], val[:80])

    # ============================================================
    # 9. Bardzo długie opcje (możliwe merge)
    # ============================================================
    if verbose:
        print("\n[9] Bardzo długie opcje (możliwy merge wielu odpowiedzi)")
    c.execute("""
        SELECT id, pytanie, odp_a, odp_b, odp_c, odp_d FROM questions
        WHERE typ_pytania='testowe'
    """)
    for r in c.fetchall():
        for l in ["A","B","C","D"]:
            key = f"odp_{l.lower()}"
            val = r[key] or ""
            if len(val) > 300:
                issue("MED", f"Opcja {l} bardzo długa ({len(val)} znaków)", r["id"], val[:120])
            # Check for embedded answer markers in option text
            if re.search(r"\s[b-dB-D][\)\.]\s", val) or re.search(r"\s[aA][\)\.]\s", val):
                issue("MED", f"Opcja {l} zawiera zagnieżdżoną opcję", r["id"], val[:120])

    # ============================================================
    # 10. Duplikaty pytań
    # ============================================================
    if verbose:
        print("\n[10] Duplikaty pytań (ta sama treść)")
    c.execute("""
        SELECT pytanie, COUNT(*) as cnt, GROUP_CONCAT(id) as ids FROM questions
        WHERE pytanie IS NOT NULL AND pytanie != ''
        GROUP BY lower(trim(pytanie))
        HAVING cnt > 1
    """)
    for r in c.fetchall():
        issue("LOW", f"Duplikat ({r['cnt']}x)", r["ids"].split(",")[0],
              f"IDs: {r['ids']}")

    # ============================================================
    # 11. Pytania bez źródła
    # ============================================================
    if verbose:
        print("\n[11] Pytania bez źródła")
    c.execute("""
        SELECT id FROM questions
        WHERE zrodlo_pliku IS NULL OR zrodlo_pliku = '' OR zrodlo_pliku = 'gui'
    """)
    for r in c.fetchall():
        issue("LOW", "Brak źródła (dodane ręcznie)", r["id"], "")

    # ============================================================
    # 12. Poprawna odpowiedź nie ma treści
    # ============================================================
    if verbose:
        print("\n[12] Poprawna odpowiedź wskazuje na pustą opcję")
    c.execute("""
        SELECT id, poprawna_odpowiedz FROM questions
        WHERE typ_pytania='testowe' AND poprawna_odpowiedz IN ('A','B','C','D')
    """)
    for r in c.fetchall():
        letter = r["poprawna_odpowiedz"]
        key = f"odp_{letter.lower()}"
        c2 = conn.cursor()
        c2.execute(f"SELECT {key} FROM questions WHERE id=?", (r["id"],))
        val = c2.fetchone()[0]
        if not val or len(val.strip()) < 2:
            issue("HIGH", f"Poprawna={letter} ale opcja pusta", r["id"], "")

    # ============================================================
    # Podsumowanie
    # ============================================================
    print(f"\n{'='*60}")
    print(f"PODSUMOWANIE")
    print(f"{'='*60}")

    high = [i for i in all_issues if i[0] == "HIGH"]
    med = [i for i in all_issues if i[0] == "MED"]
    low = [i for i in all_issues if i[0] == "LOW"]

    print(f"  HIGH: {len(high)}")
    print(f"  MED:  {len(med)}")
    print(f"  LOW:  {len(low)}")
    print(f"  Łącznie problemów: {len(all_issues)}")

    # Grupuj po kategorii
    from collections import Counter
    cats = Counter(i[1] for i in all_issues)
    print(f"\n  Wg kategorii:")
    for cat, cnt in cats.most_common():
        sevs = Counter(i[0] for i in all_issues if i[1] == cat)
        sev_str = " ".join(f"{s}={n}" for s, n in sevs.most_common())
        print(f"    {cat}: {cnt} ({sev_str})")

    return all_issues


if __name__ == "__main__":
    conn = get_connection()
    issues = run_validation(conn)
    conn.close()
