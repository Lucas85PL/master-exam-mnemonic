"""Zbiór nowych: scala pytania z 4 plików (MD, 2x xlsx, docx) w jeden Excel, klasyfikuje (MASTER/POKŁAD/ANGIELSKI),
5 modeli odpowiada z wyszukiwaniem w sieci (wtyczka web OpenRouter; wymóg źródła, nie z pamięci), przy >=3 zgodnych: Notka + Wyjaśnienie.
Użycie: python zbior_nowych.py [--limit N] ; cache: runs/zbior_cache.jsonl (powtórka kosztuje tylko brakujące wywołania)."""
import concurrent.futures as cf, difflib, hashlib, json, re, sys, threading, time
from pathlib import Path

import docx
import openpyxl
import requests

ROOT = Path(__file__).resolve().parents[2]
FOLDER = Path(r"C:\Users\Lukasz\Desktop\Zbiór nowych")
OUT = FOLDER / "Zbior_nowych_pytan_AI.xlsx"
CACHE = Path(__file__).resolve().parent / "runs" / "zbior_cache.jsonl"
import os
KEY = os.environ.get("ZBIOR_OR_KEY") or re.search(r"OPENROUTER_API_KEY\s*=\s*(\S+)", (ROOT / ".env").read_text(encoding="utf-8")).group(1)
MODELS = [("deepseek/deepseek-v4.1-flash", "AI1"), ("deepseek/deepseek-v4.1-flash", "AI2"),
          ("openai/gpt-6-luna", "AI3"), ("openai/gpt-6-luna", "AI4"), ("openai/gpt-6.1-terra", "AI5")]
CAP = float(sys.argv[sys.argv.index("--cap") + 1]) if "--cap" in sys.argv else 11.0
LIMIT = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
lock = threading.Lock()
cost_total = [0.0]


# ------------------------------------------------------------------ wczytanie
def strip_letter(s):
    return re.sub(r"^\s*[A-Fa-f][\)\.]\s*", "", s or "").strip()


def load_md():
    out, cur, src = [], None, ""
    for line in (FOLDER / "NOWE PYTANIA DO BAZY OCT.MD").read_text(encoding="utf-8").splitlines():
        if line.startswith("## Źródło:"):
            src = line.split(":", 1)[1].strip()
            continue
        m = re.match(r"###\s*\d+\.\s*(.*?)(\s+_\(nr \d+\)_)?\s*$", line)
        if m:
            cur = {"q": m.group(1).strip(), "opts": [], "src": "MD: " + src}
            out.append(cur)
            continue
        m = re.match(r"-\s*\*\*([A-Fa-f])\.\*\*\s*(.*)", line)
        if m and cur:
            cur["opts"].append(m.group(2).strip())
    return out


def load_sprawdzenia():
    ws = openpyxl.load_workbook(FOLDER / "Do sprawdzenia.xlsx").active
    out = []
    for r in list(ws.iter_rows(values_only=True))[1:]:
        if not r[0]:
            continue
        opts = [strip_letter(str(c)) for c in r[1:7] if c]
        out.append({"q": str(r[0]).strip(), "opts": opts, "src": "Do sprawdzenia.xlsx"})
    return out


def load_wyjasnienia2():
    ws = openpyxl.load_workbook(FOLDER / "Do wyjasnienia 2.xlsx").active
    out = []
    for r in list(ws.iter_rows(values_only=True))[1:]:
        if not r[1]:
            continue
        opts = [strip_letter(x) for x in str(r[2] or "").split("\n") if x.strip()]
        out.append({"q": str(r[1]).strip(), "opts": opts, "src": f"Do wyjasnienia 2.xlsx (ID {int(float(r[0]))})" if r[0] else "Do wyjasnienia 2.xlsx"})
    return out


def load_docx():
    out, cur = [], None
    for p in docx.Document(FOLDER / "Do wyjasnienia 1.docx").paragraphs:
        t = p.text.strip()
        m = re.match(r"(\d+)\.\s*(.*)", t)
        if m:
            cur = {"q": re.sub(r"\s*\[[^\]]*\]\s*$", "", m.group(2)).strip(), "opts": [], "src": "Do wyjasnienia 1.docx"}
            out.append(cur)
        elif cur and re.match(r"[A-D]\.\s", t):
            cur["opts"].append(strip_letter(t))
    return out


def norm(s):
    return re.sub(r"[^\w]+", " ", (s or "").lower()).strip()


