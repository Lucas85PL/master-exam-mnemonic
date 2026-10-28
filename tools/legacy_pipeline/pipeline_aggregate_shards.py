"""
Zbiera statystyki z pipeline_shard_summaries/*.json po rownoleglym runie.
"""
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from init_db import get_connection
from pipeline_scope import count_pending_consensus, count_pending_vision

SUMMARY_DIR = os.path.join(BASE_DIR, "pipeline_shard_summaries")
LOG_DIR = os.path.join(BASE_DIR, "pipeline_parallel_logs")


def parse_summary_from_log(log_path, header):
    """Czyta linie pod '--- Podsumowanie X ---'."""
    if not os.path.isfile(log_path):
        return {}
    stats = {}
    in_block = False
    with open(log_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if header in line:
                in_block = True
                continue
            if in_block:
                line = line.strip()
                if not line or line.startswith("Log:") or line.startswith("Podsumowanie"):
                    break
                if ":" in line:
                    k, v = line.split(":", 1)
                    stats[k.strip()] = int(v.strip())
    return stats


def load_shard_from_logs(shard):
    """vision_W1.log / vision_W1_retry.log + consensus_*"""
    vision = {}
    consensus = {}
    for suffix in ("", "_retry"):
        vpath = os.path.join(LOG_DIR, f"vision_{shard}{suffix}.log")
        cpath = os.path.join(LOG_DIR, f"consensus_{shard}{suffix}.log")
        if not vision:
            vision = parse_summary_from_log(vpath, "Podsumowanie Vision")
        else:
            v2 = parse_summary_from_log(vpath, "Podsumowanie Vision")
            for k, n in v2.items():
                vision[k] = vision.get(k, 0) + n
        c2 = parse_summary_from_log(cpath, "Podsumowanie konsensus")
        for k, n in c2.items():
            consensus[k] = consensus.get(k, 0) + n
    return vision, consensus


def sum_stats(dicts):
    total = {}
    for d in dicts:
        for k, v in (d or {}).items():
            total[k] = total.get(k, 0) + int(v)
    return total


def main():
    shards = []
    if os.path.isdir(SUMMARY_DIR):
        for name in sorted(os.listdir(SUMMARY_DIR)):
            if not name.endswith(".json"):
                continue
            path = os.path.join(SUMMARY_DIR, name)
            with open(path, encoding="utf-8") as f:
                shards.append(json.load(f))

    print("=" * 60)
    print("PODSUMOWANIE SHARDOW (pipeline PDF)")
    print("=" * 60)

    shard_names = sorted({s.get("shard") for s in shards if s.get("shard")})
    if not shard_names:
        shard_names = ["W1", "W2", "W3", "W4", "W5"]

    all_vision = []
    all_consensus = []

    for name in shard_names:
        s = next((x for x in shards if x.get("shard") == name), {})
        off = s.get("offset", "?")
        lim = s.get("limit", "?")
        v = s.get("vision") or {}
        c = s.get("consensus") or {}
        if not v or not c:
            lv, lc = load_shard_from_logs(name)
            if not v:
                v = lv
            if not c:
                c = lc
        all_vision.append(v)
        all_consensus.append(c)
        print(f"\n--- {name} (offset={off}, limit={lim}) ---")
        print("  Vision:")
        for k in sorted(v.keys()):
            print(f"    {k}: {v[k]}")
        print("  Konsensus:")
        for k in sorted(c.keys()):
            print(f"    {k}: {c[k]}")

    tv = sum_stats(all_vision)
    tc = sum_stats(all_consensus)

    print("\n" + "=" * 60)
    print("RAZEM (wszystkie shardy)")
    print("=" * 60)
    print("Vision:")
    for k in sorted(tv.keys()):
        print(f"  {k}: {tv[k]}")
    print("Konsensus:")
    for k in sorted(tc.keys()):
        print(f"  {k}: {tc[k]}")

    conn = get_connection()
    print("\nStan bazy po runie:")
    print(f"  pending_vision:    {count_pending_vision(conn)}")
    print(f"  pending_consensus: {count_pending_consensus(conn)}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
