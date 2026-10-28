@echo off
chcp 65001 >nul
title Database Review Tool
cd /d "%~dp0"

echo Uruchamianie Review Tool...
python review.py
pause
