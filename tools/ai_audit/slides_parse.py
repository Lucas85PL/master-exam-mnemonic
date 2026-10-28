"""Pytania ze zrzutów slajdów (PNG) z zaznaczoną na CZERWONO (kółko) poprawną odpowiedzią -> MD, kontrola, porównanie z bazą.
1) odczyt dwoma modelami wizyjnymi (DeepSeek + Qwen): treść, odpowiedzi i która odpowiedź jest zakreślona czerwonym kółkiem,
2) konsensus (treść podobna, ta sama zaznaczona odpowiedź), 3) kontrola gramatyki DeepSeekiem, 4) odrzucenie pytań już obecnych w bazie
(dopasowanie rozmyte + embeddingi + ocena DeepSeek). Baza tylko do odczytu.
Użycie: python slides_parse.py "<folder z PNG>" ; wynik: review/PYTANIA_czerwone/ (parsed.md, nowe_nieznane.json/.md, juz_w_bazie.json, odrzucone.json)."""
import base64, concurrent.futures as cf, difflib, json, math, re, sqlite3, sys, time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
SRC = Path(sys.argv[1])
D = ROOT / "review" / "PYTANIA_czerwone"
D.mkdir(parents=True, exist_ok=True)
DB = str(Path.home() / "Documents" / "memonic_app.db")
KEY = re.search(r"OPENROUTER_API_KEY\s*=\s*(\S+)", (ROOT / ".env").read_text(encoding="utf-8")).group(1)
H = {"Authorization": "Bearer " + KEY}
MODELS = {"deepseek": "deepseek/deepseek-v4.1-flash", "qwen": "qwen/qwen3.7-flash"}
imgs = sorted(SRC.glob("*.png"), key=lambda p: int(re.search(r"\d+", p.stem).group(0)) if re.search(r"\d+", p.stem) else 0)
PROMPT = ("This is a screenshot of a presentation slide with Polish multiple-choice exam questions (maritime topics). Extract EVERY question that is visible. "
          "Each question has options (often labelled A., B., C. in pink; a letter may be hidden under a mark). A DARK RED CIRCLE/ELLIPSE drawn next to or around an option "
          "marks the CORRECT answer. Return ONLY a JSON array; each element: "
          '{"nr": <printed question number or null>, "question": "<full question text>", "options": ["<text of option 1>", ...] (without letters), '
          '"marked": <1-based index of the option that has the red circle, or null if none>, "confidence": "high"|"low"}. '
          "Keep Polish diacritics; fix only obvious spacing, do not invent words. Skip headings. A question cut off at the image edge must have confidence low.")


def ask_vision(name, path):
    f = D / f"json_{name}" / (path.stem + ".json")
    f.parent.mkdir(exist_ok=True)
    if f.exists() and f.stat().st_size > 5:
        return json.loads(f.read_text(encoding="utf-8"))
    b64 = base64.b64encode(path.read_bytes()).decode()
    for attempt in range(4):
        try:
            r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=H, timeout=300,
                              json={"model": MODELS[name], "temperature": 0, "max_tokens": 9000, "reasoning": {"effort": "low"},
                                    "messages": [{"role": "user", "content": [{"type": "text", "text": PROMPT},
                                                                              {"type": "image_url", "image_url": {"url": "data:image/png;base64," + b64}}]}]})
            if r.status_code == 200:
                m = re.search(r"\[.*\]", r.json()["choices"][0]["message"]["content"] or "", re.S)
                if m:
                    data = json.loads(m.group(0))
                    f.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
                    return data
            time.sleep(3 * (attempt + 1))
        except Exception:
            time.sleep(3 * (attempt + 1))
    return []


def norm(s):
    return re.sub(r"[^\w]+", " ", (s or "").lower()).strip()


def text(q):
    return norm(q["question"]) + " | " + " | ".join(norm(o) for o in q["options"])


