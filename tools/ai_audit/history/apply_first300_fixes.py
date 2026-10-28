"""Naprawa/porzadki po przegladzie 300 pierwszych pytan (cascade v5). Zapisuje dziennik zmian first300_fix_log.json."""
import json, shutil, sqlite3, time

TARGETS = ["C:/Users/Lukasz/Documents/memonic_app.db", "../memonic_app/assets/db/memonic_app_seed.db"]
out = json.load(open("calibration/runs/audit_first300.json", encoding="utf-8"))
FIG = sorted(int(k) for k, o in out.items() if o["l2_conf"] == "figure")
TEXT = sorted(int(k) for k, o in out.items() if o["l2_conf"] == "integrity")
L3_OK = sorted(int(k) for k, o in out.items() if (o.get("L3") or {}).get("verdict") == "OK")
CLEAN = sorted(int(k) for k, o in out.items() if o["l2_conf"] is None)
MANUAL = {70: "B", 279: "A"}
assert len(FIG) == 23 and len(TEXT) == 23 and len(CLEAN) == 238, (len(FIG), len(TEXT), len(CLEAN))

SIGN_A = "wartość bezwzględna φA > φB"
R = lambda **kw: kw
FIX = {}
for i in (2, 42, 47, 54, 57, 63, 72, 92, 100, 103):
    FIX[i] = {"odp_a": ("*", SIGN_A)}
FIX[11] = {"pytanie": ("*", "Statek znajduje się na pozycji: φ=05°17,8′S λ=136°14,8′E i przemieścił się 480 Mm na północ. Jego pozycja będzie wynosiła:"),
           "odp_a": ("*", "φ=13°17,8′S λ=136°14,8′E"), "odp_b": ("*", "φ=03°17,8′S λ=136°14,8′E"), "odp_c": ("*", "φ=02°42,2′N λ=136°14,8′E")}
FIX[40] = {"odp_a": ("*", "AlOc WR 8s"), "odp_b": ("*", "AlFl WG 8s")}
for i in (140, 154, 167):
    FIX[i] = {"odp_c": ("carry our observations", "carry out observations")}
for i in (142, 156):
    FIX[i] = {"odp_a": ("umieszczone go", "umieszczonego"), "odp_c": ("słuzy", "służy")}
FIX[187] = {"pytanie": ("znajduje się przybliżeniu", "znajduje się w przybliżeniu")}
FIX[195] = {"odp_b": ("statkujesz", "statku jest")}
FIX[197] = {"pytanie": ("powoduję następujące zjawiska::", "powoduje następujące zjawiska:"),
            "odp_b": ("opychany", "odpychany"), "odp_c": ("brxegu", "brzegu")}
FIX[212] = {"odp_c": ("sytemu", "systemu")}
FIX[215] = {"pytanie": ("*", "Czy manewr powrotu na kontrkurs podczas akcji „człowiek za burtą”, nazywany pętlą Williamsona, różni się od pętli Scharnova:"),
            "odp_a": ("*", "jest zawsze wykonywany przez wyłożenie steru prawo na burtę, a po zmianie kursu o 60° - wyłożenie steru lewo na burtę"),
            "odp_b": ("*", "w odróżnieniu od pętli Scharnowa, może być wykonywany przez statki o dużej zwrotności"),
            "odp_c": ("*", "jego wykonanie nie pozostawia za rufą statku poszukującego odcinka nieprzeszukanego")}
FIX[217] = {"pytanie": ("metodą, on load release hooks\"", "metodą „on load release hooks”")}
assert set(FIX) == set(TEXT), set(TEXT) ^ set(FIX)

ts = time.strftime("%Y%m%d_%H%M%S"); log = {"text": {}, "deleted": [], "figure_ids": FIG}
for t in TARGETS:
    shutil.copy(t, t + f".bak_first300_{ts}")
    c = sqlite3.connect(t); c.row_factory = sqlite3.Row
    for i, fields in FIX.items():
        r = c.execute("select * from questions where id=?", (i,)).fetchone()
        new, old = {}, {}
        for col, (src, dst) in fields.items():
            cur = r[col] or ""
            if src == "*": val = dst
            else:
                assert src in cur, (t, i, col, src, cur[:80])
                val = cur.replace(src, dst)
            if val != cur: old[col] = cur; new[col] = val
        key = r["poprawna_odpowiedz"].lower()
        if "odp_" + key in new: new["poprawna_odpowiedz_tekst"] = new["odp_" + key]
        sets = ", ".join(f"{k}=?" for k in new)
        c.execute(f"update questions set {sets}, ai_verified=? where id=?", [*new.values(), "ai_cascade_v5:tekst_poprawiony:2026-10-05", i])
        log["text"].setdefault(str(i), old)
    ok_tag = "ai_cascade_v5:ok:2026-10-05"
    c.executemany("update questions set ai_verified=? where id=?", [(ok_tag, i) for i in CLEAN + L3_OK])
    for i, letter in MANUAL.items():
        row = c.execute(f"select odp_{letter.lower()} from questions where id=?", (i,)).fetchone()
        c.execute("update questions set poprawna_odpowiedz=?, poprawna_odpowiedz_tekst=?, ai_verified=?, review_status='ok' where id=?",
                  (letter, row[0], f"manual:klucz_{letter}:2026-10-05", i))
    q = ",".join("?" * len(FIG))
    deleted = c.execute(f"select id,pytanie from questions where id in ({q})", FIG).fetchall()
    c.execute(f"delete from srs_cards where question_id in ({q})", FIG)
    c.execute(f"delete from explanation_cache where question_id in ({q})", FIG)
    c.execute(f"delete from questions where id in ({q})", FIG)
    c.commit()
    print(t[-24:], "tekst poprawiony:", len(FIX), "| ok-cascade:", len(CLEAN + L3_OK), "| usuniete (rysunek):", len(deleted),
          "| razem pytan:", c.execute("select count(*) from questions").fetchone()[0], "| srs:", c.execute("select count(*) from srs_cards").fetchone()[0])
    if t == TARGETS[0]: log["deleted"] = [{"id": d["id"], "pytanie": d["pytanie"][:80]} for d in deleted]
json.dump(log, open("first300_fix_log.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
