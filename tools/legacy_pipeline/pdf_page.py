"""
Render pełnych stron PDF dla Vision API (Kapitan full-page).
1 lub 2 strony gdy pytanie może być podzielone między stronami.
"""
import io
import os
import re

import fitz

from pdf_crop import _extract_lines, _find_pytanie_line_anchor, _parse_structure

PAGE_BOTTOM_RATIO = 0.70


def _get_scale():
    return float(os.getenv("VISION_PAGE_SCALE", "1.5"))


def _qnum_y_on_page(all_qnums, page_num, qnum):
    for qp, qy, _, qn, _ in all_qnums:
        if qp == page_num and qn == qnum:
            return qy
    return None


def locate_question_page(doc, nr_pytania=None, pytanie=None):
    """
    Zwraca (page_num, anchor_y0, all_qnums) lub (None, None, all_qnums).
    """
    lines = _extract_lines(doc)
    all_qnums, _, _, _, _ = _parse_structure(lines)

    anchor = _find_pytanie_line_anchor(lines, all_qnums, nr_pytania, pytanie)
    if anchor:
        return anchor[0], anchor[1], all_qnums

    if nr_pytania is not None:
        for qp, qy, _, qn, _ in all_qnums:
            if qn == nr_pytania:
                return qp, qy, all_qnums

    return None, None, all_qnums


def needs_two_pages(doc, page_num, anchor_y0, nr_pytania, all_qnums):
    if page_num + 1 >= len(doc):
        return False

    page_h = doc[page_num].rect.height
    in_bottom = anchor_y0 >= page_h * PAGE_BOTTOM_RATIO
    has_next_on_same = (
        nr_pytania is not None
        and _qnum_y_on_page(all_qnums, page_num, nr_pytania + 1) is not None
    )
    next_page = page_num + 1
    has_next_on_next = (
        nr_pytania is not None
        and _qnum_y_on_page(all_qnums, next_page, nr_pytania + 1) is not None
    )
    same_on_next = (
        nr_pytania is not None
        and _qnum_y_on_page(all_qnums, next_page, nr_pytania) is not None
    )

    if not has_next_on_same and (in_bottom or has_next_on_next or same_on_next):
        return True
    return False


def render_page_to_png(doc, page_num, scale=None):
    scale = scale or _get_scale()
    page = doc[page_num]
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
    return pix.tobytes("png")


def _page_cache_path(cache_dir, filepath, page_num):
    base = os.path.splitext(os.path.basename(filepath))[0]
    safe = re.sub(r'[^\w\-]+', "_", base)[:80]
    return os.path.join(cache_dir, f"{safe}_p{page_num:03d}.png")


def get_or_render_page(doc, filepath, page_num, cache_dir, page_cache):
    """Zwraca (png_bytes, path_on_disk). Używa page_cache dict (filepath, pn) -> bytes."""
    key = (os.path.normpath(filepath), page_num)
    if page_cache is not None and key in page_cache:
        return page_cache[key]

    os.makedirs(cache_dir, exist_ok=True)
    path = _page_cache_path(cache_dir, filepath, page_num)

    if os.path.isfile(path):
        with open(path, "rb") as f:
            data = f.read()
    else:
        data = render_page_to_png(doc, page_num)
        with open(path, "wb") as f:
            f.write(data)

    if page_cache is not None:
        page_cache[key] = (data, path)
    return data, path


def render_pages_at_nums(
    filepath,
    page_nums,
    cache_dir=None,
    page_cache=None,
):
    """Renderuje podane numery stron (0-based) jako lista PNG."""
    if not page_nums:
        return None, "", "no pages", []

    if not cache_dir:
        cache_dir = os.path.join(os.path.dirname(__file__), "vision_cache", "_pages")

    doc = fitz.open(filepath)
    try:
        pngs = []
        for pn in page_nums:
            if pn < 0 or pn >= len(doc):
                return None, "", f"invalid page {pn}", []
            data, _ = get_or_render_page(
                doc, filepath, pn, cache_dir, page_cache
            )
            pngs.append(data)
        tag = "1p" if len(pngs) == 1 else "2p"
        return pngs, tag, "", page_nums
    finally:
        doc.close()


def render_pages_for_question(
    filepath,
    nr_pytania=None,
    pytanie=None,
    cache_dir=None,
    page_cache=None,
):
    """
    Renderuje 1 lub 2 pełne strony PDF.

    Returns:
        (list[png_bytes], tag, warning, page_nums)
        tag: '1p' | '2p'
    """
    if not cache_dir:
        cache_dir = os.path.join(os.path.dirname(__file__), "vision_cache", "_pages")

    doc = fitz.open(filepath)
    try:
        page_num, anchor_y0, all_qnums = locate_question_page(
            doc, nr_pytania, pytanie
        )
        if page_num is None:
            return None, "", "anchor not found", []

        page_nums = [page_num]
        tag = "1p"
        if anchor_y0 is not None and needs_two_pages(
            doc, page_num, anchor_y0, nr_pytania, all_qnums
        ):
            page_nums.append(page_num + 1)
            tag = "2p"

        pngs = []
        for pn in page_nums:
            data, _ = get_or_render_page(
                doc, filepath, pn, cache_dir, page_cache
            )
            pngs.append(data)

        return pngs, tag, "", page_nums
    finally:
        doc.close()


def save_question_page_audit(cache_dir, question_id, png_list, tag):
    """Kopia stron wysłanych do API: {id}_1p.png lub złożony zapis."""
    import shutil

    os.makedirs(cache_dir, exist_ok=True)
    if len(png_list) == 1:
        path = os.path.join(cache_dir, f"{question_id}_{tag}.png")
        with open(path, "wb") as f:
            f.write(png_list[0])
        return path

    from PIL import Image

    images = [Image.open(io.BytesIO(b)) for b in png_list]
    width = max(im.width for im in images)
    height = sum(im.height for im in images)
    canvas = Image.new("RGB", (width, height), (255, 255, 255))
    y = 0
    for im in images:
        canvas.paste(im, (0, y))
        y += im.height
    path = os.path.join(cache_dir, f"{question_id}_{tag}.png")
    canvas.save(path, format="PNG")
    return path
