"""Dodaje do bazy pytania z rysunkami z arkuszy PDF (wszystkie arkusze poza F1-P6 Lacznosc morska, ktora weszla w pilotazu).

  python apply_figures.py             # podglad (nic nie zapisuje poza PNG w app/assets/question_images)
  python apply_figures.py --apply     # kopia *.bak_figures_* obu baz, kolumna image_path, UPDATE/INSERT

Zasady: klucz odpowiedzi czytany prosto z PDF; pytanie juz obecne w bazie (ta sama tresc i klucz, bez obrazka)
dostaje tylko image_path, reszta jest wstawiana (nowe id = MAX+1, ta sama numeracja w bazie aplikacji i w seedzie)."""
import argparse
import re
import hashlib
import json
import shutil
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from figures import image_questions, save_figure  # noqa: E402
from list_figures import sheets  # noqa: E402
from pdf_table_dzial import n  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "sources" / "pdf_urzad"
IMG_DIR = ROOT / "app" / "assets" / "question_images"
DBS = {"app": Path.home() / "Documents" / "memonic_app.db",
       "seed": ROOT / "app" / "assets" / "db" / "memonic_app_seed.db"}
STAMP = "2026-10-06"
# pominiete recznie: rysunek wykryty omylkowo (to fragment tekstu z adnotacja, nie rysunek)
SKIP = {("Angielski/Oficer wachtowy/F1-P1-Nawigacja .pdf", 4, 28)}


def meta(pdf):
    """(kategoria, podkategoria, poziom, tematyka) wg polozenia arkusza i nazwy pliku."""
    rel = pdf.relative_to(SRC).as_posix()
    tem = re.sub(r"^F\d-P\d-", "", pdf.stem).strip()
    if rel.startswith("Angielski/"):
        return "Angielski", "Oficer wachtowy", None, tem
    if "Poziom operacyjny" in rel:
        return "Dział pokładowy", "Oficer wachtowy", "operacyjny", tem
    return ("Dział pokładowy", "Starszy oficer pokładowy w żegludze międzynarodowej", "zarządzania", tem)


def collect():
    items = []
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = IMG_DIR / "_tmp.png"
    for pdf in sheets():
        kat, sub, poziom, tem = meta(pdf)
        rel = pdf.relative_to(SRC).as_posix()
        for q in image_questions(pdf):
            if (rel, q["page"], q["nr"]) in SKIP:
                continue
            if q["correct"] not in list("ABCD"):
                print("POMINIETO (brak klucza w PDF):", rel, q["nr"])
                continue
            save_figure(q, tmp)
            data = tmp.read_bytes()
            name = f"q_{hashlib.sha1(data).hexdigest()[:10]}.png"
            (IMG_DIR / name).write_bytes(data)
            items.append({
                "kategoria": kat, "podkategoria": sub, "poziom": poziom, "tematyka": tem, "nr": q["nr"],
                "pytanie": q["q"], "opts": [q["opts"].get(l) for l in "ABCD"], "correct": q["correct"],
                "image": name, "src": rel,
            })
    tmp.unlink(missing_ok=True)
    return items


def match_key(q, a, b, c, d, corr):
    return (n(q), n(a or ""), n(b or ""), n(c or ""), n(d or ""), corr)


def plan(db, items):
    cur = db.execute("SELECT id, kategoria, pytanie, odp_a, odp_b, odp_c, odp_d, poprawna_odpowiedz, tematyka, poziom "
                     "FROM questions" + (" WHERE image_path IS NULL" if has_col(db) else ""))
    pool = {}
    for r in cur:
        pool.setdefault((r[1], r[8], r[9]) + match_key(r[2], r[3], r[4], r[5], r[6], (r[7] or "").upper()), []).append(r[0])
    upd, ins = [], []
    for it in items:
        k = (it["kategoria"], it["tematyka"], it["poziom"]) + match_key(it["pytanie"], *it["opts"], it["correct"])
        ids = pool.get(k)
        if ids:
            upd.append((ids.pop(0), it))
        else:
            ins.append(it)
    return upd, ins


def has_col(db):
    return any(r[1] == "image_path" for r in db.execute("PRAGMA table_info(questions)"))


def apply(path, items, label):
    bak = path.with_name(path.name + f".bak_figures_{time.strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(path, bak)
    db = sqlite3.connect(path)
    if not has_col(db):
        db.execute("ALTER TABLE questions ADD COLUMN image_path TEXT")
    upd, ins = plan(db, items)
    now = int(time.time() * 1000)
    max_id = db.execute("SELECT MAX(id) FROM questions").fetchone()[0]
    log = {"backup": str(bak), "updated": [], "inserted": []}
    for qid, it in upd:
        db.execute("UPDATE questions SET image_path=?, ai_verified=? WHERE id=?",
                   (it["image"], f"pdf_urzad:z_obrazkiem:{STAMP}", qid))
        log["updated"].append({"id": qid, "nr": it["nr"], "image": it["image"]})
    nid = max_id
    for it in ins:
        nid += 1
        a, b, c, d = it["opts"]
        db.execute(
            "INSERT INTO questions (id, kategoria, podkategoria, poziom, tematyka, nr_pytania, typ_pytania, pytanie,"
            " odp_a, odp_b, odp_c, odp_d, poprawna_odpowiedz, poprawna_odpowiedz_tekst, zrodlo_pliku, review_status,"
            " review_notes, study_hidden, ai_verified, image_path) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (nid, it["kategoria"], it["podkategoria"], it["poziom"], it["tematyka"], it["nr"], "testowe", it["pytanie"],
             a, b, c, d, it["correct"], dict(zip("ABCD", it["opts"])).get(it["correct"]), it["src"], "ok",
             f"figure_from_pdf:{STAMP}", 0, f"pdf_urzad:z_obrazkiem:{STAMP}", it["image"]))
        db.execute("INSERT INTO srs_cards (question_id, repetitions, interval_days, ease_factor, due_ms, lapses, state, step)"
                   " VALUES (?,?,?,?,?,?,?,?)", (nid, 0, 0, 2.5, now, 0, 0, 0))
        log["inserted"].append({"id": nid, "nr": it["nr"], "kat": it["kategoria"], "image": it["image"]})
    db.commit()
    db.close()
    print(f"[{label}] zaktualizowano {len(upd)}, dodano {len(ins)}, kopia: {bak.name}")
    return log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    items = collect()
    print(f"Pytan z obrazkami w PDF: {len(items)}; unikalnych obrazkow: {len({i['image'] for i in items})}")
    for label, path in DBS.items():
        db = sqlite3.connect(path)
        upd, ins = plan(db, items)
        print(f"[{label}] do aktualizacji {len(upd)} (id {[u[0] for u in upd]}), do dodania {len(ins)}")
        db.close()
    if args.apply:
        logs = {label: apply(path, items, label) for label, path in DBS.items()}
        ids = {l: [x["id"] for x in v["inserted"]] for l, v in logs.items()}
        assert ids["app"] == ids["seed"], "rozjazd numeracji ID miedzy baza aplikacji a seedem"
        out = ROOT / "tools" / "pdf_extraction" / "figures_apply_log.json"
        out.write_text(json.dumps(logs, ensure_ascii=False, indent=1), encoding="utf-8")
        print("Log:", out)


if __name__ == "__main__":
    main()
