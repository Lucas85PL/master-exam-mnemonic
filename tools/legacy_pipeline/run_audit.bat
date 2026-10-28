@echo off
chcp 65001 >nul
title Audyt PDF (Dzial + Angielski + Kapitan)
cd /d "%~dp0"

echo ========================================
echo   Audyt PDF: plumber + konsensus 3x
echo   Conservative: AUTO_OK tylko PDF==DB==3/3
echo ========================================
echo.
echo 1. Pilot dry-run (limit 50) + porownanie z konsensusem
echo 2. Pilot dry-run (limit 20)
echo 3. Pelny audyt (raport JSONL + CSV, bez zapisu OK)
echo 4. Zastosuj AUDIT_OK z JSONL (szybko, bez API)
echo 5. Zastosuj AUTO_OK (--apply-ok, limit 100)
echo 6. Zastosuj AUTO_OK (--apply-ok, wszystkie pending)
echo 7. Per kategoria: Dzial pokladowy
echo 8. Per kategoria: Angielski
echo 9. Per kategoria: Kapitan
echo 10. Wlasne argumenty audit_pdf.py
echo 0. Wyjscie
echo.
set /p choice="Wybierz opcje (0-10): "

if "%choice%"=="1" goto pilot50
if "%choice%"=="2" goto pilot20
if "%choice%"=="3" goto full
if "%choice%"=="4" goto applyjsonl
if "%choice%"=="5" goto apply100
if "%choice%"=="6" goto applyall
if "%choice%"=="7" goto dzial
if "%choice%"=="8" goto ang
if "%choice%"=="9" goto kap
if "%choice%"=="10" goto custom
if "%choice%"=="0" goto end
echo Nieprawidlowy wybor.
pause
goto end

:pilot50
python audit_pdf.py --dry-run --limit 50 --compare-consensus
pause
goto end

:pilot20
python audit_pdf.py --dry-run --limit 20
pause
goto end

:full
python audit_pdf.py --compare-consensus
pause
goto end

:applyjsonl
python audit_pdf.py --apply-from-jsonl
pause
goto end

:apply100
python audit_pdf.py --apply-ok --limit 100
pause
goto end

:applyall
python audit_pdf.py --apply-ok
pause
goto end

:dzial
python audit_pdf.py --kategoria "Dział pokładowy" --compare-consensus
pause
goto end

:ang
python audit_pdf.py --kategoria Angielski --compare-consensus
pause
goto end

:kap
python audit_pdf.py --kategoria "Kapitan żeglugi wielkiej" --compare-consensus
pause
goto end

:custom
set /p args="Argumenty audit_pdf.py: "
python audit_pdf.py %args%
pause
goto end

:end
