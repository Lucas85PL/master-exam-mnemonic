"""Workflow kaskadowy L1 (Luna, z kluczem) -> L2 (DeepSeek, na slepo) -> L3 (Sonnet, final).
Uzycie: python wf.py --set calibration_set.json --tag v1 --pv v1 [--l3]
Cache wywolan: runs/cache_<tag>.jsonl (nie placimy dwa razy za to samo)."""
import argparse, base64, hashlib, json, re, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def _load_key():
    import os
    if os.environ.get("OPENROUTER_API_KEY"):
        return os.environ["OPENROUTER_API_KEY"]
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("OPENROUTER_API_KEY="):
                return line.split("=", 1)[1].strip()
    raise SystemExit("Brak OPENROUTER_API_KEY (zmienna środowiskowa albo plik .env w katalogu głównym projektu)")


KEY = _load_key()
M1, M2, M3 = "openai/gpt-6-luna", "deepseek/deepseek-v4.1-flash", "anthropic/claude-sonnet-5.5"
DEFECTS = ("truncated_start, truncated_end, blank_option, missing_option, duplicate_options, garbled, "
           "needs_figure, stem_options_mismatch, other")


def render(item, with_key):
    opts = item["opts"]
    letters = {k for k, v in opts.items() if (v or "").strip()}
    if with_key or not (opts.get(item["key"]) or "").strip():
        letters |= {item["key"]}
    last = max(letters) if letters else "A"
    lines = []
    for k in "ABCD":
        if k > last:
            break
        v = (opts.get(k) or "").strip()
        lines.append(f"{k}: {v if v else '(PUSTE)'}")
    body = f"Pytanie:\n{item['pytanie']}\n\nWarianty:\n" + "\n".join(lines)
    if with_key:
        body += f"\n\nOdpowiedź z arkusza: {item['key']}"
    return body


IMG_NOTE = ("\n\nUWAGA: do pytania dołączono RYSUNEK będący częścią treści (załączony obraz). Oceniaj pytanie razem z rysunkiem; "
            "brak rysunku w tekście NIE jest usterką (needs_figure nie zgłaszaj).")


def image_bytes(item):
    p = item.get("image")
    return Path(p).read_bytes() if p else None


def user_content(item, text):
    """Tekst albo [tekst + obraz] (OpenRouter: image_url z data URI), gdy pytanie ma rysunek."""
    img = image_bytes(item)
    if not img:
        return text
    uri = "data:image/png;base64," + base64.b64encode(img).decode()
    return [{"type": "text", "text": text}, {"type": "image_url", "image_url": {"url": uri}}]


