"""Wykrywanie powtarzajacych sie pytan, ktorych tresc rozni sie tylko redakcyjnie (OCR, interpunkcja, kolejnosc wariantow,
wersje arkuszy) - czego nie lapie dokladne porownanie tresci. ROJ modeli Claude Haiku 5.5 (OpenRouter) ocenia pary-kandydatow.

  1) kandydaci: podobienstwo trigramow tresci pytania i wariantow (bez zewnetrznych bibliotek) miedzy unikalnymi tresciami,
  2) kazda para trafia do 2 niezaleznych sedziow (Haiku 5.5, kolejnosc par zamieniona), 16 watkow rownolegle,
  3) para uznana za powtorzenie tylko gdy OBAJ sedziowie: to samo pytanie + ta sama poprawna odpowiedz,
  4) wynik: grupy (zbiory ID) + wskazanie ID kanonicznego, zapis runs/dups_<tag>.json i review/Duplikaty_swarm_<tag>.xlsx.

Baza jest tylko CZYTANA (uzyj kopii, gdy aplikacja jest uruchomiona):
  python dup_swarm.py --db <kopia.db> --tag run1 [--max-pairs 3000] [--min-stem 0.55] [--dry]"""
import argparse
import hashlib
import itertools
import json
import re
import sqlite3
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODEL = "anthropic/claude-haiku-5.5"


def load_key():
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("Brak OPENROUTER_API_KEY w .env")


def norm(s):
    return re.sub(r"[\W_]+", " ", (s or "").lower()).strip()


def grams(s, n=3):
    s = norm(s).replace(" ", "")
    return {s[i:i + n] for i in range(max(1, len(s) - n + 1))}


