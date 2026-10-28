"""Jednorazowo (2026-10-09, schemat v7): uzupelnia w review_log kolumny streak_before / streak_after dla odpowiedzi
zapisanych przed v7, odtwarzajac serie dni wg tych samych regul co aplikacja (nextStreak: +1 raz na dzien nauki, blad zeruje).
Poczatkowa seria pytania = szacunek migracji v6 z kopii sprzed v6 (min(3, powtorzenia - lapsy) dla kart w powtorkach).
Kontrola: seria odtworzona po ostatniej odpowiedzi musi zgadzac sie z srs_cards.streak_days (raport rozbieznosci).
Uzycie: python backfill_review_streaks.py <baza.db> <kopia_przed_v6.db>   (robi kopie <baza>.bak_backfill_*)"""
import shutil
import sqlite3
import sys
import time
from pathlib import Path

db_path, pre_path = Path(sys.argv[1]), Path(sys.argv[2])
bak = db_path.with_name(db_path.name + f".bak_backfill_{time.strftime('%Y%m%d_%H%M%S')}")
shutil.copy2(db_path, bak)

pre = sqlite3.connect(f"file:{pre_path.as_posix()}?mode=ro", uri=True)
init = {}
for qid, state, reps, lapses, last in pre.execute(
        "SELECT question_id, state, repetitions, lapses, last_review_ms FROM srs_cards"):
    if state == 2 and (reps or 0) > 0:
        init[qid] = (min(3, max(0, (reps or 0) - (lapses or 0))), int(last // 86400000) if last else None)
pre.close()

db = sqlite3.connect(db_path)
cols = {r[1] for r in db.execute("PRAGMA table_info(review_log)")}
for c in ("streak_before", "streak_after"):
    if c not in cols:
        db.execute(f"ALTER TABLE review_log ADD COLUMN {c} INTEGER")

rows = db.execute("SELECT id, question_id, day, correct FROM review_log ORDER BY question_id, id").fetchall()
state = {}
updates = []
for rid, qid, day, correct in rows:
    days, last_good = state.get(qid, init.get(qid, (0, None)))
    before = days
    if not correct:
        days = 0
    elif last_good != day:
        days = min(days + 1, 99)
        last_good = day
    state[qid] = (days, last_good)
    updates.append((before, days, rid))
db.executemany("UPDATE review_log SET streak_before=?, streak_after=? WHERE id=?", updates)

mism = []
for qid, (days, _) in state.items():
    r = db.execute("SELECT streak_days FROM srs_cards WHERE question_id=?", (qid,)).fetchone()
    if r is not None and r[0] != days:
        mism.append((qid, days, r[0]))
db.commit()
print(f"uzupelniono {len(updates)} wpisow dziennika dla {len(state)} pytan; kopia: {bak.name}")
print(f"zgodnosc z aktualna seria w srs_cards: {len(state) - len(mism)}/{len(state)}; rozbieznosci: {len(mism)}", mism[:10])
tot = db.execute("SELECT COUNT(*), SUM(streak_after-streak_before), SUM(streak_after>=3 AND streak_before<3) FROM review_log").fetchone()
print("podsumowanie: odpowiedzi", tot[0], "| przyrost netto serii", tot[1], "| opanowane (zdarzenia)", tot[2])
db.close()