jobs = [(n, p) for p in imgs for n in MODELS]
with cf.ThreadPoolExecutor(4) as ex:
    res = list(ex.map(lambda a: (a[0], a[1], ask_vision(*a)), jobs))
read = {n: {p.stem: [q for q in data if isinstance(q, dict) and q.get("question") and isinstance(q.get("options"), list)]
            for nn, p, data in res if nn == n} for n in MODELS}
print("obrazów:", len(imgs), "| pytań DeepSeek:", sum(len(v) for v in read["deepseek"].values()), "| Qwen:", sum(len(v) for v in read["qwen"].values()))

accepted, rejected = [], []
for stem, qs in read["deepseek"].items():
    others, used = read["qwen"].get(stem, []), set()
    for q in qs:
        why, best, bj = None, 0.0, None
        for j, o in enumerate(others):
            if j in used:
                continue
            s = difflib.SequenceMatcher(None, text(q), text(o)).ratio()
            if s > best:
                best, bj = s, j
        if len(q["options"]) < 2 or len(q["question"].strip()) < 12:
            why = "za mało treści / odpowiedzi"
        elif q.get("confidence") == "low":
            why = "niska pewność odczytu"
        elif bj is None or best < 0.85:
            why = f"brak zgodności z drugim odczytem ({best:.2f})"
        else:
            used.add(bj)
            m1, m2 = q.get("marked"), others[bj].get("marked")
            if m1 and m2 and m1 != m2:
                why = f"różne zaznaczenie odpowiedzi ({m1} vs {m2})"
        rec = dict(obraz=stem, nr=q.get("nr"), question=q["question"].strip(), options=[o.strip() for o in q["options"]],
                   marked=q.get("marked") or (others[bj].get("marked") if bj is not None else None),
                   marked_potwierdzone=bool(bj is not None and q.get("marked") and q.get("marked") == others[bj].get("marked")))
        (rejected if why else accepted).append({**rec, "powod": why} if why else rec)
print("po konsensusie:", len(accepted), "| odrzucone:", len(rejected))

SYSTEM = ("You review Polish exam questions (stem plus options) extracted from a screenshot. Decide whether the text is reasonably grammatical and coherent Polish. "
          "REJECT only clear parsing/OCR damage (nonsense sentences, scrambled or repeated words, garbled/glued words, text from two questions mixed, an option that does not fit, "
          "truncated text). Do NOT reject minor typos or odd-but-understandable wording. "
          'Reply with JSON only: {"ok": true|false, "issue": "<max 12 words, empty if ok>"}')


