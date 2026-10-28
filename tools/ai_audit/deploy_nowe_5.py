"""Wdrożenie 16 pytań Master (Nowe pytania - materiały: NOR/prawo przewozowe) z review/Nowe_pytania_Master_5_propozycja.md.
Pominięte na decyzję użytkownika: 9, 10, 11, 14. Kolejność wariantów jak w pliku. Uruchom przy zamkniętej aplikacji."""
import re, shutil, sqlite3, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
SKIP = {9, 10, 11, 14}
DBS = {"app": Path.home() / "Documents" / "memonic_app.db", "seed": ROOT / "app" / "assets" / "db" / "memonic_app_seed.db"}
txt = (ROOT / "review" / "Nowe_pytania_Master_5_propozycja.md").read_text(encoding="utf-8")
items = []
for m in re.finditer(r"^(\d+)\. (.+?)\n((?:\s+[ABC]\) .+\n?){3})", txt, re.M):
    n = int(m.group(1))
    if n in SKIP:
        continue
    opts = re.findall(r"^\s+([ABC])\) (.+?)\n?$", m.group(3), re.M)
    key = [l for l, o in opts if o.endswith("✔")][0]
    opts = [o.replace(" ✔", "").strip() for _, o in opts]
    items.append((n, m.group(2).strip(), opts, key))
assert len(items) == 16, len(items)
stamp = "2026-10-16"
for label, path in DBS.items():
    bak = (ROOT / "data" if label == "seed" else path.parent) / (path.name + "." + "bak_nowe5_" + time.strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(path, bak)
    db = sqlite3.connect(path)
    start = db.execute("SELECT MAX(id) FROM questions").fetchone()[0] + 1
    now = int(time.time() * 1000)
    for k, (n, q, o, key) in enumerate(items):
        qid = start + k
        db.execute("INSERT INTO questions (id,kategoria,tematyka,typ_pytania,pytanie,odp_a,odp_b,odp_c,odp_d,poprawna_odpowiedz,poprawna_odpowiedz_tekst,"
                   "zrodlo_pliku,review_status,review_notes,study_hidden,ai_verified) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (qid, "Kapitan żeglugi wielkiej", "Zarządzanie statkiem", "testowe", q, o[0], o[1], o[2], None, key, o["ABC".index(key)],
                    f"ai_authored:Nowe pytania - materiały (NOR_klauzule, Prawo) pyt. {n}; Reguły Haasko-Visbijskie/Hamburskie, BIMCO Laytime Definitions 2013",
                    "ok", f"ai_authored:{stamp}", 0, f"ai_authored:{stamp}:user_approved"))
        db.execute("INSERT INTO srs_cards (question_id,repetitions,interval_days,ease_factor,due_ms,lapses,state,step) VALUES (?,?,?,?,?,?,?,?)",
                   (qid, 0, 0, 2.5, now, 0, 0, 0))
    db.commit()
    print(label, start, "-", start + len(items) - 1, db.execute("select count(*) from questions").fetchone()[0], bak.name)
    db.close()
