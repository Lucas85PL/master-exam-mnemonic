"""Wdrożenie pytań z Zbior_nowych_pytan_AI.xlsx do bazy (obie bazy: Documents + seed), wg kategorii z Excela.
 - 5/5 identycznych odpowiedzi AI -> pewne (z wyjaśnieniem);
 - 3-4 zgodne (<5) -> dodane + oznaczone NIEPEWNE (ai_disputed), z wyjaśnieniem;
 - reszta (<3 zgodne, >4 warianty, duplikat w bazie nie wchodzi) -> 'Do wyjasnienia.xlsx' (ta sama forma co oryginał).
Użycie: python deploy_zbior_nowych.py [--apply]. Aplikacja musi być zamknięta; kopie obu baz przed zapisem."""
import collections, difflib, hashlib, json, re, shutil, sqlite3, subprocess, sys, time
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[2]
FOLDER = Path(r"C:\Users\Lukasz\Desktop\Zbiór nowych")
XLSX = FOLDER / "Zbior_nowych_pytan_AI.xlsx"
OUT_REST = FOLDER / "Do wyjasnienia.xlsx"
DBS = {"app": Path.home() / "Documents" / "memonic_app.db", "seed": ROOT / "app" / "assets" / "db" / "memonic_app_seed.db"}
KAT = {"MASTER": "Kapitan żeglugi wielkiej", "POKŁAD": "Dział pokładowy", "ANGIELSKI": "Angielski"}
APPLY = "--apply" in sys.argv
STAMP = time.strftime("%Y-%m-%d")


def norm(s):
    return re.sub(r"[^\w]+", " ", (s or "").lower()).strip()


def h(r):
    return hashlib.sha256("|".join([r[1], r[2] or "", r[3] or "", r[4] or "", r[5] or "", r[6], "v6-best-option"]).encode("utf-8")).hexdigest()


wb = openpyxl.load_workbook(XLSX)
ws = wb.active
rows = [(i, [c.value for c in ws[i]]) for i in range(2, ws.max_row + 1) if ws.cell(i, 2).value]
db0 = sqlite3.connect(f"file:{DBS['app'].as_posix()}?mode=ro", uri=True)
dbtexts = [(r[0], norm(r[1] + " " + " ".join(x or "" for x in r[2:6]))) for r in db0.execute("SELECT id,pytanie,odp_a,odp_b,odp_c,odp_d FROM questions")]
db0.close()

certain, uncertain, rest, dups = [], [], [], []
for rown, r in rows:
    no, q, opt_txt, cat, own = r[0], r[1], r[2] or "", r[3], r[4]
    opts = [re.sub(r"^[A-F]\)\s*", "", x).strip() for x in re.split(r"\n(?=[A-F]\) )", opt_txt) if x.strip()]
    votes = [str(v).strip().upper() if v and str(v).strip().upper() in list("ABCDEF") else "" for v in r[5:10]]
    valid = [v for v in votes if v]
    counts = collections.Counter(valid)
    cnt = max(counts.values()) if counts else 0
    tied = [l for l, c in counts.items() if c == cnt]
    # remis (przy braku konsensusu): wybiera litera modelu o najwyższym priorytecie: Terra, Luna 2, Luna 1, DeepSeek 2, DeepSeek 1
    top = next((votes[i] for i in (4, 3, 2, 1, 0) if votes[i] in tied), "")
    item = dict(row=rown, no=no, q=q, opts=opts, cat=cat, top=top, cnt=cnt, notka=r[10] or "", expl=r[11] or "", src=r[12] or "", votes=votes)
    if not top or cat not in KAT or not 2 <= len(opts) <= 4 or "ABCDEF".index(top) >= len(opts):
        item["why"] = "brak głosu AI" if not top else ("więcej niż 4 warianty" if len(opts) > 4 else "inne")
        rest.append(item)
        continue
    t = norm(q + " " + " ".join(opts))
    dup = None
    # pytania z pliku MD zostały już ocenione względem bazy (embeddingi + 2 modele: DeepSeek, Luna), więc próg tekstowy dotyczy tylko reszty
    for did, dt in ([] if str(item["src"]).startswith("MD:") else dbtexts):
        if abs(len(dt) - len(t)) > 0.2 * max(len(dt), len(t)):
            continue
        sm = difflib.SequenceMatcher(None, t, dt)
        if sm.real_quick_ratio() >= 0.93 and sm.quick_ratio() >= 0.93 and sm.ratio() >= 0.93:
            dup = did
            break
    if dup:
        item["dup"] = dup
        dups.append(item)
        continue
    # zgoda >=3 AI: niepewne + wyjaśnienie; zgoda <3: niepewne, bez wyjaśnienia (tekst z Excela nie jest zapisywany)
    if cnt < 3:
        item["expl"] = ""
    (uncertain if cnt >= 3 else certain).append(item)  # 'certain' = bez konsensusu (też niepewne, bez wyjaśnienia)

