"""Wdrożenie wybranych pytań Master z prezentacji (tools/ai_audit/nowe6_data.py; numeracja jak w review/Nowe_pytania_Master_6_do_przegladu.docx:
oryginalne pytanie nr 11 pominięte, reszta numerowana od 1). Uruchom przy zamkniętej aplikacji; kopie obu baz przed zapisem."""
import shutil, sqlite3, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nowe6_data import Q as ALL

ROOT = Path(__file__).resolve().parents[2]
PICK = [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 18, 19, 20, 23, 24, 25, 28, 30, 31]
if len(sys.argv) > 1:  # np. '6,16,17,21,22,26,27,29' - dowolny podzbiór (numeracja jak w docx)
    PICK = [int(x) for x in sys.argv[1].split(',')]
DBS = {"app": Path.home() / "Documents" / "memonic_app.db", "seed": ROOT / "app" / "assets" / "db" / "memonic_app_seed.db"}
numbered = [q for i, q in enumerate(ALL, 1) if i != 11]
items = [(n, numbered[n - 1]) for n in PICK]
stamp = time.strftime("%Y-%m-%d")
for label, path in DBS.items():
    bak = (ROOT / "data" if label == "seed" else path.parent) / (path.name + ".bak_nowe6_" + time.strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(path, bak)
    db = sqlite3.connect(path)
    start = db.execute("SELECT MAX(id) FROM questions").fetchone()[0] + 1
    now = int(time.time() * 1000)
    have = {r[0] for r in db.execute('SELECT pytanie FROM questions')}
    if any(q in have for _, (_, q, *_r) in items):
        sys.exit('Któreś z tych pytań już jest w bazie - przerwano przed zapisem.')
    for k, (n, (tem, q, o, key, src)) in enumerate(items):
        qid = start + k
        db.execute("INSERT INTO questions (id,kategoria,tematyka,typ_pytania,pytanie,odp_a,odp_b,odp_c,odp_d,poprawna_odpowiedz,poprawna_odpowiedz_tekst,"
                   "zrodlo_pliku,review_status,review_notes,study_hidden,ai_verified) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (qid, "Kapitan żeglugi wielkiej", "Zarządzanie statkiem", "testowe", q, o[0], o[1], o[2], None, key, o["ABC".index(key)],
                    f"ai_authored:Prezentacja prawo morskie ({src})", "ok", f"ai_authored:{stamp}", 0, f"ai_authored:{stamp}:user_approved"))
        db.execute("INSERT INTO srs_cards (question_id,repetitions,interval_days,ease_factor,due_ms,lapses,state,step) VALUES (?,?,?,?,?,?,?,?)",
                   (qid, 0, 0, 2.5, now, 0, 0, 0))
    db.commit()
    print(label, start, "-", start + len(items) - 1, db.execute("select count(*) from questions").fetchone()[0], bak.name)
    db.close()
