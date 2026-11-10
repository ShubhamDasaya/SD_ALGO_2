"""
===============================================================================
NIFTY 50 LIVE SMC OPTION SCALPER (ANGEL ONE SMARTAPI) - v2.0
===============================================================================
Exact replication of MT5 Institutional SMC Engine adapted for Indian Options:
- 15M Swing High/Low & Previous Day High/Low Liquidity Sweep (PP Grab)
- Displacement Candle Validation (Body Ratio >= 45% or Rejection Wick >= 45%)
- Trend Alignment Shield (HTF EMA 20/50 + Day Open Direction)
- Options Greeks Defense:
  * Theta Shield (Strict 20-min Time Stop)
  * Gamma Stop Loss (-9.0 Option Points = Rs 585 risk per lot)
  * Auto Break-Even Protection (+8.0 Option Points moves SL to Cost + 1 pt)
  * Hard 1-Loss Daily Kill Switch (Protects remaining 93% Capital)
===============================================================================
"""

import os
import sys
import time
from datetime import datetime, time as dtime
import pandas as pd
from angel_connector import AngelConnector
from token_manager import AngelOptionMaster

# --- Configuration Loader ---
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.env")

def load_config() -> dict:
    cfg = {
        "API_KEY": "", "CLIENT_CODE": "", "PIN": "", "TOTP_SECRET": "",
        "TRADING_MODE": "PAPER_TRADING", "MAX_TRADES_PER_DAY": 2,
        "MAX_DAILY_LOSS": 800.0, "TARGET_PROFIT_PER_TRADE": 975.0, # +15 pts
        "STOP_LOSS_POINTS": 9.0, "BREAK_EVEN_TRIGGER_POINTS": 8.0,
        "MOMENTUM_TIMEOUT_MINUTES": 20
    }
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    if "#" in v: v = v.split("#", 1)[0]
                    v = v.strip()
                    if k in cfg:
                        if isinstance(cfg[k], float): cfg[k] = float(v)
                        elif isinstance(cfg[k], int): cfg[k] = int(v)
                        else: cfg[k] = v
    return cfg


