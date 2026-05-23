# diagnose.py — fixed credential handling
import os, sys, json
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from execution.mt5_connector import connect
from config.trading_pairs import TradingPairs
from strategy.pre_trade_analysis import analyze_market_top_down
from strategy.setup_confirmations import liquidity_sweep_or_swing, bos_setup
from strategy.entry_model import hybrid_entry_model
from config.symbol_mappings import candidates_for

# ---- Connect exactly like main bot ----
login = os.getenv("MT5_ACCOUNT_LOGIN")
if login:
    creds = {
        "login": login,
        "password": os.getenv("MT5_ACCOUNT_PASSWORD"),
        "server": os.getenv("MT5_ACCOUNT_SERVER"),
    }
else:
    creds = None

if not connect(creds):
    print("❌ Could not connect to MT5. Make sure the terminal is running.")
    sys.exit(1)

print("✅ Connected to MT5\n")

# ---- Resolve first 3 tradable symbols ----
pairs = TradingPairs.get_trading_pairs()
symbols = []
for p in pairs[:10]:
    sym = p["symbol"] if isinstance(p, dict) else p
    for cand in [sym] + candidates_for(sym):
        try:
            import MetaTrader5 as mt5
            if mt5.symbol_select(cand, True):
                tick = mt5.symbol_info_tick(cand)
                if tick and tick.bid > 0:
                    symbols.append(cand)
                    break
        except:
            continue
    if len(symbols) >= 3:
        break

print(f"Testing symbols: {symbols}\n")

for sym in symbols:
    try:
        tick = mt5.symbol_info_tick(sym)
        price = tick.bid if tick else 0
        print(f"--- {sym} (price={price}) ---")

        topdown = analyze_market_top_down(sym, price)
        print("  topdown keys:", list(topdown.keys()))
        print("  overall_trend:", topdown.get("overall_trend"))
        mtf = topdown.get("MTF", {})
        print("  MTF swings:", len(mtf.get("swings", [])))
        fib = mtf.get("fib", {})
        print("  MTF fib:", fib if fib else "EMPTY")
        print("  HTF atr:", topdown.get("HTF", {}).get("atr", 0))

        market_data = {
            "trend": topdown.get("overall_trend", "neutral"),
            "price": price,
            "atr": topdown.get("HTF", {}).get("atr", 0),
            "m1_candles": topdown.get("m1_candles", []),
            "m5_candles": topdown.get("m5_candles", []),
        }

        signal = hybrid_entry_model(market_data)
        print("  signal:", "yes" if signal else "no")
        if signal:
            print("    htf_ob:", signal.get("htf_ob"))
            print("    valid_fvg:", signal.get("valid_fvg"))

        direction = "buy" if topdown.get("overall_trend") == "bullish" else "sell"
        liq = liquidity_sweep_or_swing(price, topdown, direction)
        bos = bos_setup(topdown, direction)
        print("  liquidity:", json.dumps(liq, default=str))
        print("  bos:", json.dumps(bos, default=str))
        print()
    except Exception as e:
        print(f"  ❌ Error: {e}\n")
        import traceback
        traceback.print_exc()