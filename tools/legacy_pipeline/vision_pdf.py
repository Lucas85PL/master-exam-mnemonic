"""
CLI: Vision full-page dla Dział pokładowy + Angielski (format1/format2).
"""
import argparse
import json
import os
import sys
from datetime import date, datetime

import fitz

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv

load_dotenv(os.path.join(BASE_DIR, ".env"))

from init_db import get_connection
from parser_pdf_plumber import find_question_page, vision_format_tag
from pdf_crop import clean_for_search
from pdf_page import (
    locate_question_page,
    needs_two_pages,
    render_pages_at_nums,
    render_pages_for_question,
    save_question_page_audit,
)
from openrouter_vision import extract_question_from_pages, validate_parsed
from pipeline_scope import count_pending_vision, fetch_pending_vision, skip_if_no_pdf

CACHE_ROOT = os.path.join(BASE_DIR, "vision_cache")
LOG_PATH = os.path.join(BASE_DIR, "vision_pdf.log")
_log_path = LOG_PATH


def configure_shard(shard=None):
    global _log_path
    if shard:
        _log_path = os.path.join(BASE_DIR, f"vision_pdf_{shard}.log")
    else:
        _log_path = LOG_PATH


def log(msg):
    print(msg)
    with open(_log_path, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def make_scan_cache_dir(shard=None):
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    tag = f"pdf_{shard}_{stamp}" if shard else f"pdf_{stamp}"
    path = os.path.join(CACHE_ROOT, tag)
    os.makedirs(path, exist_ok=True)
    return path


def resolve_pdf_path(zrodlo_pliku):
    if not zrodlo_pliku:
        return None
    if os.path.isfile(zrodlo_pliku):
        return zrodlo_pliku
    alt = os.path.join(BASE_DIR, zrodlo_pliku)
    if os.path.isfile(alt):
        return alt
    return None


def find_page_by_text(filepath, pytanie):
    search_text = clean_for_search(pytanie or "")
    if len(search_text) < 5:
        return None
    doc = fitz.open(filepath)
    try:
        for pn in range(len(doc)):
            page = doc[pn]
            for fragment in [search_text[:80], search_text[:50], search_text[:30]]:
                if len(fragment) < 5:
                    continue
                if page.search_for(fragment):
                    return pn
        return None
    finally:
        doc.close()


def render_for_row(row, cache_dir, page_cache):
    path = resolve_pdf_path(row["zrodlo_pliku"])
    nr = row["nr_pytania"]
    pytanie = row["pytanie"]
    pdf_format = "format1"
    page_nums = None

    if nr is not None:
        page_num, table_fmt = find_question_page(path, nr)
        if page_num is not None:
            pdf_format = vision_format_tag(table_fmt)
            page_nums = [page_num]
            doc = fitz.open(path)
            try:
                _, anchor_y0, all_qnums = locate_question_page(
                    doc, nr, pytanie
                )
                if anchor_y0 is None:
                    anchor_y0 = doc[page_num].rect.height * 0.5
                if needs_two_pages(doc, page_num, anchor_y0, nr, all_qnums):
                    if page_num + 1 < len(doc):
                        page_nums.append(page_num + 1)
            finally:
                doc.close()

    if page_nums is None:
        pngs, tag, warn, page_nums = render_pages_for_question(
            path,
            nr_pytania=nr,
            pytanie=pytanie,
            cache_dir=cache_dir,
            page_cache=page_cache,
        )
        if pngs:
            return pngs, tag, warn, page_nums, "format2"
        text_page = find_page_by_text(path, pytanie)
        if text_page is not None:
            page_nums = [text_page]
            pdf_format = "format1"
        else:
            return None, "", warn or "page render failed", [], pdf_format

    pngs, tag, warn, page_nums = render_pages_at_nums(
        path, page_nums, cache_dir=cache_dir, page_cache=page_cache
    )
    return pngs, tag, warn, page_nums, pdf_format


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
    reason = skip_if_no_pdf(row)
    if reason:
        return "SKIP", reason

    try:
        pngs, tag, warn, page_nums, pdf_format = render_for_row(
            row, cache_dir, page_cache
        )
    except Exception as e:
        return "FAIL", str(e)[:120]

    if not pngs:
        return "FAIL", warn or "page render failed"

    save_question_page_audit(cache_dir, qid, pngs, tag)
    pages_label = (
        f"pages={page_nums[0]}"
        if len(page_nums) == 1
        else f"pages={page_nums[0]}-{page_nums[-1]}"
    )
    tag_label = f"[{tag}] {pdf_format} {pages_label}"
    if warn:
        tag_label += f" ({warn})"

    if dry_run:
        return "DRY", tag_label

    try:
        raw = extract_question_from_pages(
            pngs,
            nr_pytania=row["nr_pytania"],
            pytanie_hint=row["pytanie"],
            pdf_format=pdf_format,
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


def run_vision(
    limit=None,
    question_id=None,
    dry_run=False,
    rescan=False,
    cache_dir=None,
    offset=0,
    shard=None,
):
    configure_shard(shard)
    cache_dir = cache_dir or make_scan_cache_dir(shard)
    conn = get_connection()
    pending = count_pending_vision(conn, rescan=rescan)
    rows = fetch_pending_vision(
        conn,
        question_id=question_id,
        limit=limit,
        offset=offset,
        rescan=rescan,
    )

    if not rows:
        print(f"Brak pytań w zakresie (pending SQL ~{pending}).")
        conn.close()
        return {}, 0

    shard_lbl = f" shard={shard}" if shard else ""
    print(f"Pending w zakresie (SQL): ~{pending}{shard_lbl}")
    if offset:
        print(f"Offset: {offset}")
    print(f"Do przetworzenia: {len(rows)} pytań (Dział + Angielski)")
    print(f"Cache: {cache_dir}")
    if dry_run:
        print("(dry-run — bez API i bez zapisu do bazy)")

    log(f"\n=== vision_pdf {datetime.now().isoformat()} cache={cache_dir} rescan={rescan} ===")

    page_cache = {}
    stats = {}
    for i, row in enumerate(rows, 1):
        status, detail = process_one(row, conn, cache_dir, page_cache, dry_run)
        stats[status] = stats.get(status, 0) + 1
        line = f"[{i}/{len(rows)}] ID={row['id']} {status}"
        if detail:
            line += f" {detail}"
        log(line)

    print("\n--- Podsumowanie Vision ---")
    for k, v in sorted(stats.items()):
        print(f"  {k}: {v}")
    print(f"Log: {_log_path}")
    conn.close()
    return stats, 0 if stats.get("FAIL", 0) == 0 else 1


def main():
    parser = argparse.ArgumentParser(
        description="Vision full-page — Dział pokładowy + Angielski"
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--id", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--rescan", action="store_true")
    parser.add_argument("--cache-dir")
    args = parser.parse_args()
    _, code = run_vision(
        limit=args.limit,
        question_id=args.id,
        dry_run=args.dry_run,
        rescan=args.rescan,
        cache_dir=args.cache_dir,
    )
    return code


if __name__ == "__main__":
    sys.exit(main())
