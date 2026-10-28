"""
Usuwa z bazy rekordy pending (error / nieoznaczone, bez Anki):
1) duplikaty pełnych pytań (to samo pytanie + źródło) — zostaw najniższe ID
2) niepełne: brak treści pytania lub puste A,B,C
"""
import argparse
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from init_db import get_connection

PENDING = "(review_status IS NULL OR review_status = '' OR review_status = 'error')"
NOT_ANKI = """(
    kategoria != 'Chief Officer'
    AND (zrodlo_pliku IS NULL OR zrodlo_pliku NOT LIKE '%colpkg%')
)"""

FULL_RECORD = """
    trim(coalesce(pytanie, '')) != ''
    AND trim(coalesce(odp_a, '')) != ''
    AND trim(coalesce(poprawna_odpowiedz, '')) != ''
    AND upper(trim(poprawna_odpowiedz)) IN ('A', 'B', 'C', 'D')
"""

INCOMPLETE = """
    trim(coalesce(pytanie, '')) = ''
    OR (
        trim(coalesce(odp_a, '')) = ''
        AND trim(coalesce(odp_b, '')) = ''
        AND trim(coalesce(odp_c, '')) = ''
    )
"""


def pending_where():
    return f"WHERE {PENDING} AND {NOT_ANKI}"


def find_incomplete_ids(conn):
    sql = f"""
        SELECT id, kategoria, nr_pytania, substr(pytanie, 1, 80) AS pyt
        FROM questions
        {pending_where()}
          AND ({INCOMPLETE})
        ORDER BY id
    """
    return conn.execute(sql).fetchall()


def find_duplicate_ids_to_delete(conn):
    """Z grup duplikatów pełnych rekordów usuń wszystkie oprócz min(id)."""
    sql = f"""
        SELECT lower(trim(pytanie)) AS qkey, zrodlo_pliku,
               GROUP_CONCAT(id ORDER BY id) AS ids
        FROM questions
        {pending_where()}
          AND ({FULL_RECORD})
        GROUP BY qkey, zrodlo_pliku
        HAVING COUNT(*) > 1
    """
    to_delete = []
    groups = 0
    for row in conn.execute(sql):
        ids = [int(x) for x in row["ids"].split(",")]
        groups += 1
        keep = ids[0]
        for qid in ids[1:]:
            to_delete.append((qid, keep, row["qkey"][:60] if row["qkey"] else ""))
    return to_delete, groups


def delete_ids(conn, ids, dry_run):
    if not ids:
        return 0
    if dry_run:
        return len(ids)
    placeholders = ",".join("?" * len(ids))
    conn.execute(
        f"DELETE FROM questions WHERE id IN ({placeholders})",
        ids,
    )
    conn.commit()
    return len(ids)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Tylko raport, bez DELETE")
    args = ap.parse_args()

    conn = get_connection()
    w = pending_where()

    total_pending = conn.execute(
        f"SELECT COUNT(*) FROM questions {w}"
    ).fetchone()[0]
    print(f"Pending (error/NULL, bez Anki): {total_pending}")

    incomplete = find_incomplete_ids(conn)
    inc_ids = [r["id"] for r in incomplete]
    print(f"\n[2] Niepełne (brak pytania lub A,B,C puste): {len(inc_ids)}")
    for r in incomplete[:10]:
        print(f"  id={r['id']} nr={r['nr_pytania']} {r['kategoria']}: {(r['pyt'] or '')[:60]}")
    if len(incomplete) > 10:
        print(f"  ... i {len(incomplete) - 10} więcej")

    dup_delete, dup_groups = find_duplicate_ids_to_delete(conn)
    dup_ids = [x[0] for x in dup_delete]
    print(f"\n[1] Grupy duplikatów (pełne pytanie+źródło): {dup_groups}")
    print(f"    Do usunięcia (kopie, zostaje min ID): {len(dup_ids)}")
    for qid, keep, preview in dup_delete[:10]:
        print(f"  usuń id={qid} (zostaw {keep}) «{preview}…»")
    if len(dup_delete) > 10:
        print(f"  ... i {len(dup_delete) - 10} więcej")

    all_delete = sorted(set(inc_ids + dup_ids))
    overlap = set(inc_ids) & set(dup_ids)
    if overlap:
        print(f"\nUwaga: {len(overlap)} ID w obu listach (i tak jedno usunięcie)")

    print(f"\nRazem do usunięcia: {len(all_delete)}")
    if args.dry_run:
        print("DRY-RUN — brak zmian w bazie.")
        conn.close()
        return

    if not all_delete:
        print("Nic do usunięcia.")
        conn.close()
        return

    n = delete_ids(conn, all_delete, dry_run=False)
    remaining = conn.execute(f"SELECT COUNT(*) FROM questions {w}").fetchone()[0]
    print(f"Usunięto: {n}. Pending po czyszczeniu: {remaining}")
    conn.close()


if __name__ == "__main__":
    main()
