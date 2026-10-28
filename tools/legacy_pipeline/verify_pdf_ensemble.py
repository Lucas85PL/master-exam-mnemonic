"""
Ensemble PDF na kolejce audytu (audit_review_queue.csv):
multipage pdfplumber + opcjonalnie parse tabeli + fuzzy opcji vs baza.
Bez API. AUTO_OK (--apply-ok) tylko dla ENSEMBLE_OK.
"""
import argparse
import csv
import json
import os
import sys
from datetime import date, datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from audit_decision import normalize_letter, skip_reason
from audit_report import print_summary, write_jsonl
from audit_scope import (
    AUDIT_ROW_FIELDS,
    count_pending_audit,
    fetch_pending_audit,
    resolve_pdf_path,
)
from ensemble_decision import (
    FUZZY_THRESHOLD,
    QUEUE_PRIORITY,
    count_db_options,
    decide_ensemble_tier,
)
from init_db import get_connection
from parser_pdf_plumber import find_question_page, parse_question_from_table
from pdf_cross_page import parse_question_multipage

try:
    from rapidfuzz import fuzz

    def option_similarity(a, b):
        if not a or not b:
            return 0
        return fuzz.ratio(str(a).strip(), str(b).strip())

except ImportError:
    import difflib

    def option_similarity(a, b):
        if not a or not b:
            return 0
        return int(
            difflib.SequenceMatcher(None, str(a).strip(), str(b).strip()).ratio()
            * 100
        )


LOG_PATH = os.path.join(BASE_DIR, "ensemble_pdf.log")
JSONL_PATH = os.path.join(BASE_DIR, "ensemble_results.jsonl")
QUEUE_CSV = os.path.join(BASE_DIR, "audit_review_queue.csv")
ENSEMBLE_QUEUE_CSV = os.path.join(BASE_DIR, "ensemble_review_queue.csv")


def log(msg):
    print(msg)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def already_ensemble_ok(row):
    notes = row["review_notes"] if row["review_notes"] else ""
    return "ensemble_ok:" in str(notes)


def extract_pdf_parsed(row):
    path = resolve_pdf_path(row["zrodlo_pliku"])
    nr = row["nr_pytania"]
    if not path or not nr:
        return None, "no path or nr"

    db_opts = count_db_options(row)
    p_multi = parse_question_multipage(
        path, nr, row["pytanie"], db_option_count=db_opts
    )
    p_table = None
    pn, _fmt = find_question_page(path, nr)
    if pn is not None:
        p_table = parse_question_from_table(path, pn, nr)

    parsed = p_multi or p_table
    dual_note = ""
    if p_multi and p_table:
        lm = normalize_letter(p_multi.get("poprawna_odpowiedz"))
        lt = normalize_letter(p_table.get("poprawna_odpowiedz"))
        if lm and lt:
            dual_note = f" dual_agree={lm == lt}"
            if lm != lt and parsed is p_multi:
                dual_note += f" letter_multi={lm} table={lt}"
        if not lm and lt:
            parsed = p_table
    elif p_table and not p_multi:
        dual_note = " source=table_only"

    if not parsed:
        return None, "", "parse failed"

    return parsed, dual_note.strip(), None


def fuzzy_scores_for_row(row, parsed):
    scores = {}
    for letter in "ABCD":
        key = f"odp_{letter.lower()}"
        db_val = row[key]
        if db_val and str(db_val).strip():
            scores[letter] = option_similarity(db_val, parsed.get(key))
    return scores


def _make_record(row, audit_tier, tier, detail, **extra):
    rec = {
        "id": row["id"],
        "kategoria": row["kategoria"],
        "nr_pytania": row["nr_pytania"],
        "audit_tier": audit_tier,
        "tier": tier,
        "detail": detail,
        "pdf_letter": None,
        "db_letter": normalize_letter(row["poprawna_odpowiedz"]),
        "fuzzy_scores": {},
        "cross_page": False,
        "pdf_pages": None,
        "zrodlo_pliku": row["zrodlo_pliku"],
        "ts": datetime.now().isoformat(timespec="seconds"),
    }
    rec.update(extra)
    return rec


