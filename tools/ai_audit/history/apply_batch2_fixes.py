"""Poprawki po przegladzie ID 301-900 (cascade v5): tekst, usuniecie rysunkow i watpliwych kluczy. Dziennik: batch2_fix_log.json"""
import json, shutil, sqlite3, time

TARGETS = ["C:/Users/Lukasz/Documents/memonic_app.db", "../memonic_app/assets/db/memonic_app_seed.db"]
out = json.load(open("calibration/runs/audit_batch2.json", encoding="utf-8"))
conf = {int(k): o["l2_conf"] for k, o in out.items()}
l3 = {int(k): (o.get("L3") or {}).get("verdict") for k, o in out.items()}
FIG = sorted(k for k, v in conf.items() if v == "figure")
KEYS = sorted(k for k, v in l3.items() if v == "KEY_SUSPECT")
AMBIG = sorted(k for k, v in l3.items() if v == "DEFECT")          # 447, 462 - zostaja, z adnotacja
INTEG = sorted(k for k, v in conf.items() if v == "integrity")
PLACEHOLDER = [306, 309, 313, 314, 717, 719, 724, 747, 614, 624]  # oryginalny tekst arkusza
assert len(FIG) == 18 and len(KEYS) == 13 and AMBIG == [447, 462], (len(FIG), len(KEYS), AMBIG)

SIGN_A = "wartość bezwzględna φA > φB"
F = {}
F[320] = {"pytanie": ("*", "-------- cargo from no.4 tank to no.6 tank and report.")}
for i in (350, 762): F[i] = {"pytanie": ("this are (", "this area (")}
F[398] = {"odp_a": ("ioznakowań", "i oznakowań")}
F[417] = {"odp_c": ("zawarte w, informacji na podróż\"", "zawarte w „informacji na podróż”")}
F[483] = {"pytanie": ("*", "Rozprawa prowadzona przez Izbę Morską kończy się:")}
F[609] = {"pytanie": ("mijania w kanale się ze statkiem", "mijania się w kanale ze statkiem")}
F[615] = {"pytanie": ("zazwy- czaj", "zazwyczaj"),
          "odp_b": ("fal i jest związana z układem fal", None) if False else ("układem fal", "układem fal okrętowych płynącego statku"),
          "odp_c": ("strumieni zaśru-", "strumieni zaśrubowych jednostek")}
F[622] = {"odp_a": ("zbliżonej do", "zbliżonej do prędkości statku i równolegle przebiegającego z przewracaniem statku")}
F[653] = {"odp_a": ("przygotowujące go mostek", "przygotowującego mostek")}
F[768] = {"pytanie": ("inbulk-", "in bulk -")}
F[772] = {"odp_b": ("poniżej-161,5", "poniżej -161,5"), "odp_c": ("0°°C", "0°C")}
F[809] = {"odp_a": ("fuldy", "fully"), "odp_c": ("fuldy", "fully"), "odp_b": ("semi-pressurised", "semi-pressurised")}
F[826] = {"pytanie": ("chips weat-", "ship's sweat -")}
for i in (520, 533): F[i] = {"odp_a": ("ΦΑ>ФВ", "φA > φB")}
for i in (578, 594): F[i] = {"odp_c": ("carry our observations", "carry out observations")}
for i in (583, 598): F[i] = {"odp_a": ("umieszczone go", "umieszczonego"), "odp_c": ("słuzy", "służy")}
F[634] = {"odp_b": ("zdjąć oraz i zabezpieczyć", "zdjąć i zabezpieczyć")}
assert set(F) | set(PLACEHOLDER) == set(INTEG), set(INTEG) ^ (set(F) | set(PLACEHOLDER))

ts = time.strftime("%Y%m%d_%H%M%S"); log = {"text": {}, "deleted_rows": [], "figure_ids": FIG, "key_ids": KEYS}
ok_ids = sorted(k for k, v in conf.items() if v is None) + sorted(k for k, v in l3.items() if v == "OK")
ok_ids = sorted(set(ok_ids) | set(PLACEHOLDER))
for t in TARGETS:
    shutil.copy(t, t + f".bak_batch2_{ts}")
    c = sqlite3.connect(t); c.row_factory = sqlite3.Row
    for i, fields in F.items():
        r = c.execute("select * from questions where id=?", (i,)).fetchone()
        new, old = {}, {}
        for col, (src, dst) in fields.items():
            cur = r[col] or ""
            if src == "*": val = dst
            else:
                assert src in cur, (t, i, col, src, cur[:90])
                val = cur.replace(src, dst, 1)
            if val != cur: old[col] = cur; new[col] = val
        if "odp_" + r["poprawna_odpowiedz"].lower() in new:
            new["poprawna_odpowiedz_tekst"] = new["odp_" + r["poprawna_odpowiedz"].lower()]
        if new:
            sets = ", ".join(f"{k}=?" for k in new)
            c.execute(f"update questions set {sets} where id=?", [*new.values(), i])
        c.execute("update questions set ai_verified=? where id=?", ("ai_cascade_v5:tekst_poprawiony:2026-10-05", i))
        log["text"].setdefault(str(i), old)
    c.executemany("update questions set ai_verified=? where id=?", [("ai_cascade_v5:ok:2026-10-05", i) for i in ok_ids])
    c.executemany("update questions set ai_verified=? where id=?", [("ai_cascade_v5:wiele_poprawnych_odp:2026-10-05", i) for i in AMBIG])
    dele = FIG + KEYS; q = ",".join("?" * len(dele))
    rows = [dict(r) for r in c.execute(f"select * from questions where id in ({q})", dele)]
    if t == TARGETS[0]: log["deleted_rows"] = rows
    c.execute(f"delete from srs_cards where question_id in ({q})", dele)
    c.execute(f"delete from explanation_cache where question_id in ({q})", dele)
    c.execute(f"delete from questions where id in ({q})", dele)
    c.commit()
    print(t[-24:], "tekst:", len(F), "| ok:", len(ok_ids), "| zostawione z adnotacja:", len(AMBIG), "| usuniete:", len(rows),
          "(rysunek", len(FIG), "+ klucz", len(KEYS), ") | razem pytan:", c.execute("select count(*) from questions").fetchone()[0],
          "| srs:", c.execute("select count(*) from srs_cards").fetchone()[0],
          "| sieroty:", c.execute("select count(*) from srs_cards where question_id not in (select id from questions)").fetchone()[0])
json.dump(log, open("batch2_fix_log.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
