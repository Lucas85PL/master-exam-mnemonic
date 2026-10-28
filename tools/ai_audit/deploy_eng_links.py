"""Powiązanie nowych pytań ENG z odpowiednikami PL (wyniki eng_pl_match.py i eng_translate_expl.py):
 - odpowiednik PL i ta sama odpowiedź -> przetłumaczone wyjaśnienie do explanation_cache + karta nauki „1 raz odpowiedziane dobrze” (nie nowe),
 - odpowiednik PL, ale inna odpowiedź -> pytanie zostaje NOWE, w notatce ostrzeżenie,
 - brak odpowiednika -> bez zmian (nowe).
Karta po 1 poprawnej odpowiedzi: wartości z FsrsScheduler (stan powtórka, interwał 2 dni, termin = 4:00 za 2 dni nauki). Dziennik odpowiedzi (review_log) NIE jest ruszany,
żeby nie zmieniać statystyk. Obie bazy, kopie przed zapisem; aplikacja musi być zamknięta. --dry = podgląd."""
import hashlib, json, shutil, sqlite3, subprocess, sys, time
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "review" / "Zgodnosc_z_PDF"
M = json.load(open(D / "eng_pl_matches.json", encoding="utf-8"))
E = json.load(open(D / "eng_wyjasnienia.json", encoding="utf-8")) if (D / "eng_wyjasnienia.json").exists() else {}
DBS = {"app": Path.home() / "Documents" / "memonic_app.db", "seed": ROOT / "app" / "assets" / "db" / "memonic_app_seed.db"}
DRY = "--dry" in sys.argv
if not DRY and "memonic_app.exe" in subprocess.run(["tasklist"], capture_output=True, text=True).stdout:
    sys.exit("Aplikacja jest uruchomiona - zamknij ją i powtórz.")
STAB, DIFF, INTERVAL = 2.3065, 2.118103970459015, 2  # FsrsScheduler: pierwsza ocena Good, retencja 0.9


def h(r):
    return hashlib.sha256("|".join([r[1], r[2] or "", r[3] or "", r[4] or "", r[5] or "", r[6], "v6-best-option"]).encode("utf-8")).hexdigest()


now = datetime.now()
study_day = (now - timedelta(hours=4)).date()
today = (study_day - datetime(1970, 1, 1).date()).days
due = datetime.combine(study_day + timedelta(days=INTERVAL), datetime.min.time()) + timedelta(hours=4)
due_ms, now_ms = int(due.timestamp() * 1000), int(now.timestamp() * 1000)
ts = time.strftime("%Y%m%d_%H%M%S")
for label, path in DBS.items():
    if not DRY:
        shutil.copy2(path, (ROOT / "data" if label == "seed" else path.parent) / (path.name + ".bak_englinks_" + ts))
    db = sqlite3.connect(path)
    same = diff = expl = 0
    cols = {c[1] for c in db.execute('PRAGMA table_info(srs_cards)')}
    for eid, v in M.items():
        r = db.execute("SELECT id,kategoria,review_notes FROM questions WHERE id=?", (int(eid),)).fetchone()
        if not r or r[1] != "Angielski" or not v.get("match"):
            continue
        notes = r[2] or ""
        if v.get("same_answer") is True:
            same += 1
            db.execute("UPDATE srs_cards SET repetitions=1, interval_days=?, ease_factor=2.5, due_ms=?, lapses=0, state=2, step=0, stability=?, difficulty=?, "
                       "last_review_ms=? WHERE question_id=?", (INTERVAL, due_ms, STAB, DIFF, now_ms, int(eid)))
            if "streak_days" in cols:  # starszy schemat seeda: kolumny serii dodaje migracja przy starcie aplikacji
                db.execute("UPDATE srs_cards SET streak_days=1, last_good_day=?, hard=0 WHERE question_id=?", (today, int(eid)))
            db.execute("UPDATE questions SET review_notes=? WHERE id=?", (notes + f" | odpowiednik PL ID {v['match']}: odpowiedź zgodna; oznaczone jako 1x odpowiedziane dobrze", int(eid)))
            e = E.get(eid)
            if e and e.get("expl"):
                row = db.execute("SELECT id,pytanie,odp_a,odp_b,odp_c,odp_d,poprawna_odpowiedz FROM questions WHERE id=?", (int(eid),)).fetchone()
                db.execute("DELETE FROM explanation_cache WHERE question_id=?", (int(eid),))
                db.execute("INSERT INTO explanation_cache VALUES (?,?,?,?,?)", (int(eid), h(row), e["expl"], "deepseek (tłumaczenie wyjaśnienia PL ID %s)" % v["match"], now_ms))
                expl += 1
        elif v.get("same_answer") is False:
            diff += 1
            db.execute("UPDATE questions SET review_notes=? WHERE id=?", (notes + f" | UWAGA: odpowiednik PL ID {v['match']} ma INNĄ odpowiedź niż arkusz ENG - sprawdź", int(eid)))
    print(label, "zgodne (1x dobrze):", same, "| z wyjaśnieniem:", expl, "| inna odpowiedź niż PL:", diff)
    if DRY:
        db.rollback()
    else:
        db.commit()
    db.close()
