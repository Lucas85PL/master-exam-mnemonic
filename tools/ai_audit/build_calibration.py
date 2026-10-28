"""Zestaw kalibracyjny 30 pytan: 15 czystych + 15 z wstrzyknieta usterka. Nie modyfikuje bazy aplikacji."""
import json, os, random, re, sqlite3
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = os.environ.get("MEM_DB", str(Path.home() / "Documents" / "memonic_app.db"))
import os
SEED = int(os.environ.get('CAL_SEED', 11))
OUT = os.environ.get('CAL_OUT', 'calibration_set.json')

c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
rows = c.execute("select * from questions where kategoria not like 'Kapitan%' and ai_verified is null or "
                 "(kategoria not like 'Kapitan%' and ai_verified like 'pdf_urzad%')").fetchall()
BAD = re.compile(r"rysun|fotograf|zdjęci|ilustrac|schemat|poniższ|flag|figure|picture|\d{3,}", re.I)

def usable(r):
    q = (r["pytanie"] or "").strip()
    opts = [r["odp_" + k] for k in "abcd" if r["odp_" + k]]
    return (len(q) >= 45 and len(q.split()) >= 7 and len(opts) >= 3 and not BAD.search(q)
            and all(len(o.strip()) >= 4 for o in opts) and "\n" not in q
            and r["poprawna_odpowiedz"] in "ABCD" and r["review_status"] == "ok"
            and (q[0].isupper() or q[0].isdigit()) and q.rstrip()[-1] in "?:.…")

_seen = set(); pool = []
for r in rows:
    if usable(r):
        k = re.sub(r'\W+', '', r['pytanie'].lower())
        if k not in _seen: _seen.add(k); pool.append(r)
rnd = random.Random(SEED)
pk = [r for r in pool if r["kategoria"].startswith("Dzia")]; en = [r for r in pool if r["kategoria"].startswith("Angiel")]
rnd.shuffle(pk); rnd.shuffle(en)
picks = pk[:23] + en[:7]            # 30 roznych pytan (ok. 23% angielski)
rnd.shuffle(picks)

def base(r):
    return {"source_id": r["id"], "kategoria": r["kategoria"], "tematyka": r["tematyka"],
            "pytanie": r["pytanie"].strip(), "opts": {k.upper(): r["odp_" + k] for k in "abcd" if r["odp_" + k]},
            "key": r["poprawna_odpowiedz"]}

def other_letter(d):
    return rnd.choice([k for k in d["opts"] if k != d["key"]])

# plan usterek: (typ, ilosc, oczekiwana warstwa wykrycia)
PLAN = [("truncated_start", 3), ("truncated_end", 2), ("key_option_blank", 2), ("only_one_option", 1),
        ("key_swapped", 3), ("garbled", 2), ("duplicate_options", 1), ("stem_mismatch", 1)]

def inject(d, typ, donor):
    q = d["pytanie"]; w = q.split()
    if typ == "truncated_start":
        d["pytanie"] = " ".join(w[len(w) // 2 + 1:])           # zostaje tylko druga polowa
    elif typ == "truncated_end":
        d["pytanie"] = " ".join(w[: max(3, len(w) // 2)])      # urwane w pol zdania, bez ?/:
    elif typ == "key_option_blank":
        d["opts"][d["key"]] = ""
    elif typ == "only_one_option":
        d["opts"] = {k: (v if k == d["key"] else "") for k, v in d["opts"].items()}
    elif typ == "key_swapped":
        d["key"] = other_letter(d)
    elif typ == "garbled":
        i = rnd.randrange(len(w)); w[i] = "".join(rnd.choice("xqzjw#~") for _ in range(len(w[i])))
        j = rnd.randrange(len(w)); w[j] = "§" + w[j][:2] + "¤"
        d["pytanie"] = " ".join(w)
    elif typ == "duplicate_options":
        a, b = [k for k in d["opts"] if k != d["key"]][:2]; d["opts"][b] = d["opts"][a]
    elif typ == "stem_mismatch":
        d["pytanie"] = donor["pytanie"].strip()
    return d

items, defect_slots = [], []
for typ, n in PLAN: defect_slots += [typ] * n
rnd.shuffle(defect_slots)
clean, dirty = picks[:15], picks[15:]
for i, r in enumerate(clean):
    d = base(r); d["label"] = {"defect": None}; items.append(d)
for r, typ in zip(dirty, defect_slots):
    d = base(r); donor = base(clean[0] if typ != "stem_mismatch" else next(x for x in pool if x["kategoria"] != r["kategoria"] or x["tematyka"] != r["tematyka"]))
    d = inject(d, typ, donor)
    d["label"] = {"defect": typ,
                  "klasa": "key" if typ in ("key_swapped", "stem_mismatch") else "integrity"}
    items.append(d)
rnd.shuffle(items)
for n_, d in enumerate(items, 1): d["cid"] = f"C{n_:02d}"
json.dump(items, open(HERE / OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
import collections
print("pytan:", len(items), collections.Counter(d["label"]["defect"] or "clean" for d in items))
for d in items[:30]:
    print(d["cid"], (d["label"]["defect"] or "clean").ljust(17), d["kategoria"][:5], "|", d["pytanie"][:70], "|", {k: v[:14] for k, v in d["opts"].items()}, d["key"])
