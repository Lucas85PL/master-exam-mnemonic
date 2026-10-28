@echo off
rem Master Exam Mnemonic 2.0 - przebuduj aplikacje na Windows i uruchom.
cd /d "%~dp0app"
call "%~dp0app\Start-rebuild.bat"
exit /b %ERRORLEVEL%
