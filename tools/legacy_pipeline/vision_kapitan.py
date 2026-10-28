"""
CLI: Vision full-page dla Kapitan żeglugi wielkiej.
Pytania error / niezweryfikowane — pełna strona PDF (lub 2 strony) do OpenRouter.
"""
import argparse
import json
import os
import sys
from datetime import date, datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv

load_dotenv(os.path.join(BASE_DIR, ".env"))

from init_db import get_connection
from pdf_page import render_pages_for_question, save_question_page_audit
from openrouter_vision import (
    extract_question_from_pages,
    validate_parsed,
)

CACHE_ROOT = os.path.join(BASE_DIR, "vision_cache")
LOG_PATH = os.path.join(BASE_DIR, "vision_kapitan.log")

SELECT_KAPITAN = """
SELECT id, nr_pytania, pytanie, zrodlo_pliku, typ_pytania
FROM questions
WHERE kategoria = 'Kapitan żeglugi wielkiej'
  AND (review_status = 'error'
       OR review_status IS NULL
       OR review_status = '')
  AND zrodlo_pliku IS NOT NULL AND zrodlo_pliku != ''
  AND zrodlo_pliku NOT LIKE '%colpkg%'
  AND zrodlo_pliku LIKE '%Kapitan%'
"""


def log(msg):
    print(msg)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def make_scan_cache_dir():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(CACHE_ROOT, f"kapitan_{stamp}")
    os.makedirs(path, exist_ok=True)
    return path


def fetch_questions(conn, question_id=None, limit=None):
    sql = SELECT_KAPITAN
    params = []
    if question_id is not None:
        sql += " AND id = ?"
        params.append(question_id)
    sql += " ORDER BY COALESCE(nr_pytania, id), id"
    if limit is not None:
        sql += f" LIMIT {int(limit)}"
    return conn.execute(sql, params).fetchall()


def save_response_cache(cache_dir, question_id, data):
    path = os.path.join(cache_dir, f"{question_id}.response.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def update_success(conn, question_id, data, model):
    notes = f"vision_page:{model}:{date.today().isoformat()}"
    conn.execute(
        """UPDATE questions SET
            pytanie=?, odp_a=?, odp_b=?, odp_c=?, odp_d=?,
            poprawna_odpowiedz=?, poprawna_odpowiedz_tekst=?,
            typ_pytania=?,
            review_status=NULL,
            review_notes=?
        WHERE id=?""",
        (
            data["pytanie"],
            data["odp_a"],
            data["odp_b"],
            data["odp_c"],
            data["odp_d"],
            data["poprawna_odpowiedz"],
            data["poprawna_odpowiedz_tekst"],
            data["typ_pytania"],
            notes,
            question_id,
        ),
    )
    conn.commit()


def update_fail_notes(conn, question_id, msg):
    conn.execute(
        "UPDATE questions SET review_notes=? WHERE id=?",
        (f"vision_page_fail:{msg[:200]}", question_id),
    )
    conn.commit()


def process_one(row, conn, cache_dir, page_cache, dry_run):
    qid = row["id"]
    path = row["zrodlo_pliku"]
    if not path or not os.path.isfile(path):
        return "SKIP", "no PDF file"

    pngs, tag, warn, page_nums = render_pages_for_question(
        path,
        nr_pytania=row["nr_pytania"],
        pytanie=row["pytanie"],
        cache_dir=cache_dir,
        page_cache=page_cache,
    )
    if not pngs:
        return "FAIL", warn or "page render failed"

    save_question_page_audit(cache_dir, qid, pngs, tag)
    pages_label = f"pages={page_nums[0]}" if len(page_nums) == 1 else (
        f"pages={page_nums[0]}-{page_nums[-1]}"
    )
    tag_label = f"[{tag}] {pages_label}"
    if warn:
        tag_label += f" ({warn})"

    if dry_run:
        return "DRY", tag_label

    try:
        raw = extract_question_from_pages(
            pngs,
            nr_pytania=row["nr_pytania"],
            pytanie_hint=row["pytanie"],
        )
        model = raw.pop("_model", "unknown")
        raw.pop("_usage", None)
        save_response_cache(cache_dir, qid, raw)

        ok, normalized, err = validate_parsed(raw)
        if not ok:
            update_fail_notes(conn, qid, err)
            return "FAIL", f"validation: {err}"

        update_success(conn, qid, normalized, model)
        return "OK", tag_label
    except Exception as e:
        update_fail_notes(conn, qid, str(e))
        return "FAIL", str(e)[:120]


def main():
    parser = argparse.ArgumentParser(
        description="Vision full-page — Kapitan żeglugi wielkiej"
    )
    parser.add_argument("--limit", type=int, help="Maks. liczba pytań")
    parser.add_argument("--id", type=int, help="Tylko to ID pytania")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Render stron + cache, bez API i UPDATE bazy",
    )
    parser.add_argument("--cache-dir", help="Folder cache (domyślnie kapitan_TIMESTAMP)")
    args = parser.parse_args()

    cache_dir = args.cache_dir or make_scan_cache_dir()
    conn = get_connection()
    rows = fetch_questions(conn, question_id=args.id, limit=args.limit)

    if not rows:
        print("Brak pytań Kapitan (error / niezweryfikowane) z PDF.")
        return 0

    print(f"Do przetworzenia: {len(rows)} pytań (Kapitan full-page)")
    print(f"Cache: {cache_dir}")
    if args.dry_run:
        print("(dry-run — bez API i bez zapisu do bazy)")

    log(f"\n=== kapitan {datetime.now().isoformat()} cache={cache_dir} ===")

    page_cache = {}
    stats = {"OK": 0, "SKIP": 0, "FAIL": 0, "DRY": 0}

    for i, row in enumerate(rows, 1):
        status, detail = process_one(
            row, conn, cache_dir, page_cache, args.dry_run
        )
        stats[status] = stats.get(status, 0) + 1
        line = f"[{i}/{len(rows)}] ID={row['id']} {status}"
        if detail:
            line += f" {detail}"
        log(line)

    print("\n--- Podsumowanie ---")
    for k, v in stats.items():
        if v:
            print(f"  {k}: {v}")
    print(f"Cropy i JSON: {cache_dir}")
    conn.close()
    return 0 if stats.get("FAIL", 0) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
