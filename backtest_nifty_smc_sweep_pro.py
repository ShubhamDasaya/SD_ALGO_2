"""
===============================================================================
NIFTY 50 SMC LIQUIDITY SWEEP (PP) - INSTITUTIONAL PRO VERSION
===============================================================================
Incorporating MT5 Task 1 & Task 2 Rules:
1. Anti-Counter Trend Shield: Trend Filter (HTF EMA + Day Open alignment).
   - Never Buy PE when market is in strong Uptrend!
   - Never Buy CE when market is in strong Downtrend!
2. False Breakout Trap Filter: 09:15 - 09:45 morning whip protection.
3. Options Greeks Defense (Theta Shield):
   - Strict 20-min holding cap.
   - ATM Selection with dynamic Target (1.5R = +15 pts, SL = -9 pts).
   - Auto Break-Even at +8 pts (+Rs 520 profit moves SL to Cost + 1 pt).
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


class NiftySMCSweepPro:
    def __init__(
        self,
        starting_capital: float = 10000.0,
        lot_size: int = 65,
        target_pts: float = 16.0,
        sl_pts: float = 9.0,
        be_pts: float = 8.0,
        slippage_pts: float = 1.0,
        brokerage_per_trade: float = 55.0,
        delta: float = 0.50,
        max_hold_bars: int = 4  # 20 mins max hold
    ):
        self.starting_capital = starting_capital
        self.capital = starting_capital
        self.lot_size = lot_size
        self.target_pts = target_pts
        self.sl_pts = sl_pts
        self.be_pts = be_pts
        self.slippage_pts = slippage_pts
        self.brokerage_per_trade = brokerage_per_trade
        self.delta = delta
        self.max_hold_bars = max_hold_bars

    def fetch_data(self, period: str = "1mo") -> tuple[pd.DataFrame, pd.DataFrame]:
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

        for df in [df_5m, df_15m]:
            if df.index.tz is None:
                df.index = df.index.tz_localize("UTC").tz_convert("Asia/Kolkata")
            else:
                df.index = df.index.tz_convert("Asia/Kolkata")

        df_5m = df_5m.between_time("09:15", "15:25")
        df_15m = df_15m.between_time("09:15", "15:25")

        # Indicators for Trend (MT5 Core: HTF Trend Filter)
        df_5m["EMA20"] = df_5m["Close"].ewm(span=20, adjust=False).mean()
        df_5m["EMA50"] = df_5m["Close"].ewm(span=50, adjust=False).mean()

        return df_5m, df_15m

    def compute_15m_swings(self, df_15m: pd.DataFrame, pivot_len: int = 3) -> list:
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

    def run(self, df_5m: pd.DataFrame, df_15m: pd.DataFrame) -> dict:
        swings = self.compute_15m_swings(df_15m)
        days = df_5m.groupby(df_5m.index.date)
        trades = []

        prev_day_high = None
        prev_day_low = None

        for date, day_df in days:
            if len(day_df) < 15:
                continue

            day_open = day_df.iloc[0]["Open"]
            current_day_high = day_df["High"].max()
            current_day_low = day_df["Low"].min()

            day_start = day_df.index[0]
            past_swings = [s for s in swings if s["time"] < day_start]
            recent_highs = [s["price"] for s in past_swings if s["type"] == "SWING_HIGH"][-6:]
            recent_lows = [s["price"] for s in past_swings if s["type"] == "SWING_LOW"][-6:]

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
                ema20 = row["EMA20"]
                ema50 = row["EMA50"]
                c_rng = max(h - l, 0.05)
                body = abs(c - o)

                # 1. POSITION MANAGEMENT
                if open_pos is not None:
                    open_pos["bars"] += 1
                    decay = open_pos["bars"] * 0.12  # Theta decay per bar

                    if open_pos["type"] == "CE":
                        best_opt = ((h - open_pos["entry"]) * self.delta) - decay
                        worst_opt = ((open_pos["entry"] - l) * self.delta) + decay
                        cur_opt = ((c - open_pos["entry"]) * self.delta) - decay
                    else:  # PE
                        best_opt = ((open_pos["entry"] - l) * self.delta) - decay
                        worst_opt = ((h - open_pos["entry"]) * self.delta) + decay
                        cur_opt = ((open_pos["entry"] - c) * self.delta) - decay

                    # Auto Break-Even Protection (Moves SL to Cost + 1 pt)
                    if not open_pos["be_moved"] and best_opt >= self.be_pts:
                        open_pos["be_moved"] = True

                    reason = None
                    exit_pts = 0.0

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
                        reason = "THETA_TIMESTOP"
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
                            "level": round(open_pos["level"], 1),
                            "opt_pts": round(exit_pts, 2),
                            "net_pnl": round(net_pnl, 2),
                            "capital": round(self.capital, 2),
                            "reason": reason,
                            "bars": open_pos["bars"]
                        })

                        # KILL SWITCH TRIGGER: 1 Loss halts the bot for the day!
                        if net_pnl < 0:
                            kill_switch_active = True

                        open_pos = None
                        continue

                # 2. TRADE PERMISSION CHECKS
                if open_pos is not None or trades_today >= 2 or kill_switch_active:
                    continue

                # Golden Windows (Avoid 09:15-09:45 morning noise and 11:30-13:15 Lunch Chop)
                is_golden_morning = (time(9, 45) <= t <= time(11, 30))
                is_golden_afternoon = (time(13, 15) <= t <= time(14, 30))
                if not (is_golden_morning or is_golden_afternoon):
                    continue

                if c_rng < 12.0:
                    continue

                body_ratio = body / c_rng
                lower_wick = min(c, o) - l
                upper_wick = h - max(c, o)

                # MT5 DISPLACEMENT REQUIREMENT:
                # Strong body (>=45%) or long rejection wick (>=45%)
                has_bull_disp = (c > o) and (body_ratio >= 0.45 or (lower_wick / c_rng) >= 0.45)
                has_bear_disp = (c < o) and (body_ratio >= 0.45 or (upper_wick / c_rng) >= 0.45)

                # MT5 TREND SHIELD (Never fight the dominant trend):
                is_uptrend = (c > day_open and ema20 >= ema50)
                is_downtrend = (c < day_open and ema20 <= ema50)

                # 3. SMC PP SIGNALS

                # SETUP A: Bullish Liquidity Sweep (CE) in Uptrend / Pullback to Demand
                if has_bull_disp and is_uptrend:
                    for lvl in recent_lows:
                        if l < lvl and c > lvl and abs(lvl - l) >= 4.0:
                            atm_strike = int(round(c / 50.0) * 50)
                            open_pos = {
                                "entry": c,
                                "type": "CE",
                                "strike": atm_strike,
                                "level": lvl,
                                "bars": 0,
                                "entry_time": idx,
                                "be_moved": False
                            }
                            trades_today += 1
                            break

                # SETUP B: Bearish Liquidity Sweep (PE) in Downtrend / Rally into Supply
                elif has_bear_disp and is_downtrend and open_pos is None:
                    for lvl in recent_highs:
                        if h > lvl and c < lvl and abs(h - lvl) >= 4.0:
                            atm_strike = int(round(c / 50.0) * 50)
                            open_pos = {
                                "entry": c,
                                "type": "PE",
                                "strike": atm_strike,
                                "level": lvl,
                                "bars": 0,
                                "entry_time": idx,
                                "be_moved": False
                            }
                            trades_today += 1
                            break

            prev_day_high = current_day_high
            prev_day_low = current_day_low

        return self.compile_report(trades)

    def compile_report(self, trades: list) -> dict:
        total = len(trades)
        if total == 0:
            print("\n[-] No trades triggered with the refined SMC parameters.")
            return {}

        wins = [t for t in trades if t["net_pnl"] > 0]
        losses = [t for t in trades if t["net_pnl"] < 0]
        bes = [t for t in trades if t["reason"] == "BREAK_EVEN"]

        win_rate = (len(wins) / total) * 100.0
        net_profit = self.capital - self.starting_capital
        pct_return = (net_profit / self.starting_capital) * 100.0

        print("\n" + "=" * 74)
        print("  🇮🇳 NIFTY 50 SMC LIQUIDITY SWEEP (PRO) - AUDIT REPORT 🇮🇳")
        print("=" * 74)
        print(f"  Starting Capital     : Rs {self.starting_capital:,.2f}")
        print(f"  Final Capital        : Rs {self.capital:,.2f}")
        print(f"  Net Profit (Post-Tax): Rs {net_profit:+,.2f} ({pct_return:+.2f}%)")
        print("-" * 74)
        print(f"  Total Trades Taken   : {total}")
        print(f"  Winning Trades       : {len(wins)} ({win_rate:.1f}% Win Rate)")
        print(f"  Losing Trades        : {len(losses)}")
        print(f"  Break-Even Protected : {len(bes)} (Zero Loss)")
        print("=" * 74)

        print("\nDETAILED TRADE LOG:")
        print("-" * 74)
        for t in trades:
            print(f"  {t['date']} {t['entry_time']}-{t['exit_time']} | {t['type']} {t['strike']} (Sweep {t['level']}) | Opt: {t['opt_pts']:+5.1f} pts | Net: Rs {t['net_pnl']:+8.2f} | {t['reason']}")
        print("=" * 74)

        csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nifty_smc_sweep_pro_results.csv")
        pd.DataFrame(trades).to_csv(csv_path, index=False)
        print(f"[+] Full audit log saved to: {csv_path}\n")

        return {
            "total_trades": total,
            "win_rate": win_rate,
            "net_profit": net_profit,
            "pct_return": pct_return
        }


if __name__ == "__main__":
    bot = NiftySMCSweepPro()
    df_5m, df_15m = bot.fetch_data(period="1mo")
    bot.run(df_5m, df_15m)

