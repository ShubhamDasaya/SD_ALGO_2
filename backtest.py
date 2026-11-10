"""
===============================================================================
NIFTY 50 HYBRID OPTION BOT - COMPREHENSIVE HISTORICAL BACKTEST
===============================================================================
Executes rigorous backtest of the Dual-Regime Hybrid Strategy:
1. User Schedule: 10:00 AM Entry Start -> 14:45 PM Forced Intraday Exit.
2. Capital Model: ₹50,000 Total Capital (₹40,000 Pledged Margin + ₹10,000 Cash).
3. Strategy Regimes:
   - Sideways Chop (65-70% of days): Hedged Option Selling (Theta Decay Accretion)
   - Trending Breakout (30-35% of days): ATM Option Buying (1:2 R:R + Break-Even Armor)
4. Realistic Friction:
   - Full Indian Transaction Charges (₹55 per trade: Angel One ₹20+₹20, STT, GST, Stamp Duty)
   - 1.0 Point Slippage on options execution
   - Real-time Theta decay modeling
   - Hard Pro-Desk Kill Switch: ₹900 Max Daily Loss
===============================================================================
"""

import os
import sys
from datetime import datetime, time
import pandas as pd
import numpy as np
import yfinance as yf

from config import Config
from strategy.liquidity_engine import LiquidityEngine

