"""Faza 4: odrzucenie pytań ze skanów, które już są w bazie (po treści; także gdy inaczej sformułowane): dopasowanie rozmyte, potem embeddingi + ocena DeepSeek.
Wejście: review/Nowe_21_10/nowe_pytania_po_gramatyce.json. Baza tylko do odczytu (wszystkie wiersze, także wyłączone).
Wyjście: nowe_nieznane.json/.md, juz_w_bazie.json."""
import concurrent.futures as cf, difflib, json, math, re, sqlite3, sys, time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "review" / "Nowe_21_10"
DB = sys.argv[1] if len(sys.argv) > 1 else str(Path.home() / "Documents" / "memonic_app.db")
KEY = re.search(r"OPENROUTER_API_KEY\s*=\s*(\S+)", (ROOT / ".env").read_text(encoding="utf-8")).group(1)
H = {"Authorization": "Bearer " + KEY}
cands = json.load(open(D / "nowe_pytania_po_gramatyce.json", encoding="utf-8"))
con = sqlite3.connect(f"file:{Path(DB).as_posix()}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
rows = con.execute("select * from questions").fetchall()


def norm(s):
    return re.sub(r"[^\w]+", " ", (s or "").lower()).strip()


def dbtext(r):
    return norm(r["pytanie"]) + " " + " ".join(norm(r["odp_" + k]) for k in "abcd" if r["odp_" + k])


def ctext(q):
    return norm(q["question"]) + " " + " ".join(norm(o) for o in q["options"])


db_full = [(r["id"], dbtext(r)) for r in rows]
db_stem = [(r["id"], norm(r["pytanie"])) for r in rows]


def fuzzy(q):
    k, s = ctext(q), norm(q["question"])
    best_k = (0.0, None)
    for rid, t in db_full:
        if abs(len(t) - len(k)) > 0.5 * max(len(t), len(k), 1):
            continue
        sm = difflib.SequenceMatcher(None, k, t)
        if sm.real_quick_ratio() < max(best_k[0], 0.75) or sm.quick_ratio() < max(best_k[0], 0.75):
            continue
        r_ = sm.ratio()
        if r_ > best_k[0]:
            best_k = (r_, rid)
    best_s = (0.0, None)
    for rid, t in db_stem:
        if abs(len(t) - len(s)) > 0.4 * max(len(t), len(s), 1):
            continue
        r_ = difflib.SequenceMatcher(None, s, t).ratio()
        if r_ > best_s[0]:
            best_s = (r_, rid)
    return best_k, best_s


dup_fuzzy, rest = [], []
for q in cands:
    (kr, kid), (sr, sid) = fuzzy(q)
    if kr >= 0.8:
        dup_fuzzy.append({**q, "w_bazie": kid, "podobienstwo": round(kr, 2), "metoda": "treść+odpowiedzi"})
    elif sr >= 0.88:
        dup_fuzzy.append({**q, "w_bazie": sid, "podobienstwo": round(sr, 2), "metoda": "treść pytania"})
    else:
        rest.append(q)
print("kandydatów:", len(cands), "| już w bazie (dopasowanie rozmyte):", len(dup_fuzzy), "| do oceny embeddingami:", len(rest))

# ---- embeddingi + ocena DeepSeek dla reszty
CACHE = D / "_emb_cache.json"
emb = json.load(open(CACHE, encoding="utf-8")) if CACHE.exists() else {}


def embed(keyed):
    todo = [(k, t) for k, t in keyed if k not in emb]
    for i in range(0, len(todo), 100):
        chunk = todo[i:i + 100]
        for attempt in range(4):
            r = requests.post("https://openrouter.ai/api/v1/embeddings", headers=H, timeout=120,
                              json={"model": "openai/text-embedding-3-small", "input": [t[:1800] for _, t in chunk]})
            if r.status_code == 200:
                for (k, _), d in zip(chunk, r.json()["data"]):
                    emb[k] = d["embedding"]
                break
            time.sleep(3 * (attempt + 1))
        else:
            sys.exit("embeddings: błąd " + str(r.status_code))


def full(r):
    return r["pytanie"] + " | " + " | ".join(r["odp_" + k] for k in "abcd" if r["odp_" + k])


embed([(f"db{r['id']}", full(r)) for r in rows])
embed([(f"c{i}", q["question"] + " | " + " | ".join(q["options"])) for i, q in enumerate(rest)])
json.dump(emb, open(CACHE, "w"), separators=(",", ":"))


def unit(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


dbv = [(r, unit(emb[f"db{r['id']}"])) for r in rows]
SYSTEM = ("You compare a Polish exam question with candidate questions from an existing database. Decide whether any candidate is the SAME exam question "
          "(same meaning; wording or the order/phrasing of options may differ slightly because the candidate comes from a poor scan; key facts, numbers and "
          "the meaning of the options must agree). Questions that only share a topic are NOT the same. "
          'Reply with JSON only: {"match": <candidate id or null>}')


def judge(i):
    q = rest[i]
    qv = unit(emb[f"c{i}"])
    sims = sorted(((sum(a * b for a, b in zip(qv, v)), r) for r, v in dbv), key=lambda x: -x[0])[:4]
    qopts = "\n".join(f"  {chr(97 + k)}) {o}" for k, o in enumerate(q["options"]))
    cand_txt = []
    for _, r in sims:
        opts = "\n".join(f"  {k.upper()}) {r['odp_' + k]}" for k in "abcd" if r["odp_" + k])
        cand_txt.append(f"id={r['id']}: {r['pytanie']}\n{opts}")
    body = "SCANNED QUESTION:\n" + q["question"] + "\n" + qopts + "\n\nDATABASE CANDIDATES:\n" + "\n".join(cand_txt)
    for attempt in range(4):
        try:
            resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=H, timeout=90,
                                 json={"model": "deepseek/deepseek-v4.1-flash", "temperature": 0, "max_tokens": 1500, "reasoning": {"effort": "low"},
                                       "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": body}]})
            if resp.status_code == 200:
                m = re.search(r"\{.*\}", resp.json()["choices"][0]["message"]["content"] or "", re.S)
                v = json.loads(m.group(0))
                return i, v.get("match"), [(r["id"], round(s, 3)) for s, r in sims]
            time.sleep(2 * (attempt + 1))
        except Exception:
            time.sleep(2 * (attempt + 1))
    return i, "BŁĄD", []


