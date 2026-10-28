"""Parowanie pytan Master z bazy z pytaniami wyciagnietymi z PDF (pdf_master_extract.json)."""
import difflib, json, re, sqlite3, unicodedata
from pathlib import Path

import os

HERE = Path(__file__).resolve().parent
DB = os.environ.get("MEM_DB", str(Path.home() / "Documents" / "memonic_app.db"))  # baza aplikacji (Windows)


def n(s):
    s = unicodedata.normalize("NFKD", s or "").lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def ratio(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()


def load():
    x = json.load(open(HERE / "pdf_master_extract.json", encoding="utf-8"))
    pdf = [dict(q, file=f, idx=i) for i, (f, v) in enumerate(x.items()) for q in v]
    for i, q in enumerate(pdf):
        q["uid"] = i
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    rows = c.execute("select * from questions where kategoria like 'Kapitan%' order by id").fetchall()
    return pdf, rows


def pair(pdf, rows):
    scores = []
    for r in rows:
        dbo = n(" ".join(r["odp_" + k] or "" for k in "abcd"))
        dbq = n(r["pytanie"])
        for q in pdf:
            po = n(" ".join(q["opts"][k] for k in sorted(q["opts"])))
            if abs(len(po) - len(dbo)) > 0.5 * max(len(po), len(dbo), 1):
                continue
            so = ratio(dbo, po)
            if so < 0.6:
                continue
            sq = ratio(dbq, n(q["q"]))
            # pytanie w bazie moze byc ogonem prawdziwego pytania
            tail = 1.0 if dbq and n(q["q"]).endswith(dbq) else 0
            scores.append((0.65 * so + 0.35 * max(sq, tail), so, sq, r["id"], q["uid"]))
    scores.sort(reverse=True)
    used_r, used_q, pairs = set(), set(), {}
    for sc, so, sq, rid, qid in scores:
        if rid in used_r:
            continue
        used_r.add(rid); used_q.add(qid)
        pairs[rid] = (qid, sc, so, sq)
    return pairs


if __name__ == "__main__":
    pdf, rows = load()
    pairs = pair(pdf, rows)
    import collections
    b = collections.Counter()
    for rid, (qid, sc, so, sq) in pairs.items():
        b["exact" if sc >= 0.98 else "fuzzy>=.85" if sc >= 0.85 else "low"] += 1
    print(len(rows), "db;", len(pdf), "pdf; sparowane", len(pairs), b)
    print("db bez pary:", [r["id"] for r in rows if r["id"] not in pairs])
    print("pdf bez pary:", len(pdf) - len({v[0] for v in pairs.values()}))
    json.dump({str(k): v for k, v in pairs.items()}, open(HERE / "pairs.json", "w"))
