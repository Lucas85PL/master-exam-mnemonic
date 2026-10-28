"""
Wspólny zakres SQL i filtry dla pipeline Vision + konsensus (Dział pokładowy, Angielski).
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

EXCLUDE_KAPITAN = """(
    kategoria != 'Kapitan żeglugi wielkiej'
    AND (zrodlo_pliku IS NULL OR zrodlo_pliku NOT LIKE '%Kapitan%')
)"""

INCLUDE_DZIAL_ANG_SQL = """(
    zrodlo_pliku LIKE '%Dział_pokładowy%'
    OR zrodlo_pliku LIKE '%Dzia%pokładowy%'
    OR zrodlo_pliku LIKE '%Dzial_pokladowy%'
    OR zrodlo_pliku LIKE '%angielski%angielski%'
    OR zrodlo_pliku LIKE '%angielski\\angielski%'
)"""

PDF_EXISTS = "zrodlo_pliku IS NOT NULL AND zrodlo_pliku != ''"

VISION_ROW_FIELDS = "id, nr_pytania, pytanie, zrodlo_pliku, typ_pytania"
CONSENSUS_ROW_FIELDS = (
    "id, pytanie, odp_a, odp_b, odp_c, odp_d, poprawna_odpowiedz, typ_pytania"
)


def _norm_path(path):
    if not path:
        return ""
    p = os.path.normpath(path).replace("\\", "/").lower()
    return p


def is_in_scope_path(zrodlo_pliku):
    """PDF z folderów Dział_pokładowy lub angielski/angielski."""
    if not zrodlo_pliku:
        return False
    raw = zrodlo_pliku.replace("\\", "/")
    p = _norm_path(zrodlo_pliku)
    if not p.endswith(".pdf"):
        return False
    if re.search(r"/kapitan[^/]*\.pdf$", p) or "/kapitan/" in p:
        return False
    if "pokładowy" in raw or "pokladowy" in p:
        return True
    if re.search(r"angielski/angielski", raw, re.I):
        return True
    return False


def skip_if_no_pdf(row):
    path = row["zrodlo_pliku"]
    if not path:
        return "no zrodlo_pliku"
    if not is_in_scope_path(path):
        return "outside scope path"
    if not os.path.isfile(path):
        abs_path = path if os.path.isabs(path) else os.path.join(BASE_DIR, path)
        if os.path.isfile(abs_path):
            return None
        return "no PDF file"
    return None


def count_pending_vision(conn, rescan=False):
    sql = f"""
    SELECT COUNT(*) FROM questions
    WHERE {PENDING_REVIEW}
      AND {EXCLUDE_ANKI}
      AND {EXCLUDE_KAPITAN}
      AND {INCLUDE_DZIAL_ANG_SQL}
      AND {PDF_EXISTS}
    """
    if not rescan:
        sql += """
      AND (review_notes IS NULL OR review_notes NOT LIKE 'vision_page:%')
    """
    return conn.execute(sql).fetchone()[0]


def count_pending_consensus(conn):
    sql = f"""
    SELECT COUNT(*) FROM questions
    WHERE {PENDING_REVIEW}
      AND {EXCLUDE_ANKI}
      AND {EXCLUDE_KAPITAN}
      AND {INCLUDE_DZIAL_ANG_SQL}
      AND review_notes LIKE 'vision_page:%'
      AND (review_notes NOT LIKE '%consensus_ok:%')
    """
    return conn.execute(sql).fetchone()[0]


def fetch_pending_vision(conn, question_id=None, limit=None, offset=0, rescan=False):
    sql = f"""
    SELECT {VISION_ROW_FIELDS}
    FROM questions
    WHERE {PENDING_REVIEW}
      AND {EXCLUDE_ANKI}
      AND {EXCLUDE_KAPITAN}
      AND {INCLUDE_DZIAL_ANG_SQL}
      AND {PDF_EXISTS}
    """
    if not rescan:
        sql += """
      AND (review_notes IS NULL OR review_notes NOT LIKE 'vision_page:%')
    """
    params = []
    if question_id is not None:
        sql += " AND id = ?"
        params.append(question_id)
    sql += " ORDER BY COALESCE(nr_pytania, id), id"
    if limit is not None:
        sql += f" LIMIT {int(limit)}"
        if offset:
            sql += f" OFFSET {int(offset)}"
    rows = conn.execute(sql, params).fetchall()
    return [r for r in rows if skip_if_no_pdf(r) is None]


def fetch_pending_consensus(conn, question_id=None, limit=None, offset=0):
    sql = f"""
    SELECT {CONSENSUS_ROW_FIELDS}
    FROM questions
    WHERE {PENDING_REVIEW}
      AND {EXCLUDE_ANKI}
      AND {EXCLUDE_KAPITAN}
      AND {INCLUDE_DZIAL_ANG_SQL}
      AND review_notes LIKE 'vision_page:%'
      AND (review_notes IS NULL OR review_notes NOT LIKE '%consensus_ok:%')
    """
    params = []
    if question_id is not None:
        sql += " AND id = ?"
        params.append(question_id)
    sql += " ORDER BY id"
    if limit is not None:
        sql += f" LIMIT {int(limit)}"
        if offset:
            sql += f" OFFSET {int(offset)}"
    return conn.execute(sql, params).fetchall()
