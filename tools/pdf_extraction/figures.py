"""Pytania z rysunkami w arkuszach PDF (tabela: Lp | [O/T] | tresc+warianty | litera).
Wiersz ma rysunek, gdy w komorce tresci leza osadzone obrazy rastrowe albo rysunki wektorowe (kształty >= 4x4 pt;
cienkie kreski/podkreslenia sa pomijane). Pojedynczy obraz rastrowy wyjmujemy z PDF w oryginale (save_native),
reszte (wektory, kilka obrazow, wektory + etykiety) renderujemy jako clip sumy grafik (render_crop, 300 dpi)."""
import re
import sys
from pathlib import Path

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pdf_table_dzial import parse_cell  # noqa: E402

DPI = 300
PAD = 3.0  # pt
MIN_SHAPE = 4.0  # pt


def _is_invisible(d):
    """Biale prostokaty bez obramowania (nakladki na tekst) tez nie sa rysunkiem."""
    fill = d.get("fill")
    if fill and len(fill) == 3 and all(c > 0.97 for c in fill) and not d.get("color"):
        return True
    return _is_highlight(fill)


def _is_highlight(fill):
    """Zolte zakreslenia i szare cieniowanie komorek (0.75) to nie rysunki."""
    if not fill or len(fill) != 3:
        return False
    return (fill[0] > 0.95 and fill[1] > 0.95 and fill[2] < 0.2) or all(abs(c - 0.75) < 0.02 for c in fill)


def image_questions(pdf):
    """[dict(nr, page, q, opts, correct, rects, xrefs, vec, pg, doc, cell)] dla wierszy z rysunkami."""
    doc = fitz.open(pdf)
    out = []
    for pi, page in enumerate(doc):
        info = page.get_image_info(xrefs=True)
        imgs = [fitz.Rect(i["bbox"]) for i in info]
        # zolte prostokaty to adnotacje (zakreslenia) w arkuszach, nie rysunki pytan
        drawings = [fitz.Rect(d["rect"]) for d in page.get_drawings() if not _is_invisible(d)]
        for t in page.find_tables().tables:
            data = t.extract()
            for row, vals in zip(t.rows, data):
                cells = [c for c in row.cells if c]
                if len(cells) < 4 or not vals:
                    continue
                num = re.fullmatch(r"(\d{1,3})\.?", (vals[0] or "").strip())
                if not num:
                    continue
                ci = max(range(len(row.cells)), key=lambda i: (row.cells[i][2] - row.cells[i][0]) if row.cells[i] else -1)
                cell = fitz.Rect(row.cells[ci])
                inner = fitz.Rect(cell.x0 + 3, cell.y0 + 3, cell.x1 - 3, cell.y1 - 3)
                hit_i = [k for k, i in enumerate(imgs) if cell.x0 <= (i.x0 + i.x1) / 2 <= cell.x1
                         and cell.y0 <= (i.y0 + i.y1) / 2 <= cell.y1]
                vec = [r for r in drawings if inner.contains(r) and r.width >= MIN_SHAPE and r.height >= MIN_SHAPE]
                if not hit_i and not vec:
                    continue
                text = (vals[ci] or "").strip()
                if vec:
                    text = _text_outside(page, cell, union([imgs[k] for k in hit_i] + vec)) or text
                q, opts = parse_cell(text)
                letter = (vals[-1] or "").strip()
                m2 = re.fullmatch(r"([A-D])\d?", letter)  # np. "C1" - przypis/numer strony przy literze
                letter = m2.group(1) if m2 else letter
                out.append({"nr": int(num.group(1)), "page": pi + 1, "q": q, "opts": opts,
                            "correct": letter if letter in list("ABCD") else "",
                            "rects": [imgs[k] for k in hit_i], "xrefs": [info[k]["xref"] for k in hit_i],
                            "vec": vec, "pg": page, "doc": doc, "cell": cell})
    return out


def _text_outside(page, cell, u):
    """Tekst komorki bez etykiet leżacych wewnatrz rysunku (np. numery rzedow na rysunku kontenerowca)."""
    lines = []
    for b in page.get_text("dict", clip=cell)["blocks"]:
        for ln in b.get("lines", []):
            t = "".join(sp["text"] for sp in ln["spans"]).strip()
            lb = fitz.Rect(ln["bbox"])
            if t and re.fullmatch(r"[-\d\s.,]+", t):
                continue  # same liczby = podzialki/etykiety rysunku
            if t and not (u.x0 <= (lb.x0 + lb.x1) / 2 <= u.x1 and u.y0 + 1 < (lb.y0 + lb.y1) / 2 < u.y1 - 1):
                lines.append(t)
    return "\n".join(lines)


def union(rects):
    r = fitz.Rect(rects[0])
    for x in rects[1:]:
        r |= x
    return r


def render_crop(q, path):
    """PNG: suma grafik wiersza (obrazy + wektory) z marginesem, w DPI. Zwraca prostokat."""
    page = q["pg"]
    u = union(q["rects"] + q["vec"])
    pad = 0 if (len(q["rects"]) == 1 and not q["vec"]) else PAD
    r = fitz.Rect(u.x0 - pad, u.y0 - pad, u.x1 + pad, u.y1 + pad) & fitz.Rect(q["cell"])
    # linie tekstu pytania/wariantow lezace nad/pod rysunkiem nie wchodza do kadru (etykiety wewnatrz rysunku zostaja)
    for b in page.get_text("blocks", clip=fitz.Rect(q["cell"])):
        for ln in page.get_text("dict", clip=fitz.Rect(b[:4]))["blocks"]:
            for line in ln.get("lines", []):
                if not "".join(sp["text"] for sp in line["spans"]).strip():
                    continue  # puste linie (spacje) nie sa trescia
                lb = fitz.Rect(line["bbox"])
                cy = (lb.y0 + lb.y1) / 2
                if cy <= u.y0 + 0.5 and lb.y1 > r.y0:
                    r.y0 = lb.y1
                elif cy >= u.y1 - 0.5 and lb.y0 < r.y1:
                    r.y1 = lb.y0
    page.get_pixmap(dpi=DPI, clip=r, annots=False).save(str(path))
    return r


def native_ok(doc, xref):
    """Oryginal obrazu mozna zapisac bez ryzyka przekłamania kolorow: zwykly RGB/Gray, bez maski i bez palety/stencilu."""
    obj = doc.xref_object(xref)
    if "/ImageMask true" in obj or "/SMask" in obj or "/Mask" in obj:
        return False
    return "/DeviceRGB" in obj or "/DeviceGray" in obj


def save_native(doc, xref, path):
    """Zapisuje oryginalny obraz z PDF (bez tekstu z sasiedztwa)."""
    from PIL import Image
    pix = fitz.Pixmap(doc, xref)
    if (pix.colorspace and pix.colorspace.n > 3) or pix.alpha:
        pix = fitz.Pixmap(fitz.csRGB, pix)
    mode = "L" if pix.n == 1 else "RGB"
    Image.frombytes(mode, (pix.width, pix.height), pix.samples).convert("RGB").save(str(path))


def save_figure(q, path):
    """Pojedynczy zwykly obraz rastrowy bez wektorow -> oryginal; w pozostalych przypadkach render clip."""
    if len(q["xrefs"]) == 1 and q["xrefs"][0] and not q["vec"] and native_ok(q["doc"], q["xrefs"][0]):
        try:
            save_native(q["doc"], q["xrefs"][0], path)
            return
        except Exception:
            pass
    render_crop(q, path)
