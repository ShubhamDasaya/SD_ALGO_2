"""
Angel One SmartAPI Option Chain & Token Master Manager
Fetches and caches the official NSE Scrip Master for NIFTY weekly options.
"""
import os
import json
import urllib.request
from datetime import datetime

SCRIP_MASTER_URL = "https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json"
CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scrip_master_cache.json")

class AngelOptionMaster:
    def __init__(self):
        self.instruments = []
        self.load_scrip_master()

    def load_scrip_master(self, force_refresh: bool = False):
        """Loads scrip master from local cache or downloads fresh daily copy."""
        need_download = True
        if not force_refresh and os.path.exists(CACHE_FILE):
            mod_time = datetime.fromtimestamp(os.path.getmtime(CACHE_FILE))
            if mod_time.date() == datetime.today().date():
                need_download = False
                try:
                    with open(CACHE_FILE, "r", encoding="utf-8") as f:
                        self.instruments = json.load(f)
                    print(f"[SCRIP MASTER] Loaded {len(self.instruments)} instruments from local cache.")
                except Exception:
                    need_download = True

        if need_download:
            print("[SCRIP MASTER] Downloading fresh Instrument Master from Angel One...")
            try:
                req = urllib.request.Request(SCRIP_MASTER_URL, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=30) as response:
                    data = response.read().decode('utf-8')
                    self.instruments = json.loads(data)
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    f.write(data)
                print(f"[SCRIP MASTER] Successfully cached {len(self.instruments)} instruments.")
            except Exception as e:
                print(f"[WARN] Failed to download Scrip Master: {e}")
                if os.path.exists(CACHE_FILE):
                    with open(CACHE_FILE, "r", encoding="utf-8") as f:
                        self.instruments = json.load(f)

    def get_atm_option(self, current_nifty_price: float, is_call: bool = True) -> dict:
        """
        Dynamically finds the closest ATM Call (CE) or Put (PE) option contract for the current weekly expiry.
        """
        atm_strike = round(current_nifty_price / 50.0) * 50
        suffix = "CE" if is_call else "PE"

        nifty_options = [
            item for item in self.instruments
            if item.get("name") == "NIFTY"
            and item.get("instrumenttype") == "OPTIDX"
            and item.get("symbol", "").endswith(suffix)
        ]

        if not nifty_options:
            return None

        matched = []
        for item in nifty_options:
            try:
                item_strike = float(item.get("strike", 0)) / 100.0
                if abs(item_strike - atm_strike) < 0.1:
                    matched.append(item)
            except Exception:
                continue

        if not matched:
            return None

        # Filter by expiry date >= today
        today_date = datetime.now().date()
        valid_expiries = []
        for item in matched:
            exp_str = item.get("expiry")  # e.g., "09NOV2026"
            try:
                exp_dt = datetime.strptime(exp_str, "%d%b%Y").date()
                if exp_dt >= today_date:
                    valid_expiries.append((exp_dt, item))
            except Exception:
                continue

        if not valid_expiries:
            return matched[0]

        valid_expiries.sort(key=lambda x: x[0])
        best_contract = valid_expiries[0][1]

        return {
            "symbol": best_contract.get("symbol"),
            "token": best_contract.get("token"),
            "strike": float(best_contract.get("strike", 0)) / 100.0,
            "expiry": best_contract.get("expiry"),
            "lotsize": int(best_contract.get("lotsize", 65)),
            "type": suffix
        }

if __name__ == "__main__":
    master = AngelOptionMaster()
    sample_price = 24320.0
    ce = master.get_atm_option(sample_price, is_call=True)
    pe = master.get_atm_option(sample_price, is_call=False)
    print("\n--- TEST ATM RESOLUTION ---")
    print("ATM CE:", ce)
    print("ATM PE:", pe)