def chat(system, user):
    for attempt in range(4):
        try:
            r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=H, timeout=90,
                              json={"model": MODELS["deepseek"], "temperature": 0, "max_tokens": 1500, "reasoning": {"effort": "low"},
                                    "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
            if r.status_code == 200:
                m = re.search(r"\{.*\}", r.json()["choices"][0]["message"]["content"] or "", re.S)
                return json.loads(m.group(0))
            time.sleep(2 * (attempt + 1))
        except Exception:
            time.sleep(2 * (attempt + 1))
    return None


def fmt_c(q):
    return q["question"] + "\n" + "\n".join(f"{chr(97 + k)}) {o}" for k, o in enumerate(q["options"]))


with cf.ThreadPoolExecutor(3) as ex:
    verdicts = list(ex.map(lambda q: chat(SYSTEM, fmt_c(q)), accepted))
good = []
for q, v in zip(accepted, verdicts):
    if v and v.get("ok") is True:
        good.append(q)
    else:
        rejected.append({**q, "powod": "gramatyka/parsowanie: " + ((v or {}).get("issue") or "brak oceny")})
print("po kontroli gramatyki:", len(good))


def md(items, title):
    out = [f"# {title}", "", f"Liczba pytań: {len(items)}", ""]
    for n, q in enumerate(items, 1):
        out.append(f"{n}. {q['question']}  _(obraz {q['obraz']}, nr {q['nr']})_")
        for k, o in enumerate(q["options"]):
            out.append(f"   {chr(97 + k)}) {o}" + ("  🔴 (zakreślone)" if q.get("marked") == k + 1 else ""))
        out.append("")
    return "\n".join(out)


(D / "parsed.md").write_text(md(good, "Pytania ze slajdów (czerwone kółko = poprawna odp.) po konsensusie i kontroli gramatyki"), encoding="utf-8")

# ---- porównanie z bazą
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
        r_ = sm.ratio()
        if r_ > bk[0]:
            bk = (r_, rid)
    bs = (0.0, None)
    for rid, t in db_stem:
        if abs(len(t) - len(s)) > 0.4 * max(len(t), len(s), 1):
            continue
        r_ = difflib.SequenceMatcher(None, s, t).ratio()
        if r_ > bs[0]:
            bs = (r_, rid)
    return bk, bs


dup, rest = [], []
for q in good:
    (kr, kid), (sr, sid) = fuzzy(q)
    if kr >= 0.8:
        dup.append({**q, "w_bazie": kid, "podobienstwo": round(kr, 2), "metoda": "treść+odpowiedzi"})
    elif sr >= 0.88:
        dup.append({**q, "w_bazie": sid, "podobienstwo": round(sr, 2), "metoda": "treść pytania"})
    else:
        rest.append(q)
print("już w bazie (rozmyte):", len(dup), "| do oceny embeddingami:", len(rest))


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


new, dup_llm = [], []
if rest:
    dbv = list(zip(rows, map(unit, embed([full(r) for r in rows]))))
    ev = list(map(unit, embed([q["question"] + " | " + " | ".join(q["options"]) for q in rest])))
    JSYS = ("You compare a Polish exam question with candidate questions from an existing database. Decide whether any candidate is the SAME exam question "
            "(same meaning; wording may differ slightly; key facts and the meaning of the options must agree). Questions that only share a topic are NOT the same. "
            'Reply with JSON only: {"match": <candidate id or null>}')

    def judge(i):
        sims = sorted(((sum(a * b for a, b in zip(ev[i], v)), r) for r, v in dbv), key=lambda x: -x[0])[:4]
        cand = []
        for _, r in sims:
            opts = "\n".join(f"  {k.upper()}) {r['odp_' + k]}" for k in "abcd" if r["odp_" + k])
            cand.append(f"id={r['id']}: {r['pytanie']}\n{opts}")
        return chat(JSYS, "SCANNED QUESTION:\n" + fmt_c(rest[i]) + "\n\nDATABASE CANDIDATES:\n" + "\n".join(cand)), [(r["id"], round(s, 3)) for s, r in sims]

    with cf.ThreadPoolExecutor(3) as ex:
        for q, (v, c) in zip(rest, ex.map(judge, range(len(rest)))):
            if v is None:
                new.append({**q, "uwaga": "ocena duplikatu nie powiodła się — do sprawdzenia", "kandydaci": c})
            elif v.get("match"):
                dup_llm.append({**q, "w_bazie": v["match"], "metoda": "embedding+DeepSeek"})
            else:
                new.append({**q, "kandydaci": c})
print("już w bazie (embeddingi+DeepSeek):", len(dup_llm), "| NOWE, nieznane:", len(new))
(D / "nowe_nieznane.json").write_text(json.dumps(new, ensure_ascii=False, indent=1), encoding="utf-8")
(D / "juz_w_bazie.json").write_text(json.dumps(dup + dup_llm, ensure_ascii=False, indent=1), encoding="utf-8")
(D / "odrzucone.json").write_text(json.dumps(rejected, ensure_ascii=False, indent=1), encoding="utf-8")
(D / "nowe_nieznane.md").write_text(md(new, "Nowe, nieznane pytania ze slajdów (nie ma ich w bazie)"), encoding="utf-8")
print("KONIEC | wczytane:", sum(len(v) for v in read["deepseek"].values()), "| po konsensusie i gramatyce:", len(good), "| w bazie:", len(dup) + len(dup_llm), "| nowe:", len(new))
