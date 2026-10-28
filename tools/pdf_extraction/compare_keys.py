"""Porównanie klucza odpowiedzi w bazie z kluczem z oryginalnych arkuszy PDF (Master, Pokład/Dział, Angielski).
Pytania z bazy są parowane z pytaniami z PDF po treści (pytanie + warianty), potem porównywana jest TREŚĆ poprawnej odpowiedzi
(litera może się różnić, gdy kolejność wariantów była zmieniona). Wynik: raport na ekranie + compare_keys_report.json.
Użycie: python compare_keys.py [baza.db]   (domyślnie Documents\\memonic_app.db; baza tylko do odczytu)"""
import collections, difflib, json, os, re, sqlite3, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pdf_table_dzial as dz
import pdf_table_master as ms

ROOT = HERE.parents[1]
DB = sys.argv[1] if len(sys.argv) > 1 else str(Path.home() / "Documents" / "memonic_app.db")
n = dz.n

con = sqlite3.connect(f"file:{Path(DB).as_posix()}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
rows = con.execute("select * from questions where review_status='ok' or review_status is null").fetchall()


def sim(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()


def db_text(r, letter):
    return r["odp_" + letter.lower()] or ""


def dbkey(r):
    p = n(r["pytanie"] or "")
    parts = [p]
    for k in "abcd":
        o = r["odp_" + k] or ""
        if o and n(o)[:25] not in p:
            parts.append(n(o))
    return " ".join(parts)


def pdfkey(q):
    return n(q["q"] + " " + " ".join(q["opts"].values()))


def extract_en(pdf):
    """Arkusze angielskie mają 4 kolumny: Lp | O/T | treść+warianty | litera klucza."""
    import fitz
    out, cur = [], None
    for pi, page in enumerate(fitz.open(pdf)):
        for t in page.find_tables().tables:
            for row in t.extract():
                c = [(x or "").strip() for x in (list(row) + [None] * 4)[:4]]
                num = re.fullmatch(r"(\d{1,3})\.?", c[0])
                if num:
                    q, opts = dz.parse_cell(c[2])
                    cur = {"nr": int(num.group(1)), "q": q, "opts": opts, "correct": c[3], "raw": c[2]}
                    out.append(cur)
                elif cur and not c[0] and c[2] and not c[3]:
                    cur["raw"] += "\n" + c[2]
                    cur["q"], cur["opts"] = dz.parse_cell(cur["raw"])
                elif cur and not c[0] and c[3] and not cur["correct"]:
                    cur["correct"] = c[3]
    return out


# ------------------------------------------------------------------ PDF -> pytania
pdf_q = []  # (grupa, plik, dict(q, opts, letters))
for pdf in sorted((ROOT / "sources" / "pdf_urzad" / "Master").glob("*.pdf")):
    for q in ms.extract(pdf):
        q["correct"] = sorted(set(q["correct"]))
        if len(q["opts"]) >= 2 and q["correct"]:
            pdf_q.append(("Master", pdf.name, dict(q=q["q"], opts=q["opts"], letters=q["correct"])))
for pdf in sorted((ROOT / "sources" / "pdf_urzad").rglob("*.pdf")):
    rel = str(pdf.relative_to(ROOT / "sources" / "pdf_urzad"))
    if rel.startswith("Master"):
        continue
    grp = "Angielski" if rel.startswith("Angielski") else "Pokład"
    if grp == "Angielski":
        qs = extract_en(pdf)
    else:
        qt, qx = dz.extract(pdf), dz.extract_text(pdf)
        qs = qt if len(qt) >= 0.85 * len(qx) else qx
    for q in qs:
        c = (q["correct"] or "").strip().upper()
        if q["opts"] and c in "ABCD" and c:
            pdf_q.append((grp, rel, dict(q=q["q"], opts=q["opts"], letters=[c])))
print("pytań z PDF:", collections.Counter(g for g, _, _ in pdf_q))

# ------------------------------------------------------------------ parowanie
def group_of(r):
    k = r["kategoria"] or ""
    return "Master" if k.startswith("Kapitan") else "Angielski" if k.startswith("Angiel") else "Pokład"


by_group = collections.defaultdict(list)
for r in rows:
    by_group[group_of(r)].append(r)

result = []  # dict(id, grupa, status, ...)
for grp in ("Master", "Pokład", "Angielski"):
    dbr = by_group[grp]
    dk = {r["id"]: dbkey(r) for r in dbr}
    exact = collections.defaultdict(list)
    for r in dbr:
        exact[dk[r["id"]]].append(r)
    # kolejne wiersze bazy dopasowujemy do pytań PDF (jeden PDF-owy wiersz może odpowiadać kilku wierszom bazy: kopie)
    pq = [(pdfkey(q), f, q) for g, f, q in pdf_q if g == grp]
    matched_db = {}  # id -> (score, plik, pdf q)
    for k, f, q in pq:
        cands = exact.get(k)
        if cands:
            for r in cands:
                if r["id"] not in matched_db or matched_db[r["id"]][0] < 1:
                    matched_db[r["id"]] = (1.0, f, q)
    # niedopasowane wiersze bazy: dopasowanie przybliżone do pytań PDF
    rest = [r for r in dbr if r["id"] not in matched_db and (r["zrodlo_pliku"] or "").lower().find("pdf") >= 0 or
            (r["id"] not in matched_db and grp != "Master" and (r["ai_verified"] or "").startswith(("ai_cascade", "pdf_urzad", "ok:")))]
    pq_by_len = pq
    for r in rest:
        k = dk[r["id"]]
        best, bq = 0.0, None
        for k2, f, q in pq_by_len:
            if abs(len(k) - len(k2)) > 0.4 * max(len(k), len(k2), 1):
                continue
            sm = difflib.SequenceMatcher(None, k, k2)
            if sm.real_quick_ratio() < max(best, 0.85) or sm.quick_ratio() < max(best, 0.85):
                continue
            s = sm.ratio()
            if s > best:
                best, bq = s, (f, q)
        if bq and best >= 0.85:
            matched_db[r["id"]] = (best, bq[0], bq[1])
    for r in dbr:
        m = matched_db.get(r["id"])
        if not m:
            result.append(dict(id=r["id"], grupa=grp, status="brak_w_PDF", zrodlo=r["zrodlo_pliku"], ai=r["ai_verified"]))
            continue
        score, f, q = m
        dbl = (r["poprawna_odpowiedz"] or "").strip().upper()
        pl = q["letters"]
        dbt = db_text(r, dbl) if dbl else ""
        ptexts = [q["opts"].get(L, "") for L in pl]
        same_letter = dbl in pl
        same_text = any(sim(n(dbt), n(t)) >= 0.85 for t in ptexts if t)
        if same_letter and same_text or (same_letter and score >= 0.99):
            st = "zgodne"
        elif same_text:
            st = "zgodne_inna_litera"
        else:
            st = "ROZNE"
        result.append(dict(id=r["id"], grupa=grp, status=st, score=round(score, 3), plik=f, baza=dbl, pdf=pl,
                           baza_tekst=dbt[:90], pdf_tekst=[t[:90] for t in ptexts], ai=r["ai_verified"], pytanie=(r["pytanie"] or "")[:100]))

cnt = collections.Counter((x["grupa"], x["status"]) for x in result)
for g in ("Master", "Pokład", "Angielski"):
    print(g, {s: cnt[(g, s)] for s in ("zgodne", "zgodne_inna_litera", "ROZNE", "brak_w_PDF")})
diff = [x for x in result if x["status"] == "ROZNE"]
print("RÓŻNE razem:", len(diff))
json.dump(result, open(ROOT / "review" / "Zgodnosc_z_PDF" / "compare_keys_report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
