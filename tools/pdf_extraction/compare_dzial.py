import json, os, re, sqlite3, difflib, collections, unicodedata
from pathlib import Path
from pdf_table_dzial import n, DB, HERE
ext = json.load(open(HERE / "dzial_extract.json", encoding="utf-8"))
c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
rows = c.execute("select * from questions where kategoria not like 'Kapitan%' and kategoria not like 'Angiel%'").fetchall()
def base(z): return os.path.basename(z.replace("\\", "/")).strip()
def lvl(p): return "operacyjny" if "operacyjny" in p else "zarz"
dbg = collections.defaultdict(list)
for r in rows: dbg[(("operacyjny" if (r["poziom"] or "").startswith("oper") else "zarz"), base(r["zrodlo_pliku"]))].append(r)
def dbkey(r): return n((r["pytanie"] or "") + " " + " ".join(r["odp_" + k] or "" for k in "abcd"))
def pdfkey(q): return n(q["q"] + " " + " ".join(q["opts"].values()))
report, missing, mism = [], [], []
tot = collections.Counter()
for rel, d in ext.items():
    old = d["old"]; key = (lvl(old), base(old))
    dbrows = list(dbg.get(key, []))
    pk = [(pdfkey(q), q) for q in d["q"]]
    dk = [(dbkey(r), r) for r in dbrows]
    used = set(); unmatched = []
    for k, q in pk:
        best, bi = 0, None
        for i, (k2, r) in enumerate(dk):
            if i in used: continue
            if k == k2: best, bi = 1.0, i; break
            if abs(len(k) - len(k2)) > 0.4 * max(len(k), len(k2), 1): continue
            s = difflib.SequenceMatcher(None, k, k2).ratio()
            if s > best: best, bi = s, i
        if bi is not None and best >= 0.82:
            used.add(bi)
            r = dk[bi][1]
            if q["correct"] and r["poprawna_odpowiedz"] and q["correct"].strip().upper() != r["poprawna_odpowiedz"]:
                mism.append((r["id"], rel, q["nr"], r["poprawna_odpowiedz"], q["correct"]))
        else:
            unmatched.append(q); missing.append((rel, old, q))
    extra = len(dk) - len(used)
    report.append((rel, len(pk), len(dk), len(unmatched), extra))
    tot["pdf"] += len(pk); tot["db"] += len(dk); tot["missing"] += len(unmatched); tot["db_extra"] += extra
for r in report: print(f"{r[0][-60:]:60} pdf={r[1]:3} db={r[2]:3} brak_w_bazie={r[3]:3} nadmiar_w_bazie={r[4]:3}")
print(tot, "niezgodne litery:", len(mism))
json.dump({"missing": [(a, b, q) for a, b, q in missing], "mism": mism}, open(HERE / "dzial_compare.json", "w", encoding="utf-8"), ensure_ascii=False)
