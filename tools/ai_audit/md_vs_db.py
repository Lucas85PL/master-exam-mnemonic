"""WSZYSTKIE_PYTANIA.md (skany) vs baza: które pytania są nowe.
Etapy: parsowanie -> dokładne dopasowanie po znormalizowanym tekście -> embeddingi (top-4 kandydatów) -> DeepSeek ocenia 'to samo pytanie?'
-> pytania uznane za nowe, a podobne (sim>=0.85), dostają drugą opinię GPT Luna. Baza tylko do odczytu.
Użycie: python md_vs_db.py [baza] ; wynik: runs/md_vs_db.json + 'NOWE PYTANIA DO BAZY OCT.MD' obok pliku źródłowego."""
import concurrent.futures as cf, json, math, re, sqlite3, sys, time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
SRC = Path(r"C:\Users\Lukasz\Desktop\Skany - pytania\MD\WSZYSTKIE_PYTANIA.md")
OUT_MD = SRC.parent / "NOWE PYTANIA DO BAZY OCT.MD"
RUNS = Path(__file__).resolve().parent / "runs"
RUNS.mkdir(exist_ok=True)
DB = sys.argv[1] if len(sys.argv) > 1 else str(Path.home() / "Documents" / "memonic_app.db")
KEY = re.search(r"OPENROUTER_API_KEY\s*=\s*(\S+)", (ROOT / ".env").read_text(encoding="utf-8")).group(1)
H = {"Authorization": "Bearer " + KEY}
DEEPSEEK, LUNA = "deepseek/deepseek-v4.1-flash", "openai/gpt-6-luna"


def parse():
    qs, src, cur = [], "", None
    for line in SRC.read_text(encoding="utf-8").splitlines():
        if line.startswith("## Źródło:"):
            src = line.split(":", 1)[1].strip()
            continue
        m = re.match(r"###\s*(\d+)\.\s*(.*)", line)
        if m:
            cur = {"nr": int(m.group(1)), "q": m.group(2).strip(), "opts": [], "src": src}
            qs.append(cur)
            continue
        m = re.match(r"-\s*\*\*([A-Da-d])\.\*\*\s*(.*)", line)
        if m and cur:
            cur["opts"].append(m.group(2).strip())
            continue
        if cur and line.strip() and not line.startswith(("#", "---")):
            # ciąg dalszy treści pytania lub ostatniego wariantu
            if cur["opts"]:
                cur["opts"][-1] += " " + line.strip()
            else:
                cur["q"] += " " + line.strip()
    return qs


def norm(s):
    return re.sub(r"[^\w]+", " ", (s or "").lower()).strip()


def full(q, opts):
    return q + " | " + " | ".join(opts)


def post(url, body, tries=4):
    for a in range(tries):
        try:
            r = requests.post(url, headers=H, json=body, timeout=120)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        time.sleep(3 * (a + 1))
    return None


def embed(emb, keyed):
    todo = [(k, t) for k, t in keyed if k not in emb]
    for i in range(0, len(todo), 100):
        chunk = todo[i:i + 100]
        d = post("https://openrouter.ai/api/v1/embeddings", {"model": "openai/text-embedding-3-small", "input": [t[:1800] for _, t in chunk]})
        if not d:
            sys.exit("embeddings: błąd")
        for (k, _), x in zip(chunk, d["data"]):
            emb[k] = x["embedding"]


def unit(v):
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


SYSTEM = ("You compare a Polish maritime-exam question with candidate questions from an existing database. Decide whether any candidate is the SAME exam question "
          "(same meaning; wording, punctuation, OCR errors or option order may differ slightly; the key facts, numbers and the meaning of the options must agree). "
          "Questions that only share a topic, or differ in a number/condition/option meaning, are NOT the same. "
          'Reply with JSON only: {"match": <candidate id or null>}')


def judge(model, body_txt):
    d = post("https://openrouter.ai/api/v1/chat/completions",
             {"model": model, "temperature": 0, "max_tokens": 2500, "reasoning": {"effort": "low"},
              "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": body_txt}]})
    if not d:
        return "BŁĄD"
    try:
        m = re.search(r"\{.*\}", d["choices"][0]["message"]["content"] or "", re.S)
        return json.loads(m.group(0)).get("match")
    except Exception:
        return "BŁĄD"


