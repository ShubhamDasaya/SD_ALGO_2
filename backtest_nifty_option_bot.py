"""
===============================================================================
NIFTY 50 OPTION BUYING - INSTITUTIONAL BACKTESTING ENGINE
===============================================================================
Strategy: 
  1. Opening Range (09:15 - 09:45) Liquidity Sweep & Momentum Breakout
  2. Multi-Timeframe Alignment: Daily Open + 5M 20/50 EMA Trend Filter
  3. High-Probability Time Windows (09:45-11:30 & 13:15-14:15, Zero Lunch Chop)
  4. Candlestick Momentum Confirmation (Strong close in top 30% of bar range)
  5. Capital Discipline (Rs 10,000 Capital):
     - 1 Lot (65 Qty) ATM Option (Delta = 0.50)
     - Target: +18 Option Pts (+Rs 1,050 Net Profit)
     - Stop Loss: -10 Option Pts (-Rs 770 Net Loss)
     - Max 2 Trades / Day
     - HARD 1-LOSS KILL SWITCH (1 SL = Bot Shuts Down for the Day)
     - 30-Min Time Stop (Avoid Theta Decay Burn)
     - Friction: 1.0 pt slippage + Rs 55 brokerage & taxes per trade
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


class NiftyOptionBacktester:
    def __init__(
        self,
        starting_capital: float = 10000.0,
        lot_size: int = 65,
        target_pts: float = 18.0,
        sl_pts: float = 10.0,
        max_daily_loss: float = 800.0,
        max_trades_per_day: int = 2,
        slippage_pts: float = 1.0,
        brokerage_per_trade: float = 55.0,
        delta: float = 0.50,
        max_hold_bars: int = 6  # 6 * 5m = 30 minutes
    ):
        self.starting_capital = starting_capital
        self.capital = starting_capital
        self.lot_size = lot_size
        self.target_pts = target_pts
        self.sl_pts = sl_pts
        self.max_daily_loss = max_daily_loss
        self.max_trades_per_day = max_trades_per_day
        self.slippage_pts = slippage_pts
        self.brokerage_per_trade = brokerage_per_trade
        self.delta = delta
        self.max_hold_bars = max_hold_bars

    def fetch_data(self, period: str = "1mo", interval: str = "5m") -> pd.DataFrame:
        """Download real intraday candles for Nifty 50."""
        print(f"[*] Fetching NIFTY 50 data from market feed (Period: {period}, Interval: {interval})...")
        df = yf.download("^NSEI", period=period, interval=interval, progress=False)
        if df.empty:
            raise ValueError("No data returned for ^NSEI")

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]

        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()

        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC").tz_convert("Asia/Kolkata")
        else:
            df.index = df.index.tz_convert("Asia/Kolkata")

        df = df.between_time("09:15", "15:25")
        print(f"[+] Loaded {len(df)} candles spanning {df.index[0].date()} to {df.index[-1].date()}")
        return df

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute trend and momentum indicators."""
        data = df.copy()
        data["EMA20"] = data["Close"].ewm(span=20, adjust=False).mean()
        data["EMA50"] = data["Close"].ewm(span=50, adjust=False).mean()
        data["Candle_Range"] = data["High"] - data["Low"]
        return data

    def run(self, df: pd.DataFrame) -> dict:
        """Execute the institutional backtest simulation."""
        days = df.groupby(df.index.date)
        trades = []

        for date, day_df in days:
            if len(day_df) < 15:
                continue

            day_open = day_df.iloc[0]["Open"]
            or_df = day_df.between_time("09:15", "09:45")
            if len(or_df) < 5:
                continue

            or_high = or_df["High"].max()
            or_low = or_df["Low"].min()

            post_or = day_df.between_time("09:50", "14:30")
            open_pos = None
            trades_today = 0
            kill_switch_active = False

            for idx, row in post_or.iterrows():
                c = row["Close"]
                h = row["High"]
                l = row["Low"]
                o = row["Open"]
                ema20 = row["EMA20"]
                ema50 = row["EMA50"]
                c_range = row["Candle_Range"]

                # ---------------------------------------------------------
                # 1. POSITION MANAGEMENT
                # ---------------------------------------------------------
                if open_pos is not None:
                    open_pos["bars"] += 1
                    theta = open_pos["bars"] * 0.10  # Theta decay per 5m bar

                    if open_pos["type"] == "CE":
                        best_gain = ((h - open_pos["entry"]) * self.delta) - theta
                        worst_loss = ((open_pos["entry"] - l) * self.delta) + theta
                        cur_opt = ((c - open_pos["entry"]) * self.delta) - theta
                    else:  # PE
                        best_gain = ((open_pos["entry"] - l) * self.delta) - theta
                        worst_loss = ((h - open_pos["entry"]) * self.delta) + theta
                        cur_opt = ((open_pos["entry"] - c) * self.delta) - theta

                    reason = None
                    exit_pts = 0.0

                    if best_gain >= self.target_pts:
                        reason = "TARGET"
                        exit_pts = self.target_pts - self.slippage_pts
                    elif worst_loss >= self.sl_pts:
                        reason = "STOP_LOSS"
                        exit_pts = -self.sl_pts - self.slippage_pts
                    elif open_pos["bars"] >= self.max_hold_bars:
                        reason = "TIME_STOP_THETA"
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
                            "entry_spot": round(open_pos["entry"], 1),
                            "exit_spot": round(c, 1),
                            "opt_pts": round(exit_pts, 2),
                            "gross_pnl": round(gross_pnl, 2),
                            "net_pnl": round(net_pnl, 2),
                            "capital": round(self.capital, 2),
                            "reason": reason,
                            "bars": open_pos["bars"]
                        })

                        # KILL SWITCH TRIGGER: 1 Loss shuts down trading for the day!
                        if net_pnl < 0:
                            kill_switch_active = True

                        open_pos = None
                        continue

                # ---------------------------------------------------------
                # 2. TRADE PERMISSION & TIMING CHECKS
                # ---------------------------------------------------------
                if open_pos is not None or trades_today >= self.max_trades_per_day or kill_switch_active:
                    continue

                t = idx.time()
                is_morning = (time(9, 45) <= t <= time(11, 30))
                is_afternoon = (time(13, 15) <= t <= time(14, 15))
                if not (is_morning or is_afternoon):
                    continue  # Zero trading during 11:30 - 13:15 Lunch Chop

                if c_range < 12.0:  # Skip sluggish/indecisive micro candles
                    continue

                # Candlestick Momentum Confirmation
                bullish_close = (h - c) <= c_range * 0.30
                bearish_close = (c - l) <= c_range * 0.30

                # ---------------------------------------------------------
                # 3. ENTRY SIGNALS
                # ---------------------------------------------------------
                # Setup A: Bullish Momentum Breakout (Buy ATM CE)
                if c > day_open and ema20 > ema50 and c > or_high and o <= or_high and bullish_close:
                    atm_strike = int(round(c / 50.0) * 50)
                    open_pos = {
                        "entry": c,
                        "type": "CE",
                        "strike": atm_strike,
                        "bars": 0,
                        "entry_time": idx
                    }
                    trades_today += 1

                # Setup B: Bearish Momentum Breakdown (Buy ATM PE)
                elif c < day_open and ema20 < ema50 and c < or_low and o >= or_low and bearish_close:
                    atm_strike = int(round(c / 50.0) * 50)
                    open_pos = {
                        "entry": c,
                        "type": "PE",
                        "strike": atm_strike,
                        "bars": 0,
                        "entry_time": idx
                    }
                    trades_today += 1

        return self._format_results(trades)

    def _format_results(self, trades: list) -> dict:
        if not trades:
            return {"status": "NO_TRADES"}

        df_t = pd.DataFrame(trades)
        total = len(df_t)
        wins = df_t[df_t["net_pnl"] > 0]
        losses = df_t[df_t["net_pnl"] < 0]

        win_count = len(wins)
        loss_count = len(losses)
        win_rate = (win_count / total) * 100.0 if total > 0 else 0.0

        tot_prof = wins["net_pnl"].sum() if not wins.empty else 0.0
        tot_loss = abs(losses["net_pnl"].sum()) if not losses.empty else 0.0
        net = tot_prof - tot_loss
        pf = (tot_prof / tot_loss) if tot_loss > 0 else 999.0

        # Equity Curve and Drawdown
        df_t["cum_pnl"] = df_t["net_pnl"].cumsum()
        df_t["equity"] = self.starting_capital + df_t["cum_pnl"]
        df_t["peak"] = df_t["equity"].cummax()
        df_t["drawdown"] = df_t["peak"] - df_t["equity"]
        max_dd = df_t["drawdown"].max()

        daily = df_t.groupby("date")["net_pnl"].sum()
        green_days = (daily > 0).sum()
        red_days = (daily < 0).sum()

        return {
            "status": "SUCCESS",
            "starting_capital": self.starting_capital,
            "final_capital": round(self.capital, 2),
            "net_profit": round(net, 2),
            "return_pct": round((net / self.starting_capital) * 100.0, 2),
            "total_trades": total,
            "win_count": win_count,
            "loss_count": loss_count,
            "win_rate_pct": round(win_rate, 1),
            "profit_factor": round(pf, 2),
            "max_drawdown_rs": round(max_dd, 2),
            "max_drawdown_pct": round((max_dd / self.starting_capital) * 100.0, 1),
            "green_days": int(green_days),
            "red_days": int(red_days),
            "df": df_t
        }