new, dup_llm, errors = [], [], 0
with cf.ThreadPoolExecutor(3) as ex:
    for i, m, c in ex.map(judge, range(len(rest))):
        if m == "BŁĄD":
            errors += 1
            new.append({**rest[i], "uwaga": "ocena duplikatu nie powiodła się — do sprawdzenia", "kandydaci": c})
        elif m:
            dup_llm.append({**rest[i], "w_bazie": m, "metoda": "embedding+DeepSeek"})
        else:
            new.append({**rest[i], "kandydaci": c})
print("już w bazie (embeddingi+DeepSeek):", len(dup_llm), "| NOWE, nieznane:", len(new), "| (w tym bez oceny:", errors, ")")
(D / "nowe_nieznane.json").write_text(json.dumps(new, ensure_ascii=False, indent=1), encoding="utf-8")
(D / "juz_w_bazie.json").write_text(json.dumps(dup_fuzzy + dup_llm, ensure_ascii=False, indent=1), encoding="utf-8")
out = ["# Nowe, nieznane pytania ze skanów (nie ma ich w bazie)", "", f"Liczba pytań: {len(new)}", ""]
for n, q in enumerate(new, 1):
    out.append(f"{n}. {q['question']}  _(str. {q['strona']}, nr {q['nr']})_")
    for k, o in enumerate(q["options"]):
        out.append(f"   {chr(97 + k)}) {o}")
    if q.get("printed_key"):
        out.append(f"   _(drukowana odp. w skanie: {q['printed_key']} — niepewna)_")
    out.append("")
(D / "nowe_nieznane.md").write_text("\n".join(out), encoding="utf-8")
