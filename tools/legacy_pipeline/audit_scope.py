"""
Zakres SQL audytu PDF: Dział pokładowy, Angielski, Kapitan (bez Anki).
"""
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PENDING_REVIEW = """(
    review_status = 'error'
    OR review_status IS NULL
    OR review_status = ''
)"""

EXCLUDE_ANKI = """(
    kategoria != 'Chief Officer'
    AND (zrodlo_pliku IS NULL OR zrodlo_pliku NOT LIKE '%colpkg%')
)"""

INCLUDE_AUDIT_SQL = """(
    kategoria = 'Dział pokładowy'
    OR kategoria = 'Angielski'
    OR kategoria = 'Kapitan żeglugi wielkiej'
    OR zrodlo_pliku LIKE '%Dział_pokładowy%'
    OR zrodlo_pliku LIKE '%Dzia%pokładowy%'
    OR zrodlo_pliku LIKE '%Dzial_pokladowy%'
    OR zrodlo_pliku LIKE '%angielski%angielski%'
    OR zrodlo_pliku LIKE '%angielski\\angielski%'
    OR zrodlo_pliku LIKE '%Kapitan%'
)"""

PDF_EXISTS = "zrodlo_pliku IS NOT NULL AND zrodlo_pliku != ''"

AUDIT_ROW_FIELDS = """
    id, kategoria, nr_pytania, typ_pytania, pytanie,
    odp_a, odp_b, odp_c, odp_d,
    poprawna_odpowiedz, poprawna_odpowiedz_tekst,
    zrodlo_pliku, review_status, review_notes
"""


def resolve_pdf_path(zrodlo_pliku):
    if not zrodlo_pliku:
        return None
    if os.path.isfile(zrodlo_pliku):
        return zrodlo_pliku
    alt = os.path.join(BASE_DIR, zrodlo_pliku)
    if os.path.isfile(alt):
        return alt
    return None


def skip_if_no_pdf(row):
    if not resolve_pdf_path(row["zrodlo_pliku"]):
        return "no PDF file"
    return None


NOT_AUTO_OK = """(
    review_notes IS NULL
    OR (review_notes NOT LIKE '%audit_ok:%' AND review_notes NOT LIKE '%ensemble_ok:%')
)"""


def count_pending_audit(conn, kategoria=None):
    sql = f"""
    SELECT COUNT(*) FROM questions
    WHERE {PENDING_REVIEW}
      AND {EXCLUDE_ANKI}
      AND {INCLUDE_AUDIT_SQL}
      AND {PDF_EXISTS}
      AND {NOT_AUTO_OK}
    """
    params = []
    if kategoria:
        sql += " AND kategoria = ?"
        params.append(kategoria)
    return conn.execute(sql, params).fetchone()[0]


def fetch_pending_audit(conn, question_id=None, limit=None, offset=0, kategoria=None):
    sql = f"""
    SELECT {AUDIT_ROW_FIELDS}
    FROM questions
    WHERE {PENDING_REVIEW}
      AND {EXCLUDE_ANKI}
      AND {INCLUDE_AUDIT_SQL}
      AND {PDF_EXISTS}
      AND {NOT_AUTO_OK}
    """
    params = []
    if kategoria:
        sql += " AND kategoria = ?"
        params.append(kategoria)
    if question_id is not None:
        sql += " AND id = ?"
        params.append(question_id)
    sql += " ORDER BY kategoria, COALESCE(nr_pytania, id), id"
    if limit is not None:
        sql += f" LIMIT {int(limit)}"
        if offset:
            sql += f" OFFSET {int(offset)}"
    rows = conn.execute(sql, params).fetchall()
    return [r for r in rows if skip_if_no_pdf(r) is None]
