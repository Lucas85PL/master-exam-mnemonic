"""Przygotowanie do dodania: pytania z arkuszy PDF (Angielski, wybrane Pokład/Master), których nie ma w bazie — z PEŁNĄ treścią i kluczem z PDF.
Pytanie uznajemy za obecne w bazie, gdy zgadza się treść pytania + warianty (>=0.8) albo sama treść pytania (>=0.85).
Wynik: review/Zgodnosc_z_PDF/do_dodania_pelne.json (baza tylko do odczytu). Użycie: python stage_missing.py [baza.db]"""
import collections, difflib, json, re, sqlite3, sys
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
rows = con.execute("select * from questions").fetchall()


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
    import fitz
    out, cur = [], None
    for page in fitz.open(pdf):
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


SRC = ROOT / "sources" / "pdf_urzad"
pdf_q = []
for pdf in sorted((SRC / "Master").glob("*.pdf")):
    for q in ms.extract(pdf):
        pdf_q.append(("Master", str(pdf.relative_to(SRC)), q))
for pdf in sorted(SRC.rglob("*.pdf")):
    rel = str(pdf.relative_to(SRC))
    if rel.startswith("Master"):
        continue
    if rel.startswith("Angielski"):
        qs, grp = extract_en(pdf), "Angielski"
    else:
        qt, qx = dz.extract(pdf), dz.extract_text(pdf)
        qs, grp = (qt if len(qt) >= 0.85 * len(qx) else qx), "Pokład"
    for q in qs:
        pdf_q.append((grp, rel, q))

db_keys = [dbkey(r) for r in rows]
db_stems = [n(r["pytanie"]) for r in rows]
exact = set(db_keys)
out = []
for grp, f, q in pdf_q:
    corr = q.get("correct")
    letter = (corr[0] if isinstance(corr, list) and corr else corr or "").strip().upper()[:1]
    if len(q["opts"]) < 2 or len(n(q["q"])) < 8 or letter not in "ABCD" or letter not in q["opts"]:
        continue  # uszkodzona ekstrakcja / brak klucza - nie do automatycznego dodania
    k, s = pdfkey(q), n(q["q"])
    if k in exact:
        continue
    best = 0.0
    for k2 in db_keys:
        if abs(len(k) - len(k2)) > 0.4 * max(len(k), len(k2), 1):
            continue
        sm = difflib.SequenceMatcher(None, k, k2)
        if sm.real_quick_ratio() < max(best, 0.8) or sm.quick_ratio() < max(best, 0.8):
            continue
        best = max(best, sm.ratio())
        if best >= 0.9:
            break
    if best >= 0.8:
        continue
    stem_best = 0.0
    for t in db_stems:
        if abs(len(t) - len(s)) > 0.5 * max(len(t), len(s), 1):
            continue
        stem_best = max(stem_best, difflib.SequenceMatcher(None, s, t).ratio())
        if stem_best >= 0.85:
            break
    if stem_best >= 0.85:
        continue
    out.append(dict(grupa=grp, plik=f, nr=q.get("nr"), q=q["q"].strip(), opts={L: t.strip() for L, t in q["opts"].items()},
                    key=letter, page=q.get("page"), sim=round(best, 2)))
print("do dodania:", len(out), dict(collections.Counter(o["grupa"] for o in out)))
json.dump(out, open(ROOT / "review" / "Zgodnosc_z_PDF" / "do_dodania_pelne.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
