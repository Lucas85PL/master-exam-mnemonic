# Status pipeline Vision + konsensus

Ostatnia aktualizacja dokumentu: **2026-05-24** (po **4 partiach** + test; łącznie **653**× Vision, **220** auto-OK).

Dokument kontrolny — jak wznowić pracę, co już zrobione, gdzie szukać logów.

**Nazwa pipeline:** `pipeline_pdf.py` (alias: **Pipeline PDF**, Dział + Angielski).

---

## Aplikacja Flutter (`../memonic_app/`) — 2026-05-25

| Element | Stan |
|---------|------|
| Windows | Działa (`run.ps1`, SDK `.tools/flutter`) |
| Import bazy | Ręczny z `questions.db` (merge po `id`) |
| Git | `memonic_app/.git` — `main`, commit `f871aff` |
| Nauka w app | Tylko `review_status=ok`; Anki pomijane przy imporcie |

Kontynuacja app: patrz `../memonic_app/AGENTS.md` i `../AGENTS.md`.  
Pipeline DB: liczniki poniżej mogą być nieaktualne — **`python _pipeline_stats.py`** przed partią.

---

## Szybki start (wznowienie pipeline)

```powershell
cd "C:\Users\lukas\Desktop\Dev\Master Exam Mnemonic\Question Database"

# Sprawdź kolejkę
python _pipeline_stats.py

# Następna partia (Vision → konsensus)
python pipeline_pdf.py --phase all --limit 200

# Tylko konsensus dla pytań z vision_page (bez nowego Vision)
python pipeline_pdf.py --phase consensus --limit 200
```

Wymaga `.env` z `OPENROUTER_API_KEY` i modelami konsensusu (`CONSENSUS_MODEL_1` … `_3`).

---

## Zakresy pipeline (3 niezależne ścieżki)

| Ścieżka | Skrypt orchestratora | Źródło PDF | Status (2026-05-24) |
|---------|----------------------|------------|---------------------|
| **Kapitan** | `vision_kapitan.py` → `kapitan_consensus.py` | `Kapitan_żeglugi_wielkiej_pytania/` | Vision **154/154** OK; konsensus: **77** auto-OK, reszta ręcznie |
| **Dział + Angielski** | `pipeline_pdf.py` | `Dział_pokładowy/`, `angielski/angielski/` | W toku — patrz poniżej |
| **Crop (stary)** | `vision_fix.py` | error z PDF (bez Kapitan/Anki) | Osobny flow; notatka `vision:` nie `vision_page:` |

**Pomijane zawsze:** Anki (`Chief Officer`, `%colpkg%`).

---

## Dział pokładowy + Angielski — stan bazy

*Odśwież: `python _pipeline_stats.py`*

| Metryka | Liczba |
|---------|--------|
| Pending Vision (bez `vision_page`) | **~1508** |
| Pending konsensus (`vision_page`, bez `consensus_ok`, nie-OK) | **~433** |
| Z `vision_page:` w notatce (łącznie) | **653** |
| Auto-OK (`consensus_ok` w notatce) | **220** |

Szacunek zakresu Vision: **~2161** pytań → przetworzono **653** (**~30%**). Pozostało Vision: **~1508**.

---

## Wykonane partie (`pipeline_pdf.py --phase all`)

### Partia 1 — limit 50 (~6,5 min)

| Faza | OK | AUTO_OK | NO_CONSENSUS | MISMATCH_DB | SKIP |
|------|-----|---------|--------------|-------------|------|
| Vision | 50 | — | — | — | — |
| Konsensus | — | 16 | 29 | 4 | 1 |

Cache: `vision_cache/pdf_20260524_153925/`

### Partia 2 — limit 200 (~26 min)

| Faza | OK | AUTO_OK | NO_CONSENSUS | MISMATCH_DB | SKIP |
|------|-----|---------|--------------|-------------|------|
| Vision | 200 | — | — | — | — |
| Konsensus | — | 99 | 77 | 22 | 2 |

### Partia 3 — limit 200 (~22 min)

| Faza | OK | AUTO_OK | NO_CONSENSUS | MISMATCH_DB | SKIP |
|------|-----|---------|--------------|-------------|------|
| Vision | 200 | — | — | — | — |
| Konsensus | — | 61 | 88 | 49 | 2 |

### Partia 4 — limit 200 (~31 min)

| Faza | OK | AUTO_OK | NO_CONSENSUS | MISMATCH_DB | SKIP |
|------|-----|---------|--------------|-------------|------|
| Vision | 200 | — | — | — | — |
| Konsensus | — | 44 | 109 | 39 | 8 |

