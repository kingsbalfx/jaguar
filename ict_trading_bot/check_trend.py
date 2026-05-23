import os, sys, json
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv()
from execution.mt5_connector import connect
from strategy.pre_trade_analysis import analyze_market_top_down
from config.trading_pairs import TradingPairs

creds = {
    "login": os.getenv("MT5_ACCOUNT_LOGIN"),
    "password": os.getenv("MT5_ACCOUNT_PASSWORD"),
    "server": os.getenv("MT5_ACCOUNT_SERVER"),
} if os.getenv("MT5_ACCOUNT_LOGIN") else None
if not connect(creds):
    print("MT5 connection failed")
    sys.exit(1)

# Test a few well‑known forex pairs
for sym in ["EURUSD", "GBPUSD", "USDJPY"]:
    try:
        import MetaTrader5 as mt5
        tick = mt5.symbol_info_tick(sym)
        price = (tick.ask + tick.bid) / 2.0
        topdown = analyze_market_top_down(sym, price)
        trend = topdown.get("overall_trend", "neutral")
        print(f"{sym}: price={price:.5f}, trend={trend}")
    except Exception as e:
        print(f"{sym}: error={e}")