@echo off
chcp 65001 >nul
setlocal
set "APP_DIR=%~dp0"
echo Przebudowa Release i uruchomienie...
echo Zamykam dzialajaca aplikacje (jesli jest)...
taskkill /IM memonic_app.exe /F >nul 2>&1
timeout /t 1 /nobreak >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%APP_DIR%run.ps1" -Action build-windows
if errorlevel 1 (
  echo Budowanie nie powiodlo sie.
  pause
  exit /b 1
)
call "%APP_DIR%Start.bat"
