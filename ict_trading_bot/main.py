# =====================================================
# CORE CONNECTION
# =====================================================
from dotenv import load_dotenv
from execution.mt5_connector import (
    connect,
    reconnect,
    ensure_symbol,
    get_price,
    get_open_positions,
    get_account_snapshot,
)
from config.symbol_mappings import candidates_for
from execution.trade_executor import calculate_lot_size, execute_trade, apply_trade_action
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
from fundamentals.news_filter import news_allows_trade

# =====================================================
# SESSION FILTER
# =====================================================
from utils.sessions import in_london_session, in_newyork_session

# =====================================================
# PORTFOLIO + DASHBOARD
# =====================================================
from portfolio.allocator import allocate_risk
from dashboard.bridge import push_trade, persist_signal_to_supabase, persist_log_to_supabase
from utils.mt5_credentials import fetch_mt5_credentials_signature
import time
import traceback
import os
from bot_state import (
    is_running,
    consume_restart_request,
    set_connection,
    update_metrics,
    append_log,
)

load_dotenv()


def bot_log(event, message, payload=None, persist=True):
    entry = payload or {}
    print(f"[BOT] {message}")
    append_log(event, message, entry)
    if persist:
        try:
            persist_log_to_supabase(event, {"message": message, **entry})
        except Exception:
            pass


def publish_runtime_metrics(symbols=None):
    try:
        positions = get_open_positions()
        account = get_account_snapshot() or {}
        update_metrics(
            open_positions=len(positions),
            floating_profit=round(sum(float(p.get("profit") or 0) for p in positions), 2),
            balance=account.get("balance"),
            equity=account.get("equity"),
            margin_free=account.get("margin_free"),
            symbols=symbols or [],
        )
        set_connection(True, None, account)
    except Exception as metric_error:
        set_connection(False, str(metric_error), None)


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
    bot_log("mt5_disabled", "MT5 is disabled. Bot API will stay online without live trading.", persist=False)
    while True:
        time.sleep(60)

SYMBOLS = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "NZDUSD", "USDCAD",
    "USDCHF", "EURGBP", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY",
    "GBPCHF", "EURCHF", "EURAUD", "GBPAUD",
    "XAUUSD", "XAGUSD", "BTCUSD", "ETHUSD",
]

def resolve_symbols():
    # Validate and resolve symbols using mapping candidates; keep a mapping original->resolved
    valid = []
    resolved_map = {}
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
            valid.append(resolved)
            resolved_map[symbol] = resolved
        else:
            bot_log(
                "symbol_unavailable",
                f"Symbol {symbol} unavailable in MT5. Skipping it.",
                {"symbol": symbol},
                persist=False,
            )

    if not valid:
        raise RuntimeError("No valid trading symbols available in MT5. Check account/instruments.")

    return valid, resolved_map


AUTO_SYNC_INTERVAL = int(os.getenv("MT5_AUTO_SYNC_INTERVAL", "15"))
fallback_allowed = os.getenv("MT5_FALLBACK_API_ONLY", "true").lower() in ("1", "true", "yes")
VALID_SYMBOLS = []
RESOLVED_MAP = {}
CONNECTED = False
LAST_CREDENTIAL_SIGNATURE = None


def ensure_connected(force_reconnect=False):
    global VALID_SYMBOLS, RESOLVED_MAP, CONNECTED, LAST_CREDENTIAL_SIGNATURE

    connector = reconnect if force_reconnect else connect
    connector()
    VALID_SYMBOLS, RESOLVED_MAP = resolve_symbols()
    LAST_CREDENTIAL_SIGNATURE = fetch_mt5_credentials_signature()
    CONNECTED = True
    publish_runtime_metrics(list(VALID_SYMBOLS))
    account = get_account_snapshot() or {}
    bot_log(
        "mt5_connected",
        f"MT5 connected for account {account.get('login')} on {account.get('server')}.",
        {
            "account_login": account.get("login"),
            "server": account.get("server"),
            "balance": account.get("balance"),
            "symbols": list(VALID_SYMBOLS),
        },
    )


try:
    ensure_connected()
except Exception as e:
    set_connection(False, str(e), None)
    if fallback_allowed:
        bot_log("mt5_connect_failed", f"MT5 connect failed: {e}", {"error": str(e)})
    else:
        raise


