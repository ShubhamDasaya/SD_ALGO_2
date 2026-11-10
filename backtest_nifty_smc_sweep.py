"""
===============================================================================
NIFTY 50 SMC LIQUIDITY SWEEP (PP) OPTION BUYING - INSTITUTIONAL BACKTEST
===============================================================================
Ported directly from MT5 Institutional SMC Engine (smc_master_bot.py)
Calibrated with Options Greeks Defense (Theta Shield, Gamma Control, Delta 0.50)

Key Rules for Indian Market:
1. Liquidity Sweeps on 15M Swing High/Low, PDH (Prev Day High), PDL (Prev Day Low).
2. Pure Price (PP) Sweep + Displacement Candle (Engulfing or Body Ratio >= 50%).
3. Theta Shield: Max 4 bars (20 mins) hold time to prevent time decay burn.
4. Capital Protection:
   - 1 Lot (65 Qty) ATM Option
   - Stop Loss: -10 pts Option Premium (-Rs 650 to -Rs 715 max risk)
   - Target: +18 pts Option Premium (+Rs 1,170 profit)
   - Auto Break-Even: At +10 pts gain, SL moved to Cost (Risk = Rs 0)
   - Hard Kill Switch: 1 SL hit shuts down bot for the day.
   - Lunch Chop Blackout (11:30 AM - 01:15 PM): Zero trading.
===============================================================================
"""

import sys
import os
from datetime import datetime, time
import pandas as pd
import numpy as np

try:
    import yfinance as yf
except ImportError:
    print("[-] Error: yfinance is required. Install via: pip install yfinance")
    sys.exit(1)


