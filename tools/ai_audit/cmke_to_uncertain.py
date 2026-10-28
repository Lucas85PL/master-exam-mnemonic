"""Pytania z oznaczeniem „Odp. wg. CMKE” (cmke_diff) -> oznaczenie „Niepewne” (ai_disputed) i usunięcie oznaczenia CMKE.
Obejmuje też kopie z grupy powtórzeń. Kopia bazy przed zmianą + log JSON. Uruchamiać przy zamkniętej aplikacji.
Użycie: python cmke_to_uncertain.py <baza> [<baza> ...] [--apply]"""
import json, shutil, sqlite3, sys, time
from pathlib import Path

apply = "--apply" in sys.argv
for path in [a for a in sys.argv[1:] if not a.startswith("--")]:
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE IF NOT EXISTS ai_disputed (question_id INTEGER PRIMARY KEY)")
    con.execute("CREATE TABLE IF NOT EXISTS cmke_diff (question_id INTEGER PRIMARY KEY, cmke_letter TEXT)")
    cm = con.execute("SELECT question_id, cmke_letter FROM cmke_diff").fetchall()
    ids = {r[0] for r in cm}
    group = set(ids)
    has_group = any(r[1] == "dup_group" for r in con.execute("PRAGMA table_info(questions)"))
    for (i,) in [] if not has_group else con.execute("SELECT q2.id FROM questions q1 JOIN questions q2 ON q1.dup_group = q2.dup_group "
                            f"WHERE q1.dup_group IS NOT NULL AND q1.id IN ({','.join(map(str, ids)) or 'NULL'})"):
        group.add(i)
    before = {r[0] for r in con.execute("SELECT question_id FROM ai_disputed")}
    print(path, "| cmke_diff:", len(cm), "| z kopiami:", len(group), "| już niepewnych:", len(before), "| razem po:", len(before | group))
    if not apply:
        con.close()
        continue
    ts = time.strftime("%Y%m%d_%H%M%S")
    con.close()
    shutil.copy2(path, f"{path}.bak_cmke_to_uncertain_{ts}")
    Path(f"{path}.cmke_log_{ts}.json").write_text(json.dumps({"cmke_diff": cm, "ai_disputed_dodane": sorted(group - before)}, ensure_ascii=False), encoding="utf-8")
    con = sqlite3.connect(path)
    con.executemany("INSERT OR IGNORE INTO ai_disputed(question_id) VALUES (?)", [(i,) for i in group])
    con.execute("DELETE FROM cmke_diff")
    con.commit()
    print("  zapisano: ai_disputed =", con.execute("SELECT COUNT(*) FROM ai_disputed").fetchone()[0], "| cmke_diff =", con.execute("SELECT COUNT(*) FROM cmke_diff").fetchone()[0])
    con.close()
