# =====================================================
# CORE CONNECTION
# =====================================================
from dotenv import load_dotenv
import sys
from config.trading_pairs import TradingPairs
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
from strategy.entry_model import check_entry, explain_entry_failure
from strategy.smt_filter import smt_confirmed
from strategy.setup_confirmations import bos_setup, liquidity_sweep_or_swing

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
from backtest.approval import ensure_setup_backtest_approval
from backtest.setup_occurrence import build_setup_signature

# =====================================================
# SESSION FILTER
# =====================================================
from utils.sessions import in_london_session, in_newyork_session, trading_session_open

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

if (
    os.getenv("MULTI_ACCOUNT_ENABLED", "false").lower() in ("1", "true", "yes", "on")
    and os.getenv("MULTI_ACCOUNT_CHILD", "false").lower() not in ("1", "true", "yes", "on")
):
    from multi_account_runner import main as run_multi_account_supervisor

    run_multi_account_supervisor()
    sys.exit(0)


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

DEFAULT_SYMBOLS = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "NZDUSD", "USDCAD",
    "USDCHF", "EURGBP", "EURJPY", "GBPJPY", "AUDJPY", "CADJPY",
    "GBPCHF", "EURCHF", "EURAUD", "GBPAUD",
    "XAUUSD", "XAGUSD",
] + TradingPairs.CRYPTO


def load_symbols():
    raw = os.getenv("SYMBOLS", "").strip()
    requested = [item.strip().upper() for item in raw.split(",") if item.strip()] if raw else DEFAULT_SYMBOLS
    out = []
    for symbol in requested:
        if symbol not in out:
            out.append(symbol)
    return out


