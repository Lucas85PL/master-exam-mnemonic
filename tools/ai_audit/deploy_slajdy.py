"""Dodanie 6 pytań ze zrzutów slajdów (Desktop\\PYTANIA) do kategorii Master, klucze wskazane przez użytkownika, jako NOWE karty nauki.
Pominięte jako obecne już w bazie: nr 6 (3236), 8 (3553), 9 (3389), 10 (1897), 11 (3411), 14 (3473), 15 (3477), 5 i 12 (to samo co 943). Obie bazy, kopie przed zapisem."""
import shutil, sqlite3, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DBS = {"app": Path.home() / "Documents" / "memonic_app.db", "seed": ROOT / "app" / "assets" / "db" / "memonic_app_seed.db"}
if "memonic_app.exe" in subprocess.run(["tasklist"], capture_output=True, text=True).stdout:
    sys.exit("Aplikacja jest uruchomiona - zamknij ją i powtórz.")
Q = [
    ("Bezpieczeństwo statku", "Które organy IMO mogą przyjmować zmiany do Konwencji SOLAS, MARPOL:",
     ["Sub-Committees", "Committees", "Assembly"], "C", "slajd 2, nr 5"),
    ("Bezpieczeństwo statku", "AIS powinno nadawać automatycznie informacje co najmniej:",
     ["raz na 3 min", "raz na 6 min", "zależnie od prędkości statku"], "C", "slajd 3, nr 7"),
    ("Zarządzanie statkiem", "Umowa czarterowa z opcją „SSHEX” w odniesieniu do okresu ładowania oznacza zwyczajowo:",
     ["sobota włączona do obliczania okresu ładowania", "sobota i niedziela wyłączone z okresu ładowania", "sobota i niedziela włączone do okresu ładowania"], "B", "slajd 4, nr 9"),
    ("Zarządzanie statkiem", "Której decyzji nie może wydać Dyrektor Urzędu Morskiego jako organ PSC:",
     ["zatrzymania statku z rygorem natychmiastowym", "zakazu wejścia statku do portu", "aresztowania statku"], "C", "slajd 5/6, nr 14"),
    ("Bezpieczeństwo statku", "Procedury w sytuacjach awaryjnych na statkach przewożących towary niebezpieczne, szkodliwe, zanieczyszczające:",
     ["EmS Guide", "IGC Code", "MFAG Guide"], "A", "slajd 1, nr 1"),
    ("Bezpieczeństwo statku", "Poziom 3 ochrony dla obiektu portowego lub portu polskiego wprowadza w drodze decyzji:",
     ["Dyrektor urzędu morskiego", "Kapitan portu", "Minister właściwy do spraw gospodarki morskiej"], "C", "slajd 7, nr 17"),
]
ts = time.strftime("%Y%m%d_%H%M%S")
for label, path in DBS.items():
    shutil.copy2(path, (ROOT / "data" if label == "seed" else path.parent) / (path.name + ".bak_slajdy_" + ts))
    db = sqlite3.connect(path)
    start = db.execute("SELECT MAX(id) FROM questions").fetchone()[0] + 1
    now = int(time.time() * 1000)
    for k, (tem, q, o, key, src) in enumerate(Q):
        qid = start + k
        db.execute("INSERT INTO questions (id,kategoria,tematyka,typ_pytania,pytanie,odp_a,odp_b,odp_c,odp_d,poprawna_odpowiedz,poprawna_odpowiedz_tekst,"
                   "zrodlo_pliku,review_status,review_notes,study_hidden,ai_verified) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (qid, "Kapitan żeglugi wielkiej", tem, "testowe", q, o[0], o[1], o[2], None, key, o["ABC".index(key)],
                    f"zrzuty slajdów z czerwonym kółkiem (Desktop\\PYTANIA, {src})", "ok", "klucz wskazany przez użytkownika", 0, "manual:user_verified:2026-10-21"))
        db.execute("INSERT INTO srs_cards (question_id,repetitions,interval_days,ease_factor,due_ms,lapses,state,step) VALUES (?,?,?,?,?,?,?,?)",
                   (qid, 0, 0, 2.5, now, 0, 0, 0))
    db.commit()
    print(label, "ID", start, "-", start + len(Q) - 1, "| razem pytań", db.execute("SELECT COUNT(*) FROM questions").fetchone()[0])
    db.close()
