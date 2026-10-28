"""Weryfikacja pytań z nowych skanów egzaminów (review/Egzaminy_lokalna_baza.json), TYLKO lokalnie, baza aplikacji tylko do odczytu.

Etap A - duplikaty wzgledem bazy aplikacji (i miedzy partiami): kandydaci (trigramy), 2 sedziow Haiku 5.5 (kolejnosc zamieniona) + rozstrzygniecie.
         Duplikat = to samo pytanie (tresc + zestaw wariantow), niezaleznie od zgodnosci odpowiedzi.
Etap B - dla pozostalych: ROJ 3 sedziow Haiku 5.5 (reasoning medium): 2 "slepi" (warianty przetasowane, bez naszej odpowiedzi) + 1 weryfikator.
         Kazdy dostaje fragmenty przepisow (Kodeks morski, ustawa o pracy na morzu, ustawa o PKBWM) znalezione po slowach kluczowych.
Wynik: review/Weryfikacja_2026-10-12/wyniki.json, wyniki.xlsx, raport.md"""
import hashlib
import json
import random
import re
import sqlite3
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / "review" / "Weryfikacja_2026-10-12"
OUT.mkdir(parents=True, exist_ok=True)
MODEL = "anthropic/claude-haiku-5.5"
EFFORT = "medium"
CAP = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
DB = Path.home() / "Documents" / "memonic_app.db"
_lock = threading.Lock()
COST = [0.0]
CACHE = OUT / "cache.jsonl"
_cache = {}
if CACHE.exists():
    for line in CACHE.read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        _cache[r["ck"]] = r["res"]


def key():
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("brak klucza")


KEY = key()


def norm(s):
    return re.sub(r"[\W_]+", " ", (s or "").lower()).strip()


def grams(s, n=3):
    s = norm(s).replace(" ", "")
    return {s[i:i + n] for i in range(max(1, len(s) - n + 1))}


def jac(a, b):
    return len(a & b) / len(a | b) if a and b else 0.0


def call(system, user, tag):
    ck = hashlib.md5(f"{MODEL}|{EFFORT}|{system}|{user}|{tag}".encode()).hexdigest()
    with _lock:
        if ck in _cache:
            return _cache[ck]
    if COST[0] >= CAP:
        return {"error": "cap"}
    body = {"model": MODEL, "max_tokens": 6000, "reasoning": {"effort": EFFORT}, "usage": {"include": True},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    err = None
    for i in range(3):
        try:
            r = requests.post("https://openrouter.ai/api/v1/chat/completions",
                              headers={"Authorization": f"Bearer {KEY}"}, json=body, timeout=180)
            if r.status_code != 200:
                err = f"HTTP {r.status_code}"
                time.sleep(2 * (i + 1))
                continue
            d = r.json()
            txt = d["choices"][0]["message"]["content"] or ""
            res = json.loads(re.search(r"\{.*\}", txt, re.S).group(0))
            with _lock:
                COST[0] += (d.get("usage") or {}).get("cost") or 0
                _cache[ck] = res
                with CACHE.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({"ck": ck, "res": res}, ensure_ascii=False) + "\n")
            return res
        except Exception as e:  # noqa: BLE001
            err = repr(e)
            time.sleep(2 * (i + 1))
    return {"error": err}


# ---------- dane
rows = json.loads((ROOT / "review" / "Egzaminy_lokalna_baza.json").read_text(encoding="utf-8"))
for r in rows:
    r["opcje"] = {k: v for k, v in r["opcje"].items() if v}
con = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
dbq = []
for r in con.execute("SELECT id,kategoria,pytanie,odp_a,odp_b,odp_c,odp_d,poprawna_odpowiedz,study_hidden FROM questions"):
    d = dict(r)
    d["opcje"] = {k: d[f"odp_{k.lower()}"] for k in "ABCD" if d.get(f"odp_{k.lower()}")}
    d["_s"] = grams(d["pytanie"])
    d["_a"] = grams(d["pytanie"] + " " + " ".join(d["opcje"].values()))
    dbq.append(d)
for r in rows:
    r["_s"] = grams(r["pytanie"])
    r["_a"] = grams(r["pytanie"] + " " + " ".join(r["opcje"].values()))


def fmt(q, name, mark=None):
    lines = [f"Pytanie {name}: {q['pytanie']}"]
    for l, o in q["opcje"].items():
        lines.append(f"  {l}) {o}" + ("   <- ODPOWIEDŹ W ŹRÓDLE" if l == mark else ""))
    return "\n".join(lines)


