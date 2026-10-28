@echo off
chcp 65001 >nul
title Ensemble PDF (kolejka audytu)
cd /d "%~dp0"

echo ========================================
echo   Ensemble: multipage PDF + fuzzy opcji
echo   Zrodlo: audit_review_queue.csv
echo   AUTO_OK tylko ENSEMBLE_OK (--apply-ok)
echo ========================================
echo.
echo 1. Pilot dry-run (limit 30, MISMATCH)
echo 2. Pilot dry-run (limit 50, wszystkie tiery)
echo 3. Pelna baza pending --from-db (bez zapisu OK)
echo 4. Baza pending --apply-ok (limit 100)
echo 5. Pelna kolejka audit_review_queue.csv (dry-run)
echo 6. Zastosuj ENSEMBLE_OK z JSONL
echo 7. Batch apply-ok (limit 100, MISMATCH z CSV)
echo 8. Wlasne argumenty verify_pdf_ensemble.py
echo 0. Wyjscie
echo.
set /p choice="Wybierz opcje (0-8): "

if "%choice%"=="1" goto p30
if "%choice%"=="2" goto p50
if "%choice%"=="3" goto fulldb
if "%choice%"=="4" goto applydb100
if "%choice%"=="5" goto fullcsv
if "%choice%"=="6" goto applyjsonl
if "%choice%"=="7" goto apply100
if "%choice%"=="8" goto custom
if "%choice%"=="0" goto end
echo Nieprawidlowy wybor.
pause
goto end

:p30
python verify_pdf_ensemble.py --dry-run --limit 30 --audit-tier AUDIT_REVIEW_MISMATCH
pause
goto end

:p50
python verify_pdf_ensemble.py --dry-run --limit 50
pause
goto end

:fulldb
python verify_pdf_ensemble.py --from-db --dry-run
pause
goto end

:applydb100
python verify_pdf_ensemble.py --from-db --limit 100 --apply-ok
pause
goto end

:fullcsv
python verify_pdf_ensemble.py --dry-run
pause
goto end

:applyjsonl
python verify_pdf_ensemble.py --apply-from-jsonl
pause
goto end

:apply100
python verify_pdf_ensemble.py --limit 100 --audit-tier AUDIT_REVIEW_MISMATCH --apply-ok
pause
goto end

:custom
set /p args="Argumenty verify_pdf_ensemble.py: "
python verify_pdf_ensemble.py %args%
pause
goto end

:end
