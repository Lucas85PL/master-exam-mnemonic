"""Wdrozenie pytan HIGH z weryfikacji skanow egzaminow (review/Weryfikacja_2026-10-12) do bazy aplikacji i seeda.
Zachowuje oryginalna kolejnosc wariantow, klucz = zweryfikowana odpowiedz, kategoria Master. Kopie obu baz przed zmiana + log.
  python deploy_exam_high.py            # podglad
  python deploy_exam_high.py --apply    # zapis (zamknij aplikacje)"""
import json
import re
import shutil
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "review" / "Weryfikacja_2026-10-12"
DBS = {"app": Path.home() / "Documents" / "memonic_app.db", "seed": ROOT / "app" / "assets" / "db" / "memonic_app_seed.db"}
KAT = "Kapitan żeglugi wielkiej"
STAMP = "2026-10-12"
APPLY = "--apply" in sys.argv

r1 = {x["id"]: x for x in json.loads((OUT / "wyniki.json").read_text(encoding="utf-8"))}
r2 = {x["id"]: x for x in json.loads((OUT / "wyniki_runda2.json").read_text(encoding="utf-8"))}
base = {x["id"]: x for x in json.loads((ROOT / "review" / "Egzaminy_lokalna_baza.json").read_text(encoding="utf-8"))}

sel = []
for qid, x in r1.items():
    st = r2[qid]["status_runda2"] if qid in r2 else x["status"]
    if st == "HIGH":
        sel.append((qid, "runda1_haiku" if qid not in r2 else "runda2_sonnet_sol", x))
print("HIGH:", len(sel))


def norm(s):
    return re.sub(r"[\W_]+", " ", (s or "").lower()).strip()


def key_of(q, opts):
    return "|".join(norm(v) for v in [q] + opts)


items = []
for qid, via, x in sel:
    b = base[qid]
    opts = [x["opcje"].get(k) for k in "ABCD"]
    letter = x["odpowiedz_wstepna"]
    assert letter in "ABCD" and x["opcje"].get(letter), qid
    assert sum(1 for o in opts if o) >= 2, qid
    items.append({"id": qid, "via": via, "tem": x["przedmiot"], "q": x["pytanie"], "opts": opts, "key": letter,
                  "src": b.get("zrodlo") or "", "podstawa": (x.get("podstawa_wstepna") or "")[:200], "partia": b["partia"]})

# bezpieczenstwo: brak dokladnych duplikatow w obrebie wdrazanych i wzgledem bazy
seen = {}
for it in items:
    k = key_of(it["q"], [o or "" for o in it["opts"]])
    assert k not in seen, ("duplikat w obrebie partii", it["id"], seen[k])
    seen[k] = it["id"]
con = sqlite3.connect(f"file:{DBS['app'].as_posix()}?mode=ro", uri=True)
exist = {key_of(q, [a or "", b or "", c or "", d or ""]) for q, a, b, c, d in
         con.execute("SELECT pytanie,odp_a,odp_b,odp_c,odp_d FROM questions")}
con.close()
clash = [it["id"] for it in items if key_of(it["q"], [o or "" for o in it["opts"]]) in exist]
print("dokladne duplikaty wzgledem bazy:", clash)
items = [it for it in items if it["id"] not in clash]
print("do zapisu:", len(items), "rozklad kluczy:", dict(sorted(Counter(i["key"] for i in items).items())),
      "przedmioty:", dict(Counter(i["tem"] for i in items)))
if not APPLY:
    sys.exit(0)

log = {"stamp": STAMP, "items": []}
first = None
for label, path in DBS.items():
    bak = (ROOT / "data" if label == "seed" else path.parent) / (path.name + f".bak_exam_high_{time.strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(path, bak)
    db = sqlite3.connect(path, timeout=30)
    start = db.execute("SELECT MAX(id) FROM questions").fetchone()[0] + 1
    first = start if first is None else first
    assert start == first, "rozjazd numeracji ID miedzy baza aplikacji a seedem"
    now = int(time.time() * 1000)
    for k, it in enumerate(items):
        qid = start + k
        a, b, c, d = it["opts"]
        db.execute(
            "INSERT INTO questions (id, kategoria, podkategoria, poziom, tematyka, nr_pytania, typ_pytania, pytanie, odp_a, odp_b, odp_c, odp_d,"
            " poprawna_odpowiedz, poprawna_odpowiedz_tekst, zrodlo_pliku, review_status, review_notes, study_hidden, ai_verified, image_path)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (qid, KAT, None, None, it["tem"], None, "testowe", it["q"], a, b, c, d, it["key"], dict(zip("ABCD", it["opts"]))[it["key"]],
             f"skan egzaminu ({it['partia']}) {it['src']}", "ok", f"exam_scan:{it['podstawa']}", 0,
             f"exam_scan:ai_high_{it['via']}:{STAMP}", None))
        db.execute("INSERT INTO srs_cards (question_id, repetitions, interval_days, ease_factor, due_ms, lapses, state, step)"
                   " VALUES (?,?,?,?,?,?,?,?)", (qid, 0, 0, 2.5, now, 0, 0, 0))
        if label == "app":
            log["items"].append({"db_id": qid, "scan_id": it["id"], "klucz": it["key"], "via": it["via"]})
    db.commit()
    n = db.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
    db.close()
    print(label, "dodano", len(items), "ID od", start, "razem pytan", n, bak.name)
(OUT / "wdrozenie_log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
print("log: wdrozenie_log.json")
