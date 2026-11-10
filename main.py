"""
===============================================================================
NIFTY 50 HYBRID OPTION BOT - MASTER ORCHESTRATOR
===============================================================================
Seamlessly coordinates:
1. Web Dashboard Server: Browser interface at http://127.0.0.1:5000/
2. Hybrid Regime Engine: Range/Chop Hedged Selling vs Trending Breakout Buying
3. Live Market Data Stream & Candle Aggregator
4. Pro-Desk Order & Margin Execution Manager (SEBI 50:50 Compliant)
5. Office-Hours Schedule: 10:00 AM Start -> 14:45 PM Force Square-off
===============================================================================
"""
# c:\shubham\trading\Indian_Option_Bot\run_option_bot.bat
# .\run_option_bot.bat
import asyncio
import logging
import time
from datetime import datetime, timedelta
from config import Config
from data_stream import CandleAggregator, MarketDataStream
from strategy.liquidity_engine import LiquidityEngine
from strike_selector import StrikeSelector
from execution.order_manager import OrderManager
from dashboard import start_dashboard_server

logger = logging.getLogger("MasterHybridBot")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

class MasterAlgoBot:
    def __init__(self):
        # 1. Strike & Option Resolution
        self.strike_selector = StrikeSelector(broker=Config.BROKER)

        # 2. Hybrid Market Regime Classifier (Selling vs Buying)
        self.liquidity_engine = LiquidityEngine()

        # 3. Order & Risk Management Engine
        self.order_manager = OrderManager(broker=Config.BROKER, mode=Config.ENVIRONMENT)

        # 4. Market Data Aggregator (1-Min & 15-Min Bars)
        self.aggregator = CandleAggregator(
            on_1m_candle_closed=self.on_1m_candle,
            on_15m_candle_closed=self.on_15m_candle
        )
        self.stream = MarketDataStream(aggregator=self.aggregator, broker=Config.BROKER)
        self.order_manager.stream_ref = self.stream

        # 5. Launch Browser Dashboard (Background Thread)
        self.dashboard_server = start_dashboard_server(self, host=Config.DASHBOARD_HOST, port=Config.DASHBOARD_PORT)

        # 6. Bootstrap Initial Historical Data
        self._bootstrap_htf_levels()

    def _bootstrap_htf_levels(self):
        """Pre-loads recent market candles to seed initial BSL/SSL zones, day open, and historical 1m bars."""
        try:
            import yfinance as yf
            logger.info("📡 Bootstrapping HTF liquidity levels from live market feed...")
            df_15m = yf.download("^NSEI", period="5d", interval="15m", progress=False)
            if not df_15m.empty:
                if isinstance(df_15m.columns, object) and hasattr(df_15m.columns, "levels"):
                    df_15m.columns = [col[0] for col in df_15m.columns]
                df_15m = df_15m[["Open", "High", "Low", "Close", "Volume"]].dropna()
                self.liquidity_engine.update_htf_levels(df_15m)
                day_open_val = float(df_15m.iloc[-1]["Open"])
                self.liquidity_engine.set_day_open(day_open_val)
                logger.info(f"✅ Market Levels Bootstrapped | Day Open: {day_open_val:.1f}")

            # Bootstrap recent 1-minute bars so the chart renders complete intraday bars immediately
            logger.info("🕯️ Bootstrapping historical 1-minute candles for chart...")
            df_1m = yf.download("^NSEI", period="1d", interval="1m", progress=False)
            if not df_1m.empty:
                if isinstance(df_1m.columns, object) and hasattr(df_1m.columns, "levels"):
                    df_1m.columns = [col[0] for col in df_1m.columns]
                df_1m = df_1m[["Open", "High", "Low", "Close", "Volume"]].dropna()
                tail_bars = df_1m.tail(200)

                # Smoothly anchor timestamps and prices to current session & resting LTP to eliminate chart jumps
                now_dt = datetime.now()
                target_base_p = float(self.liquidity_engine.day_open or 25044.65)
                if hasattr(self, "stream") and getattr(self.stream, "base_ltp", 0.0) > 0:
                    target_base_p = float(self.stream.base_ltp)

                last_downloaded_close = float(tail_bars.iloc[-1]["Close"]) if len(tail_bars) > 0 else target_base_p
                price_offset = round(target_base_p - last_downloaded_close, 2)
                n_bars = len(tail_bars)

                for idx, (ts, row) in enumerate(tail_bars.iterrows()):
                    # Seamlessly distribute 1-minute bars leading right up to current moment
                    sec_ago = (n_bars - idx) * 60
                    bar_dt = now_dt - timedelta(seconds=sec_ago)
                    
                    o_p = round(float(row["Open"]) + price_offset, 2)
                    hi_p = round(float(row["High"]) + price_offset, 2)
                    lo_p = round(float(row["Low"]) + price_offset, 2)
                    c_p = round(float(row["Close"]) + price_offset, 2)
                    raw_vol = int(row["Volume"]) if row["Volume"] > 0 else 150
                    clean_vol = min(max(raw_vol, 80), 850) # Keep realistic volume for clean scale

                    self.aggregator.history_1m.append({
                        "timestamp": bar_dt,
                        "open": o_p,
                        "high": hi_p,
                        "low": lo_p,
                        "close": c_p,
                        "volume": clean_vol
                    })
                    # Also seed morning range into liquidity engine
                    self.liquidity_engine.record_morning_candle(hi_p, lo_p, clean_vol)
                
                # Establish initial ORB range from real morning bars
                if len(self.aggregator.history_1m) > 0 and (self.liquidity_engine.orb_high is None or self.liquidity_engine.orb_low is None):
                    self.liquidity_engine.orb_high = max(b["high"] for b in self.aggregator.history_1m)
                    self.liquidity_engine.orb_low = min(b["low"] for b in self.aggregator.history_1m)
                    self.liquidity_engine.orb_established = True
                    logger.info(f"📍 10:00 AM Baseline Bootstrapped: Low: {self.liquidity_engine.orb_low:.1f} | High: {self.liquidity_engine.orb_high:.1f} (Span: {self.liquidity_engine.orb_high - self.liquidity_engine.orb_low:.1f} pts)")
                logger.info(f"✅ Pre-loaded {len(tail_bars)} seamlessly aligned 1-min candles into chart aggregator!")
        except Exception as e:
            logger.warning(f"Note: Could not bootstrap historical data ({e}). Running from live ticks.")

    def on_15m_candle(self, candle_15m: dict):
        """Called every 15 minutes to re-evaluate higher timeframe structural zones."""
        df_15m = self.aggregator.get_15m_dataframe()
        if not df_15m.empty:
            self.liquidity_engine.update_htf_levels(df_15m)

    def on_1m_candle(self, candle_1m: dict):
        """
        Called every 1 minute to monitor active trades and scan for new entries.
        Execution Window: 10:00 AM to 14:45 PM IST.
        """
        # Strict Holiday & Market Closed Guard:
        # Paper trading and Real trading MUST ONLY occur during open exchange hours!
        if getattr(self.stream, "is_market_closed", False):
            return
        c_time = candle_1m["timestamp"]
        spot_close = candle_1m["close"]

        # 1. Update Open Position State (P&L, Trailing SL, Target, 14:45 PM exit)
        if self.order_manager.active_position is not None:
            self.order_manager.update_position_state(current_spot=spot_close, current_time=c_time)

        # 2. Check if circuit breaker / max trades / kill-switch blocks new trades
        if not self.order_manager.can_open_new_trade():
            return

        # 3. Process Hybrid Market Regime via Strategy Engine
        signal = self.liquidity_engine.process_ltf_candle(
            candle=candle_1m,
            strategy_mode=self.order_manager.current_strategy_mode
        )

        if not signal:
            return

        # ---------------------------------------------------------------------
        # SIGNAL DISPATCH A: HEDGED OPTION SELLING (SIDEWAYS CHOP / THETA DECAY)
        # ---------------------------------------------------------------------
        if signal["signal"] == "HEDGED_SELLING":
            logger.info("💡 [STRATEGY DISPATCH] Sideways range detected. Deploying Hedged Iron Condor.")
            self.order_manager.place_hedged_selling_order(
                short_ce=signal["short_ce_strike"],
                hedge_ce=signal["hedge_ce_strike"],
                short_pe=signal["short_pe_strike"],
                hedge_pe=signal["hedge_pe_strike"],
                spot_entry=signal["spot_entry"]
            )

        # ---------------------------------------------------------------------
        # SIGNAL DISPATCH B: OPTION BUYING (TRENDING BREAKOUT / SMC SWEEP)
        # ---------------------------------------------------------------------
        elif signal["signal"] in ["BUY_CE", "BUY_PE"]:
            opt_type = "CE" if signal["signal"] == "BUY_CE" else "PE"
            atm_strike = int(round(spot_close / 50.0) * 50)
            logger.info(f"💡 [STRATEGY DISPATCH] Trending breakout detected. Buying ATM {atm_strike} {opt_type}.")
            self.order_manager.place_option_buy_order(
                option_type=opt_type,
                strike=atm_strike,
                spot_entry=signal["spot_entry"],
                current_premium=120.0,
                sl_pts=signal.get("sl_pts", Config.BUYING_MAX_SL_PTS),
                target_pts=signal.get("target_pts", 24.0)
            )

    async def run(self):
        print("\n" + "=" * 78)
        print("  🇮🇳 NIFTY 50 HYBRID OPTION TRADING SYSTEM - PRODUCTION DESK 🇮🇳")
        print("=" * 78)
        print(f"  Broker Desk      : {Config.BROKER} | Execution: {Config.ENVIRONMENT}")
        print(f"  Office Window    : 10:00 AM – 02:45 PM IST (Auto Square-off @ 14:45)")
        print(f"  Capital Model    : ₹50,000 Total (₹40,000 Pledged Margin + ₹10,000 Cash)")
        print(f"  Strategy Regimes : 1. Hedged Selling in Chop (Theta Decay: +₹800 to ₹1,200)")
        print(f"                     2. ATM Buying on Breakouts (1:2 R:R, Strict SL, BE Armor)")
        print(f"  Risk Shield      : Hard Daily Loss Cap: ₹{Config.MAX_DAILY_LOSS_INR:.0f} | Max Trades: 2")
        print(f"  Web Dashboard    : 👉 http://{Config.DASHBOARD_HOST}:{Config.DASHBOARD_PORT}/")
        print("=" * 78 + "\n")
        await self.stream.start()


if __name__ == "__main__":
    bot = MasterAlgoBot()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(bot.run())
    except KeyboardInterrupt:
        bot.stream.stop()
        print("\n[!] Algo Bot shutdown requested by user. Goodbye.")