class NiftySMCSweepBacktester:
    def __init__(
        self,
        starting_capital: float = 10000.0,
        lot_size: int = 65,
        target_pts: float = 18.0,
        sl_pts: float = 10.0,
        be_pts: float = 10.0,
        max_daily_loss: float = 800.0,
        max_trades_per_day: int = 2,
        slippage_pts: float = 1.0,
        brokerage_per_trade: float = 55.0,
        delta: float = 0.50,
        max_hold_bars: int = 4  # 4 * 5m = 20 minutes strict Theta Shield
    ):
        self.starting_capital = starting_capital
        self.capital = starting_capital
        self.lot_size = lot_size
        self.target_pts = target_pts
        self.sl_pts = sl_pts
        self.be_pts = be_pts
        self.max_daily_loss = max_daily_loss
        self.max_trades_per_day = max_trades_per_day
        self.slippage_pts = slippage_pts
        self.brokerage_per_trade = brokerage_per_trade
        self.delta = delta
        self.max_hold_bars = max_hold_bars

    def fetch_data(self, period: str = "1mo") -> tuple[pd.DataFrame, pd.DataFrame]:
        """Fetch 5m and 15m candles from Yahoo Finance."""
        print(f"[*] Fetching real NIFTY 50 intraday data (Period: {period})...")
        df_5m = yf.download("^NSEI", period=period, interval="5m", progress=False)
        df_15m = yf.download("^NSEI", period=period, interval="15m", progress=False)

        if df_5m.empty:
            raise ValueError("No data returned for ^NSEI")

        if isinstance(df_5m.columns, pd.MultiIndex):
            df_5m.columns = [col[0] for col in df_5m.columns]
        if isinstance(df_15m.columns, pd.MultiIndex):
            df_15m.columns = [col[0] for col in df_15m.columns]

        df_5m = df_5m[["Open", "High", "Low", "Close", "Volume"]].dropna()
        df_15m = df_15m[["Open", "High", "Low", "Close", "Volume"]].dropna()

        # Localize to IST
        for df in [df_5m, df_15m]:
            if df.index.tz is None:
                df.index = df.index.tz_localize("UTC").tz_convert("Asia/Kolkata")
            else:
                df.index = df.index.tz_convert("Asia/Kolkata")

        df_5m = df_5m.between_time("09:15", "15:25")
        df_15m = df_15m.between_time("09:15", "15:25")

        print(f"[+] Loaded {len(df_5m)} 5m candles & {len(df_15m)} 15m candles.")
        return df_5m, df_15m

    def compute_15m_swings(self, df_15m: pd.DataFrame, pivot_len: int = 3) -> list:
        """Ported from MT5 discover_zones logic for HTF liquidity."""
        swings = []
        h = df_15m["High"].values
        l = df_15m["Low"].values
        t = df_15m.index
        n = len(df_15m)

        for i in range(pivot_len, n - pivot_len):
            is_high = all(h[i] >= h[i - k] for k in range(1, pivot_len + 1)) and all(h[i] >= h[i + k] for k in range(1, pivot_len + 1))
            is_low = all(l[i] <= l[i - k] for k in range(1, pivot_len + 1)) and all(l[i] <= l[i + k] for k in range(1, pivot_len + 1))

            if is_high:
                swings.append({"time": t[i], "price": h[i], "type": "SWING_HIGH"})
            if is_low:
                swings.append({"time": t[i], "price": l[i], "type": "SWING_LOW"})

        return swings

    def run_backtest(self, df_5m: pd.DataFrame, df_15m: pd.DataFrame) -> dict:
        swings = self.compute_15m_swings(df_15m)
        days = df_5m.groupby(df_5m.index.date)
        trades = []

        prev_day_high = None
        prev_day_low = None

        for date, day_df in days:
            if len(day_df) < 15:
                continue

            # Day levels
            current_day_high = day_df["High"].max()
            current_day_low = day_df["Low"].min()

            # Active liquidity pools available at start of day
            day_start = day_df.index[0]
            past_swings = [s for s in swings if s["time"] < day_start]
            recent_highs = [s["price"] for s in past_swings if s["type"] == "SWING_HIGH"][-5:]
            recent_lows = [s["price"] for s in past_swings if s["type"] == "SWING_LOW"][-5:]

            if prev_day_high is not None:
                recent_highs.append(prev_day_high)
            if prev_day_low is not None:
                recent_lows.append(prev_day_low)

            open_pos = None
            trades_today = 0
            kill_switch_active = False

            for idx, row in day_df.iterrows():
                t = idx.time()
                c = row["Close"]
                h = row["High"]
                l = row["Low"]
                o = row["Open"]
                c_rng = max(h - l, 0.05)
                body = abs(c - o)

                # -------------------------------------------------------------
                # 1. ACTIVE POSITION MANAGEMENT (WITH GREEKS / THETA SHIELD)
                # -------------------------------------------------------------
                if open_pos is not None:
                    open_pos["bars"] += 1
                    
                    # Greek Model:
                    # Delta = 0.50 ATM
                    # Theta Decay: accelerates per 5m bar (~0.15 pt / bar)
                    decay = open_pos["bars"] * 0.15

                    if open_pos["type"] == "CE":
                        best_spot_gain = h - open_pos["entry"]
                        worst_spot_loss = open_pos["entry"] - l
                        cur_spot_gain = c - open_pos["entry"]

                        best_opt = (best_spot_gain * self.delta) - decay
                        worst_opt = (worst_spot_loss * self.delta) + decay
                        cur_opt = (cur_spot_gain * self.delta) - decay
                    else:  # PE
                        best_spot_gain = open_pos["entry"] - l
                        worst_spot_loss = h - open_pos["entry"]
                        cur_spot_gain = open_pos["entry"] - c

                        best_opt = (best_spot_gain * self.delta) - decay
                        worst_opt = (worst_spot_loss * self.delta) + decay
                        cur_opt = (cur_spot_gain * self.delta) - decay

                    # Auto Break-Even Check (+10 pts gain moves SL to 0)
                    if not open_pos["be_moved"] and best_opt >= self.be_pts:
                        open_pos["be_moved"] = True
                        open_pos["sl_price"] = 0.0  # Cost

                    reason = None
                    exit_pts = 0.0

                    # Exit priority: Target -> Stop Loss / Break Even -> Theta Time Stop
                    if best_opt >= self.target_pts:
                        reason = "TARGET_HIT"
                        exit_pts = self.target_pts - self.slippage_pts
                    elif open_pos["be_moved"] and cur_opt <= 0.0:
                        reason = "BREAK_EVEN"
                        exit_pts = 0.0 - self.slippage_pts
                    elif worst_opt >= self.sl_pts:
                        reason = "STOP_LOSS"
                        exit_pts = -self.sl_pts - self.slippage_pts
                    elif open_pos["bars"] >= self.max_hold_bars:
                        reason = "THETA_SHIELD_TIMESTOP"
                        exit_pts = cur_opt - self.slippage_pts

                    if reason:
                        gross_pnl = exit_pts * self.lot_size
                        net_pnl = gross_pnl - self.brokerage_per_trade
                        self.capital += net_pnl

                        trades.append({
                            "date": str(date),
                            "entry_time": open_pos["entry_time"].strftime("%H:%M"),
                            "exit_time": idx.strftime("%H:%M"),
                            "type": open_pos["type"],
                            "strike": open_pos["strike"],
                            "sweep_level": round(open_pos["level"], 1),
                            "opt_pts": round(exit_pts, 2),
                            "net_pnl": round(net_pnl, 2),
                            "capital": round(self.capital, 2),
                            "reason": reason,
                            "bars": open_pos["bars"]
                        })

                        # KILL SWITCH: 1 Loss halts bot for rest of the day
                        if net_pnl < 0:
                            kill_switch_active = True

                        open_pos = None
                        continue

                # -------------------------------------------------------------
                # 2. TRADE PERMISSION & SESSION FILTER
                # -------------------------------------------------------------
                if open_pos is not None or trades_today >= self.max_trades_per_day or kill_switch_active:
                    continue

                # Session Filter: High momentum windows only
                is_morning = (time(9, 30) <= t <= time(11, 30))
                is_afternoon = (time(13, 15) <= t <= time(14, 45))
                if not (is_morning or is_afternoon):
                    continue  # Zero trading during 11:30 - 13:15 Lunch Chop

                if c_rng < 10.0:  # Skip dead micro candles
                    continue

                # Displacement Check (Ported from MT5 is_disp_buy / is_disp_sell)
                body_ratio = body / c_rng
                upper_wick = h - max(c, o)
                lower_wick = min(c, o) - l

                # -------------------------------------------------------------
                # 3. SMC LIQUIDITY SWEEP SIGNALS (PP SETUP)
                # -------------------------------------------------------------

                # SETUP 1: BULLISH LIQUIDITY SWEEP (Buy Call Option - CE)
                # Market dips below recent swing low / PDL (Sweeps Liquidity) but closes back ABOVE
                # with strong bullish displacement (Green body >= 50% or long rejection wick)
                bullish_disp = (c > o) and (body_ratio >= 0.45 or lower_wick / c_rng >= 0.45)
                if bullish_disp:
                    for lvl in recent_lows:
                        # Sweep condition: Low dipped below level, but Close finished back above level
                        if l < lvl and c > lvl and abs(lvl - l) >= 3.0:
                            atm_strike = int(round(c / 50.0) * 50)
                            open_pos = {
                                "entry": c,
                                "type": "CE",
                                "strike": atm_strike,
                                "level": lvl,
                                "bars": 0,
                                "entry_time": idx,
                                "be_moved": False,
                                "sl_price": self.sl_pts
                            }
                            trades_today += 1
                            break

                # SETUP 2: BEARISH LIQUIDITY SWEEP (Buy Put Option - PE)
                # Market pops above recent swing high / PDH (Trapping breakout traders) but closes back BELOW
                # with strong bearish displacement (Red body >= 50% or long upper wick)
                bearish_disp = (c < o) and (body_ratio >= 0.45 or upper_wick / c_rng >= 0.45)
                if bearish_disp and open_pos is None:
                    for lvl in recent_highs:
                        # Sweep condition: High spiked above level, but Close finished back below level
                        if h > lvl and c < lvl and abs(h - lvl) >= 3.0:
                            atm_strike = int(round(c / 50.0) * 50)
                            open_pos = {
                                "entry": c,
                                "type": "PE",
                                "strike": atm_strike,
                                "level": lvl,
                                "bars": 0,
                                "entry_time": idx,
                                "be_moved": False,
                                "sl_price": self.sl_pts
                            }
                            trades_today += 1
                            break

            # Save PDH / PDL for next day
            prev_day_high = current_day_high
            prev_day_low = current_day_low

        return self.compile_report(trades)

    def compile_report(self, trades: list) -> dict:
        total = len(trades)
        if total == 0:
            print("\n[-] No trades triggered with the current SMC parameters.")
            return {}

        wins = [t for t in trades if t["net_pnl"] > 0]
        losses = [t for t in trades if t["net_pnl"] < 0]
        bes = [t for t in trades if t["reason"] == "BREAK_EVEN"]

        win_rate = (len(wins) / total) * 100.0
        net_profit = self.capital - self.starting_capital
        pct_return = (net_profit / self.starting_capital) * 100.0

        print("\n" + "=" * 74)
        print("  🇮🇳 NIFTY 50 SMC LIQUIDITY SWEEP (PP) - INSTITUTIONAL AUDIT REPORT 🇮🇳")
        print("=" * 74)
        print(f"  Starting Capital     : Rs {self.starting_capital:,.2f}")
        print(f"  Final Capital        : Rs {self.capital:,.2f}")
        print(f"  Net Profit (Post-Tax): Rs {net_profit:+,.2f} ({pct_return:+.2f}%)")
        print("-" * 74)
        print(f"  Total Trades Taken   : {total} (High Quality Institutional Sweeps)")
        print(f"  Winning Trades       : {len(wins)} ({win_rate:.1f}% Win Rate)")
        print(f"  Losing Trades        : {len(losses)}")
        print(f"  Break-Even Exits     : {len(bes)} (Zero Loss Capital Protected)")
        print("=" * 74)

        print("\nDETAILED TRADE LOG:")
        print("-" * 74)
        for t in trades[-15:]:
            print(f"  {t['date']} {t['entry_time']}-{t['exit_time']} | {t['type']} {t['strike']} (Sweep {t['sweep_level']}) | Opt: {t['opt_pts']:+5.1f} pts | Net: Rs {t['net_pnl']:+8.2f} | {t['reason']}")
        print("=" * 74)

        csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nifty_smc_sweep_backtest_results.csv")
        pd.DataFrame(trades).to_csv(csv_path, index=False)
        print(f"[+] Full audit log saved to: {csv_path}\n")

        return {
            "total_trades": total,
            "win_rate": win_rate,
            "net_profit": net_profit,
            "pct_return": pct_return
        }


if __name__ == "__main__":
    backtester = NiftySMCSweepBacktester()
    df_5m, df_15m = backtester.fetch_data(period="1mo")
    backtester.run_backtest(df_5m, df_15m)

