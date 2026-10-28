"""Tłumaczenie wyjaśnień PL -> EN (DeepSeek) dla pytań ENG, które mają odpowiednik PL z tą samą odpowiedzią (wynik eng_pl_match.py).
Baza tylko do odczytu. Wynik: review/Zgodnosc_z_PDF/eng_wyjasnienia.json {id_eng: {"expl": "...", "pl": id_pl}}."""
import concurrent.futures as cf, json, re, sqlite3, sys, time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
DB = sys.argv[1] if len(sys.argv) > 1 else str(Path.home() / "Documents" / "memonic_app.db")
M = json.load(open(ROOT / "review" / "Zgodnosc_z_PDF" / "eng_pl_matches.json", encoding="utf-8"))
OUT = ROOT / "review" / "Zgodnosc_z_PDF" / "eng_wyjasnienia.json"
KEY = re.search(r"OPENROUTER_API_KEY\s*=\s*(\S+)", (ROOT / ".env").read_text(encoding="utf-8")).group(1)
H = {"Authorization": "Bearer " + KEY}
con = sqlite3.connect(f"file:{Path(DB).as_posix()}?mode=ro", uri=True, check_same_thread=False)
con.row_factory = sqlite3.Row
SYSTEM = ("You translate Polish maritime exam explanations into clear, concise English. Keep the meaning exactly; do not add facts. "
          "The Polish explanation refers to Polish option letters; the English question has its own options, possibly in a different order. "
          "Rewrite any letter references so they match the ENGLISH option letters. "
          "Start with exactly: 'The correct answer is <ENGLISH LETTER>.' (replace the Polish 'Prawidłowa odpowiedź to X.'). "
          "Output only the translated explanation text.")


def fmt(r):
    return r["pytanie"] + "\n" + "\n".join(f"  {L.upper()}) {r['odp_' + L]}" for L in "abcd" if r["odp_" + L]) + f"\n  [correct: {r['poprawna_odpowiedz']}]"


def prep(eid, v):
    e = con.execute("select * from questions where id=?", (int(eid),)).fetchone()
    p = con.execute("select * from questions where id=?", (v["match"],)).fetchone()
    ex = con.execute("select explanation from explanation_cache where question_id=? order by created_at_ms desc limit 1", (p["id"],)).fetchone()
    if not ex or ex[0].startswith("UWAGA"):
        return None
    return "ENGLISH QUESTION:\n" + fmt(e) + "\n\nPOLISH QUESTION:\n" + fmt(p) + "\n\nPOLISH EXPLANATION:\n" + ex[0], p["id"]


def job(args):
    eid, body, pid = args
    for attempt in range(4):
        try:
            r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=H, timeout=120,
                              json={"model": "deepseek/deepseek-v4.1-flash", "temperature": 0, "max_tokens": 2500, "reasoning": {"effort": "low"},
                                    "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": body}]})
            if r.status_code == 200:
                t = (r.json()["choices"][0]["message"]["content"] or "").strip()
                if t:
                    return eid, {"expl": t, "pl": pid}
            time.sleep(2 * (attempt + 1))
        except Exception:
            time.sleep(2 * (attempt + 1))
    return eid, {"error": True}


res = json.load(open(OUT, encoding="utf-8")) if OUT.exists() else {}
todo = []
for k, v in M.items():
    if v.get("match") and v.get("same_answer") is True and (k not in res or (res[k] or {}).get("error")):
        pr = prep(k, v)
        if pr is None:
            res[k] = None
        else:
            todo.append((k, pr[0], pr[1]))
print("do przetłumaczenia:", len(todo))
with cf.ThreadPoolExecutor(3) as ex:
    for n, (eid, r) in enumerate(ex.map(job, todo), 1):
        res[eid] = r
        if n % 40 == 0:
            json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("gotowe:", sum(1 for v in res.values() if v and v.get("expl")), "| bez wyjaśnienia PL:", sum(1 for v in res.values() if v is None), "| błędy:", sum(1 for v in res.values() if v and v.get("error")))
