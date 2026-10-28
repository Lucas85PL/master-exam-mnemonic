"""Niezalezna weryfikacja odpowiedzi z bazy przez 2 modele (OpenRouter).

Modele dostaja pytanie i warianty BEZ odpowiedzi z bazy (test "na slepo").
Pytanie przechodzi tylko, gdy OBA modele wskaza ta sama litere co baza
i zaden nie zglosi problemu z trescia (np. blad OCR).

Wyniki: verify_<kat>_results.jsonl (wznawialne). Uzycie:
  python verify_master_ai.py --db <app.db> --limit 8      # pilot
  python verify_master_ai.py --db <app.db>                # calosc
"""
import argparse
import json
import re
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

HERE = Path(__file__).parent
MODELS = {
    "gpt": "openai/gpt-6.1-sol",
    "sonnet": "anthropic/claude-sonnet-5.5",
}
SYSTEM = (
    "Jesteś egzaminatorem morskim (egzamin na Kapitana żeglugi wielkiej). "
    "Pytania zostały wyciągnięte z PDF przez OCR i mogą zawierać błędy odczytu. "
    "Wybierz jedną najlepszą odpowiedź na pytanie testowe, opierając się na wiedzy "
    "i aktach prawnych (Kodeks morski, STCW, COLREG, SOLAS, MARPOL, MLC, UNCLOS itd.). "
    'Zwróć WYŁĄCZNIE JSON: {"answer":"A|B|C|D|NONE","confidence":0-100,'
    '"ocr_problem":true|false,"note":"max 1 zdanie po polsku"}. '
    "Pytania mają zwykle 3 warianty (A-C); brak wariantu D jest NORMALNY i NIE jest błędem OCR. "
    "Pytania bywają krótkie lub skrótowe - to też normalne. "
    "ocr_problem=true TYLKO gdy w tekście jest wyraźnie uszkodzone słowo/liczba/znak, "
    "które zmienia sens pytania lub odpowiedzi (np. obcięte słowo, zła cyfra); drobna "
    "literówka bez wpływu na sens to false. "
    "answer=NONE gdy żadna odpowiedź nie jest poprawna lub nie da się rozstrzygnąć."
)


def load_key():
    for line in (HERE / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith("OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("Brak OPENROUTER_API_KEY w .env")


def build_prompt(r):
    parts = [f"Pytanie:\n{r['pytanie'].strip()}\n"]
    for k in "abcd":
        v = r[f"odp_{k}"]
        if v:
            parts.append(f"{k.upper()}: {v}")
    return "\n".join(parts)


def call(key, model, prompt, retries=3):
    body = {
        "model": model,
        "max_tokens": 8000,
        "reasoning": {"effort": "medium"},
        "usage": {"include": True},
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
    }
    err = None
    for i in range(retries):
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json=body,
                timeout=180,
            )
            if resp.status_code != 200:
                err = f"HTTP {resp.status_code}: {resp.text[:200]}"
                time.sleep(3 * (i + 1))
                continue
            d = resp.json()
            text = d["choices"][0]["message"]["content"] or ""
            m = re.search(r"\{.*\}", text, re.S)
            parsed = json.loads(m.group(0))
            cost = (d.get("usage") or {}).get("cost") or 0
            return parsed, cost, None
        except Exception as e:  # noqa: BLE001
            err = repr(e)
            time.sleep(3 * (i + 1))
    return None, 0, err


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--like", default="Kapitan%")
    ap.add_argument("--out", default=str(HERE / "verify_master_results.jsonl"))
    ap.add_argument("--limit", type=int)
    ap.add_argument("--ids-file", help="plik z ID (po jednym w linii) do przetestowania")
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()

    key = load_key()
    con = sqlite3.connect(a.db)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT * FROM questions WHERE kategoria LIKE ? ORDER BY id", (a.like,)
    ).fetchall()
    out = Path(a.out)
    done = set()
    if out.exists():
        for ln in out.read_text(encoding="utf-8").splitlines():
            done.add(json.loads(ln)["id"])
    if a.ids_file:
        want = {int(x) for x in Path(a.ids_file).read_text().split()}
        rows = [r for r in rows if r["id"] in want]
    todo = [r for r in rows if r["id"] not in done]
    if a.limit:
        todo = todo[: a.limit]
    print(f"{len(rows)} pytan, do zrobienia {len(todo)}", flush=True)

    lock = threading.Lock()
    total = {"cost": 0.0, "n": 0}

    def work(r):
        prompt = build_prompt(r)
        res, cost = {}, 0.0
        for name, model in MODELS.items():
            p, c, e = call(key, model, prompt)
            res[name] = p if p else {"error": e}
            cost += c
        db = r["poprawna_odpowiedz"]
        ok = all(
            isinstance(v, dict)
            and v.get("answer") == db
            and not v.get("ocr_problem")
            for v in res.values()
        )
        rec = {"id": r["id"], "db_answer": db, "pass": ok, "models": res, "cost": cost}
        with lock:
            with out.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            total["cost"] += cost
            total["n"] += 1
            if total["n"] % 10 == 0:
                print(f"{total['n']}/{len(todo)}  koszt ${total['cost']:.2f}", flush=True)

    with ThreadPoolExecutor(a.workers) as ex:
        list(ex.map(work, todo))
    print(f"Gotowe: {total['n']} pytan, koszt ${total['cost']:.2f}")


if __name__ == "__main__":
    sys.exit(main())
