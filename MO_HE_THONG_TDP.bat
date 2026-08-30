@echo off
chcp 65001 >nul
cd /d "%~dp0tdp_system"
title THANH DAT PHAT - HE THONG VAN HANH
python server.py
if errorlevel 1 (
  echo.
  echo Khong khoi dong duoc he thong. Hay chup man hinh nay gui ky thuat.
  pause
)
