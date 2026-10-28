"""
Parsiuje PDFy w formacie 1 (Dział pokładowy + Angielski).

Format tabeli: Lp | O/T | Pytanie | a) b) c) | Poprawna
"""
import fitz
import re
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR)
sys.path.insert(0, BASE_DIR)
from init_db import get_connection, insert_questions, mark_file_parsed, is_file_parsed


def normalize(text):
    return re.sub(r"\s+", " ", text.strip())


def extract_text_from_pdf(filepath):
    doc = fitz.open(filepath)
    all_text = []
    for page in doc:
        text = page.get_text("text")
        all_text.append(text)
    doc.close()
    return "\n".join(all_text)


def parse_format1(filepath, kategoria, podkategoria, poziom, tematyka):
    raw = extract_text_from_pdf(filepath)
    lines = raw.split("\n")
    lines = [normalize(l) for l in lines]
    lines = [l for l in lines if l]

    questions = []
    current_q = None
    current_answers = []
    current_text_lines = []
    in_question_text = False

    i = 0
    expect_flag = False
    pending_answer_letter = None  # For split answer options (label on one line, text on next)

    while i < len(lines):
        line = lines[i]

        # Handle pending split answer text
        if pending_answer_letter and current_q:
            current_answers.append((pending_answer_letter, line))
            pending_answer_letter = None
            in_question_text = False
            i += 1
            continue

        # Detect question number at start of line (e.g., "1." or "1")
        nr_match = re.match(r"^(\d{1,3})\.?$", line)

        if nr_match:
            # Save previous question if exists
            if current_q and current_answers:
                q = finalize_question(current_q, current_answers, current_text_lines,
                                      kategoria, podkategoria, poziom, tematyka, filepath)
                if q:
                    questions.append(q)

            current_q = {"nr": int(nr_match.group(1))}
            current_answers = []
            current_text_lines = []
            in_question_text = False
            expect_flag = False
            pending_answer_letter = None

            # Peek at next line to determine if it's a page number vs question number
            next_line = lines[i + 1].strip() if i + 1 < len(lines) else ""
            # If next line is O/T/D/B flag, this is a real question
            # Otherwise, check if next line is empty (page number marker) or text
            if re.match(r"^[OTDBMotdbm]$", next_line):
                in_question_text = False
                expect_flag = False
                i += 1
                continue
            else:
                # Could be question without flag (question text directly follows)
                # OR a page number. If it's a page number, skip.
                # Page numbers are at the start of pages, followed by headers
                # Simple heuristic: if the line after next_line is also not a real answer/question,
                # treat as page number
                if not current_answers and not (next_line and (
                    len(next_line) > 10 or
                    re.match(r"^([a-dA-D])[\)\.]", next_line)
                )):
                    # Likely a page number, discard current_q
                    current_q = None
                    in_question_text = False
                    expect_flag = False
                    i += 1
                    continue
                in_question_text = True
                i += 1
                continue

        # Detect correct answer letter - must check BEFORE flags
        # (A-D can also be flags, but if we have answers, it's a correct answer)
        correct_match = re.match(r"^([A-D])$", line)
        if correct_match and current_q and current_answers:
            current_q["correct"] = correct_match.group(1)
            in_question_text = False
            i += 1
            continue

        # Skip O/T/D/B/M flag lines (right after question number)
        if re.match(r"^[OTDBMotdbm]$", line):
            if current_q:
                in_question_text = True
            i += 1
            continue

        # Detect answer option (a), b), c), d) or a., b., c., d.)
        opt_match = re.match(r"^([a-dA-D])[\)\.]\s*(.+)", line)
        if opt_match and current_q:
            letter = opt_match.group(1).upper()
            text = opt_match.group(2).strip()
            current_answers.append((letter, text))
            pending_answer_letter = None
            in_question_text = False
            i += 1
            continue

        # Detect split answer label: just "a)" or "c)" with no text after
        split_label = re.match(r"^([a-dA-D])[\)\.]\s*$", line)
        if split_label and current_q:
            pending_answer_letter = split_label.group(1).upper()
            in_question_text = False
            i += 1
            continue

        # Detect correct answer letter (single uppercase letter) - only after answers collected
        correct_match = re.match(r"^([A-D])$", line)
        if correct_match and current_q and current_answers:
            current_q["correct"] = correct_match.group(1)
            in_question_text = False
            i += 1
            continue

        # Accumulate question text
        if in_question_text and current_q:
            current_text_lines.append(line)

        i += 1

    # Save the last question
    if current_q and current_answers:
        q = finalize_question(current_q, current_answers, current_text_lines,
                              kategoria, podkategoria, poziom, tematyka, filepath)
        if q:
            questions.append(q)

    return questions


