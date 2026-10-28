"""Aktualizacja bazy Master wg oficjalnych PDF (pdf_master_extract.json).

1) poprawia litere/tresc istniejacych pytan (tylko pewne pary),
2) dodaje brakujace pytania (review_status='ai_pending' - nie sa w nauce do czasu testu AI).
Dziennik zmian (stare wartosci) -> pdf_apply_log.json
"""
import json, os, re, shutil, sqlite3, time
from pair_master import load, pair, n

TARGETS = ["C:/Users/Lukasz/Documents/memonic_app.db",
           "../memonic_app/assets/db/memonic_app_seed.db"]
pdf, rows = load()
pairs = pair(pdf, rows)
P = {q["uid"]: q for q in pdf}
import collections
share = collections.Counter(v[0] for v in pairs.values())
R = {r["id"]: r for r in rows}

def clean(q): return len(q["correct"]) == 1 and len(q["opts"]) >= 3 and q["correct"][0] in q["opts"]

updates, letter_fix = {}, {}
for rid, (qid, sc, so, sq) in pairs.items():
    q, r = P[qid], R[rid]
    if not clean(q) or share[qid] > 1 or sc < 0.85: continue
    tail = n(q["q"]).endswith(n(r["pytanie"])) and n(q["q"]) != n(r["pytanie"])
    textdiff = sc < 0.98
    if textdiff and (tail or (sq >= 0.9 and so >= 0.85)):
        updates[rid] = q
    elif q["correct"][0] != r["poprawna_odpowiedz"]:
        letter_fix[rid] = q

covered = {v[0] for v in pairs.values()}
seen, new = set(), []
for q in pdf:
    if q["uid"] in covered or not clean(q): continue
    k = n(q["q"] + " " + " ".join(q["opts"][a] for a in sorted(q["opts"])))
    if k in seen: continue
    seen.add(k); new.append(q)

print("update tresci:", len(updates), "poprawa litery:", len(letter_fix), "nowe:", len(new))
if os.environ.get("DRY"): raise SystemExit

kat = rows[0]["kategoria"]
def tematyka(f):
    return re.sub(r"^.*?-\d\d-\d\d-", "", f).rsplit("-", 1)[0]

log = {"updated": {}, "letter_fix": {}, "new": []}
ts = time.strftime("%Y%m%d_%H%M%S")
for t in TARGETS:
    shutil.copy(t, t + f".bak_pdf_{ts}")
    c = sqlite3.connect(t)
    nid = 100001
    for rid, q in {**updates, **letter_fix}.items():
        old = c.execute("select pytanie,odp_a,odp_b,odp_c,odp_d,poprawna_odpowiedz,poprawna_odpowiedz_tekst from questions where id=?", (rid,)).fetchone()
        if old is None: continue
        L = q["correct"][0]; o = q["opts"]
        c.execute("""update questions set pytanie=?,odp_a=?,odp_b=?,odp_c=?,odp_d=?,
            poprawna_odpowiedz=?,poprawna_odpowiedz_tekst=?,ai_verified=NULL where id=?""",
            (q["q"], o.get("A"), o.get("B"), o.get("C"), o.get("D"), L, o[L], rid))
        log["updated" if rid in updates else "letter_fix"].setdefault(str(rid), list(old))
    for q in new:
        o = q["opts"]; L = q["correct"][0]
        c.execute("""insert into questions (id,kategoria,tematyka,nr_pytania,typ_pytania,pytanie,odp_a,odp_b,odp_c,odp_d,
            poprawna_odpowiedz,poprawna_odpowiedz_tekst,zrodlo_pliku,review_status,review_notes,study_hidden)
            values (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)""",
            (nid, kat, tematyka(q["file"]), q["nr"], "testowe", q["q"], o.get("A"), o.get("B"), o.get("C"), o.get("D"),
             L, o[L], q["file"], "ai_pending", f"pdf_urzad:{q['file']} s.{q['page']}"))
        c.execute("insert into srs_cards (question_id,repetitions,interval_days,ease_factor,due_ms,lapses) values (?,0,0,2.5,?,0)",
                  (nid, int(time.time() * 1000)))
        if t == TARGETS[0]: log["new"].append(nid)
        nid += 1
    c.commit(); c.close()
json.dump(log, open("pdf_apply_log.json", "w"), ensure_ascii=False)
open("round3_ids.txt", "w").write("\n".join(map(str, [*updates, *letter_fix, *log["new"]])))
print("zapisano; ids do testu:", len(updates) + len(letter_fix) + len(log["new"]))
