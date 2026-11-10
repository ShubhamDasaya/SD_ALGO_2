@echo off
title NIFTY 50 HYBRID OPTION BOT - PRODUCTION DESK
cd /d "%~dp0"

echo =================================================================
echo   [IN] NIFTY 50 HYBRID OPTION BOT - AUTO LAUNCHER
echo   Office Hours: 10:00 AM - 02:45 PM IST
echo   Web Dashboard: http://127.0.0.1:5000/
echo =================================================================

set "PY_CMD=c:\shubham\Python311\python.exe"
if not exist "%PY_CMD%" (
    set "PY_CMD=python"
)

echo [INFO] Starting Master Hybrid Engine and Web Dashboard...
%PY_CMD% main.py
pause
