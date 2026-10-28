"""Zapis tabeli cmke_diff (pytania z odpowiedzią inną niż w arkuszach CMKE) do obu baz.
Dane: review/Zgodnosc_z_PDF/cmke_diffs.json (tools/pdf_extraction/export_key_diffs.py). Tabela jest w całości zastępowana.
Uruchom przy zamkniętej aplikacji; kopie obu baz przed zapisem. --dry = tylko podgląd."""
import json, shutil, sqlite3, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = json.load(open(ROOT / "review" / "Zgodnosc_z_PDF" / "cmke_diffs.json", encoding="utf-8"))
DBS = {"app": Path.home() / "Documents" / "memonic_app.db", "seed": ROOT / "app" / "assets" / "db" / "memonic_app_seed.db"}
DRY = "--dry" in sys.argv
if not DRY and "memonic_app.exe" in subprocess.run(["tasklist"], capture_output=True, text=True).stdout:
    sys.exit("Aplikacja jest uruchomiona - zamknij ją i powtórz.")
ts = time.strftime("%Y%m%d_%H%M%S")
for label, path in DBS.items():
    if not DRY:
        shutil.copy2(path, (ROOT / "data" if label == "seed" else path.parent) / (path.name + ".bak_cmke_" + ts))
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE IF NOT EXISTS cmke_diff (question_id INTEGER PRIMARY KEY, cmke_letter TEXT NOT NULL)")
    db.execute("DELETE FROM cmke_diff")
    n = 0
    for qid, letter in DATA.items():
        r = db.execute("SELECT poprawna_odpowiedz FROM questions WHERE id=?", (int(qid),)).fetchone()
        if r is None or letter not in "ABCD" or letter == r[0]:
            print("  pominięto", qid, letter, r)
            continue
        db.execute("INSERT INTO cmke_diff VALUES (?,?)", (int(qid), letter)); n += 1
    print(label, "wpisów:", n)
    if DRY: db.rollback()
    else: db.commit()
    db.close()