# =====================================================
# 2️⃣ MAIN EXECUTION LOOP (resilient)
# =====================================================
last_sync_check = 0.0
last_metrics_refresh = 0.0
last_idle_summary = 0.0
skip_stats = {}
while True:
    try:
        now = time.time()
        restart_requested = consume_restart_request()

        if restart_requested:
            try:
                ensure_connected(force_reconnect=True)
                bot_log("mt5_reconnect", "MT5 reconnect completed.")
            except Exception as e:
                CONNECTED = False
                set_connection(False, str(e), None)
                bot_log("mt5_reconnect_failed", f"MT5 reconnect failed: {e}", {"error": str(e)})
                time.sleep(5)
                continue

        if now - last_sync_check >= AUTO_SYNC_INTERVAL:
            last_sync_check = now
            try:
                latest_signature = fetch_mt5_credentials_signature()
                credentials_changed = (
                    LAST_CREDENTIAL_SIGNATURE is not None
                    and latest_signature != LAST_CREDENTIAL_SIGNATURE
                )

                if not CONNECTED or credentials_changed:
                    ensure_connected(force_reconnect=CONNECTED or credentials_changed)
                    if credentials_changed:
                        bot_log("credentials_synced", "MT5 credentials changed in Supabase. Reconnected automatically.")
            except Exception as e:
                CONNECTED = False
                set_connection(False, str(e), None)
                if fallback_allowed:
                    bot_log("mt5_sync_failed", f"MT5 sync/reconnect failed: {e}", {"error": str(e)})
                else:
                    raise

        if not CONNECTED:
            time.sleep(1)
            continue

        if now - last_metrics_refresh >= 5:
            publish_runtime_metrics(list(VALID_SYMBOLS))
            last_metrics_refresh = now

        if not is_running():
            time.sleep(1)
            continue

        if now - last_idle_summary >= 30:
            metrics_positions = len(get_open_positions())
            skip_summary = ", ".join(f"{key}={value}" for key, value in sorted(skip_stats.items()))
            heartbeat_message = f"Bot is scanning {len(VALID_SYMBOLS)} symbols. Open positions: {metrics_positions}."
            if skip_summary:
                heartbeat_message += f" Skip reasons: {skip_summary}."
            bot_log(
                "bot_heartbeat",
                heartbeat_message,
                {
                    "symbols": list(VALID_SYMBOLS),
                    "open_positions": metrics_positions,
                    "skip_stats": dict(skip_stats),
                },
                persist=False,
            )
            skip_stats = {}
            last_idle_summary = now

        for symbol in VALID_SYMBOLS:

            # -----------------------------
            # SESSION FILTER (HARD RULE)
            # -----------------------------
            if not (in_london_session() or in_newyork_session()):
                skip_stats["session"] = skip_stats.get("session", 0) + 1
                continue

            original_symbol = next((k for k, v in RESOLVED_MAP.items() if v == symbol), symbol)

            # -----------------------------
            # FUNDAMENTALS / NEWS FILTER
            # -----------------------------
            if os.getenv("NEWS_FILTER_ENABLED", "true").lower() in ("1", "true", "yes"):
                if not news_allows_trade(original_symbol):
                    skip_stats["fundamentals"] = skip_stats.get("fundamentals", 0) + 1
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
                skip_stats["liquidity"] = skip_stats.get("liquidity", 0) + 1
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
                skip_stats["entry_error"] = skip_stats.get("entry_error", 0) + 1
                continue

            if not isinstance(signal, dict) or not signal:
                skip_stats["entry"] = skip_stats.get("entry", 0) + 1
                continue

            # attach symbol and direction (use original name mapping if available)
            signal["symbol"] = original_symbol
            signal["direction"] = direction
            signal["trend"] = trend

            # -----------------------------
            # SMT CONFIRMATION
            # -----------------------------
            if not smt_confirmed(signal, analysis["correlated"]):
                skip_stats["smt"] = skip_stats.get("smt", 0) + 1
                continue

            # -----------------------------
            # RULE QUALITY FILTER
            # -----------------------------
            if not rule_quality_filter(signal):
                skip_stats["rule_quality"] = skip_stats.get("rule_quality", 0) + 1
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
                skip_stats["ml"] = skip_stats.get("ml", 0) + 1
                continue

            # -----------------------------
            # PROTECTION (ONE TRADE PER OB)
            # -----------------------------
            htf_ob = signal.get("htf_ob") or {}
            ob_id = htf_ob.get("id")
            if not ob_id or not can_trade(symbol, ob_id):
                skip_stats["protection"] = skip_stats.get("protection", 0) + 1
                continue

            # -----------------------------
            # PORTFOLIO RISK ALLOCATION
            # -----------------------------
            open_positions = get_open_positions()
            allowed_risk = allocate_risk(symbol, open_positions)

            if allowed_risk <= 0:
                skip_stats["risk"] = skip_stats.get("risk", 0) + 1
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

            bot_log(
                "signal_detected",
                f"Signal detected on {original_symbol} ({direction}).",
                {
                    "symbol": original_symbol,
                    "direction": direction,
                    "entry": price,
                    "sl": sl,
                    "tp": tp,
                    "probability": probability,
                },
            )

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
            if not trade:
                skip_stats["trade_failed"] = skip_stats.get("trade_failed", 0) + 1
                bot_log(
                    "trade_failed",
                    f"Trade execution failed for {original_symbol}.",
                    {"symbol": original_symbol, "direction": direction},
                )
                continue
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
            bot_log(
                "trade_opened",
                f"Trade opened on {original_symbol} ({direction}) with lot {lot}.",
                {
                    "symbol": original_symbol,
                    "direction": direction,
                    "lot": lot,
                    "entry": price,
                    "sl": sl,
                    "tp": tp,
                },
            )
            publish_runtime_metrics(list(VALID_SYMBOLS))

            # -----------------------------
            # LIVE TRADE MANAGEMENT
            # -----------------------------
            while trade and trade.get("open"):
                live_price = get_price(symbol)
                action = manage_trade(trade, live_price)

                if action:
                    trade = apply_trade_action(trade, action)
                    bot_log(
                        "trade_update",
                        f"Trade update on {original_symbol}: {action.get('action')}.",
                        {
                            "symbol": original_symbol,
                            "action": action,
                            "live_price": live_price,
                        },
                        persist=False,
                    )
                else:
                    break
    except Exception as e:
        set_connection(False, str(e), None)
        bot_log("main_loop_error", f"Error in main loop: {e}", {"error": str(e)})
        traceback.print_exc()
        time.sleep(5)
        continue
