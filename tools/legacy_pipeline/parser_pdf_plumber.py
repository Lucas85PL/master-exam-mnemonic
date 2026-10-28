"""
Parser PDF oparty na pdfplumber — drugi, niezależny silnik do odczytu
tekstu z PDF (cross-check dla PyMuPDF/fitz).

Używa wykrywania tabel (find_tables) aby poprawnie obsłużyć układy
wielokolumnowe. Fallback: ekstrakcja tekstu z obszaru.
"""
import pdfplumber
import re
import os


def normalize(text):
    return re.sub(r"\s+", " ", text.strip())


def _extract_table_text(page, bbox=None):
    """
    Wyciąga tekst z tabeli na stronie, z zachowaniem kolumn.
    Zwraca listę wierszy (każdy wiersz to lista komórek).
    """
    tables = page.find_tables()
    if not tables:
        return None

    best_table = None
    best_score = 0

    for table in tables:
        if bbox:
            r = table.bbox
            x_overlap = max(0, min(r[2], bbox[2]) - max(r[0], bbox[0]))
            y_overlap = max(0, min(r[3], bbox[3]) - max(r[1], bbox[1]))
            score = x_overlap * y_overlap
        else:
            data = table.extract()
            if not data:
                continue
            score = len(data)

        if score > best_score:
            best_score = score
            best_table = table

    if not best_table:
        return None

    return best_table.extract()


def _extract_table_file(filepath, page_num, bbox=None):
    """Otwiera PDF i wyciąga dane tabeli z podanej strony."""
    with pdfplumber.open(filepath) as pdf:
        if page_num >= len(pdf.pages):
            return None
        return _extract_table_text(pdf.pages[page_num], bbox)


def extract_region(filepath, page_num, bbox):
    """
    Wyciąga tekst z prostokątnego obszaru strony (fallback).
    bbox: (x0, y0, x1, y1) w punktach PDF.
    """
    with pdfplumber.open(filepath) as pdf:
        if page_num >= len(pdf.pages):
            return ""
        page = pdf.pages[page_num]
        crop = page.crop(bbox)
        return crop.extract_text() or ""


def parse_question_from_table(filepath, page_num, target_num, bbox=None):
    """
    Parsuje pytanie z tabeli PDF używając pdfplumber.
    Obsługuje oba formaty: Dział pokładowy/Angielski (format1)
    i Kapitan (format2).

    Zwraca dict lub None.
    """
    with pdfplumber.open(filepath) as pdf:
        if page_num >= len(pdf.pages):
            return None
        page = pdf.pages[page_num]

        tables = page.find_tables()
        if not tables:
            return None

        best_table = None
        best_score = 0
        for table in tables:
            if bbox:
                r = table.bbox
                xo = max(0, min(r[2], bbox[2]) - max(r[0], bbox[0]))
                yo = max(0, min(r[3], bbox[3]) - max(r[1], bbox[1]))
                score = xo * yo
            else:
                data = table.extract()
                score = len(data) if data else 0
            if score > best_score:
                best_score = score
                best_table = table

        if not best_table:
            return None

        data = best_table.extract()
        if not data:
            return None

        fmt = _detect_format(data)
        if fmt in ("format1_4col", "format1_6col"):
            return _parse_format1_table(data, target_num, fmt)
        else:
            return _parse_format2_table(page, best_table, data, target_num)


def _detect_format(data):
    """Wykryj format tabeli na podstawie układu kolumn."""
    for row in data:
        if not row:
            continue
        ncols = len(row)

        if ncols == 6:
            return "format1_6col"
        if ncols == 4:
            # Check if question text is in col1 or col2
            col1 = normalize(row[1] or "") if ncols > 1 else ""
            col2 = normalize(row[2] or "") if ncols > 2 else ""
            if col2 and ("\na)" in col2 or "\na." in col2 or "\nA)" in col2):
                return "format1_4col"
            if col2 and len(col2) > 50:
                return "format1_4col"
            if col1 and re.match(r"^[a-dA-D][\)\.]", col1):
                return "format2"
            if col1 and len(col1) > 30:
                return "format2"

    return "format1_4col"


def _parse_format1_table(data, target_num, fmt):
    for row in data:
        if not row:
            continue

        if fmt == "format1_6col":
            if len(row) < 6:
                continue
            col0 = normalize(row[0] or "")
            col5 = normalize(row[5] or "")
            question_cell = (row[4] or "").strip()
            correct_cell = col5
        else:
            if len(row) < 3:
                continue
            col0 = normalize(row[0] or "")
            col3 = normalize(row[3] or "") if len(row) > 3 else ""
            question_cell = (row[2] or "").strip()
            correct_cell = col3

        if not col0 or not question_cell:
            continue

        num_match = re.match(r"(\d+)", col0)
        if not num_match:
            continue
        num = int(num_match.group(1))
        if target_num is not None and num != target_num:
            continue

        return _split_format1_cell(question_cell, correct_cell, num)

    return None