class HybridOptionBacktester:
    def __init__(
        self,
        starting_capital: float = Config.TOTAL_PORTFOLIO_CAPITAL,
        lot_size: int = Config.LOT_SIZE,
        brokerage_per_trade: float = 55.0,  # Indian exchange STT + GST + Brokerage
        slippage_pts: float = 1.0,          # Conservative slippage
        daily_loss_limit: float = Config.MAX_DAILY_LOSS_INR
    ):
        self.starting_capital = starting_capital
        self.capital = starting_capital
        self.lot_size = lot_size
        self.brokerage = brokerage_per_trade
        self.slippage = slippage_pts
        self.daily_loss_limit = daily_loss_limit
        self.engine = LiquidityEngine()

    def fetch_historical_data(self) -> pd.DataFrame:
        """Fetches maximum available 5-minute intraday Nifty data (~60 days)."""
        print("[*] Fetching real NIFTY 50 intraday 5-min candles from market feed...")
        df = yf.download("^NSEI", period="60d", interval="5m", progress=False)

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]

        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()

        # Localize timezone to Asia/Kolkata
        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC").tz_convert("Asia/Kolkata")
        else:
            df.index = df.index.tz_convert("Asia/Kolkata")

        df = df.between_time("09:15", "15:25")
        print(f"[+] Loaded {len(df)} 5-minute candles across historical sessions.")
        return df

    def run(self):
        df = self.fetch_historical_data()
        days = df.groupby(df.index.date)
        trades = []

        peak_capital = self.starting_capital
        max_drawdown = 0.0

        for date, day_df in days:
            if len(day_df) < 20:
                continue

            day_open = float(day_df.iloc[0]["Open"])
            self.engine.set_day_open(day_open)

            # Establish 09:15 - 10:00 AM Morning Range
            morning_df = day_df.between_time("09:15", "09:55")
            if not morning_df.empty:
                for _, row in morning_df.iterrows():
                    self.engine.record_morning_candle(row["High"], row["Low"], row["Volume"])

            # Trading begins strictly at 10:00 AM
            trading_df = day_df.between_time("10:00", "15:15")
            open_pos = None
            daily_realized = 0.0
            trades_today = 0
            kill_switch_active = False

            for idx, row in trading_df.iterrows():
                cur_t = idx.time()
                candle_dict = {
                    "timestamp": idx,
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": float(row["Volume"])
                }

                # -------------------------------------------------------------
                # 1. MONITOR OPEN ACTIVE POSITION
                # -------------------------------------------------------------
                if open_pos is not None:
                    open_pos["bars"] += 1
                    exit_reason = None
                    exit_pts = 0.0

                    # Forced 14:45 PM Exit
                    if cur_t >= Config.FORCE_EOD_SQUAREOFF:
                        exit_reason = "FORCE_1445_EOD"
                        if open_pos["type"] == "HEDGED_SELLING":
                            exit_pts = open_pos["current_decay_pts"]
                        else:
                            spot_diff = row["Close"] - open_pos["spot_entry"]
                            if open_pos["type"] == "PE_BUY":
                                spot_diff = -spot_diff
                            exit_pts = (spot_diff * 0.52) - (open_pos["bars"] * 0.20)

                    # Monitor Option Buying Trade
                    elif open_pos["type"] in ["CE_BUY", "PE_BUY"]:
                        decay = open_pos["bars"] * 0.20  # ~0.20 pt decay per 5-min bar
                        if open_pos["type"] == "CE_BUY":
                            best_spot = row["High"] - open_pos["spot_entry"]
                            cur_spot = row["Close"] - open_pos["spot_entry"]
                            worst_spot = open_pos["spot_entry"] - row["Low"]
                        else:
                            best_spot = open_pos["spot_entry"] - row["Low"]
                            cur_spot = open_pos["spot_entry"] - row["Close"]
                            worst_spot = row["High"] - open_pos["spot_entry"]

                        best_opt = (best_spot * 0.52) - decay
                        worst_opt = (worst_spot * 0.52) + decay
                        cur_opt = (cur_spot * 0.52) - decay

                        # Auto Break-Even Trailing at +10 pts
                        if not open_pos["be_active"] and best_opt >= 10.0:
                            open_pos["be_active"] = True
                            open_pos["sl_pts"] = -0.5  # Lock cost

                        # Target Hit (+24 pts)
                        if best_opt >= open_pos["target_pts"]:
                            exit_reason = "TARGET_HIT"
                            exit_pts = open_pos["target_pts"] - self.slippage
                        # Break-Even Exit
                        elif open_pos["be_active"] and cur_opt <= open_pos["sl_pts"]:
                            exit_reason = "BREAK_EVEN"
                            exit_pts = open_pos["sl_pts"] - self.slippage
                        # Stop Loss Hit (-12 pts)
                        elif worst_opt >= abs(open_pos["sl_pts"]):
                            exit_reason = "STOP_LOSS"
                            exit_pts = -abs(open_pos["sl_pts"]) - self.slippage
                        # Theta Timeout (25 mins = 5 bars)
                        elif open_pos["bars"] >= 5:
                            exit_reason = "THETA_TIMEOUT"
                            exit_pts = cur_opt - self.slippage

                    # Monitor Hedged Option Selling Trade (Iron Condor)
                    elif open_pos["type"] == "HEDGED_SELLING":
                        # Accrete theta decay (+0.35 pts per 5m bar during range)
                        decay_earned = min(open_pos["bars"] * 0.35, 18.0)
                        
                        # Check spot adverse move beyond short wings
                        spot_breach = 0.0
                        if row["High"] > open_pos["short_ce"]:
                            spot_breach = (row["High"] - open_pos["short_ce"]) * 0.35
                        elif row["Low"] < open_pos["short_pe"]:
                            spot_breach = (open_pos["short_pe"] - row["Low"]) * 0.35

                        current_net_decay = decay_earned - spot_breach
                        open_pos["current_decay_pts"] = current_net_decay

                        # Target Decay Hit (+16 pts ~ ₹1,040)
                        if current_net_decay >= 16.0:
                            exit_reason = "THETA_TARGET"
                            exit_pts = 16.0 - self.slippage
                        # Safety Stop Loss (-13 pts ~ ₹845)
                        elif current_net_decay <= -13.0:
                            exit_reason = "SHORT_BREACH_SL"
                            exit_pts = -13.0 - self.slippage

                    if exit_reason:
                        gross_pnl = exit_pts * self.lot_size
                        net_pnl = gross_pnl - self.brokerage
                        daily_realized += net_pnl
                        self.capital += net_pnl

                        peak_capital = max(peak_capital, self.capital)
                        max_drawdown = max(max_drawdown, peak_capital - self.capital)

                        trades.append({
                            "date": str(date),
                            "entry_time": open_pos["entry_time"].strftime("%H:%M"),
                            "exit_time": idx.strftime("%H:%M"),
                            "strategy": open_pos["strategy"],
                            "type": open_pos["type"],
                            "opt_pts": round(exit_pts, 2),
                            "gross_pnl": round(gross_pnl, 2),
                            "net_pnl": round(net_pnl, 2),
                            "capital": round(self.capital, 2),
                            "reason": exit_reason
                        })

                        if daily_realized <= -self.daily_loss_limit:
                            kill_switch_active = True

                        open_pos = None
                        continue

                # -------------------------------------------------------------
                # 2. SCAN FOR NEW SIGNALS (10:00 AM - 14:15 PM)
                # -------------------------------------------------------------
                if open_pos is not None or kill_switch_active or trades_today >= Config.MAX_TRADES_PER_DAY:
                    continue

                if cur_t > Config.LAST_NEW_ENTRY_TIME:
                    continue

                signal = self.engine.process_ltf_candle(candle_dict, strategy_mode=Config.DEFAULT_STRATEGY_MODE)
                if not signal:
                    continue

                trades_today += 1

                # Hedged Selling Signal
                if signal["signal"] == "HEDGED_SELLING":
                    open_pos = {
                        "entry_time": idx,
                        "type": "HEDGED_SELLING",
                        "strategy": "IRON_CONDOR_SELL",
                        "short_ce": signal["short_ce_strike"],
                        "short_pe": signal["short_pe_strike"],
                        "spot_entry": signal["spot_entry"],
                        "current_decay_pts": 0.0,
                        "bars": 0
                    }

                # Option Buying Signal
                elif signal["signal"] in ["BUY_CE", "BUY_PE"]:
                    opt_type = "CE_BUY" if signal["signal"] == "BUY_CE" else "PE_BUY"
                    open_pos = {
                        "entry_time": idx,
                        "type": opt_type,
                        "strategy": signal["strategy"],
                        "spot_entry": signal["spot_entry"],
                        "target_pts": signal.get("target_pts", 24.0),
                        "sl_pts": -signal.get("sl_pts", 12.0),
                        "be_active": False,
                        "bars": 0
                    }

        self.print_performance_report(trades, peak_capital, max_drawdown)

    def print_performance_report(self, trades: list, peak_capital: float, max_drawdown: float):
        total = len(trades)
        if total == 0:
            print("[-] No trades executed.")
            return

        wins = [t for t in trades if t["net_pnl"] > 0]
        losses = [t for t in trades if t["net_pnl"] < 0]
        bes = [t for t in trades if t["reason"] == "BREAK_EVEN"]

        selling_trades = [t for t in trades if "SELL" in t["strategy"]]
        buying_trades = [t for t in trades if "BUY" in t["type"]]

        gross_wins = sum(t["net_pnl"] for t in wins)
        gross_losses = abs(sum(t["net_pnl"] for t in losses))
        profit_factor = (gross_wins / gross_losses) if gross_losses > 0 else 999.0

        win_rate = (len(wins) / total) * 100.0
        net_profit = self.capital - self.starting_capital
        pct_return = (net_profit / self.starting_capital) * 100.0
        expectancy = net_profit / total

        print("\n" + "=" * 78)
        print("  🇮🇳 NIFTY 50 HYBRID OPTION BOT - RIGOROUS INSTITUTIONAL AUDIT 🇮🇳")
        print("=" * 78)
        print(f"  Starting Capital             : ₹{self.starting_capital:,.2f}")
        print(f"  Final Capital (Post-Taxes)   : ₹{self.capital:,.2f}")
        print(f"  Total Net Return             : ₹{net_profit:+,.2f} ({pct_return:+.2f}%)")
        print(f"  Peak Capital Reached         : ₹{peak_capital:,.2f}")
        print(f"  Max Drawdown                 : ₹{max_drawdown:,.2f} ({(max_drawdown/peak_capital)*100:.1f}%)")
        print(f"  Profit Factor                : {profit_factor:.2f}")
        print(f"  Expectancy Per Trade         : ₹{expectancy:+,.2f}")
        print("-" * 78)
        print(f"  Total Trades Triggered       : {total}")
        print(f"  Hedged Selling Trades (Chop) : {len(selling_trades)} ({len([t for t in selling_trades if t['net_pnl']>0])} Wins)")
        print(f"  Option Buying Trades (Trend) : {len(buying_trades)} ({len([t for t in buying_trades if t['net_pnl']>0])} Wins)")
        print(f"  Winning Trades               : {len(wins)} ({win_rate:.1f}% Win Rate)")
        print(f"  Losing Trades                : {len(losses)}")
        print(f"  Break-Even Shield Exits      : {len(bes)}")
        print("=" * 78)

        print("\nSAMPLE RECENT TRADES:")
        print("-" * 78)
        for t in trades[-10:]:
            print(f"  {t['date']} {t['entry_time']}-{t['exit_time']} | {t['type']:<15} | Opt: {t['opt_pts']:+5.1f} pts | Net: ₹{t['net_pnl']:+8.2f} | {t['reason']}")
        print("=" * 78)

        csv_file = os.path.join(os.path.dirname(__file__), "nifty_hybrid_option_backtest.csv")
        pd.DataFrame(trades).to_csv(csv_file, index=False)
        print(f"[+] Full trade report saved to: {csv_file}\n")


if __name__ == "__main__":
    backtester = HybridOptionBacktester()
    backtester.run()
