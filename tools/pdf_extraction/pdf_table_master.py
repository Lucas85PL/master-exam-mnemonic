"""Niezalezny ekstraktor pytan Master z PDF (find_tables).

Czyta strukture tabeli (Lp | Pytanie/litera | tresc | Odpowiedz), obsluguje
pytania rozciete na granicy stron (tresc na dole strony, warianty na gorze
nastepnej, numer dopiero w pierwszym wierszu wariantow).
Wynik: pdf_master_extract.json  {plik: [ {nr, q, opts, correct, page}, ... ]}
"""
import json
import re
import sys
from pathlib import Path

import fitz

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PDF_DIR = ROOT / "sources" / "pdf_urzad" / "Master"
LABEL = re.compile(r"^([a-dA-D])[\.\)]$")


def norm(s):
    return re.sub(r"\s+", " ", (s or "").replace("\u00ad", "")).strip()


def answer_letters(cell):
    return re.findall(r"(?<![A-Za-z])([A-D])(?![A-Za-z])", cell or "")


def extract(pdf):
    doc = fitz.open(pdf)
    qs, cur = [], None
    for pi, page in enumerate(doc):
        words = page.get_text("words")
        for t in page.find_tables().tables:
            rows = t.extract()
            ans_x = None
            for ri, row in enumerate(rows):
                c = [norm(x) for x in (row + [None] * 4)[:4]]
                if c[0].lower().startswith("l. p") or c[1].lower() == "pytanie":
                    ans_x = t.rows[ri].cells[3][0] if len(t.rows[ri].cells) > 3 and t.rows[ri].cells[3] else None
                    continue
                if c[0].lower().startswith("kapitan") or not (c[0] or c[1] or c[2]):
                    continue
                lab = LABEL.match(c[1])
                num = re.fullmatch(r"(\d{1,3})\.", c[0])
                if lab:
                    L = lab.group(1).upper()
                    if cur is None:
                        continue
                    if num and cur["nr"] is None:
                        cur["nr"] = int(num.group(1))
                    cur["opts"][L] = c[2]
                    got = answer_letters(c[3])
                    if not got and ans_x is not None:
                        y0, y1 = t.rows[ri].bbox[1], t.rows[ri].bbox[3]
                        got = [w[4].strip().upper() for w in words
                               if w[0] >= ans_x - 2 and y0 - 1 <= w[1] <= y1 and w[4].strip().upper() in "ABCD" and len(w[4].strip()) == 1]
                    if got:
                        cur["correct"].append(got[0])
                elif c[1]:
                    # tresc pytania (numer moze byc pusty - rozciete na strony)
                    if cur is not None and not cur["opts"] and not num and not c[0]:
                        # kontynuacja tresci poprzedniego wiersza
                        cur["q"] = norm(cur["q"] + " " + c[1])
                        continue
                    cur = {"nr": int(num.group(1)) if num else None, "q": c[1],
                           "opts": {}, "correct": [], "page": pi + 1}
                    qs.append(cur)
    return qs


def main():
    out = {}
    for pdf in sorted(PDF_DIR.glob("*.pdf")):
        qs = extract(pdf)
        for q in qs:
            q["correct"] = sorted(set(q["correct"]))
        out[pdf.name] = [q for q in qs if len(q["opts"]) >= 2]
        print(pdf.name, len(out[pdf.name]))
    (HERE / "pdf_master_extract.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8"
    )


if __name__ == "__main__":
    sys.exit(main())
