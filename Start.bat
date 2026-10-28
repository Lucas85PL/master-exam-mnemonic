@echo off
rem Master Exam Mnemonic 2.0 - uruchom aplikacje na Windows (jesli brak builda, zbuduje ja).
cd /d "%~dp0app"
call "%~dp0app\Start.bat"
exit /b %ERRORLEVEL%
