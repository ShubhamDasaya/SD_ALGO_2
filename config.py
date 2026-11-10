"""
===============================================================================
NIFTY 50 HYBRID OPTION BOT - CONFIGURATION (PRO-DESK)
===============================================================================
Hybrid Option Architecture:
- 10:00 AM to 14:45 PM Execution Window (Optimized for office schedule)
- Capital Structure: ₹51,235 Holdings (Pledged ~₹40k) + ₹10,000 Cash = ₹50,000 Total Capital
- Regime 1: Sideways/Chop  -> Hedged Credit Spread / Iron Condor (Theta Decay Income)
- Regime 2: Trend/Breakout -> ATM Option Buying (1:2 Risk-to-Reward Scalp)
- Pro-Desk Kill Switch: Max ₹900 daily loss limit | Auto Square-off at 14:45 PM
===============================================================================
"""

import os
from datetime import time

def _load_env_file():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        v = v.split("#")[0].strip()
                        os.environ[k.strip()] = v
        except Exception:
            pass

_load_env_file()

class Config:
    # -------------------------------------------------------------------------
    # 1. BROKER CREDENTIALS & ENVIRONMENT
    # -------------------------------------------------------------------------
    BROKER = os.getenv("ALGO_BROKER", "ANGEL_ONE")  # "ANGEL_ONE", "DHAN", "FYERS", "PAPER"
    ENVIRONMENT = os.getenv("TRADING_MODE", "PAPER_TRADING")  # "LIVE_TRADING" or "PAPER_TRADING"

    # Real Indian F&O Taxes & Charges (Angel One / NSE Compliant for Paper Trading)
    BROKERAGE_PER_ORDER = 20.0          # Angel One flat ₹20 per executed order
    STT_SELL_PERCENT = 0.001            # 0.1% on Option Sell Turnover
    NSE_TURNOVER_PERCENT = 0.0005       # 0.05% Exchange transaction charges
    GST_PERCENT = 0.18                  # 18% GST on (Brokerage + Exchange turnover)
    STAMP_DUTY_BUY_PERCENT = 0.00003    # 0.003% on Buy Turnover
    SEBI_TURNOVER_PERCENT = 0.000001    # ₹10 per crore turnover
    REALISTIC_SLIPPAGE_PTS = 1.0        # 1.0 pt market execution slippage

    # Angel One SmartAPI Credentials (https://smartapi.angelone.in/)
    ANGEL_API_KEY = os.getenv("API_KEY", "0X8BOWCU")
    ANGEL_CLIENT_CODE = os.getenv("CLIENT_CODE", "S867615")
    ANGEL_PIN = os.getenv("PIN", "8153")
    ANGEL_PASSWORD = os.getenv("PASSWORD", "sd6266936500")
    ANGEL_TOTP_SECRET = os.getenv("TOTP_SECRET", "QAJTI3YIFY6JZ2ZML4ROD2UPWQ")

    # DhanHQ Credentials (https://dhanhq.co)
    DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "YOUR_DHAN_CLIENT_ID")
    DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "YOUR_DHAN_ACCESS_TOKEN")

    # Fyers Credentials (https://myapi.fyers.in)
    FYERS_APP_ID = os.getenv("FYERS_APP_ID", "YOUR_FYERS_APP_ID")
    FYERS_ACCESS_TOKEN = os.getenv("FYERS_ACCESS_TOKEN", "YOUR_FYERS_ACCESS_TOKEN")

    # -------------------------------------------------------------------------
    # 2. CAPITAL & MARGIN CALIBRATION (User Portfolio Match)
    # -------------------------------------------------------------------------
    TOTAL_PORTFOLIO_CAPITAL = 50000.0   # ₹40,000 Pledged Margin + ₹10,000 Cash
    MAX_DEPLOYMENT_PER_TRADE = 35000.0  # Max margin used per trade (Safe SEBI 50:50 compliant)
    LOT_SIZE = 65                       # Standard NSE Nifty 50 Lot Size
    MAX_LOTS = 1                        # Conservative 1 Lot for steady compounding

    # -------------------------------------------------------------------------
    # 3. TRADING TIME WINDOWS (OFFICE SCHEDULE: 10:00 AM - 14:45 PM)
    # -------------------------------------------------------------------------
    # Exclude 09:15-10:00 opening traps and fake wicks; baseline established by 10:00
    SESSION_START_TIME     = time(10, 0)   # User arrives at office, bot begins scanning
    LAST_NEW_ENTRY_TIME    = time(14, 15)  # No new trades after 2:15 PM
    FORCE_EOD_SQUAREOFF    = time(14, 45)  # Strict auto square-off at 2:45 PM before broker charges

    # -------------------------------------------------------------------------
    # 4. STRATEGY MODE & REGIME THRESHOLDS
    # -------------------------------------------------------------------------
    STRIKE_SELECTION_MODE = "ATM"       # Options: "ATM" or "ITM_1"
    TARGET_DELTA = 0.52                 # Option Delta for ATM contracts
    # Operating Mode: "HYBRID" (Auto switches), "BUY_ONLY", "SELL_ONLY"
    DEFAULT_STRATEGY_MODE = "HYBRID"

    # Sideways / Range-Bound Criteria (Hedging & Option Selling):
    ORB_PERIOD_MINUTES = 45             # 09:15 to 10:00 establishes Morning Range (ORB)
    MAX_CHOP_RANGE_PTS = 85.0           # If Day Range <= 85 pts -> Chop/Sideways market
    RANGE_PCR_LOW = 0.85                # Neutral Option Chain PCR range
    RANGE_PCR_HIGH = 1.15
    MAX_INDIA_VIX_FOR_SELLING = 17.5    # News Shield: If VIX > 17.5, pause option selling automatically
    HIGH_IMPACT_NEWS_DEFENSE = True     # Skips trading during major macro news spikes

    # Hedged Option Selling Strike Offsets:
    SELLING_SHORT_OTM_PTS = 150         # Sell 100-150 pts OTM (High probability ~85%+)
    SELLING_WING_HEDGE_PTS = 250        # Buy 250 pts OTM wing for SEBI margin benefit & risk cap
    SELLING_TARGET_DECAY_PCT = 0.65     # Book profit when 65% of sold premium decays
    SELLING_STOP_LOSS_PCT = 0.80        # Hard SL: If short premium surges 80%, exit hedge

    # Trending Breakout Criteria (Option Buying):
    BREAKOUT_VOLUME_MULTIPLIER = 1.40   # Volume must be >= 1.4x 20-period average
    BUYING_TARGET_RR = 2.0              # Strict 1:2 Risk-to-Reward
    BUYING_MAX_SL_PTS = 7.5             # Max 7.5 pts option premium SL (65 lot * 7.5 = ~₹487.50, strictly within ₹500 loss cap)
    BUYING_BE_TRIGGER_PTS = 8.0         # Move SL to Cost+Buffer at +8 pts gain
    BUYING_THETA_TIMEOUT_MINS = 25      # Exit if momentum stalls for 25 mins (Theta shield)

    # -------------------------------------------------------------------------
    # 5. RISK MANAGEMENT & PRO-DESK KILL SWITCH
    # -------------------------------------------------------------------------
    MAX_TRADES_PER_DAY = 2              # Overtrading protection
    MAX_CONSECUTIVE_LOSSES = 2          # 2 losses = Halt trading immediately
    MAX_DAILY_LOSS_INR = 500.0          # Strict circuit breaker: Max ₹500 loss in a single day
    MAX_MONTHLY_LOSS_INR = 5000.0       # Strict portfolio circuit breaker: Max ₹5,000 loss in a month
    DAILY_PROFIT_GOAL_INR = 1200.0      # Once +₹1,200 is reached, protect capital
    SLIPPAGE_TOLERANCE_PTS = 1.0        # Limit order slippage safety buffer

    # -------------------------------------------------------------------------
    # 6. WEB DASHBOARD CONFIGURATION
    # -------------------------------------------------------------------------
    DASHBOARD_HOST = "127.0.0.1"
    DASHBOARD_PORT = 5000
    DASHBOARD_AUTO_OPEN_BROWSER = False # Avoid interrupting user work unless launched
