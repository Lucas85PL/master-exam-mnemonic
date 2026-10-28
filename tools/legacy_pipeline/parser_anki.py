"""
Parsiuje plik .colpkg (Anki export) do unified bazy pytań.

.colpkg to nazwany ZIP zawierający collection.anki21 (SQLite).
Parser jest niezależny od modelu - automatycznie wykrywa format pytania.
"""
import sqlite3
import json
import zipfile
import re
import os
import sys
import tempfile
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)
from init_db import get_connection, insert_questions, mark_file_parsed, is_file_parsed


def anki_normalize(text):
    """Normalize Anki HTML text: replace <br> with newlines, &nbsp; with space."""
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = text.replace("&nbsp;", " ")
    text = re.sub(r"\s+", " ", text.strip())
    return text


def parse_colpkg(filepath, kategoria):
    work_dir = tempfile.mkdtemp()
    try:
        db_path = extract_anki_db(filepath, work_dir)
        conn_anki = sqlite3.connect(db_path)
        conn_anki.row_factory = sqlite3.Row
        c = conn_anki.cursor()

        c.execute("SELECT decks FROM col")
        decks = json.loads(c.fetchone()[0])

        deck_names = {}
        for did, deck in decks.items():
            deck_names[did] = clean_deck_name(deck["name"])

        questions = []

        # Get all notes with their deck
        c.execute("""
            SELECT n.id, n.flds, c.did
            FROM notes n
            JOIN cards c ON c.nid = n.id
            GROUP BY n.id
        """)

        for row in c.fetchall():
            fields = row["flds"].split("\x1f")
            front = fields[0] if len(fields) > 0 else ""
            back = fields[1] if len(fields) > 1 else ""
            did = str(row["did"])
            tematyka = deck_names.get(did, "Nieznana")

            q = parse_note(front, back, kategoria, tematyka, filepath)
            if q:
                questions.append(q)

        conn_anki.close()
        return questions

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


def extract_anki_db(colpkg_path, work_dir):
    with zipfile.ZipFile(colpkg_path, "r") as zf:
        db_path = zf.extract("collection.anki21", work_dir)
    return db_path


def clean_deck_name(name):
    cleaned = re.sub(r"^\d+\.\s*", "", name.strip())
    if cleaned.lower() in ("domyślna", "default", "domylna"):
        return "Inne"
    cleaned = cleaned.replace("\u009c", "ś").replace("\u009b", "ł")
    return cleaned


def parse_note(front, back, kategoria, tematyka, filepath):
    """Parse a single Anki note, auto-detecting format."""
    if not front:
        return None

    # First, try to parse the raw front (before HTML normalization)
    # This handles MS Office HTML tables
    mso_result = extract_mso_table(front)
    if mso_result:
        question_text, answers = mso_result
    else:
        question_text = ""
        answers = []

    if not answers:
        # Strip all HTML including MSO boilerplate, then try inline parsing
        front_norm = strip_all_html(front)
        question_text, answers = split_inline_answers(front_norm)

    if answers:
        # Clean question text from any remaining HTML
        question_text = strip_html(question_text)

        # Multiple choice question
        correct_letter = extract_correct_from_back(back)

        q = {
            "kategoria": kategoria,
            "podkategoria": None,
            "poziom": None,
            "tematyka": tematyka,
            "nr_pytania": None,
            "typ_pytania": "testowe",
            "pytanie": question_text,
            "odp_a": None, "odp_b": None, "odp_c": None, "odp_d": None,
            "poprawna_odpowiedz": correct_letter,
            "poprawna_odpowiedz_tekst": None,
            "zrodlo_pliku": filepath,
        }

        for letter, text in answers:
            key = f"odp_{letter.lower()}"
            q[key] = strip_html(text)

        if correct_letter:
            key = f"odp_{correct_letter.lower()}"
            q["poprawna_odpowiedz_tekst"] = q.get(key)

        return q

    # No answers found - treat as flashcard (open question)
    front_norm = anki_normalize(front)
    back_norm = anki_normalize(back)

    # If front is pure HTML/MSO garbage, extract text from it
    if not front_norm or front_norm.startswith("<!--[if"):
        front_norm = strip_all_html(front)

    if not front_norm or len(front_norm.strip()) < 3:
        return None

    # Also clean the back answer (strip HTML)
    back_clean = strip_all_html(back)
    if not back_clean:
        back_clean = back_norm

    return {
        "kategoria": kategoria,
        "podkategoria": None,
        "poziom": None,
        "tematyka": tematyka,
        "nr_pytania": None,
        "typ_pytania": "otwarte",
        "pytanie": front_norm,
        "odp_a": None, "odp_b": None, "odp_c": None, "odp_d": None,
        "poprawna_odpowiedz": None,
        "poprawna_odpowiedz_tekst": back_clean,
        "zrodlo_pliku": filepath,
    }


