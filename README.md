# SD_ALGO_2 ⚡
### NIFTY 50 Institutional Hybrid Option Trading Bot & Pro Terminal

A high-frequency algorithmic options trading terminal engineered for Indian Markets (NSE NIFTY 50), connected directly to **Angel One SmartAPI** with sub-millisecond execution, zero-latency charts, and Sensibull-grade risk analytics.

---

## 🌟 Key Architecture & Highlights

- **📊 Zero-Delay Real-Time Charting:** Direct Angel One feed using TradingView Lightweight Charts (0s latency, 1M/3M/5M/15M timeframes, 9-EMA, 21-EMA, VWAP, ORB boundaries, and volume scale).
- **⛓️ Sensibull-Grade Option Chain:** Real-time visual Open Interest bars (Call vs Put), Greek delta calculations, ATM straddle pricing, Max Pain, and Put-Call Ratio (PCR).
- **💼 Live Portfolio & Holdings Desk:** Real Angel One equity share delivery holdings (LTP, Invested Value, Current Value, Unrealized P&L) and intraday option derivative positions.
- **🛡️ Strict Risk Shield & Armor:**
  - **₹500 Hard Daily Loss Cap** with automated circuit breaker halt.
  - **₹5,000 Monthly Loss Armor** to protect capital.
  - Max 2 trades/day limit with SEBI compliance checks.
  - Auto 14:45 PM intraday square-off.
- **🔄 Dual Trading Modes:** Real-time Paper Trading sandbox and Real Live Broker execution toggle.
- **🚀 Multi-Threaded Asynchronous Architecture:** Zero-blocking HTTP terminal serving telemetry in 3-4ms.

---

## 🚀 Quick Start Guide

### 1. Clone & Setup
```bash
git clone https://github.com/ShubhamDasaya/SD_ALGO_2.git
cd SD_ALGO_2
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```
*(Or install core libraries: `pip install smartapi-python pyotp pandas yfinance requests`)*

### 3. Configure Credentials
Copy `config.env.example` to `config.env` and enter your Angel One SmartAPI credentials:
```bash
cp config.env.example config.env
```

### 4. Run Bot & Launch Dashboard
```bash
python main.py
```
Open your browser at: **http://127.0.0.1:5000/**

---

## ⚖️ Disclaimer
*This repository is intended for quantitative research, backtesting, and educational purposes. Trading financial derivatives involves substantial risk of loss. Always test thoroughly in Paper Trading mode before deploying real capital.*