# pytania odwołujące się do rysunku (nie ma go w tekście) odpadają z nowej puli
import concurrent.futures as cf, os, requests
FIG_CACHE = ROOT / "tools" / "ai_audit" / "runs" / "zbior_fig_cache.json"
fig_cache = json.load(open(FIG_CACHE, encoding="utf-8")) if FIG_CACHE.exists() else {}
OR_KEY = os.environ.get("ZBIOR_OR_KEY") or re.search(r"OPENROUTER_API_KEY\s*=\s*(\S+)", (ROOT / ".env").read_text(encoding="utf-8")).group(1)
FIG_SYS = ("Polish maritime exam question. Decide whether it REFERS TO A DRAWING/FIGURE/DIAGRAM/CHART/PICTURE/SYMBOL that is not reproduced in the text, "
           "so it cannot be answered without seeing it (e.g. 'na rysunku', 'poniższy rysunek', 'element oznaczony cyfrą 2', 'pokazane światła', 'przedstawiony schemat'). "
           'Ordinary questions that merely mention a topic are NOT figure questions. Reply JSON only: {"needs_figure": true|false}')


def needs_figure(x):
    key = hashlib.md5((x["q"] + "|".join(x["opts"])).encode()).hexdigest()
    if key in fig_cache:
        return fig_cache[key]
    body = {"model": "deepseek/deepseek-v4.1-flash", "max_tokens": 1500, "reasoning": {"effort": "low"},
            "messages": [{"role": "system", "content": FIG_SYS}, {"role": "user", "content": x["q"] + "\n" + "\n".join(f"{chr(65 + k)}) {o}" for k, o in enumerate(x["opts"]))}]}
    for a in range(4):
        try:
            r = requests.post("https://openrouter.ai/api/v1/chat/completions", headers={"Authorization": f"Bearer {OR_KEY}"}, json=body, timeout=120)
            if r.status_code == 200:
                v = bool(json.loads(re.search(r"\{.*\}", r.json()["choices"][0]["message"]["content"], re.S).group(0)).get("needs_figure"))
                fig_cache[key] = v
                return v
        except Exception:
            pass
        time.sleep(3 * (a + 1))
    return False


figs = []
with cf.ThreadPoolExecutor(8) as ex:
    allc = certain + uncertain
    flags = list(ex.map(needs_figure, allc))
json.dump(fig_cache, open(FIG_CACHE, "w", encoding="utf-8"))
figs = [x for x, f in zip(allc, flags) if f]
figset = {id(x) for x in figs}
certain = [x for x in certain if id(x) not in figset]
uncertain = [x for x in uncertain if id(x) not in figset]

print("odrzucone (odwołanie do rysunku):", len(figs))
print("zgoda >=3 (niepewne + wyjaśnienie):", len(uncertain), "| zgoda <3 (niepewne, bez wyjaśnienia):", len(certain),
      "| nie wdrożone (>4 warianty / brak głosu):", len(rest), "| duplikaty z bazą pominięte:", len(dups))
print("kategorie (dodawane):", collections.Counter(x["cat"] for x in certain + uncertain))
print("zgoda >=3 bez wyjaśnienia w Excelu:", sum(1 for x in uncertain if not x["expl"].strip()))
if "--show-figs" in sys.argv:
    for x in figs:
        print("RYSUNEK nr", x["no"], "|", x["q"][:120])
