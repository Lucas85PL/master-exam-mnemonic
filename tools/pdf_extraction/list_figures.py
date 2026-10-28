"""Lista pytan z rysunkami we wszystkich arkuszach PDF + podglad kadrow (contact sheet) do kontroli wzrokowej."""
import sys
from pathlib import Path

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parent))
from figures import image_questions, save_figure  # noqa: E402

ROOT = Path(__file__).resolve().parents[2] / "sources" / "pdf_urzad"


def sheets():
    return sorted(p for p in ROOT.rglob("*.pdf") if not ("czno" in p.name and p.name.startswith("F1-P6")))


if __name__ == "__main__":
    tmp = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    total = 0
    for p in sheets():
        rel = str(p.relative_to(ROOT)).replace("\\", "/")
        qs = image_questions(p)
        total += len(qs)
        for q in qs:
            kind = "R" if (len(q["xrefs"]) == 1 and not q["vec"]) else ("V" if not q["xrefs"] else "M")
            print(f"{rel[:62]:62} p{q['page']:<2} nr{q['nr']:<3} {kind} vec={len(q['vec']):<4} img={len(q['xrefs'])} | {' '.join(q['q'].split())[:55]}")
            if tmp:
                tmp.mkdir(parents=True, exist_ok=True)
                save_figure(q, tmp / f"{abs(hash(rel)) % 10**6}_{q['page']}_{q['nr']}.png")
    print("razem", total)