DUP_PROMPT = ("Jesteś redaktorem bazy pytań testowych na egzamin morski. Porównaj DWA pytania (A i B) i oceń, czy to to samo pytanie "
              "zapisane dwa razy (różnice OCR, interpunkcja, drobne różnice redakcyjne, inna kolejność wariantów, inne litery wariantów). "
              "TO SAMO = ta sama treść pytania co do znaczenia ORAZ ten sam zestaw wariantów co do znaczenia. "
              "RÓŻNE = zmienia się liczba, wartość, nazwa, zaprzeczenie, przedmiot pytania, albo któryś wariant co do znaczenia, "
              "nawet gdy tekst jest bardzo podobny. Wątpliwość = RÓŻNE. Zgodność wskazanej odpowiedzi oceń osobno. "
              'Zwróć WYŁĄCZNIE JSON: {"same_question":true|false,"same_correct_answer":true|false,"difference":"max 1 zdanie"}')

# ---------- Etap A
cands = defaultdict(list)
for i, r in enumerate(rows):
    sc = []
    for d in dbq:
        s, a = jac(r["_s"], d["_s"]), jac(r["_a"], d["_a"])
        if a >= 0.5 or s >= 0.6:
            sc.append((max(a, s), d))
    sc.sort(key=lambda x: -x[0])
    cands[i] = [("db", d) for _, d in sc[:3]]
    # między partiami (wcześniejszy wiersz jest kanoniczny)
    for j in range(i):
        if rows[j]["partia"] != r["partia"] and jac(r["_a"], rows[j]["_a"]) >= 0.6:
            cands[i].append(("row", rows[j]))
print("pytań:", len(rows), "z kandydatami:", sum(1 for v in cands.values() if v), flush=True)


def dup_check(i):
    r = rows[i]
    best = None
    for kind, c in cands[i]:
        if kind == "db":
            other = {"pytanie": c["pytanie"], "opcje": c["opcje"]}
            mark_b = c["poprawna_odpowiedz"]
        else:
            other = {"pytanie": c["pytanie"], "opcje": c["opcje"]}
            mark_b = c.get("odpowiedz")
        vs = []
        for sw in (False, True):
            a_, b_ = (r, other) if not sw else (other, r)
            ma = r.get("odpowiedz") if not sw else mark_b
            mb = mark_b if not sw else r.get("odpowiedz")
            vs.append(call(DUP_PROMPT, fmt(a_, "A", ma) + "\n\n" + fmt(b_, "B", mb), "dup"))
        yes = [v.get("same_question") is True for v in vs]
        if all(yes) or (any(yes) and call(DUP_PROMPT + " Różnice redakcyjne, literówki OCR, skróty i interpunkcja NIE zmieniają znaczenia.",
                                           fmt(r, "A", r.get("odpowiedz")) + "\n\n" + fmt(other, "B", mark_b), "dup3").get("same_question") is True):
            best = {"typ": kind, "id": c["id"], "klucz_w_bazie": mark_b,
                    "ukryte": c.get("study_hidden") if kind == "db" else None,
                    "zgodna_odpowiedz": all(v.get("same_correct_answer") is True for v in vs)}
            break
    return i, best


dups = {}
with ThreadPoolExecutor(16) as ex:
    for n, (i, b) in enumerate(ex.map(dup_check, [i for i in range(len(rows)) if cands[i]]), 1):
        if b:
            dups[i] = b
        if n % 50 == 0:
            print(f"A {n} koszt ${COST[0]:.2f}", flush=True)
print("duplikatów:", len(dups), f"koszt ${COST[0]:.2f}", flush=True)

# ---------- Etap B: przepisy
SRC = {"Kodeks morski": ROOT / "review" / "Egzamin_2026-03-30" / "kodeks_morski.txt",
       "Ustawa o pracy na morzu": ROOT / "review" / "Egzamin_2026-03-30" / "src" / "pracy_na_morzu.txt",
       "Ustawa o PKBWM": ROOT / "review" / "Egzamin_2026-03-30" / "src" / "pkbwm.txt"}
arts = []
for name, p in SRC.items():
    if not p.exists():
        continue
    t = p.read_text(encoding="utf-8")
    parts = re.split(r"(?=\nArt\. \d+[a-z]?\. )", t)
    for ptxt in parts:
        m = re.match(r"\n(Art\. \d+[a-z]?)\. ", ptxt)
        if m and len(ptxt) > 80:
            arts.append((name, m.group(1), re.sub(r"\s+", " ", ptxt)[:1600]))
