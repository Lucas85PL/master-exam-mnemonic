"""Odwrotne porównanie: pytania z arkuszy PDF (Master, Pokład, Angielski), których NIE MA w bazie (po treści pytania + wariantów).
Wynik: lista na ekranie + review/Zgodnosc_z_PDF/brakujace_w_bazie.json. Baza tylko do odczytu.
Użycie: python missing_from_db.py [baza.db]"""
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
rows = con.execute("select * from questions").fetchall()  # także nieaktywne: pytanie "usunięte" nie jest brakiem


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
pdf_q = []  # (grupa, plik, nr, q)
for pdf in sorted((SRC / "Master").glob("*.pdf")):
    for q in ms.extract(pdf):
        pdf_q.append(("Master", pdf.name, q.get("nr"), q))
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
        pdf_q.append((grp, rel, q.get("nr"), q))
print("pytań wyodrębnionych z PDF:", collections.Counter(g for g, *_ in pdf_q))

db_keys = [dbkey(r) for r in rows]
exact = set(db_keys)
missing, weak = [], []
for grp, f, nr, q in pdf_q:
    k = pdfkey(q)
    if len(q["opts"]) < 2 or len(n(q["q"])) < 8:
        weak.append(dict(grupa=grp, plik=f, nr=nr, q=q["q"][:100], opts=len(q["opts"])))  # uszkodzona ekstrakcja (nie da się porównać)
        continue
    if k in exact:
        continue
    best = 0.0
    for k2 in db_keys:
        if abs(len(k) - len(k2)) > 0.4 * max(len(k), len(k2), 1):
            continue
        sm = difflib.SequenceMatcher(None, k, k2)
        if sm.real_quick_ratio() < max(best, 0.8) or sm.quick_ratio() < max(best, 0.8):
            continue
        s = sm.ratio()
        if s > best:
            best = s
            if best >= 0.9:
                break
    if best < 0.8:
        missing.append(dict(grupa=grp, plik=f, nr=nr, q=q["q"][:200], opts={L: t[:100] for L, t in q["opts"].items()},
                            correct=q.get("correct"), best=round(best, 2)))
print("BRAKUJE w bazie:", len(missing), collections.Counter(m["grupa"] for m in missing))
print("uszkodzona ekstrakcja (nie do porównania):", len(weak), collections.Counter(w["grupa"] for w in weak))
json.dump(dict(missing=missing, weak=weak), open(ROOT / "review" / "Zgodnosc_z_PDF" / "brakujace_w_bazie.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
for m in missing[:60]:
    print(f"- [{m['grupa']}] {Path(m['plik']).name} nr {m['nr']} (podobieństwo {m['best']}): {m['q'][:110]}")
