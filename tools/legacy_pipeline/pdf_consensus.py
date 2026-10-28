"""
CLI: konsensus 3 modeli → auto OK dla Dział pokładowy + Angielski (po vision_page).
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
from openrouter_consensus import ask_all_models, evaluate_consensus, get_consensus_models
from pipeline_scope import count_pending_consensus, fetch_pending_consensus

LOG_PATH = os.path.join(BASE_DIR, "pdf_consensus.log")
JSONL_PATH = os.path.join(BASE_DIR, "pdf_consensus_results.jsonl")
_log_path = LOG_PATH
_jsonl_path = JSONL_PATH


def configure_shard(shard=None):
    global _log_path, _jsonl_path
    if shard:
        _log_path = os.path.join(BASE_DIR, f"pdf_consensus_{shard}.log")
        _jsonl_path = os.path.join(BASE_DIR, f"pdf_consensus_results_{shard}.jsonl")
    else:
        _log_path = LOG_PATH
        _jsonl_path = JSONL_PATH


def log(msg):
    print(msg)
    with open(_log_path, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def append_jsonl(record):
    with open(_jsonl_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def skip_reason(row):
    if (row["typ_pytania"] or "").strip().lower() != "testowe":
        return "not testowe"
    letter = (row["poprawna_odpowiedz"] or "").strip().upper()
    if letter not in ("A", "B", "C", "D"):
        return "no poprawna_odpowiedz in db"
    opts = sum(
        1
        for k in ("odp_a", "odp_b", "odp_c", "odp_d")
        if row[k] and str(row[k]).strip()
    )
    if opts < 2:
        return "fewer than 2 options"
    if not (row["pytanie"] or "").strip():
        return "empty pytanie"
    return None


def mark_ok(conn, question_id, models_tag):
    note_suffix = f" | consensus_ok:{models_tag}:{date.today().isoformat()}"
    conn.execute(
        """UPDATE questions SET
            review_status = 'ok',
            review_notes = COALESCE(review_notes, '') || ?
        WHERE id = ?""",
        (note_suffix, question_id),
    )
    conn.commit()


def process_one(row, conn, dry_run):
    qid = row["id"]
    reason = skip_reason(row)
    if reason:
        rec = {"id": qid, "action": "SKIP", "detail": reason}
        append_jsonl(rec)
        return "SKIP", reason

    try:
        votes = ask_all_models(
            row["pytanie"],
            row["odp_a"],
            row["odp_b"],
            row["odp_c"],
            row["odp_d"],
        )
    except Exception as e:
        rec = {"id": qid, "action": "API_FAIL", "error": str(e)}
        append_jsonl(rec)
        return "API_FAIL", str(e)[:100]

    action, consensus, detail = evaluate_consensus(votes, row["poprawna_odpowiedz"])
    vote_letters = [v.get("letter") for v in votes]
    rec = {
        "id": qid,
        "action": action,
        "votes": {v["model"]: v.get("letter") for v in votes},
        "consensus": consensus,
        "db": row["poprawna_odpowiedz"],
        "detail": detail,
    }
    append_jsonl(rec)

    if action == "AUTO_OK":
        if not dry_run:
            models_tag = "+".join(
                m.split("/")[-1][:12] for m in get_consensus_models()
            )
            mark_ok(conn, qid, models_tag)
        return "AUTO_OK", f"{vote_letters} == db {row['poprawna_odpowiedz']}"

    return action, f"{vote_letters} db={row['poprawna_odpowiedz']} ({detail})"


def run_consensus(
    limit=None, question_id=None, dry_run=False, offset=0, shard=None
):
    configure_shard(shard)
    if os.path.exists(_jsonl_path):
        os.remove(_jsonl_path)

    conn = get_connection()
    pending = count_pending_consensus(conn)
    rows = fetch_pending_consensus(
        conn, question_id=question_id, limit=limit, offset=offset
    )

    if not rows:
        print(f"Brak pytań do konsensusu (pending ~{pending}).")
        conn.close()
        return {}, 0

    models = get_consensus_models()
    print(f"Pending konsensus (SQL): ~{pending}")
    print(f"Modele: {', '.join(models)}")
    print(f"Do przetworzenia: {len(rows)} pytań")
    if dry_run:
        print("(dry-run — bez UPDATE bazy)")

    log(f"\n=== pdf_consensus {datetime.now().isoformat()} dry_run={dry_run} ===")

    stats = {}
    for i, row in enumerate(rows, 1):
        status, detail = process_one(row, conn, dry_run)
        stats[status] = stats.get(status, 0) + 1
        line = f"[{i}/{len(rows)}] ID={row['id']} {status}"
        if detail:
            line += f" {detail}"
        log(line)

    print("\n--- Podsumowanie konsensus ---")
    for k in sorted(stats.keys()):
        print(f"  {k}: {stats[k]}")
    print(f"Log: {_log_path}")
    print(f"JSONL: {_jsonl_path}")
    conn.close()
    return stats, 0


def main():
    parser = argparse.ArgumentParser(
        description="Konsensus 3 modeli → auto OK (Dział + Angielski)"
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--id", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    _, code = run_consensus(
        limit=args.limit, question_id=args.id, dry_run=args.dry_run
    )
    return code


if __name__ == "__main__":
    sys.exit(main())
