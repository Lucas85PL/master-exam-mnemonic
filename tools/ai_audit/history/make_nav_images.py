"""Rysunki do autorskich pytan (2026-10-07): znaki IALA (kardynalne N/E/S/W, specjalny, bezpiecznej wody)
i znaki dzienne COLREG (kula, cylinder, stozek, romb...). Rysowane programowo (PIL, supersampling), PNG na bialym tle
-> app/assets/question_images/. Uruchomienie: python make_nav_images.py [--preview katalog]"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[3] / "app" / "assets" / "question_images"
S = 4  # supersampling
BLACK, YELLOW, RED, WHITE = (20, 20, 20), (250, 204, 0), (214, 30, 30), (255, 255, 255)
SEA, SEA2 = (60, 120, 190), (40, 95, 160)


def canvas(w, h):
    return Image.new("RGB", (w * S, h * S), WHITE), None


def fin(im, w, h):
    return im.resize((w, h), Image.LANCZOS)


def cone(d, cx, top, h, w, up, fill=BLACK):
    """Stozek jako trojkat: up=True wierzcholek u gory."""
    if up:
        pts = [(cx, top), (cx - w / 2, top + h), (cx + w / 2, top + h)]
    else:
        pts = [(cx - w / 2, top), (cx + w / 2, top), (cx, top + h)]
    d.polygon([(x * S, y * S) for x, y in pts], fill=fill)


def ball(d, cx, cy, r, fill=BLACK):
    d.ellipse([(cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S], fill=fill)


def buoy(name, bands, topmark):
    """bands: lista kolorow od gory do dolu (lub 'stripes'); topmark: funkcja rysujaca znak szczytowy."""
    w, h = 260, 380
    im, _ = canvas(w, h)
    d = ImageDraw.Draw(im)
    cx = w / 2
    # woda
    d.rectangle([0, 300 * S, w * S, h * S], fill=SEA)
    d.rectangle([0, 300 * S, w * S, 312 * S], fill=SEA2)
    # korpus (trapez, slupowy)
    top_y, bot_y, tw, bw = 150, 312, 38, 54
    if bands == "stripes":
        # pionowe pasy czerwono-biale, przyciete do trapezu korpusu
        mask = Image.new("L", im.size, 0)
        ImageDraw.Draw(mask).polygon([((cx - tw / 2) * S, top_y * S), ((cx + tw / 2) * S, top_y * S),
                                      ((cx + bw / 2) * S, bot_y * S), ((cx - bw / 2) * S, bot_y * S)], fill=255)
        layer = Image.new("RGB", im.size, WHITE)
        ld = ImageDraw.Draw(layer)
        n = 8
        for i in range(n):
            x0 = cx - bw / 2 + i * bw / n
            ld.rectangle([x0 * S, top_y * S, (x0 + bw / n) * S, bot_y * S], fill=RED if i % 2 == 0 else WHITE)
        im.paste(layer, (0, 0), mask)
        d.line([((cx - tw / 2) * S, top_y * S), ((cx - bw / 2) * S, bot_y * S)], fill=BLACK, width=2 * S)
        d.line([((cx + tw / 2) * S, top_y * S), ((cx + bw / 2) * S, bot_y * S)], fill=BLACK, width=2 * S)
        d.line([((cx - tw / 2) * S, top_y * S), ((cx + tw / 2) * S, top_y * S)], fill=BLACK, width=2 * S)
    else:
        total = bot_y - top_y
        weights = bands[1]
        y = top_y
        for col, wt in zip(bands[0], weights):
            hh = total * wt
            y1 = y + hh
            def half(yy):
                return tw / 2 + (bw / 2 - tw / 2) * (yy - top_y) / total
            pts = [((cx - half(y)) * S, y * S), ((cx + half(y)) * S, y * S), ((cx + half(y1)) * S, y1 * S), ((cx - half(y1)) * S, y1 * S)]
            d.polygon(pts, fill=col)
            y = y1
        d.line([((cx - tw / 2) * S, top_y * S), ((cx - bw / 2) * S, bot_y * S)], fill=BLACK, width=2 * S)
        d.line([((cx + tw / 2) * S, top_y * S), ((cx + bw / 2) * S, bot_y * S)], fill=BLACK, width=2 * S)
        d.line([((cx - tw / 2) * S, top_y * S), ((cx + tw / 2) * S, top_y * S)], fill=BLACK, width=2 * S)
    # maszt / szkielet znaku szczytowego i latarnia
    d.line([(cx * S, 128 * S), (cx * S, top_y * S)], fill=BLACK, width=3 * S)
    d.rectangle([(cx - 7) * S, 118 * S, (cx + 7) * S, 132 * S], fill=(255, 255, 255), outline=BLACK, width=2 * S)
    topmark(d, cx)
    # fale
    for k in range(3):
        d.arc([(20 + k * 80) * S, 312 * S, (60 + k * 80) * S, 326 * S], 180, 360, fill=WHITE, width=2 * S)
    return fin(im, w, h)


def tm_cones(first_up, second_up):
    def f(d, cx):
        cone(d, cx, 28, 38, 46, first_up)
        cone(d, cx, 70, 38, 46, second_up)
    return f


def tm_sphere_red(d, cx):
    ball(d, cx, 74, 24, RED)


def tm_cross_yellow(d, cx):
    d.line([((cx - 24) * S, 50 * S), ((cx + 24) * S, 98 * S)], fill=YELLOW, width=9 * S)
    d.line([((cx + 24) * S, 50 * S), ((cx - 24) * S, 98 * S)], fill=YELLOW, width=9 * S)
    d.line([((cx - 24) * S, 50 * S), ((cx + 24) * S, 98 * S)], fill=BLACK, width=1 * S)


def buoys():
    return {
        "iala_polnocny.png": buoy("N", ([BLACK, YELLOW], [0.5, 0.5]), tm_cones(True, True)),
        "iala_poludniowy.png": buoy("S", ([YELLOW, BLACK], [0.5, 0.5]), tm_cones(False, False)),
        "iala_wschodni.png": buoy("E", ([BLACK, YELLOW, BLACK], [0.34, 0.32, 0.34]), tm_cones(True, False)),
        "iala_zachodni.png": buoy("W", ([YELLOW, BLACK, YELLOW], [0.34, 0.32, 0.34]), tm_cones(False, True)),
        "iala_specjalny.png": buoy("SP", ([YELLOW], [1.0]), tm_cross_yellow),
        "iala_bezpiecznej_wody.png": buoy("SW", "stripes", tm_sphere_red),
    }


def dayshape(items, h_total=None):
    """items: lista ('ball'|'cone_down'|'cone_up'|'diamond'|'cylinder') od gory do dolu; maszt jako linia."""
    w = 220
    gap, size = 14, 56
    h = 30 + len(items) * (size + gap) + 20
    im, _ = canvas(w, h)
    d = ImageDraw.Draw(im)
    cx = w / 2
    d.line([(cx * S, 6 * S), (cx * S, (h - 8) * S)], fill=(120, 120, 120), width=3 * S)
    y = 24
    for it in items:
        if it == "ball":
            ball(d, cx, y + size / 2, size / 2)
        elif it == "cone_down":
            cone(d, cx, y, size, size, False)
        elif it == "cone_up":
            cone(d, cx, y, size, size, True)
        elif it == "diamond":
            pts = [(cx, y), (cx + size / 2, y + size / 2), (cx, y + size), (cx - size / 2, y + size / 2)]
            d.polygon([(a * S, b * S) for a, b in pts], fill=BLACK)
        elif it == "cylinder":
            d.rectangle([(cx - size * 0.38) * S, y * S, (cx + size * 0.38) * S, (y + size) * S], fill=BLACK)
        y += size + gap
    return fin(im, w, h)


def shapes():
    return {
        "dzienny_kotwica.png": dayshape(["ball"]),
        "dzienny_nuc.png": dayshape(["ball", "ball"]),
        "dzienny_na_mieliznie.png": dayshape(["ball", "ball", "ball"]),
        "dzienny_ram.png": dayshape(["ball", "diamond", "ball"]),
        "dzienny_cbd.png": dayshape(["cylinder"]),
        "dzienny_zagl_silnik.png": dayshape(["cone_down"]),
        "dzienny_rybacki.png": dayshape(["cone_down", "cone_up"]),
        "dzienny_holowanie.png": dayshape(["diamond"]),
    }


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    allimg = {**buoys(), **shapes()}
    for name, im in allimg.items():
        im.save(OUT / name, optimize=True)
    print("zapisano", len(allimg), "rysunków")
    if "--preview" in sys.argv:
        prev = Path(sys.argv[sys.argv.index("--preview") + 1])
        prev.mkdir(parents=True, exist_ok=True)
        ims = list(allimg.values())
        W = sum(i.width for i in ims[:7]) + 80
        H = max(i.height for i in ims) * 2 + 20
        sh = Image.new("RGB", (W, H), "#999")
        x = y = 0
        for k, im in enumerate(ims):
            if k == 7:
                x, y = 0, H // 2
            sh.paste(im, (x, y))
            x += im.width + 10
        sh.save(prev / "nav_sheet.png")