def print_report(res: dict):
    print("\n" + "=" * 72)
    print("      NIFTY 50 OPTION BUYING BOT - INSTITUTIONAL AUDIT REPORT      ")
    print("=" * 72)

    if res.get("status") == "NO_TRADES":
        print("[-] No trades triggered.")
        print("=" * 72)
        return

    print(f"  Starting Capital     : Rs {res['starting_capital']:,.2f}")
    print(f"  Final Capital        : Rs {res['final_capital']:,.2f}")
    print(f"  Net Profit (Post-Tax): Rs {res['net_profit']:+,.2f} ({res['return_pct']:+.2f}%)")
    print("-" * 72)
    print(f"  Total Trades Taken   : {res['total_trades']} across period (Disciplined Selectivity)")
    print(f"  Winning Trades       : {res['win_count']} ({res['win_rate_pct']:.1f}% Win Rate)")
    print(f"  Losing Trades        : {res['loss_count']}")
    print(f"  Profit Factor        : {res['profit_factor']:.2f}")
    print(f"  Max Drawdown         : Rs {res['max_drawdown_rs']:,.2f} ({res['max_drawdown_pct']:.1f}%)")
    print(f"  Trading Days         : {res['green_days']} Green Days | {res['red_days']} Red Days")
    print("=" * 72)

    df_t = res["df"]
    print("\nDETAILED TRADE LOG:")
    print("-" * 72)
    for _, t in df_t.iterrows():
        pnl_str = f"Rs {t['net_pnl']:+8.2f}"
        print(f"  {t['date']} {t['entry_time']}-{t['exit_time']} | {t['type']:2} {t['strike']} | Opt Pts: {t['opt_pts']:+5.1f} | Net: {pnl_str} | {t['reason']}")
    print("=" * 72)


if __name__ == "__main__":
    bt = NiftyOptionBacktester(
        starting_capital=10000.0,
        lot_size=65,
        target_pts=18.0,       # +18 pts = +Rs 1,050 Net Gain
        sl_pts=10.0,           # -10 pts = -Rs 770 Net Loss
        max_daily_loss=800.0,  # 1 SL halts the day
        max_trades_per_day=2,
        slippage_pts=1.0,
        brokerage_per_trade=55.0,
        delta=0.50,
        max_hold_bars=6        # 30 mins time-stop
    )

    try:
        data = bt.fetch_data(period="1mo", interval="5m")
        data = bt.compute_indicators(data)
        results = bt.run(data)
        print_report(results)

        if results.get("df") is not None:
            csv_file = os.path.join(os.path.dirname(__file__), "nifty_option_backtest_results.csv")
            results["df"].to_csv(csv_file, index=False)
            print(f"[+] Full audit log saved to: {csv_file}")

    except Exception as exc:
        print(f"[-] Execution error: {exc}")
        import traceback
        traceback.print_exc()