def split_inline_answers(front):
    """Split plain text front into question + [(letter, answer_text), ...]"""
    pattern = re.compile(r"\s*([a-dA-D])[\)\.]\s*")
    match = pattern.search(front)
    if not match:
        pattern2 = re.compile(r"^([a-dA-D])[\)\.]\s*")
        match = pattern2.match(front)
        if match:
            question_text = ""
            remaining = front[match.end():]
        else:
            return front, []
    else:
        question_text = front[:match.start()].strip()
        remaining = front[match.start():]

    answers = []
    parts = re.split(r"\s*([a-dA-D])[\)\.]\s*", remaining)
    if len(parts) > 1:
        for j in range(1, len(parts) - 1, 2):
            letter = parts[j].upper()
            text = parts[j + 1].strip() if j + 1 < len(parts) else ""
            answers.append((letter, text))

    if not question_text and answers:
        question_text = "(pytanie bez treści - patrz opcje)"

    return question_text, answers


def extract_mso_table(html):
    """Extract question + answers from MS Office HTML table format.
    Returns (question_text, [(letter, answer_text), ...]) or None."""
    if "StartFragment" not in html and "<table>" not in html:
        return None

    start = html.find("<!--StartFragment-->")
    if start == -1:
        start = html.find("<table")
        if start == -1:
            return None
    else:
        start += len("<!--StartFragment-->")

    end = html.find("<!--EndFragment-->")
    if end == -1:
        end = len(html)

    table_html = html[start:end].strip()

    # Extract question from first row (td with colspan=2)
    q_match = re.search(
        r'<td[^>]*colspan\s*=\s*["\']?\s*2[^>]*>(.*?)</td>',
        table_html, re.DOTALL | re.IGNORECASE
    )
    question_text = ""
    if q_match:
        question_text = strip_html(q_match.group(1))

    # Extract answer rows
    answers = []
    answer_rows = re.finditer(r'<tr>(.*?)</tr>', table_html, re.DOTALL | re.IGNORECASE)
    for row in answer_rows:
        row_html = row.group(1)
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row_html, re.DOTALL | re.IGNORECASE)
        if len(cells) >= 2:
            label = strip_html(cells[0]).strip()
            label_match = re.match(r"^([a-dA-D])[\)\.]?\s*$", label)
            if label_match:
                letter = label_match.group(1).upper()
                text = strip_html(cells[1]).strip()
                answers.append((letter, text))

    if not question_text and not answers:
        return None

    return question_text, answers


def extract_correct_from_back(back):
    """Extract correct answer letter from Back field."""
    back_clean = anki_normalize(back).strip()

    # Text format: "a. text" or "a.text" or "a) text"
    prefix_match = re.match(r"^([a-dA-D])[\)\.]\s*", back_clean)
    if prefix_match:
        return prefix_match.group(1).upper()

    # HTML table format
    cell_match = re.search(
        r'<td[^>]*>\s*<div[^>]*>\s*([a-dA-D])[\)\.]?\s*</div>\s*</td>',
        back, re.IGNORECASE | re.DOTALL
    )
    if cell_match:
        return cell_match.group(1).upper()

    return None


def strip_html(text):
    """Remove HTML tags including style blocks from text."""
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ")
    text = re.sub(r"\s+", " ", text.strip())
    return text


def strip_all_html(text):
    """Remove all HTML including MSO comments."""
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ")
    text = re.sub(r"\s+", " ", text.strip())
    return text


def run_anki(conn):
    base = BASE_DIR
    colpkg_path = os.path.join(base, "cpt-AllInOne.colpkg")

    if not os.path.isfile(colpkg_path):
        print("  Plik .colpkg nie znaleziony")
        return 0

    rel = os.path.relpath(colpkg_path, base)
    if is_file_parsed(conn, rel):
        print(f"  {rel} już sparsowany")
        return 0

    kategoria = "Chief Officer"

    print(f"  Parsuję colpkg: {rel}")
    questions = parse_colpkg(colpkg_path, kategoria)

    if questions:
        n = insert_questions(conn, questions)
        mark_file_parsed(conn, rel, "anki", n)
        mc_count = sum(1 for q in questions if q["typ_pytania"] == "testowe")
        fc_count = sum(1 for q in questions if q["typ_pytania"] == "otwarte")
        print(f"    → {n} pytań ({mc_count} testowych, {fc_count} otwartych)")
        return n
    else:
        print(f"    → 0 pytań")
        return 0


if __name__ == "__main__":
    conn = get_connection()
    n = run_anki(conn)
    print(f"\nAnki: dodano {n} pytań")
    conn.close()