### Wcześniejszy test (3 pytania)

ID 39307, 39355, 39365 — Vision OK; konsensus NO_CONSENSUS (wzór `A,C,A` vs baza `C`).

### Podsumowanie partii 1–4 + test

| | Vision OK | AUTO_OK |
|--|-----------|---------|
| Partia 1 (50) | 50 | 16 |
| Partia 2 (200) | 200 | 99 |
| Partia 3 (200) | 200 | 61 |
| Partia 4 (200) | 200 | 44 |
| Test (3) | 3 | 0 |
| **Razem** | **653** | **220** |

Średni odsetek AUTO_OK w konsensusie (partie 1–4): **~35%** (220 / 650 pytań z partii, bez testu).

---

## Kapitan — stan (zakończony batch)

| Metryka | Liczba |
|---------|--------|
| Vision full-page (`vision_page:`) | **154** |
| Auto-OK (`consensus_ok`) | **77** |
| Do ręcznej weryfikacji (NO_CONSENSUS + MISMATCH) | **~73** |

Logi: `vision_kapitan.log`, `kapitan_consensus.log`, `consensus_results.jsonl`.

---

## Konwencje `review_notes`

| Prefiks | Znaczenie |
|---------|-----------|
| `vision_page:MODEL:DATE` | Udany skan full-page — treść zaktualizowana, `review_status` NULL |
| `vision_page_fail:…` | Błąd Vision |
| `vision:MODEL:DATE` | Stary crop (`vision_fix.py`) — pipeline PDF domyślnie ponawia full-page |
| `consensus_ok:MODELS:DATE` | 3/3 zgodne z bazą → `review_status=ok` (stary gate) |
| `audit_ok:pdf+consensus:DATE` | PDF == DB == 3/3 → `review_status=ok` (audyt) |

---

## Modele OpenRouter (`.env`)

**Vision:** `OPENROUTER_MODEL` → `google/gemini-2.0-flash-001`

**Konsensus:** Gemini 2.0 Flash, Qwen 2.5 72B Instruct, DeepSeek V3 (`deepseek/deepseek-chat`) — bez modeli reasoning.

---

## Pliki logów

| Plik | Pipeline |
|------|----------|
| `vision_pdf.log` | Dział + EN Vision |
| `pdf_consensus.log` | Dział + EN konsensus |
| `pdf_consensus_results.jsonl` | Głosy (nadpisywany co run) |
| `vision_kapitan.log` / `kapitan_consensus.log` | Kapitan |

---

## Audyt PDF (triage — PDF jako ground truth)

**Skrypt:** `audit_pdf.py` · launcher: `run_audit.bat`

Zasada: `review_status=ok` tylko gdy **pdfplumber** + **3/3 konsensus** (tekst z bazy) + **litera w bazie** są zgodne; przy konflikcie PDF ≠ baza → kolejka review (bez auto-poprawy).

```powershell
# Pilot (bez zapisu do bazy)
python audit_pdf.py --dry-run --limit 50 --compare-consensus

# Pełny audyt (~1312 pending) — raport + CSV kolejki
python audit_pdf.py --compare-consensus

# Zapis AUDIT_OK do bazy (z gotowego JSONL — szybko, bez API)
python audit_pdf.py --apply-from-jsonl

# Zapis w trakcie ponownego audytu (wolne)
python audit_pdf.py --apply-ok --limit 100
```

| Plik | Zawartość |
|------|-----------|
| `audit_results.jsonl` | Wynik per ID (tier, pdf/db letter, głosy) |
| `audit_review_queue.csv` | Kolejka review (MISMATCH → NO_CONSENSUS → NO_PDF) |
| `audit_pdf.log` | Log tekstowy |

Tiery: `AUDIT_OK` · `AUDIT_REVIEW_MISMATCH` · `AUDIT_REVIEW_NO_CONSENSUS` · `AUDIT_REVIEW_NO_PDF` · `AUDIT_SKIP` · `AUDIT_STRUCT`

Pending audytu (bez `audit_ok:`): **1312** (836 Dział + 466 EN + 10 Kapitan).

### Wynik pełnego audytu (2026-05-24, ~100 min)

| Tier | Razem | Dział | Angielski | Kapitan |
|------|-------|-------|-----------|---------|
| **AUDIT_OK** | **240** | 170 | 70 | 0 |
| AUDIT_REVIEW_MISMATCH | 281 | 168 | 111 | 2 |
| AUDIT_REVIEW_NO_CONSENSUS | 729 | 478 | 250 | 1 |
| AUDIT_REVIEW_NO_PDF | 18 | 0 | 12 | 6 |
| AUDIT_SKIP | 41 | 20 | 21 | 0 |
| AUDIT_STRUCT | 3 | 0 | 2 | 1 |

