"""
Główny skrypt budujący unified bazę pytań z PDFów i pliku colpkg.
Uruchamia wszystkie parsery po kolei.
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from init_db import get_connection, create_tables, get_stats
from parser_pdf_format1 import run_format1
from parser_pdf_format2 import run_format2
from parser_anki import run_anki


def main():
    print("=" * 60)
    print("BUDOWANIE UNIFIED BAZY PYTAŃ")
    print("=" * 60)

    conn = get_connection()
    create_tables(conn)

    # Show initial state
    stats = get_stats(conn)
    print(f"\nStan przed: {stats['total']} pytań w bazie\n")

    # 1. Parse Format 1 PDFs (Dział pokładowy + Angielski)
    print("[1/3] Parsowanie PDF - Format 1 (Dział pokładowy + Angielski)")
    print("-" * 40)
    n1 = run_format1(conn)
    print(f"  → Dodano {n1} pytań\n")

    # 2. Parse Format 2 PDFs (Kapitan)
    print("[2/3] Parsowanie PDF - Format 2 (Kapitan żeglugi wielkiej)")
    print("-" * 40)
    n2 = run_format2(conn)
    print(f"  → Dodano {n2} pytań\n")

    # 3. Parse Anki/colpkg
    print("[3/3] Parsowanie Anki/colpkg (Chief Officer)")
    print("-" * 40)
    n3 = run_anki(conn)
    print(f"  → Dodano {n3} pytań\n")

    # Final stats
    print("=" * 60)
    print("PODSUMOWANIE")
    print("=" * 60)
    stats = get_stats(conn)
    print(f"Łącznie pytań: {stats['total']}")
    print(f"  Testowe (A/B/C/D): {stats['testowe']}")
    print(f"  Otwarte (fiszki):   {stats['otwarte']}")
    print(f"\nWedług kategorii:")
    for kat, cnt in stats["kategorie"]:
        print(f"  {kat}: {cnt}")

    conn.close()
    print("\nGotowe.")


if __name__ == "__main__":
    main()
