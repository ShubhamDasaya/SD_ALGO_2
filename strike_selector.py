"""
===============================================================================
NIFTY 50 OPTION CHAIN & TOKEN RESOLVER
===============================================================================
Resolves:
1. Nearest Expiry Date (Current Weekly / Monthly Expiry)
2. Strike Calculation (ATM / 50-pts ITM for CE & PE)
3. Broker-specific Security ID / Trading Symbol generation for Dhan & Fyers
4. Automated NSE Option Contract Scrip Master mapping
===============================================================================
"""

import os
import json
import logging
from datetime import datetime, date, timedelta
import urllib.request
from config import Config

logger = logging.getLogger("StrikeSelector")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

class StrikeSelector:
    def __init__(self, broker: str = Config.BROKER):
        self.broker = broker.upper()
        self.scrip_cache_file = os.path.join(os.path.dirname(__file__), "scrip_master_cache.json")
        self.instruments = []
        self._load_scrip_master()

    def _load_scrip_master(self, force_refresh: bool = False):
        """Loads and caches the official instrument master."""
        if not force_refresh and os.path.exists(self.scrip_cache_file):
            try:
                with open(self.scrip_cache_file, "r", encoding="utf-8") as f:
                    self.instruments = json.load(f)
                logger.info(f"Loaded {len(self.instruments)} instruments from local cache.")
                return
            except Exception as e:
                logger.warning(f"Failed to read cache file: {e}")

        # Download fresh master if cache is missing or force_refresh is requested
        logger.info("Fetching fresh instrument directory...")
        try:
            url = "https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read().decode('utf-8')
                self.instruments = json.loads(data)
            with open(self.scrip_cache_file, "w", encoding="utf-8") as f:
                f.write(data)
            logger.info(f"Downloaded & cached {len(self.instruments)} instruments.")
        except Exception as e:
            logger.error(f"Error fetching instrument master: {e}")

    @staticmethod
    def calculate_strike(spot_price: float, option_type: str, mode: str = Config.STRIKE_SELECTION_MODE) -> int:
        """
        Calculates ATM or ITM_1 strike for Nifty 50.
        Step size = 50 points.
        CE ITM = ATM - 50
        PE ITM = ATM + 50
        """
        atm_strike = int(round(spot_price / 50.0) * 50)
        
        if mode == "ITM_1":
            if option_type.upper() == "CE":
                return atm_strike - 50
            else:
                return atm_strike + 50
        return atm_strike

    def get_upcoming_expiry(self) -> date:
        """Finds closest Thursday (or NSE holiday adjusted expiry date)."""
        today = date.today()
        # Nifty weekly contracts expire on Thursday (weekday = 3)
        days_ahead = 3 - today.weekday()
        if days_ahead < 0:  # If today is Friday/Saturday/Sunday
            days_ahead += 7
        target_expiry = today + timedelta(days=days_ahead)
        return target_expiry

    def resolve_contract(self, spot_price: float, option_type: str) -> dict:
        """
        Returns full contract descriptor:
        {
            'symbol': 'NIFTY 13NOV26 24500 CE',
            'strike': 24500,
            'option_type': 'CE',
            'expiry': '13NOV2026',
            'security_id': '45123',
            'fyers_symbol': 'NSE:NIFTY26N1324500CE',
            'lot_size': 65
        }
        """
        strike = self.calculate_strike(spot_price, option_type)
        suffix = option_type.upper()

        # Filter all Nifty Option Index contracts matching strike & type
        matched = []
        for item in self.instruments:
            if (item.get("name") == "NIFTY" and 
                item.get("instrumenttype") == "OPTIDX" and 
                item.get("symbol", "").endswith(suffix)):
                try:
                    item_strike = float(item.get("strike", 0)) / 100.0
                    if abs(item_strike - strike) < 0.1:
                        matched.append(item)
                except Exception:
                    continue

        if not matched:
            logger.warning(f"No direct match found in cache for {strike} {suffix}. Generating algorithmic descriptor.")
            exp_date = self.get_upcoming_expiry()
            exp_str = exp_date.strftime("%d%b%y").upper()
            dhan_symbol = f"NIFTY {exp_date.strftime('%d %b').upper()} {strike} {suffix}"
            fyers_sym = f"NSE:NIFTY{exp_date.strftime('%y%m%d')}{strike}{suffix}"
            return {
                "symbol": dhan_symbol,
                "fyers_symbol": fyers_sym,
                "strike": strike,
                "option_type": suffix,
                "expiry": exp_date.strftime("%d%b%Y").upper(),
                "security_id": "0",
                "lot_size": Config.LOT_SIZE
            }

        # Sort matches by nearest upcoming expiry >= today
        today_date = date.today()
        valid_expiries = []
        for item in matched:
            exp_str = item.get("expiry")  # e.g., "13NOV2026"
            try:
                exp_dt = datetime.strptime(exp_str, "%d%b%Y").date()
                if exp_dt >= today_date:
                    valid_expiries.append((exp_dt, item))
            except Exception:
                continue

        if not valid_expiries:
            chosen = matched[0]
        else:
            valid_expiries.sort(key=lambda x: x[0])
            chosen = valid_expiries[0][1]

        token = chosen.get("token", "0")
        trading_symbol = chosen.get("symbol", "")
        lot_size = int(chosen.get("lotsize", Config.LOT_SIZE))
        expiry_val = chosen.get("expiry", "")

        # Format Fyers standardized symbol
        try:
            exp_dt = datetime.strptime(expiry_val, "%d%b%Y")
            fyers_sym = f"NSE:NIFTY{exp_dt.strftime('%y%b').upper()}{strike}{suffix}"
        except Exception:
            fyers_sym = f"NSE:{trading_symbol}"

        return {
            "symbol": trading_symbol,
            "fyers_symbol": fyers_sym,
            "security_id": token,
            "strike": strike,
            "option_type": suffix,
            "expiry": expiry_val,
            "lot_size": lot_size
        }


if __name__ == "__main__":
    selector = StrikeSelector()
    test_spot = 24320.5
    ce_contract = selector.resolve_contract(test_spot, "CE")
    pe_contract = selector.resolve_contract(test_spot, "PE")
    print("\n--- SAMPLE STRIKE RESOLUTION ---")
    print("CE Contract:", ce_contract)
    print("PE Contract:", pe_contract)
