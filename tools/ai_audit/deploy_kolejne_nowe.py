"""Wdrozenie 6 pytan HIGH z PDF 'Pytania super nowe' (review/Super_nowe/wyniki.json) do bazy aplikacji i seeda. --apply = zapis."""
import json, re, shutil, sqlite3, sys, time
from difflib import SequenceMatcher as S
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "review" / "Kolejne_nowe"
DBS = {"app": Path.home() / "Documents" / "memonic_app.db", "seed": ROOT / "app" / "assets" / "db" / "memonic_app_seed.db"}
NEW = ["T1","T10","T14","T26","T30","T32","T34","T39","T40","T41","T46","T69","T71"]
APPLY = "--apply" in sys.argv
res = {x["nr"]: x for x in json.loads((OUT / "wyniki.json").read_text(encoding="utf-8"))}
n = lambda s: re.sub(r"[\W_]+", " ", (s or "").lower()).strip()
con = sqlite3.connect(f"file:{DBS['app'].as_posix()}?mode=ro", uri=True)
rows = con.execute("SELECT id,pytanie,odp_a,odp_b,odp_c,odp_d FROM questions").fetchall(); con.close()
items = []
for nr in NEW:
    x = res[nr]; assert x["status"] == "HIGH"
    opts = [x["opcje"].get(k) for k in "ABCD"]
    full = n(x["pytanie"] + " " + " ".join(o or "" for o in opts))
    best = max(((S(None, full, n(" ".join(map(str, r[1:])))).ratio(), r[0]) for r in rows))
    print(nr, "najblizszy w bazie:", best)
    assert best[0] < 0.96, nr
    items.append((nr, x, opts))
if not APPLY: sys.exit(0)
log = []
first = None
for label, path in DBS.items():
    bak = (ROOT / "data" if label == "seed" else path.parent) / (path.name + f".bak_kolejne_nowe_{time.strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(path, bak)
    db = sqlite3.connect(path, timeout=30)
    start = db.execute("SELECT MAX(id) FROM questions").fetchone()[0] + 1
    first = first or start; assert start == first
    now = int(time.time() * 1000)
    for k, (nr, x, opts) in enumerate(items):
        qid = start + k; key = x["zgodna"]
        db.execute("INSERT INTO questions (id,kategoria,podkategoria,poziom,tematyka,nr_pytania,typ_pytania,pytanie,odp_a,odp_b,odp_c,odp_d,poprawna_odpowiedz,poprawna_odpowiedz_tekst,zrodlo_pliku,review_status,review_notes,study_hidden,ai_verified,image_path) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (qid, "Kapitan żeglugi wielkiej", None, None, "Zarządzanie statkiem", None, "testowe", x["pytanie"], *opts, key, dict(zip("ABCD", opts))[key],
             f"Kolejne nowe pytania (testy.pdf, poziom zarządzania) {nr}", "ok", "exam_scan:" + " | ".join(x["podstawy"].values())[:200], 0, "exam_scan:ai_high_kolejne_nowe_sonnet_sol:2026-10-13", None))
        db.execute("INSERT INTO srs_cards (question_id,repetitions,interval_days,ease_factor,due_ms,lapses,state,step) VALUES (?,?,?,?,?,?,?,?)", (qid, 0, 0, 2.5, now, 0, 0, 0))
        if label == "app": log.append({"db_id": qid, "pdf_nr": nr, "klucz": key})
    db.commit(); print(label, "razem", db.execute("SELECT COUNT(*) FROM questions").fetchone()[0], "ID od", start, bak.name); db.close()
(OUT / "wdrozenie_log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
