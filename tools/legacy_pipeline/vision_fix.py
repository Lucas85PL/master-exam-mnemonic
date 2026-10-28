"""
CLI: auto-fix pytań z review_status='error' przez OpenRouter Vision.
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
from pdf_crop import render_question_strip, save_strip_cache
from openrouter_vision import extract_question_from_image, validate_parsed

CACHE_ROOT = os.path.join(BASE_DIR, "vision_cache")
LOG_PATH = os.path.join(BASE_DIR, "vision_fix.log")

PDF_FILTER = """
  AND kategoria != 'Chief Officer'
  AND zrodlo_pliku NOT LIKE '%colpkg%'
  AND zrodlo_pliku IS NOT NULL AND zrodlo_pliku != ''
"""

SELECT_ERROR = f"""
SELECT id, nr_pytania, pytanie, zrodlo_pliku, typ_pytania
FROM questions
WHERE review_status = 'error'
{PDF_FILTER}
"""

SELECT_RESCAN = f"""
SELECT id, nr_pytania, pytanie, zrodlo_pliku, typ_pytania
FROM questions
WHERE (
    review_status = 'error'
    OR review_notes LIKE 'vision:%'
    OR review_notes LIKE 'vision_fail:%'
)
{PDF_FILTER}
"""


def log(msg):
    print(msg)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def make_scan_cache_dir():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(CACHE_ROOT, f"scan_{stamp}")
    os.makedirs(path, exist_ok=True)
    return path


def fetch_questions(conn, rescan=False, question_id=None, limit=None):
    sql = SELECT_RESCAN if rescan else SELECT_ERROR
    params = []
    if question_id is not None:
        sql += " AND id = ?"
        params.append(question_id)
    sql += " ORDER BY COALESCE(nr_pytania, id), id"
    if limit is not None:
        sql += f" LIMIT {int(limit)}"
    rows = conn.execute(sql, params).fetchall()
    return rows


def skip_reason(row):
    path = row["zrodlo_pliku"]
    if not path or not os.path.isfile(path):
        return "no PDF file"
    return None


def save_response_cache(cache_dir, question_id, data):
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, f"{question_id}.response.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def update_success(conn, question_id, data, model):
    notes = f"vision:{model}:{date.today().isoformat()}"
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
        (f"vision_fail:{msg[:200]}", question_id),
    )
    conn.commit()


def process_one(row, conn, cache_dir, dry_run):
    qid = row["id"]
    reason = skip_reason(row)
    if reason:
        return "SKIP", reason

    png, tag, warn = render_question_strip(
        row["zrodlo_pliku"],
        nr_pytania=row["nr_pytania"],
        pytanie=row["pytanie"],
    )
    if not png:
        return "FAIL", warn or "crop failed"

    crop_path = save_strip_cache(cache_dir, qid, png, tag)
    tag_label = f"[{tag}]" if tag else ""
    if warn:
        tag_label += f" ({warn})"

    try:
        raw = extract_question_from_image(png, nr_pytania=row["nr_pytania"])
        model = raw.pop("_model", "unknown")
        raw.pop("_usage", None)
        save_response_cache(cache_dir, qid, raw)

        ok, normalized, err = validate_parsed(raw)
        if not ok:
            if not dry_run:
                update_fail_notes(conn, qid, err)
            return "FAIL", f"validation: {err}"

        if dry_run:
            return "DRY", tag_label

        update_success(conn, qid, normalized, model)
        return "OK", f"{tag_label} -> {os.path.basename(crop_path)}"
    except Exception as e:
        if not dry_run:
            update_fail_notes(conn, qid, str(e))
        return "FAIL", str(e)[:120]


def main():
    parser = argparse.ArgumentParser(description="Vision auto-fix pytań z błędem parsowania")
    parser.add_argument("--limit", type=int, help="Maks. liczba pytań")
    parser.add_argument("--id", type=int, help="Tylko to ID pytania")
    parser.add_argument("--dry-run", action="store_true",
                        help="Crop + API + cache, bez UPDATE bazy")
    parser.add_argument(
        "--rescan",
        action="store_true",
        help="Ponów skan: error + wcześniejsze vision/vision_fail",
    )
    parser.add_argument(
        "--cache-dir",
        help="Folder na cropy (domyślnie vision_cache/scan_YYYYMMDD_HHMMSS)",
    )
    args = parser.parse_args()

    cache_dir = args.cache_dir or make_scan_cache_dir()

    conn = get_connection()
    rows = fetch_questions(
        conn, rescan=args.rescan, question_id=args.id, limit=args.limit
    )

    if not rows:
        print("Brak pytań do przetworzenia.")
        return 0

    mode = "rescan" if args.rescan else "error"
    print(f"Do przetworzenia: {len(rows)} pytań (tryb: {mode})")
    print(f"Cropy: {cache_dir}")
    if args.dry_run:
        print("(tryb dry-run — crop + API, bez zapisu do bazy)")

    log(f"\n=== run {datetime.now().isoformat()} mode={mode} cache={cache_dir} ===")

    stats = {"OK": 0, "SKIP": 0, "FAIL": 0, "DRY": 0}

    for i, row in enumerate(rows, 1):
        status, detail = process_one(row, conn, cache_dir, args.dry_run)
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
