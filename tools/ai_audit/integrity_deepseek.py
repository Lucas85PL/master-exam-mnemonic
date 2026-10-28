"""Tania kontrola INTEGRALNOŚCI TEKSTU pytań wyodrębnionych z PDF (DeepSeek przez OpenRouter): czy treść i warianty są czytelne i kompletne.
NIE ocenia poprawności klucza (klucz = z PDF). Wejście: review/Zgodnosc_z_PDF/do_dodania_pelne.json (pozycje oznaczone 'wybrane'),
wynik: review/Zgodnosc_z_PDF/integralnosc_deepseek.json {indeks: {ok, issue}}. Wymaga .env z OPENROUTER_API_KEY. Wywołania cache'owane w pliku wyniku."""
import concurrent.futures as cf, json, re, sys, time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "review" / "Zgodnosc_z_PDF" / "do_dodania_pelne.json"
OUT = ROOT / "review" / "Zgodnosc_z_PDF" / "integralnosc_deepseek.json"
MODEL = "deepseek/deepseek-v4.1-flash"
KEY = re.search(r"OPENROUTER_API_KEY\s*=\s*(\S+)", (ROOT / ".env").read_text(encoding="utf-8")).group(1)
items = json.load(open(SRC, encoding="utf-8"))
res = json.load(open(OUT, encoding="utf-8")) if OUT.exists() else {}

SYSTEM = ("You check the TEXT INTEGRITY of exam questions extracted from a PDF table (maritime exams). "
          "Do NOT judge whether the marked answer is correct. Report problems only with the extracted text: "
          "garbled or lost characters/symbols (e.g. missing degree signs or Greek letters making numbers ambiguous), truncated or merged sentences, "
          "options that look mixed up or duplicated, text that clearly belongs to a different question, a reference to a figure/drawing/table that is not included, "
          "or missing option text. Minor typos and odd spacing are fine. "
          'Answer with JSON only: {"ok": true|false, "issue": "<max 12 words, empty if ok>"}')


def ask(i):
    it = items[i]
    body = f"Question: {it['q']}\n" + "\n".join(f"{L}) {t}" for L, t in it["opts"].items())
    for attempt in range(4):
        try:
            r = requests.post("https://openrouter.ai/api/v1/chat/completions",
                              headers={"Authorization": "Bearer " + KEY},
                              json={"model": MODEL, "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": body}],
                                    "max_tokens": 1500, "temperature": 0, "reasoning": {"effort": "low"}}, timeout=90)
            if r.status_code == 200:
                txt = r.json()["choices"][0]["message"]["content"] or ""
                m = re.search(r"\{.*\}", txt, re.S)
                return i, json.loads(m.group(0))
            time.sleep(2 * (attempt + 1))
        except Exception:
            time.sleep(2 * (attempt + 1))
    return i, {"ok": None, "issue": "brak odpowiedzi modelu"}


todo = [i for i, it in enumerate(items) if it.get("wybrane") and (str(i) not in res or res[str(i)].get("ok") is None)]
print("do sprawdzenia:", len(todo))
with cf.ThreadPoolExecutor(3) as ex:
    for k, (i, v) in enumerate(ex.map(ask, todo), 1):
        res[str(i)] = v
        if k % 50 == 0:
            json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
bad = [i for i, v in res.items() if v.get("ok") is not True]
print("sprawdzone:", len(res), "| z uwagami:", len(bad))
