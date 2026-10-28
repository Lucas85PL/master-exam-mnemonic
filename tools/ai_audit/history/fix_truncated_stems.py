"""Jednorazowo (2026-10-08): naprawa urwanych/pomieszanych tresci pytan Master (tresc z PDF wg ekstraktora tabel), duplikatu 1794,
oraz 2 pytan Pokladu. Kopie *.bak_stems_* (seed w data/), log history/logs/fix_truncated_stems_log.json."""
import glob
import json
import os
import shutil
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "pdf_extraction"))
import pdf_table_master as m  # noqa: E402

FILES = {"nawigacja": "01-01", "urządzenia nawigacyjne": "01-02", "bezpieczeństwo nawigacji": "01-03",
         "zarządzanie statkiem": "02-01", "bezpieczeństwo statku": "02-02", "prawo morskie": "02-03"}
ext = {}
for k, v in FILES.items():
    f = glob.glob(str(ROOT / "sources" / "pdf_urzad" / "Master" / f"*{v}*.pdf"))[0]
    ext[k] = {q["nr"]: q for q in m.extract(f) if q["nr"] is not None}

FROM_PDF = [1622, 1626, 1631, 1655, 1693, 1717, 1742, 1664, 1705, 1768, 1802]
UNHIDE = [1622, 1626, 1631, 1693, 1742]  # byly ukryte („Błąd”) przez urwany tekst; klucze zgodne z PDF
DELETE = [1794]  # duplikat 1802 z urwanym tekstem „się na:”
STAMP = "2026-10-08"
log = {}
for label, path in {"app": Path.home() / "Documents" / "memonic_app.db",
                    "seed": ROOT / "app" / "assets" / "db" / "memonic_app_seed.db"}.items():
    bak = (ROOT / "data" if label == "seed" else path.parent) / (path.name + f".bak_stems_{time.strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(path, bak)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    changes = []
    for i in FROM_PDF:
        r = db.execute("SELECT * FROM questions WHERE id=?", (i,)).fetchone()
        p = ext[r["tematyka"]][r["nr_pytania"]]
        assert p["correct"] and p["correct"][0] == r["poprawna_odpowiedz"], (i, p["correct"], r["poprawna_odpowiedz"])
        changes.append({"id": i, "old": r["pytanie"], "new": p["q"]})
        db.execute("UPDATE questions SET pytanie=?, ai_verified=? WHERE id=?", (p["q"], f"manual:tekst_z_pdf:{STAMP}", i))
    for i in UNHIDE:
        db.execute("UPDATE questions SET study_hidden=0 WHERE id=?", (i,))
    r = db.execute("SELECT pytanie FROM questions WHERE id=2078").fetchone()
    assert r["pytanie"].startswith("d Która")
    changes.append({"id": 2078, "old": r["pytanie"], "new": r["pytanie"][2:]})
    db.execute("UPDATE questions SET pytanie=?, ai_verified=? WHERE id=2078", (r["pytanie"][2:], f"manual:tekst_z_pdf:{STAMP}"))
    r = db.execute("SELECT pytanie FROM questions WHERE id=733").fetchone()
    assert r["pytanie"].startswith("cargo from")
    db.execute("UPDATE questions SET pytanie=?, ai_verified=? WHERE id=733", ("---------- " + r["pytanie"], f"manual:tekst_z_pdf:{STAMP}"))
    changes.append({"id": 733, "old": r["pytanie"], "new": "---------- " + r["pytanie"]})
    deleted = []
    for i in DELETE:
        deleted.append(dict(db.execute("SELECT * FROM questions WHERE id=?", (i,)).fetchone()))
        db.execute("DELETE FROM srs_cards WHERE question_id=?", (i,))
        db.execute("DELETE FROM explanation_cache WHERE question_id=?", (i,))
        if db.execute("SELECT name FROM sqlite_master WHERE name='review_log'").fetchone():
            db.execute("DELETE FROM review_log WHERE question_id=?", (i,))
        db.execute("DELETE FROM questions WHERE id=?", (i,))
    db.commit()
    print(label, "poprawiono", len(changes), "usunięto", len(deleted), "razem pytan", db.execute("SELECT COUNT(*) FROM questions").fetchone()[0], bak.name)
    log[label] = {"backup": str(bak), "changes": changes, "deleted": deleted, "unhidden": UNHIDE}
    db.close()
(Path(__file__).parent / "logs" / "fix_truncated_stems_log.json").write_text(
    json.dumps(log, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