def main():
    qs = [q for q in parse() if len(q["opts"]) >= 2]
    print("sparsowano:", len(qs))
    con = sqlite3.connect(f"file:{Path(DB).as_posix()}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute("select * from questions").fetchall()
    rec = {r["id"]: r for r in rows}

    def dbfull(r):
        return full(r["pytanie"], [r["odp_" + k] for k in "abcd" if r["odp_" + k]])

    exact = {}
    for r in rows:
        exact.setdefault(norm(dbfull(r)), r["id"])
        exact.setdefault(norm(r["pytanie"]) + "#" + norm(r["poprawna_odpowiedz_tekst"] or ""), r["id"])
    res = [None] * len(qs)
    rest = []
    for i, q in enumerate(qs):
        k = norm(full(q["q"], q["opts"]))
        if k in exact:
            res[i] = {"status": "w_bazie", "id": exact[k], "metoda": "dokładne"}
        else:
            rest.append(i)
    print("dokładne trafienia:", len(qs) - len(rest), "| do embeddingów:", len(rest))

    cache = RUNS / "md_vs_db_emb.json"
    emb = json.load(open(cache, encoding="utf-8")) if cache.exists() else {}
    embed(emb, [(f"db{r['id']}", dbfull(r)) for r in rows])
    embed(emb, [(f"q{i}", full(qs[i]["q"], qs[i]["opts"])) for i in rest])
    json.dump(emb, open(cache, "w"), separators=(",", ":"))
    dbv = [(r, unit(emb[f"db{r['id']}"])) for r in rows]

    def cands(i):
        qv = unit(emb[f"q{i}"])
        return sorted(((sum(a * b for a, b in zip(qv, v)), r) for r, v in dbv), key=lambda x: -x[0])[:4]

    def body(i, cs):
        q = qs[i]
        qo = "\n".join(f"  {chr(65 + k)}) {o}" for k, o in enumerate(q["opts"]))
        ct = []
        for _, r in cs:
            o = "\n".join(f"  {k.upper()}) {r['odp_' + k]}" for k in "abcd" if r["odp_" + k])
            ct.append(f"id={r['id']}: {r['pytanie']}\n{o}")
        return "SCANNED QUESTION:\n" + q["q"] + "\n" + qo + "\n\nDATABASE CANDIDATES:\n" + "\n".join(ct)

    def work(i):
        cs = cands(i)
        top = cs[0][0]
        info = [(r["id"], round(s, 3)) for s, r in cs]
        if top < 0.80:
            return i, {"status": "nowe", "top": round(top, 3), "kandydaci": info}
        m = judge(DEEPSEEK, body(i, cs))
        if m == "BŁĄD":
            return i, {"status": "nowe", "top": round(top, 3), "kandydaci": info, "uwaga": "DeepSeek błąd"}
        if m:
            return i, {"status": "w_bazie", "id": int(m), "metoda": "embedding+DeepSeek", "top": round(top, 3)}
        if top >= 0.85:  # druga opinia dla podobnych, uznanych za nowe
            m2 = judge(LUNA, body(i, cs))
            if m2 and m2 != "BŁĄD":
                return i, {"status": "w_bazie", "id": int(m2), "metoda": "embedding+GPT Luna", "top": round(top, 3)}
            return i, {"status": "nowe", "top": round(top, 3), "kandydaci": info, "uwaga": "podobne, ale dwa modele: to inne pytanie" if m2 is None else "Luna błąd"}
        return i, {"status": "nowe", "top": round(top, 3), "kandydaci": info}

    done = 0
    with cf.ThreadPoolExecutor(6) as ex:
        for i, r in ex.map(work, rest):
            res[i] = r
            done += 1
            if done % 500 == 0:
                print(" ocenione", done, "/", len(rest), flush=True)
    new = [dict(qs[i], **res[i]) for i in range(len(qs)) if res[i]["status"] == "nowe"]
    old = [dict(qs[i], **res[i]) for i in range(len(qs)) if res[i]["status"] == "w_bazie"]
    (RUNS / "md_vs_db.json").write_text(json.dumps({"nowe": new, "w_bazie": old}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("razem:", len(qs), "| w bazie:", len(old), "| NOWE:", len(new))
    out = ["# NOWE PYTANIA DO BAZY (OCT)", "",
           f"Źródło: WSZYSTKIE_PYTANIA.md ({len(qs)} pytań). Porównano z bazą ({len(rows)} wierszy): dokładne dopasowanie, embeddingi, DeepSeek V4.1 Flash, "
           f"dla podobnych druga opinia GPT 6 Luna. **Nowych: {len(new)}.** Brak zaznaczonych odpowiedzi w źródle.", ""]
    last = None
    for n, q in enumerate(new, 1):
        if q["src"] != last:
            out += ["---", f"## Źródło: {q['src']}", ""]
            last = q["src"]
        out.append(f"### {n}. {q['q']}  _(nr {q['nr']})_")
        out.append("")
        for k, o in enumerate(q["opts"]):
            out.append(f"- **{chr(65 + k)}.** {o}")
        if q.get("uwaga"):
            out.append(f"\n_Uwaga: {q['uwaga']}; najbliższe w bazie: {q['kandydaci'][0][0]} (sim {q['kandydaci'][0][1]})_")
        out.append("")
    OUT_MD.write_text("\n".join(out), encoding="utf-8")
    print("zapisano:", OUT_MD)


main()
