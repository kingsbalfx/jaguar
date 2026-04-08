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
from utils.symbol_profile import (
    LIQUID_FOREX,
    LIQUID_METALS,
    LIQUID_CRYPTO,
    infer_asset_class,
)
from risk.intelligence_system import get_cis_decision
from config.symbol_mappings import candidates_for
from execution.trade_executor import calculate_lot_size, execute_trade, apply_trade_action
from execution.order_router import choose_order_type

# =====================================================
# STRATEGY & ANALYSIS
# =====================================================
from strategy.pre_trade_analysis import analyze_market_top_down
from strategy.entry_model import check_entry, explain_entry_failure
from strategy.weighted_entry_validator import (
    calculate_entry_confidence,
    should_execute_immediately,
    should_skip_signal,
    format_confidence_report,
    calculate_smart_risk_params,
)
from strategy.smt_filter import smt_confirmed
from strategy.setup_confirmations import (
    bos_setup,
    evaluate_confirmation_quality,
    liquidity_sweep_or_swing,
    price_action_setup,
)

# =====================================================
# RISK & TRADE MANAGEMENT
# =====================================================
from risk.sl_tp_engine import calculate_sl_tp
from risk.protection import can_trade, register_trade
from risk.trade_management import manage_trade
from risk.intelligent_execution import (
    calculate_precise_winning_rate,
    calculate_dynamic_lot_size,
    calculate_intelligent_stop_loss,
    record_trade_outcome,
    should_take_trade,
    get_market_intelligence_report,
    get_intelligent_recommendation,
    record_skip_detailed,
    get_skip_pattern_analysis,
    get_skip_statistics_report,
    should_skip_symbol_entirely,
    get_learned_threshold_adjustment,
    learn_from_repeated_skips,
    load_intelligent_stats,
)
from risk.intelligent_sync import sync_intelligent_stats_to_supabase, sync_trade_outcome_to_supabase
from risk.profitability_guard import (
    evaluate_profitability_guard,
    normalize_rr_after_sl_adjustment,
)
from risk.strategy_memory import get_strategy_adaptation

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
from dashboard.bridge import (
    push_trade,
    persist_signal_to_supabase,
    persist_log_to_supabase,
    persist_account_snapshot_to_supabase,
)
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


def get_trading_session():
    """Determine current active session name."""
    from utils.sessions import in_london_session, in_newyork_session
    if in_london_session():
        return "london"
    if in_newyork_session():
        return "newyork"
    return "other"


def extract_setup_types(signal):
    """Normalize the live signal into strategy-memory setup tags."""
    setup_types = []
    setup_context = (signal or {}).get("setup_context", {})

    if setup_context.get("liquidity", {}).get("confirmed"):
        setup_types.append("liquidity")
    if setup_context.get("bos", {}).get("confirmed"):
        setup_types.append("bos")
    if setup_context.get("price_action", {}).get("confirmed"):
        setup_types.append("price_action")
    if (signal or {}).get("fvg"):
        setup_types.append("fvg")
    if (signal or {}).get("htf_ob"):
        setup_types.append("order_block")

    return setup_types or ["unknown"]


LAST_ACCOUNT_SNAPSHOT_SYNC = 0


def build_asset_scan_breakdown(symbols):
    breakdown = {"forex": 0, "metals": 0, "crypto": 0, "other": 0}
    for item in symbols or []:
        asset_class = infer_asset_class(item)
        if asset_class not in breakdown:
            asset_class = "other"
        breakdown[asset_class] += 1
    return breakdown


def publish_runtime_metrics(symbols=None):
    global LAST_ACCOUNT_SNAPSHOT_SYNC
    try:
        symbols = symbols or []
        positions = get_open_positions()
        account = get_account_snapshot() or {}
        floating_profit = round(sum(float(p.get("profit") or 0) for p in positions), 2)
        asset_breakdown = build_asset_scan_breakdown(symbols)
        update_metrics(
            open_positions=len(positions),
            floating_profit=floating_profit,
            balance=account.get("balance"),
            equity=account.get("equity"),
            margin_free=account.get("margin_free"),
            symbols=symbols,
            asset_scan=asset_breakdown,
        )
        set_connection(True, None, account)

        interval = max(10, int(os.getenv("ACCOUNT_SNAPSHOT_SYNC_INTERVAL", "30")))
        now = time.time()
        if now - LAST_ACCOUNT_SNAPSHOT_SYNC >= interval:
            persist_account_snapshot_to_supabase(
                {
                    "bot_id": os.getenv("PERSISTENT_BOT_ID") or os.getenv("BOT_ID"),
                    "user_id": os.getenv("BOT_USER_ID") or os.getenv("SIGNAL_USER_ID"),
                    "user_email": os.getenv("BOT_USER_EMAIL"),
                    "account_login": account.get("login"),
                    "server": account.get("server"),
                    "balance": account.get("balance"),
                    "equity": account.get("equity"),
                    "floating_profit": floating_profit,
                    "open_positions": len(positions),
                    "margin_free": account.get("margin_free"),
                    "currency": account.get("currency"),
                    "company": account.get("company"),
                    "symbols_count": len(symbols),
                    "asset_scan": asset_breakdown,
                    "symbols": symbols,
                    "unavailable_symbols": list(UNAVAILABLE_SYMBOLS),
                }
            )
            LAST_ACCOUNT_SNAPSHOT_SYNC = now
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

DEFAULT_SYMBOLS = LIQUID_FOREX + LIQUID_METALS + LIQUID_CRYPTO


def load_symbols():
    raw = os.getenv("SYMBOLS", "").strip()
    requested = [item.strip().upper() for item in raw.split(",") if item.strip()] if raw else DEFAULT_SYMBOLS
    out = []
    for symbol in requested:
        if symbol not in out:
            out.append(symbol)
    return out


SYMBOLS = load_symbols()
UNAVAILABLE_SYMBOLS = []

