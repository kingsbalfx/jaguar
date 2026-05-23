import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from dotenv import load_dotenv
load_dotenv()
from execution.mt5_connector import connect
from strategy.pre_trade_analysis import analyze_market_top_down
from strategy.entry_model import hybrid_entry_model

creds = {
    "login": os.getenv("MT5_ACCOUNT_LOGIN"),
    "password": os.getenv("MT5_ACCOUNT_PASSWORD"),
    "server": os.getenv("MT5_ACCOUNT_SERVER"),
} if os.getenv("MT5_ACCOUNT_LOGIN") else None
if not connect(creds):
    print("MT5 connection failed")
    sys.exit(1)

for sym in ["EURUSD", "GBPUSD", "USDJPY"]:
    try:
        import MetaTrader5 as mt5
        tick = mt5.symbol_info_tick(sym)
        price = (tick.ask + tick.bid) / 2.0
        topdown = analyze_market_top_down(sym, price)
        trend = topdown.get("overall_trend")

        market_data = {
            "trend": trend,
            "price": price,
            "atr": topdown.get("HTF", {}).get("atr", 0.0),
            "m1_candles": topdown.get("m1_candles", []),
            "m5_candles": topdown.get("m5_candles", []),
            "swing_low": None,
            "swing_high": None,
            "trend_strength": 0.6,   # <-- force a valid strength
        }
        # Also inject the FVG/OB data from analysis so signal can enrich
        mtf = topdown.get("MTF", {})
        ltf = topdown.get("LTF", {})
        market_data["fvg"] = next(iter(ltf.get("fvgs", [])), None)
        market_data["htf_ob"] = next(iter(mtf.get("order_blocks", [])), None)

        signal = hybrid_entry_model(market_data)
        if signal is None:
            # Check each sub‑condition
            strength = float(market_data.get("trend_strength", 0))
            if strength < 0.45:
                print(f"{sym}: skipped – trend_strength too low ({strength})")
            else:
                print(f"{sym}: signal is None despite valid trend/strength – check internal validation")
        else:
            print(f"{sym}: signal OK – direction={signal.get('direction')}")
    except Exception as e:
        print(f"{sym}: error={e}")