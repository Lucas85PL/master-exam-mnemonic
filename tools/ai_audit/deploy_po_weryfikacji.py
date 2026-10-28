r"""Wdrożenie pytań 'Po weryfikacji' (Desktop\Po weryfikacji): klucze z Excela, nowe pytania z Worda, wyjaśnienia AI do explanation_cache,
zdjęcie pomarańczowego oznaczenia (ai_disputed). Dane: review/Wyjasnij_AI/po_weryfikacji_final.json. --apply = zapis (aplikacja musi być zamknięta).
Opcjonalnie: --db <app.db> <seed.db> (do próby na kopiach), --data <plik.json> (inny zestaw; pole "mark" = znacznik ai_verified)."""
import hashlib, json, shutil, sqlite3, subprocess, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = Path(sys.argv[sys.argv.index("--data") + 1]) if "--data" in sys.argv else ROOT / "review" / "Wyjasnij_AI" / "po_weryfikacji_final.json"
DATA = json.load(open(DATA_PATH, encoding="utf-8"))
DBS = {"app": Path.home() / "Documents" / "memonic_app.db", "seed": ROOT / "app" / "assets" / "db" / "memonic_app_seed.db"}
if "--db" in sys.argv:
    i = sys.argv.index("--db"); DBS = {"app": Path(sys.argv[i + 1]), "seed": Path(sys.argv[i + 2])}
APPLY = "--apply" in sys.argv
MARK = DATA.get("mark", "manual:po_weryfikacji_user_verified:2026-10-14")
if APPLY and "--db" not in sys.argv and "memonic_app.exe" in subprocess.run(["tasklist"], capture_output=True, text=True).stdout:
    sys.exit("Aplikacja jest uruchomiona - zamknij ją i powtórz.")
def h(r):
    return hashlib.sha256("|".join([r[1], r[2] or "", r[3] or "", r[4] or "", r[5] or "", r[6], "v6-best-option"]).encode("utf-8")).hexdigest()
log = {}
for label, path in DBS.items():
    if APPLY and "--db" not in sys.argv:
        shutil.copy2(path, str(path) + f".bak_po_weryfikacji_{time.strftime('%Y%m%d_%H%M%S')}")
    db = sqlite3.connect(path, timeout=30)
    now = int(time.time() * 1000)
    ch = unch = cache = 0
    ids_ok = []
    for u in DATA["updates"]:
        for i in u["ids"]:
            r = db.execute("SELECT odp_a,odp_b,odp_c,odp_d,poprawna_odpowiedz FROM questions WHERE id=?", (i,)).fetchone()
            if not r: continue
            ids_ok.append(i)
            txt = r["ABCD".index(u["key"])]
            assert txt, (i, u["key"])
            if r[4] != u["key"]:
                db.execute("UPDATE questions SET poprawna_odpowiedz=?, poprawna_odpowiedz_tekst=?, ai_verified=? WHERE id=?", (u["key"], txt, MARK, i)); ch += 1
            else: unch += 1
            row = db.execute("SELECT id,pytanie,odp_a,odp_b,odp_c,odp_d,poprawna_odpowiedz FROM questions WHERE id=?", (i,)).fetchone()
            db.execute("DELETE FROM explanation_cache WHERE question_id=?", (i,))
            db.execute("INSERT INTO explanation_cache VALUES (?,?,?,?,?)", (i, h(row), u["explanation"], "claude-haiku-5-5 (klucz zweryfikowany ręcznie)", now)); cache += 1
    db.execute("CREATE TABLE IF NOT EXISTS ai_disputed (question_id INTEGER PRIMARY KEY)")
    db.executemany("DELETE FROM ai_disputed WHERE question_id=?", [(i,) for i in ids_ok])
    start = db.execute("SELECT MAX(id) FROM questions").fetchone()[0] + 1
    for k, w in enumerate(DATA["new"]):
        qid = start + k; o = [w["opts"].get(L) for L in "ABCD"]
        db.execute("INSERT INTO questions (id,kategoria,podkategoria,poziom,tematyka,nr_pytania,typ_pytania,pytanie,odp_a,odp_b,odp_c,odp_d,poprawna_odpowiedz,poprawna_odpowiedz_tekst,zrodlo_pliku,review_status,review_notes,study_hidden,ai_verified,image_path) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (qid, "Kapitan żeglugi wielkiej", None, None, "Egzamin kapitański", None, "testowe", w["q"], *o, w["key"], w["opts"][w["key"]],
             f"skany egzaminów, weryfikacja ręczna ({w['tag']})", "ok", "exam_scan: klucz zweryfikowany przez użytkownika", 0, MARK, None))
        db.execute("INSERT INTO srs_cards (question_id,repetitions,interval_days,ease_factor,due_ms,lapses,state,step) VALUES (?,?,?,?,?,?,?,?)", (qid, 0, 0, 2.5, now, 0, 0, 0))
        row = db.execute("SELECT id,pytanie,odp_a,odp_b,odp_c,odp_d,poprawna_odpowiedz FROM questions WHERE id=?", (qid,)).fetchone()
        db.execute("INSERT INTO explanation_cache VALUES (?,?,?,?,?)", (qid, h(row), w["explanation"], "claude-haiku-5-5 (klucz zweryfikowany ręcznie)", now)); cache += 1
        log.setdefault(label, []).append(qid)
    res = dict(klucz_zmieniony=ch, klucz_bez_zmian=unch, wyjasnienia=cache, nowe=len(DATA["new"]), ID_od=start, ai_disputed_zostalo=db.execute("SELECT COUNT(*) FROM ai_disputed").fetchone()[0], razem=db.execute("SELECT COUNT(*) FROM questions").fetchone()[0])
    print(label, res)
    if APPLY: db.commit()
    else: db.rollback()
    db.close()
