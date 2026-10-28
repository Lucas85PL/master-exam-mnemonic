# Question Database

## What this is
Skrypty do budowania ujednoliconej bazy pytań egzaminacyjnych z PDFów (egzaminy morskie) i pliku Anki (.colpkg). Wynikowa baza to SQLite (`questions.db`).

## Current state (2026-05-25)

- **Aplikacja nauki:** `../memonic_app/` — Flutter v1 na Windows, import `questions.db` ręczny; git w `memonic_app/.git`. Nie commituj kopii bazy z danymi użytkownika w app.
- Baza: **3435 pytań** (3195 testowych + 240 otwartych) — liczniki pending odśwież: `python _pipeline_stats.py`
- **Pipeline auto-weryfikacji** (Vision + konsensus 3 modeli OpenRouter):
  - **Kapitan** — zakończony: 154× Vision, **77** auto-OK (`consensus_ok`)
  - **Dział + Angielski** (`pipeline_pdf.py`) — Vision **~2139**× `vision_page`, stary konsensus **~859** `consensus_ok`; pending Vision **~13**, pending konsensus **~1049**
- **Audyt PDF (conservative)** — pełny batch **1312**; zapisano **240**× `audit_ok:pdf+consensus` → `review_status=ok`; kolejka ręczna **1031** (`audit_review_queue.csv`); pending bez audytu OK: **1072**
- Wznowienie Vision/konsensus: `python pipeline_pdf.py --phase all --limit 200`
- Zapis audytu OK (bez ponownego API): `python audit_pdf.py --apply-from-jsonl`
- Ensemble na kolejce audytu (bez API): `python verify_pdf_ensemble.py --csv audit_review_queue.csv --dry-run`
- Konsensus 5× pending (3/5 z bazą → OK): `python consensus_pending.py --limit 50 --fresh`
- Szczegóły: **[PIPELINE_STATUS.md](PIPELINE_STATUS.md)** · liczniki: `python _pipeline_stats.py`

## Database schema (SQLite)

```
questions:
  id, kategoria, podkategoria, poziom, tematyka,
  nr_pytania, typ_pytania (testowe/otwarte),
  pytanie, odp_a, odp_b, odp_c, odp_d,
  poprawna_odpowiedz, poprawna_odpowiedz_tekst, zrodlo_pliku,
  review_status, review_notes

parsed_files:
  sciezka, parser, liczba_pytan, data_parsowania
```

`review_status`: `ok` | `error` | `NULL`/`''` (niezweryfikowane).  
`review_notes`: m.in. `vision_page:…`, `consensus_ok:…`, `audit_ok:pdf+consensus:…` — patrz PIPELINE_STATUS.md.

## Source mapping

| Folder | Parser | Kategoria | Hierarchia |
|--------|--------|-----------|------------|
| `Dział_pokładowy/` | format1 | Dział pokładowy | poziom → podkategoria → tematyka (z pliku) |
| `angielski/` | format1 | Angielski | podkategoria → tematyka (z pliku) |
| `Kapitan_żeglugi_wielkiej_pytania/` | format2 | Kapitan żeglugi wielkiej | tematyka (z pliku) |
| `cpt-AllInOne.colpkg` | anki | Chief Officer | tematyka (z talii Anki) |

## Files

