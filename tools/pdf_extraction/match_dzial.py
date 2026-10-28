"""Dopasowanie pytan z PDF (dzial_extract.json) do bazy aplikacji - cala pula kategorii, z licznoscia."""
import json, sqlite3, difflib, collections, re
from pdf_table_dzial import n, DB, HERE

ext = json.load(open(HERE / "dzial_extract.json", encoding="utf-8"))
c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
rows = c.execute("select * from questions where kategoria not like 'Kapitan%'").fetchall()
def dkey(r):
    p = n(r["pytanie"] or ""); parts = [p]
    for k in "abcd":
        o = r["odp_" + k] or ""
        if o and n(o)[:25] not in p:      # warianty wpisane w tresc pytania - nie dubluj
            parts.append(n(o))
    return " ".join(parts)
def qkey(q): return n(q["q"] + " " + " ".join(q["opts"].values()))
def level_of(r): return "operacyjny" if (r["poziom"] or "").startswith("oper") else "zarz"
dk = {r["id"]: dkey(r) for r in rows}
bylevel = collections.defaultdict(list)
for r in rows:
    if not r["kategoria"].startswith("Angiel"): bylevel[level_of(r)].append(r)

def best_match(q, taken, level):
    k = qkey(q); best, br = 0, None
    for r in bylevel[level]:
        if r["id"] in taken: continue
        k2 = dk[r["id"]]
        if k == k2: return 1.0, r
        if abs(len(k) - len(k2)) > 0.5 * max(len(k), len(k2), 1): continue
        sm = difflib.SequenceMatcher(None, k, k2)
        if sm.real_quick_ratio() < best or sm.quick_ratio() < best: continue
        s = sm.ratio()
        if s > best: best, br = s, r
    return best, br

def run(th=0.75):
    taken, found, missing, mism = set(), [], [], []
    for rel, d in ext.items():
        level = "operacyjny" if "operacyjny" in d["old"] else "zarz"
        for q in d["q"]:
            s, r = best_match(q, taken, level)
            if r is not None and s >= th:
                taken.add(r["id"]); found.append((rel, q, r, s))
                if q["correct"] and q["correct"].strip().upper() != (r["poprawna_odpowiedz"] or ""):
                    mism.append((r["id"], rel, q["nr"], r["poprawna_odpowiedz"], q["correct"]))
            else:
                missing.append((rel, q, round(s, 2), r["id"] if r else None))
    return found, missing, mism

if __name__ == "__main__":
    found, missing, mism = run()
    tot = sum(len(d["q"]) for d in ext.values())
    print("PDF:", tot, "znalezione w bazie:", len(found), "brakuje:", len(missing), "litera inna:", len(mism))
    by = collections.Counter(m[0] for m in missing)
    for k, v in sorted(by.items()): print(f"  {v:3}  {k[-70:]}")
    json.dump({"missing": [(a, b, s, i) for a, b, s, i in missing], "mism": mism}, open(HERE / "dzial_match.json", "w", encoding="utf-8"), ensure_ascii=False)
