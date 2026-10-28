"""Poprawki po przegladzie ID 901-2948 (cascade v5). DRY=1 -> tylko podglad. Dziennik: batch3_fix_log.json"""
import json
import os
import re
import shutil
import sqlite3
import time

TARGETS = ["C:/Users/Lukasz/Documents/memonic_app.db", "../memonic_app/assets/db/memonic_app_seed.db"]
out = json.load(open("calibration/runs/audit_batch3.json", encoding="utf-8"))
conf = {int(k): o["l2_conf"] for k, o in out.items()}
l3 = {int(k): (o.get("L3") or {}).get("verdict") for k, o in out.items()}
err = sorted(int(k) for k, o in out.items()
             if "error" in o["L1"] or "error" in (o.get("L2") or {}) or "error" in (o.get("L3") or {}))
FIG = sorted(k for k, v in conf.items() if v == "figure") + [1348]
KEYS = sorted(k for k, v in l3.items() if v == "KEY_SUSPECT")
INTEG = sorted(k for k, v in conf.items() if v == "integrity")
DELETE_UNFIXABLE = [2363]
PUA = {"\uf06a": "φ", "\uf06c": "λ", "\uf0b0": "°", "\uf061": "α", "\uf020": " ", "\uf02d": "-"}
GREEK_LATIN = {"Ν": "N", "Ε": "E", "ς": "S", "΄": "′"}


def pua(t):
    for a, b in PUA.items():
        t = t.replace(a, b)
    return t


def coords(t):
    for a, b in GREEK_LATIN.items():
        t = t.replace(a, b)
    return t


def sub(col, src, dst):
    def f(r, cur):
        assert src in cur, (r["id"], col, src, cur[:90])
        return cur.replace(src, dst)
    return (col, f)


def fn(col, g):
    return (col, lambda r, cur: g(cur))


def setv(col, v):
    return (col, lambda r, cur: v)


def no_cn(t):
    return t.replace(" cn cn", "")


F = {}
for i in (976, 1580):
    F[i] = [sub("pytanie", "prze Izbę", "przez Izbę")]
F[999] = [sub("odp_a", "starta", "strata")]
for i in (1060, 1110, 1128, 1141, 1157, 1184, 1198, 1208):
    F[i] = [sub("odp_a", "absolute valueΦΑ>ΦΒ", "absolute value φA > φB"), sub("odp_c", "nortern", "northern")]
for i in (1064, 1145, 1161, 1188, 1202):
    F[i] = [fn("pytanie", lambda t: coords(t.replace("point q =", "point φ ="))),
            fn("odp_a", lambda t: coords(t.replace("X =", "λ ="))),
            fn("odp_b", lambda t: coords(t.replace("X =", "λ ="))),
            fn("odp_c", coords)]
for i in (1069, 1121, 1138, 1152, 1166, 1194, 1206):
    F[i] = [fn("pytanie", lambda t: coords(t.replace("located at: q=", "located at: φ="))),
            fn("odp_a", coords), fn("odp_b", coords), fn("odp_c", coords)]


def shipfix(t):
    t = pua(t).replace("position 4 =", "position φ =").replace("located at =", "located at φ =")
    return t.replace("Ship A was located at position", "Ship B was located at position")


for i in (1071, 1122, 1139, 1167, 1153, 1195):
    F[i] = [fn("pytanie", shipfix)]
for i in (1144, 1160, 1187, 1201):
    F[i] = [sub("odp_a", "of cos increases", "of cos φ increases"), sub("odp_b", "sec o", "sec φ"),
            sub("odp_c", "cos o", "cos φ")]
for i in (1245, 1258, 1270):
    F[i] = [sub("odp_c", "carry our observations", "carry out observations")]
F[1271] = [sub("odp_a", "umieszczone go", "umieszczonego"), sub("odp_c", "słuzy", "służy")]
F[1315] = [sub("pytanie", "metodą „, on", "metodą „on")]
FULL_B = ("a power-driven vessel which due to its draft in relation to the available depth and width of a navigable "
          "water is severely restricted in its ability to deviate from the course she is following")
for i in (1375, 1405, 1418, 1436):
    F[i] = [fn("pytanie", lambda t: t.replace("contrained", "constrained")), setv("odp_b", FULL_B)]
F[1384] = [fn("odp_c", lambda t: t.replace("contrained", "constrained"))]
for i in (1385, 1422):
    F[i] = [fn("pytanie", lambda t: t.replace("contrained", "constrained"))]
