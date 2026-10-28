@echo off
chcp 65001 >nul
title Kapitan Consensus (3 modele)
cd /d "%~dp0"

echo ========================================
echo   Kapitan Consensus (auto-OK)
echo ========================================
echo.
echo 1. Test dry-run (limit 5)
echo 2. Test limit 20 (z UPDATE)
echo 3. Pelny batch
echo 4. Wlasne argumenty
echo 5. Wyjscie
echo.
set /p choice="Wybierz opcje (1-5): "

if "%choice%"=="1" goto dry
if "%choice%"=="2" goto limit20
if "%choice%"=="3" goto run
if "%choice%"=="4" goto custom
if "%choice%"=="5" goto end
echo Nieprawidlowy wybor.
pause
goto end

:dry
python kapitan_consensus.py --dry-run --limit 5
pause
goto end

:limit20
python kapitan_consensus.py --limit 20
pause
goto end

:run
python kapitan_consensus.py
pause
goto end

:custom
set /p args="Argumenty kapitan_consensus.py: "
python kapitan_consensus.py %args%
pause
goto end

:end
