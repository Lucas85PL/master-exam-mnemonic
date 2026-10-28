"""Ustawia karty podanych pytań jako NOWE (stan 0, bez postępu) w obu bazach (kopie przed zapisem). Dziennik odpowiedzi i flaga „Błąd” nie są ruszane.
Użycie: python reset_new_cards.py ID [ID ...]   (aplikacja musi być zamknięta)"""
import shutil, sqlite3, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IDS = [int(x) for x in sys.argv[1:]]
DBS = {"app": Path.home() / "Documents" / "memonic_app.db", "seed": ROOT / "app" / "assets" / "db" / "memonic_app_seed.db"}
if not IDS:
    sys.exit("Podaj ID pytań.")
if "memonic_app.exe" in subprocess.run(["tasklist"], capture_output=True, text=True).stdout:
    sys.exit("Aplikacja jest uruchomiona - zamknij ją i powtórz.")
ts = time.strftime("%Y%m%d_%H%M%S")
now = int(time.time() * 1000)
for label, path in DBS.items():
    shutil.copy2(path, (ROOT / "data" if label == "seed" else path.parent) / (path.name + ".bak_resetnew_" + ts))
    db = sqlite3.connect(path)
    cols = {c[1] for c in db.execute("PRAGMA table_info(srs_cards)")}
    for i in IDS:
        db.execute("UPDATE srs_cards SET repetitions=0, interval_days=0, ease_factor=2.5, due_ms=?, lapses=0, state=0, step=0, stability=NULL, "
                   "difficulty=NULL, last_review_ms=NULL WHERE question_id=?", (now, i))
        if "streak_days" in cols:
            db.execute("UPDATE srs_cards SET streak_days=0, last_good_day=NULL, hard=0 WHERE question_id=?", (i,))
    db.commit()
    n = db.execute("SELECT COUNT(*) FROM srs_cards WHERE state=0 AND question_id IN (%s)" % ",".join(map(str, IDS))).fetchone()[0]
    print(label, "nowych kart:", n, "z", len(IDS))
    db.close()