def process_row(row, audit_tier=None):
    sk_tier, sk_detail = skip_reason(row)
    if sk_tier:
        return _make_record(row, audit_tier, "ENSEMBLE_SKIP", sk_detail)

    if already_ensemble_ok(row):
        return _make_record(row, audit_tier, "ENSEMBLE_SKIP", "already ensemble_ok")

    parsed, dual_note, err = extract_pdf_parsed(row)
    if err and not parsed:
        return _make_record(row, audit_tier, "ENSEMBLE_NO_PDF", err)

    scores = fuzzy_scores_for_row(row, parsed) if parsed else {}
    tier, detail = decide_ensemble_tier(row, parsed, scores, option_similarity)
    if dual_note:
        detail = f"{detail}; {dual_note}"

    return _make_record(
        row,
        audit_tier,
        tier,
        detail,
        fuzzy_scores=scores,
        pdf_letter=normalize_letter(parsed.get("poprawna_odpowiedz")) if parsed else None,
        cross_page=parsed.get("cross_page") if parsed else False,
        pdf_pages=parsed.get("pages") if parsed else None,
    )


def mark_ensemble_ok(conn, question_id):
    note_suffix = f" | ensemble_ok:pdf+fuzzy:{date.today().isoformat()}"
    conn.execute(
        """UPDATE questions SET
            review_status = 'ok',
            review_notes = COALESCE(review_notes, '') || ?
        WHERE id = ?""",
        (note_suffix, question_id),
    )
    conn.commit()


def apply_ok_from_jsonl(conn, jsonl_path):
    if not os.path.isfile(jsonl_path):
        raise FileNotFoundError(jsonl_path)
    applied = skipped = 0
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("tier") != "ENSEMBLE_OK":
                continue
            qid = rec["id"]
            row = conn.execute(
                "SELECT review_notes FROM questions WHERE id = ?", (qid,)
            ).fetchone()
            if row and row["review_notes"] and "ensemble_ok:" in row["review_notes"]:
                skipped += 1
                continue
            mark_ensemble_ok(conn, qid)
            applied += 1
    return applied, skipped


