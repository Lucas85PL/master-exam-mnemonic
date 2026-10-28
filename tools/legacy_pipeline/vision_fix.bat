@echo off
chcp 65001 >nul
title Vision Auto-Fix
cd /d "%~dp0"

echo ========================================
echo   Vision Auto-Fix (OpenRouter)
echo ========================================
echo.
echo 1. Test (dry-run, limit 5)
echo 2. Uruchom na wszystkich error
echo 3. Wlasne argumenty (np. --id 1234)
echo 4. Wyjscie
echo.
set /p choice="Wybierz opcje (1-4): "

if "%choice%"=="1" goto dry
if "%choice%"=="2" goto run
if "%choice%"=="3" goto custom
if "%choice%"=="4" goto end
echo Nieprawidlowy wybor.
pause
goto end

:dry
python vision_fix.py --dry-run --limit 5
pause
goto end

:run
python vision_fix.py
pause
goto end

:custom
set /p args="Argumenty vision_fix.py: "
python vision_fix.py %args%
pause
goto end

:end
