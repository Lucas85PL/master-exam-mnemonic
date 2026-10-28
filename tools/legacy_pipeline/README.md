# legacy_pipeline — pierwsza wersja budowy bazy z PDF (archiwum)

Parsery PDF (`parser_pdf_format1/2.py`, `parser_pdf_plumber.py`), `init_db.py`/`build_db.py`, narzędzia GUI (`gui.py`, `review.py`, `fix_pdf.py`),
Vision i konsensus modeli (`vision_*.py`, `pdf_consensus.py`, `kapitan_consensus.py`, `pipeline_pdf.py`, `audit_*.py`). Opis: `LEGACY_AGENTS.md`.

Skrypty zakładają stary układ folderów (PDF-y w `Dział_pokładowy/`, `angielski/`, `Kapitan_…/` obok skryptów, baza `questions.db`)
i `.env` z kluczem OpenRouter w tym samym katalogu — **po przeniesieniu wymagają dostosowania ścieżek**. Zostawione na wszelki wypadek.
Bieżący workflow jakości: `../ai_audit/`.
