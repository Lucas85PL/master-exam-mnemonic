import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "questions.db")


def get_connection(db_path=None):
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def create_tables(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kategoria TEXT NOT NULL,
            podkategoria TEXT,
            poziom TEXT,
            tematyka TEXT NOT NULL,
            nr_pytania INTEGER,
            typ_pytania TEXT NOT NULL DEFAULT 'testowe',
            pytanie TEXT NOT NULL,
            odp_a TEXT,
            odp_b TEXT,
            odp_c TEXT,
            odp_d TEXT,
            poprawna_odpowiedz TEXT,
            poprawna_odpowiedz_tekst TEXT,
            zrodlo_pliku TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS parsed_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sciezka TEXT UNIQUE NOT NULL,
            parser TEXT NOT NULL,
            liczba_pytan INTEGER NOT NULL,
            data_parsowania TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_kategoria ON questions(kategoria)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_tematyka ON questions(tematyka)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_zrodlo ON questions(zrodlo_pliku)
    """)

    # Add review columns if they don't exist
    try:
        conn.execute("ALTER TABLE questions ADD COLUMN review_status TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE questions ADD COLUMN review_notes TEXT")
    except sqlite3.OperationalError:
        pass

    conn.commit()


def clear_data(conn):
    conn.execute("DELETE FROM questions")
    conn.execute("DELETE FROM parsed_files")
    conn.commit()


def insert_questions(conn, questions):
    inserted = 0
    for q in questions:
        conn.execute("""
            INSERT INTO questions
                (kategoria, podkategoria, poziom, tematyka, nr_pytania,
                 typ_pytania, pytanie, odp_a, odp_b, odp_c, odp_d,
                 poprawna_odpowiedz, poprawna_odpowiedz_tekst, zrodlo_pliku)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            q["kategoria"], q.get("podkategoria"), q.get("poziom"),
            q["tematyka"], q.get("nr_pytania"),
            q["typ_pytania"], q["pytanie"],
            q.get("odp_a"), q.get("odp_b"), q.get("odp_c"), q.get("odp_d"),
            q.get("poprawna_odpowiedz"), q.get("poprawna_odpowiedz_tekst"),
            q["zrodlo_pliku"]
        ))
        inserted += 1
    conn.commit()
    return inserted


def mark_file_parsed(conn, sciezka, parser, liczba_pytan):
    conn.execute("""
        INSERT OR REPLACE INTO parsed_files (sciezka, parser, liczba_pytan, data_parsowania)
        VALUES (?, ?, ?, datetime('now'))
    """, (sciezka, parser, liczba_pytan))
    conn.commit()


def is_file_parsed(conn, sciezka):
    row = conn.execute("SELECT COUNT(*) as cnt FROM parsed_files WHERE sciezka = ?",
                       (sciezka,)).fetchone()
    return row["cnt"] > 0


def get_stats(conn):
    total = conn.execute("SELECT COUNT(*) as cnt FROM questions").fetchone()["cnt"]
    testowe = conn.execute(
        "SELECT COUNT(*) as cnt FROM questions WHERE typ_pytania = 'testowe'"
    ).fetchone()["cnt"]
    otwarte = conn.execute(
        "SELECT COUNT(*) as cnt FROM questions WHERE typ_pytania = 'otwarte'"
    ).fetchone()["cnt"]
    kategorie = conn.execute(
        "SELECT kategoria, COUNT(*) as cnt FROM questions GROUP BY kategoria ORDER BY cnt DESC"
    ).fetchall()
    return {
        "total": total,
        "testowe": testowe,
        "otwarte": otwarte,
        "kategorie": [(r["kategoria"], r["cnt"]) for r in kategorie],
    }


if __name__ == "__main__":
    conn = get_connection()
    create_tables(conn)
    stats = get_stats(conn)
    print(f"Baza gotowa. Pytań: {stats['total']}")
    conn.close()
