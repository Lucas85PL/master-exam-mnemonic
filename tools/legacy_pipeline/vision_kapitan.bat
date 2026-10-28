@echo off
chcp 65001 >nul
title Vision Kapitan Full-Page
cd /d "%~dp0"

echo ========================================
echo   Vision Kapitan (pelna strona PDF)
echo ========================================
echo.
echo 1. Test dry-run (limit 5)
echo 2. Uruchom wszystkie (error + niezweryfikowane)
echo 3. Wlasne argumenty
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
python vision_kapitan.py --dry-run --limit 5
pause
goto end

:run
python vision_kapitan.py
pause
goto end

:custom
set /p args="Argumenty vision_kapitan.py: "
python vision_kapitan.py %args%
pause
goto end

:end