def jacc(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def load_items(db_path):
    c = sqlite3.connect(f"file:{Path(db_path).as_posix()}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    cols = {r[1] for r in c.execute("PRAGMA table_info(questions)")}
    rows = c.execute("SELECT q.*, s.streak_days AS sd, s.state AS st, s.repetitions AS reps FROM questions q "
                     "LEFT JOIN srs_cards s ON s.question_id = q.id WHERE q.review_status = 'ok' AND q.image_path IS NULL").fetchall()
    c.close()
    # unikalne tresci (dokladne duplikaty traktujemy jako jedna pozycje; cala grupa pozniej dziedziczy wynik)
    by_key = defaultdict(list)
    for r in rows:
        key = "|".join(norm(r[k]) for k in ("pytanie", "odp_a", "odp_b", "odp_c", "odp_d"))
        by_key[key].append(r)
    items = []
    for key, rs in by_key.items():
        rep = min(rs, key=lambda r: r["id"])
        opts = [rep["odp_" + l] for l in "abcd"]
        corr = opts["ABCD".index((rep["poprawna_odpowiedz"] or "A").upper())] or ""
        items.append({
            "key": key, "rep": rep["id"], "ids": sorted(r["id"] for r in rs), "kat": sorted({r["kategoria"] for r in rs}),
            "q": (rep["pytanie"] or "").strip(), "opts": [o for o in opts], "key_letter": (rep["poprawna_odpowiedz"] or "").upper(),
            "corr": corr, "reps": sum((r["reps"] or 0) for r in rs),
        })
    return items


def candidates(items, min_stem, max_pairs):
    stems = [grams(it["q"]) for it in items]
    alls = [grams(it["q"] + " " + " ".join(o or "" for o in it["opts"])) for it in items]
    corr = [grams(it["corr"]) for it in items]
    inv = defaultdict(list)
    for i, g in enumerate(stems):
        for t in g:
            inv[t].append(i)
    pairs = {}
    for i, g in enumerate(stems):
        cnt = defaultdict(int)
        for t in g:
            for j in inv[t]:
                if j > i:
                    cnt[j] += 1
        for j, c in cnt.items():
            if c / max(1, min(len(g), len(stems[j]))) < min_stem:
                continue
            sj = jacc(g, stems[j])
            aj = jacc(alls[i], alls[j])
            cj = jacc(corr[i], corr[j])
            # to samo pytanie: bardzo podobna tresc calosci albo (podobna tresc pytania i podobna poprawna odpowiedz)
            if aj >= 0.75 or (sj >= min_stem and cj >= 0.6 and aj >= 0.45):
                pairs[(i, j)] = (round(aj, 3), round(sj, 3), round(cj, 3))
    ranked = sorted(pairs.items(), key=lambda kv: -kv[1][0])[:max_pairs]
    return ranked


PROMPT = ("Jesteś redaktorem bazy pytań testowych na egzamin morski. Porównaj DWA pytania (A i B) i oceń, czy to to samo pytanie "
          "zapisane dwa razy (np. różnice OCR, interpunkcja, drobne różnice redakcyjne, inna kolejność wariantów). "
          "Uznaj za TO SAMO pytanie tylko wtedy, gdy: treść pytania ma to samo znaczenie, zestaw wariantów odpowiedzi ma to samo znaczenie "
          "(kolejność i litery mogą być inne) ORAZ poprawna odpowiedź jest tym samym wariantem co do znaczenia. "
          "Uznaj za RÓŻNE, jeśli różnią się liczby, wartości, nazwy, zaprzeczenie („nie”), przedmiot pytania, dowolny wariant co do znaczenia "
          "lub poprawna odpowiedź — nawet gdy tekst jest bardzo podobny. Bądź ostrożny: wątpliwość = różne. "
          'Zwróć WYŁĄCZNIE JSON: {"same_question":true|false,"same_correct_answer":true|false,"confidence":0-100,"difference":"max 1 zdanie"}')


TIEBREAK = PROMPT + (" UWAGA (rozstrzygnięcie): różnice czysto redakcyjne — literówki i błędy OCR (np. litera „o” zamiast „φ”), "
                     "skróty („pow.” = „powyżej”, „GT”), interpunkcja, cudzysłowy, formy gramatyczne („uczestniczy(-ą)” = „uczestniczą”), "
                     "dopiski w nawiasach, drobne różnice w szyku — NIE zmieniają znaczenia. Różne są dopiero pytania, w których zmienia się "
                     "wartość liczbowa, zakres, warunek, zaprzeczenie lub sens któregoś wariantu.")


def fmt(it, name):
    lines = [f"Pytanie {name}: {it['q']}"]
    for l, o in zip("ABCD", it["opts"]):
        if o:
            lines.append(f"  {l}) {o}" + ("   <- POPRAWNA" if l == it["key_letter"] else ""))
    return "\n".join(lines)


_lock = threading.Lock()


def judge(key, cache_path, a, b, swapped, prompt=None):
    prompt = prompt or PROMPT
    first, second = (b, a) if swapped else (a, b)
    ck = hashlib.md5(f"{MODEL}|{first['key']}|{second['key']}|{'' if prompt is PROMPT else prompt}".encode()).hexdigest()
    with _lock:
        if cache_path.exists():
            for line in cache_path.read_text(encoding="utf-8").splitlines():
                r = json.loads(line)
                if r["ck"] == ck:
                    return r["res"], 0.0
    body = {"model": MODEL, "max_tokens": 1500, "reasoning": {"effort": "low"}, "usage": {"include": True},
            "messages": [{"role": "system", "content": prompt},
                         {"role": "user", "content": fmt(first, "A") + "\n\n" + fmt(second, "B")}]}
    err = None
    for i in range(3):
        try:
            r = requests.post("https://openrouter.ai/api/v1/chat/completions",
                              headers={"Authorization": f"Bearer {key}"}, json=body, timeout=120)
            if r.status_code != 200:
                err = f"HTTP {r.status_code}"
                time.sleep(2 * (i + 1))
                continue
            d = r.json()
            txt = d["choices"][0]["message"]["content"] or ""
            res = json.loads(re.search(r"\{.*\}", txt, re.S).group(0))
            cost = (d.get("usage") or {}).get("cost") or 0
            with _lock:
                with cache_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({"ck": ck, "res": res, "cost": cost}, ensure_ascii=False) + "\n")
            return res, cost
        except Exception as e:  # noqa: BLE001
            err = repr(e)
            time.sleep(2 * (i + 1))
    return {"error": err}, 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--tag", default="run")
    ap.add_argument("--max-pairs", type=int, default=3000)
    ap.add_argument("--min-stem", type=float, default=0.55)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--cap", type=float, default=3.0, help="limit kosztu USD")
    ap.add_argument("--dry", action="store_true", help="tylko kandydaci, bez wywolan modelu")
    a = ap.parse_args()

    items = load_items(a.db)
    ranked = candidates(items, a.min_stem, a.max_pairs)
    print(f"unikalnych tresci: {len(items)}, par-kandydatow: {len(ranked)}")
    if a.dry:
        for (i, j), sc in ranked[:15]:
            print(sc, "|", items[i]["q"][:70], "|", items[j]["q"][:70])
        return
    key = load_key()
    cache = HERE / "runs" / f"cache_dups_{a.tag}.jsonl"
    cost = [0.0]
    verdicts = {}

    def work(job):
        (i, j), sc = job
        if cost[0] >= a.cap:
            return (i, j), None
        r1, c1 = judge(key, cache, items[i], items[j], False)
        r2, c2 = judge(key, cache, items[i], items[j], True)
        cost[0] += c1 + c2
        return (i, j), (r1, r2)

    with ThreadPoolExecutor(a.workers) as ex:
        for n, (pair, res) in enumerate(ex.map(work, ranked), 1):
            verdicts[pair] = res
            if n % 100 == 0:
                print(f"  {n}/{len(ranked)} koszt ${cost[0]:.3f}", flush=True)

    # polaczenia: obaj sedziowie TAK/TAK
    confirmed, uncertain, errors = [], [], 0
    for (i, j), res in verdicts.items():
        if res is None:
            continue
        r1, r2 = res
        if "error" in r1 or "error" in r2:
            errors += 1
            continue
        ok = all(r.get("same_question") is True and r.get("same_correct_answer") is True for r in (r1, r2))
        any_ok = any(r.get("same_question") is True and r.get("same_correct_answer") is True for r in (r1, r2))
        rec = {"a": items[i]["rep"], "b": items[j]["rep"], "score": dict(zip(("all", "stem", "correct"), dict(ranked)[(i, j)])),
               "diff": [r1.get("difference"), r2.get("difference")], "conf": [r1.get("confidence"), r2.get("confidence")]}
        if ok:
            confirmed.append(rec)
        elif any_ok:
            # rozstrzygniecie: trzeci sedzia (ten sam model, prompt z wyjasnieniem, ze roznice redakcyjne nie licza sie)
            r3, c3 = judge(key, cache, items[i], items[j], False, TIEBREAK)
            cost[0] += c3
            rec["tiebreak"] = r3.get("difference")
            if r3.get("same_question") is True and r3.get("same_correct_answer") is True:
                rec["via"] = "2 z 3 sedziow"
                confirmed.append(rec)
            else:
                uncertain.append(rec)
    # grupy (union-find po unikalnych tresciach, potem rozwiniecie do wszystkich ID)
    par = {}

    def find(x):
        par.setdefault(x, x)
        while par[x] != x:
            par[x] = par[par[x]]
            x = par[x]
        return x

    by_rep = {it["rep"]: it for it in items}
    for rec in confirmed:
        par[find(rec["a"])] = find(rec["b"])
    comps = defaultdict(set)
    for r in list(par):
        comps[find(r)].add(r)
    groups = []
    for reps in comps.values():
        ids = sorted(i for r in reps for i in by_rep[r]["ids"])
        canon = max(reps, key=lambda r: (by_rep[r]["reps"], -r))  # kanoniczny: ten z najwiekszym postepem, potem najnizsze ID
        groups.append({"canonical_id": canon, "ids": ids, "texts": [by_rep[r]["q"][:110] for r in sorted(reps)],
                       "kategorie": sorted({k for r in reps for k in by_rep[r]["kat"]})})
    out = {"model": MODEL, "pairs": len(ranked), "confirmed_pairs": len(confirmed), "uncertain_pairs": len(uncertain),
           "errors": errors, "cost_usd": round(cost[0], 4), "groups": groups, "uncertain": uncertain}
    (HERE / "runs" / f"dups_{a.tag}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"potwierdzonych par: {len(confirmed)}, niepewnych (1 sedzia): {len(uncertain)}, bledy API: {errors}, "
          f"grup: {len(groups)}, koszt ${cost[0]:.3f}")

    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Grupy powtorzen"
    ws.append(["ID kanoniczne", "Wszystkie ID", "Kategorie", "Tresc (pierwsze 110 znakow)"])
    for g in sorted(groups, key=lambda g: -len(g["ids"])):
        ws.append([g["canonical_id"], ", ".join(map(str, g["ids"])), ", ".join(g["kategorie"]), " || ".join(g["texts"])])
    ws2 = wb.create_sheet("Niepewne (1 sedzia)")
    ws2.append(["ID A", "ID B", "podobienstwo", "roznica wg sedziow", "pewnosc"])
    for u in uncertain:
        ws2.append([u["a"], u["b"], str(u["score"]), " | ".join(str(x) for x in u["diff"]), str(u["conf"])])
    path = ROOT / "review" / f"Duplikaty_swarm_{a.tag}.xlsx"
    wb.save(path)
    print("zapisano", path)


if __name__ == "__main__":
    main()
