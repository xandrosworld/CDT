@echo off
chcp 65001 >nul
cd /d "%~dp0"
title THANH DAT PHAT - HE THONG VAN HANH
python server.py
if errorlevel 1 pause
