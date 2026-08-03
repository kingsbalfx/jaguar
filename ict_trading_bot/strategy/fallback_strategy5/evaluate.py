"""
FALLBACK STRATEGY 5 — Main Evaluation Pipeline
=================================================
Central entry point. Called from main.py after Fallback 4 returns no valid trade.

Flow:
1. Check enabled & config
2. Symbol gate: EURUSD, XAUUSD, BTCUSD, AUDJPY only
3. Session gate: 08:00-12:00 or 14:00-20:00
4. Data availability check
5. Trend analysis (H1, M15, M5, M1)
6. Model evaluation (A → B → C)
7. Stop loss / take profit calculation
8. Risk gate + position sizing
9. Pre-trade safety validation
10. Setup scoring
11. Signal generation
"""

import hashlib
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from . import config
from .logging import (
    LOGGER, log_activation, log_skip, log_trend_analysis,
    log_setup_scan, log_trade_open, log_entry_event, log_exception,
)
from .session import (
    is_session_open, is_in_sleep, classify_session, current_session_name,
    get_session_timestamps,
)
from .symbol_gate import resolve_symbol, is_allowed_symbol, get_symbol_profile
from .indicators import atr, signal_to_direction, estimate_point, _to_float
from .trend import classify_trend, trend_supports_direction, BULLISH, BEARISH, NEUTRAL, STRONG, MODERATE
from .model_a import evaluate_model_a
from .model_b import evaluate_model_b
from .model_c import evaluate_model_c
from .scoring import calculate_score
from .risk import (
    check_risk_gate, calculate_active_risk, calculate_position_size,
    calculate_stop_loss, calculate_take_profit,
    check_duplicate_setup, check_spread_acceptable, set_symbol_pause,
)
from .cooldown import check_cooldown, set_cooldown
from .exhaustion import check_exhaustion, check_minimum_target_room
from .news_block import news_allows_trade
from .daily_stats import get_stats as get_f5_stats
from .signal import generate_fallback5_signal
from .state_machine import Fallback5StateMachine, Fallback5StateResult


