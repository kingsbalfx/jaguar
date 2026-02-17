# =====================================================
# CORE CONNECTION
# =====================================================
from execution.mt5_connector import (
    connect,
    ensure_symbol,
    get_price,
    get_open_positions
)
from config.symbol_mappings import candidates_for
from execution.trade_executor import calculate_lot_size, execute_trade
from execution.order_router import choose_order_type

# =====================================================
# STRATEGY & ANALYSIS
# =====================================================
from strategy.pre_trade_analysis import analyze_market_top_down
from strategy.entry_model import check_entry
from strategy.liquidity_filter import liquidity_taken
from strategy.smt_filter import smt_confirmed

# =====================================================
# RISK & TRADE MANAGEMENT
# =====================================================
from risk.sl_tp_engine import calculate_sl_tp
from risk.protection import can_trade, register_trade, resize_lot
from risk.trade_management import manage_trade

# =====================================================
# QUALITY FILTERS
# =====================================================
from ml.rule_filter import rule_quality_filter
from ml.ml_filter import ml_quality_filter

# =====================================================
# SESSION FILTER
# =====================================================
from utils.sessions import in_london_session, in_newyork_session

# =====================================================
# PORTFOLIO + DASHBOARD
# =====================================================
from portfolio.allocator import allocate_risk
from dashboard.bridge import push_trade, persist_signal_to_supabase
import time
import traceback
import os


# Start internal bot API (health / control) in a background thread
try:
    from bot_api import start_in_thread
    start_in_thread()
except Exception as e:
    print("Failed to start bot API thread:", e)


# =====================================================
# 1️⃣ CONNECT TO MT5
# =====================================================
if os.getenv("MT5_DISABLED", "").lower() in ("1", "true", "yes"):
    print("MT5_DISABLED=1 set. Skipping MT5 connection and trading loop.")
    while True:
        time.sleep(60)

connect()

SYMBOLS = [
    "EURUSD", "GBPUSD", "USDJPY",
    "AUDUSD", "NZDUSD", "USDCAD",
    # added instruments (may require mapping)
    "BTCUSD", "XAUUSD", "AUDJPY", "EURJPY", "ETHBTC"
]

# Validate and resolve symbols using mapping candidates; keep a mapping original->resolved
VALID_SYMBOLS = []
RESOLVED_MAP = {}
for symbol in SYMBOLS:
    resolved = None
    # try direct first, then mapping candidates
    for cand in candidates_for(symbol):
        try:
            ensure_symbol(cand)
            resolved = cand
            break
        except Exception:
            continue

    if resolved:
        VALID_SYMBOLS.append(resolved)
        RESOLVED_MAP[symbol] = resolved
    else:
        print(f"Warning: symbol {symbol} unavailable in MT5 (tried candidates), skipping")

if not VALID_SYMBOLS:
    raise RuntimeError("No valid trading symbols available in MT5. Check account/instruments.")


