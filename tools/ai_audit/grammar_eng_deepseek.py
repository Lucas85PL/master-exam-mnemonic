"""Szybka kontrola GRUBYCH błędów językowych w nowo dodanych pytaniach ENG (DeepSeek przez OpenRouter): np. powtórzone słowa, zepsute zdanie po złym
odczycie z PDF. NIE poprawia pytań i NIE ocenia merytoryki ani drobnej stylistyki. Baza tylko do odczytu.
Wynik: review/Zgodnosc_z_PDF/gramatyka_eng.json oraz lista MD/TXT podejrzanych. Użycie: python grammar_eng_deepseek.py [baza.db]"""
import concurrent.futures as cf, json, re, sqlite3, sys, time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
DB = sys.argv[1] if len(sys.argv) > 1 else str(Path.home() / "Documents" / "memonic_app.db")
OUT = ROOT / "review" / "Zgodnosc_z_PDF" / "gramatyka_eng.json"
KEY = re.search(r"OPENROUTER_API_KEY\s*=\s*(\S+)", (ROOT / ".env").read_text(encoding="utf-8")).group(1)
H = {"Authorization": "Bearer " + KEY}
con = sqlite3.connect(f"file:{Path(DB).as_posix()}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
rows = con.execute("select id,pytanie,odp_a,odp_b,odp_c,odp_d from questions where kategoria='Angielski' and ai_verified like 'pdf_urzad:dodane_z_arkusza%' order by id").fetchall()
items = {r["id"]: r["pytanie"] + "\n" + "\n".join(f"{L.upper()}) {r['odp_' + L]}" for L in "abcd" if r["odp_" + L]) for r in rows}
print("pytań ENG do sprawdzenia:", len(items))
SYSTEM = ("You review English maritime exam questions (a question stem plus answer options, extracted from a PDF) ONLY for GROSS language errors, "
          "typically caused by faulty extraction: repeated or duplicated words/phrases (e.g. 'Master master master'), a stem or option that is not a "
          "grammatical sentence or phrase at all, scrambled word order, words glued together or split into pieces, clearly missing key words that make the "
          "sentence unreadable, text from another question mixed in, or obvious garbage characters. "
          "Do NOT report: minor style, terminology choices, Polish-English flavour, missing articles, small typos, unusual-but-understandable phrasing, "
          "factual correctness, or symbols/figures. When in doubt, answer ok. "
          'Reply with JSON only: {"ok": true|false, "issue": "<max 15 words, empty if ok>"}')


def ask(qid):
    for attempt in range(4):
        try:
            r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=H, timeout=90,
                              json={"model": "deepseek/deepseek-v4.1-flash", "temperature": 0, "max_tokens": 1500, "reasoning": {"effort": "low"},
                                    "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": items[qid]}]})
            if r.status_code == 200:
                m = re.search(r"\{.*\}", r.json()["choices"][0]["message"]["content"] or "", re.S)
                return qid, json.loads(m.group(0))
            time.sleep(2 * (attempt + 1))
        except Exception:
            time.sleep(2 * (attempt + 1))
    return qid, {"ok": None, "issue": "brak odpowiedzi modelu"}


res = json.load(open(OUT, encoding="utf-8")) if OUT.exists() else {}
todo = [q for q in items if str(q) not in res or res[str(q)].get("ok") is None]
print("do oceny:", len(todo))
with cf.ThreadPoolExecutor(3) as ex:
    for k, (q, v) in enumerate(ex.map(ask, todo), 1):
        res[str(q)] = v
        if k % 50 == 0:
            json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
bad = [q for q in items if res.get(str(q), {}).get("ok") is False]
unk = [q for q in items if res.get(str(q), {}).get("ok") is None]
print("sprawdzone:", len(res), "| podejrzane:", len(bad), "| bez odpowiedzi:", len(unk))