if "--show-dups" in sys.argv:
    con = sqlite3.connect(f"file:{DBS['app'].as_posix()}?mode=ro", uri=True)
    for x in dups:
        r = con.execute("SELECT pytanie,odp_a,odp_b,odp_c,odp_d,poprawna_odpowiedz FROM questions WHERE id=?", (x["dup"],)).fetchone()
        print(f"--- nr {x['no']} vs ID {x['dup']}\n  EXCEL: {x['q'][:110]} || {' | '.join(o[:40] for o in x['opts'])}\n  BAZA : {r[0][:110]} || {' | '.join((o or '')[:40] for o in r[1:5])}")
if not APPLY:
    sys.exit(0)
if "memonic_app.exe" in subprocess.run(["tasklist"], capture_output=True, text=True).stdout:
    sys.exit("Aplikacja jest uruchomiona - zamknij ją i powtórz.")

ts = time.strftime("%Y%m%d_%H%M%S")
add = [(x, True) for x in uncertain] + [(x, True) for x in certain]  # wszystkie wchodzą jako niepewne
(ROOT / "data" / "backup_seed").mkdir(parents=True, exist_ok=True)
starts = {}
for label, path in DBS.items():
    shutil.copy2(path, (ROOT / "data" / "backup_seed" if label == "seed" else path.parent) / (path.name + ".bak_zbior_nowych_" + ts))
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE IF NOT EXISTS ai_disputed (question_id INTEGER PRIMARY KEY)")
    start = db.execute("SELECT MAX(id) FROM questions").fetchone()[0] + 1
    starts[label] = start
    now = int(time.time() * 1000)
    for k, (x, unsure) in enumerate(add):
        qid = start + k
        o = x["opts"] + [None] * (4 - len(x["opts"]))
        key = x["top"]
        mark = f"ai_consensus{x['cnt']}:{STAMP}" if x["cnt"] >= 3 else f"ai_brak_konsensusu:{STAMP}"
        notes = (x["notka"] or "")[:500]
        db.execute("INSERT INTO questions (id,kategoria,tematyka,typ_pytania,pytanie,odp_a,odp_b,odp_c,odp_d,poprawna_odpowiedz,poprawna_odpowiedz_tekst,"
                   "zrodlo_pliku,review_status,review_notes,study_hidden,ai_verified) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (qid, KAT[x["cat"]], "Zbiór nowych", "testowe", x["q"], o[0], o[1], o[2], o[3], key, o["ABCD".index(key)],
                    f"Zbiór nowych (Zbior_nowych_pytan_AI.xlsx), nr {x['no']}; {x['src']}"[:400], "ok", notes, 0, mark))
        db.execute("INSERT INTO srs_cards (question_id,repetitions,interval_days,ease_factor,due_ms,lapses,state,step) VALUES (?,?,?,?,?,?,?,?)",
                   (qid, 0, 0, 2.5, now, 0, 0, 0))
        if x["expl"].strip():
            row = db.execute("SELECT id,pytanie,odp_a,odp_b,odp_c,odp_d,poprawna_odpowiedz FROM questions WHERE id=?", (qid,)).fetchone()
            db.execute("INSERT OR REPLACE INTO explanation_cache VALUES (?,?,?,?,?)", (qid, h(row), x["expl"], f"zgodność {x['cnt']} AI", now))
        if unsure:
            db.execute("INSERT OR IGNORE INTO ai_disputed(question_id) VALUES (?)", (qid,))
    db.commit()
    print(label, "ID", start, "-", start + len(add) - 1, "| razem pytań", db.execute("SELECT COUNT(*) FROM questions").fetchone()[0])
    db.close()
assert starts["app"] == starts["seed"], "różne numery startowe w bazach"

log = {"ids": {"od": starts["app"], "do": starts["app"] + len(add) - 1}, "zgoda_min3_z_wyjasnieniem": [x["no"] for x in uncertain],
       "bez_konsensusu_bez_wyjasnienia": [x["no"] for x in certain], "nie_wdrozone": [(x["no"], x["why"]) for x in rest], "odrzucone_rysunek": [x["no"] for x in figs],
       "duplikaty": [(x["no"], x["dup"]) for x in dups]}
(ROOT / "review").mkdir(exist_ok=True)
(ROOT / "review" / "Zbior_nowych_wdrozenie_log.json").write_text(json.dumps(log, ensure_ascii=False), encoding="utf-8")
print("log: review/Zbior_nowych_wdrozenie_log.json")