def dedup(items):
    kept, texts = [], []
    for it in items:
        t = norm(it["q"] + " " + " ".join(it["opts"]))
        dup = None
        for k, kt in zip(kept, texts):
            if abs(len(kt) - len(t)) > 0.2 * max(len(kt), len(t), 1):
                continue
            sm = difflib.SequenceMatcher(None, t, kt)
            if sm.real_quick_ratio() >= 0.93 and sm.quick_ratio() >= 0.93 and sm.ratio() >= 0.93:
                dup = k
                break
        if dup:
            dup["src"] += " | " + it["src"]
        else:
            kept.append(it)
            texts.append(t)
    return kept


# ------------------------------------------------------------------ LLM
def llm(model, system, user, tag, web=False, effort="low", max_tokens=6000):
    ck = hashlib.md5(f"{model}|{tag}|{system}|{user}|{web}".encode()).hexdigest()
    with lock:
        if CACHE.exists():
            for line in CACHE.read_text(encoding="utf-8").splitlines():
                r = json.loads(line)
                if r["ck"] == ck:
                    return r["res"]
    body = {"model": model, "max_tokens": max_tokens, "reasoning": {"effort": effort}, "usage": {"include": True},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if web:
        body["plugins"] = [{"id": "web", "max_results": 3}]
    err = None
    for i in range(4):
        try:
            r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": f"Bearer {KEY}"}, json=body, timeout=300)
            if r.status_code != 200:
                err = f"HTTP {r.status_code} {r.text[:150]}"
                time.sleep(4 * (i + 1))
                continue
            d = r.json()
            txt = d["choices"][0]["message"]["content"] or ""
            res = json.loads(re.search(r"\{.*\}", txt, re.S).group(0))
            cost = (d.get("usage") or {}).get("cost") or 0
            res["_cost"] = cost
            with lock:
                cost_total[0] += cost
                with CACHE.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({"ck": ck, "res": res}, ensure_ascii=False) + "\n")
            return res
        except Exception as e:  # noqa: BLE001
            err = repr(e)
            time.sleep(4 * (i + 1))
    return {"error": err}


def qtext(it):
    return it["q"] + "\n" + "\n".join(f"{chr(65 + k)}) {o}" for k, o in enumerate(it["opts"]))


CAT_SYS = ("Classify a maritime exam question (Polish exam for ship officers/masters) into exactly one category:\n"
           "ANGIELSKI - the question text is entirely in English.\n"
           "POKŁAD - questions about calculating something (positions, latitude/longitude, distances, speed, time, tides), flags/signals, stability, "
           "navigational equipment/instruments, seamanship, meteorology.\n"
           "MASTER - legal/regulatory and management questions: Maritime Code (Kodeks morski), acts, SOLAS, MARPOL, IMDG, IMSBC, STCW, ISM, MLC, ship management, "
           "charter, cargo law, salvage, insurance, PSC.\n"
           'Reply JSON only: {"category":"MASTER|POKŁAD|ANGIELSKI"}')
ANS_SYS = ("You answer a Polish maritime exam multiple-choice question. You MUST NOT answer from memory: use the web search results and find the relevant "
           "provision in an authoritative document (Kodeks morski, Polish acts and regulations, SOLAS, MARPOL, STCW, ISM, IMDG, IMSBC, COLREG, MLC, UNCLOS, "
           "IMO circulars, etc.). For calculation questions, take the formula/method from a document and compute. Choose the single best option. "
           'Reply JSON only: {"answer":"A|B|C|D|NONE","source":"document, article/section or URL actually found","quote":"short supporting passage (<=40 words)",'
           '"reasoning":"1-3 sentences"}. Use NONE only if the documents found do not allow choosing.')
ANS_SYS_NOWEB = ("You answer a Polish maritime exam multiple-choice question. Choose the single best option; for calculations compute the result. "
                 'Reply JSON only: {"answer":"A|B|C|D|E|F|NONE","source":"document/article you rely on","quote":"","reasoning":"1-2 sentences"}')
EXP_SYS = ("You write for a Polish maritime exam trainee. Given a question, the chosen correct option and the findings of independent AI checkers (with sources), "
           'write in Polish: "notka" = 1-3 sentences why the checkers agree (cite the document/article they found), "wyjasnienie" = a clear explanation of why this option is '
           'correct and the others are not (4-8 sentences), grounded only in the provided findings. Do not invent articles. Reply JSON only: {"notka":"...","wyjasnienie":"..."}')


