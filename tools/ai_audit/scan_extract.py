"""Faza 1 (wersja strukturalna): ekstrakcja pytań ze skanów PDF dwoma modelami wizyjnymi (DeepSeek + Qwen) do JSON, strona po stronie.
Zaznaczenia odręczne (kółka, cyfry) są ignorowane; drukowana linia 'Odp. X' jest zapisywana jako printed_key (niepewny).
Wynik: review/Nowe_21_10/json_<model>/strona_NN.json. Użycie: python scan_extract.py "<plik.pdf>" ; istniejące strony są pomijane (cache)."""
import base64, concurrent.futures as cf, json, re, sys, time
from pathlib import Path

import fitz
import requests

ROOT = Path(__file__).resolve().parents[2]
PDF = Path(sys.argv[1])
OUT = ROOT / "review" / "Nowe_21_10"
KEY = re.search(r"OPENROUTER_API_KEY\s*=\s*(\S+)", (ROOT / ".env").read_text(encoding="utf-8")).group(1)
H = {"Authorization": "Bearer " + KEY}
MODELS = {"deepseek": "deepseek/deepseek-v4.1-flash", "qwen": "qwen/qwen3.7-flash"}
# opcjonalnie: python scan_extract.py plik.pdf <model_id> <strony 8,10,12> <katalog_docelowy np. qwen> — drugi odczyt innym modelem dla wskazanych stron
ONLY_PAGES = None
if len(sys.argv) >= 5:
    MODELS = {sys.argv[4]: sys.argv[2]}
    ONLY_PAGES = [int(x) - 1 for x in sys.argv[3].split(",")]
PROMPT = (
    "This is a scanned page (possibly rotated, upside-down, or a two-page spread with text on both halves) from a Polish multiple-choice exam booklet "
    "(maritime topics). Read it in the correct orientation and extract EVERY multiple-choice question that is visible. "
    "IGNORE handwriting and marks: circles/ticks around options, margin numbers, stamps, black bars, stains. Do NOT say which option was marked by hand. "
    "Return ONLY a JSON array; each element: "
    '{"nr": <printed question number or null>, "question": "<full question text>", "options": ["<text of option 1>", "<option 2>", ...] '
    '(without the letters), "printed_key": "<letter>" or null (ONLY if a PRINTED line such as \'Odp. B\' follows the question), "confidence": "high"|"low"}. '
    "Keep Polish diacritics exactly. Write [?] for unreadable words and set confidence to low. Do not invent text. Skip headings and non-question text.")
doc = fitz.open(PDF)


def render(i):
    r = doc[i].rect
    zoom = max(1.6, min(3.2, 2600 / max(r.width, r.height)))
    return base64.b64encode(doc[i].get_pixmap(matrix=fitz.Matrix(zoom, zoom)).tobytes("jpeg", jpg_quality=88)).decode()


def job(args):
    name, i = args
    d = OUT / f"json_{name}"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"strona_{i + 1:02d}.json"
    if f.exists() and f.stat().st_size > 5:
        return name, i, "cache"
    b64 = render(i)
    for attempt in range(4):
        try:
            r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=H, timeout=300,
                              json={"model": MODELS[name], "temperature": 0, "max_tokens": 9000, "reasoning": {"effort": "low"},
                                    "messages": [{"role": "user", "content": [{"type": "text", "text": PROMPT},
                                                                              {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64}}]}]})
            if r.status_code == 200:
                t = (r.json()["choices"][0]["message"]["content"] or "").strip()
                m = re.search(r"\[.*\]", t, re.S)
                if m:
                    data = json.loads(m.group(0))
                    f.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
                    return name, i, "ok"
            time.sleep(3 * (attempt + 1))
        except Exception:
            time.sleep(3 * (attempt + 1))
    return name, i, "BŁĄD"


jobs = [(n, i) for i in (ONLY_PAGES if ONLY_PAGES is not None else range(len(doc))) for n in MODELS]
with cf.ThreadPoolExecutor(4) as ex:
    res = list(ex.map(job, jobs))
for n in MODELS:
    cnt = {k: sum(1 for a, _, v in res if a == n and v == k) for k in ("ok", "cache", "BŁĄD")}
    total = sum(len(json.loads(p.read_text(encoding="utf-8"))) for p in (OUT / f"json_{n}").glob("strona_*.json"))
    print(n, cnt, "| pytań łącznie:", total)
