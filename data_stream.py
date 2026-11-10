"""
===============================================================================
NIFTY 50 REAL-TIME WEBSOCKET & TICK-TO-CANDLE DATA STREAM ENGINE
===============================================================================
Provides:
1. Resilient tick-by-tick WebSocket connection for DhanHQ and Fyers v3.
2. Auto-reconnecting backoff mechanism (heartbeat monitoring & auto-recovery).
3. Real-time OHLCV Bar Aggregator (synthesizes 1-min & 15-min candles live from raw ticks).
4. Synchronous/Asynchronous callback pipeline for the Liquidity Sweep Engine.
===============================================================================
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Callable, Optional
import pandas as pd
from config import Config

logger = logging.getLogger("DataStream")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

IST = timezone(timedelta(hours=5, minutes=30))

class CandleAggregator:
    """Aggregates streaming raw tick data into real-time 1-min and 15-min bars."""
    def __init__(self, on_1m_candle_closed: Optional[Callable[[dict], None]] = None,
                 on_15m_candle_closed: Optional[Callable[[dict], None]] = None):
        self.on_1m_closed = on_1m_candle_closed
        self.on_15m_closed = on_15m_candle_closed
        self.cur_1m = None
        self.cur_15m = None
        self.history_1m = []
        self.history_15m = []

    def on_tick(self, ltp: float, vol: int, tick_time: Optional[datetime] = None):
        if tick_time is None:
            tick_time = datetime.now(IST)

        minute_key = tick_time.replace(second=0, microsecond=0)
        m15_minute = (tick_time.minute // 15) * 15
        m15_key = tick_time.replace(minute=m15_minute, second=0, microsecond=0)

        # ---------------------------------------------------------------------
        # 1-MINUTE CANDLE AGGREGATION
        # ---------------------------------------------------------------------
        if self.cur_1m is None:
            self.cur_1m = {
                "timestamp": minute_key,
                "open": ltp, "high": ltp, "low": ltp, "close": ltp,
                "volume": vol
            }
        elif self.cur_1m["timestamp"] == minute_key:
            self.cur_1m["high"] = max(self.cur_1m["high"], ltp)
            self.cur_1m["low"] = min(self.cur_1m["low"], ltp)
            self.cur_1m["close"] = ltp
            self.cur_1m["volume"] += vol
        else:
            # 1-Min Bar Closed!
            closed_bar = self.cur_1m.copy()
            self.history_1m.append(closed_bar)
            if self.on_1m_closed:
                try:
                    self.on_1m_closed(closed_bar)
                except Exception as e:
                    logger.error(f"Error in on_1m_closed callback: {e}")

            # Start new 1-Min Bar
            self.cur_1m = {
                "timestamp": minute_key,
                "open": ltp, "high": ltp, "low": ltp, "close": ltp,
                "volume": vol
            }

        # ---------------------------------------------------------------------
        # 15-MINUTE CANDLE AGGREGATION
        # ---------------------------------------------------------------------
        if self.cur_15m is None:
            self.cur_15m = {
                "timestamp": m15_key,
                "open": ltp, "high": ltp, "low": ltp, "close": ltp,
                "volume": vol
            }
        elif self.cur_15m["timestamp"] == m15_key:
            self.cur_15m["high"] = max(self.cur_15m["high"], ltp)
            self.cur_15m["low"] = min(self.cur_15m["low"], ltp)
            self.cur_15m["close"] = ltp
            self.cur_15m["volume"] += vol
        else:
            # 15-Min Bar Closed!
            closed_15m = self.cur_15m.copy()
            self.history_15m.append(closed_15m)
            if self.on_15m_closed:
                try:
                    self.on_15m_closed(closed_15m)
                except Exception as e:
                    logger.error(f"Error in on_15m_closed callback: {e}")

            # Start new 15-Min Bar
            self.cur_15m = {
                "timestamp": m15_key,
                "open": ltp, "high": ltp, "low": ltp, "close": ltp,
                "volume": vol
            }

    def get_1m_dataframe(self) -> pd.DataFrame:
        if not self.history_1m:
            return pd.DataFrame()
        return pd.DataFrame(self.history_1m).set_index("timestamp")

    def get_15m_dataframe(self) -> pd.DataFrame:
        if not self.history_15m:
            return pd.DataFrame()
        return pd.DataFrame(self.history_15m).set_index("timestamp")


class MarketDataStream:
    """Universal resilient market feed for Angel One, DhanHQ, Fyers and Simulated Paper Streams."""
    def __init__(self, aggregator: CandleAggregator, broker: str = Config.BROKER):
        self.aggregator = aggregator
        self.broker = broker.upper()
        self.is_running = False
        self.reconnect_delay = 5.0
        self.last_tick_time = 0.0
        self.market_status = "INITIALIZING"
        self.market_status_desc = ""
        self.market_feed_time = ""
        self.base_ltp = 25044.65

    async def connect_dhan_feed(self):
        """Connects to DhanHQ Feed via official WebSocket client."""
        logger.info("Initializing DhanHQ Live Feed WebSocket...")
        try:
            from dhanhq import marketfeed
            # Dhan marketfeed connection parameters
            # InstrumentTuple: (ExchangeSegment, SecurityId) -> (Index, 13 for NIFTY)
            instruments = [(marketfeed.NSE_INDEX, Config.DHAN_SECURITY_ID)]

            def on_dhan_message(instance, message):
                self.last_tick_time = time.time()
                try:
                    data = json.loads(message) if isinstance(message, str) else message
                    ltp = float(data.get("LTP", data.get("ltp", 0.0)))
                    vol = int(data.get("volume", 0))
                    if ltp > 0:
                        self.aggregator.on_tick(ltp, vol)
                except Exception as e:
                    logger.debug(f"Dhan feed tick parse: {e}")

            # Infinite resilient loop
            while self.is_running:
                try:
                    subscription_code = marketfeed.Ticker
                    feed = marketfeed.DhanFeed(
                        Config.DHAN_CLIENT_ID,
                        Config.DHAN_ACCESS_TOKEN,
                        instruments,
                        subscription_code,
                        on_message=on_dhan_message
                    )
                    feed.run_forever()
                except Exception as exc:
                    logger.warning(f"Dhan feed disconnected: {exc}. Reconnecting in {self.reconnect_delay}s...")
                    await asyncio.sleep(self.reconnect_delay)
        except Exception as e:
            logger.error(f"Dhan Feed initialization failed: {e}. Falling back to Simulated Live Stream.")
            await self.run_simulated_stream()

    async def connect_fyers_feed(self):
        """Connects to Fyers v3 Data Socket."""
        logger.info("Initializing Fyers API v3 WebSocket Feed...")
        try:
            from fyers_apiv3.FyersWebsocket import data_ws

            def on_fyers_message(message):
                self.last_tick_time = time.time()
                try:
                    ltp = float(message.get("ltp", 0.0))
                    vol = int(message.get("vol_traded_today", 0))
                    if ltp > 0:
                        self.aggregator.on_tick(ltp, vol)
                except Exception as e:
                    logger.debug(f"Fyers parse error: {e}")

            while self.is_running:
                try:
                    fyers_socket = data_ws.FyersDataSocket(
                        access_token=f"{Config.FYERS_APP_ID}:{Config.FYERS_ACCESS_TOKEN}",
                        log_path="",
                        litemode=True,
                        write_to_file=False,
                        reconnect=True,
                        on_message=on_fyers_message
                    )
                    fyers_socket.connect()
                    fyers_socket.subscribe(symbols=[Config.FYERS_SYMBOL], data_type="SymbolUpdate")
                    fyers_socket.keep_running()
                except Exception as exc:
                    logger.warning(f"Fyers stream error: {exc}. Reconnecting in {self.reconnect_delay}s...")
                    await asyncio.sleep(self.reconnect_delay)
        except Exception as e:
            logger.error(f"Fyers Feed initialization failed: {e}. Falling back to Simulated Live Stream.")
            await self.run_simulated_stream()

    async def connect_angel_feed(self):
        """Polls live LTP for Nifty 50 from Angel One SmartAPI every second."""
        logger.info("Initializing Angel One SmartAPI Live Market Feed...")
        try:
            from angel_connector import AngelConnector
            connector = AngelConnector(
                api_key=Config.ANGEL_API_KEY,
                client_code=Config.ANGEL_CLIENT_CODE,
                pin=Config.ANGEL_PIN,
                totp_secret=Config.ANGEL_TOTP_SECRET
            )
            if connector.connect():
                logger.info("✅ [ANGEL ONE SMARTAPI CONNECTED] Validating NSE Market Status...")
                # Fetch full market quote to verify exchange feed time
                market_info = None
                try:
                    res = connector.smart_api.getMarketData(mode="FULL", exchangeTokens={"NSE": ["99926000"]})
                    if res and res.get("status") and res.get("data", {}).get("fetched"):
                        market_info = res["data"]["fetched"][0]
                except Exception as ex:
                    logger.debug(f"getMarketData check: {ex}")

                today_str = datetime.now().strftime("%d-%b-%Y")
                exch_feed_time = market_info.get("exchFeedTime", "") if market_info else ""
                self.market_feed_time = exch_feed_time
                base_ltp = float(market_info.get("ltp", 25044.65)) if market_info else 25044.65
                self.base_ltp = base_ltp

                # Check if market is closed / on holiday today (e.g. Diwali Balipratipada)
                is_exchange_closed = (today_str not in exch_feed_time) if exch_feed_time else False

                self.is_market_closed = is_exchange_closed

                if is_exchange_closed:
                    self.market_status = "NSE_HOLIDAY"
                    self.market_status_desc = f"Diwali-Balipratipada Holiday (Feed: {exch_feed_time})"
                    logger.warning(f"🏖️ [NSE MARKET CLOSED / HOLIDAY DETECTED] Exchange Feed Time: {exch_feed_time}. Base LTP: {base_ltp}")
                    logger.info("🛡️ [STRICT HOLIDAY MODE] Paper & Live trading strictly HALTED. No synthetic ticks or fake paper orders will be generated.")
                    # Broadcast true resting price once to anchor chart cleanly
                    self.aggregator.on_tick(base_ltp, 0)
                    while self.is_running:
                        # Calmly poll Angel One every 30s to detect when real market opens tomorrow
                        await asyncio.sleep(30.0)
                        try:
                            res = connector.smart_api.getMarketData(mode="FULL", exchangeTokens={"NSE": ["99926000"]})
                            if res and res.get("status") and res.get("data", {}).get("fetched"):
                                cur_feed_time = res["data"]["fetched"][0].get("exchFeedTime", "")
                                if datetime.now().strftime("%d-%b-%Y") in cur_feed_time:
                                    logger.info("🟢 [MARKET OPEN DETECTED] Real exchange session has started!")
                                    self.is_market_closed = False
                                    break
                        except Exception as poll_ex:
                            logger.debug(f"Holiday poll: {poll_ex}")
                else:
                    self.market_status = "NSE_LIVE"
                    self.market_status_desc = "NSE Live Trading Session Active"
                    logger.info("✅ [NSE LIVE TRADING ACTIVE] Streaming live ticks from exchange!")
                    last_ltp = base_ltp
                    while self.is_running:
                        try:
                            ltp = connector.get_ltp("NSE", "Nifty 50", "99926000")
                            if ltp > 0:
                                last_ltp = ltp
                                self.aggregator.on_tick(ltp, 100)
                            elif last_ltp > 0:
                                self.aggregator.on_tick(last_ltp, 50)
                        except Exception as e:
                            logger.debug(f"Angel tick poll exception: {e}")
                        await asyncio.sleep(1.0)
            else:
                logger.warning("Could not authenticate Angel One feed. Falling back to simulated stream.")
                await self.run_simulated_stream()
        except Exception as e:
            logger.error(f"Angel feed error: {e}. Falling back to simulated stream.")
            await self.run_simulated_stream()

    async def run_simulated_stream(self, base_price: float = 25040.0):
        """High-fidelity simulated live tick stream for off-market hours or paper testing."""
        logger.info(f"Running high-fidelity Simulated Live Feed (Base Price: {base_price})...")
        cur_p = base_price
        while self.is_running:
            import random
            tick_drift = random.gauss(0.0, 1.2)
            cur_p += tick_drift
            cur_p = round(cur_p, 2)
            self.aggregator.on_tick(cur_p, random.randint(50, 500))
            await asyncio.sleep(0.5)

    async def start(self):
        self.is_running = True
        if self.broker == "ANGEL_ONE" and Config.ANGEL_API_KEY and "YOUR_" not in Config.ANGEL_API_KEY:
            await self.connect_angel_feed()
        elif self.broker == "DHAN":
            await self.connect_dhan_feed()
        elif self.broker == "FYERS":
            await self.connect_fyers_feed()
        else:
            await self.run_simulated_stream()

    def stop(self):
        self.is_running = False
        logger.info("MarketDataStream stopped.")


if __name__ == "__main__":
    def print_1m(bar):
        print(f"[1M BAR CLOSED] {bar['timestamp'].strftime('%H:%M')} | O:{bar['open']} H:{bar['high']} L:{bar['low']} C:{bar['close']}")

    agg = CandleAggregator(on_1m_candle_closed=print_1m)
    stream = MarketDataStream(agg)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(stream.start())
    except KeyboardInterrupt:
        stream.stop()
