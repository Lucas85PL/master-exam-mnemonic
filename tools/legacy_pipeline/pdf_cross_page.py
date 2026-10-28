"""
Parsowanie pytań PDF z obsługą cross-page (pytanie na dole strony N, opcje na N+1).
Wspólne API dla audytu, ensemble i narzędzi naprawczych.
"""
import re

import fitz

from parser_pdf_plumber import (
    _detect_format,
    _parse_format1_table,
    _parse_format2_table,
    _split_format1_cell,
    find_question_page,
    normalize,
    parse_question,
    parse_question_from_table,
)
from pdf_page import locate_question_page, needs_two_pages

PAGE_BOTTOM_RATIO = 0.70


def count_options(parsed):
    if not parsed:
        return 0
    return sum(
        1
        for l in "ABCD"
        if parsed.get(f"odp_{l.lower()}") and str(parsed[f"odp_{l.lower()}"]).strip()
    )


def merge_parse_results(base, extra):
    """Scala wynik ze strony N i kontynuacji na N+1."""
    if not base:
        return extra
    if not extra:
        return base

    merged = dict(base)
    bq = (base.get("pytanie") or "").strip()
    eq = (extra.get("pytanie") or "").strip()
    if eq:
        if not bq:
            merged["pytanie"] = eq
        elif eq.startswith(bq) or bq in eq:
            merged["pytanie"] = eq
        elif bq.startswith(eq):
            pass
        elif len(eq) > 20 and bq not in eq:
            merged["pytanie"] = (bq + " " + eq).strip()

    for letter in "ABCD":
        key = f"odp_{letter.lower()}"
        bv = (merged.get(key) or "").strip()
        ev = (extra.get(key) or "").strip()
        if not bv and ev:
            merged[key] = ev
        elif bv and ev and ev not in bv and bv not in ev:
            merged[key] = (bv + " " + ev).strip()
        elif bv and ev and len(ev) > len(bv):
            merged[key] = ev

    if not merged.get("poprawna_odpowiedz") and extra.get("poprawna_odpowiedz"):
        merged["poprawna_odpowiedz"] = extra["poprawna_odpowiedz"]
    elif extra.get("poprawna_odpowiedz") and not base.get("poprawna_odpowiedz"):
        merged["poprawna_odpowiedz"] = extra["poprawna_odpowiedz"]

    return merged


def _parse_format1_continuation(filepath, page_num):
    """Odpowiedzi / dokończenie pytania na stronie bez numeru pytania w wierszu."""
    import pdfplumber

    with pdfplumber.open(filepath) as pdf:
        if page_num >= len(pdf.pages):
            return None
        page = pdf.pages[page_num]
        tables = page.find_tables()
        if not tables:
            return None
        best_table = max(tables, key=lambda t: len(t.extract() or []))
        data = best_table.extract()
        if not data:
            return None
        fmt = _detect_format(data)

        answers = {}
        question_lines = []
        correct = None

        for row in data:
            if not row:
                continue
            col0 = normalize(row[0] or "")
            if re.match(r"^\d+[\.)]?\s*$", col0) or re.match(r"^\d+\s", col0):
                continue

            if fmt == "format1_6col":
                cells = [(row[4] or "").strip(), (row[5] or "").strip()]
            else:
                cells = [(row[2] or "").strip(), (row[3] or "").strip() if len(row) > 3 else ""]

            for cell in cells:
                if not cell:
                    continue
                lines = cell.split("\n")
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    m = re.match(r"^([a-dA-D])[\)\.]\s*(.+)", line)
                    if m:
                        answers[m.group(1).upper()] = m.group(2).strip()
                    elif not re.match(r"^[a-dA-D][\)\.]", line) and not answers:
                        question_lines.append(line)

            correct_cell = cells[-1] if cells else ""
            for c in (correct_cell or "").split():
                cu = c.strip().upper()
                if cu in ("A", "B", "C", "D"):
                    correct = cu

        if not answers and not question_lines:
            return None

        return {
            "nr": None,
            "pytanie": " ".join(question_lines).strip() or None,
            "odp_a": answers.get("A"),
            "odp_b": answers.get("B"),
            "odp_c": answers.get("C"),
            "odp_d": answers.get("D"),
            "poprawna_odpowiedz": correct,
        }


