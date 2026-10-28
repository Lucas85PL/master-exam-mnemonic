"""Renderuje wszystkie wykryte rysunki do katalogu i sklada arkusze podgladu (3 kolumny) do kontroli wzrokowej.
  python contact_sheets.py <katalog_wyjsciowy>"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from figures import image_questions, save_figure  # noqa: E402
from list_figures import ROOT, sheets  # noqa: E402

W = 380


def tile(tag, nr, f):
    im = Image.open(f).convert("RGB")
    size = im.size
    s = min(1, W / im.width)
    im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))))
    c = Image.new("RGB", (W + 10, min(im.height, 230) + 16), "white")
    c.paste(im.crop((0, 0, im.width, 230)), (0, 16))
    ImageDraw.Draw(c).text((2, 2), f"{tag} nr{nr} {size}", fill="red")
    return c


def sheet(tiles, path, cols=3):
    rows = (len(tiles) + cols - 1) // cols
    hs = [max(t.height for t in tiles[r * cols:(r + 1) * cols]) for r in range(rows)]
    sh = Image.new("RGB", (cols * (W + 14), sum(hs) + 4 * rows), "#aaa")
    y = 0
    for r in range(rows):
        for c in range(cols):
            k = r * cols + c
            if k < len(tiles):
                sh.paste(tiles[k], (c * (W + 14), y))
        y += hs[r] + 4
    sh.save(path)


if __name__ == "__main__":
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    items = []
    for p in sheets():
        rel = p.relative_to(ROOT).as_posix()
        tag = ("EN" if rel.startswith("Ang") else ("PLz" if "zarz" in rel else "PLo")) + "-" + p.name[:5]
        for q in image_questions(p):
            f = out / f"{tag}_{q['page']}_{q['nr']}.png"
            save_figure(q, f)
            items.append((tag, q["nr"], f))
    print(len(items))
    for i in range(0, len(items), 12):
        sheet([tile(*it) for it in items[i:i + 12]], out / f"sheet{i // 12}.png")
