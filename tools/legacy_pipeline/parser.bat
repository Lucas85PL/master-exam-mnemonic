@echo off
chcp 65001 >nul
title Fix PDF - poprawa pytan
cd /d "%~dp0"

echo Uruchamianie Fix PDF Tool...
python fix_pdf.py
pause
