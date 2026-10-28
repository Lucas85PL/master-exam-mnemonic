@echo off
chcp 65001 >nul
setlocal EnableExtensions

set "APP_DIR=%~dp0"
set "RUN_DIR=%APP_DIR%build\windows\x64\runner\Release"
set "EXE=%RUN_DIR%\memonic_app.exe"

if not exist "%EXE%" (
  echo [Start] Brak buildu Release. Buduje aplikacje...
  echo.
  powershell -NoProfile -ExecutionPolicy Bypass -File "%APP_DIR%run.ps1" -Action build-windows
  if errorlevel 1 goto error
)

if not exist "%EXE%" (
  echo [Start] Nadal brak pliku exe.
  goto error
)

echo [Start] Uruchamiam memonic_app...
cd /d "%RUN_DIR%"
start "" "%EXE%"
exit /b 0

:error
echo.
echo [Start] Nie udalo sie uruchomic.
echo W PowerShell: cd "%APP_DIR%"
echo   .\run.ps1 -Action run-windows
echo.
pause
exit /b 1