def resolve_symbols():
    # Validate and resolve symbols using mapping candidates; keep a mapping original->resolved
    global UNAVAILABLE_SYMBOLS
    valid = []
    resolved_map = {}
    unavailable = []
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
            unavailable.append(symbol)
            bot_log(
                "symbol_unavailable",
                f"Symbol {symbol} unavailable in MT5. Skipping it.",
                {"symbol": symbol},
                persist=False,
            )

    if not valid:
        raise RuntimeError("No valid trading symbols available in MT5. Check account/instruments.")

    UNAVAILABLE_SYMBOLS = unavailable
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
    asset_breakdown = build_asset_scan_breakdown(VALID_SYMBOLS)
    bot_log(
        "mt5_connected",
        f"MT5 connected for account {account.get('login')} on {account.get('server')}.",
        {
            "account_login": account.get("login"),
            "server": account.get("server"),
            "balance": account.get("balance"),
            "symbols": list(VALID_SYMBOLS),
            "asset_scan": asset_breakdown,
            "unavailable_symbols": list(UNAVAILABLE_SYMBOLS),
            "symbol_map": symbol_map,
        },
    )
    bot_log(
        "symbol_resolution",
        "Resolved trading symbols for this broker.",
        {
            "symbol_map": symbol_map,
            "asset_scan": asset_breakdown,
            "unavailable_symbols": list(UNAVAILABLE_SYMBOLS),
        },
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
_bot_state = {}  # Module-level state for tracking timers


def record_skip(reason, symbol, confidence=0.0, analysis=None):
    """Legacy wrapper - now calls persistent skip tracking."""
    skip_stats[reason] = skip_stats.get(reason, 0) + 1
    examples = skip_examples.setdefault(reason, [])
    if symbol not in examples and len(examples) < 5:
        examples.append(symbol)

    # ALSO save to persistent storage (survives network disruption!)
    record_skip_detailed(reason, symbol, confidence=confidence, analysis=analysis)


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
WEIGHTED_CONFIRMATION_DIRECT_EXECUTION = os.getenv("WEIGHTED_CONFIRMATION_DIRECT_EXECUTION", "true").lower() in ("1", "true", "yes")
WEIGHTED_CONFIRMATION_BACKTEST_FALLBACK = os.getenv("WEIGHTED_CONFIRMATION_BACKTEST_FALLBACK", "true").lower() in ("1", "true", "yes")
FOUR_CONFIRMATION_DIRECT_EXECUTION = os.getenv("FOUR_CONFIRMATION_DIRECT_EXECUTION", "true").lower() in ("1", "true", "yes")
FOUR_CONFIRMATION_DIRECT_MIN_COUNT = max(4, int(os.getenv("FOUR_CONFIRMATION_DIRECT_MIN_COUNT", "4")))
ANALYSIS_RESCUE_MIN_CONFIDENCE = max(0.0, min(100.0, float(os.getenv("ANALYSIS_RESCUE_MIN_CONFIDENCE", "65"))))
ANALYSIS_RESCUE_REQUIRES_INTELLIGENCE = os.getenv(
    "ANALYSIS_RESCUE_REQUIRES_INTELLIGENCE",
    "true",
).lower() in ("1", "true", "yes")


def build_execution_context(
    signal,
    analysis,
    confirmation_flags,
    confirmation_threshold,
    confirmation_summary=None,
    execution_route=None,
    decision_bundle=None,
):
    timeframes = analysis.get(
        "timeframes",
        {"DAILY": "D1", "H4": "H4", "HTF": "H1", "MTF": "M30", "LTF": "M15", "EXECUTION": "M5"},
    )
    brief_context = analysis.get("brief_context") or {}
    daily_state = analysis.get("DAILY") or brief_context.get("daily") or {}
    h4_state = analysis.get("H4_CONTEXT") or brief_context.get("h4") or {}
    timeframe_trends = {
        "DAILY": daily_state.get("trend"),
        "H4": h4_state.get("trend"),
        "HTF": analysis.get("HTF", {}).get("trend"),
        "MTF": analysis.get("MTF", {}).get("trend"),
        "LTF": analysis.get("LTF", {}).get("trend"),
        "EXECUTION": analysis.get("EXECUTION", {}).get("trend"),
    }
    met_confirmations = [name for name, passed in confirmation_flags.items() if _confirmation_passed(passed)]
    setup_context = signal.get("setup_context") or {}
    context = {
        "topdown_trend": signal.get("trend"),
        "timeframes": timeframes,
        "timeframe_trends": timeframe_trends,
        "brief_context_alignment": brief_context.get("alignment"),
        "confirmation_threshold": confirmation_threshold,
        "confirmation_count": len(met_confirmations),
        "confirmation_score": float((confirmation_summary or {}).get("score", 0.0)),
        "confirmation_score_required": float((confirmation_summary or {}).get("min_score", 0.0)),
        "confirmation_weighted_flags": (confirmation_summary or {}).get("weighted_flags") or {},
        "confirmations_met": met_confirmations,
        "execution_route": execution_route or "unknown",
        "weighted_direct_alignment": signal.get("weighted_direct_alignment"),
        "four_confirmation_direct_alignment": signal.get("four_confirmation_direct_alignment"),
        "four_confirmation_direct_threshold": FOUR_CONFIRMATION_DIRECT_MIN_COUNT,
        "fib_zone": signal.get("fib_zone"),
        "fvg_timeframe": (signal.get("fvg") or {}).get("timeframe"),
        "order_block_timeframe": (signal.get("htf_ob") or {}).get("timeframe"),
        "bos": setup_context.get("bos"),
        "liquidity": setup_context.get("liquidity"),
        "price_action": setup_context.get("price_action"),
    }
    if decision_bundle:
        context["decision_source"] = decision_bundle.get("decision_source")
        context["engine_agreement"] = decision_bundle.get("engine_agreement")
        context["analysis_pass"] = decision_bundle.get("analysis_pass")
        context["weighted_pass"] = decision_bundle.get("weighted_pass")
        context["intelligence_pass"] = decision_bundle.get("intelligence_pass")
        context["weighted_intelligence_pass"] = decision_bundle.get("weighted_intelligence_pass")
    return context


def _confirmation_passed(flag):
    if isinstance(flag, bool):
        return flag
    if isinstance(flag, dict):
        return bool(flag.get("confirmed", flag.get("passed", False)))
    return False


def build_classic_trade_analysis(
    symbol,
    trend,
    signal,
    confirmation_flags,
    confirmation_summary,
):
    """
    Classic trade analysis engine.

    This keeps the original top-down + entry + confirmation logic alive as a
    separate decision family that can rescue trades when the weighted engine is
    too strict, and vice versa.
    """
    met_flags = list((confirmation_summary or {}).get("met_flags") or [])
    score = float((confirmation_summary or {}).get("score", 0.0))
    min_score = float((confirmation_summary or {}).get("min_score", 0.0))
    asset_class = (confirmation_summary or {}).get("asset_class", "other")
    structure_hits = sum(
        1
        for name in ("liquidity_setup", "bos", "price_action")
        if _confirmation_passed((confirmation_flags or {}).get(name))
    )
    topdown_ok = trend in ("bullish", "bearish")
    signal_ok = isinstance(signal, dict) and bool(signal)
    order_block_ok = bool((signal or {}).get("htf_ob"))
    direction_ok = (signal or {}).get("direction") in ("buy", "sell")
    score_ratio = min(1.0, score / max(min_score, 1.0)) if min_score > 0 else 0.0
    structure_ratio = structure_hits / 3.0
    confirmation_ratio = min(1.0, len(met_flags) / max(FOUR_CONFIRMATION_DIRECT_MIN_COUNT, 1))

    result = {
        "symbol": symbol,
        "asset_class": asset_class,
        "decision": False,
        "confidence": 0.0,
        "score": round(score, 2),
        "threshold": round(min_score, 2),
        "confirmation_count": len(met_flags),
        "required_confirmations": MIN_EXTRA_CONFIRMATIONS,
        "met_flags": met_flags,
        "structure_hits": structure_hits,
        "execution_route": "skip",
        "backtest_required": True,
        "factors": [],
    }

    if not topdown_ok:
        result["factors"].append("Classic analysis rejected: topdown trend is not directional")
        return result
    if not signal_ok:
        result["factors"].append("Classic analysis rejected: entry model did not produce a signal")
        return result
    if not order_block_ok:
        result["factors"].append("Classic analysis rejected: HTF order block confirmation missing")
        return result
    if not direction_ok:
        result["factors"].append("Classic analysis rejected: signal direction is incomplete")
        return result

    result["factors"].append(f"Classic score {score:.1f}/{min_score:.1f} across {len(met_flags)} confirmations")
    result["factors"].append(f"Structure confirmations: {structure_hits}/3")

    if score < min_score:
        result["factors"].append("Classic analysis rejected: weighted confirmation score is below the asset-class minimum")
        return result

    if len(met_flags) < MIN_EXTRA_CONFIRMATIONS:
        result["factors"].append(
            f"Classic analysis rejected: only {len(met_flags)} confirmations, need {MIN_EXTRA_CONFIRMATIONS}"
        )
        return result

    if structure_hits < 2:
        result["factors"].append("Classic analysis rejected: not enough structure agreement (need at least 2 of 3)")
        return result

    confidence = min(
        0.99,
        0.45 + (score_ratio * 0.20) + (structure_ratio * 0.20) + (confirmation_ratio * 0.15),
    )

    direct_ready = (
        FOUR_CONFIRMATION_DIRECT_EXECUTION
        and len(met_flags) >= FOUR_CONFIRMATION_DIRECT_MIN_COUNT
        and structure_hits >= 2
    )

    if direct_ready:
        confidence = max(confidence, 0.82)
        result["decision"] = True
        result["confidence"] = round(confidence, 2)
        result["execution_route"] = "standard"
        result["backtest_required"] = False
        result["factors"].append("Classic analysis approved: direct execution via multi-confirmation agreement")
        return result

    confidence = max(confidence, 0.68)
    result["decision"] = True
    result["confidence"] = round(confidence, 2)
    result["execution_route"] = "conservative"
    result["backtest_required"] = True
    result["factors"].append("Classic analysis approved: execute with backtest validation")
    return result


def build_hybrid_trade_decision(
    symbol,
    confidence_data,
    confirmation_score_value,
    signal,
    trend,
    confirmation_flags,
    confirmation_summary,
):
    weighted_route = confidence_data.get("execution_route", "skip")
    weighted_pass = not should_skip_signal(weighted_route)
    intelligence_pass, intelligence_analysis = should_take_trade(
        symbol,
        confirmation_score_value,
        weighted_route,
    )
    classic_analysis = build_classic_trade_analysis(
        symbol=symbol,
        trend=trend,
        signal=signal,
        confirmation_flags=confirmation_flags,
        confirmation_summary=confirmation_summary,
    )

    weighted_intelligence_pass = weighted_pass and intelligence_pass
    analysis_pass = classic_analysis["decision"]
    analysis_rescue_allowed = (
        analysis_pass
        and confirmation_score_value >= ANALYSIS_RESCUE_MIN_CONFIDENCE
        and (
            intelligence_pass
            or not ANALYSIS_RESCUE_REQUIRES_INTELLIGENCE
        )
    )

    if weighted_intelligence_pass and analysis_pass:
        decision_source = "analysis_and_weighted_intelligence"
        engine_agreement = "both_passed"
        effective_execution_route = weighted_route
        backtest_required = bool(
            confidence_data.get("backtest_required", True) and classic_analysis.get("backtest_required", True)
        )
        execute = True
        skip_reason = None
    elif weighted_intelligence_pass:
        decision_source = "weighted_intelligence_only"
        engine_agreement = "weighted_intelligence_rescue"
        effective_execution_route = weighted_route
        backtest_required = bool(confidence_data.get("backtest_required", True))
        execute = True
        skip_reason = None
    elif analysis_rescue_allowed:
        decision_source = "analysis_only"
        engine_agreement = "analysis_rescue"
        effective_execution_route = classic_analysis.get("execution_route", "conservative")
        backtest_required = bool(classic_analysis.get("backtest_required", True))
        execute = True
        skip_reason = None
    else:
        decision_source = "none"
        if analysis_pass and not intelligence_pass:
            engine_agreement = "analysis_blocked_by_intelligence"
            skip_reason = "intelligence"
        elif analysis_pass and confirmation_score_value < ANALYSIS_RESCUE_MIN_CONFIDENCE:
            engine_agreement = "analysis_blocked_by_weighted_confidence"
            skip_reason = "weighted_confidence"
        else:
            engine_agreement = "both_failed"
            skip_reason = "hybrid_reject"
        effective_execution_route = "skip"
        backtest_required = False
        execute = False

    reasons = []
    if weighted_intelligence_pass:
        reasons.append("weighted+intelligence approved")
    else:
        reasons.append("weighted+intelligence rejected")
    if analysis_pass:
        reasons.append("classic analysis approved")
    else:
        reasons.append("classic analysis rejected")
    if analysis_pass and not analysis_rescue_allowed and not weighted_intelligence_pass:
        reasons.append(
            f"classic rescue blocked: intelligence={intelligence_pass}, "
            f"weighted_confidence={confirmation_score_value:.1f}, "
            f"required={ANALYSIS_RESCUE_MIN_CONFIDENCE:.1f}"
        )

    return {
        "execute": execute,
        "skip_reason": skip_reason,
        "decision_source": decision_source,
        "engine_agreement": engine_agreement,
        "effective_execution_route": effective_execution_route,
        "backtest_required": backtest_required,
        "weighted_route": weighted_route,
        "weighted_pass": weighted_pass,
        "intelligence_pass": intelligence_pass,
        "weighted_intelligence_pass": weighted_intelligence_pass,
        "analysis_pass": analysis_pass,
        "classic_analysis": classic_analysis,
        "intelligence_analysis": intelligence_analysis,
        "reasons": reasons,
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
        trade_all_day = os.getenv("TRADE_ALL_SESSIONS", "false").lower() in ("1", "true", "yes")

        if not session_open and not trade_all_day:
            if now - last_idle_summary >= 30:
                metrics_positions = len(get_open_positions())
                asset_breakdown = build_asset_scan_breakdown(VALID_SYMBOLS)
                bot_log(
                    "bot_heartbeat",
                    f"Bot is online but outside primary sessions. "
                    f"Scanning forex={asset_breakdown['forex']}, metals={asset_breakdown['metals']}, "
                    f"crypto={asset_breakdown['crypto']}, other={asset_breakdown['other']}. "
                    f"Open positions: {metrics_positions}. "
                    "Set TRADE_ALL_SESSIONS=true to trade 24/5 with Session IQ.",
                    {
                        "symbols": list(VALID_SYMBOLS),
                        "asset_scan": asset_breakdown,
                        "unavailable_symbols": list(UNAVAILABLE_SYMBOLS),
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
            asset_breakdown = build_asset_scan_breakdown(VALID_SYMBOLS)
            heartbeat_message = (
                f"Bot is scanning {len(VALID_SYMBOLS)} symbols "
                f"(forex={asset_breakdown['forex']}, metals={asset_breakdown['metals']}, "
                f"crypto={asset_breakdown['crypto']}, other={asset_breakdown['other']}). "
                f"Open positions: {metrics_positions}."
            )
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
            route_summary = []
            if stage_hits.get("weighted_intelligence_pass"):
                route_summary.append(f"weighted_intelligence={stage_hits['weighted_intelligence_pass']}")
            if stage_hits.get("analysis_pass"):
                route_summary.append(f"classic_analysis={stage_hits['analysis_pass']}")
            if stage_hits.get("dual_engine_agreement"):
                route_summary.append(f"dual_agreement={stage_hits['dual_engine_agreement']}")
            if stage_hits.get("analysis_rescue"):
                route_summary.append(f"analysis_rescue={stage_hits['analysis_rescue']}")
            if stage_hits.get("weighted_intelligence_rescue"):
                route_summary.append(f"weighted_rescue={stage_hits['weighted_intelligence_rescue']}")
            if route_summary:
                heartbeat_message += f" Execution routes: {', '.join(route_summary)}."

            # Sync local intelligence to Supabase periodically
            try:
                sync_intelligent_stats_to_supabase(load_intelligent_stats())
            except Exception:
                pass

            # Add symbol stats to heartbeat
            try:
                from risk.symbol_stats import get_symbol_summary
                symbol_summary = get_symbol_summary()
                if symbol_summary:
                    heartbeat_message += f" Symbol Performance: {symbol_summary}"
            except Exception:
                pass

            # Add intelligent execution report (every 60 seconds)
            if '_last_intel_report' not in _bot_state:
                _bot_state['_last_intel_report'] = 0

            now_for_intel = time.time()
            if now_for_intel - _bot_state['_last_intel_report'] >= 120:  # Every 2 minutes
                try:
                    intel_report = get_market_intelligence_report(list(VALID_SYMBOLS))
                    bot_log(
                        "market_intelligence",
                        intel_report,
                        {"report": "comprehensive_market_analysis"},
                        persist=True,
                    )
                    _bot_state['_last_intel_report'] = now_for_intel
                except Exception as e:
                    pass  # Silently fail if intelligence report fails

            bot_log(
                "bot_heartbeat",
                heartbeat_message,
                {
                    "symbols": list(VALID_SYMBOLS),
                    "asset_scan": asset_breakdown,
                    "unavailable_symbols": list(UNAVAILABLE_SYMBOLS),
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

            # ===================================
            # SKIP ENTIRELY FILTER (LEARNED FROM SKIP PATTERNS)
            # ===================================
            # DISABLED: Pattern learning blacklist removed in favor of weighted entry validation
            # The new weighted entry system is more intelligent and doesn't require symbol blacklisting
            # should_skip_entirely, skip_reason = should_skip_symbol_entirely(original_symbol)
            # if should_skip_entirely:
            #     record_skip("skip_pattern_learned", original_symbol)
            #     continue

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
            atr = float(
                analysis.get("MTF", {}).get("atr")
                or analysis.get("LTF", {}).get("atr")
                or atr
            )
            atr_threshold = max(atr * 1.5, atr_threshold)

            trend = analysis["overall_trend"]
            if trend not in ("bullish", "bearish"):
                record_skip("topdown", original_symbol)
                continue
            record_stage("topdown", original_symbol)
            direction = "buy" if trend == "bullish" else "sell"

            # -----------------------------
            # ENTRY MODEL (ICT CORE)
            # -----------------------------
            m30_state = analysis.get("MTF", {})
            m15_state = analysis.get("LTF", {})
            execution_state = analysis.get("EXECUTION", {})
            entry_fib_levels = m15_state.get("fib") or m30_state.get("fib", {})
            entry_fvgs = execution_state.get("fvgs") or m15_state.get("fvgs", {})
            entry_order_blocks = m15_state.get("order_blocks") or m30_state.get("order_blocks", {})
            entry_atr = execution_state.get("atr") or m15_state.get("atr") or m30_state.get("atr")
            try:
                signal = check_entry(
                    trend=trend,
                    price=price,
                    fib_levels=entry_fib_levels,
                    fvgs=entry_fvgs,
                    htf_order_blocks=entry_order_blocks,
                    symbol=original_symbol,
                    atr=entry_atr,
                )
            except Exception as e:
                print("Entry model error, skipping symbol:", e)
                record_skip("entry_error", original_symbol)
                continue

            if not isinstance(signal, dict) or not signal:
                entry_reason = explain_entry_failure(
                    trend=trend,
                    price=price,
                    fib_levels=entry_fib_levels,
                    fvgs=entry_fvgs,
                    htf_order_blocks=entry_order_blocks,
                    symbol=original_symbol,
                    atr=entry_atr,
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

            bos_state = bos_setup(analysis, trend)
            if bos_state["confirmed"]:
                record_stage("bos", original_symbol)
            else:
                record_skip("bos", original_symbol)

            price_action_state = price_action_setup(analysis, trend)
            if price_action_state["confirmed"]:
                record_stage("price_action", original_symbol)
            else:
                record_skip("price_action", original_symbol)

            signal["setup_context"] = {
                "liquidity": liquidity_state,
                "bos": bos_state,
                "price_action": price_action_state,
            }

            # --- CIS INTELLIGENCE DECISION ---
            cis_decision = get_cis_decision(
                symbol=original_symbol,
                direction="BUY" if trend == "bullish" else "SELL",
                timeframe=analysis.get("timeframes", {}).get("EXECUTION", "M5"),
                entry_price=price,
                multi_tf_analysis=analysis,
            )

            # ============================================================
            # WEIGHTED ENTRY VALIDATION (Replaces Hard-Gate Filtering)
            # ============================================================
            # Instead of sequential binary checks, use weighted confidence scoring
            # This allows strong confirmations to bypass weak filters

            # Log initial confirmations (informational only)
            smt_ok = smt_confirmed(signal, analysis["correlated"])
            if smt_ok:
                # record_stage("smt", original_symbol)
                pass

            rule_ok = rule_quality_filter(signal)
            if rule_ok:
                # record_stage("rule_quality", original_symbol)
                pass

            # ML QUALITY FILTER
            features = build_signal_features(signal, price, analysis, atr)
            model = None  # load trained model
            ml_ok, probability = ml_quality_filter(features, model)

            # Build confirmation flags for weighted system
            confirmation_flags = {
                "liquidity_setup": liquidity_state,
                "bos": bos_state,
                "price_action": price_action_state,
                "fvg": {
                    "confirmed": bool(signal.get("fvg")),
                    "timeframe": (signal.get("fvg") or {}).get("timeframe"),
                },
                "order_block_confirmed": bool(signal.get("htf_ob")),
                "smt": smt_ok,
                "rule_quality": rule_ok,
                "ml": ml_ok,
            }
            if COUNT_FUNDAMENTALS_AS_CONFIRMATION:
                confirmation_flags["fundamentals"] = fundamentals_ok

            # Calculate weighted entry confidence
            confidence_data = calculate_entry_confidence(
                signal=signal,
                analysis=analysis,
                trend=trend,
                price=price,
                confirmation_flags=confirmation_flags,
                cis_decision=cis_decision,
            )

            execution_route = confidence_data.get("execution_route", "skip")
            confirmation_score_value = float(confidence_data.get("confidence", 0.0))

            # Log confidence data
            record_stage("weighted_confidence", original_symbol)
            confidence_report = format_confidence_report(confidence_data)
            bot_log(
                "weighted_entry_confidence",
                f"[{original_symbol}] {confidence_report}",
                {
                    "symbol": original_symbol,
                    "confidence": confirmation_score_value,
                    "execution_route": execution_route,
                    "components": confidence_data.get("component_scores", {}),
                },
                persist=False,
            )

            confirmation_summary = evaluate_confirmation_quality(
                confirmation_flags,
                symbol=original_symbol,
            )
            hybrid_decision = build_hybrid_trade_decision(
                symbol=original_symbol,
                confidence_data=confidence_data,
                confirmation_score_value=confirmation_score_value,
                signal=signal,
                trend=trend,
                confirmation_flags=confirmation_flags,
                confirmation_summary=confirmation_summary,
            )

            if hybrid_decision["weighted_intelligence_pass"]:
                record_stage("weighted_intelligence_pass", original_symbol)
                record_stage(f"exec_route_{execution_route}", original_symbol)
            if hybrid_decision["analysis_pass"]:
                record_stage("analysis_pass", original_symbol)
            if hybrid_decision["engine_agreement"] == "analysis_rescue":
                record_stage("analysis_rescue", original_symbol)
            elif hybrid_decision["engine_agreement"] == "weighted_intelligence_rescue":
                record_stage("weighted_intelligence_rescue", original_symbol)
            elif hybrid_decision["engine_agreement"] == "both_passed":
                record_stage("dual_engine_agreement", original_symbol)

            signal["confirmation_summary"] = {
                **confirmation_summary,
                "type": hybrid_decision["decision_source"],
            }
            signal["weighted_confidence"] = confirmation_score_value
            signal["weighted_confidence_details"] = confidence_data
            signal["hybrid_decision"] = hybrid_decision
            signal["execution_route"] = hybrid_decision["effective_execution_route"]

            bot_log(
                "hybrid_trade_decision",
                (
                    f"[{original_symbol}] Hybrid decision: {hybrid_decision['engine_agreement']}. "
                    f"Weighted route={execution_route}, intelligence={hybrid_decision['intelligence_pass']}, "
                    f"classic={hybrid_decision['analysis_pass']}."
                ),
                {
                    "symbol": original_symbol,
                    "weighted_route": execution_route,
                    "weighted_pass": hybrid_decision["weighted_pass"],
                    "intelligence_pass": hybrid_decision["intelligence_pass"],
                    "analysis_pass": hybrid_decision["analysis_pass"],
                    "decision_source": hybrid_decision["decision_source"],
                    "effective_execution_route": hybrid_decision["effective_execution_route"],
                    "backtest_required": hybrid_decision["backtest_required"],
                    "classic_analysis": hybrid_decision["classic_analysis"],
                    "intelligence_analysis": hybrid_decision["intelligence_analysis"],
                },
                persist=False,
            )

            if not hybrid_decision["execute"]:
                record_skip(
                    hybrid_decision["skip_reason"] or "hybrid_reject",
                    original_symbol,
                    confidence=round(confirmation_score_value / 100.0, 2),
                    analysis=hybrid_decision,
                )
                bot_log(
                    "hybrid_trade_reject",
                    (
                        f"[{original_symbol}] Rejected by both engines. "
                        f"Weighted route={execution_route}, intelligence={hybrid_decision['intelligence_pass']}, "
                        f"classic={hybrid_decision['analysis_pass']}."
                    ),
                    {
                        "symbol": original_symbol,
                        "weighted_route": execution_route,
                        "intelligence_pass": hybrid_decision["intelligence_pass"],
                        "analysis_pass": hybrid_decision["analysis_pass"],
                        "classic_analysis": hybrid_decision["classic_analysis"],
                        "intelligence_analysis": hybrid_decision["intelligence_analysis"],
                    },
                    persist=False,
                )
                continue

            execution_route = hybrid_decision["effective_execution_route"]

            # ========================================
            # WHOLE EXECUTION PLAN
            # ========================================
            # 1. Score the setup with the weighted validator.
            # 2. Ask the intelligence engine whether the weighted route is still healthy.
            # 3. Run classic trade analysis as an independent fallback engine.
            # 4. Execute if either engine family passes; skip only if both fail.
            # 5. Record which engine approved the trade so learning can evolve toward a full autonomous wizard.
            backtest_required = hybrid_decision["backtest_required"]

            if backtest_required:
                # Need backtest approval for conservative/protected routes
                try:
                    record_backtest_required(original_symbol)
                except Exception:
                    pass

                if not WEIGHTED_CONFIRMATION_BACKTEST_FALLBACK:
                    record_skip(
                        "backtest_required",
                        original_symbol,
                        confidence=round(confirmation_score_value / 100.0, 2),
                        analysis=confidence_data,
                    )
                    continue

                setup_signature = build_setup_signature(signal, analysis, confirmation_flags)
                backtest_approved, backtest_details = ensure_setup_backtest_approval(
                    symbol,
                    setup_signature=setup_signature,
                    report_key=original_symbol,
                )
                if not backtest_approved:
                    record_skip(
                        "backtest",
                        original_symbol,
                        confidence=round(confirmation_score_value / 100.0, 2),
                        analysis=confidence_data,
                    )
                    continue
                record_stage("backtest", original_symbol)
                record_stage("backtest_approved", original_symbol)
            else:
                # Elite/Standard routes skip backtest
                try:
                    record_backtest_skip(original_symbol)
                except Exception:
                    pass
                backtest_details = {
                    "reason": f"weighted_entry_{execution_route}_skip_backtest",
                    "required": False,
                }

            # ===================================
            # INTELLIGENT EXECUTION
            # ===================================
            htf_ob = signal.get("htf_ob") or {}
            ob_id = get_order_block_id(symbol, htf_ob)
            if not ob_id or not can_trade(symbol, ob_id):
                record_skip(
                    "protection",
                    original_symbol,
                    confidence=round(confirmation_score_value / 100.0, 2),
                    analysis=confidence_data,
                )
                continue
            record_stage("protection", original_symbol)

            # ----------------------------
            # PORTFOLIO RISK ALLOCATION
            # ----------------------------
            open_positions = get_open_positions()
            allowed_risk = allocate_risk(symbol, open_positions)

            # Implement IQ Sizing based on Account balance and Execution Route
            account_info = get_account_snapshot()
            account_balance = account_info.get("balance", 10000) if account_info else 10000
            smart_risk = calculate_smart_risk_params(
                account_balance=account_balance,
                confidence=confirmation_score_value,
                base_risk_percent=allowed_risk,
                execution_route=execution_route
            )
            allowed_risk = smart_risk["risk_percent"]

            if allowed_risk <= 0:
                record_skip(
                    "risk",
                    original_symbol,
                    confidence=round(confirmation_score_value / 100.0, 2),
                    analysis=confidence_data,
                )
                continue
            record_stage("risk", original_symbol)

            # ----------------------------
            # ORDER ROUTING
            # ----------------------------
            order_type = choose_order_type(
                price,
                signal.get("fvg"),
                mode="auto"
            )

            # ----------------------------
            # INTELLIGENT SL/TP CALCULATION
            # ----------------------------
            # Precise Structural SL/TP with ATR Buffer
            sl, tp = calculate_sl_tp(
                direction=direction,
                entry_price=price,
                htf_ob=signal["htf_ob"],
                atr=atr,
                rr=float(os.getenv("DEFAULT_RR_RATIO", "3.0"))
            )

            # Refine SL based on symbol win-rate history
            base_pips = abs(sl - price) / (0.01 if "JPY" in symbol else 0.0001)
            sl_final, sl_intelligence = calculate_intelligent_stop_loss(
                price, direction, base_pips, original_symbol
            )
            sl = sl_final
            sl, tp, rr_adjustment = normalize_rr_after_sl_adjustment(
                direction=direction,
                entry=price,
                sl=sl,
                tp=tp,
                min_rr=float(os.getenv("MIN_RR_RATIO", "2.0")),
            )

            profitability_guard = evaluate_profitability_guard(
                symbol=original_symbol,
                direction=direction,
                entry=price,
                sl=sl,
                tp=tp,
                confidence=confirmation_score_value,
                execution_route=execution_route,
                open_positions=open_positions,
            )
            signal["profitability_guard"] = profitability_guard
            signal["rr_adjustment"] = rr_adjustment
            if not profitability_guard.get("allow", True):
                record_skip(
                    f"profitability_guard_{profitability_guard.get('reason', 'reject')}",
                    original_symbol,
                    confidence=round(confirmation_score_value / 100.0, 2),
                    analysis=profitability_guard,
                )
                bot_log(
                    "profitability_guard_block",
                    (
                        f"[{original_symbol}] Blocked by profitability guard: "
                        f"{profitability_guard.get('reason')}. "
                        f"RR={profitability_guard.get('rr')}, "
                        f"confidence={profitability_guard.get('confidence')}."
                    ),
                    profitability_guard,
                )
                continue

            # ----------------------------
            # INTELLIGENT POSITION SIZING
            # ----------------------------
            # First get base lot size
            sl_pips = abs(price - sl) / (0.01 if "JPY" in symbol else 0.0001)
            lot_base = calculate_lot_size(
                symbol=symbol,
                risk_percent=allowed_risk,
                stop_loss_pips=max(5, sl_pips)
            )

            # Then apply intelligent multipliers based on symbol confidence
            lot_intelligent, lot_intelligence = calculate_dynamic_lot_size(
                original_symbol,
                lot_base,
                account_balance,
                allowed_risk
            )

            lot = lot_intelligent  # Use intelligent lot sizing
            session = get_trading_session()
            setup_types = extract_setup_types(signal)
            strategy_adaptation = get_strategy_adaptation(
                original_symbol,
                setup_types=setup_types,
                execution_route=execution_route or "unknown",
                session=session,
            )

            if not strategy_adaptation.get("allow_trade", True):
                record_skip(
                    "strategy_memory",
                    original_symbol,
                    confidence=round(confirmation_score_value / 100.0, 2),
                    analysis={
                        "factors": [strategy_adaptation.get("reason", "Strategy memory blocked trade")],
                        "signal_type": execution_route or "unknown",
                    },
                )
                bot_log(
                    "strategy_memory_block",
                    (
                        f"[{original_symbol}] Blocked by strategy memory: "
                        f"{strategy_adaptation.get('reason')}"
                    ),
                    {
                        "symbol": original_symbol,
                        "execution_route": execution_route,
                        "setup_types": setup_types,
                        "strategy_adaptation": strategy_adaptation,
                    },
                )
                continue

            lot *= float(strategy_adaptation.get("lot_multiplier", 1.0) or 1.0)

            # Log intelligent decisions
            bot_log(
                "intelligent_execution",
                f"Intelligent execution for {original_symbol}: "
                f"SL adjustment {sl_intelligence['multiplier']:.2f}x, "
                f"Lot adjustment {lot_intelligence['final_multiplier']:.2f}x, "
                f"Memory adjustment {strategy_adaptation.get('lot_multiplier', 1.0):.2f}x",
                {
                    "symbol": original_symbol,
                    "sl_intelligence": sl_intelligence,
                    "lot_intelligence": lot_intelligence,
                    "strategy_adaptation": strategy_adaptation,
                    "setup_types": setup_types,
                    "rr_adjustment": rr_adjustment,
                    "profitability_guard": profitability_guard,
                    "trade_confidence": round(confirmation_score_value / 100.0, 2),
                    "weighted_trade_confidence": confirmation_score_value,
                    "execution_route": execution_route,
                },
                persist=False,
            )

            lot = max(0.01, round(lot, 2))

            # -----------------------------
            # PERSIST SIGNAL TO SUPABASE (no webhook)
            # -----------------------------
            current_bot_id = os.getenv("PERSISTENT_BOT_ID") or os.getenv("BOT_ID") or f"mt5_bot_{original_symbol}"
            signal_allowed = True
            try:
                signal_allowed = persist_signal_to_supabase({
                    "bot_id": current_bot_id,
                    "user_id": os.getenv("BOT_USER_ID") or os.getenv("SIGNAL_USER_ID"),
                    "symbol": original_symbol,
                    "direction": direction,
                    "entry_price": price,
                    "stop_loss": sl,
                    "tp": tp,
                    "lot": lot,
                    "ml_probability": probability,
                    "signal_quality": "premium",
                    "confidence": confirmation_score_value,
                    "reason": build_execution_context(
                        signal,
                        analysis,
                        confirmation_flags,
                        MIN_EXTRA_CONFIRMATIONS,
                        confirmation_summary=confirmation_summary,
                        execution_route=execution_route,
                        decision_bundle=hybrid_decision,
                    ),
                    "status": "pending",
                })
            except Exception:
                pass
            if signal_allowed is False:
                record_skip("user_signal_limit", original_symbol)
                bot_log(
                    "signal_quota_blocked",
                    f"Signal and execution blocked for {original_symbol} by user/group bot limits.",
                    {"symbol": original_symbol, "direction": direction},
                )
                continue

            execution_context = build_execution_context(
                signal,
                analysis,
                confirmation_flags,
                MIN_EXTRA_CONFIRMATIONS,
                confirmation_summary=confirmation_summary,
                execution_route=execution_route,
                decision_bundle=hybrid_decision,
            )
            execution_context["backtest"] = backtest_details
            bot_log(
                "signal_detected",
                (
                    f"Signal detected on {original_symbol} ({direction}). "
                    f"Brief {execution_context['timeframes'].get('DAILY', 'D1')}/"
                    f"{execution_context['timeframes'].get('H4', 'H4')} trends: "
                    f"{execution_context['timeframe_trends'].get('DAILY')}/"
                    f"{execution_context['timeframe_trends'].get('H4')} "
                    f"({execution_context.get('brief_context_alignment') or 'context'}). "
                    f"Analysis {execution_context['timeframes']['HTF']}/"
                    f"{execution_context['timeframes']['MTF']}/"
                    f"{execution_context['timeframes']['LTF']} trends: "
                    f"{execution_context['timeframe_trends']['HTF']}/"
                    f"{execution_context['timeframe_trends']['MTF']}/"
                    f"{execution_context['timeframe_trends']['LTF']}. "
                    f"Execution {execution_context['timeframes'].get('EXECUTION', 'M5')} trend: "
                    f"{execution_context['timeframe_trends'].get('EXECUTION')}. "
                    f"Confirmations met: {', '.join(execution_context['confirmations_met']) or 'none'}. "
                    f"Score: {execution_context['confirmation_score']:.1f}/"
                    f"{execution_context['confirmation_score_required']:.1f} "
                    f"({execution_context['confirmation_count']} flags). "
                    f"Execution route: {execution_context['execution_route']}. "
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
            try:
                trade = execute_trade(
                    symbol=symbol,
                    direction=direction,
                    lot=lot,
                    sl_price=sl,
                    tp_price=tp,
                    order_type=order_type,
                    entry_price=price,
                )
            except Exception as execution_error:
                record_skip("trade_execution_error", original_symbol)
                bot_log(
                    "trade_execution_error",
                    f"Trade execution error for {original_symbol}: {execution_error}",
                    {
                        "symbol": original_symbol,
                        "resolved_symbol": symbol,
                        "direction": direction,
                        "lot": lot,
                        "sl": sl,
                        "tp": tp,
                        "order_type": order_type,
                        "error": str(execution_error),
                    },
                )
                continue
            if not trade:
                record_skip("trade_failed", original_symbol)
                bot_log(
                    "trade_failed",
                    f"Trade execution failed for {original_symbol}.",
                    {
                        "symbol": original_symbol,
                        "resolved_symbol": symbol,
                        "direction": direction,
                        "lot": lot,
                        "sl": sl,
                        "tp": tp,
                        "order_type": order_type,
                    },
                )
                continue
            record_stage("trade_opened", original_symbol)

            # Register trade and track symbol IQ
            from risk.protection import register_trade, update_symbol_confidence
            from risk.symbol_stats import record_symbol_trade, record_backtest_skip, record_backtest_required

            register_trade(symbol, ob_id)
            # Do not record trade outcomes on open.
            # Trade outcome and confirmation quality are recorded on SL/TP close.

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
                    f"Brief {execution_context['timeframes'].get('DAILY', 'D1')}/"
                    f"{execution_context['timeframes'].get('H4', 'H4')} context "
                    f"{execution_context['timeframe_trends'].get('DAILY')}/"
                    f"{execution_context['timeframe_trends'].get('H4')}; "
                    f"analysis trend {execution_context['topdown_trend']} across "
                    f"{execution_context['timeframes']['HTF']}/"
                    f"{execution_context['timeframes']['MTF']}/"
                    f"{execution_context['timeframes']['LTF']}; "
                    f"execution {execution_context['timeframes'].get('EXECUTION', 'M5')}. "
                    f"Confirmations used: {', '.join(execution_context['confirmations_met']) or 'none'}. "
                    f"Score: {execution_context['confirmation_score']:.1f}/"
                    f"{execution_context['confirmation_score_required']:.1f}. "
                    f"Execution route: {execution_context['execution_route']}."
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
            # Record trade entry for later stats/reporting
            trade_entry_time = time.time()
            trade_entry_price = trade.get("entry", price)

            # -----------------------------
            while trade and trade.get("open"):
                live_price = get_price(symbol)

                # Check for SL/TP hits
                sl_hit = False
                tp_hit = False
                if trade["direction"] == "buy":
                    sl_hit = live_price <= trade["sl"]
                    tp_hit = live_price >= trade["tp"]
                else:  # sell
                    sl_hit = live_price >= trade["sl"]
                    tp_hit = live_price <= trade["tp"]

                if sl_hit:
                    # Trade hit stop loss - record as loss with detailed intelligence
                    try:
                        pnl = round((live_price - price) * lot if direction == "buy" else (price - live_price) * lot, 2)
                        update_symbol_confidence(original_symbol, win=False, confirmation_score=confirmation_score_value)
                        record_trade_outcome(
                            original_symbol,
                            win=False,
                            confirmation_score=confirmation_score_value,
                            entry_price=price,
                            exit_price=live_price,
                            stop_loss_price=trade["sl"],
                            take_profit_price=trade["tp"],
                            lot_size=lot,
                            pnl=pnl,
                            signal_type=execution_route,
                            decision_source=hybrid_decision["decision_source"],
                            analysis_score=hybrid_decision["classic_analysis"].get("score", 0.0),
                            analysis_confidence=hybrid_decision["classic_analysis"].get("confidence", 0.0),
                            analysis_pass=hybrid_decision["analysis_pass"],
                            weighted_pass=hybrid_decision["weighted_pass"],
                            intelligence_pass=hybrid_decision["intelligence_pass"],
                            engine_agreement=hybrid_decision["engine_agreement"],
                        )
                        record_symbol_trade(original_symbol, win=False, confirmation_score=confirmation_score_value)
                        sync_trade_outcome_to_supabase(
                            symbol=original_symbol,
                            win=False,
                            confirmation_score=confirmation_score_value,
                            entry_price=price,
                            exit_price=live_price,
                            pnl=pnl,
                            execution_route=execution_route
                        )

                        # RECORD STRATEGY MEMORY - what strategy was used, did it work?
                        try:
                            from risk.strategy_memory import record_strategy_execution
                            from utils.symbol_profile import infer_asset_class

                            setup_types = extract_setup_types(signal)
                            session = get_trading_session()
                            asset_class = infer_asset_class(original_symbol)
                            bars_held = int((time.time() - trade_entry_time) / 60 / 5)  # Approx bars

                            record_strategy_execution(
                                symbol=original_symbol,
                                setup_types=setup_types,
                                execution_route=execution_route or "unknown",
                                confirmation_type=signal.get("confirmation_summary", {}).get("type", "unknown"),
                                session=session,
                                asset_class=asset_class,
                                confirmation_score=confirmation_score_value,
                                entry_price=price,
                                sl=trade["sl"],
                                tp=trade["tp"],
                                win=False,
                                pnl=pnl,
                                bars_held=bars_held
                            )
                        except Exception as e:
                            pass  # Don't fail main bot if strategy memory fails
                    except Exception:
                        pass
                    bot_log(
                        "trade_closed",
                        f"Trade closed by SL on {original_symbol}",
                        {"symbol": original_symbol, "price": live_price, "sl": trade["sl"]},
                    )
                    trade["open"] = False
                    break
                elif tp_hit:
                    # Trade hit take profit - record as win with detailed intelligence
                    try:
                        pnl = round((live_price - price) * lot if direction == "buy" else (price - live_price) * lot, 2)
                        update_symbol_confidence(original_symbol, win=True, confirmation_score=confirmation_score_value)
                        record_trade_outcome(
                            original_symbol,
                            win=True,
                            confirmation_score=confirmation_score_value,
                            entry_price=price,
                            exit_price=live_price,
                            stop_loss_price=trade["sl"],
                            take_profit_price=trade["tp"],
                            lot_size=lot,
                            pnl=pnl,
                            signal_type=execution_route,
                            decision_source=hybrid_decision["decision_source"],
                            analysis_score=hybrid_decision["classic_analysis"].get("score", 0.0),
                            analysis_confidence=hybrid_decision["classic_analysis"].get("confidence", 0.0),
                            analysis_pass=hybrid_decision["analysis_pass"],
                            weighted_pass=hybrid_decision["weighted_pass"],
                            intelligence_pass=hybrid_decision["intelligence_pass"],
                            engine_agreement=hybrid_decision["engine_agreement"],
                        )
                        record_symbol_trade(original_symbol, win=True, confirmation_score=confirmation_score_value)
                        sync_trade_outcome_to_supabase(
                            symbol=original_symbol,
                            win=True,
                            confirmation_score=confirmation_score_value,
                            entry_price=price,
                            exit_price=live_price,
                            pnl=pnl,
                            execution_route=execution_route
                        )

                        # RECORD STRATEGY MEMORY - what strategy was used, did it work?
                        try:
                            from risk.strategy_memory import record_strategy_execution
                            from utils.symbol_profile import infer_asset_class

                            setup_types = extract_setup_types(signal)
                            session = get_trading_session()
                            asset_class = infer_asset_class(original_symbol)
                            bars_held = int((time.time() - trade_entry_time) / 60 / 5)  # Approx bars

                            record_strategy_execution(
                                symbol=original_symbol,
                                setup_types=setup_types,
                                execution_route=execution_route or "unknown",
                                confirmation_type=signal.get("confirmation_summary", {}).get("type", "unknown"),
                                session=session,
                                asset_class=asset_class,
                                confirmation_score=confirmation_score_value,
                                entry_price=price,
                                sl=trade["sl"],
                                tp=trade["tp"],
                                win=True,
                                pnl=pnl,
                                bars_held=bars_held
                            )
                        except Exception as e:
                            pass  # Don't fail main bot if strategy memory fails
                    except Exception:
                        pass
                    bot_log(
                        "trade_closed",
                        f"Trade closed by TP on {original_symbol}",
                        {"symbol": original_symbol, "price": live_price, "tp": trade["tp"]},
                    )
                    trade["open"] = False
                    break

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
