"""
Audyt PDF: pdfplumber (ground truth) + konsensus 3 modeli + litera w bazie.
AUTO_OK tylko przy PDF == DB == 3/3 oraz brak HIGH strukturalnych.
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
from openrouter_consensus import ask_all_models, get_consensus_models
from pdf_cross_page import parse_question_multipage

from audit_decision import (
    decide_tier,
    normalize_letter,
    skip_reason,
    structural_issues,
)
from audit_report import print_summary, write_jsonl, write_review_queue_csv
from audit_scope import count_pending_audit, fetch_pending_audit, resolve_pdf_path

LOG_PATH = os.path.join(BASE_DIR, "audit_pdf.log")
JSONL_PATH = os.path.join(BASE_DIR, "audit_results.jsonl")
QUEUE_CSV = os.path.join(BASE_DIR, "audit_review_queue.csv")


def log(msg):
    print(msg)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def extract_pdf_parsed(row):
    path = resolve_pdf_path(row["zrodlo_pliku"])
    nr = row["nr_pytania"]
    if not path:
        return None, "no pdf path"
    if not nr:
        return None, "no nr_pytania"
    db_opts = sum(
        1
        for k in ("odp_a", "odp_b", "odp_c", "odp_d")
        if row[k] and str(row[k]).strip()
    )
    parsed = parse_question_multipage(
        path, nr, row["pytanie"], db_option_count=db_opts
    )
    if not parsed:
        return None, "table parse failed"
    return parsed, None


def extract_pdf_letter(row):
    parsed, err = extract_pdf_parsed(row)
    if err:
        return None, err
    return normalize_letter(parsed.get("poprawna_odpowiedz")), None


def mark_audit_ok(conn, question_id):
    note_suffix = f" | audit_ok:pdf+consensus:{date.today().isoformat()}"
    conn.execute(
        """UPDATE questions SET
            review_status = 'ok',
            review_notes = COALESCE(review_notes, '') || ?
        WHERE id = ?""",
        (note_suffix, question_id),
    )
    conn.commit()


def process_one(row, conn, dry_run, apply_ok, skip_consensus_on_no_pdf=True):
    qid = row["id"]
    db_letter = normalize_letter(row["poprawna_odpowiedz"])

    sk_tier, sk_detail = skip_reason(row)
    if sk_tier:
        return {
            "id": qid,
            "kategoria": row["kategoria"],
            "nr_pytania": row["nr_pytania"],
            "tier": sk_tier,
            "detail": sk_detail,
            "pdf_letter": None,
            "db_letter": db_letter,
            "votes": None,
            "zrodlo_pliku": row["zrodlo_pliku"],
        }

    struct = structural_issues(row)
    if struct:
        return {
            "id": qid,
            "kategoria": row["kategoria"],
            "nr_pytania": row["nr_pytania"],
            "tier": "AUDIT_STRUCT",
            "detail": "; ".join(struct),
            "pdf_letter": None,
            "db_letter": db_letter,
            "votes": None,
            "zrodlo_pliku": row["zrodlo_pliku"],
        }

    parsed_pdf, pdf_err = extract_pdf_parsed(row)
    pdf_letter = normalize_letter(parsed_pdf.get("poprawna_odpowiedz")) if parsed_pdf else None
    votes = None

    if pdf_letter is None:
        if skip_consensus_on_no_pdf:
            return {
                "id": qid,
                "kategoria": row["kategoria"],
                "nr_pytania": row["nr_pytania"],
                "tier": "AUDIT_REVIEW_NO_PDF",
                "detail": pdf_err or "no pdf letter",
                "pdf_letter": None,
                "db_letter": db_letter,
                "votes": None,
                "zrodlo_pliku": row["zrodlo_pliku"],
            }

    if votes is None:
        try:
            votes = ask_all_models(
                row["pytanie"],
                row["odp_a"],
                row["odp_b"],
                row["odp_c"],
                row["odp_d"],
            )
        except Exception as e:
            return {
                "id": qid,
                "kategoria": row["kategoria"],
                "nr_pytania": row["nr_pytania"],
                "tier": "AUDIT_REVIEW_NO_CONSENSUS",
                "detail": f"API_FAIL: {e}",
                "pdf_letter": pdf_letter,
                "db_letter": db_letter,
                "votes": None,
                "zrodlo_pliku": row["zrodlo_pliku"],
            }

    tier, detail, vote_letters, _consensus = decide_tier(
        pdf_letter, db_letter, votes, []
    )

    vote_map = None
    if votes:
        models = get_consensus_models()
        vote_map = {}
        for i, v in enumerate(votes):
            key = f"model_{i + 1}"
            vote_map[key] = v.get("letter")
            vote_map[v.get("model", models[i] if i < len(models) else key)] = v.get(
                "letter"
            )

    rec = {
        "id": qid,
        "kategoria": row["kategoria"],
        "nr_pytania": row["nr_pytania"],
        "tier": tier,
        "detail": detail,
        "pdf_letter": pdf_letter,
        "db_letter": db_letter,
        "votes": vote_map,
        "vote_letters": vote_letters,
        "zrodlo_pliku": row["zrodlo_pliku"],
        "cross_page": parsed_pdf.get("cross_page") if parsed_pdf else False,
        "pdf_pages": parsed_pdf.get("pages") if parsed_pdf else None,
        "ts": datetime.now().isoformat(timespec="seconds"),
    }

    if tier == "AUDIT_OK" and apply_ok and not dry_run:
        mark_audit_ok(conn, qid)

    return rec


def apply_ok_from_jsonl(conn, jsonl_path):
    """Zapisuje review_status=ok dla AUDIT_OK z wcześniejszego audit_results.jsonl."""
    if not os.path.isfile(jsonl_path):
        raise FileNotFoundError(jsonl_path)
    applied = 0
    skipped = 0
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("tier") != "AUDIT_OK":
                continue
            qid = rec["id"]
            row = conn.execute(
                "SELECT review_notes FROM questions WHERE id = ?", (qid,)
            ).fetchone()
            if row and row["review_notes"] and "audit_ok:" in row["review_notes"]:
                skipped += 1
                continue
            mark_audit_ok(conn, qid)
            applied += 1
    return applied, skipped


def compare_with_consensus_log(records, consensus_jsonl=None):
    """Porównanie tierów z historycznym pdf_consensus_results.jsonl."""
    path = consensus_jsonl or os.path.join(BASE_DIR, "pdf_consensus_results.jsonl")
    if not os.path.isfile(path):
        log(f"Brak pliku do porównania: {path}")
        return

    hist = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
                hist[o["id"]] = o.get("action")
            except json.JSONDecodeError:
                continue

    overlap = [r for r in records if r["id"] in hist]
    if not overlap:
        log("Brak wspólnych ID z pdf_consensus_results.jsonl")
        return

    cross = {}
    for r in overlap:
        key = (hist[r["id"]], r["tier"])
        cross[key] = cross.get(key, 0) + 1

    log(f"\n--- Porównanie z {path} ({len(overlap)} ID) ---")
    for (old, new), cnt in sorted(cross.items(), key=lambda x: -x[1]):
        log(f"  consensus {old} -> audit {new}: {cnt}")


def main():
    ap = argparse.ArgumentParser(description="Audyt PDF + triage (conservative)")
    ap.add_argument("--dry-run", action="store_true", help="Bez zapisu do bazy")
    ap.add_argument(
        "--apply-ok",
        action="store_true",
        help="Ustaw review_status=ok tylko dla AUDIT_OK (w trakcie batcha)",
    )
    ap.add_argument(
        "--apply-from-jsonl",
        action="store_true",
        help="Zapisz AUDIT_OK z istniejącego audit_results.jsonl (bez ponownego audytu)",
    )
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--id", type=int, default=None, dest="question_id")
    ap.add_argument(
        "--kategoria",
        type=str,
        default=None,
        help="Filtr: Dział pokładowy | Angielski | Kapitan żeglugi wielkiej",
    )
    ap.add_argument(
        "--consensus-on-no-pdf",
        action="store_true",
        help="Wywołaj modele nawet gdy plumber nie znalazł litery",
    )
    ap.add_argument(
        "--compare-consensus",
        action="store_true",
        help="Porównaj z pdf_consensus_results.jsonl po batchu",
    )
    ap.add_argument(
        "--jsonl",
        type=str,
        default=JSONL_PATH,
        help="Ścieżka wyników JSONL",
    )
    ap.add_argument(
        "--queue-csv",
        type=str,
        default=QUEUE_CSV,
        help="Eksport kolejki review CSV",
    )
    args = ap.parse_args()

    if args.apply_ok and args.dry_run:
        print("Uwaga: --apply-ok ignorowane przy --dry-run")

    conn = get_connection()

    if args.apply_from_jsonl:
        applied, skipped = apply_ok_from_jsonl(conn, args.jsonl)
        log(f"Zastosowano audit_ok: {applied} (pominięto już oznaczone: {skipped})")
        pending = count_pending_audit(conn, kategoria=args.kategoria)
        log(f"Pending audit po zapisie: {pending}")
        return

    pending = count_pending_audit(conn, kategoria=args.kategoria)
    log(f"Pending audit (bez audit_ok): {pending}")
    log(f"Modele: {get_consensus_models()}")

    rows = fetch_pending_audit(
        conn,
        question_id=args.question_id,
        limit=args.limit,
        offset=args.offset,
        kategoria=args.kategoria,
    )
    log(f"Przetwarzam {len(rows)} rekordów (dry_run={args.dry_run})")

    records = []
    stats = {}
    for i, row in enumerate(rows, 1):
        rec = process_one(
            row,
            conn,
            dry_run=args.dry_run,
            apply_ok=args.apply_ok,
            skip_consensus_on_no_pdf=not args.consensus_on_no_pdf,
        )
        records.append(rec)
        stats[rec["tier"]] = stats.get(rec["tier"], 0) + 1
        log(
            f"[{i}/{len(rows)}] id={rec['id']} {rec['tier']} "
            f"pdf={rec.get('pdf_letter')} db={rec.get('db_letter')} "
            f"{rec.get('detail', '')[:80]}"
        )

    write_jsonl(args.jsonl, records)
    n_queue = write_review_queue_csv(args.queue_csv, records)
    log(f"Zapisano {args.jsonl} ({len(records)} wierszy)")
    log(f"Kolejka review CSV: {args.queue_csv} ({n_queue} wierszy)")

    print_summary(records)

    if args.compare_consensus:
        compare_with_consensus_log(records)

    if args.apply_ok and not args.dry_run:
        ok_n = stats.get("AUDIT_OK", 0)
        log(f"Zastosowano review_status=ok dla {ok_n} rekordów (AUDIT_OK)")


if __name__ == "__main__":
    main()
