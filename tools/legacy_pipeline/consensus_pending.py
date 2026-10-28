"""
Konsensus 5 modeli (3/5 zgodnych z bazą) → review_status=ok dla pending (error/NULL).
Bez wymogu vision_page. Pytania testowe z poprawną literą A–D w bazie.
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
from openrouter_consensus import (
    ask_all_models,
    evaluate_consensus_majority,
    get_consensus_models,
)

LOG_PATH = os.path.join(BASE_DIR, "consensus_pending.log")
JSONL_PATH = os.path.join(BASE_DIR, "consensus_pending_results.jsonl")

PENDING = "(review_status IS NULL OR review_status = '' OR review_status = 'error')"
NOT_ANKI = """(
    kategoria != 'Chief Officer'
    AND (zrodlo_pliku IS NULL OR zrodlo_pliku NOT LIKE '%colpkg%')
)"""
NOT_ALREADY_OK = """(
    review_notes IS NULL
    OR (
        review_notes NOT LIKE '%consensus_ok:%'
        AND review_notes NOT LIKE '%consensus_5ok:%'
        AND review_notes NOT LIKE '%audit_ok:%'
    )
)"""

ROW_FIELDS = """
    id, kategoria, nr_pytania, typ_pytania, pytanie,
    odp_a, odp_b, odp_c, odp_d, poprawna_odpowiedz, review_notes
"""


def log(msg):
    print(msg)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def append_jsonl(record, path):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def count_pending(conn):
    sql = f"""
        SELECT COUNT(*) FROM questions
        WHERE {PENDING} AND {NOT_ANKI} AND {NOT_ALREADY_OK}
          AND lower(trim(coalesce(typ_pytania, 'testowe'))) = 'testowe'
          AND upper(trim(coalesce(poprawna_odpowiedz, ''))) IN ('A','B','C','D')
          AND trim(coalesce(pytanie, '')) != ''
    """
    return conn.execute(sql).fetchone()[0]


def fetch_pending(conn, limit=None, offset=0, question_id=None):
    sql = f"""
        SELECT {ROW_FIELDS} FROM questions
        WHERE {PENDING} AND {NOT_ANKI} AND {NOT_ALREADY_OK}
          AND lower(trim(coalesce(typ_pytania, 'testowe'))) = 'testowe'
          AND upper(trim(coalesce(poprawna_odpowiedz, ''))) IN ('A','B','C','D')
          AND trim(coalesce(pytanie, '')) != ''
    """
    params = []
    if question_id is not None:
        sql += " AND id = ?"
        params.append(question_id)
    sql += " ORDER BY kategoria, COALESCE(nr_pytania, id), id"
    if limit is not None:
        sql += f" LIMIT {int(limit)}"
        if offset:
            sql += f" OFFSET {int(offset)}"
    rows = conn.execute(sql, params).fetchall()
    out = []
    for row in rows:
        opts = sum(
            1
            for k in ("odp_a", "odp_b", "odp_c", "odp_d")
            if row[k] and str(row[k]).strip()
        )
        if opts >= 2:
            out.append(row)
    return out


def mark_ok(conn, question_id, agree_count, n_models):
    note_suffix = (
        f" | consensus_5ok:{agree_count}/{n_models}:{date.today().isoformat()}"
    )
    conn.execute(
        """UPDATE questions SET
            review_status = 'ok',
            review_notes = COALESCE(review_notes, '') || ?
        WHERE id = ?""",
        (note_suffix, question_id),
    )
    conn.commit()


def process_one(row, conn, models, dry_run, min_agree, jsonl_path):
    qid = row["id"]
    db_l = (row["poprawna_odpowiedz"] or "").strip().upper()

    try:
        votes = ask_all_models(
            row["pytanie"],
            row["odp_a"],
            row["odp_b"],
            row["odp_c"],
            row["odp_d"],
            models=models,
        )
    except Exception as e:
        rec = {"id": qid, "action": "API_FAIL", "error": str(e)}
        append_jsonl(rec, jsonl_path)
        return "API_FAIL", str(e)[:80]

    action, _, detail = evaluate_consensus_majority(
        votes, db_l, min_agree=min_agree
    )
    letters = [v.get("letter") for v in votes]
    rec = {
        "id": qid,
        "kategoria": row["kategoria"],
        "action": action,
        "db": db_l,
        "votes": {v["model"]: v.get("letter") for v in votes},
        "vote_letters": letters,
        "detail": detail,
        "ts": datetime.now().isoformat(timespec="seconds"),
    }
    append_jsonl(rec, jsonl_path)

    if action == "AUTO_OK":
        agree = sum(1 for x in letters if x == db_l)
        if not dry_run:
            mark_ok(conn, qid, agree, len(models))
        return "AUTO_OK", detail

    return action, detail


def main():
    ap = argparse.ArgumentParser(
        description="Konsensus 5× (3/5 z bazą) → OK dla pending"
    )
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--id", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--min-agree", type=int, default=3)
    ap.add_argument("--jsonl", type=str, default=JSONL_PATH)
    ap.add_argument("--fresh", action="store_true", help="Nadpisz JSONL na start")
    args = ap.parse_args()

    models = get_consensus_models(n=5)
    if len(models) < 5:
        log(f"Uwaga: tylko {len(models)} modeli skonfigurowanych")

    conn = get_connection()
    pending = count_pending(conn)
    log(f"\n=== consensus_pending {datetime.now().isoformat()} ===")
    log(f"Pending kwalifikujących się: {pending}")
    log(f"Modele ({len(models)}): {', '.join(models)}")
    log(f"Regula: >={args.min_agree}/{len(models)} zgodnych z baza -> OK")

    if args.fresh and os.path.isfile(args.jsonl):
        os.remove(args.jsonl)

    rows = fetch_pending(
        conn, limit=args.limit, offset=args.offset, question_id=args.id
    )
    log(f"Przetwarzam {len(rows)} rekordów (dry_run={args.dry_run})")

    stats = {}
    for i, row in enumerate(rows, 1):
        action, detail = process_one(
            row, conn, models, args.dry_run, args.min_agree, args.jsonl
        )
        stats[action] = stats.get(action, 0) + 1
        log(f"[{i}/{len(rows)}] id={row['id']} {action} {detail[:70]}")

    log("\n--- Podsumowanie ---")
    for k in sorted(stats.keys()):
        log(f"  {k}: {stats[k]}")
    if args.dry_run:
        log("(dry-run — bez UPDATE bazy)")
    elif stats.get("AUTO_OK"):
        log(f"Zapisano OK: {stats['AUTO_OK']}")
    log(f"JSONL: {args.jsonl}")
    conn.close()


if __name__ == "__main__":
    main()
