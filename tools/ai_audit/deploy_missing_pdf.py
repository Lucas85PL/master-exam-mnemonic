"""Dodanie do bazy pytań z arkuszy PDF, których brakowało (Angielski + 4 pytania Pokład/Master), z kluczem z PDF, jako NOWE karty nauki.
Dane: review/Zgodnosc_z_PDF/do_dodania_pelne.json (pozycje 'wybrane'), uwagi z kontroli tekstu (DeepSeek): integralnosc_deepseek.json.
Uruchom przy zamkniętej aplikacji; kopie obu baz przed zapisem. --dry = tylko podgląd (bez zapisu)."""
import json, re, shutil, sqlite3, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "review" / "Zgodnosc_z_PDF"
items = [x for x in json.load(open(D / "do_dodania_pelne.json", encoding="utf-8")) if x.get("wybrane")]
integ = json.load(open(D / "integralnosc_deepseek.json", encoding="utf-8")) if (D / "integralnosc_deepseek.json").exists() else {}
all_items = json.load(open(D / "do_dodania_pelne.json", encoding="utf-8"))
# uwagi z kontroli tekstu (DeepSeek) trafiają do review_notes pytania
for i, x in enumerate(all_items):
    v = integ.get(str(i))
    if x.get("wybrane") and v and v.get("ok") is False:
        x["notatka"] = "dodane z arkusza PDF (brakujące w bazie); klucz z PDF; UWAGA tekst (kontrola AI): " + (v.get("issue") or "?")
    elif x.get("wybrane") and v and v.get("ok") is None:
        x["notatka"] = "dodane z arkusza PDF (brakujące w bazie); klucz z PDF; kontrola tekstu AI nie powiodła się - sprawdź ręcznie"
items = [x for x in all_items if x.get("wybrane")]
DBS = {"app": Path.home() / "Documents" / "memonic_app.db", "seed": ROOT / "app" / "assets" / "db" / "memonic_app_seed.db"}
DRY = "--dry" in sys.argv
if not DRY and "memonic_app.exe" in subprocess.run(["tasklist"], capture_output=True, text=True).stdout:
    sys.exit("Aplikacja jest uruchomiona - zamknij ją i powtórz.")
MARK = "pdf_urzad:dodane_z_arkusza:2026-10-20"


def norm(s):
    return re.sub(r"[^\w]+", " ", (s or "").lower()).strip()


def meta(x):
    f = x["plik"].replace("\\", "/")
    base = f.split("/")[-1]
    m = re.match(r"F\d-P\d+\s*[- ]\s*(.+?)\s*\.pdf$", base) or re.match(r"F\dP\d+\s+(.+?)\s*\.pdf$", base)
    topic = (m.group(1) if m else base).strip()
    if x["grupa"] == "Angielski":
        return dict(kat="Angielski", pod="Oficer wachtowy", poz=None, tem=topic)
    if x["grupa"] == "Pokład":
        mgmt = "Poziom zarządzania" in f
        return dict(kat="Dział pokładowy", pod="Starszy oficer pokładowy w żegludze międzynarodowej" if mgmt else "Oficer wachtowy",
                    poz="zarządzania" if mgmt else "operacyjny", tem=topic)
    m = re.search(r"-\d\d-\d\d-(.+?)-2025", base)
    return dict(kat="Kapitan żeglugi wielkiej", pod=None, poz=None, tem=(m.group(1) if m else topic))


# bez powtórzeń wewnątrz partii
seen, batch = set(), []
for x in items:
    k = norm(x["q"]) + "|" + "|".join(norm(t) for t in x["opts"].values())
    if k in seen:
        continue
    seen.add(k)
    batch.append(x)
print("do dodania:", len(batch), "(pominięto powtórzeń w partii:", len(items) - len(batch), ")")
ts = time.strftime("%Y%m%d_%H%M%S")
for label, path in DBS.items():
    if not DRY:
        shutil.copy2(path, (ROOT / "data" if label == "seed" else path.parent) / (path.name + ".bak_missingpdf_" + ts))
    db = sqlite3.connect(path)
    start = db.execute("SELECT MAX(id) FROM questions").fetchone()[0] + 1
    now = int(time.time() * 1000)
    for k, x in enumerate(batch):
        m = meta(x)
        o = [x["opts"].get(L) for L in "ABCD"]
        db.execute("INSERT INTO questions (id,kategoria,podkategoria,poziom,tematyka,nr_pytania,typ_pytania,pytanie,odp_a,odp_b,odp_c,odp_d,"
                   "poprawna_odpowiedz,poprawna_odpowiedz_tekst,zrodlo_pliku,review_status,review_notes,study_hidden,ai_verified,image_path) "
                   "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (start + k, m["kat"], m["pod"], m["poz"], m["tem"], x.get("nr"), "testowe", x["q"], *o, x["key"], x["opts"][x["key"]],
                    x["plik"], "ok", x.get("notatka") or "dodane z arkusza PDF (brakujące w bazie); klucz z PDF; do sprawdzenia przez użytkownika", 0, MARK, None))
        db.execute("INSERT INTO srs_cards (question_id,repetitions,interval_days,ease_factor,due_ms,lapses,state,step) VALUES (?,?,?,?,?,?,?,?)",
                   (start + k, 0, 0, 2.5, now, 0, 0, 0))
    print(label, "ID", start, "-", start + len(batch) - 1, "| razem pytań", db.execute("SELECT COUNT(*) FROM questions").fetchone()[0])
    if DRY:
        db.rollback()
    else:
        db.commit()
    db.close()
