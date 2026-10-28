@echo off
chcp 65001 >nul
echo Budowa APK Master Exam Mnemonic 2.0...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0android\build-apk.ps1"
if errorlevel 1 (
  echo.
  echo Budowanie nie powiodlo sie.
  pause
  exit /b 1
)
echo.
echo Gotowe: %~dp0dist\Master-Exam-Mnemonic-2.0.apk
pause
