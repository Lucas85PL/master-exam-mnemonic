"""Lista pytań, w których poprawna odpowiedź w bazie różni się od klucza w arkuszach PDF Urzędu Morskiego.
Wejście: review/Zgodnosc_z_PDF/compare_keys_report.json (wynik compare_keys.py) + baza (pełne treści).
Wyjście: PDF (legenda na górze każdej strony; zielony = baza, pomarańczowy = arkusze PDF) i kopia MD.
Użycie: python export_key_diffs.py [baza.db] [katalog_wyjściowy]"""
import difflib, html, json, re, sqlite3, sys
from pathlib import Path

import fitz

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DB = sys.argv[1] if len(sys.argv) > 1 else str(Path.home() / "Documents" / "memonic_app.db")
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "review" / "Zgodnosc_z_PDF"
OUT.mkdir(parents=True, exist_ok=True)
GREEN, ORANGE = "#1B7F3B", "#D9730D"

report = json.load(open(ROOT / "review" / "Zgodnosc_z_PDF" / "compare_keys_report.json", encoding="utf-8"))
diffs = sorted((x for x in report if x["status"] == "ROZNE"), key=lambda x: x["id"])
con = sqlite3.connect(f"file:{Path(DB).as_posix()}?mode=ro", uri=True)
con.row_factory = sqlite3.Row


def norm(s):
    return re.sub(r"[^\w]+", " ", (s or "").lower()).strip()


items = []
for d in diffs:
    r = con.execute("select * from questions where id=?", (d["id"],)).fetchone()
    if r is None or r["review_status"] != "ok":
        continue
    opts = {L: (r["odp_" + L.lower()] or "").strip() for L in "ABCD" if (r["odp_" + L.lower()] or "").strip()}
    db_letter = (r["poprawna_odpowiedz"] or "").strip().upper()
    if db_letter in (d.get("pdf") or []):
        continue  # ta sama litera i niemal ta sama treść (różnice tylko w zapisie: º/°, spacje, OCR l/I) — nie jest inną odpowiedzią
    # litera odpowiedzi z arkusza PDF w układzie wariantów bazy: dopasowanie po treści (a gdy brak — litera z PDF)
    pdf_txt = (d.get("pdf_tekst") or [""])[0]
    best, pdf_letter = 0.0, (d["pdf"][0] if d.get("pdf") else "?")
    for L, t in opts.items():
        s = difflib.SequenceMatcher(None, norm(t)[:90], norm(pdf_txt)).ratio()
        if s > best:
            best, pdf_letter = s, L
    if best < 0.6 or pdf_letter == db_letter:
        pdf_letter = d["pdf"][0] if d.get("pdf") else "?"
    items.append(dict(id=r["id"], q=(r["pytanie"] or "").strip(), opts=opts, db=db_letter, pdf=pdf_letter,
                      grupa=d["grupa"], plik=d.get("plik", ""), ai=r["ai_verified"] or ""))
print("pytań z inną odpowiedzią:", len(items))
# litery odpowiedzi z arkusza (w układzie wariantów bazy) — dla oznaczeń w aplikacji (tabela cmke_diff, patrz tools/ai_audit/deploy_cmke_diff.py)
json.dump({str(it["id"]): it["pdf"] for it in items}, open(OUT / "cmke_diffs.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ---------------- MD
md = ["# Pytania z inną poprawną odpowiedzią w bazie niż w arkuszach PDF", "",
      "Legenda: **🟩 zielony = poprawna odpowiedź w bazie pytań** · **🟧 pomarańczowy = poprawna odpowiedź w arkuszach PDF Urzędu Morskiego**", "",
      f"Liczba pytań: {len(items)}", ""]
for it in items:
    md += [f"### ID {it['id']} (z bazy pytań)", "", f"Pytanie: {it['q']}", ""]
    for L, t in it["opts"].items():
        if L == it["db"]:
            md.append(f"- ODP {L} - <span style=\"color:{GREEN}\">**{html.escape(t)}**</span> 🟩 _(baza)_")
        elif L == it["pdf"]:
            md.append(f"- ODP {L} - <span style=\"color:{ORANGE}\">**{html.escape(t)}**</span> 🟧 _(arkusz PDF)_")
        else:
            md.append(f"- ODP {L} - {t}")
    md.append("")
(OUT / "Pytania_inna_odpowiedz_baza_vs_pdf.md").write_text("\n".join(md), encoding="utf-8")

# ---------------- PDF (Story + legenda na każdej stronie)
css = f"""
body {{ font-family: sans-serif; font-size: 10pt; }}
.id {{ font-weight: bold; font-size: 11pt; margin: 0; padding-top: 9pt; }}
.q {{ margin: 2pt 0 2pt 0; }}
.o {{ margin: 0 0 0 12pt; }}
.g {{ color: {GREEN}; font-weight: bold; }}
.p {{ color: {ORANGE}; font-weight: bold; }}
"""
body = []
for it in items:
    body.append(f"<p class='id'>(ID {it['id']} - z bazy pytań)</p>")
    body.append(f"<p class='q'>Pytanie: {html.escape(it['q'])}</p>")
    for L, t in it["opts"].items():
        cls = "g" if L == it["db"] else "p" if L == it["pdf"] else ""
        tag = " ✔ baza" if cls == "g" else " ✔ PDF" if cls == "p" else ""
        body.append(f"<p class='o'><span class='{cls}'>ODP {L} - {html.escape(t)}{tag}</span></p>")
story = fitz.Story(html="<body>" + "\n".join(body) + "</body>", user_css=css)
mb = fitz.paper_rect("a4")
TOP = 62
where = fitz.Rect(40, TOP, mb.width - 40, mb.height - 40)
pdf_tmp = OUT / "_tmp.pdf"
w = fitz.DocumentWriter(str(pdf_tmp))
more = 1
while more:
    dev = w.begin_page(mb)
    more, _ = story.place(where)
    story.draw(dev)
    w.end_page()
w.close()

doc = fitz.open(str(pdf_tmp))
legend = (f"<div style='font-family:sans-serif;font-size:9pt;'><b>Legenda:</b> "
          f"<span style='color:{GREEN};font-weight:bold'>zielony, pogrubiony = poprawna odpowiedź w bazie pytań</span> &nbsp;|&nbsp; "
          f"<span style='color:{ORANGE};font-weight:bold'>pomarańczowy, pogrubiony = poprawna odpowiedź w arkuszach PDF (Urząd Morski)</span></div>")
for i, page in enumerate(doc, 1):
    page.draw_rect(fitz.Rect(30, 22, mb.width - 30, 52), color=(0.7, 0.7, 0.7), fill=(0.96, 0.96, 0.96), width=0.5)
    page.insert_htmlbox(fitz.Rect(36, 26, mb.width - 36, 50), legend)
    page.insert_htmlbox(fitz.Rect(mb.width - 120, mb.height - 30, mb.width - 40, mb.height - 12),
                        f"<div style='font-family:sans-serif;font-size:8pt;text-align:right'>str. {i} / {len(doc)}</div>")
final = OUT / "Pytania_inna_odpowiedz_baza_vs_pdf.pdf"
doc.save(str(final)); doc.close()
del w, story
try:
    pdf_tmp.unlink()
except OSError:
    pass
print("zapisano:", final)