# =====================================================
# 2️⃣ MAIN EXECUTION LOOP (resilient)
# =====================================================
while True:
    try:
        for symbol in VALID_SYMBOLS:

            # -----------------------------
            # SESSION FILTER (HARD RULE)
            # -----------------------------
            if not (in_london_session() or in_newyork_session()):
                continue

            # -----------------------------
            # LIVE MARKET DATA
            # -----------------------------
            price = get_price(symbol)
            atr = 0.0012
            atr_threshold = 0.002

            # -----------------------------
            # TOP-DOWN ANALYSIS
            # -----------------------------
            analysis = analyze_market_top_down(symbol, price)

            trend = analysis["overall_trend"]
            direction = "buy" if trend == "bullish" else "sell"

            # -----------------------------
            # LIQUIDITY (MANDATORY)
            # -----------------------------
            if not liquidity_taken(
                price,
                analysis["MTF"]["liquidity"],
                direction
            ):
                continue

            # -----------------------------
            # ENTRY MODEL (ICT CORE)
            # -----------------------------
            try:
                signal = check_entry(
                    trend=trend,
                    price=price,
                    fib_levels=analysis.get("MTF", {}).get("fib", {}),
                    fvgs=analysis.get("LTF", {}).get("fvgs", {}),
                    htf_order_blocks=analysis.get("MTF", {}).get("order_blocks", {})
                )
            except Exception as e:
                print("Entry model error, skipping symbol:", e)
                continue

            if not isinstance(signal, dict) or not signal:
                continue

            # attach symbol and direction (use original name mapping if available)
            original_symbol = next((k for k, v in RESOLVED_MAP.items() if v == symbol), symbol)
            signal["symbol"] = original_symbol
            signal["direction"] = direction

            # -----------------------------
            # SMT CONFIRMATION
            # -----------------------------
            if not smt_confirmed(signal, analysis["correlated"]):
                continue

            # -----------------------------
            # RULE QUALITY FILTER
            # -----------------------------
            if not rule_quality_filter(signal):
                continue

            # -----------------------------
            # ML QUALITY FILTER
            # -----------------------------
            features = [
                atr,
                abs(signal["fvg"]["high"] - signal["fvg"]["low"]),
                abs(signal["htf_ob"]["high"] - signal["htf_ob"]["low"]),
                abs(price - analysis["MTF"]["fib"]["0.5"]),
            ]

            model = None  # load trained model
            ml_ok, probability = ml_quality_filter(features, model)

            if not ml_ok:
                continue

            # -----------------------------
            # PROTECTION (ONE TRADE PER OB)
            # -----------------------------
            htf_ob = signal.get("htf_ob") or {}
            ob_id = htf_ob.get("id")
            if not ob_id or not can_trade(symbol, ob_id):
                continue

            # -----------------------------
            # PORTFOLIO RISK ALLOCATION
            # -----------------------------
            open_positions = get_open_positions()
            allowed_risk = allocate_risk(symbol, open_positions)

            if allowed_risk <= 0:
                continue

            # -----------------------------
            # ORDER ROUTING
            # -----------------------------
            order_type = choose_order_type(
                price,
                signal["fvg"],
                mode="auto"
            )

            # -----------------------------
            # SL / TP ENGINE
            # -----------------------------
            sl, tp = calculate_sl_tp(
                direction=direction,
                entry_price=price,
                htf_ob=signal["htf_ob"]
            )

            # -----------------------------
            # POSITION SIZING (DYNAMIC)
            # -----------------------------
            lot = calculate_lot_size(
                symbol=symbol,
                risk_percent=allowed_risk,
                stop_loss_pips=20
            )

            lot = resize_lot(lot, atr, atr_threshold)

            # -----------------------------
            # PERSIST SIGNAL TO SUPABASE (no webhook)
            # -----------------------------
            try:
                persist_signal_to_supabase({
                    "symbol": original_symbol,
                    "direction": direction,
                    "entry": price,
                    "sl": sl,
                    "tp": tp,
                    "lot": lot,
                    "ml_probability": probability,
                    "signal_quality": "premium",
                    "status": "pending",
                })
            except Exception:
                pass

            # -----------------------------
            # EXECUTE TRADE
            # -----------------------------
            trade = execute_trade(
                symbol=symbol,
                direction=direction,
                lot=lot,
                sl_price=sl,
                tp_price=tp,
                order_type=order_type
            )
            register_trade(symbol, ob_id)

            # -----------------------------
            # PUSH TO DASHBOARD
            # -----------------------------
            push_trade({
                "symbol": symbol,
                "direction": direction,
                "entry": price,
                "sl": sl,
                "tp": tp,
                "lot": lot,
                "ml_probability": probability,
                "status": "OPEN"
            })

            # -----------------------------
            # LIVE TRADE MANAGEMENT
            # -----------------------------
            while trade and trade["open"]:
                live_price = get_price(symbol)
                action = manage_trade(trade, live_price)

                if action:
                    trade = execute_trade(**action)
    except Exception as e:
        print("Error in main loop:", e)
        traceback.print_exc()
        time.sleep(5)
        continue