F[1394] = [fn("pytanie", lambda t: t.split("\na)")[0].rstrip())]
F[1348] = []  # usuwany (rysunek flagi)
F[2174] = [fn("pytanie", lambda t: t.replace("KR = N W , to", "KR = NbW, to").rstrip(" b").rstrip()),
           setv("odp_a", "WbS"), setv("odp_b", "SWbW"), setv("odp_c", "EbN")]


def fixpoints(t):
    t = t.replace(" A A B", "").replace(" A A ", " ").rstrip()
    t = re.sub(r":\s*B$", ":", t)
    head, _, tail = t.partition("a punktu przeznaczenia:")
    head = head.replace("A – φ =", "A – φA =").replace("λ =", "λA =")
    tail = tail.replace("B – φ =", "B – φB =").replace("λ =", "λB =")
    return head + "a punktu przeznaczenia:" + tail


for i in (2216, 2221, 2222):
    F[i] = [fn("pytanie", fixpoints)]
for i in (2172, 2173):
    F[i] = [fn("pytanie", lambda t: re.sub(r"V = (\d+) d d", r"Vd = \1", pua(t)))]
F[2176] = [fn("pytanie", lambda t: t.replace(" a a ", " ").replace(" b b ", " "))]
F[2177] = [fn("pytanie", lambda t: pua(t).replace(" d o godz", " do godz")), fn("odp_a", pua), fn("odp_c", pua)]
F[2191] = [sub("pytanie", "odwzorowaniu Merk", "odwzorowaniu Merkatora")]
F[2212] = [setv("pytanie", "Jeżeli żegluga loksodromiczna przecina południk pod kątem różnym od 000° lub 090°, "
                           "wówczas loksodroma na kuli przyjmuje kształt:")]
F[2219] = [sub("pytanie", "jest to punkty w którym", "jest to punkt, w którym")]
F[2228] = [fn("odp_c", pua)]
for i in (2245, 2246):
    F[i] = [fn("pytanie", pua)]
F[2297] = [fn("odp_a", no_cn), fn("odp_b", no_cn), fn("odp_c", no_cn)]
F[2301] = [fn("odp_a", no_cn), fn("odp_b", no_cn), fn("odp_c", no_cn)]
F[2303] = [sub("odp_a", "minimum 90", "minimum 90°"), sub("odp_b", "minimum 30", "minimum 30°")]
F[2351] = [sub("odp_a", "26600 m", "26600 km")]
F[2365] = [sub("pytanie", "mieędzynarodową", "międzynarodową"), sub("odp_a", "niezleznie", "niezależnie"),
           sub("odp_a", "wiekości", "wielkości")]
F[2367] = [sub("pytanie", "nadainikiem", "nadajnikiem")]
F[2369] = [sub("pytanie", "nadainika", "nadajnika")]
F[2396] = [sub("odp_a", "moż e", "może")]
F[2411] = [sub("odp_b", "zagrożenie rzadziej niż co trzy", "zagrożeń nie rzadziej niż co trzy"),
           sub("odp_c", "zagrożenie rzadziej", "zagrożeń rzadziej")]
F[2429] = [sub("odp_b", "anit-exposure", "anti-exposure")]
F[2550] = [sub("odp_c", "każdy za statków", "każdy ze statków")]
F[2592] = [fn("pytanie", lambda t: re.sub(r"\s+1 1 2 2$", "", t))]
F[2636] = [sub("odp_a", "zastaw klauzul", "zestaw klauzul")]
F[2638] = [sub("pytanie", "deadfreightto", "deadfreight to")]
F[2692] = [sub("pytanie", "Fliners", "Flinders")]
F[2702] = [setv("pytanie", "Błędy, które powstały podczas obliczeń nawigacyjnych, na skutek pomylenia cyfry lub znaku "
                           "zaliczamy do:"),
           setv("odp_a", "błędów systematycznych"), setv("odp_b", "błędów przypadkowych"),
           setv("odp_c", "błędów grubych"), setv("poprawna_odpowiedz_tekst", "błędów grubych")]
