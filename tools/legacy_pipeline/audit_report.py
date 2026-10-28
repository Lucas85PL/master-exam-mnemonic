"""
Eksport raportów audytu: JSONL, CSV kolejki review, podsumowanie per kategoria.
"""
import csv
import json
import os
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

from audit_decision import QUEUE_PRIORITY


def write_jsonl(path, records):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def write_review_queue_csv(path, records):
    """Tylko rekordy wymagające review (nie AUDIT_OK / AUDIT_SKIP)."""
    queue = [
        r
        for r in records
        if r["tier"].startswith("AUDIT_REVIEW") or r["tier"] == "AUDIT_STRUCT"
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
        "tier",
        "pdf_letter",
        "db_letter",
        "vote_a",
        "vote_b",
        "vote_c",
        "detail",
        "zrodlo_pliku",
    ]
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in queue:
            vl = r.get("vote_letters") or []
            votes = r.get("votes") or {}
            row = {
                "id": r.get("id"),
                "kategoria": r.get("kategoria"),
                "nr_pytania": r.get("nr_pytania"),
                "tier": r.get("tier"),
                "pdf_letter": r.get("pdf_letter") or "",
                "db_letter": r.get("db_letter") or "",
                "vote_a": vl[0] if len(vl) > 0 else votes.get("model_1", ""),
                "vote_b": vl[1] if len(vl) > 1 else votes.get("model_2", ""),
                "vote_c": vl[2] if len(vl) > 2 else votes.get("model_3", ""),
                "detail": r.get("detail", ""),
                "zrodlo_pliku": r.get("zrodlo_pliku", ""),
            }
            w.writerow(row)
    return len(queue)


def print_summary(records):
    by_tier = defaultdict(int)
    by_kat_tier = defaultdict(lambda: defaultdict(int))

    for r in records:
        by_tier[r["tier"]] += 1
        by_kat_tier[r.get("kategoria", "?")][r["tier"]] += 1

    print("\n--- Podsumowanie audytu (tier) ---")
    for tier in sorted(by_tier.keys()):
        print(f"  {tier}: {by_tier[tier]}")

    print("\n--- Per kategoria ---")
    for kat in sorted(by_kat_tier.keys()):
        parts = ", ".join(f"{t}={by_kat_tier[kat][t]}" for t in sorted(by_kat_tier[kat]))
        print(f"  {kat}: {parts}")

    return dict(by_tier), {k: dict(v) for k, v in by_kat_tier.items()}