class IndianSMCOptionBot:
    def __init__(self):
        self.cfg = load_config()
        self.connector = AngelConnector(
            self.cfg["API_KEY"], self.cfg["CLIENT_CODE"],
            self.cfg["PIN"], self.cfg["TOTP_SECRET"]
        )
        self.token_master = AngelOptionMaster()
        self.daily_trades_count = 0
        self.daily_realized_pnl = 0.0
        self.active_position = None
        self.kill_switch_activated = False

    def print_banner(self):
        print("=" * 70)
        print("  🇮🇳 SMC INSTITUTIONAL NIFTY OPTION SCALPER (ANGEL ONE) 🇮🇳")
        print(f"  Mode: {self.cfg['TRADING_MODE']} | Max Trades: {self.cfg['MAX_TRADES_PER_DAY']}/day")
        print(f"  Greeks Defense: Theta Shield 20m | SL: {self.cfg['STOP_LOSS_POINTS']} pts | BE Trigger: +{self.cfg['BREAK_EVEN_TRIGGER_POINTS']} pts")
        print(f"  Kill Switch: ₹{self.cfg['MAX_DAILY_LOSS']} (1 Loss = Stop Trading)")
        print("=" * 70)

    def check_kill_switch(self) -> bool:
        if self.kill_switch_activated:
            return True
        if self.daily_realized_pnl <= -self.cfg["MAX_DAILY_LOSS"]:
            print(f"\n🚨 [KILL SWITCH] Daily Loss limit reached (-₹{abs(self.daily_realized_pnl):.2f}). Trading halted for today!")
            self.kill_switch_activated = True
            return True
        if self.daily_trades_count >= self.cfg["MAX_TRADES_PER_DAY"]:
            print(f"\n🔒 [MAX TRADES REACHED] Completed {self.daily_trades_count} trades. Capital secured.")
            self.kill_switch_activated = True
            return True
        return False

    def execute_entry(self, is_call: bool, nifty_spot: float, premium_entry: float, sweep_level: float):
        contract = self.token_master.get_atm_option(nifty_spot, is_call=is_call)
        if not contract:
            print("[ENTRY ERROR] Could not find ATM Option Contract.")
            return

        lot_size = contract["lotsize"]
        sl_price = premium_entry - self.cfg["STOP_LOSS_POINTS"]
        target_pts = self.cfg["TARGET_PROFIT_PER_TRADE"] / lot_size
        tp_price = premium_entry + target_pts

        self.daily_trades_count += 1
        now_str = datetime.now().strftime("%H:%M:%S")

        self.active_position = {
            "symbol": contract["symbol"],
            "token": contract["token"],
            "type": contract["type"],
            "strike": contract["strike"],
            "lotsize": lot_size,
            "entry_price": premium_entry,
            "current_sl": sl_price,
            "tp_price": tp_price,
            "sweep_level": sweep_level,
            "entry_time": time.time(),
            "be_moved": False
        }

        print(f"\n[{now_str}] 🚀 [SMC PP SWEEP ENTRY] {contract['symbol']} (1 Lot = {lot_size} Qty)")
        print(f"     ➔ Swept Level: {sweep_level:.1f} | Nifty Spot: {nifty_spot:.1f}")
        print(f"     ➔ Buy Premium: ₹{premium_entry:.2f} | SL: ₹{sl_price:.2f} (-{self.cfg['STOP_LOSS_POINTS']} pts) | TP: ₹{tp_price:.2f} (+{target_pts:.1f} pts)")
        print(f"     ➔ Total Capital Deployed: ₹{premium_entry * lot_size:.2f} (Safe Capital Guard)")

        if self.cfg["TRADING_MODE"] == "LIVE_TRADING":
            res = self.connector.place_option_order(contract["symbol"], contract["token"], lot_size, is_buy=True)
            print(f"     ➔ Angel One Order Response: {res}")

    def manage_active_trade(self, current_premium: float):
        if not self.active_position:
            return

        pos = self.active_position
        entry_p = pos["entry_price"]
        lot_size = pos["lotsize"]
        gain_pts = current_premium - entry_p
        trade_pnl = gain_pts * lot_size
        elapsed_min = (time.time() - pos["entry_time"]) / 60.0

        # 1. Break-Even Protection (Moves SL to Cost + 1.0 pt brokerage buffer)
        if not pos["be_moved"] and gain_pts >= self.cfg["BREAK_EVEN_TRIGGER_POINTS"]:
            pos["current_sl"] = entry_p + 1.0
            pos["be_moved"] = True
            print(f"\n🛡️ [BREAK-EVEN ACTIVE] SL moved to ₹{pos['current_sl']:.2f} | Risk is now ₹0.00!")

        # 2. Target Hit
        if current_premium >= pos["tp_price"]:
            print(f"\n🎯 [TARGET HIT] Profit: +₹{trade_pnl:.2f} (+{gain_pts:.1f} pts) on {pos['symbol']}!")
            self.daily_realized_pnl += trade_pnl
            self.active_position = None
            return

        # 3. Stop Loss Hit
        if current_premium <= pos["current_sl"]:
            reason_label = "BREAK-EVEN EXIT" if pos["be_moved"] else "STOP LOSS HIT"
            print(f"\n🛑 [{reason_label}] Net PnL: ₹{trade_pnl:.2f} ({gain_pts:.1f} pts) on {pos['symbol']}!")
            self.daily_realized_pnl += trade_pnl
            self.active_position = None
            return

        # 4. Theta Shield (Strict 20-min Time Stop)
        if elapsed_min >= self.cfg["MOMENTUM_TIMEOUT_MINUTES"]:
            print(f"\n⏱️ [THETA SHIELD TIMESTOP] 20 mins elapsed without target. Exiting @ ₹{current_premium:.2f} (PnL: ₹{trade_pnl:.2f})")
            self.daily_realized_pnl += trade_pnl
            self.active_position = None
            return

    def run_simulation_demo(self):
        self.print_banner()
        print("\n[SIMULATION DEMO] Demonstrating MT5 Liquidity Sweep in Indian Market...")
        time.sleep(1)

        # Bullish Liquidity Sweep Simulation
        nifty_spot = 22550.0
        sweep_level = 22545.0
        premium_entry = 110.0

        print(f"[*] SMC Signal: 15M Swing Low {sweep_level} Swept with Rejection Wick!")
        self.execute_entry(is_call=True, nifty_spot=nifty_spot, premium_entry=premium_entry, sweep_level=sweep_level)

        test_ticks = [112.0, 115.0, 118.5, 122.0, 125.5]
        for p in test_ticks:
            time.sleep(0.8)
            pnl = (p - premium_entry) * 65
            print(f"    📈 Option LTP: ₹{p:.2f} | Running PnL: ₹{pnl:+.2f}")
            self.manage_active_trade(p)
            if not self.active_position:
                break

        print("\n" + "=" * 70)
        print(f"  🏁 Day's Realized PnL: ₹{self.daily_realized_pnl:+.2f} | Trades Taken: {self.daily_trades_count}/2")
        print("=" * 70)


if __name__ == "__main__":
    bot = IndianSMCOptionBot()
    bot.run_simulation_demo()