| File | Purpose |
|------|---------|
| `init_db.py` | Schemat SQLite, funkcje pomocnicze (insert, stats, clear) |
| `parser_pdf_format1.py` | Parser PDF — Dział pokładowy + Angielski (format tabelaryczny, split-answer detection) |
| `parser_pdf_format2.py` | Parser PDF — Kapitan (cluster-based, cross-page merge) |
| `parser_anki.py` | Parser .colpkg (ZIP + SQLite, auto-detect MSO/HTML/inline format) |
| `build_db.py` | Główny skrypt — uruchamia wszystkie parsery |
| `validate_db.py` | Walidator — sprawdza 12 kategorii błędów (HIGH/MED/LOW) |
| `gui.py` | Aplikacja GUI — przeglądanie, edycja, dodawanie, usuwanie, multi-select, eksport |
| `review.py` | Review tool — weryfikacja pytań z podglądem PDF (dual-pane) |
| `start.bat` | Menu startowe (GUI / rebuild) |
| `DBreview.bat` | Launcher review tool |
| `fix_pdf.py` | Narzędzie naprawcze — ponowny odczyt pytań z PDF (pdfplumber jako drugi silnik), tickboxy błędnych pól, zapis poprawek do bazy |
| `parser_pdf_plumber.py` | Parser PDF oparty na pdfplumber; `find_question_page`, `detect_table_format` |
| `parser.bat` | Launcher narzędzia naprawczego |
| `pdf_crop.py` | Crop PDF (+ cross-page stitch) → PNG dla Vision |
| `openrouter_vision.py` | Klient OpenRouter Vision; prompty format1 + Kapitan page |
| `vision_fix.py` | CLI batch: auto-fix pytań `review_status=error` (crop) |
| `vision_fix.bat` | Launcher vision_fix |
| `pdf_page.py` | Render pełnej strony PDF (1–2 strony); `render_pages_at_nums` |
| `vision_kapitan.py` | CLI Vision full-page — Kapitan |
| `vision_kapitan.bat` | Launcher vision_kapitan |
| `openrouter_consensus.py` | 3 modele tekstowe → litera A-D |
| `kapitan_consensus.py` | Konsensus → auto OK (Kapitan) |
| `kapitan_consensus.bat` | Launcher kapitan_consensus |
| `pipeline_scope.py` | Filtry SQL zakresu Dział + Angielski |
| `vision_pdf.py` | Vision full-page — Dział + Angielski |
| `pdf_consensus.py` | Konsensus → auto OK (Dział + Angielski) |
| `pipeline_pdf.py` | Orchestrator Vision → konsensus |
| `pipeline_pdf.bat` | Launcher pipeline_pdf |
| `audit_scope.py` | SQL zakresu audytu (Dział + EN + Kapitan, bez Anki) |
| `audit_decision.py` | Reguły triage: PDF + DB + konsensus 3/3 |
| `audit_pdf.py` | CLI audytu batch (`--dry-run`, `--apply-ok`) |
| `audit_report.py` | JSONL + `audit_review_queue.csv` |
| `run_audit.bat` | Launcher audytu PDF |
| `verify_pdf_ensemble.py` | Ensemble PDF+fuzzy na `audit_review_queue.csv` |
| `ensemble_decision.py` | Reguły tierów ENSEMBLE_* |
| `run_ensemble.bat` | Launcher ensemble |
| `consensus_pending.py` | 5 modeli, 3/5 zgodnych z DB → OK (pending) |
| `consensus_pending.bat` | Launcher konsensus pending |
| `test_ensemble_decision.py` | Testy tierów ensemble |
| `test_audit_decision.py` | Testy jednostkowe tierów |
| `PIPELINE_STATUS.md` | **Checkpoint** — partie, statystyki, wznowienie |
| `_pipeline_stats.py` | Liczniki pending / auto-OK w bazie |
| `.env` | Klucz API OpenRouter (nie commituj) |
| `vision_cache/` | Cache PNG + odpowiedzi JSON |
| `questions.db` | Wynikowa baza SQLite |
| `DB Backup/` | Kopie zapasowe bazy |

## How to rebuild

```bash
python build_db.py
```

Skrypt pomija już sparsowane pliki (tabela `parsed_files`). Aby przebudować od zera:
```bash
python -c "from init_db import get_connection, clear_data; clear_data(get_connection())"
python build_db.py
```

## GUI

```bash
python gui.py
```

Funkcje: filtrowanie (kategoria/podkategoria/tematyka/szukaj), sortowanie domyślnie po numerze pytania z PDF, kolumna Nr, edycja, dodawanie, usuwanie (pojedyncze + batch z multi-select Shift/Ctrl), eksport bazy, wyświetlanie odpowiedzi dla fiszek.

## Review tool

```bash
python review.py
```

Dual-pane: lewy panel — szczegóły pytania (identyczny jak w GUI) z edycją, prawy panel — podgląd PDF z zoom (scroll) i pan (drag). Automatyczne wyszukiwanie pytania w PDF. Przyciski OK (zweryfikowane) / BŁĄD (do poprawy) / DALEJ / WSTECZ. Tickbox "Pokaż Anki".

## Fix PDF tool (narzędzie naprawcze)

```bash
python fix_pdf.py
# lub:
parser.bat
```

Cel: naprawa pytań oflagowanych jako BŁĄD w DBreview. Używa **pdfplumber** jako drugiego, niezależnego silnika do odczytu tekstu z PDF-a.

**Workflow:**
1. Prawy panel: PDF z podświetlonym pytaniem (fitz lokalizuje)
2. Użytkownik klika **Parsuj** → parser tabelowy pdfplumber (`find_tables` + word-extraction) odczytuje pytanie + odpowiedzi
3. Lewy panel pokazuje odczytane dane (Pytanie, Odp A/B/C/D, Poprawna) z tickboxami
4. Tickbox = pole błędnie odczytane. Ponowne Parsuj ponawia odczyt dla zaznaczonych pól.
5. Ręczna edycja pól dostępna
6. **Zapisz** — zapisuje całość do bazy, zmienia `review_status` na "ok"

**Parsowanie:** używa `pdfplumber.find_tables()` do wykrycia tabeli i `extract_words(x_tolerance=2)` dla prawidłowych odstępów między słowami. Obsługuje format1 (6-kolumnowy Dział pokładowy/Angielski) i format2 (4-kolumnowy Kapitan).

