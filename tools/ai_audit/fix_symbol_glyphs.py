"""Zamienia znaki z prywatnego zakresu Unicode (czcionka Symbol z PDF: U+F0xx) w treści pytań na zwykłe symbole (°, φ, λ ...).
Obie bazy (kopie przed zapisem); dla pytań z wyjaśnieniem w cache przelicza hash treści, żeby wyjaśnienie nie przepadło. Aplikacja musi być zamknięta."""
import hashlib, shutil, sqlite3, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DBS = {"app": Path.home() / "Documents" / "memonic_app.db", "seed": ROOT / "app" / "assets" / "db" / "memonic_app_seed.db"}
if "memonic_app.exe" in subprocess.run(["tasklist"], capture_output=True, text=True).stdout:
    sys.exit("Aplikacja jest uruchomiona - zamknij ją i powtórz.")
# kodowanie Adobe Symbol (kod bajtu w U+F0xx)
MAP = {0xF020: " ", 0xF02D: "−", 0xF061: "α", 0xF062: "β", 0xF067: "γ", 0xF064: "δ", 0xF06C: "λ", 0xF06D: "μ", 0xF070: "π",
       0xF071: "θ", 0xF072: "ρ", 0xF073: "σ", 0xF074: "τ", 0xF06A: "φ", 0xF077: "ω", 0xF057: "Ω", 0xF044: "Δ", 0xF0B0: "°",
       0xF0B1: "±", 0xF0B4: "×", 0xF0B8: "÷", 0xF0A3: "≤", 0xF0B3: "≥", 0xF0B9: "≠", 0xF0AE: "→", 0xF0AC: "←", 0xF0AD: "↑",
       0xF0AF: "↓", 0xF0A8: "♦"}


def fix(s):
    return None if s is None else "".join(MAP.get(ord(ch), ch) if "" <= ch <= "" else ch for ch in s)


def h(r):
    return hashlib.sha256("|".join([r[1], r[2] or "", r[3] or "", r[4] or "", r[5] or "", r[6], "v6-best-option"]).encode("utf-8")).hexdigest()


ts = time.strftime("%Y%m%d_%H%M%S")
cols = ["pytanie", "odp_a", "odp_b", "odp_c", "odp_d", "poprawna_odpowiedz_tekst"]
for label, path in DBS.items():
    shutil.copy2(path, (ROOT / "data" if label == "seed" else path.parent) / (path.name + ".bak_glyphs_" + ts))
    db = sqlite3.connect(path)
    changed = rehash = unknown = 0
    for r in db.execute("SELECT id, " + ", ".join(cols) + " FROM questions").fetchall():
        new = [fix(v) for v in r[1:]]
        if new == list(r[1:]):
            continue
        for v in new:
            unknown += sum(1 for ch in (v or "") if "" <= ch <= "")
        db.execute("UPDATE questions SET " + ", ".join(c + "=?" for c in cols) + " WHERE id=?", (*new, r[0]))
        changed += 1
        if db.execute("SELECT 1 FROM explanation_cache WHERE question_id=?", (r[0],)).fetchone():
            row = db.execute("SELECT id,pytanie,odp_a,odp_b,odp_c,odp_d,poprawna_odpowiedz FROM questions WHERE id=?", (r[0],)).fetchone()
            db.execute("UPDATE explanation_cache SET content_hash=? WHERE question_id=?", (h(row), r[0]))
            rehash += 1
    db.commit()
    print(label, "zmienionych pytań:", changed, "| przeliczony hash wyjaśnienia:", rehash, "| nieznanych znaków PUA po zamianie:", unknown)
    db.close()
