# Workflow przeglądu bazy pytań (v5) — warstwy L1 → L2 → L3

Pełny opis, zasady i procedura: **[../../AGENTS.md](../../AGENTS.md) §6**. Tu skrót techniczny.

| Warstwa | Model | Co robi | Wchodzą |
|---|---|---|---|
| L1 | `openai/gpt-6-luna` (reasoning low) | Zna klucz; ocenia integralność tekstu + wiarygodność klucza (JSON) | wszystkie |
| L2 | `deepseek/deepseek-v4.1-flash` (low) | NIE zna klucza; lista kontrolna integralności + ślepa odpowiedź | wszystkie |
| L3 | `anthropic/claude-sonnet-5.5` (medium) | Finalny arbiter OK / DEFECT / KEY_SUSPECT | tylko `key` / `weak` |

Routing (`wf.py`, `confirmed()` dla `v5`): `integrity` (L1+L2 zgodnie → lista poprawek), `figure` (→ usunąć), `key` (ślepa odp. L2 ≥ 90, albo L1 „niewiarygodny” ≥ 85 i L2 ≥ 80 ten sam inny wariant → L3), `weak` (L1 poważna usterka, L2 nie potwierdza / błąd API → L3).

Kalibracja (3 × 30 pytań): usterki tekstu 97%, klucza 67%; czyste do Sonneta ≈ 11%; koszt ≈ 1–1,4 USD / 1000 pytań.

## Uruchamianie
Wymaga `OPENROUTER_API_KEY` (zmienna środowiskowa lub plik `.env` w katalogu głównym projektu). Baza: `MEM_DB` lub `Documents\memonic_app.db`.
```bash
cd tools/ai_audit
python build_calibration.py                       # (opcjonalnie) nowy zestaw kalibracyjny: CAL_SEED=14 CAL_OUT=holdout_c.json
python wf.py --set calibration_set.json --tag test --pv v5 --l3
python audit_db.py --limit 60 --tag probe         # próba na losowych pytaniach
python audit_db.py --after-id 900 --limit 100000 --ordered --cap 8 --tag batchN
```
Pytania z obrazkiem (`image_path`): `python audit_db.py --only-images --cap 3 --tag figures` — obraz jest dołączany do wywołań L1/L2/L3 (Luna i DeepSeek V4.1 Flash przyjmują obrazy), `needs_figure` nie jest wtedy usterką.

Wynik: `../../review/Przeglad_AI_<tag>.xlsx` oraz `runs/audit_<tag>.json`. `runs/cache_*.jsonl` (cache wywołań) jest w .gitignore.

## Zawartość
- `exam_verify.py` — weryfikacja pytań ze skanów egzaminów: etap A duplikaty względem bazy (Haiku 5.5), etap B roj 3 sędziów Haiku 5.5 (reasoning medium) z fragmentami ustaw; `exam_verify2.py` — runda 2: 2× Claude Sonnet 5.5 + GPT 6.1 Sol;
  `deploy_exam_high.py` — wdrożenie HIGH do bazy aplikacji i seeda (kopie, log; podgląd bez `--apply`). Wyniki: `review/Weryfikacja_2026-10-12/`. Klucz OpenRouter ma limit całkowity.
- `dup_swarm.py` — **roj Haiku 5.5** wykrywa powtórzone pytania o nieidentycznym zapisie (uruchamiaj na KOPII bazy): `python dup_swarm.py --db <kopia.db> --tag run1`; wynik `runs/dups_<tag>.json` + `review/Duplikaty_swarm_<tag>.xlsx`;
  `apply_dup_links.py <baza> <json> --apply` zapisuje powiązania w tabeli `dup_links` (kopia bazy przed zapisem).
- `history/authored_lib.py` + `history/add_master_authored*.py` — generator/wstawianie autorskich pytań Master; kontrola: `python audit_db.py --categories Kap --marker ai_authored --cap 3 --tag authored`.
- `wf.py` — kaskada + metryki · `audit_db.py` — przegląd bazy z limitem kosztu i Excelem · `build_calibration.py` — zestawy z wstrzykniętymi usterkami
- `calibration_set.json`, `holdout_set_a/b.json` — zestawy testowe · `runs/audit_*.json` — wyniki przeglądów (audit trail)
- `history/` — jednorazowe skrypty poprawek (`apply_*`), skrypty testowe i logi (z nich korzysta `review/restore_questions.py`)

## Ograniczenia
Zamienione klucze uznane przez tani model za „wiarygodne” (kotwiczenie) wymykają się (~1/3); zadania obliczeniowe oceniane niepewnie;
modele nie są deterministyczne.