def _parse_format2_continuation(filepath, page_num, target_num):
    """Wiersze odpowiedzi na następnej stronie (bez nowego numeru pytania)."""
    import pdfplumber

    with pdfplumber.open(filepath) as pdf:
        if page_num >= len(pdf.pages):
            return None
        page = pdf.pages[page_num]
        tables = page.find_tables()
        if not tables:
            return None
        best_table = max(tables, key=lambda t: len(t.extract() or []))
        data = best_table.extract()
        if not data:
            return None

        words = page.extract_words(x_tolerance=2)
        answers = {}
        correct = None
        question_extra = ""

        for i, row in enumerate(data):
            if not row:
                continue
            col0 = normalize(row[0] or "")
            col1 = normalize(row[1] or "") if len(row) > 1 else ""
            col3 = normalize(row[3] or "") if len(row) > 3 else ""

            num_match = re.match(r"(\d+)", col0)
            if num_match and col1:
                found = int(num_match.group(1))
                if found != target_num:
                    break
                if found == target_num:
                    continue

            if col1:
                ans_match = re.match(r"^([a-dA-D])[\)\.]?\s*(.*)", col1)
                if ans_match:
                    letter = ans_match.group(1).upper()
                    from parser_pdf_plumber import _cell_words

                    ans_text = ans_match.group(2).strip()
                    if not ans_text:
                        ans_text = _cell_words(page, words, best_table, i, 1)
                        ans_text = re.sub(r"^[a-dA-D][\)\.]?\s*", "", ans_text).strip()
                    if ans_text:
                        answers[letter] = ans_text
                elif not answers and len(col1) > 15:
                    question_extra += " " + col1

            for c in col3.split():
                cu = c.strip().upper()
                if cu in ("A", "B", "C", "D"):
                    correct = cu

        if not answers and not question_extra:
            return None

        return {
            "nr": target_num,
            "pytanie": question_extra.strip() or None,
            "odp_a": answers.get("A"),
            "odp_b": answers.get("B"),
            "odp_c": answers.get("C"),
            "odp_d": answers.get("D"),
            "poprawna_odpowiedz": correct,
        }


def _needs_two_pages_fitz(filepath, page_num, nr_pytania, pytanie_hint):
    try:
        doc = fitz.open(filepath)
        try:
            pn, anchor_y0, all_qnums = locate_question_page(
                doc, nr_pytania, pytanie_hint
            )
            if pn is None:
                pn = page_num
            if anchor_y0 is None:
                page_h = doc[page_num].rect.height
                anchor_y0 = page_h * 0.5
            return needs_two_pages(doc, pn, anchor_y0, nr_pytania, all_qnums)
        finally:
            doc.close()
    except Exception:
        return False


def should_try_cross_page(
    parsed,
    filepath,
    page_num,
    table_fmt,
    nr_pytania,
    pytanie_hint,
    db_option_count=None,
):
    if page_num is None:
        return False
    opts = count_options(parsed)
    if db_option_count is not None and opts < db_option_count:
        return True
    if opts >= 4 and parsed.get("poprawna_odpowiedz"):
        return False
    if opts < 2:
        return True
    if not parsed.get("poprawna_odpowiedz"):
        return True
    if table_fmt in ("format1_4col", "format1_6col"):
        if _needs_two_pages_fitz(filepath, page_num, nr_pytania, pytanie_hint):
            return True
    if table_fmt == "format2" or table_fmt not in ("format1_4col", "format1_6col"):
        if _needs_two_pages_fitz(filepath, page_num, nr_pytania, pytanie_hint):
            return True
    return opts < 3


def _is_kapitan_pdf(filepath):
    p = (filepath or "").replace("\\", "/").lower()
    return "kapitan" in p