def _split_format1_cell(cell_text, correct_cell, qnum):
    """Rozbija komorek format1 na pytanie i odpowiedzi."""
    text = cell_text
    answers = {}
    question_lines = []
    seen_answer = False

    lines = text.split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue

        ans_match = re.match(r"^([a-dA-D])[\)\.]\s*(.+)", line)
        if ans_match:
            letter = ans_match.group(1).upper()
            ans_text = ans_match.group(2).strip()
            answers[letter] = ans_text
            seen_answer = True
            continue

        if not seen_answer:
            question_lines.append(line)

    question_text = " ".join(question_lines).strip()

    correct = None
    for c in correct_cell.split():
        c = c.strip().upper()
        if c in ("A", "B", "C", "D"):
            correct = c
            break

    if not question_text:
        return None

    return {
        "nr": qnum,
        "pytanie": question_text,
        "odp_a": answers.get("A"),
        "odp_b": answers.get("B"),
        "odp_c": answers.get("C"),
        "odp_d": answers.get("D"),
        "poprawna_odpowiedz": correct,
    }


def _cell_words(page, words, table, row_idx, col_idx):
    """Extract properly spaced text from a table cell using word positions."""
    if row_idx >= len(table.rows):
        return ""
    row_cells = table.rows[row_idx].cells
    if col_idx >= len(row_cells) or row_cells[col_idx] is None:
        return ""

    bbox = row_cells[col_idx]
    x0, top, x1, bot = bbox

    cell_words = [
        w for w in words
        if x0 <= w['x0'] <= x1
        and top - 2 <= w['top'] <= bot + 2
    ]
    cell_words.sort(key=lambda w: (w['top'], w['x0']))
    return ' '.join(w['text'] for w in cell_words)


def _parse_format2_table(page, table, data, target_num):
    """
    Format2 (Kapitan): odpowiedzi rozbite na wiele wierszy.
    Do struktury używa cell-text, do treści używa word-extraction (spacje).
    """
    words = page.extract_words(x_tolerance=2)

    questions = {}
    current_num = None
    current_question = ""
    current_answers = {}
    current_correct = None

    for i, row in enumerate(data):
        if not row:
            continue

        col0 = normalize(row[0] or "")
        col1 = normalize(row[1] or "") if len(row) > 1 else ""
        col2 = normalize(row[2] or "") if len(row) > 2 else ""
        col3 = normalize(row[3] or "") if len(row) > 3 else ""

        # Check if new question starts (col0 has a number)
        num_match = re.match(r"(\d+)", col0)
        if num_match and col1:
            if current_num is not None:
                questions[current_num] = _build_format2_result(
                    current_question, current_answers, current_correct, current_num
                )

            current_num = int(num_match.group(1))

            # Use word-extraction for question text (proper spacing)
            current_question = _cell_words(page, words, table, i, 1)
            current_answers = {}
            current_correct = None

            for c in col3.split():
                c = c.strip().upper()
                if c in ("A", "B", "C", "D"):
                    current_correct = c
                    break
            continue

        # Answer rows: col1 has answer label
        if current_num is not None and col1:
            ans_match = re.match(r"^([a-dA-D])[\)\.]?\s*(.*)", col1)
            if ans_match:
                letter = ans_match.group(1).upper()
                ans_text = ans_match.group(2).strip()
                if ans_text:
                    current_answers[letter] = ans_text
                else:
                    # Use word-extraction for answer text (proper spacing)
                    ans_text = _cell_words(page, words, table, i, 1)
                    ans_text = re.sub(r"^[a-dA-D][\)\.]?\s*", "", ans_text).strip()
                    if col2:
                        ans_text = (ans_text + " " + col2).strip()
                    current_answers[letter] = ans_text

            for c in col3.split():
                c = c.strip().upper()
                if c in ("A", "B", "C", "D"):
                    current_correct = c
                    break

            for c in col3.split():
                c = c.strip().upper()
                if c in ("A", "B", "C", "D"):
                    current_correct = c
                    break

    if current_num is not None:
        questions[current_num] = _build_format2_result(
            current_question, current_answers, current_correct, current_num
        )

    if target_num is not None:
        return questions.get(target_num)
    return list(questions.values())[0] if questions else None


