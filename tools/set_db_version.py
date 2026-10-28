"""Ustawia wersje zawartosci bazy pytan (tabela db_info, klucz db_version), np. 3.0. Kopia przed zapisem. Aplikacja musi byc zamknieta.
Uzycie: python set_db_version.py 3.0 <baza.db> [<baza2.db> ...]"""
import shutil, sqlite3, sys, time
from pathlib import Path

version, paths = sys.argv[1], [Path(p) for p in sys.argv[2:]]
for p in paths:
    ts = time.strftime("%Y%m%d_%H%M%S")
    bak_dir = p.parent if "assets" not in p.parts else Path(__file__).resolve().parents[1] / "data" / "backup_seed"
    bak_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, bak_dir / f"{p.name}.bak_dbversion_{ts}")
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE IF NOT EXISTS db_info (key TEXT PRIMARY KEY, value TEXT)")
    c.execute("INSERT OR REPLACE INTO db_info(key, value) VALUES ('db_version', ?)", (version,))
    c.commit()
    print(p, "-> db_version", c.execute("SELECT value FROM db_info WHERE key='db_version'").fetchone()[0],
          "| pytan:", c.execute("SELECT COUNT(*) FROM questions").fetchone()[0])
    c.close()
