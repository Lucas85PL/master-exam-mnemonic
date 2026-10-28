"""
Orchestrator: Vision full-page → konsensus 3 modeli (Dział pokładowy + Angielski).
"""
import argparse
import json
import os
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv

load_dotenv(os.path.join(BASE_DIR, ".env"))

from init_db import get_connection
from pipeline_scope import count_pending_consensus, count_pending_vision
from vision_pdf import run_vision
from pdf_consensus import run_consensus

SUMMARY_DIR = os.path.join(BASE_DIR, "pipeline_shard_summaries")


def save_shard_summary(shard, phase_stats, offset, limit):
    os.makedirs(SUMMARY_DIR, exist_ok=True)
    path = os.path.join(SUMMARY_DIR, f"{shard}.json")
    data = {
        "shard": shard,
        "offset": offset,
        "limit": limit,
        "finished_at": datetime.now().isoformat(),
        "vision": phase_stats.get("vision", {}),
        "consensus": phase_stats.get("consensus", {}),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline PDF: Vision → konsensus (Dział + Angielski)"
    )
    parser.add_argument(
        "--phase",
        choices=("vision", "consensus", "all"),
        default="all",
        help="Faza pipeline (domyślnie: all)",
    )
    parser.add_argument("--limit", type=int)
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--shard", help="Etykieta sharda (np. W1) — osobne logi")
    parser.add_argument("--id", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--rescan",
        action="store_true",
        help="Vision: ponów pytania z vision_page",
    )
    parser.add_argument("--cache-dir", help="Folder cache Vision")
    args = parser.parse_args()

    conn = get_connection()
    n_vis = count_pending_vision(conn, rescan=args.rescan)
    n_con = count_pending_consensus(conn)
    conn.close()

    shard_lbl = f" [{args.shard}]" if args.shard else ""
    print(f"Zakres: Dział pokładowy + angielski (bez Anki, bez Kapitan){shard_lbl}")
    print(f"  Pending Vision:    ~{n_vis}")
    print(f"  Pending konsensus: ~{n_con}")
    if args.offset:
        print(f"  Offset: {args.offset}")
    if args.limit:
        print(f"  Limit:  {args.limit}")
    print(f"  Faza: {args.phase}")
    if args.dry_run:
        print("  (dry-run)")

    code = 0
    phase_stats = {}

    if args.phase in ("vision", "all"):
        print("\n========== FAZA 1: VISION ==========")
        v_stats, code = run_vision(
            limit=args.limit,
            offset=args.offset,
            question_id=args.id,
            dry_run=args.dry_run,
            rescan=args.rescan,
            cache_dir=args.cache_dir,
            shard=args.shard,
        )
        phase_stats["vision"] = v_stats
        if code != 0 and args.phase == "all":
            print("Vision zakończone z błędami — kontynuuję konsensus.")

    if args.phase in ("consensus", "all"):
        print("\n========== FAZA 2: KONSENSUS ==========")
        c_stats, c2 = run_consensus(
            limit=args.limit,
            offset=args.offset,
            question_id=args.id,
            dry_run=args.dry_run,
            shard=args.shard,
        )
        phase_stats["consensus"] = c_stats
        if c2 != 0:
            code = c2

    if args.shard and phase_stats:
        path = os.path.join(SUMMARY_DIR, f"{args.shard}.json")
        existing = {}
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                existing = json.load(f)
        merged = {
            "shard": args.shard,
            "offset": args.offset,
            "limit": args.limit,
            "finished_at": datetime.now().isoformat(),
            "vision": phase_stats.get("vision") or existing.get("vision") or {},
            "consensus": phase_stats.get("consensus") or existing.get("consensus") or {},
        }
        os.makedirs(SUMMARY_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
        print(f"\nPodsumowanie sharda zapisane: {path}")

    return code


if __name__ == "__main__":
    sys.exit(main())