def load_audit_queue_csv(csv_path, limit=None, offset=0, audit_tiers=None):
    """Wczytaj id + audit tier z audit_review_queue.csv."""
    items = []
    with open(csv_path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            tier = (r.get("tier") or "").strip()
            if audit_tiers and tier not in audit_tiers:
                continue
            items.append({"id": int(r["id"]), "audit_tier": tier})
    if offset:
        items = items[offset:]
    if limit is not None:
        items = items[:limit]
    return items


def fetch_rows_for_ids(conn, id_items):
    fields = " ".join(AUDIT_ROW_FIELDS.split())
    rows = []
    for item in id_items:
        row = conn.execute(
            f"SELECT {fields} FROM questions WHERE id = ?",
            (item["id"],),
        ).fetchone()
        if row:
            rows.append((row, item.get("audit_tier")))
    return rows


def write_ensemble_queue_csv(path, records):
    queue = [
        r
        for r in records
        if r["tier"].startswith("ENSEMBLE_REVIEW") or r["tier"] == "ENSEMBLE_NO_PDF"
    ]
    queue.sort(
        key=lambda r: (
            QUEUE_PRIORITY.get(r["tier"], 99),
            r.get("kategoria", ""),
            r.get("id", 0),
        )
    )
    fields = [
        "id",
        "kategoria",
        "nr_pytania",
        "audit_tier",
        "tier",
        "pdf_letter",
        "db_letter",
        "fuzzy_a",
        "fuzzy_b",
        "fuzzy_c",
        "fuzzy_d",
        "cross_page",
        "detail",
        "zrodlo_pliku",
    ]
    id_to_src = {}
    with open(QUEUE_CSV, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            id_to_src[int(r["id"])] = r.get("zrodlo_pliku", "")

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in queue:
            fs = r.get("fuzzy_scores") or {}
            w.writerow(
                {
                    "id": r.get("id"),
                    "kategoria": r.get("kategoria"),
                    "nr_pytania": r.get("nr_pytania"),
                    "audit_tier": r.get("audit_tier", ""),
                    "tier": r.get("tier"),
                    "pdf_letter": r.get("pdf_letter") or "",
                    "db_letter": r.get("db_letter") or "",
                    "fuzzy_a": fs.get("A", ""),
                    "fuzzy_b": fs.get("B", ""),
                    "fuzzy_c": fs.get("C", ""),
                    "fuzzy_d": fs.get("D", ""),
                    "cross_page": r.get("cross_page", ""),
                    "detail": r.get("detail", ""),
                    "zrodlo_pliku": r.get("zrodlo_pliku")
                    or id_to_src.get(r.get("id"), ""),
                }
            )
    return len(queue)


def main():
    ap = argparse.ArgumentParser(
        description="Ensemble PDF na kolejce audytu (bez API)"
    )
    ap.add_argument(
        "--from-db",
        action="store_true",
        help="Wszystkie pending z bazy (error/NULL, bez Anki, bez audit/ensemble ok)",
    )
    ap.add_argument(
        "--csv",
        type=str,
        default=None,
        help="audit_review_queue.csv (domyślnie przy braku --from-db)",
    )
    ap.add_argument(
        "--kategoria",
        type=str,
        default=None,
        help="Filtr: Dział pokładowy | Angielski | Kapitan żeglugi wielkiej",
    )
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument(
        "--audit-tier",
        action="append",
        dest="audit_tiers",
        help="Filtr tierów audytu, np. AUDIT_REVIEW_MISMATCH",
    )
    ap.add_argument("--jsonl", type=str, default=JSONL_PATH)
    ap.add_argument(
        "--queue-csv",
        type=str,
        default=ENSEMBLE_QUEUE_CSV,
        help="Eksport pozostałej kolejki ensemble",
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--apply-ok",
        action="store_true",
        help="Ustaw review_status=ok dla ENSEMBLE_OK",
    )
    ap.add_argument(
        "--apply-from-jsonl",
        action="store_true",
        help="Zastosuj ENSEMBLE_OK z ensemble_results.jsonl",
    )
    ap.add_argument("--id", type=int, action="append", dest="ids")
    ap.add_argument(
        "--fuzzy-threshold",
        type=int,
        default=FUZZY_THRESHOLD,
        help=f"Próg zgodności opcji (domyślnie {FUZZY_THRESHOLD})",
    )
    args = ap.parse_args()

    import ensemble_decision as ed

    ed.FUZZY_THRESHOLD = args.fuzzy_threshold

    log(f"\n=== ensemble {datetime.now().isoformat()} threshold={args.fuzzy_threshold} ===")

    conn = get_connection()

    if args.apply_from_jsonl:
        applied, skipped = apply_ok_from_jsonl(conn, args.jsonl)
        log(f"Zastosowano ensemble_ok: {applied} (pominięto: {skipped})")
        conn.close()
        return

    if args.ids:
        id_items = [{"id": i, "audit_tier": None} for i in args.ids]
        row_pairs = fetch_rows_for_ids(conn, id_items)
    elif args.from_db:
        total = count_pending_audit(conn, kategoria=args.kategoria)
        log(f"Pending z bazy (error/NULL, bez Anki): {total}")
        rows = fetch_pending_audit(
            conn,
            limit=args.limit,
            offset=args.offset,
            kategoria=args.kategoria,
        )
        row_pairs = [(r, None) for r in rows]
        log(f"Do przetworzenia: {len(row_pairs)} (limit={args.limit} offset={args.offset})")
    else:
        csv_path = args.csv or QUEUE_CSV
        if not os.path.isfile(csv_path):
            log(f"Brak pliku CSV: {csv_path} (użyj --from-db)")
            conn.close()
            return
        id_items = load_audit_queue_csv(
            csv_path,
            limit=args.limit,
            offset=args.offset,
            audit_tiers=args.audit_tiers,
        )
        log(f"Kolejka audytu: {len(id_items)} ID z {csv_path}")
        row_pairs = fetch_rows_for_ids(conn, id_items)
    log(f"Przetwarzam {len(row_pairs)} rekordów (dry_run={args.dry_run})")

    records = []
    stats = {}
    for i, (row, audit_tier) in enumerate(row_pairs, 1):
        rec = process_row(row, audit_tier=audit_tier)
        records.append(rec)
        stats[rec["tier"]] = stats.get(rec["tier"], 0) + 1
        if rec["tier"] == "ENSEMBLE_OK" and args.apply_ok and not args.dry_run:
            if not already_ensemble_ok(row):
                mark_ensemble_ok(conn, rec["id"])
        log(
            f"[{i}/{len(row_pairs)}] id={rec['id']} {rec['tier']} "
            f"pdf={rec.get('pdf_letter')} db={rec.get('db_letter')} "
            f"{str(rec.get('detail', ''))[:70]}"
        )

    write_jsonl(args.jsonl, records)
    n_q = write_ensemble_queue_csv(args.queue_csv, records)
    log(f"Zapisano {args.jsonl} ({len(records)} wierszy)")
    log(f"Kolejka ensemble CSV: {args.queue_csv} ({n_q} wierszy)")
    print_summary(records)

    if args.apply_ok and not args.dry_run:
        log(f"Zastosowano ensemble_ok: {stats.get('ENSEMBLE_OK', 0)}")

    conn.close()


if __name__ == "__main__":
    main()
