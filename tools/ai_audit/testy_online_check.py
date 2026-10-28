"""Pytania z PDF 'Testy z Prawa Morskiego' (Studocu; tekst + drukowane 'Odp. X – art. N') -> parsowanie regułami -> sprawdzenie, których NIE MA w bazie.
Dopasowanie: rozmyte (treść+odpowiedzi / sama treść), potem embeddingi + ocena DeepSeek (to samo pytanie inaczej sformułowane). Baza tylko do odczytu.
Wynik: review/Testy_online/ (parsed.json, nowe_nieznane.json/.md, juz_w_bazie.json). Użycie: python testy_online_check.py "<plik.pdf>" """
import concurrent.futures as cf, difflib, json, math, re, sqlite3, sys, time
from pathlib import Path

import fitz
import requests

ROOT = Path(__file__).resolve().parents[2]
PDF = Path(sys.argv[1])
D = ROOT / "review" / "Testy_online"
D.mkdir(parents=True, exist_ok=True)
DB = str(Path.home() / "Documents" / "memonic_app.db")
KEY = re.search(r"OPENROUTER_API_KEY\s*=\s*(\S+)", (ROOT / ".env").read_text(encoding="utf-8")).group(1)
H = {"Authorization": "Bearer " + KEY}

# ---- parsowanie tekstu PDF
raw = "\n".join(p.get_text() for p in fitz.open(PDF))
junk = re.compile(r"^(Downloaded by .*|Scan to open on Studocu|lOMoARcPSD\|\d+|Studocu is not sponsored.*|Prawo morskie - testy Z www|Prawo Morskie \(Uniwersytet.*|\d{1,2}|Test|y z prawa morskiego:?|Testy z prawa morskiego:?)$")
lines = [l.strip() for l in raw.split("\n")]
lines = [l for l in lines if l and not junk.match(l)]
items, cur = [], None
for l in lines:
    m = re.match(r"^(\d{1,3})\.\s+(.+)$", l)
    o = re.match(r"^([a-dA-D])\)\s*(.*)$", l)
    k = re.match(r"^Odp\.\s*([A-Da-d?])\s*(?:[–-]\s*(.*))?(.*)$", l)
    if m and (cur is None or int(m.group(1)) == cur["nr"] + 1 or int(m.group(1)) > cur["nr"]):
        if cur:
            items.append(cur)
        cur = dict(nr=int(m.group(1)), question=m.group(2).strip(), options=[], key=None, zrodlo="", _stage="q")
    elif cur is None:
        continue
    elif k:
        cur["key"] = None if k.group(1) == "?" else k.group(1).upper()
        cur["zrodlo"] = (k.group(2) or k.group(3) or "").strip()
        cur["_stage"] = "k"
    elif o:
        cur["options"].append(o.group(2).strip())
        cur["_stage"] = "o"
    elif cur["_stage"] == "q":
        cur["question"] += " " + l
    elif cur["_stage"] == "o" and cur["options"]:
        cur["options"][-1] += " " + l
    elif cur["_stage"] == "k":
        cur["zrodlo"] += " " + l
if cur:
    items.append(cur)
ok = [q for q in items if len(q["options"]) >= 2]
print("pytań w PDF:", len(items), "| z >=2 odpowiedziami:", len(ok), "| z drukowanym kluczem:", sum(1 for q in ok if q["key"]), "| bez klucza:", sum(1 for q in ok if not q["key"]))
for q in ok:
    q.pop("_stage", None)
(D / "parsed.json").write_text(json.dumps(ok, ensure_ascii=False, indent=1), encoding="utf-8")


def norm(s):
    return re.sub(r"[^\w]+", " ", (s or "").lower()).strip()


