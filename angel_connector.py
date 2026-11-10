"""
Angel One SmartAPI Client Connector
Handles automated TOTP session authentication, profile retrieval, and live LTP quotes.
"""
import os
import pyotp
from SmartApi import SmartConnect

class AngelConnector:
    def __init__(self, api_key: str, client_code: str, pin: str, totp_secret: str):
        self.api_key = api_key
        self.client_code = client_code
        self.pin = pin
        self.totp_secret = totp_secret
        self.smart_api = None
        self.auth_token = None
        self.feed_token = None
        self.is_connected = False

    def connect(self) -> bool:
        if not self.api_key or "YOUR_" in self.api_key:
            print("[AUTH] SmartAPI Credentials not configured. Running in Mock/Simulated Connection Mode.")
            self.is_connected = True
            return True

        try:
            totp = pyotp.TOTP(self.totp_secret).now()
            self.smart_api = SmartConnect(api_key=self.api_key)
            session = self.smart_api.generateSession(self.client_code, self.pin, totp)

            if session and session.get("status"):
                self.auth_token = session["data"]["jwtToken"]
                self.feed_token = self.smart_api.getfeedToken()
                self.is_connected = True
                print(f"[AUTH] ✅ Logged into Angel One successfully as {self.client_code}!")
                return True
            else:
                print(f"[AUTH] ❌ Login Failed: {session.get('message', 'Unknown error')}")
                return False
        except Exception as e:
            print(f"[AUTH] ❌ Exception during Angel One authentication: {e}")
            return False

    def get_ltp(self, exchange: str, tradingsymbol: str, symboltoken: str) -> float:
        """Fetches live Last Traded Price (LTP) from Angel One API."""
        if not self.smart_api or not self.is_connected:
            return 0.0
        try:
            data = self.smart_api.ltpData(exchange, tradingsymbol, symboltoken)
            if data and data.get("status"):
                return float(data["data"]["ltp"])
        except Exception:
            pass
        return 0.0

    def place_option_order(self, tradingsymbol: str, symboltoken: str, quantity: int, is_buy: bool = True) -> dict:
        """Places Market Order on NFO through SmartAPI."""
        if not self.smart_api or not self.is_connected:
            return {"status": False, "message": "API not connected"}
        try:
            order_params = {
                "variety": "NORMAL",
                "tradingsymbol": tradingsymbol,
                "symboltoken": symboltoken,
                "transactiontype": "BUY" if is_buy else "SELL",
                "exchange": "NFO",
                "ordertype": "MARKET",
                "producttype": "INTRADAY",
                "duration": "DAY",
                "quantity": str(quantity)
            }
            order_res = self.smart_api.placeOrder(order_params)
            return order_res
        except Exception as e:
            return {"status": False, "message": str(e)}

    def get_rms_funds(self) -> dict:
        """Fetches real account funds and margin limits from Angel One."""
        if not self.smart_api or not self.is_connected:
            return {"available_cash": 0.0, "net": 0.0, "collateral": 0.0}
        try:
            res = self.smart_api.rmsLimit()
            if res and res.get("status") and res.get("data"):
                d = res["data"]
                return {
                    "available_cash": float(d.get("availablecash", 0.0) or 0.0),
                    "net": float(d.get("net", 0.0) or 0.0),
                    "collateral": float(d.get("collateral", 0.0) or 0.0),
                    "m2m_unrealized": float(d.get("m2munrealized", 0.0) or 0.0),
                    "m2m_realized": float(d.get("m2mrealized", 0.0) or 0.0)
                }
        except Exception as e:
            print(f"[ANGEL RMS] Error: {e}")
        return {"available_cash": 0.0, "net": 0.0, "collateral": 0.0}

    def get_all_holdings(self) -> dict:
        """Fetches real user delivery equity share holdings."""
        if not self.smart_api or not self.is_connected:
            return {"holdings": [], "total_holding_value": 0.0, "total_inv_value": 0.0, "total_pnl": 0.0}
        try:
            res = self.smart_api.allholding()
            if res and res.get("status") and res.get("data"):
                d = res["data"]
                raw_h = d.get("holdings", [])
                tot = d.get("totalholding", {})
                clean_holdings = []
                for it in raw_h:
                    q = int(it.get("quantity", 0) or 0) + int(it.get("t1quantity", 0) or 0)
                    avg_p = float(it.get("averageprice", 0.0) or 0.0)
                    ltp = float(it.get("ltp", 0.0) or 0.0)
                    cur_v = round(q * ltp, 2)
                    inv_v = round(q * avg_p, 2)
                    pnl = float(it.get("profitandloss", 0.0) or 0.0)
                    pnl_pct = float(it.get("pnlpercentage", 0.0) or 0.0)
                    clean_holdings.append({
                        "symbol": it.get("tradingsymbol", ""),
                        "exchange": it.get("exchange", "NSE"),
                        "quantity": q,
                        "avg_price": avg_p,
                        "ltp": ltp,
                        "invested": inv_v,
                        "current_value": cur_v,
                        "pnl": pnl,
                        "pnl_pct": pnl_pct
                    })
                return {
                    "holdings": clean_holdings,
                    "total_holding_value": float(tot.get("totalholdingvalue", 0.0) or 0.0),
                    "total_inv_value": float(tot.get("totalinvvalue", 0.0) or 0.0),
                    "total_pnl": float(tot.get("totalprofitandloss", 0.0) or 0.0),
                    "total_pnl_pct": float(tot.get("totalpnlpercentage", 0.0) or 0.0)
                }
        except Exception as e:
            print(f"[ANGEL HOLDINGS] Error: {e}")
        return {"holdings": [], "total_holding_value": 0.0, "total_inv_value": 0.0, "total_pnl": 0.0}

    def get_real_positions(self) -> list:
        """Fetches active real F&O and intraday positions from Angel One."""
        if not self.smart_api or not self.is_connected:
            return []
        try:
            res = self.smart_api.position()
            if res and res.get("status") and res.get("data"):
                return res["data"] or []
        except Exception as e:
            print(f"[ANGEL POSITIONS] Error: {e}")
        return []

    def get_real_trades(self) -> list:
        """Fetches executed real trades today from Angel One."""
        if not self.smart_api or not self.is_connected:
            return []
        try:
            res = self.smart_api.tradeBook()
            if res and res.get("status") and res.get("data"):
                return res["data"] or []
        except Exception as e:
            print(f"[ANGEL TRADEBOOK] Error: {e}")
        return []

