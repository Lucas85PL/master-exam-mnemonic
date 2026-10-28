"""Jednorazowo (2026-10-06): wynik przegladu AI pytan z obrazkami (runs/audit_figures.json) -> baza aplikacji i seed.
 - literowki w tekscie (oczywiste) poprawione, ai_verified = ai_cascade_v5:tekst_poprawiony:img:<data>
 - 3017: tekst wariantu A uciety juz w PDF (nie dopisujemy), 3062: klucz z PDF kwestionowany przez AI (zostaje, decyzja czlowieka)
 - reszta pytan z obrazkiem: ai_cascade_v5:ok:img:<data>
Kopie *.bak_figaudit_* (seed trafia do data/). Log: history/logs/figures_audit_log.json."""
import json
import shutil
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STAMP = "2026-10-06"
DBS = {"app": Path.home() / "Documents" / "memonic_app.db", "seed": ROOT / "app" / "assets" / "db" / "memonic_app_seed.db"}
FIXES = {  # id -> (kolumna, stary fragment, nowy fragment)
    2971: ("odp_c", "za dala", "z dala"),
    2977: ("odp_a", "maneouvering", "manoeuvring"),
    3054: ("odp_b", "starking", "stacking"),
}
SPECIAL = {3017: "ai_cascade_v5:ok_tekst_uciety_w_PDF:img", 3062: "ai_cascade_v5:key_suspect:img"}
log = {}
for label, path in DBS.items():
    bak = (ROOT / "data" if label == "seed" else path.parent) / (path.name + f".bak_figaudit_{time.strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(path, bak)
    db = sqlite3.connect(path)
    ids = [r[0] for r in db.execute("SELECT id FROM questions WHERE image_path IS NOT NULL")]
    changed = []
    for qid in ids:
        mark = f"ai_cascade_v5:ok:img:{STAMP}"
        if qid in FIXES:
            col, old, new = FIXES[qid]
            val = db.execute(f"SELECT {col} FROM questions WHERE id=?", (qid,)).fetchone()[0]
            assert old in val, (qid, val)
            db.execute(f"UPDATE questions SET {col}=? WHERE id=?", (val.replace(old, new), qid))
            changed.append({"id": qid, "col": col, "old": val, "new": val.replace(old, new)})
            mark = f"ai_cascade_v5:tekst_poprawiony:img:{STAMP}"
        elif qid in SPECIAL:
            mark = f"{SPECIAL[qid]}:{STAMP}"
        db.execute("UPDATE questions SET ai_verified=? WHERE id=?", (mark, qid))
    db.commit()
    db.close()
    log[label] = {"backup": str(bak), "marked": len(ids), "text_fixes": changed}
    print(label, "oznaczono", len(ids), "poprawki", len(changed), bak.name)
out = Path(__file__).parent / "logs" / "figures_audit_log.json"
out.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
