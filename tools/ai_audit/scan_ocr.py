"""Faza 1: OCR skanów pytań (PDF ze skanami) przez DeepSeek (model z obsługą obrazów, OpenRouter) -> Markdown.
Zaznaczenia odpowiedzi odręcznie (kółka, cyfry na marginesie) są pomijane (to nie jest klucz). Wynik: review/Nowe_21_10/strona_NN.md + calosc.md.
Użycie: python scan_ocr.py "<plik.pdf>" ; wywołania cache'owane (istniejące strony są pomijane)."""
import base64, concurrent.futures as cf, re, sys, time
from pathlib import Path

import fitz
import requests

ROOT = Path(__file__).resolve().parents[2]
PDF = Path(sys.argv[1])
OUT = ROOT / "review" / "Nowe_21_10"
OUT.mkdir(parents=True, exist_ok=True)
KEY = re.search(r"OPENROUTER_API_KEY\s*=\s*(\S+)", (ROOT / ".env").read_text(encoding="utf-8")).group(1)
H = {"Authorization": "Bearer " + KEY}
MODEL = "deepseek/deepseek-v4.1-flash"
PROMPT = ("This is a scanned page of a Polish multiple-choice exam test (maritime law). Transcribe ALL printed text exactly as Markdown, keeping Polish diacritics, "
          "the question numbers and the options in the form 'a) ...', 'b) ...', 'c) ...'. Keep the original line order. "
          "IGNORE all handwriting and marks: circles or ticks around options, margin numbers, black bars, stains. Do NOT indicate which option was marked. "
          "If a word is unreadable write [?]. Output only the transcription, no comments.")
doc = fitz.open(PDF)


def ocr(i):
    f = OUT / f"strona_{i + 1:02d}.md"
    if f.exists() and f.stat().st_size > 50:
        return i, "cache"
    pix = doc[i].get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
    b64 = base64.b64encode(pix.tobytes("jpeg", jpg_quality=88)).decode()
    for attempt in range(4):
        try:
            r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=H, timeout=240,
                              json={"model": MODEL, "temperature": 0, "max_tokens": 6000, "reasoning": {"effort": "low"},
                                    "messages": [{"role": "user", "content": [{"type": "text", "text": PROMPT},
                                                                              {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + b64}}]}]})
            if r.status_code == 200:
                t = (r.json()["choices"][0]["message"]["content"] or "").strip()
                if t:
                    f.write_text(t, encoding="utf-8")
                    return i, "ok"
            time.sleep(3 * (attempt + 1))
        except Exception:
            time.sleep(3 * (attempt + 1))
    return i, "BŁĄD"


with cf.ThreadPoolExecutor(3) as ex:
    res = list(ex.map(ocr, range(len(doc))))
print("strony:", len(doc), "| wyniki:", {k: sum(1 for _, v in res if v == k) for k in ("ok", "cache", "BŁĄD")})
parts = []
for i in range(len(doc)):
    f = OUT / f"strona_{i + 1:02d}.md"
    if f.exists():
        parts.append(f"\n\n<!-- strona {i + 1} -->\n\n" + f.read_text(encoding="utf-8"))
(OUT / "calosc.md").write_text("".join(parts), encoding="utf-8")
print("zapisano calosc.md")