F[2746] = [fn("pytanie", lambda t: t.replace("zastaw map", "zestaw map"))]
F[2784] = [sub("pytanie", "który nie powodującym uruchomienia", "który nie powoduje uruchomienia")]
F[2846] = [sub("odp_b", "dba- łość", "dbałość")]
F[2864] = [sub("odp_a", "sytemu", "systemu")]
LEAVE = [925, 943, 1076, 1080, 1231, 1302, 1392, 1498, 2127, 2145, 2152, 2155, 2220, 2428, 2629]
covered = set(F) | set(LEAVE) | set(DELETE_UNFIXABLE)
assert covered >= set(INTEG) and not (set(F) - set(INTEG) - {1348}), sorted(covered ^ set(INTEG))
assert len(FIG) == 63 and len(KEYS) == 25, (len(FIG), len(KEYS))

DRY = bool(os.environ.get("DRY"))
if DRY:
    c = sqlite3.connect(TARGETS[0])
    c.row_factory = sqlite3.Row
    shown = set()
    for i, ops in F.items():
        if not ops:
            continue
        r = c.execute("select * from questions where id=?", (i,)).fetchone()
        key = (r["pytanie"][:30], tuple(sorted(o[0] for o in ops)))
        if key in shown:
            continue
        shown.add(key)
        acc = {}
        for col, f in ops:
            acc[col] = f(r, acc.get(col, r[col] or ""))
        for col, new in acc.items():
            old = r[col] or ""
            if new != old and i in (1071, 1153, 2216, 2176, 2365, 2172, 1405):
                print(f"#{i} {col}:\n   OLD {old!r}\n   NEW {new!r}")
    print("\nusunąć rysunek:", len(FIG), "| klucze:", len(KEYS), "| nienaprawialne:", DELETE_UNFIXABLE,
          "| bez przeglądu AI (błąd API):", err)
    raise SystemExit

ts = time.strftime("%Y%m%d_%H%M%S")
log = {"text": {}, "deleted_rows": [], "figure_ids": FIG, "key_ids": KEYS, "unfixable": DELETE_UNFIXABLE,
       "api_error_ids": err}
ok_ids = sorted(((set(k for k, v in conf.items() if v is None) - set(err))
                 | set(k for k, v in l3.items() if v == "OK") | set(LEAVE)) - {1076})
for t in TARGETS:
    shutil.copy(t, t + f".bak_batch3_{ts}")
    c = sqlite3.connect(t)
    c.row_factory = sqlite3.Row
    for i, ops in F.items():
        if i in FIG or not ops:
            continue
        r = c.execute("select * from questions where id=?", (i,)).fetchone()
        new, old = {}, {}
        for col, f in ops:
            cur = new.get(col, r[col] or "")
            val = f(r, cur)
            if val != cur:
                old.setdefault(col, r[col] or "")
                new[col] = val
        key = r["poprawna_odpowiedz"].lower()
        if "odp_" + key in new and "poprawna_odpowiedz_tekst" not in new:
            new["poprawna_odpowiedz_tekst"] = new["odp_" + key]
        if new:
            c.execute(f"update questions set {', '.join(k + '=?' for k in new)}, ai_verified=? where id=?",
                      [*new.values(), "ai_cascade_v5:tekst_poprawiony:2026-10-05", i])
        log["text"].setdefault(str(i), old)
    c.executemany("update questions set ai_verified=? where id=?", [("ai_cascade_v5:ok:2026-10-05", i) for i in ok_ids])
    c.execute("update questions set ai_verified=? where id=1076", ("manual:klucz_B:2026-10-05",))
    dele = sorted(set(FIG + KEYS + DELETE_UNFIXABLE))
    q = ",".join("?" * len(dele))
    rows = [dict(r) for r in c.execute(f"select * from questions where id in ({q})", dele)]
    if t == TARGETS[0]:
        log["deleted_rows"] = rows
    c.execute(f"delete from srs_cards where question_id in ({q})", dele)
    c.execute(f"delete from explanation_cache where question_id in ({q})", dele)
    c.execute(f"delete from questions where id in ({q})", dele)
    c.commit()
    print(t[-24:], "tekst:", len([i for i in F if F[i] and i not in FIG]), "| ok:", len(ok_ids), "| usuniete:", len(rows),
          "(rysunek", len(FIG), "+ klucz", len(KEYS), "+ nienaprawialne", len(DELETE_UNFIXABLE), ") | razem pytan:",
          c.execute("select count(*) from questions").fetchone()[0], "| sieroty srs:",
          c.execute("select count(*) from srs_cards where question_id not in (select id from questions)").fetchone()[0])
json.dump(log, open("batch3_fix_log.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
