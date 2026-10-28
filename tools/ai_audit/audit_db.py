"""Przeglad bazy pytan workflow v5 (L1 Luna -> L2 DeepSeek -> L3 Sonnet) z limitem kosztu.

  python audit_db.py --limit 20                      # proba na 20 losowych pytaniach (Pokład + Angielski)
  python audit_db.py --categories Dzia,Angiel        # cala baza (bez Master), limit kosztu domyslnie 5 USD
  python audit_db.py --categories Kapitan --cap 3    # Master, limit 3 USD

Wynik: Excel (../Przeglad_AI_<tag>.xlsx) + runs/audit_<tag>.json. Baza aplikacji jest tylko czytana.
Wznawianie: wywolania sa cache'owane (runs/cache_audit_<tag>.jsonl).
"""
import argparse
import json
import random
import sqlite3
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

import wf

HERE = Path(__file__).resolve().parent
import os

DB = os.environ.get("MEM_DB", str(Path.home() / "Documents" / "memonic_app.db"))  # baza aplikacji
PV = "v5"
IMG_DIR = HERE.parents[1] / "app" / "assets" / "question_images"


def load_items(cats, limit, seed, ordered=False, after_id=0, only_images=False, marker=None):
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    rows = []
    extra = " and image_path is not null" if only_images else ""
    if marker:
        extra += " and ai_verified like '" + marker.replace("'", "") + "%'"
    for r in c.execute("select * from questions where review_status = 'ok' and id > ?" + extra + " order by id", (after_id,)):
        if any(r["kategoria"].startswith(p) for p in cats):
            rows.append(r)
    if limit:
        if not ordered:
            random.Random(seed).shuffle(rows)
        rows = rows[:limit]
    items = []
    for r in rows:
        opts = {k.upper(): r["odp_" + k] for k in "abcd" if r["odp_" + k] is not None}
        items.append({"cid": str(r["id"]), "source_id": r["id"], "kategoria": r["kategoria"], "tematyka": r["tematyka"],
                      "pytanie": (r["pytanie"] or "").strip(), "opts": opts, "key": r["poprawna_odpowiedz"],
                      "label": {"defect": None},
                      "image": str(IMG_DIR / r["image_path"]) if r["image_path"] else None})
    return items


def sheet(wb, title, rows, cols):
    ws = wb.create_sheet(title)
    ws.append([c[0] for c in cols])
    for r in rows:
        ws.append([c[1](r) for c in cols])
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="305496")
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
    for i, c in enumerate(cols):
        ws.column_dimensions[chr(65 + i)].width = c[2]
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = ws.dimensions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--categories", default="Dzia,Angiel")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--after-id", type=int, default=0, help="zacznij od pytan o ID wiekszym niz")
    ap.add_argument("--ordered", action="store_true", help="pierwsze N pytan wg ID zamiast losowych")
    ap.add_argument("--cap", type=float, default=5.0, help="limit kosztu w USD")
    ap.add_argument("--chunk", type=int, default=100)
    ap.add_argument("--tag", default="probe")
    ap.add_argument("--marker", help="tylko pytania z ai_verified zaczynającym się od tego prefiksu, np. ai_authored")
    ap.add_argument("--only-images", action="store_true", help="tylko pytania z obrazkiem (obraz idzie do modeli)")
    a = ap.parse_args()

    items = load_items(a.categories.split(","), a.limit, a.seed, a.ordered, a.after_id, a.only_images, a.marker)
    print(f"{len(items)} pytań do przeglądu, limit kosztu ${a.cap}")
    results, spent = {}, 0.0
    for i in range(0, len(items), a.chunk):
        if spent >= a.cap:
            print(f"Limit kosztu osiągnięty (${spent:.2f}) - zatrzymano po {len(results)} pytaniach.")
            break
        part = items[i:i + a.chunk]
        out = wf.run(part, PV, f"audit_{a.tag}", True)
        results.update(out)
        spent += sum(o["cost"] for o in out.values())
        print(f"  {len(results)}/{len(items)}  koszt ${spent:.3f}", flush=True)

    def verdict(o):
        c = o["l2_conf"]
        if c == "integrity":
            return "integrity"
        if c == "figure":
            return "figure"
        l3 = (o.get("L3") or {}).get("verdict")
        if c in ("key", "weak") and l3 in ("DEFECT", "KEY_SUSPECT"):
            return "key" if l3 == "KEY_SUSPECT" else "integrity"
        return None

    flagged = {k: [] for k in ("integrity", "key", "figure")}
    for o in results.values():
        v = verdict(o)
        if v:
            flagged[v].append(o)

    def base(o):
        it = o["item"]
        return [it["source_id"], it["kategoria"], it["tematyka"], it["pytanie"]] + [it["opts"].get(k) for k in "ABCD"] + [it["key"]]

    common = [("ID", lambda o: o["item"]["source_id"], 8), ("Kategoria", lambda o: o["item"]["kategoria"], 14),
              ("Pytanie", lambda o: o["item"]["pytanie"], 55)] + \
             [(k, (lambda k: lambda o: o["item"]["opts"].get(k))(k), 28) for k in "ABCD"] + \
             [("Odp. w bazie", lambda o: o["item"]["key"], 9)]
    wb = Workbook()
    wb.remove(wb.active)
    sheet(wb, "Usterka tekstu", flagged["integrity"], common + [
        ("Typy usterek", lambda o: ", ".join(set((o["L1"].get("defects") or []) + ((o.get("L2") or {}).get("defects") or []) +
                                                 ((o.get("L3") or {}).get("defects") or []))), 22),
        ("Uwaga L1 (Luna)", lambda o: o["L1"].get("note"), 40),
        ("Uwaga L3 (Sonnet)", lambda o: (o.get("L3") or {}).get("reason"), 40)])
    sheet(wb, "Watpliwy klucz", flagged["key"], common + [
        ("Wg Sonneta", lambda o: (o.get("L3") or {}).get("best_answer"), 10),
        ("Uzasadnienie Sonneta", lambda o: (o.get("L3") or {}).get("reason"), 50),
        ("L2 (DeepSeek) odp.", lambda o: (o.get("L2") or {}).get("answer"), 10),
        ("L2 pewnosc", lambda o: (o.get("L2") or {}).get("confidence"), 10)])
    sheet(wb, "Wymaga rysunku", flagged["figure"], common + [("Uwaga L1", lambda o: o["L1"].get("note"), 40)])
    path = HERE.parents[1] / "review" / f"Przeglad_AI_{a.tag}.xlsx"
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    json.dump({k: {kk: vv for kk, vv in v.items() if kk != "item"} for k, v in results.items()},
              open(HERE / "runs" / f"audit_{a.tag}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Przejrzano {len(results)} pytań, koszt ${spent:.3f}. Oznaczone: usterka tekstu {len(flagged['integrity'])}, "
          f"watpliwy klucz {len(flagged['key'])}, rysunek {len(flagged['figure'])}. Zapisano {path}")


if __name__ == "__main__":
    main()