P = {
    "v1": {
        "L1": ("Jesteś audytorem bazy pytań egzaminacyjnych (egzamin morski, także pytania z języka angielskiego). "
               "Tekst pytań był wyciągany z PDF i mógł zostać uszkodzony. Odpowiedź z arkusza urzędu ma PRIORYTET - "
               "zakładaj, że jest poprawna, chyba że wyraźnie przeczy treści. Oceń dwie rzeczy. "
               "(1) INTEGRALNOŚĆ: czy treść pytania i wariantów jest kompletna i nieuszkodzona. "
               f"Typy usterek: {DEFECTS}. Brak wariantu D jest normalny. Krótkie lub skrótowe pytania są normalne. "
               "Pytanie z luką ---- / ..... jest normalne. "
               "(2) KLUCZ: czy odpowiedź z arkusza jest wiarygodna dla tego pytania. "
               'Zwróć WYŁĄCZNIE JSON: {"integrity":"ok|suspect","defects":[],"key":"plausible|implausible|unsure",'
               '"key_conf":0-100,"better":"A|B|C|D|-","note":"1 zdanie"}'),
        "L2": ("Jesteś egzaminatorem morskim i audytorem bazy pytań. Tekst pytań mógł zostać uszkodzony przy wyciąganiu z PDF. "
               "NIE znasz oficjalnej odpowiedzi. Wybierz najtrafniejszy wariant i oceń integralność tekstu. "
               f"Typy usterek: {DEFECTS}. Brak wariantu D, krótkie pytania i luki ---- są normalne. "
               'Zwróć WYŁĄCZNIE JSON: {"answer":"A|B|C|D|NONE","confidence":0-100,"integrity":"ok|suspect",'
               '"defects":[],"note":"1 zdanie"}'),
        "L3": ("Jesteś ekspertem prawa i praktyki morskiej, finalnym arbitrem audytu bazy pytań egzaminacyjnych. "
               "Tekst pochodzi z PDF Urzędu Morskiego i mógł zostać uszkodzony. Odpowiedź z arkusza ma priorytet - "
               "uznaj ją za błędną tylko, gdy jest wyraźnie sprzeczna z przepisami. "
               "Dwa tańsze modele zgłosiły zastrzeżenia (poniżej). Oceń samodzielnie. "
               'Zwróć WYŁĄCZNIE JSON: {"verdict":"OK|DEFECT|KEY_SUSPECT","defects":[],"best_answer":"A|B|C|D|-",'
               '"reason":"max 2 zdania"}'),
    },
}
P["v2"] = dict(P["v1"])
P["v2"]["L2"] = ("Jesteś egzaminatorem morskim i audytorem bazy pytań. Tekst pytań mógł zostać uszkodzony przy wyciąganiu z PDF. "
                 "NIE znasz oficjalnej odpowiedzi. Wykonaj dwa zadania. "
                 "(A) INTEGRALNOŚĆ - sprawdź po kolei: 1) czy pytanie zaczyna się od początku zdania (nie od środka, np. od małej litery lub od "
                 "spójnika), 2) czy kończy się kompletnie, 3) czy każdy wariant jest niepusty i różni się od pozostałych, 4) czy warianty "
                 "gramatycznie i sensownie pasują do pytania (a nie do innego tematu), 5) czy tekst nie zawiera uszkodzonych słów lub znaków. "
                 "Jeśli którykolwiek punkt zawodzi -> integrity=suspect. "
                 f"Typy usterek: {DEFECTS}. Brak wariantu D i luki ---- w zdaniach są normalne. "
                 "(B) ODPOWIEDŹ - wybierz najtrafniejszy wariant (NONE, gdy żaden nie pasuje do pytania). "
                 'Zwróć WYŁĄCZNIE JSON: {"starts_mid_sentence":true|false,"answer":"A|B|C|D|NONE","confidence":0-100,'
                 '"integrity":"ok|suspect","defects":[],"note":"1 zdanie"}')
P["v3"] = dict(P["v2"])
P["v4"] = dict(P["v2"])
P["v5"] = dict(P["v2"])
CFG = {"v1": {"l1_keyconf_min": 80, "l2_conf_min": 85}, "v2": {"l1_keyconf_min": 90, "l2_conf_min": 85},
       "v3": {"l1_keyconf_min": 90, "l2_conf_min": 90},
       "v4": {"l1_keyconf_min": 90, "l2_conf_min": 90, "l2_all": True},
       "v5": {"l1_keyconf_min": 90, "l2_conf_min": 90, "l2_all": True}}

_lock = threading.Lock()


def call(model, system, user, tag, ckey, effort="low", max_tokens=3000, item=None):
    cache = HERE / "runs" / f"cache_{tag}.jsonl"
    with _lock:
        if cache.exists():
            for line in cache.read_text(encoding="utf-8").splitlines():
                r = json.loads(line)
                if r["ck"] == ckey:
                    return r["res"], 0.0
    if item and item.get("image"):
        max_tokens = max(max_tokens, 10000)  # z obrazem model dluzej "mysli" - 3000 konczylo sie bez odpowiedzi
    body = {"model": model, "max_tokens": max_tokens, "reasoning": {"effort": effort}, "usage": {"include": True},
            "messages": [{"role": "system", "content": system + (IMG_NOTE if item and item.get("image") else "")},
                           {"role": "user", "content": user_content(item, user) if item else user}]}
    err = None
    for i in range(3):
        try:
            r = requests.post("https://openrouter.ai/api/v1/chat/completions",
                              headers={"Authorization": f"Bearer {KEY}"}, json=body, timeout=240)
            if r.status_code != 200:
                err = f"HTTP {r.status_code}"
                time.sleep(3 * (i + 1))
                continue
            d = r.json()
            t = d["choices"][0]["message"]["content"] or ""
            res = json.loads(re.search(r"\{.*\}", t, re.S).group(0))
            cost = (d.get("usage") or {}).get("cost") or 0
            with _lock:
                with cache.open("a", encoding="utf-8") as f:
                    f.write(json.dumps({"ck": ckey, "res": res, "cost": cost}, ensure_ascii=False) + "\n")
            return res, cost
        except Exception as e:  # noqa: BLE001
            err = repr(e)
            time.sleep(3 * (i + 1))
    return {"error": err}, 0.0


