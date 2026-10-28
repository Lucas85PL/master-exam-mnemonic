"""Roj 'Wyjasnij AI': 3 x Claude Haiku 5.5 (reasoning medium) na kazde pytanie z bazy (bez obrazkow), prompt IDENTYCZNY jak w aplikacji
(app/lib/domain/explain_prompt.dart, wersja v6-best-option). Baza jest tylko CZYTANA. Wynik: review/Wyjasnij_AI/*.jsonl (cache), konsensus.json.
  python explain_swarm.py --limit 10      # pilot (koszt)
  python explain_swarm.py                 # cala baza (limit kosztu --cap USD)"""
import argparse, hashlib, json, re, sqlite3, sys, threading, time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "review" / "Wyjasnij_AI"; OUT.mkdir(exist_ok=True)
ap = argparse.ArgumentParser(); ap.add_argument("--limit", type=int, default=0); ap.add_argument("--cap", type=float, default=100.0); ap.add_argument("--workers", type=int, default=16)
args = ap.parse_args()
MODEL = "anthropic/claude-haiku-5.5"; PV = "v6-best-option"
KEY = next(l.split("=", 1)[1].strip() for l in (ROOT / ".env").read_text(encoding="utf-8").splitlines() if l.startswith("OPENROUTER_API_KEY="))
SYS = """
Jesteś egzaminatorem morskim. Pytania i odpowiedzi zostały wyciągnięte z dokumentów przez OCR, więc zapisana poprawna odpowiedź (litera A-D) mogła zostać błędnie odczytana lub błędnie oznaczona.
Najpierw samodzielnie, wewnętrznie sprawdź, którą odpowiedź uważasz za prawidłową dla treści pytania i wariantów (zwróć uwagę na ewentualne błędy OCR w treści pytania lub odpowiedzi), a dopiero potem porównaj ją z odpowiedzią zapisaną w bazie.
Swoją weryfikację i wyjaśnienie opieraj PRIORYTETOWO na dokumentach morskich: Kodeks morski (polski), STCW, COLREG, MARPOL, ISM Code, LSA Code, FFE Code, MLC, UNCLOS, ISPS Code, IMDG Code, a także SOLAS. Gdy to możliwe, wskaż konkretny dokument i przepis (np. "SOLAS II-2/10"); nie podawaj numerów przepisów, jeśli nie jesteś ich pewien. Wiedzy ogólnej używaj tylko uzupełniająco.
Zasady oceny:
- Wybierz tę odpowiedź, która jest NAJTRAFNIEJSZA spośród podanych wariantów, nawet jeśli jest sformułowana skrótowo lub nieprecyzyjnie (np. "statek posiada certyfikat" zamiast "spalarka posiada certyfikat"). Nieprecyzyjne sformułowanie NIE jest powodem do zastrzeżeń, jeśli żaden inny wariant nie jest lepszy.
- Odpowiedź zawierającą wyjątek lub zastrzeżenie przepisu (np. "nie, chyba że...") jest prawidłowa, gdy przepis taki wyjątek przewiduje, a warianty bezwzględne ("zawsze", "bezwzględnie nie", "nigdy") są wtedy fałszywe.
- Oceniaj wyłącznie merytorycznie, na podstawie przepisów. Nie zgaduj, jaka odpowiedź jest "w typowym kluczu egzaminacyjnym" i nie podważaj odpowiedzi z bazy z powodu takich przypuszczeń.
- Zastrzeżenia (agree=false) zgłaszaj tylko wtedy, gdy inny wariant jest wyraźnie lepszy niż ten z bazy, wiele wariantów jest równie poprawnych, żaden nie pasuje albo treść jest ewidentnie uszkodzona przez OCR.

Zwróć WYŁĄCZNIE obiekt JSON (bez markdown i bez dodatkowego tekstu):
{"my_answer":"A|B|C|D|NONE","agree":true|false,"explanation":"..."}
- my_answer: litera, którą Ty uważasz za prawidłową (NONE, gdy żadna nie pasuje).
- agree: true TYLKO gdy my_answer jest taka sama jak odpowiedź z bazy i nie masz żadnych zastrzeżeń (ani merytorycznych, ani co do uszkodzenia treści przez OCR). W przeciwnym razie false.
- explanation: po polsku, 2-5 zdań, bez markdown i list. Gdy agree=true: uzasadnij, dlaczego odpowiedź z bazy jest prawidłowa. Gdy agree=false: opisz swoje zastrzeżenia i którą odpowiedź uważasz za poprawną. Nie dopisuj nagłówków ani zdań w rodzaju "Prawidłowa odpowiedź to" - dodaje je aplikacja.
""".strip()
db = sqlite3.connect(f"file:{(Path.home()/'Documents'/'memonic_app.db').as_posix()}?mode=ro", uri=True)
rows = db.execute("SELECT id,pytanie,odp_a,odp_b,odp_c,odp_d,poprawna_odpowiedz FROM questions WHERE image_path IS NULL ORDER BY id").fetchall(); db.close()
def chash(r): return hashlib.sha256("|".join([r[1], r[2] or "", r[3] or "", r[4] or "", r[5] or "", r[6], PV]).encode("utf-8")).hexdigest()
groups = defaultdict(list)            # unikalna tresc -> lista ID (jedno wywolanie x3 na tresc, wynik dla wszystkich ID)
for r in rows: groups[chash(r)].append(r)
uniq = [(h, g[0], [x[0] for x in g]) for h, g in groups.items()]
if args.limit: uniq = uniq[:args.limit]
print("wierszy:", len(rows), "unikalnych tresci:", len(uniq), flush=True)
def user_prompt(r):
    b = [f"Pytanie:\n{r[1].strip()}", ""]
    for k, v in zip("ABCD", r[2:6]):
        if (v or "").strip(): b.append(f"{k}: {v.strip()}")
    b += ["", f"Poprawna odpowiedź: {r[6]}"]
    return "\n".join(b) + "\n"