def finalize_question(current_q, current_answers, current_text_lines,
                      kategoria, podkategoria, poziom, tematyka, filepath):
    question_text = " ".join(current_text_lines).strip()
    if not question_text or not current_answers:
        return None

    # Special case: when the question text itself contains the answer options
    # (e.g., question starts with "a." and is not parsed as answer yet)
    # Check if question_text contains answer prefixes like " a. " and extract them
    q_text, extracted_answers = split_inline_answers(question_text)
    if extracted_answers:
        question_text = q_text
        current_answers = extracted_answers + current_answers

    q = {
        "kategoria": kategoria,
        "podkategoria": podkategoria,
        "poziom": poziom,
        "tematyka": tematyka,
        "nr_pytania": current_q["nr"],
        "typ_pytania": "testowe",
        "pytanie": question_text,
        "odp_a": None, "odp_b": None, "odp_c": None, "odp_d": None,
        "poprawna_odpowiedz": current_q.get("correct"),
        "poprawna_odpowiedz_tekst": None,
        "zrodlo_pliku": filepath,
    }

    for letter, text in current_answers:
        key = f"odp_{letter.lower()}"
        q[key] = text

    # Set correct answer text
    correct_letter = current_q.get("correct")
    if correct_letter:
        key = f"odp_{correct_letter.lower()}"
        q["poprawna_odpowiedz_tekst"] = q.get(key)

    return q


def split_inline_answers(text):
    """Extract a) b) c) prefixes from within question text."""
    pattern = re.compile(r"\s+([a-dA-D])[\)\.]\s*", re.IGNORECASE)
    parts = pattern.split(text)
    if len(parts) < 3:
        return text, []

    question = parts[0].strip()
    answers = []
    for j in range(1, len(parts) - 1, 2):
        letter = parts[j].upper()
        answer_text = parts[j + 1].strip() if j + 1 < len(parts) else ""
        answers.append((letter, answer_text))

    return question, answers


def tematyka_z_nazwy(filename):
    """Extract topic from filename like 'F1-P1-Nawigacja.pdf' or 'F1-P1-nawigacja (nowe).pdf'"""
    base = os.path.splitext(filename)[0]
    base = re.sub(r"\s*\(nowe\)\s*", "", base, flags=re.IGNORECASE)
    parts = re.split(r"[-–]", base)
    if len(parts) >= 3:
        return parts[2].strip()
    return base


def parse_directory(dirpath, filter=None):
    """Recursively find all PDFs in directory matching optional filter."""
    results = []
    for root, dirs, files in os.walk(dirpath):
        for f in files:
            if f.lower().endswith(".pdf"):
                full = os.path.join(root, f)
                if filter is None or filter(full):
                    results.append(full)
    return results


def run_format1(conn):
    base = DATA_DIR
    dzial_path = os.path.join(base, "Dział_pokładowy")
    ang_path = os.path.join(base, "angielski")

    total = 0

    # ---- Dział pokładowy ----
    if os.path.isdir(dzial_path):
        pdfs = parse_directory(dzial_path)
        for pdf in sorted(pdfs):
            rel = os.path.relpath(pdf, base)
            if is_file_parsed(conn, rel):
                continue

            parts = rel.replace("\\", "/").split("/")
            kategoria = "Dział pokładowy"
            poziom = None
            podkategoria = None

            for p in parts:
                pl = p.lower()
                if "poziom" in pl:
                    if "operacyjny" in pl:
                        poziom = "operacyjny"
                    elif "pomocniczy" in pl:
                        poziom = "pomocniczy"
                    elif "zarządzania" in pl or "zarzadzania" in pl:
                        poziom = "zarządzania"

            if len(parts) >= 5:
                podkategoria = parts[3]

            filename = os.path.basename(pdf)
            tematyka = tematyka_z_nazwy(filename)

            print(f"  Parsuję PDF: {rel}")
            questions = parse_format1(pdf, kategoria, podkategoria, poziom, tematyka)
            if questions:
                n = insert_questions(conn, questions)
                mark_file_parsed(conn, rel, "format1", n)
                total += n
                print(f"    → {n} pytań")
            else:
                print(f"    → 0 pytań (błąd parsowania?)")

    # ---- Angielski ----
    if os.path.isdir(ang_path):
        pdfs = parse_directory(ang_path)
        for pdf in sorted(pdfs):
            rel = os.path.relpath(pdf, base)
            if is_file_parsed(conn, rel):
                continue

            kategoria = "Angielski"
            poziom = None
            podkategoria = None

            parts = rel.replace("\\", "/").split("/")
            if len(parts) >= 3:
                podkategoria = parts[2]

            filename = os.path.basename(pdf)
            tematyka = tematyka_z_nazwy(filename)

            print(f"  Parsuję PDF: {rel}")
            questions = parse_format1(pdf, kategoria, podkategoria, poziom, tematyka)
            if questions:
                n = insert_questions(conn, questions)
                mark_file_parsed(conn, rel, "format1", n)
                total += n
                print(f"    → {n} pytań")
            else:
                print(f"    → 0 pytań (błąd parsowania?)")

    return total


if __name__ == "__main__":
    conn = get_connection()
    n = run_format1(conn)
    print(f"\nFormat 1: dodano {n} pytań")
    conn.close()