def ck(layer, item, pv, extra=""):
    img = image_bytes(item)
    ih = hashlib.md5(img).hexdigest() if img else ""
    return hashlib.md5(f"{layer}|{pv}|{item['cid']}|{render(item, layer != 'L2')}|{extra}|{ih}".encode()).hexdigest()


def run(items, pv, tag, do_l3, workers=5):
    cfg, pr = CFG[pv], P[pv]
    out = {i["cid"]: {"item": i, "cost": 0.0} for i in items}

    def l1(i):
        r, c = call(M1, pr["L1"], render(i, True), tag, ck("L1", i, pv), item=i)
        out[i["cid"]]["L1"] = r
        out[i["cid"]]["cost"] += c

    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(l1, items))

    def esc1(o):
        r = o["L1"]
        return ("error" in r) or r.get("integrity") != "ok" or r.get("key") != "plausible" \
            or (r.get("key_conf") or 0) < cfg["l1_keyconf_min"]

    esc = [o["item"] for o in out.values() if cfg.get("l2_all") or esc1(o)]

    def l2(i):
        r, c = call(M2, pr["L2"], render(i, False), tag, ck("L2", i, pv), item=i)
        out[i["cid"]]["L2"] = r
        out[i["cid"]]["cost"] += c

    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(l2, esc))

    def confirmed(o):
        a, b = o["L1"], o.get("L2")
        if not b or "error" in b:
            # brak odpowiedzi L2 (blad API) - nie gubimy pytania z zastrzezeniem L1
            return "weak" if pv == "v5" and (a.get("integrity") == "suspect" or a.get("key") != "plausible") else None
        if not o["item"].get("image") and ("needs_figure" in (a.get("defects") or []) or "needs_figure" in (b.get("defects") or [])):
            return "figure"
        if pv in ("v3", "v4", "v5"):
            serious = {"truncated_start", "truncated_end", "blank_option", "missing_option", "duplicate_options",
                       "stem_options_mismatch"}
            l1_susp = a.get("integrity") == "suspect"
            b_susp = b.get("integrity") == "suspect" or b.get("starts_mid_sentence") is True
            if l1_susp and b_susp:
                return "integrity"                       # dwa modele zgodnie: tekst uszkodzony -> Excel bez L3
            if pv in ("v4", "v5") and l1_susp and (set(a.get("defects") or []) & serious):
                return "weak"                            # L1 widzi powazna usterke, L2 nie potwierdza -> L3
            if pv in ("v4", "v5") and b.get("answer") != o["item"]["key"] and (b.get("confidence") or 0) >= cfg["l2_conf_min"]                     and b.get("answer") in "ABCD":
                return "key"                             # slepa odpowiedz L2 != klucz z wysoka pewnoscia -> L3
            if pv == "v5" and b.get("answer") != o["item"]["key"] and b.get("answer") in "ABCD"                     and (b.get("confidence") or 0) >= 80 and a.get("key") == "implausible"                     and (a.get("key_conf") or 0) >= 85 and a.get("better") in (b.get("answer"), "-"):
                return "key"                             # L1 i L2 niezaleznie wskazuja inny wariant -> L3
            key_cand = (a.get("key") == "implausible" and b.get("answer") != o["item"]["key"]
                        and (b.get("confidence") or 0) >= cfg["l2_conf_min"]
                        and a.get("better") in (b.get("answer"), "-"))
            if key_cand:
                return "key"                             # -> L3
            weak = (b_susp and (set(b.get("defects") or []) & serious)) or (l1_susp and not b_susp and False)
            if weak:
                return "weak"                            # -> L3
            return None
        if pv != "v1":
            doubt = a.get("integrity") == "suspect" or a.get("key") != "plausible" or (a.get("key_conf") or 0) < 90
            b_susp = b.get("integrity") == "suspect" or b.get("starts_mid_sentence") is True
            if b_susp and doubt:
                return "integrity"
            if b.get("answer") != o["item"]["key"] and (b.get("confidence") or 0) >= cfg["l2_conf_min"] and doubt:
                return "key"
            return None
        integ = (a.get("integrity") == "suspect") and (b.get("integrity") == "suspect")
        key = (b.get("answer") != o["item"]["key"]) and ((b.get("confidence") or 0) >= cfg["l2_conf_min"]) \
            and (a.get("key") != "plausible")
        return "integrity" if integ else ("key" if key else None)

    for o in out.values():
        o["l1_esc"] = esc1(o)
        o["l2_conf"] = confirmed(o) if "L2" in o else None
    l3items = [o["item"] for o in out.values() if o["l2_conf"] in ((("key", "weak")) if pv in ("v3", "v4", "v5") else ("integrity", "key"))]
    if do_l3:
        def l3(i):
            o = out[i["cid"]]
            extra = (f"\n\nZastrzeżenia L1: {json.dumps(o['L1'], ensure_ascii=False)}"
                     f"\nZastrzeżenia L2: {json.dumps(o['L2'], ensure_ascii=False)}")
            r, c = call(M3, pr["L3"], render(i, True) + extra, tag, ck("L3", i, pv, extra), effort="medium", max_tokens=6000, item=i)
            o["L3"] = r
            o["cost"] += c

        with ThreadPoolExecutor(3) as ex:
            list(ex.map(l3, l3items))
    return out