def _kapitan_page_span(filepath, nr_pytania, pytanie_hint=None):
    """Strony PDF: treść pytania (hint) + do 2 kolejnych stron na odpowiedzi."""
    import pdfplumber

    hint = (pytanie_hint or "").strip()
    with pdfplumber.open(filepath) as pdf:
        n = len(pdf.pages)
        if hint and len(hint) >= 15:
            needle = hint[: min(60, len(hint))].lower()
            for i, page in enumerate(pdf.pages):
                if needle in (page.extract_text() or "").lower():
                    return list(range(i, min(n, i + 3)))

        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if re.search(rf"(?:^|\n){nr_pytania}\s*\.", text):
                return list(range(max(0, i - 1), min(n, i + 3)))
            if re.search(rf"\n{nr_pytania}\s*\.?\s*[a-dA-D]", text):
                return list(range(max(0, i - 1), min(n, i + 3)))
        return []


def _harvest_answers_from_tables(filepath, page_nums, nr_pytania):
    """Opcje a–d z wierszy tabeli bez numeru pytania w col0 (typowy Kapitan cross-page)."""
    import pdfplumber

    answers = {}
    correct = None

    with pdfplumber.open(filepath) as pdf:
        for pn in page_nums:
            if pn >= len(pdf.pages):
                continue
            page = pdf.pages[pn]
            for table in page.find_tables() or []:
                data = table.extract() or []
                for row in data:
                    if not row:
                        continue
                    col0 = normalize(row[0] or "")
                    col1 = normalize(row[1] or "") if len(row) > 1 else ""
                    col2 = (row[2] or "").strip() if len(row) > 2 else ""
                    col3 = normalize(row[3] or "") if len(row) > 3 else ""

                    m0 = re.match(r"^(\d+)", col0)
                    if m0:
                        n = int(m0.group(1))
                        if n >= nr_pytania + 1:
                            return answers, correct
                        continue

                    if col0 and re.match(r"^\d", col0):
                        continue

                    am = re.match(r"^([a-dA-D])[\)\.]?\s*(.*)", col1)
                    if not am:
                        continue
                    letter = am.group(1).upper()
                    body = am.group(2).strip() or col2
                    if body and letter not in answers:
                        answers[letter] = body
                    for c in col3.split():
                        cu = c.strip().upper()
                        if cu in ("A", "B", "C", "D"):
                            correct = cu

    return answers, correct


def _harvest_correct_from_tables(filepath, page_nums, nr_pytania):
    _, correct = _harvest_answers_from_tables(filepath, page_nums, nr_pytania)
    return correct


def _text_from_hint(text, pytanie_hint):
    """Odetnij wcześniejsze pytania na tej samej stronie (np. Q36 przed Q37)."""
    hint = (pytanie_hint or "").strip()
    if len(hint) < 15:
        return text
    needle = hint.rstrip(":")[: min(60, len(hint))].lower()
    idx = (text or "").lower().find(needle)
    if idx >= 0:
        return text[idx:]
    return text


def _parse_answers_from_text(
    text, nr_pytania, pytanie_hint=None, continuation_only=False
):
    """Wyciąga opcje a–d z tekstu; bez wcześniejszych pytań na stronie."""
    from parser_pdf_plumber import _build_from_block

    work = text or ""
    if continuation_only:
        started = False
    else:
        work = _text_from_hint(work, pytanie_hint)
        started = bool(pytanie_hint and len((pytanie_hint or "").strip()) >= 15)

    lines = [normalize(l) for l in work.split("\n") if l.strip()]
    answers = {}
    correct = None

    for line in lines:
        nm = re.match(r"^(\d+)[\.)]?\s*$", line)
        if nm and int(nm.group(1)) >= nr_pytania + 1:
            break
        m2 = re.match(r"^(\d+)\.\s", line)
        if m2 and int(m2.group(1)) >= nr_pytania + 1:
            break

        if not started:
            if re.match(rf"^{nr_pytania}\.?\s*$", line, re.IGNORECASE):
                started = True
                continue
            if re.match(
                rf"^{nr_pytania}\.\s+[a-dA-D][\)\.]",
                line,
                re.IGNORECASE,
            ):
                started = True
            else:
                continue

        m = re.match(
            rf"^{nr_pytania}\.\s+([a-dA-D])[\)\.]?\s*(.+)",
            line,
            re.IGNORECASE,
        )
        if m:
            answers[m.group(1).upper()] = m.group(2).strip()
            continue

        if re.match(r"^([A-D])$", line.strip(), re.IGNORECASE):
            correct = line.strip().upper()
            continue

        am = re.match(r"^([a-dA-D])[\)\.]\s*(.+)", line)
        if am:
            letter = am.group(1).upper()
            if (
                continuation_only
                and letter == "A"
                and "A" not in answers
                and answers
            ):
                break
            answers[letter] = am.group(2).strip()

    if not answers:
        ans_lines = []
        block_started = started
        for line in lines:
            if re.match(rf"^{nr_pytania}[\.)]?\s*$", line, re.IGNORECASE):
                block_started = True
                continue
            if not block_started:
                continue
            nm = re.match(r"^(\d+)[\.)]?\s*$", line)
            if nm and int(nm.group(1)) >= nr_pytania + 1:
                break
            ans_lines.append(line)
        if not ans_lines:
            return None
        built = _build_from_block(nr_pytania, [f"{nr_pytania}."] + ans_lines)
        if built and not correct:
            correct = built.get("poprawna_odpowiedz")
        return built

    return {
        "nr": nr_pytania,
        "pytanie": "",
        "odp_a": answers.get("A"),
        "odp_b": answers.get("B"),
        "odp_c": answers.get("C"),
        "odp_d": answers.get("D"),
        "poprawna_odpowiedz": correct,
    }


