"""Dopasowanie nowo dodanych pytań ENG (ai_verified = pdf_urzad:dodane_z_arkusza:...) do odpowiedników PL w bazie.
1) embeddingi (openai/text-embedding-3-small) -> 4 najbliższe pytania PL, 2) DeepSeek ocenia: czy to to samo pytanie i czy poprawna odpowiedź jest taka sama.
Baza tylko do odczytu. Wynik: review/Zgodnosc_z_PDF/eng_pl_matches.json {id_eng: {match, same_answer, pl_key_in_eng, cand}}.
Użycie: python eng_pl_match.py [baza.db]"""
import concurrent.futures as cf, json, math, re, sqlite3, sys, time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
DB = sys.argv[1] if len(sys.argv) > 1 else str(Path.home() / "Documents" / "memonic_app.db")
OUT = ROOT / "review" / "Zgodnosc_z_PDF" / "eng_pl_matches.json"
CACHE = ROOT / "review" / "Zgodnosc_z_PDF" / "_emb_cache.json"
KEY = re.search(r"OPENROUTER_API_KEY\s*=\s*(\S+)", (ROOT / ".env").read_text(encoding="utf-8")).group(1)
H = {"Authorization": "Bearer " + KEY}
con = sqlite3.connect(f"file:{Path(DB).as_posix()}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
eng = con.execute("select * from questions where kategoria='Angielski' and ai_verified like 'pdf_urzad:dodane_z_arkusza%' order by id").fetchall()
pl = con.execute("select * from questions where kategoria!='Angielski' and review_status='ok'").fetchall()
print("ENG:", len(eng), "PL kandydatów:", len(pl))


def text(r):
    return (r["pytanie"] or "") + " | " + " | ".join(r["odp_" + L] or "" for L in "abcd" if r["odp_" + L])


emb = json.load(open(CACHE, encoding="utf-8")) if CACHE.exists() else {}


def embed(rows):
    todo = [r for r in rows if str(r["id"]) not in emb]
    for i in range(0, len(todo), 100):
        chunk = todo[i:i + 100]
        for attempt in range(4):
            r = requests.post("https://openrouter.ai/api/v1/embeddings", headers=H,
                              json={"model": "openai/text-embedding-3-small", "input": [text(x)[:2000] for x in chunk]}, timeout=120)
            if r.status_code == 200:
                for x, d in zip(chunk, r.json()["data"]):
                    emb[str(x["id"])] = d["embedding"]
                break
            time.sleep(3 * (attempt + 1))
        else:
            sys.exit("embeddings: błąd " + str(r.status_code))
    json.dump(emb, open(CACHE, "w"), separators=(",", ":"))


embed(eng); embed(pl)


def unit(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


plv = [(r, unit(emb[str(r["id"])])) for r in pl]
SYSTEM = ("You compare an English exam question with Polish candidate questions from the same exam database. "
          "Decide whether any candidate is the SAME question (a translation; wording may differ slightly, options may be reordered; "
          "numbers, symbols and technical details must agree). If yes, say whether the marked correct answers have the SAME MEANING in both, "
          "and which English option letter corresponds to the Polish marked answer. "
          'Reply with JSON only: {"match": <candidate id or null>, "same_answer": true|false|null, "pl_key_in_eng": "A|B|C|D|null"}')


def fmt(r):
    key = (r["poprawna_odpowiedz"] or "").upper()
    return f"id={r['id']}: {r['pytanie']}\n" + "\n".join(f"  {L.upper()}) {r['odp_' + L]}" for L in "abcd" if r["odp_" + L]) + f"\n  [marked answer: {key}]"


def ask(r):
    ev = unit(emb[str(r["id"])])
    sims = sorted(((sum(a * b for a, b in zip(ev, v)), p) for p, v in plv), key=lambda x: -x[0])[:4]
    body = ("ENGLISH QUESTION:\n" + fmt(r) + "\n\nPOLISH CANDIDATES:\n" + "\n".join(fmt(p) for _, p in sims))
    for attempt in range(4):
        try:
            resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=H, timeout=90,
                                 json={"model": "deepseek/deepseek-v4.1-flash", "temperature": 0, "max_tokens": 1500, "reasoning": {"effort": "low"},
                                       "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": body}]})
            if resp.status_code == 200:
                m = re.search(r"\{.*\}", resp.json()["choices"][0]["message"]["content"] or "", re.S)
                v = json.loads(m.group(0))
                v["cand"] = [(p["id"], round(s, 3)) for s, p in sims]
                return r["id"], v
            time.sleep(2 * (attempt + 1))
        except Exception:
            time.sleep(2 * (attempt + 1))
    return r["id"], {"match": None, "same_answer": None, "pl_key_in_eng": None, "error": True}


res = json.load(open(OUT, encoding="utf-8")) if OUT.exists() else {}
todo = [r for r in eng if str(r["id"]) not in res or res[str(r["id"])].get("error")]
print("do oceny:", len(todo))
with cf.ThreadPoolExecutor(3) as ex:
    for k, (i, v) in enumerate(ex.map(ask, todo), 1):
        res[str(i)] = v
        if k % 40 == 0:
            json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
matched = [v for v in res.values() if v.get("match")]
print("ocenione:", len(res), "| z odpowiednikiem PL:", len(matched), "| ta sama odpowiedź:", sum(1 for v in matched if v.get("same_answer") is True),
      "| inna odpowiedź:", sum(1 for v in matched if v.get("same_answer") is False), "| błędy:", sum(1 for v in res.values() if v.get("error")))
