"""Wspolny kod dodawania autorskich pytan Master (AI) do bazy aplikacji i seeda:
 - warianty mieszane tak, by klucze mialy rownomierny rozklad,
 - kopie *.bak_<tag>_* przed zmiana (seed w data/), nowe ID = MAX+1 w obu bazach, karta SRS dla kazdego pytania,
 - ai_verified = ai_authored:<data>, zrodlo w zrodlo_pliku, plik do przegladu review/Nowe_pytania_Master_<data>_<tag>.md.
Uzycie: from authored_lib import Authored; a = Authored('2026-10-09', 'zestaw4'); a.add(...); a.commit()"""
import collections
import random
import shutil
import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DBS = {"app": Path.home() / "Documents" / "memonic_app.db", "seed": ROOT / "app" / "assets" / "db" / "memonic_app_seed.db"}
KAT = "Kapitan żeglugi wielkiej"


class Authored:
    def __init__(self, stamp, tag):
        self.stamp, self.tag, self.q = stamp, tag, []

    def add(self, tem, q, correct, wrong, src, image=None):
        assert len(wrong) == 3, q
        self.q.append({"tem": tem, "q": q, "opts": [correct] + wrong, "src": src, "image": image})

    def commit(self):
        # rownomierny rozklad kluczy: cykl A,B,C,D w losowej kolejnosci
        rng = random.Random(f"{self.stamp}{self.tag}")
        targets = ["ABCD"[i % 4] for i in range(len(self.q))]
        rng.shuffle(targets)
        items = []
        for it, t in zip(self.q, targets):
            wrong = it["opts"][1:]
            rng.shuffle(wrong)
            opts = wrong[:]
            opts.insert("ABCD".index(t), it["opts"][0])
            items.append({**it, "opts": opts, "key": t})
        first = None
        for label, path in DBS.items():
            bak = (ROOT / "data" if label == "seed" else path.parent) / (
                path.name + f".bak_{self.tag}_{time.strftime('%Y%m%d_%H%M%S')}")
            shutil.copy2(path, bak)
            db = sqlite3.connect(path)
            start = db.execute("SELECT MAX(id) FROM questions").fetchone()[0] + 1
            first = start if first is None else first
            assert start == first, "rozjazd numeracji ID między bazą aplikacji a seedem"
            now = int(time.time() * 1000)
            for k, it in enumerate(items):
                qid = start + k
                a, b, c, d = it["opts"]
                db.execute(
                    "INSERT INTO questions (id, kategoria, podkategoria, poziom, tematyka, nr_pytania, typ_pytania, pytanie, odp_a, odp_b, odp_c, odp_d,"
                    " poprawna_odpowiedz, poprawna_odpowiedz_tekst, zrodlo_pliku, review_status, review_notes, study_hidden, ai_verified, image_path)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (qid, KAT, None, None, it["tem"], None, "testowe", it["q"], a, b, c, d, it["key"],
                     dict(zip("ABCD", it["opts"]))[it["key"]], f"ai_authored:{it['src']}", "ok", f"ai_authored:{self.stamp}", 0,
                     f"ai_authored:{self.stamp}", it["image"]))
                db.execute("INSERT INTO srs_cards (question_id, repetitions, interval_days, ease_factor, due_ms, lapses, state, step)"
                           " VALUES (?,?,?,?,?,?,?,?)", (qid, 0, 0, 2.5, now, 0, 0, 0))
            db.commit()
            n = db.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
            db.close()
            print(label, "dodano", len(items), "ID od", start, "razem pytan", n, bak.name)
        lines = [f"# Nowe pytania Master (autorskie, {self.tag}) — WDROŻONE {self.stamp}\n"]
        for i, it in enumerate(items, 1):
            lines.append(f"## {i}. [{it['tem']}] {it['q']}" + (f"  _(rysunek: {it['image']})_" if it["image"] else ""))
            for l, o in zip("ABCD", it["opts"]):
                lines.append(f"- {'**' if l == it['key'] else ''}{l}) {o}{'** ✔' if l == it['key'] else ''}")
            lines.append(f"\nŹródło: {it['src']}\n")
        (ROOT / "review" / f"Nowe_pytania_Master_{self.stamp}_{self.tag}.md").write_text("\n".join(lines), encoding="utf-8")
        print("pytań:", len(items), "ID", first, "–", first + len(items) - 1, "rozkład kluczy:",
              dict(sorted(collections.Counter(i["key"] for i in items).items())))
