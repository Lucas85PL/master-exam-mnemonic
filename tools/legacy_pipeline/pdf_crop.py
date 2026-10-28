"""
Wycina fragment PDF (jedna lub dwie strony) jako PNG do Vision API.
Używa struktury tabeli (jak parser format2 Kapitan): numer, treść, etykiety A–D, poprawna.
Obsługuje pytania rozcięte między stronami (cross-page stitch).
"""
import io
import re

import fitz
from PIL import Image

SCALE = 2.0
MAX_STRIP_HEIGHT_PX = 8000
MARGIN_TOP = 4
MARGIN_BOTTOM = 10
CLUSTER_GAP = 40
QNUM_MAX_DIST = 200
QTEXT_MAX_DIST = 320
ANS_TEXT_MAX_DIST = 45
CORRECT_MAX_DIST = 110


def normalize(text):
    return re.sub(r"\s+", " ", text.strip())


def clean_for_search(text):
    if not text:
        return ""
    text = re.sub(r"[^\w\s\-.,:;!?()ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_lines(doc):
    """Lista linii: page, y0, y1, x0, x1, text."""
    lines = []
    for pn in range(len(doc)):
        page = doc[pn]
        for block in page.get_text("dict")["blocks"]:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                text = "".join(s["text"] for s in line["spans"]).strip()
                if not text:
                    continue
                b = line["bbox"]
                lines.append({
                    "page": pn,
                    "y0": b[1],
                    "y1": b[3],
                    "x0": b[0],
                    "x1": b[2],
                    "text": normalize(text),
                })
    return lines


def _parse_structure(lines):
    """Zwraca elementy tabeli format2 (Kapitan) lub pusty zestaw."""
    all_qnums = []
    all_qtexts = []
    ans_labels = []
    ans_texts = []
    corrects = []

    for ln in lines:
        p, y0, x0, text = ln["page"], ln["y0"], ln["x0"], ln["text"]

        if re.match(r"^\d{1,3}\.?$", text) and x0 < 100:
            qnum = int(re.match(r"(\d+)", text).group(1))
            all_qnums.append((p, y0, ln["y1"], qnum, ln))

        elif re.match(r"^[a-dA-D][\)\.]?$", text) and 80 <= x0 <= 95:
            ans_labels.append((p, y0, ln["y1"], text[0].upper(), ln))

        elif re.match(r"^[A-D]$", text) and x0 > 400:
            corrects.append((p, y0, ln["y1"], text, ln))

        elif 65 <= x0 <= 90 and len(text) > 3:
            if not re.match(r"^\d{1,3}\.?$", text) and not re.match(r"^[a-dA-D][\)\.]?$", text):
                all_qtexts.append((p, y0, ln["y1"], text, ln))

        elif 95 <= x0 <= 350:
            ans_texts.append((p, y0, ln["y1"], x0, text, ln))

    return all_qnums, all_qtexts, ans_labels, ans_texts, corrects


def _merge_cross_page_clusters(clusters):
    if len(clusters) <= 1:
        return clusters
    merged = []
    i = 0
    while i < len(clusters):
        current = list(clusters[i])
        if i + 1 < len(clusters):
            nxt = clusters[i + 1]
            if current[0][0] != nxt[0][0]:
                last_letters = {l[3] for l in current}
                next_letters = {l[3] for l in nxt}
                if not last_letters.intersection(next_letters):
                    current.extend(nxt)
                    i += 1
        merged.append(current)
        i += 1
    return merged


def _build_label_clusters(ans_labels):
    clusters = []
    current = []
    for item in sorted(ans_labels, key=lambda x: (x[0], x[1])):
        if current:
            last = current[-1]
            if item[0] == last[0] and item[1] - last[1] < CLUSTER_GAP:
                current.append(item)
            else:
                clusters.append(current)
                current = [item]
        else:
            current = [item]
    if current:
        clusters.append(current)
    return _merge_cross_page_clusters(clusters)


def _qnum_for_cluster(cluster, all_qnums):
    cluster_page = cluster[0][0]
    cluster_y_min = min(c[1] for c in cluster)
    best_qnum = None
    best_qy = None
    best_dist = float("inf")
    for qp, qy, qy1, qnum, _ in all_qnums:
        if qp == cluster_page:
            dist = abs(qy - cluster_y_min)
            if dist < best_dist and dist < QNUM_MAX_DIST:
                best_dist = dist
                best_qnum = qnum
                best_qy = qy
    return best_qnum, best_qy


def _qtexts_for_cluster(cluster, all_qtexts):
    pages = {c[0] for c in cluster}
    cluster_y_min = min(c[1] for c in cluster)
    cluster_y_max = max(c[1] for c in cluster)
    hits = []
    for tp, ty0, ty1, text, ln in all_qtexts:
        if tp not in pages:
            continue
        dist = min(abs(ty0 - cluster_y_min), abs(ty0 - cluster_y_max))
        if dist < QTEXT_MAX_DIST:
            hits.append((dist, ty0, ty1, text, ln))
    hits.sort(key=lambda x: x[0])
    return hits


def _next_qnum_y(page, page_num, after_y, all_qnums):
    candidates = [
        qy for qp, qy, _, _, _ in all_qnums
        if qp == page_num and qy > after_y + 5
    ]
    return min(candidates) if candidates else None


def _qnum_entry(all_qnums, page_num, qnum):
    for qp, qy, qy1, qn, ln in all_qnums:
        if qp == page_num and qn == qnum:
            return qy, qy1, ln
    return None, None, None


def _find_cluster_for_qnum(clusters, all_qnums, nr_pytania):
    for cluster in clusters:
        qn, _ = _qnum_for_cluster(cluster, all_qnums)
        if qn == nr_pytania:
            return cluster
    return None


def _pick_cluster_by_text(clusters, all_qnums, all_qtexts, pytanie):
    if not pytanie:
        return None
    clean = clean_for_search(pytanie)
    for frag in [clean[:60], clean[:40], clean[:25]]:
        if len(frag) < 8:
            continue
        frag_l = frag.lower()
        for cluster in clusters:
            for _, _, _, text, _ in _qtexts_for_cluster(cluster, all_qtexts):
                if frag_l in text.lower():
                    return cluster
    return None


def _horizontal_clip(page, lines_in_range):
    """x0, x1 dla wiersza tabeli — prawie pełna szerokość, z marginesem."""
    if lines_in_range:
        x0 = min(ln["x0"] for ln in lines_in_range)
        x1 = max(ln["x1"] for ln in lines_in_range)
        x0 = max(0, x0 - 12)
        x1 = min(page.rect.width, max(x1 + 12, page.rect.width * 0.92))
    else:
        x0, x1 = 0, page.rect.width
    return x0, x1


def _page_content_bottom(pn, cluster, ans_texts, corrects):
    on_page = [c for c in cluster if c[0] == pn]
    label_bottom = max((c[2] for c in on_page), default=0)
    ans_bottom = 0
    for ap, _, ty1, _, _, _ in ans_texts:
        if ap != pn:
            continue
        for cp, cy0, cy1, _, _ in on_page:
            if cy0 <= ty1 + 5:
                ans_bottom = max(ans_bottom, ty1)
    corr_bottom = 0
    for cp, _, cy1, _, _ in corrects:
        if cp != pn:
            continue
        for lp, ly0, ly1, _, _ in on_page:
            if abs(cp - lp) == 0 and abs(cy1 - ly1) < CORRECT_MAX_DIST:
                corr_bottom = max(corr_bottom, cy1)
    return max(label_bottom, ans_bottom, corr_bottom)


def _regions_from_cluster(
    doc, cluster, all_qnums, all_qtexts, ans_texts, corrects, all_lines,
    qtext_anchor=None, nr_pytania=None,
):
    """
    Oblicz (page_num, clip_rect) dla klastra odpowiedzi.
    clip_rect: (x0, y0, x1, y1)
    """
    qnum, qnum_y = _qnum_for_cluster(cluster, all_qnums)

    pages = sorted({c[0] for c in cluster})
    qtext_hits = _qtexts_for_cluster(cluster, all_qtexts)

    if qtext_anchor:
        anchor_page, anchor_y0, anchor_y1, _, _ = qtext_anchor
        global_y_top = anchor_y0 - MARGIN_TOP
        if qnum_y is not None and qnum_y < anchor_y0 and anchor_y0 - qnum_y < 80:
            if nr_pytania is None or qnum == nr_pytania:
                global_y_top = qnum_y - MARGIN_TOP
    else:
        if qnum_y is None:
            return None, ""
        y_tops = [qnum_y]
        if qtext_hits:
            y_tops.extend(h[1] for h in qtext_hits)
        y_tops.append(min(c[1] for c in cluster))
        global_y_top = min(y_tops) - MARGIN_TOP

    ref_y = qtext_anchor[1] if qtext_anchor else (qnum_y or 0)
    ref_page = qtext_anchor[0] if qtext_anchor else pages[0]

    regions = []
    for idx, pn in enumerate(pages):
        page = doc[pn]
        page_h = page.rect.height

        if len(pages) == 1:
            y_top = max(0, global_y_top)
            content_bottom = _page_content_bottom(pn, cluster, ans_texts, corrects) + MARGIN_BOTTOM
            label_bottom = max((c[2] for c in cluster if c[0] == pn), default=0)
            next_y = _next_qnum_y(page, pn, label_bottom, all_qnums)
            if next_y is not None and next_y > label_bottom + 8:
                y_bottom = min(content_bottom, next_y - 3)
            else:
                y_bottom = content_bottom
            y_bottom = min(y_bottom, page_h)
        elif idx == 0:
            y_top = max(0, global_y_top)
            y_bottom = page_h
        else:
            y_top = 0
            y_bottom = _page_content_bottom(pn, cluster, ans_texts, corrects) + MARGIN_BOTTOM
            label_bottom = max((c[2] for c in cluster if c[0] == pn), default=0)
            qy, _, _ = _qnum_entry(all_qnums, pn, (qnum or 0) + 1)
            if qy is not None and qy > label_bottom + 12:
                y_bottom = min(y_bottom, qy - 3)
            else:
                next_y = _next_qnum_y(page, pn, 0, all_qnums)
                if next_y is not None and next_y > label_bottom + 12:
                    y_bottom = min(y_bottom, next_y - 3)
            y_bottom = min(y_bottom, page_h)

        lines_in_band = [
            ln for ln in all_lines
            if ln["page"] == pn and ln["y1"] >= y_top - 2 and ln["y0"] <= y_bottom + 2
        ]
        x0, x1 = _horizontal_clip(page, lines_in_band)
        regions.append((pn, (x0, y_top, x1, y_bottom)))

    tag = "2p" if len(regions) > 1 else "1p"
    return regions, tag


def _fallback_regions(doc, nr_pytania, pytanie):
    """Gdy brak klastra format2 — numer strukturalny + następny numer."""
    lines = _extract_lines(doc)
    all_qnums = []
    for ln in lines:
        if re.match(r"^\d{1,3}\.?$", ln["text"]) and ln["x0"] < 100:
            all_qnums.append((ln["page"], ln["y0"], ln["y1"], int(re.match(r"(\d+)", ln["text"]).group(1)), ln))

    candidates = [(p, y0, y1, ln) for p, y0, y1, qn, ln in all_qnums if qn == nr_pytania]
    if not candidates and pytanie:
        clean = clean_for_search(pytanie)
        for ln in lines:
            for frag in [clean[:50], clean[:30]]:
                if len(frag) >= 8 and frag.lower() in ln["text"].lower():
                    page_num = ln["page"]
                    next_y = _next_qnum_y(doc[page_num], page_num, ln["y0"], all_qnums)
                    y_top = max(0, ln["y0"] - MARGIN_TOP)
                    y_bot = next_y - 3 if next_y else min(doc[page_num].rect.height, ln["y1"] + 150)
                    page = doc[page_num]
                    band = [l for l in lines if l["page"] == page_num and l["y0"] >= y_top and l["y1"] <= y_bot + 50]
                    x0, x1 = _horizontal_clip(page, band)
                    return [(page_num, (x0, y_top, x1, y_bot))], "1p"
        return None, ""

    if not candidates:
        return None, ""

    if len(candidates) > 1 and pytanie:
        clean = clean_for_search(pytanie).lower()
        best = None
        best_score = -1
        for p, y0, y1, ln in candidates:
            score = 0
            for ol in lines:
                if ol["page"] == p and abs(ol["y0"] - y0) < QTEXT_MAX_DIST:
                    if clean[:30] in ol["text"].lower():
                        score += 10
            if score > best_score:
                best_score = score
                best = (p, y0, y1, ln)
        if best:
            candidates = [best]

    p, y0, y1, ln = candidates[0]
    page = doc[p]
    next_y = _next_qnum_y(page, p, y0, all_qnums)
    y_top = max(0, y0 - MARGIN_TOP)
    y_bot = (next_y - 3) if next_y else min(page.rect.height, y1 + 160)
    band = [l for l in lines if l["page"] == p and l["y0"] >= y_top - 5 and l["y1"] <= y_bot + 5]
    x0, x1 = _horizontal_clip(page, band)
    return [(p, (x0, y_top, x1, y_bot))], "1p"


def _cluster_near_qtext(cluster, qtext_page, qtext_y0):
    pages = {c[0] for c in cluster}
    if qtext_page not in pages and qtext_page - 1 not in pages:
        return False
    cymin = min(c[1] for c in cluster)
    cymax = max(c[1] for c in cluster)
    if abs(cymin - qtext_y0) < QTEXT_MAX_DIST or abs(cymax - qtext_y0) < QTEXT_MAX_DIST:
        return True
    if cymin >= qtext_y0 - 30 and cymin - qtext_y0 < 200:
        return True
    return False


def _find_pytanie_line_anchor(lines, all_qnums, nr_pytania, pytanie):
    """Szukaj treści pytania we wszystkich liniach (nie tylko kolumna qtext)."""
    if not pytanie:
        return None
    clean = clean_for_search(pytanie)
    best = None
    for frag in [clean[:70], clean[:50], clean[:35]]:
        if len(frag) < 10:
            continue
        fl = frag.lower()
        for ln in lines:
            text = ln["text"]
            if fl not in text.lower():
                continue
            if re.match(r"^[a-dA-D][\)\.]?$", text):
                continue
            if re.match(r"^\d{1,3}\.?$", text):
                continue
            score = len(frag) + min(len(text), 80)
            if len(text) > 40:
                score += 30
            if nr_pytania is not None:
                for qp, qy, _, qn, _ in all_qnums:
                    if qp == ln["page"] and qn == nr_pytania:
                        if abs(qy - ln["y0"]) < QTEXT_MAX_DIST:
                            score += 80
                        elif ln["y0"] > qy and ln["y0"] - qy < 120:
                            score += 40
            if best is None or score > best[0]:
                best = (score, ln["page"], ln["y0"], ln["y1"], text, ln)
    return best[1:] if best else None


def _cluster_after_anchor(clusters, page, anchor_y0):
    """Klastr etykiet A–D poniżej (lub tuż przy) treści pytania."""
    best_c = None
    best_d = float("inf")
    for c in clusters:
        on_page = [l for l in c if l[0] == page or l[0] == page + 1]
        if not on_page:
            continue
        cymin = min(l[1] for l in on_page)
        if cymin < anchor_y0 - 40:
            continue
        d = cymin - anchor_y0
        if 0 <= d < 250 and d < best_d:
            best_d = d
            best_c = c
    return best_c


def _best_cluster_for_question(clusters, all_qnums, all_qtexts, all_lines, nr_pytania, pytanie):
    """Najpierw dopasowanie treści pytania z bazy, potem numer."""
    qtext_anchor = _find_pytanie_line_anchor(all_lines, all_qnums, nr_pytania, pytanie)

    if qtext_anchor:
        tp, ty0, ty1, text, ln = qtext_anchor
        best_c = _cluster_after_anchor(clusters, tp, ty0)
        if best_c is None:
            candidates = [c for c in clusters if _cluster_near_qtext(c, tp, ty0)]
            if not candidates:
                candidates = clusters
            best_d = float("inf")
            for c in candidates:
                d = min(abs(l[1] - ty0) for l in c)
                if d < best_d:
                    best_d = d
                    best_c = c
        if best_c:
            return best_c, qtext_anchor

    if nr_pytania is not None:
        c = _find_cluster_for_qnum(clusters, all_qnums, nr_pytania)
        if c:
            return c, None

    if pytanie:
        c = _pick_cluster_by_text(clusters, all_qnums, all_qtexts, pytanie)
        if c:
            return c, None

    return None, None


def _compute_regions(doc, nr_pytania, pytanie):
    lines = _extract_lines(doc)
    all_qnums, all_qtexts, ans_labels, ans_texts, corrects = _parse_structure(lines)

    if not ans_labels:
        return _fallback_regions(doc, nr_pytania, pytanie)

    clusters = _build_label_clusters(ans_labels)
    cluster, qtext_anchor = _best_cluster_for_question(
        clusters, all_qnums, all_qtexts, lines, nr_pytania, pytanie
    )
    if cluster is None:
        return _fallback_regions(doc, nr_pytania, pytanie)

    return _regions_from_cluster(
        doc, cluster, all_qnums, all_qtexts, ans_texts, corrects, lines,
        qtext_anchor, nr_pytania,
    )


def _render_clip(page, clip, matrix):
    pix = page.get_pixmap(matrix=matrix, clip=fitz.Rect(clip))
    return Image.frombytes("RGB", [pix.width, pix.height], pix.samples)


def _stitch_images(images):
    if not images:
        raise ValueError("No images to stitch")
    if len(images) == 1:
        return images[0]
    width = max(im.width for im in images)
    total_h = sum(im.height for im in images)
    if total_h > MAX_STRIP_HEIGHT_PX:
        total_h = MAX_STRIP_HEIGHT_PX
    canvas = Image.new("RGB", (width, total_h), (255, 255, 255))
    y = 0
    for im in images:
        if y >= total_h:
            break
        h = min(im.height, total_h - y)
        if h < im.height:
            im = im.crop((0, 0, im.width, h))
        canvas.paste(im, (0, y))
        y += h
    return canvas


def render_question_strip(filepath, nr_pytania=None, pytanie=None):
    """
    Renderuje PNG paska pytania z PDF.

    Returns:
        (png_bytes, pages_tag, warning)
        pages_tag: '1p' | '2p'
        warning: '' lub komunikat (np. truncation)
    """
    doc = fitz.open(filepath)
    try:
        regions, tag = _compute_regions(doc, nr_pytania, pytanie)
        if not regions:
            return None, "", "anchor not found"

        matrix = fitz.Matrix(SCALE, SCALE)
        images = [_render_clip(doc[pn], clip, matrix) for pn, clip in regions]

        warning = ""
        if sum(im.height for im in images) > MAX_STRIP_HEIGHT_PX:
            warning = "strip truncated"

        stitched = _stitch_images(images)
        buf = io.BytesIO()
        stitched.save(buf, format="PNG")
        return buf.getvalue(), tag, warning
    finally:
        doc.close()


def save_strip_cache(cache_dir, question_id, png_bytes, tag):
    import os
    os.makedirs(cache_dir, exist_ok=True)
    suffix = f"_{tag}" if tag else ""
    path = os.path.join(cache_dir, f"{question_id}{suffix}.png")
    with open(path, "wb") as f:
        f.write(png_bytes)
    return path
