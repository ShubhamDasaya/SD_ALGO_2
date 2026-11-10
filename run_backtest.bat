@echo off
title NIFTY 50 HYBRID OPTION BOT - BACKTEST ENGINE
cd /d "%~dp0"

echo ====================================================================
echo      RUNNING NIFTY 50 HYBRID OPTION INSTITUTIONAL BACKTEST
echo      10:00 AM Entry - 02:45 PM Forced Exit - Real Indian Taxes & Decay
echo ====================================================================
echo.
set "PY_CMD=c:\shubham\Python311\python.exe"
if not exist "%PY_CMD%" (
    set "PY_CMD=python"
)

%PY_CMD% backtest.py
echo.
echo ====================================================================
echo Backtest Completed. Check nifty_hybrid_option_backtest.csv for trades.
echo ====================================================================
pause