con = sqlite3.connect(f"file:{Path(DB).as_posix()}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
rows = con.execute("select * from questions").fetchall()
db_full = [(r["id"], norm(r["pytanie"]) + " " + " ".join(norm(r["odp_" + k]) for k in "abcd" if r["odp_" + k])) for r in rows]
db_stem = [(r["id"], norm(r["pytanie"])) for r in rows]


def fuzzy(q):
    k, s = norm(q["question"]) + " " + " ".join(norm(o) for o in q["options"]), norm(q["question"])
    bk = (0.0, None)
    for rid, t in db_full:
        if abs(len(t) - len(k)) > 0.5 * max(len(t), len(k), 1):
            continue
        sm = difflib.SequenceMatcher(None, k, t)
        if sm.real_quick_ratio() < max(bk[0], 0.75) or sm.quick_ratio() < max(bk[0], 0.75):
            continue
        x = sm.ratio()
        if x > bk[0]:
            bk = (x, rid)
    bs = (0.0, None)
    for rid, t in db_stem:
        if abs(len(t) - len(s)) > 0.4 * max(len(t), len(s), 1):
            continue
        x = difflib.SequenceMatcher(None, s, t).ratio()
        if x > bs[0]:
            bs = (x, rid)
    return bk, bs


dup, rest = [], []
for q in ok:
    (kr, kid), (sr, sid) = fuzzy(q)
    if kr >= 0.8:
        dup.append({**q, "w_bazie": kid, "metoda": f"treść+odpowiedzi {kr:.2f}"})
    elif sr >= 0.88:
        dup.append({**q, "w_bazie": sid, "metoda": f"treść pytania {sr:.2f}"})
    else:
        rest.append(q)
print("już w bazie (rozmyte):", len(dup), "| do oceny embeddingami:", len(rest))


def chat(system, user):
    for attempt in range(4):
        try:
            r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=H, timeout=90,
                              json={"model": "deepseek/deepseek-v4.1-flash", "temperature": 0, "max_tokens": 1500, "reasoning": {"effort": "low"},
                                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
            if r.status_code == 200:
                m = re.search(r"\{.*\}", r.json()["choices"][0]["message"]["content"] or "", re.S)
                return json.loads(m.group(0))
            time.sleep(2 * (attempt + 1))
        except Exception:
            time.sleep(2 * (attempt + 1))
    return None


def embed(texts):
    out = []
    for i in range(0, len(texts), 100):
        for attempt in range(4):
            r = requests.post("https://openrouter.ai/api/v1/embeddings", headers=H, timeout=120,
                              json={"model": "openai/text-embedding-3-small", "input": [t[:1800] for t in texts[i:i + 100]]})
            if r.status_code == 200:
                out += [d["embedding"] for d in r.json()["data"]]
                break
            time.sleep(3 * (attempt + 1))
        else:
            sys.exit("embeddings: błąd " + str(r.status_code))
    return out


def unit(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def full(r):
    return r["pytanie"] + " | " + " | ".join(r["odp_" + k] for k in "abcd" if r["odp_" + k])


def fmt_c(q):
    return q["question"] + "\n" + "\n".join(f"  {chr(97 + k)}) {o}" for k, o in enumerate(q["options"]))


new, dup_llm = [], []
if rest:
    dbv = list(zip(rows, map(unit, embed([full(r) for r in rows]))))
    ev = list(map(unit, embed([q["question"] + " | " + " | ".join(q["options"]) for q in rest])))
    JSYS = ("You compare a Polish exam question with candidate questions from an existing database. Decide whether any candidate is the SAME exam question "
            "(same meaning, even if the wording or the order of options differs; the options must mean the same things). Questions that only share a topic are NOT the same. "
            'Reply with JSON only: {"match": <candidate id or null>}')

    def judge(i):
        sims = sorted(((sum(a * b for a, b in zip(ev[i], v)), r) for r, v in dbv), key=lambda x: -x[0])[:4]
        cand = []
        for _, r in sims:
            opts = "\n".join(f"  {k.upper()}) {r['odp_' + k]}" for k in "abcd" if r["odp_" + k])
            cand.append(f"id={r['id']}: {r['pytanie']}\n{opts}")
        return chat(JSYS, "NEW QUESTION:\n" + fmt_c(rest[i]) + "\n\nDATABASE CANDIDATES:\n" + "\n".join(cand)), [(r["id"], round(s, 3)) for s, r in sims]

    with cf.ThreadPoolExecutor(3) as ex:
        for q, (v, c) in zip(rest, ex.map(judge, range(len(rest)))):
            if v is None:
                new.append({**q, "uwaga": "ocena duplikatu nie powiodła się — do sprawdzenia", "kandydaci": c})
            elif v.get("match"):
                dup_llm.append({**q, "w_bazie": v["match"], "metoda": "embedding+DeepSeek"})
            else:
                new.append({**q, "kandydaci": c})
print("już w bazie (embeddingi+DeepSeek):", len(dup_llm), "| NOWE, nieznane:", len(new), "| (z drukowanym kluczem:", sum(1 for q in new if q["key"]), ")")
(D / "nowe_nieznane.json").write_text(json.dumps(new, ensure_ascii=False, indent=1), encoding="utf-8")
(D / "juz_w_bazie.json").write_text(json.dumps(dup + dup_llm, ensure_ascii=False, indent=1), encoding="utf-8")
out = ["# Nowe, nieznane pytania z 'Testy z Prawa Morskiego' (nie ma ich w bazie)", "", f"Liczba pytań: {len(new)}", ""]
for n, q in enumerate(new, 1):
    out.append(f"{n}. {q['question']}  _(nr {q['nr']} w PDF)_")
    for k, o in enumerate(q["options"]):
        out.append(f"   {chr(97 + k)}) {o}" + ("  ✔ (drukowana odp.)" if q["key"] == chr(65 + k) else ""))
    if q["key"]:
        out.append(f"   _drukowana odp.: {q['key']} {('– ' + q['zrodlo']) if q['zrodlo'] else ''}_")
    out.append("")
(D / "nowe_nieznane.md").write_text("\n".join(out), encoding="utf-8")