def is_final(o, do_l3):
    c = o["l2_conf"]
    if c == "integrity":
        return True
    if do_l3:
        return o.get("L3", {}).get("verdict") in ("DEFECT", "KEY_SUSPECT")
    return c in ("key", "weak")


def metrics(out, do_l3):
    dirty = [o for o in out.values() if o["item"]["label"]["defect"]]
    clean = [o for o in out.values() if not o["item"]["label"]["defect"]]
    groups = {"integrity": [o for o in dirty if o["item"]["label"]["klasa"] == "integrity"],
              "key": [o for o in dirty if o["item"]["label"]["klasa"] == "key"], "clean": clean}
    m = {k: (sum(1 for o in v if o["l1_esc"]), sum(1 for o in v if o["l2_conf"] in ("integrity", "key", "weak")),
             sum(1 for o in v if is_final(o, do_l3)), len(v)) for k, v in groups.items()}
    m["cost"] = sum(o["cost"] for o in out.values())
    m["n"] = len(out)
    return m


def report(out, do_l3):
    m = metrics(out, do_l3)
    print(f"{'grupa':10} {'L1 esk':>7} {'L2 potw':>8} {'FINAL':>6} {'z':>4}")
    for k in ("integrity", "key", "clean"):
        print(f"{k:10} {m[k][0]:7} {m[k][1]:8} {m[k][2]:6} {m[k][3]:4}")
    print(f"koszt przebiegu: ${m['cost']:.4f} (cache nie liczy) | wejscie do L3: "
          f"{sum(1 for o in out.values() if o['l2_conf'] in ('key', 'weak'))}/{m['n']} (bezposrednio do Excela: {sum(1 for o in out.values() if o['l2_conf'] == 'integrity')}) | figure: {sum(1 for o in out.values() if o['l2_conf'] == 'figure')}")
    for o in out.values():
        d = o["item"]["label"]["defect"]
        flag = is_final(o, do_l3)
        if (d and not flag) or (not d and (o["l1_esc"] or flag)):
            a, b = o["L1"], o.get("L2", {})
            print(f"  {'PRZEOCZONA' if d else 'FALSZ/ESK '} {o['item']['cid']} [{d}] "
                  f"L1:{a.get('integrity')}/{a.get('defects')}/{a.get('key')}({a.get('key_conf')}) "
                  f"L2:{b.get('integrity')}/{b.get('answer')}({b.get('confidence')}) L3:{o.get('L3', {}).get('verdict')} "
                  f"| {str(a.get('note'))[:70]}")
    return m


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="calibration_set.json")
    ap.add_argument("--tag", default="v1")
    ap.add_argument("--pv", default="v1")
    ap.add_argument("--l3", action="store_true")
    a = ap.parse_args()
    items = json.load(open(HERE / a.set, encoding="utf-8"))
    out = run(items, a.pv, a.tag, a.l3)
    report(out, a.l3)
    json.dump({k: {kk: vv for kk, vv in v.items() if kk != "item"} for k, v in out.items()},
              open(HERE / "runs" / f"out_{a.tag}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