stop = set("który która które jest to na w z do od po dla oraz lub się nie jako przez czy że ich jego jej są być może gdy tylko".split())


def toks(s):
    return {w[:6] for w in norm(s).split() if len(w) > 3 and w not in stop}


art_t = [toks(a[2]) for a in arts]
df = defaultdict(int)
for ts in art_t:
    for w in ts:
        df[w] += 1


def excerpts(q):
    qt = toks(q["pytanie"] + " " + " ".join(q["opcje"].values()))
    sc = []
    for (name, art, txt), ts in zip(arts, art_t):
        s = sum(1.0 / (1 + df[w] ** 0.5) for w in qt & ts)
        sc.append((s, name, art, txt))
    sc.sort(key=lambda x: -x[0])
    return [x for x in sc[:3] if x[0] > 0.6]


SYS = ("Jesteś ekspertem prawa morskiego i bezpieczeństwa żeglugi (egzamin kapitański, poziom zarządzania, Polska). "
       "Odpowiadasz na podstawie obowiązującego stanu prawnego: Kodeks morski, ustawa o bezpieczeństwie morskim, ustawa o pracy na morzu, "
       "ustawa o PKBWM, ustawa o obszarach morskich, SOLAS, STCW, MLC 2006, MARPOL, COLREG, ISM, ISPS, LL 66, UNCLOS, dyrektywy UE (PSC 2009/16, 2002/59), "
       "Paris MoU, FAL, konwencje IMO. Pytania pochodzą z egzaminów z lat 2017-2024; jeśli przepis zmienił się od tamtej pory, oceń wg stanu obecnego i zaznacz to. "
       "Nie zgaduj: gdy nie masz pewności co do przepisu, obniż pewność. Dostajesz też fragmenty ustaw (mogą być nieistotne - ignoruj je wtedy). ")
BLIND = SYS + ('Wskaż JEDNĄ najlepszą odpowiedź. Zwróć WYŁĄCZNIE JSON: {"answer":"litera","confidence":0-100,"legal_basis":"konkretny przepis/artykuł",'
               '"flaw":"none|ambiguous|outdated|incomplete|multiple_correct","note":"max 1 zdanie"}')
VERIFY = SYS + ('Ktoś wskazał odpowiedź (oznaczona strzałką). Zweryfikuj ją niezależnie względem przepisów. Zwróć WYŁĄCZNIE JSON: '
                '{"verdict":"correct|incorrect|uncertain","best_answer":"litera","confidence":0-100,"legal_basis":"konkretny przepis/artykuł",'
                '"flaw":"none|ambiguous|outdated|incomplete|multiple_correct","note":"max 1 zdanie"}')


def with_excerpt(q, text):
    ex = excerpts(q)
    if ex:
        text += "\n\nFragmenty przepisów (automatyczne wyszukiwanie):\n" + "\n".join(f"[{n} {a}] {t}" for _, n, a, t in ex)
    return text


def shuffled(q, seed):
    rnd = random.Random(seed)
    ks = list(q["opcje"])
    vals = [q["opcje"][k] for k in ks]
    rnd.shuffle(vals)
    new = dict(zip(ks, vals))
    back = {nk: next(k for k, v in q["opcje"].items() if v == nv) for nk, nv in new.items()}
    return {"pytanie": q["pytanie"], "opcje": new}, back


def verify(i):
    q = rows[i]
    out = {"blind": [], "verify": None}
    for seed in (1, 2):
        sq, back = shuffled(q, seed * 7 + i)
        v = call(BLIND, with_excerpt(q, fmt(sq, "")), f"b{seed}")
        a = v.get("answer")
        v["answer_orig"] = back.get(a) if isinstance(a, str) else None
        out["blind"].append(v)
    out["verify"] = call(VERIFY, with_excerpt(q, fmt(q, "", q["odpowiedz"])), "v")
    return i, out


todo = [i for i in range(len(rows)) if i not in dups and len(rows[i]["opcje"]) >= 2 and rows[i].get("odpowiedz")]
print("do weryfikacji:", len(todo), flush=True)
res = {}
with ThreadPoolExecutor(16) as ex:
    for n, (i, o) in enumerate(ex.map(verify, todo), 1):
        res[i] = o
        if n % 25 == 0:
            print(f"B {n}/{len(todo)} koszt ${COST[0]:.2f}", flush=True)