CACHE = OUT / "cache_haiku.jsonl"; _c = {}; _l = threading.Lock(); COST = [0.0]
if CACHE.exists():
    for line in CACHE.read_text(encoding="utf-8").splitlines():
        d = json.loads(line); _c[(d["h"], d["i"])] = d
def call(h, i, r):
    with _l:
        if (h, i) in _c: return _c[(h, i)]
        if COST[0] >= args.cap: return {"h": h, "i": i, "error": "cap"}
    body = {"model": MODEL, "max_tokens": 8000, "reasoning": {"effort": "medium"}, "usage": {"include": True},
            "messages": [{"role": "system", "content": SYS}, {"role": "user", "content": user_prompt(r)}]}
    err = None
    for a in range(4):
        try:
            x = requests.post("https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": f"Bearer {KEY}"}, json=body, timeout=240)
            if x.status_code != 200:
                err = f"HTTP {x.status_code} {x.text[:100]}"
                if x.status_code in (401, 402, 403): break
                time.sleep(3 * (a + 1)); continue
            j = x.json(); raw = j["choices"][0]["message"]["content"] or ""
            m = re.search(r"\{[\s\S]*\}", raw); data = json.loads(m.group(0))
            res = {"h": h, "i": i, "my": str(data.get("my_answer", "")).strip().upper()[:4], "agree": data.get("agree") is True, "expl": (data.get("explanation") or "").strip(), "cost": (j.get("usage") or {}).get("cost") or 0}
            with _l:
                COST[0] += res["cost"]; _c[(h, i)] = res
                with CACHE.open("a", encoding="utf-8") as f: f.write(json.dumps(res, ensure_ascii=False) + "\n")
            return res
        except Exception as e:  # noqa: BLE001
            err = repr(e); time.sleep(3 * (a + 1))
    return {"h": h, "i": i, "error": err}
def work(t):
    h, r, ids = t
    return h, [call(h, i, r) for i in range(3)]
done = {}; t0 = time.time(); errs = 0
with ThreadPoolExecutor(args.workers) as ex:
    for n, (h, rs) in enumerate(ex.map(work, uniq), 1):
        done[h] = rs; errs += sum(1 for x in rs if "error" in x)
        if n % 100 == 0 or n == len(uniq): print(f"{n}/{len(uniq)} koszt ${COST[0]:.3f} bledy {errs} {time.time()-t0:.0f}s", flush=True)
res = []
for h, r, ids in uniq:
    rs = done[h]; ok = all("error" not in x for x in rs)
    res.append({"hash": h, "ids": ids, "key": r[6], "pytanie": r[1], "opcje": {k: v for k, v in zip("ABCD", r[2:6]) if v}, "agents": [{"my": x.get("my"), "agree": x.get("agree"), "expl": x.get("expl"), "error": x.get("error")} for x in rs],
                "consensus": ok and all(x["my"] == r[6] and x["agree"] for x in rs)})
(OUT / ("konsensus_pilot.json" if args.limit else "konsensus.json")).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print("konsensus 3/3:", sum(x["consensus"] for x in res), "z", len(res), "| koszt tej sesji $%.3f" % COST[0])
