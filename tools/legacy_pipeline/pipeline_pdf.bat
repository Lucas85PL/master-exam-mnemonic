@echo off
chcp 65001 >nul
title Pipeline PDF (Dzial + Angielski)
cd /d "%~dp0"

echo ========================================
echo   Pipeline PDF: Vision + Konsensus
echo   Dzial pokladowy + angielski
echo ========================================
echo.
echo 1. Test Vision dry-run (limit 5)
echo 2. Test Vision (limit 10)
echo 3. Test pelny pipeline dry-run (limit 5)
echo 4. Test pelny pipeline (limit 10)
echo 5. Pelny pipeline (wszystkie pending)
echo 6. Tylko konsensus (limit 20)
echo 7. Wlasne argumenty
echo 8. Wyjscie
echo.
set /p choice="Wybierz opcje (1-8): "

if "%choice%"=="1" goto vdry
if "%choice%"=="2" goto v10
if "%choice%"=="3" goto alldry
if "%choice%"=="4" goto all10
if "%choice%"=="5" goto all
if "%choice%"=="6" goto con
if "%choice%"=="7" goto custom
if "%choice%"=="8" goto end
echo Nieprawidlowy wybor.
pause
goto end

:vdry
python pipeline_pdf.py --phase vision --dry-run --limit 5
pause
goto end

:v10
python pipeline_pdf.py --phase vision --limit 10
pause
goto end

:alldry
python pipeline_pdf.py --phase all --dry-run --limit 5
pause
goto end

:all10
python pipeline_pdf.py --phase all --limit 10
pause
goto end

:all
python pipeline_pdf.py --phase all
pause
goto end

:con
python pipeline_pdf.py --phase consensus --limit 20
pause
goto end

:custom
set /p args="Argumenty pipeline_pdf.py: "
python pipeline_pdf.py %args%
pause
goto end

:end