def detect_table_format(filepath, page_num):
    """Wykrywa format tabeli na stronie: format1_4col, format1_6col lub format2."""
    with pdfplumber.open(filepath) as pdf:
        if page_num >= len(pdf.pages):
            return "format1_4col"
        page = pdf.pages[page_num]
        tables = page.find_tables()
        if not tables:
            return "format1_4col"
        best_table = max(
            tables,
            key=lambda t: len(t.extract() or []),
        )
        data = best_table.extract()
        if not data:
            return "format1_4col"
        return _detect_format(data)


def vision_format_tag(table_fmt):
    """Mapuje format plumber na prompt Vision: format1 | format2."""
    if table_fmt in ("format1_4col", "format1_6col"):
        return "format1"
    return "format2"


def find_question_page(filepath, target_num):
    """
    Szuka strony z pytaniem o podanym numerze.
    Zwraca (page_num, table_fmt) lub (None, None).
    """
    if target_num is None:
        return None, None

    with pdfplumber.open(filepath) as pdf:
        for page_num in range(len(pdf.pages)):
            page = pdf.pages[page_num]
            tables = page.find_tables()
            if not tables:
                continue
            best_table = max(
                tables,
                key=lambda t: len(t.extract() or []),
            )
            data = best_table.extract()
            if not data:
                continue
            fmt = _detect_format(data)
            if fmt in ("format1_4col", "format1_6col"):
                hit = _parse_format1_table(data, target_num, fmt)
            else:
                hit = _parse_format2_table(page, best_table, data, target_num)
            if hit:
                return page_num, fmt
    return None, None


def _build_format2_result(question_text, answers, correct, num):
    """Buduje wynikowy dict dla format2."""
    question_text = normalize(question_text) if question_text else ""
    if not question_text or len(question_text) < 3:
        return None

    return {
        "nr": num,
        "pytanie": question_text,
        "odp_a": answers.get("A"),
        "odp_b": answers.get("B"),
        "odp_c": answers.get("C"),
        "odp_d": answers.get("D"),
        "poprawna_odpowiedz": correct,
    }


def parse_question(text, target_num=None):
    """
    Fallback mini-parser dla tekstu spoza tabeli.
    Rozbija surowy tekst na strukturę pytania.
    """
    if not text or not text.strip():
        return None

    lines = text.strip().split("\n")
    lines = [normalize(l) for l in lines if l.strip()]

    if not lines:
        return None

    blocks = _split_into_blocks(lines, target_num)
    if not blocks:
        return None

    return _build_from_block(blocks[0]["nr"], blocks[0]["lines"])


def _split_into_blocks(lines, target_num=None):
    blocks = []
    current_nr = None
    current_lines = []
    in_question = False

    for line in lines:
        num_match = re.match(r"^(\d{1,3})[\.)]?\s*$", line)
        if num_match:
            if current_lines and current_nr is not None:
                blocks.append({"nr": current_nr, "lines": current_lines})
            current_nr = int(num_match.group(1))
            current_lines = []
            in_question = True
            continue
        if in_question and current_nr is not None:
            current_lines.append(line)

    if current_lines and current_nr is not None:
        blocks.append({"nr": current_nr, "lines": current_lines})

    if target_num is not None:
        blocks = [b for b in blocks if b["nr"] == target_num]
    return blocks


def _build_from_block(num, lines):
    question_parts = []
    answers = {}
    correct = None
    seen_answers = False
    pending_split_label = None

    FLAGS = {"O", "T", "D", "B", "M"}
    processed = []
    skipped_first_flag = False
    for line in lines:
        if not skipped_first_flag and line.upper() in FLAGS:
            skipped_first_flag = True
            continue
        processed.append(line)

    for line in processed:
        if pending_split_label:
            answers[pending_split_label] = line.strip()
            pending_split_label = None
            continue

        ans_match = re.match(r"^([a-dA-D])[\)\.]\s*(.+)", line)
        if ans_match:
            letter = ans_match.group(1).upper()
            text = ans_match.group(2).strip()
            answers[letter] = text
            seen_answers = True
            continue

        split_label = re.match(r"^([a-dA-D])[\)\.]\s*$", line)
        if split_label:
            pending_split_label = split_label.group(1).upper()
            seen_answers = True
            continue

        correct_match = re.match(r"^([A-D])$", line)
        if correct_match and answers:
            correct = correct_match.group(1)
            continue

        if not seen_answers:
            question_parts.append(line)

    question_text = " ".join(question_parts).strip()
    if not question_text or not answers:
        return None

    return {
        "nr": num,
        "pytanie": question_text,
        "odp_a": answers.get("A"),
        "odp_b": answers.get("B"),
        "odp_c": answers.get("C"),
        "odp_d": answers.get("D"),
        "poprawna_odpowiedz": correct,
    }