def parse_kapitan_text_span(filepath, nr_pytania, pytanie_hint=None):
    """
    Fallback Kapitan: treść pytania (strona z hint) + odpowiedzi na kolejnych stronach.
    """
    pages = _kapitan_page_span(filepath, nr_pytania, pytanie_hint)
    if not pages:
        return None

    import pdfplumber

    hint = (pytanie_hint or "").strip()
    anchor = pages[0]
    answer_pages = pages[1:]

    if hint:
        needle = hint[: min(60, len(hint))].lower()
        with pdfplumber.open(filepath) as pdf:
            for i in pages:
                if needle in (pdf.pages[i].extract_text() or "").lower():
                    anchor = i
                    answer_pages = []
                    for p in pages:
                        if p <= i:
                            continue
                        t = pdf.pages[p].extract_text() or ""
                        answer_pages.append(p)
                        if re.search(rf"(?:^|\n){nr_pytania + 1}\s*\.", t):
                            break
                    break
        pytanie = hint.rstrip(":").strip()
    else:
        pytanie = ""

    anchor_text = ""
    after_text = ""
    with pdfplumber.open(filepath) as pdf:
        if not pytanie and anchor is not None:
            t = pdf.pages[anchor].extract_text() or ""
            pytanie = t[:500].strip()
        if anchor is not None:
            anchor_text = pdf.pages[anchor].extract_text() or ""
        for pn in answer_pages:
            after_text += "\n" + (pdf.pages[pn].extract_text() or "")

    table_pages = [p for p in (answer_pages or []) if p > anchor]
    tbl_ans, tbl_correct = _harvest_answers_from_tables(
        filepath, table_pages or answer_pages or pages, nr_pytania
    )

    txt_anchor = _parse_answers_from_text(
        anchor_text, nr_pytania, pytanie_hint=hint
    )
    txt_after = _parse_answers_from_text(
        after_text, nr_pytania, continuation_only=True
    )
    txt_parsed = txt_after
    if txt_anchor:
        if not txt_parsed:
            txt_parsed = txt_anchor
        else:
            for letter in "ABCD":
                k = f"odp_{letter.lower()}"
                if txt_anchor.get(k) and not txt_parsed.get(k):
                    txt_parsed[k] = txt_anchor[k]

    parsed = {
        "nr": nr_pytania,
        "pytanie": pytanie,
        "odp_a": tbl_ans.get("A"),
        "odp_b": tbl_ans.get("B"),
        "odp_c": tbl_ans.get("C"),
        "odp_d": tbl_ans.get("D"),
        "poprawna_odpowiedz": tbl_correct,
    }

    if txt_anchor:
        for letter in "ABCD":
            key = f"odp_{letter.lower()}"
            if txt_anchor.get(key):
                parsed[key] = txt_anchor[key]
    if txt_after:
        for letter in "ABCD":
            key = f"odp_{letter.lower()}"
            if txt_after.get(key) and not (parsed.get(key) or "").strip():
                parsed[key] = txt_after[key]

    if not any(parsed.get(f"odp_{l.lower()}") for l in "ABCD"):
        return None

    if hint:
        parsed["pytanie"] = pytanie

    if not parsed.get("poprawna_odpowiedz"):
        for src in (txt_anchor, txt_after):
            if src and src.get("poprawna_odpowiedz"):
                parsed["poprawna_odpowiedz"] = src["poprawna_odpowiedz"]
                break
    if not parsed.get("poprawna_odpowiedz"):
        for block in (_text_from_hint(anchor_text, hint), after_text):
            for line in (block or "").split("\n"):
                line = line.strip()
                if re.match(r"^([A-D])$", line, re.IGNORECASE):
                    parsed["poprawna_odpowiedz"] = line.upper()
                    break
            if parsed.get("poprawna_odpowiedz"):
                break

    all_pages = [anchor] + answer_pages
    parsed["cross_page"] = len(all_pages) > 1
    parsed["pages"] = all_pages
    parsed["nr"] = nr_pytania
    parsed["parse_mode"] = "kapitan_text_span"
    return parsed