def evaluate_fallback5(
    symbol: str,
    direction: str,
    analysis: dict,
    tick: dict,
    account: dict,
    positions: list,
    mt5_connector=None,
    ict_setup: Optional[Dict[str, Any]] = None,
    kingsbalfx_setup: Optional[Dict[str, Any]] = None,
    fallback3_setup: Optional[Dict[str, Any]] = None,
    fallback4_setup: Optional[Dict[str, Any]] = None,
    risk_percent: float = 0.15,
    minimum_rr: float = 1.2,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Main entry point for Fallback Strategy 5 evaluation.
    
    Called from main.py after Strategy 1 (ICT), Strategy 2 (Kingsbalfx),
    Fallback Strategy 3, and Fallback Strategy 4 all return no valid trade.
    
    Returns:
        (trade_request_dict_or_None, fallback5_setup_dict, safety_dict)
    """
    # ----------------------------------------------------------
    # Setup logging context
    # ----------------------------------------------------------
    stats = get_f5_stats()
    stats.check_day_reset()
    stats.check_session_reset()

    # ----------------------------------------------------------
    # Master switch
    # ----------------------------------------------------------
    if not config.FALLBACK5_ENABLED:
        log_skip(symbol, "fallback5_disabled")
        return _skip_result("fallback5_disabled", symbol=symbol)

    config_warnings = config.validate()
    if config_warnings:
        for w in config_warnings:
            LOGGER.warning("[%s] FALLBACK5 CONFIG: %s", symbol, w)

    # ----------------------------------------------------------
    # Activation log
    # ----------------------------------------------------------
    log_activation(symbol, {
        "ict": ict_setup.get("reason") if ict_setup else "skip",
        "kingsbalfx": kingsbalfx_setup.get("reason") if kingsbalfx_setup else "skip",
        "fallback3": fallback3_setup.get("rejection_reason") if fallback3_setup else "skip",
        "fallback4": fallback4_setup.get("rejection_reason") if fallback4_setup else "skip",
    })

    # ----------------------------------------------------------
    # Symbol gate
    # ----------------------------------------------------------
    canonical_symbol = resolve_symbol(symbol)
    if not canonical_symbol:
        log_skip(symbol, "symbol_not_allowed", {"symbol": symbol})
        return _skip_result(f"symbol_not_allowed:{symbol}", symbol=symbol)

    profile = get_symbol_profile(canonical_symbol)

    # ----------------------------------------------------------
    # Session gate
    # ----------------------------------------------------------
    if is_in_sleep():
        log_skip(symbol, "sleep_window_12_14")
        return _skip_result("sleep_window_12_14", symbol=symbol)

    if not is_session_open():
        session_name = current_session_name()
        log_skip(symbol, f"outside_trading_hours:session={session_name}")
        return _skip_result(f"outside_trading_hours:{session_name}", symbol=symbol)

    # ----------------------------------------------------------
    # Extract price info
    # ----------------------------------------------------------
    bid = _to_float(tick.get("bid"))
    ask = _to_float(tick.get("ask"))
    spread = abs(ask - bid) if ask and bid else 0.0
    price = (bid + ask) / 2.0 if bid and ask else 0.0

    if price <= 0:
        log_skip(symbol, "invalid_price")
        return _skip_result("invalid_price", symbol=symbol)

    point = estimate_point(price)

    # ----------------------------------------------------------
    # Extract candles
    # ----------------------------------------------------------
    htf_candles = _extract_candles(analysis, config.TREND_TIMEFRAME)
    mtf_candles = _extract_candles(analysis, config.CONTEXT_TIMEFRAME)
    setup_candles = _extract_candles(analysis, config.SETUP_TIMEFRAME)
    exec_candles = _extract_candles(analysis, config.EXECUTION_TIMEFRAME)

    # Sanitize
    htf_candles = _ensure_dict_list(htf_candles)
    mtf_candles = _ensure_dict_list(mtf_candles)
    setup_candles = _ensure_dict_list(setup_candles)
    exec_candles = _ensure_dict_list(exec_candles)

    if len(htf_candles) < 20 or len(mtf_candles) < 30 or len(exec_candles) < 20:
        log_skip(symbol, "insufficient_candles", {
            "htf": len(htf_candles), "mtf": len(mtf_candles), "exec": len(exec_candles),
        })
        return _skip_result(f"insufficient_candles:htf={len(htf_candles)}_ctx={len(mtf_candles)}_exec={len(exec_candles)}", symbol=symbol)

    # ----------------------------------------------------------
    # ATR
    # ----------------------------------------------------------
    atr_value = atr(setup_candles or mtf_candles, config.ATR_PERIOD)
    if atr_value <= 0:
        atr_value = price * 0.001

    # ----------------------------------------------------------
    # Resolve direction
    # ----------------------------------------------------------
    resolved_dir = _resolve_direction(symbol, direction, analysis)
    if not resolved_dir:
        log_skip(symbol, "unresolved_direction")
        return _skip_result("unresolved_direction", symbol=symbol)

    # ----------------------------------------------------------
    # Trend analysis
    # ----------------------------------------------------------
    mode = config.TREND_MODE_BY_SYMBOL.get(canonical_symbol, "B")
    trend_direction, trend_strength, trend_evidence = classify_trend(
        symbol, htf_candles, mtf_candles, setup_candles, exec_candles, mode=mode,
    )

    if not trend_direction or not trend_supports_direction(trend_direction, resolved_dir):
        log_skip(symbol, f"trend_does_not_support_direction:trend={trend_direction}_direction={resolved_dir}")
        return _skip_result(f"trend_does_not_support:{trend_direction}/{resolved_dir}", failed_stage="trend_analysis", symbol=symbol)

    # ----------------------------------------------------------
    # News filter
    # ----------------------------------------------------------
    news_ok, news_reason = news_allows_trade(symbol)
    if not news_ok:
        log_skip(symbol, f"news_block:{news_reason}")
        return _skip_result(f"news:{news_reason}", failed_stage="news_check", symbol=symbol)

    # ----------------------------------------------------------
    # Exhaustion check (anti-chase)
    # ----------------------------------------------------------
    exhausted, exhaustion_reason = check_exhaustion(setup_candles, exec_candles, resolved_dir, atr_value)
    if exhausted:
        log_skip(symbol, f"exhaustion:{exhaustion_reason}")
        return _skip_result(f"exhaustion:{exhaustion_reason}", failed_stage="exhaustion_check", symbol=symbol)

    # ----------------------------------------------------------
    # Risk gate
    # ----------------------------------------------------------
    risk_gate_passed, risk_gate_reason = check_risk_gate(symbol, resolved_dir, account, positions, stats)
    if not risk_gate_passed:
        log_skip(symbol, f"risk_gate:{risk_gate_reason}")
        return _skip_result(f"risk:{risk_gate_reason}", failed_stage="risk_gate", symbol=symbol)

    # ----------------------------------------------------------
    # Calculate active risk
    # ----------------------------------------------------------
    base_risk_pct, active_risk_pct, session_r = calculate_active_risk(stats)
    risk_used = active_risk_pct if risk_percent is None else min(active_risk_pct, risk_percent)

    # ----------------------------------------------------------
    # Model Evaluation (A → B → C)
    # ----------------------------------------------------------
    model_results = {}
    best_model = None
    best_model_name = ""
    best_score = 0

    # Model A: Trend Pullback
    model_a_passed, model_a_result = evaluate_model_a(
        symbol, resolved_dir, trend_direction,
        setup_candles, exec_candles, htf_candles,
        atr_value, trend_evidence, mode,
    )
    model_results["A"] = model_a_result
    if model_a_passed:
        best_model = model_a_result
        best_model_name = "A"
        best_score = model_a_result.get("score", 0)
        log_setup_scan(symbol, "A", True, "passed", best_score)

    # Model B: Micro Consolidation Breakout
    if not best_model:
        model_b_passed, model_b_result = evaluate_model_b(
            symbol, resolved_dir, trend_direction,
            setup_candles, exec_candles, atr_value,
        )
        model_results["B"] = model_b_result
        if model_b_passed:
            best_model = model_b_result
            best_model_name = "B"
            best_score = model_b_result.get("score", 0)
            log_setup_scan(symbol, "B", True, "passed", best_score)

    # Model C: Trend Liquidity Sweep
    if not best_model:
        model_c_passed, model_c_result = evaluate_model_c(
            symbol, resolved_dir, trend_direction,
            setup_candles, exec_candles, htf_candles, atr_value,
        )
        model_results["C"] = model_c_result
        if model_c_passed:
            best_model = model_c_result
            best_model_name = "C"
            best_score = model_c_result.get("score", 0)
            log_setup_scan(symbol, "C", True, "passed", best_score)

    if not best_model:
        models_tried = ",".join([k for k, v in model_results.items() if not v.get("detected")])
        log_skip(symbol, f"no_model_detected:tried_{models_tried}")
        return _skip_result(f"no_model_detected:{models_tried}", failed_stage="setup_scan", symbol=symbol)

    # ----------------------------------------------------------
    # Entry Price
    # ----------------------------------------------------------
    entry_price = best_model.get("entry_price", price)

    # ----------------------------------------------------------
    # Stop Loss Calculation
    # ----------------------------------------------------------
    stop_loss, risk_distance, stop_method = calculate_stop_loss(
        best_model, resolved_dir, entry_price, atr_value,
        profile, trend_direction, htf_candles, point,
    )
    if stop_loss <= 0:
        log_skip(symbol, "no_valid_stop_loss")
        return _skip_result("no_valid_stop_loss", failed_stage="stop_loss_calc", symbol=symbol)

    # ----------------------------------------------------------
    # Take Profit Calculation
    # ----------------------------------------------------------
    tp1, tp2, final_tp, targets = calculate_take_profit(
        entry_price, stop_loss, resolved_dir, atr_value, risk_distance, setup_candles,
    )

    # ----------------------------------------------------------
    # Risk/Reward
    # ----------------------------------------------------------
    rr = risk_distance > 0 and abs(final_tp - entry_price) / risk_distance or 0.0
    rr_to_tp1 = risk_distance > 0 and abs(tp1 - entry_price) / risk_distance or 0.0

    if rr < minimum_rr:
        log_skip(symbol, f"rr_{rr:.2f}_<_{minimum_rr:.2f}")
        return _skip_result(f"rr_{rr:.2f}<{minimum_rr:.2f}", failed_stage="order_approval", symbol=symbol)

    if rr < config.MIN_RR:
        log_skip(symbol, f"rr_{rr:.2f}_<_{config.MIN_RR:.2f}_config")
        return _skip_result(f"rr_{rr:.2f}<{config.MIN_RR:.2f}", failed_stage="order_approval", symbol=symbol)

    # ----------------------------------------------------------
    # Check minimum target room
    # ----------------------------------------------------------
    room_ok, max_target = check_minimum_target_room(entry_price, stop_loss, resolved_dir, setup_candles, atr_value)
    if not room_ok:
        log_skip(symbol, f"insufficient_target_room:{max_target:.5f}")
        return _skip_result(f"insufficient_target_room:{max_target:.5f}", failed_stage="order_approval", symbol=symbol)

    # ----------------------------------------------------------
    # Spread check
    # ----------------------------------------------------------
    target_distance = abs(final_tp - entry_price)
    spread_ok, spread_reason = check_spread_acceptable(spread, target_distance, atr_value, profile)
    if not spread_ok:
        log_skip(symbol, f"spread:{spread_reason}")
        return _skip_result(f"spread:{spread_reason}", failed_stage="order_approval", symbol=symbol)

    # ----------------------------------------------------------
    # Position Size
    # ----------------------------------------------------------
    lot, risk_amount = calculate_position_size(
        symbol, entry_price, stop_loss, account, risk_used, profile, mt5_connector,
    )
    if lot <= 0:
        log_skip(symbol, "position_size_zero")
        return _skip_result("position_size_zero", failed_stage="order_approval", symbol=symbol)

    # ----------------------------------------------------------
    # Duplicate check
    # ----------------------------------------------------------
    session_id = classify_session()
    dup_ok, dup_reason = check_duplicate_setup(
        symbol, resolved_dir, entry_price, stop_loss, final_tp, session_id, stats,
    )
    if not dup_ok:
        log_skip(symbol, f"duplicate:{dup_reason}")
        return _skip_result(f"duplicate:{dup_reason}", failed_stage="order_approval", symbol=symbol)

    # ----------------------------------------------------------
    # Setup ID
    # ----------------------------------------------------------
    setup_id = hashlib.sha256(
        f"{canonical_symbol}|{resolved_dir}|{best_model_name}|{entry_price:.8f}|"
        f"{stop_loss:.8f}|{int(time.time())}".encode()
    ).hexdigest()[:24]

    # ----------------------------------------------------------
    # Score
    # ----------------------------------------------------------
    score_result = calculate_score(
        best_model, trend_direction, trend_strength, trend_evidence,
        entry_price, stop_loss, final_tp, rr, spread, atr_value,
        "optimal" if is_session_open() else "acceptable",
    )

    if score_result.get("score", 0) < config.SCORE_MINIMUM:
        log_skip(symbol, f"score_{score_result.get('score', 0)}_<_{config.SCORE_MINIMUM}")
        return _skip_result(f"score_{score_result.get('score', 0)}<{config.SCORE_MINIMUM}",
                           failed_stage="order_approval", symbol=symbol)
    
    total_score = score_result.get("total", score_result.get("score", 0))

    # ----------------------------------------------------------
    # Pre-trade safety validation
    # ----------------------------------------------------------
    from execution.pre_trade_validator import validate_execution_safety
    safe, safety = validate_execution_safety(
        symbol, resolved_dir, entry_price, stop_loss,
        final_tp, lot, account, positions,
    )
    if not safe:
        log_skip(symbol, f"pre_trade_safety:{safety.get('reason', 'rejected')}")
        return None, {
            "strategy": "fallback5",
            "executable": True,
            "reason": safety.get("reason", "pre_trade_rejected"),
            "score": total_score,
            "states": [],
        }, safety

    # ----------------------------------------------------------
    # Generate signal
    # ----------------------------------------------------------
    request = generate_fallback5_signal(
        symbol=canonical_symbol,
        direction=resolved_dir,
        model=best_model_name,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=final_tp,
        lot=lot,
        rr=rr,
        score=total_score,
        setup_data={
            **best_model,
            "trend_direction": trend_direction,
            "trend_strength": trend_strength,
            "atr": atr_value,
            "profile": profile,
            "mode": mode,
        },
        base_risk=base_risk_pct,
        active_risk=active_risk_pct,
        session_r=session_r,
    )

    # ----------------------------------------------------------
    # Register duplicate protection
    # ----------------------------------------------------------
    from risk.protection import register_trade
    register_trade(symbol, request.get("identity", ""))

    # ----------------------------------------------------------
    # Log to daily stats
    # ----------------------------------------------------------
    stats.register_trade_open(
        symbol=canonical_symbol,
        direction=resolved_dir,
        model=best_model_name,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=final_tp,
        lot=lot,
        rr=rr,
        score=total_score,
        setup_id=setup_id,
        setup_data=request.get("setup_data", {}),
    )

    # ----------------------------------------------------------
    # Log trade open
    # ----------------------------------------------------------
    log_trade_open(
        symbol=canonical_symbol,
        direction=resolved_dir,
        model=best_model_name,
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=final_tp,
        lot=lot,
        rr=rr,
        score=total_score,
        setup_id=setup_id,
        base_risk=base_risk_pct,
        active_risk=active_risk_pct,
        session_r=session_r,
    )

    # ----------------------------------------------------------
    # Build setup dict
    # ----------------------------------------------------------
    setup_dict = {
        "strategy": "fallback5",
        "executable": True,
        "direction": resolved_dir,
        "model": best_model_name,
        "entry_price": entry_price,
        "stop_loss": stop_loss,
        "take_profit": final_tp,
        "position_size": lot,
        "risk_reward": rr,
        "score": total_score,
        "score_components": score_result.get("components", {}),
        "setup_id": setup_id,
        "atr": atr_value,
        "trend_direction": trend_direction,
        "trend_strength": trend_strength,
        "mode": mode,
        "session": classify_session(),
        "profile": profile,
        "states": [],
        "evidence": {
            "trend_evidence": trend_evidence,
            "model_result": best_model,
            "score_result": score_result,
        },
        "timeframe": config.SETUP_TIMEFRAME,
        "execution_timeframe": config.EXECUTION_TIMEFRAME,
        "asset_class": profile.get("asset_class", "forex"),
        "rejection_reason": "",
        "failed_stage": "",
    }

    LOGGER.info(
        "FALLBACK5 | TRADE OK | symbol=%s dir=%s model=%s score=%d rr=%.2f "
        "entry=%.5f sl=%.5f tp=%.5f lot=%.4f risk=%.2f%% setup_id=%s",
        canonical_symbol, resolved_dir.upper(), best_model_name, total_score, rr,
        entry_price, stop_loss, final_tp, lot, risk_used, setup_id,
    )

    return request, setup_dict, {"approved": True, "reason": "all_checks_passed"}


# ============================================================
# Helper Functions
# ============================================================

def _extract_candles(analysis: dict, tf: str) -> List[dict]:
    """Extract candle data for a given timeframe from analysis dict."""
    key_map = {
        "H1": "H1",
        "M15": "M15",
        "M5": "M5",
        "M1": "M1",
    }
    data_key = key_map.get(tf, tf)

    # Try direct access
    candles = analysis.get(data_key, {}).get("recent_candles", []) or analysis.get(f"{tf.lower()}_candles", [])
    if candles and len(candles) > 0:
        return candles

    # Try timeframe-specific keys
    tf_data = analysis.get(tf) or analysis.get(tf.lower()) or analysis.get(data_key)
    if isinstance(tf_data, dict):
        candles = tf_data.get("recent_candles", []) or tf_data.get("candles", [])
        if candles:
            return candles

    # Try topdown structure
    topdown = analysis.get("topdown") or {}
    for level in ["execution", "structure", "context", "htf"]:
        data = topdown.get(level) or {}
        if data.get("timeframe") == tf:
            candles = data.get("candles", []) or data.get("recent_candles", [])
            if candles:
                return candles

    return candles or []


def _ensure_dict_list(candles: list) -> list:
    """Ensure candles are a list of dicts, not raw floats."""
    if isinstance(candles, list) and candles and not isinstance(candles[0], dict):
        return []
    return candles or []


def _resolve_direction(symbol: str, direction: str, analysis: dict) -> str:
    """Resolve the direction to evaluate. Returns 'buy', 'sell', or empty."""
    if direction in ("buy", "sell"):
        return direction
    overall = (analysis.get("overall_trend") or "").lower()
    if overall in ("buy", "bullish", "long"):
        return "buy"
    if overall in ("sell", "bearish", "short"):
        return "sell"
    return ""


def _skip_result(
    reason: str,
    failed_stage: str = "",
    score: int = 0,
    symbol: str = "",
) -> Tuple[Optional[Dict], Optional[Dict], Optional[Dict]]:
    """Create a consistent skip/failure result."""
    setup = {
        "strategy": "fallback5",
        "executable": False,
        "reason": reason,
        "failed_stage": failed_stage,
        "score": score,
        "states": [],
        "rejection_reason": reason,
    }
    return None, setup, {"reason": reason, "approved": False}
