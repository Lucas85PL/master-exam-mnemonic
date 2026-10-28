"""Dodanie pytania nr 97 z arkusza 'Zarządzanie statkiem' (Master, 2025), którego ekstrakcja nie odczytała (uszkodzony układ ostatniej strony).
Klucz D z arkusza. Obie bazy (kopie przed zapisem), karta SRS, wyjaśnienie w explanation_cache. Uruchom przy zamkniętej aplikacji."""
import hashlib, shutil, sqlite3, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DBS = {"app": Path.home() / "Documents" / "memonic_app.db", "seed": ROOT / "app" / "assets" / "db" / "memonic_app_seed.db"}
if "memonic_app.exe" in subprocess.run(["tasklist"], capture_output=True, text=True).stdout:
    sys.exit("Aplikacja jest uruchomiona - zamknij ją i powtórz.")
Q = "Certyfikat IOPP traci ważność w dniu dzisiejszym. W tym samym dniu statek przeszedł pozytywnie wymagany przegląd i wychodzi w morze. Które z poniższych działań inspektora jest właściwe"
OPTS = ["inspektor musi wystawić nowy certyfikat przed wyjściem w morze",
        "istniejący certyfikat może być potwierdzony jako ważny do czasu wejścia do następnego portu",
        "istniejący certyfikat może być potwierdzony jako ważny na okres do 90 dni",
        "istniejący certyfikat może być potwierdzony jako ważny na okres do 150 dni"]
KEY = "D"
EXPL = ("Prawidłowa odpowiedź to D. Zgodnie z kluczem arkusza CMKE, gdy statek w dniu wygaśnięcia certyfikatu IOPP pozytywnie przeszedł wymagany przegląd, "
        "inspektor nie musi wystawiać nowego certyfikatu przed wyjściem w morze (A) – może potwierdzić istniejący jako ważny na okres do 150 dni. "
        "Warianty B (do następnego portu) i C (do 90 dni) podają inne okresy. Podobne pytanie dotyczy certyfikatu bezpieczeństwa statku (pyt. 3455).")
SRC = "kapitan żeglugi wielkiej-02-01-zarządzanie statkiem-2025.pdf (pyt. 97)"
MARK = "pdf_urzad:z_arkusza_recznie:2026-10-20"


def h(r):
    return hashlib.sha256("|".join([r[1], r[2] or "", r[3] or "", r[4] or "", r[5] or "", r[6], "v6-best-option"]).encode("utf-8")).hexdigest()


ts = time.strftime("%Y%m%d_%H%M%S")
for label, path in DBS.items():
    shutil.copy2(path, (ROOT / "data" if label == "seed" else path.parent) / (path.name + ".bak_zs97_" + ts))
    db = sqlite3.connect(path)
    if db.execute("SELECT 1 FROM questions WHERE pytanie LIKE 'Certyfikat IOPP traci%'").fetchone():
        print(label, "pytanie już istnieje - pomijam"); db.close(); continue
    qid = db.execute("SELECT MAX(id) FROM questions").fetchone()[0] + 1
    now = int(time.time() * 1000)
    db.execute("INSERT INTO questions (id,kategoria,tematyka,typ_pytania,pytanie,odp_a,odp_b,odp_c,odp_d,poprawna_odpowiedz,poprawna_odpowiedz_tekst,"
               "zrodlo_pliku,review_status,review_notes,study_hidden,ai_verified) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (qid, "Kapitan żeglugi wielkiej", "Zarządzanie statkiem", "testowe", Q, *OPTS, KEY, OPTS["ABCD".index(KEY)], SRC, "ok",
                "dodane ręcznie z arkusza PDF (ekstrakcja nie odczytała ostatniej strony)", 0, MARK))
    db.execute("INSERT INTO srs_cards (question_id,repetitions,interval_days,ease_factor,due_ms,lapses,state,step) VALUES (?,?,?,?,?,?,?,?)", (qid, 0, 0, 2.5, now, 0, 0, 0))
    row = (qid, Q, *OPTS[:4], KEY)
    db.execute("INSERT INTO explanation_cache VALUES (?,?,?,?,?)", (qid, h(row), EXPL, "manual", now))
    db.commit()
    print(label, "dodano ID", qid, "| razem pytań", db.execute("SELECT COUNT(*) FROM questions").fetchone()[0])
    db.close()
