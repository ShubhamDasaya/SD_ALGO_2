"""
Indian Market SMC Option Scalper Bot v1.0
Specialized for NIFTY 50 Option Buying (₹7K - ₹10K Capital)
Key Guards:
- Max 2 Trades Per Day
- Hard Daily Loss Kill Switch: ₹800
- Auto Break-Even Protection (+12 points on Premium)
- Momentum Time-Stop (15 min Theta shield)
"""
import os
import sys
import time
import json
from datetime import datetime
import pandas as pd
from angel_connector import AngelConnector
from token_manager import AngelOptionMaster

# --- Configuration Loader ---
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.env")

def load_config() -> dict:
    cfg = {
        "API_KEY": "", "CLIENT_CODE": "", "PIN": "", "TOTP_SECRET": "",
        "TRADING_MODE": "PAPER_TRADING", "MAX_TRADES_PER_DAY": 2,
        "MAX_DAILY_LOSS": 800.0, "TARGET_PROFIT_PER_TRADE": 1500.0,
        "STOP_LOSS_POINTS": 12.0, "BREAK_EVEN_TRIGGER_POINTS": 12.0,
        "MOMENTUM_TIMEOUT_MINUTES": 15
    }
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    # Strip inline comments
                    if "#" in v:
                        v = v.split("#", 1)[0]
                    v = v.strip()
                    if k in cfg:
                        if isinstance(cfg[k], float): cfg[k] = float(v)
                        elif isinstance(cfg[k], int): cfg[k] = int(v)
                        else: cfg[k] = v
    return cfg

class IndianOptionBot:
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
        print("=" * 65)
        print("  🇮🇳 SMC INDIAN MARKET NIFTY OPTION SCALPER (ANGEL ONE) 🇮🇳")
        print(f"  Mode: {self.cfg['TRADING_MODE']} | Max Trades: {self.cfg['MAX_TRADES_PER_DAY']}/day")
        print(f"  Daily Loss Kill Switch: ₹{self.cfg['MAX_DAILY_LOSS']} | Target: ₹{self.cfg['TARGET_PROFIT_PER_TRADE']}")
        print(f"  SL: {self.cfg['STOP_LOSS_POINTS']} pts | BE Trigger: +{self.cfg['BREAK_EVEN_TRIGGER_POINTS']} pts")
        print("=" * 65)

    def check_kill_switch(self) -> bool:
        """Enforces ironclad daily risk rules."""
        if self.kill_switch_activated:
            return True

        if self.daily_realized_pnl <= -self.cfg["MAX_DAILY_LOSS"]:
            print(f"\n🚨 [KILL SWITCH ACTIVATED] Daily Loss limit reached (-₹{abs(self.daily_realized_pnl):.2f}). Bot stopped for today!")
            self.kill_switch_activated = True
            return True

        if self.daily_trades_count >= self.cfg["MAX_TRADES_PER_DAY"]:
            print(f"\n🔒 [MAX TRADES REACHED] Completed {self.daily_trades_count} trades today. Capital secured. Bot finished.")
            self.kill_switch_activated = True
            return True

        return False

    def execute_entry(self, is_call: bool, nifty_spot: float, premium_entry: float):
        """Selects ATM contract and enters trade (Paper or Live)."""
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
            "entry_time": time.time(),
            "be_moved": False
        }

        print(f"\n[{now_str}] 🚀 [ENTRY EXECUTED] {contract['symbol']} (1 Lot = {lot_size} Qty)")
        print(f"     ➔ Buy Price: ₹{premium_entry:.2f} | SL: ₹{sl_price:.2f} (-{self.cfg['STOP_LOSS_POINTS']} pts) | TP: ₹{tp_price:.2f} (+{target_pts:.1f} pts)")
        print(f"     ➔ Capital Allocated: ₹{premium_entry * lot_size:.2f}")

        if self.cfg["TRADING_MODE"] == "LIVE_TRADING":
            res = self.connector.place_option_order(contract["symbol"], contract["token"], lot_size, is_buy=True)
            print(f"     ➔ Broker Response: {res}")

    def manage_active_trade(self, current_premium: float):
        """Monitors live trade for Target, Stop Loss, Break-Even, and Time Decay."""
        if not self.active_position:
            return

        pos = self.active_position
        entry_p = pos["entry_price"]
        lot_size = pos["lotsize"]
        gain_pts = current_premium - entry_p
        trade_pnl = gain_pts * lot_size
        elapsed_min = (time.time() - pos["entry_time"]) / 60.0

        # 1. Break-Even Trigger (+12 pts on premium)
        if not pos["be_moved"] and gain_pts >= self.cfg["BREAK_EVEN_TRIGGER_POINTS"]:
            pos["current_sl"] = entry_p + 1.0 # Cost + 1 pt brokerage buffer
            pos["be_moved"] = True
            print(f"\n🛡️ [BREAK-EVEN ACTIVE] SL moved to Cost (₹{pos['current_sl']:.2f}) | Risk: ₹0.00!")

        # 2. Target Hit
        if current_premium >= pos["tp_price"]:
            print(f"\n🎯 [TARGET HIT] Profit: +₹{trade_pnl:.2f} (+{gain_pts:.1f} pts) on {pos['symbol']}!")
            self.daily_realized_pnl += trade_pnl
            self.active_position = None
            return

        # 3. Stop Loss Hit
        if current_premium <= pos["current_sl"]:
            print(f"\n🛑 [STOP LOSS HIT] Loss: -₹{abs(trade_pnl):.2f} ({gain_pts:.1f} pts) on {pos['symbol']}!")
            self.daily_realized_pnl += trade_pnl
            self.active_position = None
            return

        # 4. Momentum Timeout (Theta Shield)
        if elapsed_min >= self.cfg["MOMENTUM_TIMEOUT_MINUTES"]:
            print(f"\n⏱️ [THETA TIME-STOP] 15 mins elapsed with no momentum. Exiting @ ₹{current_premium:.2f} (PnL: ₹{trade_pnl:.2f})")
            self.daily_realized_pnl += trade_pnl
            self.active_position = None
            return

    def run_simulation_demo(self):
        """Demonstrates a complete paper trade simulation from signal to exit."""
        self.print_banner()
        print("\n[SIMULATION DEMO] Simulating Live SMC Signal on NIFTY 50...")
        time.sleep(1)

        # 1. Simulating Bullish Liquidity Sweep at 24,310
        nifty_spot = 24310.0
        premium_entry = 110.0 # ATM Option priced at ₹110
        print(f"[*] SMC Signal: 15M Bullish Sweep Detected at Nifty {nifty_spot}!")
        self.execute_entry(is_call=True, nifty_spot=nifty_spot, premium_entry=premium_entry)

        # 2. Simulating price progression
        test_prices = [112.0, 118.0, 123.0, 126.0, 134.0]
        for p in test_prices:
            time.sleep(0.8)
            pnl = (p - premium_entry) * 65
            print(f"    📈 LTP Update: ₹{p:.2f} | Unrealized PnL: ₹{pnl:+.2f}")
            self.manage_active_trade(p)
            if not self.active_position:
                break

        print("\n" + "=" * 65)
        print(f"  🏁 Day's Realized PnL: ₹{self.daily_realized_pnl:+.2f} | Trades Taken: {self.daily_trades_count}/2")
        print("=" * 65)

if __name__ == "__main__":
    bot = IndianOptionBot()
    bot.run_simulation_demo()
