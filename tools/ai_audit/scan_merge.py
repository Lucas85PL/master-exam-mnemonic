"""Faza 2-3: konsensus dwóch odczytów OCR (DeepSeek + Qwen) i kontrola gramatyki DeepSeekiem.
Wejście: review/Nowe_21_10/json_deepseek|json_qwen. Wyjście: nowe_pytania_surowe.json/.md (po konsensusie i kontroli struktury),
nowe_pytania_po_gramatyce.json/.md (bez pytań ze zepsutą gramatyką), odrzucone.json (z powodem)."""
import concurrent.futures as cf, difflib, json, re, sys, time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "review" / "Nowe_21_10"
KEY = re.search(r"OPENROUTER_API_KEY\s*=\s*(\S+)", (ROOT / ".env").read_text(encoding="utf-8")).group(1)
H = {"Authorization": "Bearer " + KEY}


def norm(s):
    return re.sub(r"[^\w]+", " ", (s or "").lower()).strip()


def load(name):
    out = {}
    for p in sorted((D / f"json_{name}").glob("strona_*.json")):
        page = int(re.search(r"(\d+)", p.stem).group(1))
        data = json.loads(p.read_text(encoding="utf-8"))
        out[page] = [q for q in data if isinstance(q, dict) and q.get("question") and isinstance(q.get("options"), list)]
    return out


def text(q):
    return norm(q["question"]) + " | " + " | ".join(norm(o) for o in q["options"])


ds, qw = load("deepseek"), load("qwen")
accepted, rejected = [], []
for page, qs in ds.items():
    others = qw.get(page, [])
    used = set()
    for q in qs:
        why = None
        if len(q["options"]) < 2:
            why = "mniej niż 2 odpowiedzi"
        elif len(q["question"].strip()) < 12:
            why = "zbyt krótka treść pytania"
        elif "[?]" in json.dumps(q, ensure_ascii=False) or "..." in q["question"] or "…" in q["question"]:
            why = "nieczytelne fragmenty ([?]/…)"
        elif q.get("confidence") == "low":
            why = "niska pewność odczytu (model 1)"
        best, bj = 0.0, None
        for j, o in enumerate(others):
            if j in used:
                continue
            s = difflib.SequenceMatcher(None, text(q), text(o)).ratio()
            if s > best:
                best, bj = s, j
        if why is None and (bj is None or best < 0.85):
            why = f"brak zgodności z drugim odczytem (podobieństwo {best:.2f})"
        elif why is None and others[bj].get("confidence") == "low":
            why = "niska pewność odczytu (model 2)"
        if bj is not None and best >= 0.85:
            used.add(bj)
        rec = dict(strona=page, nr=q.get("nr"), question=q["question"].strip(), options=[o.strip() for o in q["options"]],
                   printed_key=q.get("printed_key"), zgodnosc=round(best, 2))
        (rejected if why else accepted).append({**rec, "powod": why} if why else rec)
print("odczyt DeepSeek:", sum(len(v) for v in ds.values()), "| Qwen:", sum(len(v) for v in qw.values()),
      "| po konsensusie i strukturze:", len(accepted), "| odrzucone:", len(rejected))
(D / "nowe_pytania_surowe.json").write_text(json.dumps(accepted, ensure_ascii=False, indent=1), encoding="utf-8")

# ---- kontrola gramatyki (DeepSeek, tekst)
SYSTEM = ("You review Polish exam questions (a question stem plus answer options) extracted from a poor-quality scan. Decide whether the text is reasonably "
          "grammatical and coherent Polish: the question reads as a sensible question and every option is a sensible continuation/answer. "
          "REJECT only clear parsing/OCR damage: sentences that make no sense, scrambled or repeated words, words that are clearly garbled or glued, "
          "text from two different questions mixed, an option that does not fit the question at all, or obviously truncated text. "
          "Do NOT reject for minor typos, legal-style wording or if the factual content seems odd. "
          'Reply with JSON only: {"ok": true|false, "issue": "<max 12 words, empty if ok>"}')


def check(i):
    q = accepted[i]
    body = q["question"] + "\n" + "\n".join(f"{chr(97 + k)}) {o}" for k, o in enumerate(q["options"]))
    for attempt in range(4):
        try:
            r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=H, timeout=90,
                              json={"model": "deepseek/deepseek-v4.1-flash", "temperature": 0, "max_tokens": 1500, "reasoning": {"effort": "low"},
                                    "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": body}]})
            if r.status_code == 200:
                m = re.search(r"\{.*\}", r.json()["choices"][0]["message"]["content"] or "", re.S)
                return i, json.loads(m.group(0))
            time.sleep(2 * (attempt + 1))
        except Exception:
            time.sleep(2 * (attempt + 1))
    return i, {"ok": None, "issue": "brak odpowiedzi modelu"}


with cf.ThreadPoolExecutor(3) as ex:
    verdicts = dict(ex.map(check, range(len(accepted))))
good = []
for i, q in enumerate(accepted):
    v = verdicts[i]
    if v.get("ok") is True:
        good.append(q)
    else:
        rejected.append({**q, "powod": "gramatyka/parsowanie: " + (v.get("issue") or "brak oceny")})
print("po kontroli gramatyki:", len(good), "| odrzucone razem:", len(rejected))
(D / "nowe_pytania_po_gramatyce.json").write_text(json.dumps(good, ensure_ascii=False, indent=1), encoding="utf-8")
(D / "odrzucone.json").write_text(json.dumps(rejected, ensure_ascii=False, indent=1), encoding="utf-8")


def md(items, title):
    out = [f"# {title}", "", f"Liczba pytań: {len(items)}", ""]
    for n, q in enumerate(items, 1):
        out.append(f"{n}. {q['question']}  _(str. {q['strona']}, nr {q['nr']})_")
        for k, o in enumerate(q["options"]):
            out.append(f"   {chr(97 + k)}) {o}")
        if q.get("printed_key"):
            out.append(f"   _(drukowana odp. w skanie: {q['printed_key']} — niepewna)_")
        out.append("")
    return "\n".join(out)


(D / "nowe_pytania_surowe.md").write_text(md(accepted, "Pytania ze skanów po konsensusie dwóch odczytów OCR"), encoding="utf-8")
(D / "nowe_pytania_po_gramatyce.md").write_text(md(good, "Pytania ze skanów po kontroli gramatyki"), encoding="utf-8")
