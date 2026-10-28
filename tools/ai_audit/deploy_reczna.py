"""Wdrozenie pytan zweryfikowanych recznie przez uzytkownika (Pytania - dodac do bazy.docx) - review/Reczna_weryfikacja/q2.json. --apply = zapis."""
import json, shutil, sqlite3, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "review" / "Reczna_weryfikacja"
DBS = {"app": Path.home() / "Documents" / "memonic_app.db", "seed": ROOT / "app" / "assets" / "db" / "memonic_app_seed.db"}
SKIP = {40, 73, 92, 45, 89, 140, 54, 72, 128}   # duplikaty (partia/baza) i 3 pytania z watpliwym kluczem (do decyzji uzytkownika)
APPLY = "--apply" in sys.argv
Q = [q for q in json.load(open(OUT / "q2.json", encoding="utf-8")) if q["n"] not in SKIP]
assert all(q["k"] in q["o"] for q in Q)
TEM = {"ZS": "Zarządzanie statkiem", "BS": "Bezpieczeństwo statku", "PM": "Prawo morskie"}
print("do wdrozenia:", len(Q), "rozklad kluczy:", {k: sum(1 for q in Q if q["k"] == k) for k in "ABCD"})
if not APPLY: sys.exit(0)
log = []; first = None
for label, path in DBS.items():
    bak = (ROOT / "data" if label == "seed" else path.parent) / (path.name + f".bak_reczna_{time.strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(path, bak)
    db = sqlite3.connect(path, timeout=30)
    start = db.execute("SELECT MAX(id) FROM questions").fetchone()[0] + 1
    first = first or start; assert start == first
    now = int(time.time() * 1000)
    for i, q in enumerate(Q):
        qid = start + i; o = [q["o"].get(L) for L in "ABCD"]; key = q["k"]
        db.execute("INSERT INTO questions (id,kategoria,podkategoria,poziom,tematyka,nr_pytania,typ_pytania,pytanie,odp_a,odp_b,odp_c,odp_d,poprawna_odpowiedz,poprawna_odpowiedz_tekst,zrodlo_pliku,review_status,review_notes,study_hidden,ai_verified,image_path) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (qid, "Kapitan żeglugi wielkiej", None, None, TEM.get(q["id"][:2], "Egzamin kapitański"), None, "testowe", q["q"], *o, key, q["o"][key],
             f"skany egzaminów, weryfikacja ręczna ({q['id']})", "ok", "exam_scan: klucz zweryfikowany przez użytkownika", 0, "manual:exam_scan_user_verified:2026-10-13", None))
        db.execute("INSERT INTO srs_cards (question_id,repetitions,interval_days,ease_factor,due_ms,lapses,state,step) VALUES (?,?,?,?,?,?,?,?)", (qid, 0, 0, 2.5, now, 0, 0, 0))
        if label == "app": log.append({"db_id": qid, "zrodlo": q["id"], "klucz": key})
    db.commit(); print(label, "razem", db.execute("SELECT COUNT(*) FROM questions").fetchone()[0], "ID od", start, bak.name); db.close()
(OUT / "wdrozenie_log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