Kolejka CSV: **1031** wierszy (`audit_review_queue.csv`). AUTO_OK **~18%** (240/1312) — poniżej szacunku planu; konserwatywna reguła PDF+3/3 działa.

Porównanie z `pdf_consensus_results.jsonl` (145 wspólnych ID): głównie `NO_CONSENSUS→AUDIT_REVIEW_NO_CONSENSUS` (86), `MISMATCH_DB→AUDIT_REVIEW_MISMATCH` (34); 12× stary MISMATCH_DB → audyt MISMATCH (konsensus ≠ PDF mimo zgodności z bazą).

### Zapis do bazy (2026-05-24)

```powershell
python audit_pdf.py --apply-from-jsonl
```

| Akcja | Liczba |
|-------|--------|
| `review_status=ok` + `audit_ok:pdf+consensus:…` | **240** |
| Pozostało w kolejce audytu (bez `audit_ok`) | **1072** |

Podział zapisanych OK: Dział **170**, Angielski **70**, Kapitan **0**.

---

## Ensemble PDF (kolejka audytu — bez API)

**Skrypt:** `verify_pdf_ensemble.py` · launcher: `run_ensemble.bat`

Wejście: **`audit_review_queue.csv`** (domyślnie). Parsowanie: `parse_question_multipage` (+ opcjonalnie parse tabeli na tej samej stronie) + **fuzzy** opcji vs baza (rapidfuzz, próg 85).

Zasada: `review_status=ok` tylko dla **`ENSEMBLE_OK`** (litera PDF == DB + fuzzy wszystkich wypełnionych opcji); przy `--apply-ok` notatka `ensemble_ok:pdf+fuzzy:DATE`.

```powershell
# Pilot na MISMATCH (bez zapisu)
python verify_pdf_ensemble.py --dry-run --limit 50 --audit-tier AUDIT_REVIEW_MISMATCH

# Cała kolejka audytu → JSONL + ensemble_review_queue.csv
python verify_pdf_ensemble.py --dry-run

# Zapis ENSEMBLE_OK z JSONL
python verify_pdf_ensemble.py --apply-from-jsonl

# Batch z zapisem (np. 100 MISMATCH)
python verify_pdf_ensemble.py --limit 100 --audit-tier AUDIT_REVIEW_MISMATCH --apply-ok
```

| Plik | Zawartość |
|------|-----------|
| `ensemble_results.jsonl` | Wynik per ID (tier, fuzzy, pdf/db letter, audit_tier) |
| `ensemble_review_queue.csv` | Pozostała kolejka (REVIEW / MISMATCH / NO_PDF) |
| `ensemble_pdf.log` | Log tekstowy |

Tiery: `ENSEMBLE_OK` · `ENSEMBLE_REVIEW_MISMATCH` · `ENSEMBLE_REVIEW` · `ENSEMBLE_NO_PDF` · `ENSEMBLE_SKIP`

Filtry: `--audit-tier` (wielokrotnie) · `--limit` · `--offset` · `--id` · `--fuzzy-threshold`

---

## DBreview — priorytety ręczne

1. **`ensemble_review_queue.csv`** — po ensemble (szybki PDF+fuzzy)
2. **`audit_review_queue.csv`** — po audycie (MISMATCH, NO_CONSENSUS, NO_PDF)
2. `MISMATCH_DB` w `pdf_consensus_results.jsonl` (stary konsensus)
3. `NO_CONSENSUS` — zwłaszcza gdy 2/3 zgodne z PDF
4. Kapitan bez `consensus_ok`

---

## Znane obserwacje

- Vision format1: typowo `[1p] format1 pages=0`; czasem `pages=1` (strona 0-based w logu).
- Wczesne ID (~39307+): często `A,C,A` vs baza `C` (Qwen vs Gemini/DeepSeek).
- Partia 2: ~50% AUTO_OK; partia 3: ~31%; partia 4: ~22% (więcej MISMATCH/SKIP).
- Kolejna partia: `python pipeline_pdf.py --phase all --limit 200` (~22–31 min).
- Konsensus bez nowego Vision: `--phase consensus --limit 200` (kolejka ~433).

---

## Historia dokumentu

| Data | Notatka |
|------|---------|
| 2026-05-25 | Sekcja `memonic_app` — app Windows OK, git w app |
| 2026-05-24 | 4 partie pipeline_pdf, audyt batch 240 OK |