**Filtry:** kategoria, podkategoria, tematyka (jak DBreview). Tickbox "Parsuj wyłącznie błędy" (domyślnie ON) — pokazuje tylko error + niezweryfikowane.
**Anki:** pytania z Chief Officer (colpkg) są ukryte.

## Vision auto-fix (OpenRouter) — crop

Automatyczna korekta pytań oflagowanych jako BŁĄD (`review_status='error'`) przez model Vision (domyślnie `google/gemini-2.0-flash-001`).

**Konfiguracja:** skopiuj `.env.example` → `.env`, ustaw `OPENROUTER_API_KEY`.

```bash
pip install -r requirements.txt
python vision_fix.py --limit 5
python vision_fix.py --id 1234
python vision_fix.py --dry-run
python vision_fix.py
python vision_fix.py --rescan
```

Notatka w bazie: `vision:` (nie `vision_page:`). Pipeline Dział+EN domyślnie ponawia te pytania full-page.

## Vision Kapitan full-page (OpenRouter)

Dla kategorii **Kapitan żeglugi wielkiej** — pytania `error` lub niezweryfikowane. Pełna strona PDF (lub 2 strony).

```bash
python vision_kapitan.py --dry-run --limit 5
python vision_kapitan.py --id 41556
python vision_kapitan.py
```

Cache: `vision_cache/kapitan_YYYYMMDD_HHMMSS/`. Zmienna `.env`: `VISION_PAGE_SCALE=1.5`.

## Kapitan consensus auto-OK (OpenRouter)

Po `vision_page:` — 3 modele, 3/3 zgodne z `poprawna_odpowiedz` → `review_status=ok`.

```bash
python kapitan_consensus.py --dry-run --limit 5
python kapitan_consensus.py
```

Modele: `CONSENSUS_MODEL_1` … `_3` w `.env`. Log: `kapitan_consensus.log`, `consensus_results.jsonl`.

## Pipeline PDF — Dział pokładowy + Angielski

Zakres: `Dział_pokładowy/`, `angielski/angielski/` — error / niezweryfikowane. Pomija Anki i Kapitan.

```bash
python pipeline_pdf.py --phase all --limit 200   # typowa partia (~25–30 min)
python pipeline_pdf.py --phase consensus --limit 200
python pipeline_pdf.py --phase vision --dry-run --limit 5
python pipeline_pdf.py --phase all --rescan
python _pipeline_stats.py                      # liczniki kolejki
```

**Stan i historia partii:** [PIPELINE_STATUS.md](PIPELINE_STATUS.md)

Logi: `vision_pdf.log`, `pdf_consensus.log`, `pdf_consensus_results.jsonl`. Cache: `vision_cache/pdf_*/`.

## Validation

```bash
python validate_db.py
```

Sprawdza: puste pytania, brak opcji, brak poprawnej, poprawna → pusta opcja, HTML w treści, dziwne znaki, bardzo długie opcje (merge), duplikaty.

## Known issues
- Brak opcji D w ~3000 pytaniach — normalne, większość ma tylko A/B/C
- ~500 duplikatów — angielskie wersje tych samych pytań co polskie (różne kategorie)
- Folder "Poziom pomocniczy" nie istnieje w katalogu `Dział_pokładowy`
- 3 encje HTML w treści pytań (pozostałości po parsowaniu)
- Parser Kapitan (format2) traci ~112 pytań i ma ~34% błędnych odpowiedzi — wymaga przepisania na pdfplumber (raport walidacji: `raport_walidacji_bazy_pytan.docx`)
- Fix PDF tool — parser tabelowy pdfplumber może gubić niektóre odpowiedzi w formacie2 gdy komórki kontynuacji nakładają się na kolumny
- Konsensus: Qwen czasem rozjeżdża głos względem Gemini/DeepSeek (NO_CONSENSUS)

## Change log
- 2026-05-25: `memonic_app` v1 — konsumpcja `questions.db` (pula `ok`, SM-2); pipeline bez zmian w schemacie pod app
- 2026-05-17: Initial implementation — parsery PDF format1/format2, Anki colpkg
- 2026-05-17: Fix v1 — Kapitan cluster-based parser, Format1 split answer, Anki HTML/embed, GUI multi-select
- 2026-05-22: Review tool — zaznaczanie i kopiowanie tekstu z PDF (Ctrl+drag)
- 2026-05-22: Fix PDF tool v2 — pdfplumber find_tables + format1_6col/format2
- 2026-05-24: Vision auto-fix — `vision_fix.py` + OpenRouter, cross-page stitch
- 2026-05-24: Vision Kapitan full-page — `vision_kapitan.py` + `pdf_page.py`
- 2026-05-24: Kapitan consensus — 77 auto-OK / 154 vision_page
- 2026-05-24: Pipeline PDF Dział+EN — `pipeline_pdf.py`; 4 partie (50+200+200+200) → 653 vision_page, 220 auto-OK; `PIPELINE_STATUS.md`
