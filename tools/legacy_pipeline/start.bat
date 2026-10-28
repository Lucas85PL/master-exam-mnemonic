@echo off
chcp 65001 >nul
title Question Database
cd /d "%~dp0"

echo ========================================
echo   Przegladarka Pytan Egzaminacyjnych
echo ========================================
echo.
echo 1. Uruchom GUI (przegladanie / edycja)
echo 2. Przebuduj baze z PDF i colpkg
echo 3. Wyjscie
echo.
set /p choice="Wybierz opcje (1-3): "

if "%choice%"=="1" goto gui
if "%choice%"=="2" goto build
if "%choice%"=="3" goto end
echo Nieprawidlowy wybor.
pause
goto end

:gui
echo.
echo Uruchamianie GUI...
python gui.py
goto end

:build
echo.
echo Przebudowywanie bazy pytan...
python build_db.py
echo.
pause
goto end

:end
