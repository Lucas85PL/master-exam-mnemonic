"""Tani przeglad bazy (Pokład + Angielski): Luna -> DeepSeek V4.1 Flash. Slepy test odpowiedzi + kompletnosc tresci."""
import argparse, json, random, re, sqlite3, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests

HERE = Path(__file__).parent
DB = "C:/Users/Lukasz/Documents/memonic_app.db"
MODELS = {"luna": "openai/gpt-6-luna", "deepseek": "deepseek/deepseek-v4.1-flash"}
SYSTEM = (
    "Jesteś egzaminatorem morskim. Dostajesz pytanie testowe z egzaminu (oficer wachtowy / starszy oficer pokładowy, "
    "także pytania z języka angielskiego). Tekst mógł zostać uszkodzony przy wyciąganiu z PDF. "
    "Wybierz jedną najlepszą odpowiedź (wybierz najtrafniejszą spośród podanych, nawet jeśli sformułowana skrótowo). "
    'Zwróć WYŁĄCZNIE JSON: {"answer":"A|B|C|D|NONE","confidence":0-100,"incomplete":true|false,'
    '"needs_figure":true|false,"note":"max 1 zdanie po polsku"}. '
    "incomplete=true TYLKO gdy treść pytania lub odpowiedzi jest wyraźnie ucięta, brakuje jej początku/końca albo zawiera "
    "uszkodzone słowa/liczby zmieniające sens. Brak wariantu D jest normalny, a krótkie pytania też. "
    "needs_figure=true gdy pytanie odwołuje się do rysunku/zdjęcia/schematu, którego nie widzisz. "
    "answer=NONE gdy żadna odpowiedź nie pasuje lub nie da się rozstrzygnąć."
)

def key():
    for l in (HERE / ".env").read_text(encoding="utf-8").splitlines():
        if l.startswith("OPENROUTER_API_KEY="): return l.split("=", 1)[1].strip()

def prompt(r):
    opts = "\n".join(f"{k.upper()}: {r['odp_'+k]}" for k in "abcd" if r["odp_" + k])
    return f"Kategoria: {r['kategoria']} / {r['tematyka']}\n\nPytanie:\n{r['pytanie'].strip()}\n\n{opts}"

def call(k, model, text):
    body = {"model": model, "max_tokens": 3000, "reasoning": {"effort": "low"}, "usage": {"include": True},
            "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": text}]}
    err = None
    for i in range(3):
        try:
            r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": f"Bearer {k}"}, json=body, timeout=180)
            if r.status_code != 200: err = f"HTTP {r.status_code}"; time.sleep(3 * (i + 1)); continue
            d = r.json(); t = d["choices"][0]["message"]["content"] or ""
            return json.loads(re.search(r"\{.*\}", t, re.S).group(0)), (d.get("usage") or {}).get("cost") or 0, None
        except Exception as e:
            err = repr(e); time.sleep(3 * (i + 1))
    return None, 0, err

def suspicious(res, db_letter):
    if not isinstance(res, dict) or "answer" not in res: return None
    return res.get("answer") != db_letter or bool(res.get("incomplete"))

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30); ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="cheap_batch1.jsonl"); ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row
    rows = c.execute("select * from questions where kategoria not like 'Kapitan%'").fetchall()
    random.seed(a.seed)
    pk = [r for r in rows if r["kategoria"].startswith("Dzia")]; en = [r for r in rows if r["kategoria"].startswith("Angiel")]
    n_en = round(a.n * len(en) / len(rows))
    sample = random.sample(pk, a.n - n_en) + random.sample(en, n_en)
    k = key(); lock = threading.Lock(); out = Path(a.out); out.write_text("", encoding="utf-8")
    def work(r):
        text = prompt(r); rec = {"id": r["id"], "kategoria": r["kategoria"], "db": r["poprawna_odpowiedz"], "cost": 0}
        for name, m in MODELS.items():
            res, cost, err = call(k, m, text)
            rec[name] = res if res else {"error": err}; rec["cost"] += cost
        with lock: out.open("a", encoding="utf-8").write(json.dumps(rec, ensure_ascii=False) + "\n")
    with ThreadPoolExecutor(a.workers) as ex: list(ex.map(work, sample))
    print("gotowe", len(sample))
