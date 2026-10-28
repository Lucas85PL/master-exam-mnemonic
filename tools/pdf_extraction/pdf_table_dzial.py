"""Ekstraktor pytan Dzial pokladowy/Angielski (format: Lp | O/T | tresc+warianty | litera) i
porownanie z baza aplikacji. Wynik: dzial_extract.json + raport."""
import hashlib, json, os, re, sqlite3, sys, unicodedata, collections
from pathlib import Path
import fitz

import os

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NEW = ROOT / "sources" / "pdf_urzad" / "Pokład_Dział"
OLD_ROOTS = [NEW]
DB = os.environ.get("MEM_DB", str(Path.home() / "Documents" / "memonic_app.db"))  # baza aplikacji (Windows)
OPT = re.compile(r"^\s*([a-dA-D])\s*[\)\.]\s*(.*)$")


def n(s):
    s = unicodedata.normalize("NFKD", s or "").lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def parse_cell(text):
    q, opts, cur = [], {}, None
    for line in text.split("\n"):
        m = OPT.match(line)
        if m and (m.group(1).lower() == chr(ord("a") + len(opts))):
            cur = m.group(1).upper(); opts[cur] = m.group(2).strip()
        elif cur:
            opts[cur] = (opts[cur] + " " + line.strip()).strip()
        else:
            q.append(line.strip())
    return " ".join(x for x in q if x), opts


def extract(pdf):
    out, cur = [], None
    for pi, page in enumerate(fitz.open(pdf)):
        for t in page.find_tables().tables:
            for row in t.extract():
                c = [(x or "").strip() for x in (row + [None] * 6)[:6]]
                num = re.fullmatch(r"(\d{1,3})\.?", c[0])
                if num:
                    q, opts = parse_cell(c[4])
                    cur = {"nr": int(num.group(1)), "ot": c[2], "q": q, "opts": opts,
                           "correct": c[5], "page": pi + 1, "raw": c[4]}
                    out.append(cur)
                elif cur and not c[0] and c[4] and not c[5]:
                    # kontynuacja tresci pytania (rozciete na strony)
                    cur["raw"] += "\n" + c[4]
                    cur["q"], cur["opts"] = parse_cell(cur["raw"])
                elif cur and not c[0] and c[5] and not cur["correct"]:
                    cur["correct"] = c[5]
    return out


def extract_text(pdf):
    """Wersja odporna na brak wykrytych tabel: parsuje strumien tekstu strony."""
    lines = []
    for pi, page in enumerate(fitz.open(pdf)):
        for ln in page.get_text().split("\n"):
            ln = ln.strip()
            if ln: lines.append((pi + 1, ln))
    out, cur, state = [], None, "seek"
    for pg, ln in lines:
        if re.fullmatch(r"\d{1,3}\.?", ln) and state in ("seek", "done"):
            cur = {"nr": int(ln.rstrip(".")), "ot": "", "q": "", "opts": {}, "correct": "", "page": pg, "raw": ""}
            out.append(cur); state = "ot"; continue
        if state == "ot":
            if re.fullmatch(r"[OTU]", ln): cur["ot"] = ln; state = "body"; continue
            state = "body"
        if state == "body":
            if re.fullmatch(r"[A-D]", ln):
                cur["correct"] = ln; state = "done"
                cur["q"], cur["opts"] = parse_cell(cur["raw"]); continue
            cur["raw"] += ("\n" if cur["raw"] else "") + ln
    return [q for q in out if q["correct"]]


def main():
    old = {md5(p): p for r in OLD_ROOTS for p in r.rglob("*.pdf")}
    res = {}
    for p in sorted(NEW.rglob("*.pdf")):
        o = old.get(md5(p))
        rel = str(p.relative_to(NEW))
        qt = extract(p); qx = extract_text(p)
        res[rel] = {"old": str(o.relative_to(HERE)) if o else None, "q": qt if len(qt) >= 0.85 * len(qx) else qx, "n_table": len(qt), "n_text": len(qx)}
        print(f"{rel[-62:]:62} tabela={res[rel]['n_table']:3} tekst={res[rel]['n_text']:3}")
    json.dump(res, open(HERE / "dzial_extract.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

if __name__ == "__main__":
    sys.exit(main())