SYMBOLS = load_symbols()

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
    symbol_map = {original: resolved for original, resolved in RESOLVED_MAP.items()}
    bot_log(
        "mt5_connected",
        f"MT5 connected for account {account.get('login')} on {account.get('server')}.",
        {
            "account_login": account.get("login"),
            "server": account.get("server"),
            "balance": account.get("balance"),
            "symbols": list(VALID_SYMBOLS),
            "symbol_map": symbol_map,
        },
    )
    bot_log(
        "symbol_resolution",
        "Resolved trading symbols for this broker.",
        {"symbol_map": symbol_map},
        persist=False,
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
skip_examples = {}
stage_hits = {}
stage_examples = {}


def record_skip(reason, symbol):
    skip_stats[reason] = skip_stats.get(reason, 0) + 1
    examples = skip_examples.setdefault(reason, [])
    if symbol not in examples and len(examples) < 5:
        examples.append(symbol)


def record_stage(stage, symbol):
    stage_hits[stage] = stage_hits.get(stage, 0) + 1
    examples = stage_examples.setdefault(stage, [])
    if symbol not in examples and len(examples) < 5:
        examples.append(symbol)


def get_order_block_id(symbol, htf_ob):
    if not isinstance(htf_ob, dict):
        return None

    explicit = htf_ob.get("id")
    if explicit:
        return str(explicit)

    parts = [
        symbol,
        htf_ob.get("timeframe"),
        htf_ob.get("type"),
        htf_ob.get("index"),
        htf_ob.get("high"),
        htf_ob.get("low"),
    ]
    normalized = [str(part) for part in parts if part is not None]
    if not normalized:
        return None
    return "|".join(normalized)


def build_signal_features(signal, price, analysis, atr):
    fvg = signal.get("fvg") or {}
    htf_ob = signal.get("htf_ob") or {}
    fib_mid = analysis.get("MTF", {}).get("fib", {}).get("0.5", price)

    if isinstance(fvg, dict) and fvg.get("high") is not None and fvg.get("low") is not None:
        fvg_span = abs(float(fvg["high"]) - float(fvg["low"]))
    else:
        fvg_span = 0.0

    if isinstance(htf_ob, dict) and htf_ob.get("high") is not None and htf_ob.get("low") is not None:
        ob_span = abs(float(htf_ob["high"]) - float(htf_ob["low"]))
    else:
        ob_span = 0.0

    return [
        atr,
        fvg_span,
        ob_span,
        abs(price - fib_mid),
    ]


MIN_EXTRA_CONFIRMATIONS = max(3, int(os.getenv("MIN_EXTRA_CONFIRMATIONS", "3")))
STRICT_NEWS_FILTER = os.getenv("NEWS_FILTER_STRICT", "false").lower() in ("1", "true", "yes")
COUNT_FUNDAMENTALS_AS_CONFIRMATION = os.getenv("COUNT_FUNDAMENTALS_AS_CONFIRMATION", "false").lower() in ("1", "true", "yes")
RULE_QUALITY_REQUIRED = os.getenv("RULE_QUALITY_REQUIRED", "false").lower() in ("1", "true", "yes")
REQUIRE_BOS_CONFIRMATION = os.getenv("REQUIRE_BOS_CONFIRMATION", "true").lower() in ("1", "true", "yes")
REQUIRE_LIQUIDITY_SWING_CONFIRMATION = os.getenv("REQUIRE_LIQUIDITY_SWING_CONFIRMATION", "true").lower() in ("1", "true", "yes")


def build_execution_context(signal, analysis, confirmation_flags, confirmation_threshold):
    timeframes = analysis.get("timeframes", {"HTF": "H4", "MTF": "H1", "LTF": "M15"})
    timeframe_trends = {
        "HTF": analysis.get("HTF", {}).get("trend"),
        "MTF": analysis.get("MTF", {}).get("trend"),
        "LTF": analysis.get("LTF", {}).get("trend"),
    }
    met_confirmations = [name for name, passed in confirmation_flags.items() if passed]
    setup_context = signal.get("setup_context") or {}
    return {
        "topdown_trend": signal.get("trend"),
        "timeframes": timeframes,
        "timeframe_trends": timeframe_trends,
        "confirmation_threshold": confirmation_threshold,
        "confirmations_met": met_confirmations,
        "fib_zone": signal.get("fib_zone"),
        "fvg_timeframe": (signal.get("fvg") or {}).get("timeframe"),
        "order_block_timeframe": (signal.get("htf_ob") or {}).get("timeframe"),
        "bos": setup_context.get("bos"),
        "liquidity": setup_context.get("liquidity"),
    }


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

        session_open = trading_session_open()
        if not session_open:
            if now - last_idle_summary >= 30:
                metrics_positions = len(get_open_positions())
                bot_log(
                    "bot_heartbeat",
                    f"Bot is online but outside the configured session window. Open positions: {metrics_positions}. Set TRADE_ALL_SESSIONS=true to trade all day.",
                    {
                        "symbols": list(VALID_SYMBOLS),
                        "open_positions": metrics_positions,
                        "session_open": False,
                    },
                    persist=False,
                )
                last_idle_summary = now
            time.sleep(15)
            continue

        if now - last_idle_summary >= 30:
            metrics_positions = len(get_open_positions())
            skip_summary = ", ".join(f"{key}={value}" for key, value in sorted(skip_stats.items()))
            heartbeat_message = f"Bot is scanning {len(VALID_SYMBOLS)} symbols. Open positions: {metrics_positions}."
            if skip_summary:
                heartbeat_message += f" Skip reasons: {skip_summary}."
            if skip_examples:
                examples_summary = "; ".join(
                    f"{key}={', '.join(values)}" for key, values in sorted(skip_examples.items()) if values
                )
                if examples_summary:
                    heartbeat_message += f" Examples: {examples_summary}."
            if stage_hits:
                stage_summary = "; ".join(
                    f"{key}={stage_hits[key]} ({', '.join(stage_examples.get(key, []))})"
                    for key in sorted(stage_hits.keys())
                    if stage_hits.get(key)
                )
                if stage_summary:
                    heartbeat_message += f" Passed stages: {stage_summary}."
            bot_log(
                "bot_heartbeat",
                heartbeat_message,
                {
                    "symbols": list(VALID_SYMBOLS),
                    "open_positions": metrics_positions,
                    "skip_stats": dict(skip_stats),
                    "skip_examples": dict(skip_examples),
                    "stage_hits": dict(stage_hits),
                    "stage_examples": dict(stage_examples),
                },
                persist=False,
            )
            skip_stats = {}
            skip_examples = {}
            stage_hits = {}
            stage_examples = {}
            last_idle_summary = now

        for symbol in VALID_SYMBOLS:

            # -----------------------------
            # SESSION FILTER (HARD RULE)
            # -----------------------------
            original_symbol = next((k for k, v in RESOLVED_MAP.items() if v == symbol), symbol)
            record_stage("seen", original_symbol)

            # -----------------------------
            # FUNDAMENTALS / NEWS FILTER
            # -----------------------------
            fundamentals_ok = True
            if os.getenv("NEWS_FILTER_ENABLED", "true").lower() in ("1", "true", "yes"):
                fundamentals_ok = news_allows_trade(original_symbol)
                if not fundamentals_ok and STRICT_NEWS_FILTER:
                    record_skip("fundamentals", original_symbol)
                    continue
            if fundamentals_ok:
                record_stage("fundamentals", original_symbol)

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
            if trend not in ("bullish", "bearish"):
                record_skip("topdown", original_symbol)
                continue
            record_stage("topdown", original_symbol)
            direction = "buy" if trend == "bullish" else "sell"

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
                record_skip("entry_error", original_symbol)
                continue

            if not isinstance(signal, dict) or not signal:
                entry_reason = explain_entry_failure(
                    trend=trend,
                    price=price,
                    fib_levels=analysis.get("MTF", {}).get("fib", {}),
                    fvgs=analysis.get("LTF", {}).get("fvgs", {}),
                    htf_order_blocks=analysis.get("MTF", {}).get("order_blocks", {}),
                )
                record_skip(f"entry_{entry_reason}", original_symbol)
                continue
            record_stage("entry", original_symbol)

            # attach symbol and direction (use original name mapping if available)
            signal["symbol"] = original_symbol
            signal["direction"] = direction
            signal["trend"] = trend

            liquidity_state = liquidity_sweep_or_swing(price, analysis, direction)
            if liquidity_state["confirmed"]:
                record_stage("liquidity_setup", original_symbol)
            else:
                record_skip("liquidity_setup", original_symbol)
                if REQUIRE_LIQUIDITY_SWING_CONFIRMATION:
                    continue

            bos_state = bos_setup(analysis, trend)
            if bos_state["confirmed"]:
                record_stage("bos", original_symbol)
            else:
                record_skip("bos", original_symbol)
                if REQUIRE_BOS_CONFIRMATION:
                    continue

            signal["setup_context"] = {
                "liquidity": liquidity_state,
                "bos": bos_state,
            }

            smt_ok = smt_confirmed(signal, analysis["correlated"])
            if smt_ok:
                record_stage("smt", original_symbol)
            else:
                record_skip("smt", original_symbol)

            rule_ok = rule_quality_filter(signal)
            if rule_ok:
                record_stage("rule_quality", original_symbol)
            else:
                record_skip("rule_quality", original_symbol)
                if RULE_QUALITY_REQUIRED:
                    continue

            # -----------------------------
            # ML QUALITY FILTER
            # -----------------------------
            features = build_signal_features(signal, price, analysis, atr)

            model = None  # load trained model
            ml_ok, probability = ml_quality_filter(features, model)

            if ml_ok:
                record_stage("ml", original_symbol)
            else:
                record_skip("ml", original_symbol)

            confirmation_flags = {
                "liquidity_setup": liquidity_state["confirmed"],
                "bos": bos_state["confirmed"],
                "smt": smt_ok,
                "rule_quality": rule_ok,
                "ml": ml_ok,
            }
            if COUNT_FUNDAMENTALS_AS_CONFIRMATION:
                confirmation_flags["fundamentals"] = fundamentals_ok

            extra_confirmations = sum(1 for passed in confirmation_flags.values() if passed)
            if extra_confirmations < MIN_EXTRA_CONFIRMATIONS:
                record_skip("confirmations", original_symbol)
                continue
            record_stage("confirmations", original_symbol)

            setup_signature = build_setup_signature(signal, analysis, confirmation_flags)
            backtest_approved, backtest_details = ensure_setup_backtest_approval(
                symbol,
                setup_signature=setup_signature,
                report_key=original_symbol,
            )
            if not backtest_approved:
                record_skip("backtest", original_symbol)
                continue
            record_stage("backtest", original_symbol)

            # -----------------------------
            # PROTECTION (ONE TRADE PER OB)
            # -----------------------------
            htf_ob = signal.get("htf_ob") or {}
            ob_id = get_order_block_id(symbol, htf_ob)
            if not ob_id or not can_trade(symbol, ob_id):
                record_skip("protection", original_symbol)
                continue
            record_stage("protection", original_symbol)

            # -----------------------------
            # PORTFOLIO RISK ALLOCATION
            # -----------------------------
            open_positions = get_open_positions()
            allowed_risk = allocate_risk(symbol, open_positions)

            if allowed_risk <= 0:
                record_skip("risk", original_symbol)
                continue
            record_stage("risk", original_symbol)

            # -----------------------------
            # ORDER ROUTING
            # -----------------------------
            order_type = choose_order_type(
                price,
                signal.get("fvg"),
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
                    "bot_id": os.getenv("BOT_ID") or os.getenv("BOT_INSTANCE_ID") or "windows_mt5_bot",
                    "symbol": original_symbol,
                    "direction": direction,
                    "entry": price,
                    "sl": sl,
                    "tp": tp,
                    "lot": lot,
                    "ml_probability": probability,
                    "signal_quality": "premium",
                    "reason": build_execution_context(signal, analysis, confirmation_flags, MIN_EXTRA_CONFIRMATIONS),
                    "status": "pending",
                })
            except Exception:
                pass

            execution_context = build_execution_context(
                signal,
                analysis,
                confirmation_flags,
                MIN_EXTRA_CONFIRMATIONS,
            )
            execution_context["backtest"] = backtest_details
            bot_log(
                "signal_detected",
                (
                    f"Signal detected on {original_symbol} ({direction}). "
                    f"Top-down {execution_context['timeframes']['HTF']}/"
                    f"{execution_context['timeframes']['MTF']}/"
                    f"{execution_context['timeframes']['LTF']} trends: "
                    f"{execution_context['timeframe_trends']['HTF']}/"
                    f"{execution_context['timeframe_trends']['MTF']}/"
                    f"{execution_context['timeframe_trends']['LTF']}. "
                    f"Confirmations met: {', '.join(execution_context['confirmations_met']) or 'none'}. "
                    f"Backtest status: {execution_context['backtest'].get('reason')}."
                ),
                {
                    "symbol": original_symbol,
                    "direction": direction,
                    "entry": price,
                    "sl": sl,
                    "tp": tp,
                    "probability": probability,
                    **execution_context,
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
                record_skip("trade_failed", original_symbol)
                bot_log(
                    "trade_failed",
                    f"Trade execution failed for {original_symbol}.",
                    {"symbol": original_symbol, "direction": direction},
                )
                continue
            record_stage("trade_opened", original_symbol)
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
                (
                    f"Trade opened on {original_symbol} ({direction}) with lot {lot}. "
                    f"Top-down trend {execution_context['topdown_trend']} across "
                    f"{execution_context['timeframes']['HTF']}/"
                    f"{execution_context['timeframes']['MTF']}/"
                    f"{execution_context['timeframes']['LTF']}. "
                    f"Confirmations used: {', '.join(execution_context['confirmations_met']) or 'none'}."
                ),
                {
                    "symbol": original_symbol,
                    "direction": direction,
                    "lot": lot,
                    "entry": price,
                    "sl": sl,
                    "tp": tp,
                    **execution_context,
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