final = []
for i, r in enumerate(rows):
    rec = {"id": r["id"], "partia": r["partia"], "przedmiot": r["przedmiot"], "pytanie": r["pytanie"], "opcje": r["opcje"],
           "odpowiedz_wstepna": r.get("odpowiedz"), "pewnosc_wstepna": r.get("pewnosc"), "podstawa_wstepna": r.get("podstawa")}
    if i in dups:
        rec["status"] = "DUPLIKAT"
        rec["duplikat"] = dups[i]
    elif i not in res:
        rec["status"] = "NIEKOMPLETNE" if len(r["opcje"]) < 2 else "BRAK_ODPOWIEDZI"
    else:
        o = res[i]
        b1, b2, v = o["blind"][0], o["blind"][1], o["verify"]
        letters = [b1.get("answer_orig"), b2.get("answer_orig"), v.get("best_answer") if v.get("verdict") == "correct" else None]
        confs = [b1.get("confidence") or 0, b2.get("confidence") or 0, v.get("confidence") or 0]
        flaws = [x.get("flaw") for x in (b1, b2, v)]
        prop = r["odpowiedz"]
        agree = sum(1 for l in letters if l == prop)
        errors = any("error" in x for x in (b1, b2, v))
        if errors:
            st = "BLAD_API"
        elif agree == 3 and min(confs) >= 85 and all(f in ("none", None) for f in flaws) and r.get("pewnosc") != "niska":
            st = "HIGH"
        elif agree >= 2 and min(confs) >= 70 and not any(f in ("ambiguous", "multiple_correct") for f in flaws):
            st = "MEDIUM"
        elif agree <= 1 and sum(1 for l in letters if l and l != prop) >= 2:
            st = "ODRZUCONE_ROZBIEZNE"
        else:
            st = "NISKA"
        rec.update({"status": st, "sedziowie": o, "zgodnych_z_odp_wstepna": agree, "pewnosci": confs, "flagi": flaws})
    final.append(rec)

(OUT / "wyniki.json").write_text(json.dumps(final, ensure_ascii=False, indent=1), encoding="utf-8")
from collections import Counter
cnt = Counter(f["status"] for f in final)
print(cnt, f"koszt ${COST[0]:.2f}")

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
wb = Workbook()
ws = wb.active
ws.title = "Weryfikacja"
ws.append(["ID", "Status", "Przedmiot", "Pytanie", "A", "B", "C", "D", "Odp. wstępna", "Pewn. wstępna", "Zgodnych sędziów (z 3)",
           "Pewności sędziów", "Flagi", "Podstawa (wstępna)", "Duplikat → (baza ID / klucz)", "Uwagi sędziów"])
fill = {"HIGH": "C6EFCE", "MEDIUM": "FFEB9C", "NISKA": "FFC7CE", "ODRZUCONE_ROZBIEZNE": "F4B084", "DUPLIKAT": "D9D9D9"}
for f in final:
    o = f["opcje"]
    d = f.get("duplikat")
    notes = ""
    if "sedziowie" in f:
        s = f["sedziowie"]
        notes = " | ".join(f"{(x.get('legal_basis') or '')[:80]}: {(x.get('note') or '')[:100]}" for x in s["blind"] + [s["verify"]])
    ws.append([f["id"], f["status"], f["przedmiot"], f["pytanie"], o.get("A", ""), o.get("B", ""), o.get("C", ""), o.get("D", ""),
               f["odpowiedz_wstepna"], f["pewnosc_wstepna"], f.get("zgodnych_z_odp_wstepna", ""),
               str(f.get("pewnosci", "")), str(f.get("flagi", "")), f["podstawa_wstepna"],
               (f"{d['typ']} {d['id']} / klucz {d['klucz_w_bazie']}" + ("" if d["zgodna_odpowiedz"] else " (ODP. ROZNA!)")) if d else "", notes])
for i, w in enumerate([9, 14, 18, 60, 28, 28, 28, 28, 8, 10, 10, 14, 24, 50, 28, 80]):
    ws.column_dimensions[chr(65 + i)].width = w
for row in ws.iter_rows(min_row=2):
    for c in row:
        c.alignment = Alignment(wrap_text=True, vertical="top")
    if row[1].value in fill:
        row[1].fill = PatternFill("solid", fgColor=fill[row[1].value])
for c in ws[1]:
    c.font = Font(bold=True)
ws.freeze_panes = "E2"
ws.auto_filter.ref = ws.dimensions
wb.save(OUT / "wyniki.xlsx")
print("zapisano", OUT)
