"""Zapisuje potwierdzone przez roj modeli powiazania powtorzonych pytan (runs/dups_<tag>.json) do tabeli dup_links w bazie.
Aplikacja (od 2.7) przy starcie laczy takie pytania w jedna grupe: wspolny harmonogram nauki i statystyki liczone raz.
Nic nie jest usuwane; usuniecie wiersza z dup_links cofa powiazanie.

  python apply_dup_links.py <baza.db> <runs/dups_run1.json> [--apply]     # bez --apply tylko podglad (na kopii bazy)
Przed zapisem robi kopie <baza>.bak_duplinks_*. Zamknij aplikacje przed zapisem do bazy uzytkownika."""
import json
import shutil
import sqlite3
import sys
import time
from pathlib import Path

db_path, js = Path(sys.argv[1]), Path(sys.argv[2])
apply = "--apply" in sys.argv
data = json.loads(js.read_text(encoding="utf-8"))
links = [(i, g["canonical_id"]) for g in data["groups"] for i in g["ids"] if i != g["canonical_id"]]
print(f"powiazan do zapisu: {len(links)} (grup: {len(data['groups'])}); model: {data['model']}")
if not apply:
    sys.exit(0)
bak = db_path.with_name(db_path.name + f".bak_duplinks_{time.strftime('%Y%m%d_%H%M%S')}")
shutil.copy2(db_path, bak)
c = sqlite3.connect(db_path, timeout=30)
c.execute("""CREATE TABLE IF NOT EXISTS dup_links (question_id INTEGER PRIMARY KEY, canonical_id INTEGER NOT NULL, source TEXT)""")
existing = {r[0] for r in c.execute("SELECT id FROM questions")}
rows = [(a, b, f"swarm:{data['model']}:{js.stem}") for a, b in links if a in existing and b in existing]
c.executemany("INSERT OR REPLACE INTO dup_links (question_id, canonical_id, source) VALUES (?,?,?)", rows)
c.commit()
print(f"zapisano {len(rows)} powiazan; kopia: {bak.name}")
c.close()
