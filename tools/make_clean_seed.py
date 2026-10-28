"""Tworzy 'czysta' baze startowa dla wersji przenosnej PC: tresc pytan i znaczniki 'Blad' (study_hidden) z biezacej bazy uzytkownika,
ale BEZ postepu nauki (karty SRS jako nowe, pusty dziennik odpowiedzi). Gotowe wyjasnienia AI (explanation_cache) ZOSTAJA - to tresc,
ktora dziala w 'Wyjasnij' bez klucza API. Oznaczenia 'Niepewne' (ai_disputed, pomaranczowe tlo), dzialy pytan (question_categories)
i wersja bazy (db_info) ZOSTAJA - to tresc bazy, nie postep nauki.
Zrodlo jest tylko czytane (kopia przez sqlite backup API). Uzycie: python make_clean_seed.py <zrodlo.db> <wynik.db>"""
import sqlite3
import sys
import time
from pathlib import Path

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
if dst.exists():
    dst.unlink()
s = sqlite3.connect(f"file:{src.as_posix()}?mode=ro", uri=True)
d = sqlite3.connect(dst)
s.backup(d)
s.close()
now = int(time.time() * 1000)
d.execute("""UPDATE srs_cards SET repetitions=0, interval_days=0, ease_factor=2.5, due_ms=?, lapses=0, state=0, step=0,
             stability=NULL, difficulty=NULL, last_review_ms=NULL, streak_days=0, last_good_day=NULL, hard=0""", (now,))
d.execute("DELETE FROM review_log")
d.execute("DELETE FROM import_meta")
d.execute("DELETE FROM sqlite_sequence WHERE name='review_log'") if d.execute("SELECT name FROM sqlite_master WHERE name='sqlite_sequence'").fetchone() else None
d.commit()
d.execute("VACUUM")
d.close()
c = sqlite3.connect(dst)
print("pytan:", c.execute("SELECT COUNT(*) FROM questions").fetchone()[0],
      "| karty z postepem:", c.execute("SELECT COUNT(*) FROM srs_cards WHERE state>0 OR repetitions>0 OR streak_days>0 OR hard>0").fetchone()[0],
      "| review_log:", c.execute("SELECT COUNT(*) FROM review_log").fetchone()[0],
      "| cache wyjasnien:", c.execute("SELECT COUNT(*) FROM explanation_cache").fetchone()[0],
      "| niepewne:", c.execute("SELECT COUNT(*) FROM ai_disputed").fetchone()[0],
      "| wersja bazy:", (c.execute("SELECT value FROM db_info WHERE key='db_version'").fetchone() or ["-"])[0],
      "| ukryte (Blad):", c.execute("SELECT COUNT(*) FROM questions WHERE study_hidden=1").fetchone()[0],
      "| user_version:", c.execute("PRAGMA user_version").fetchone()[0],
      "| integrity:", c.execute("PRAGMA integrity_check").fetchone()[0])
