@echo off
chcp 65001 >nul
title Konsensus 5 modeli (3/5) — pending
cd /d "%~dp0"

echo ========================================
echo   5 modeli, 3/5 zgodnych z baza -^> OK
echo   Pending: error / nieoznaczone
echo ========================================
echo.
echo 1. Pilot dry-run (limit 10)
echo 2. Batch limit 50 (zapis OK)
echo 3. Pelna kolejka pending (zapis OK)
echo 4. Wlasne argumenty
echo 0. Wyjscie
echo.
set /p choice="Wybierz (0-4): "

if "%choice%"=="1" python consensus_pending.py --dry-run --limit 10 --fresh
if "%choice%"=="2" python consensus_pending.py --limit 50 --fresh
if "%choice%"=="3" python consensus_pending.py --fresh
if "%choice%"=="4" goto custom
if "%choice%"=="0" goto end
pause
goto end

:custom
set /p args="Argumenty consensus_pending.py: "
python consensus_pending.py %args%
pause
goto end

:end