def main():
    items = load_sprawdzenia() + load_wyjasnienia2() + load_docx() + load_md()
    print("wczytano:", len(items), {s: sum(1 for i in items if i["src"].startswith(s)) for s in ("MD", "Do sprawdzenia", "Do wyjasnienia 2", "Do wyjasnienia 1")})
    items = [i for i in items if len(i["opts"]) >= 2]
    items = dedup(items)
    print("po scaleniu duplikatów:", len(items))
    if LIMIT:
        step = max(1, len(items) // LIMIT)
        items = items[::step][:LIMIT]
    for n, it in enumerate(items, 1):
        it["no"] = n

    def cat(it):
        r = llm("deepseek/deepseek-v4.1-flash", CAT_SYS, qtext(it), "cat")
        c = (r.get("category") or "").upper()
        it["cat"] = c if c in ("MASTER", "POKŁAD", "ANGIELSKI") else "?"

    DS, LUNA, TERRA = MODELS[0][0], MODELS[2][0], MODELS[4][0]

    def one(it, model, col, web):
        it.setdefault("ai", {})[col] = llm(model, ANS_SYS if web else ANS_SYS_NOWEB, qtext(it), "ans-" + col + ("w" if web else ""), web=web)

    def letter(it, col):
        a = ((it.get("ai", {}).get(col) or {}).get("answer") or "").strip().upper()[:1]
        return a if a and a in "ABCDEF" else ""

    def process(it):
        # etap 1: 2x DeepSeek bez wyszukiwania (tanio); etap 2: Luna z wyszukiwaniem; etap 3 (brak zgody 3 modeli): druga Luna i Terra z wyszukiwaniem
        one(it, DS, "AI1", False)
        one(it, DS, "AI2", False)
        if cost_total[0] >= CAP:
            it["skipped"] = True
            return
        one(it, LUNA, "AI3", True)
        if letter(it, "AI1") and letter(it, "AI1") == letter(it, "AI2") == letter(it, "AI3"):
            return
        if cost_total[0] >= CAP:
            return
        one(it, LUNA, "AI4", True)
        one(it, TERRA, "AI5", True)

    with cf.ThreadPoolExecutor(8) as ex:
        list(ex.map(cat, items))
        done = 0
        for _ in ex.map(process, items):
            done += 1
            if done % 100 == 0:
                print(" pytań", done, "/", len(items), "koszt $%.2f" % cost_total[0], flush=True)

    def finish(it):
        votes = [(c, letter(it, c)) for _, c in MODELS]
        valid = [v for _, v in votes if v]
        top, cnt = (max(((a, valid.count(a)) for a in set(valid)), key=lambda x: x[1]) if valid else ("", 0))
        it["votes"], it["top"], it["cnt"] = votes, top, cnt
        if it.get("skipped"):
            it["notka"], it["wyj"] = "Nie sprawdzone przez AI (limit kosztu)", ""
        elif cnt >= 3:
            finds = "\n".join(f"- {c}: {it['ai'][c].get('source') or '(no search)'} | \"{it['ai'][c].get('quote')}\" | {it['ai'][c].get('reasoning')}"
                              for c, v in votes if v == top)
            e = llm("deepseek/deepseek-v4.1-flash", EXP_SYS, f"{qtext(it)}\n\nCORRECT OPTION: {top}\nFINDINGS:\n{finds}", "exp")
            it["notka"], it["wyj"] = e.get("notka", ""), e.get("wyjasnienie", "")
        else:
            it["notka"] = f"Brak konsensusu (najwięcej {cnt}/5): " + ", ".join(f"{c}={v or '-'}" for c, v in votes)
            it["wyj"] = ""

    with cf.ThreadPoolExecutor(8) as ex:
        list(ex.map(finish, items))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Pytania"
    ws.append(["No", "Pytanie", "Odpowiedzi", "Kategoria", "Odpowiedź własna", "Odpowiedź AI1", "AI2", "AI3", "AI4", "AI5", "Notka", "Wyjaśnienie", "Źródło"])
    for it in items:
        ws.append([it["no"], it["q"], "\n".join(f"{chr(65 + k)}) {o}" for k, o in enumerate(it["opts"])), it["cat"], None]
                  + [v or "-" for _, v in it["votes"]] + [it["notka"], it["wyj"], it["src"]])
    from openpyxl.styles import Alignment, Font
    widths = [6, 60, 70, 12, 14, 10, 8, 8, 8, 8, 60, 80, 30]
    for i, w in enumerate(widths):
        ws.column_dimensions[chr(65 + i)].width = w
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    for c in ws[1]:
        c.font = Font(bold=True)
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = ws.dimensions
    out = OUT
    try:
        wb.save(out)
    except PermissionError:  # plik otwarty w Excelu — zapisz obok pod inną nazwą
        out = OUT.with_name(OUT.stem + "_nowy" + OUT.suffix)
        wb.save(out)
    print("zapisano:", out, "| pytań:", len(items), "| koszt $%.2f" % cost_total[0])
    print("konsensus >=3:", sum(1 for i in items if i["cnt"] >= 3), "| 5/5:", sum(1 for i in items if i["cnt"] == 5),
          "| NONE/błędy:", sum(1 for i in items for _, v in i["votes"] if not v))


main()