def parse_question_multipage(filepath, nr_pytania, pytanie_hint=None, db_option_count=None):
    """
    Parsuje pytanie z PDF; przy cross-page scala stronę N i N+1.

    Zwraca dict z polami pytania lub None.
    Metadane: cross_page (bool), pages (list int).
    """
    if not filepath or nr_pytania is None:
        return None

    page_num, table_fmt = find_question_page(filepath, nr_pytania)

    if page_num is None and _is_kapitan_pdf(filepath):
        return parse_kapitan_text_span(filepath, nr_pytania, pytanie_hint)

    if page_num is None:
        return None

    parsed = parse_question_from_table(filepath, page_num, nr_pytania)

    if _is_kapitan_pdf(filepath) and (
        not parsed or count_options(parsed) < 2 or not (parsed.get("pytanie") or "").strip()
    ):
        kt = parse_kapitan_text_span(filepath, nr_pytania, pytanie_hint)
        if kt:
            parsed = merge_parse_results(parsed, kt) if parsed else kt
            parsed["cross_page"] = len(parsed.get("pages", [page_num])) > 1
            return parsed
    pages = [page_num]
    cross_page = False

    if not should_try_cross_page(
        parsed,
        filepath,
        page_num,
        table_fmt,
        nr_pytania,
        pytanie_hint,
        db_option_count=db_option_count,
    ):
        if parsed:
            parsed["cross_page"] = False
            parsed["pages"] = pages
        return parsed

    next_page = page_num + 1
    import pdfplumber

    with pdfplumber.open(filepath) as pdf:
        if next_page >= len(pdf.pages):
            if parsed:
                parsed["cross_page"] = False
                parsed["pages"] = pages
            return parsed

    cross_page = True
    pages.append(next_page)

    if _is_kapitan_pdf(filepath) and count_options(parsed) < (db_option_count or 3):
        extra_page = page_num + 2
        import pdfplumber

        with pdfplumber.open(filepath) as pdf:
            if extra_page < len(pdf.pages):
                pages.append(extra_page)
                kt = parse_kapitan_text_span(filepath, nr_pytania, pytanie_hint)
                if kt:
                    parsed = merge_parse_results(parsed, kt)
                    parsed["cross_page"] = True
                    parsed["pages"] = sorted(set(pages))
                    parsed["nr"] = nr_pytania
                    return parsed

    extra = parse_question_from_table(filepath, next_page, nr_pytania)
    if extra and extra.get("nr") == nr_pytania:
        parsed = merge_parse_results(parsed, extra)
    else:
        if table_fmt in ("format1_4col", "format1_6col"):
            cont = _parse_format1_continuation(filepath, next_page)
        else:
            cont = _parse_format2_continuation(filepath, next_page, nr_pytania)
        if cont:
            parsed = merge_parse_results(parsed, cont)

    if not parsed:
        return None

    parsed["cross_page"] = cross_page and len(pages) > 1
    parsed["pages"] = pages
    parsed["nr"] = nr_pytania
    return parsed
