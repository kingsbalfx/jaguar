"""
FALLBACK STRATEGY 4 - Main Evaluation Pipeline
================================================
Public entry point for Fallback 4 evaluation.
Called from main.py after ICT, Kingsbalfx, and Fallback 3 all return no valid trade.
"""

import hashlib
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from . import config
from .models import (
    BoundaryZone, DisplacementResult, EntryResult, Fallback4SetupResult,
    Fallback4TradeRequest, RangeResult, RangeTarget, ReclaimResult,
    StructureChangeResult, SweepResult, make_state,
)
from .range_detector import detect_range
from .sweep_classifier import classify_sweep
from .reclaim import confirm_reclaim
from .displacement import detect_displacement
from .structure_change import confirm_structure_change
from .entry_zone import calculate_entry_zone
from .state_machine import Fallback4StateMachine
from .scoring import calculate_score
from .risk import (
    check_risk_gate, check_duplicate_range_setup, register_fallback4_trade,
    calculate_position_size, calculate_sl_tp, check_spread_allowed,
)
from .signal import generate_fallback4_signal, setup_identity
from .logging import log_fallback4_result

# Reuse Fallback 3 indicators
from strategy.fallback_strategy3.indicators import atr as _atr, sma, macd

LOGGER = logging.getLogger("ict_state_machine.fallback4")


def _to_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _extract_candles(analysis: dict, tf: str) -> List[dict]:
    """Extract candle data for a given timeframe from analysis dict."""
    key_map = {
        "M1": "M1",
        "M5": "M5",
        "M15": "M15",
        "M30": "M30",
        "H1": "H1",
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


def _estimate_point(price: float) -> float:
    """Estimate point/tick size from price magnitude."""
    if price <= 0:
        return 0.0001
    if price < 1:
        return 0.0001
    if price < 100:
        return 0.001
    return 0.01


def _extract_context_bias(candles: List[dict], direction: str, atr_value: float) -> str:
    """
    Determine higher-context timeframe bias.
    Returns "bullish", "bearish", "neutral", or "conflicting".
    """
    if len(candles) < 10:
        return "neutral"

    # Check recent price position relative to SMA
    sma_20 = sma(candles, 20)
    sma_50 = sma(candles, 50) if len(candles) >= 50 else sma_20

    recent_close = _to_float(candles[-1].get("close"))
    prev_close = _to_float(candles[-2].get("close")) if len(candles) > 1 else recent_close

    # Direction from SMA slope
    sma_slope = sma_20 - sma(candles[:len(candles)-1], 20) if len(candles) > 20 else 0

    if sma_slope > atr_value * 0.1 and recent_close > sma_20:
        return "bullish"
    elif sma_slope < -atr_value * 0.1 and recent_close < sma_20:
        return "bearish"
    elif abs(sma_slope) <= atr_value * 0.05:
        return "neutral"

    # Check for conflict with proposed direction
    if direction == "buy" and sma_slope < -atr_value * 0.05:
        return "conflicting"
    if direction == "sell" and sma_slope > atr_value * 0.05:
        return "conflicting"

    return "neutral"


def _resolve_direction(
    symbol: str,
    direction: str,
    analysis: dict,
) -> str:
    """Resolve the direction to evaluate. Returns 'buy', 'sell', or empty."""
    if direction in ("buy", "sell"):
        return direction
    # Fall back to analysis trend
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
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Create a consistent skip/failure result."""
    setup = {
        "strategy": "fallback4",
        "executable": False,
        "reason": reason,
        "failed_stage": failed_stage,
        "score": score,
        "states": [],
        "rejection_reason": reason,
    }
    return None, setup, {"reason": reason, "approved": False}


def evaluate_fallback4(
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
    risk_percent: float = 0.35,
    minimum_rr: float = 1.5,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Main entry point for Fallback Strategy 4 evaluation.
    
    Called from main.py after ICT, Kingsbalfx, and Fallback 3 all return no valid trade.
    
    Returns:
        (trade_request_dict_or_None, fallback4_setup_dict, safety_dict)
    """
    # ----------------------------------------------------------
    # Master switch and config validation
    # ----------------------------------------------------------
    if not config.FALLBACK4_ENABLED:
        return _skip_result("fallback4_disabled", symbol=symbol)

    config_warnings = config.validate()
    if config_warnings:
        for w in config_warnings:
            LOGGER.warning("[%s] FALLBACK4 CONFIG: %s", symbol, w)

    # ----------------------------------------------------------
    # Extract parameters
    # ----------------------------------------------------------
    is_m1 = config.EXECUTION_TIMEFRAME == "M1"
    execution_tf = config.EXECUTION_TIMEFRAME
    context_tf = config.CONTEXT_TIMEFRAME
    entry_model = config.ENTRY_MODEL

    # Extract candles
    exec_candles = _extract_candles(analysis, execution_tf)
    context_candles = _extract_candles(analysis, context_tf)

    if len(exec_candles) < 15:
        return _skip_result(f"insufficient_{execution_tf}_candles", symbol=symbol)

    # Extract price info
    bid = _to_float(tick.get("bid"))
    ask = _to_float(tick.get("ask"))
    spread = abs(ask - bid) if ask and bid else 0.0
    price = (bid + ask) / 2.0 if bid and ask else 0.0

    # Resolve direction
    resolved_dir = _resolve_direction(symbol, direction, analysis)
    if not resolved_dir:
        return _skip_result("unresolved_direction", symbol=symbol)

    # Point and ATR
    point = _estimate_point(price)
    atr_value = _atr(exec_candles, 14)
    if atr_value <= 0:
        atr_value = price * 0.001  # fallback estimate

    # ----------------------------------------------------------
    # Context bias
    # ----------------------------------------------------------
    context_bias = _extract_context_bias(context_candles, resolved_dir, atr_value)

    # Countertrend check
    if not config.COUNTERTREND_ENABLED:
        if (resolved_dir == "buy" and context_bias == "bearish") or \
           (resolved_dir == "sell" and context_bias == "bullish"):
            return _skip_result(f"countertrend_not_enabled: context={context_bias} direction={resolved_dir}",
                               failed_stage="context_analysis", symbol=symbol)

    LOGGER.info("[%s] FALLBACK4 | eval direction=%s exec=%s ctx=%s bias=%s | M1=%s model=%s",
                symbol, resolved_dir, execution_tf, context_tf, context_bias, is_m1, entry_model)

    # ----------------------------------------------------------
    # 1. DETECT THE RANGE
    # ----------------------------------------------------------
    range_data = detect_range(exec_candles, atr_value, point, is_m1)

    if not range_data.detected:
        return _skip_result(f"no_valid_range: {range_data.rejection_reason}",
                           failed_stage="range_confirmed", symbol=symbol)

    LOGGER.debug("[%s] FALLBACK4 RANGE | H=%.5f L=%.5f W=%.5f W_atr=%.1f quality=%s",
                 symbol, range_data.range_high, range_data.range_low,
                 range_data.range_width, range_data.range_width_atr,
                 range_data.quality_score)

    # ----------------------------------------------------------
    # 2. CLASSIFY SWEEP / BREAKOUT
    # ----------------------------------------------------------
    sweep = classify_sweep(exec_candles, range_data, atr_value, point)

    if not sweep.detected or sweep.classification in ("genuine_breakout", "uncertain"):
        reason = sweep.classification if sweep.detected else "no_sweep_detected"
        return _skip_result(f"sweep_classification: {reason}",
                           failed_stage="sweep_or_breakout_classification", symbol=symbol)

    if sweep.classification not in ("sweep", "probable_sweep"):
        return _skip_result(f"not_confident_sweep: {sweep.classification}",
                           failed_stage="sweep_or_breakout_classification", symbol=symbol)

    LOGGER.debug("[%s] FALLBACK4 SWEEP | side=%s extreme=%.5f pen_atr=%.2f class=%s score=%.2f",
                 symbol, sweep.side, sweep.extreme_price,
                 sweep.penetration_atr, sweep.classification, sweep.sweep_score)

    # ----------------------------------------------------------
    # 3. CONFIRM RANGE RECLAIM
    # ----------------------------------------------------------
    reclaim = confirm_reclaim(
        exec_candles, range_data,
        sweep_side=sweep.side or "",
        sweep_direction=sweep.direction,
        atr_value=atr_value,
    )

    if not reclaim.reclaimed:
        return _skip_result(f"no_reclaim: {reclaim.failure_reason}",
                           failed_stage="range_reclaimed", symbol=symbol)

    LOGGER.debug("[%s] FALLBACK4 RECLAIM | idx=%s strength=%s mode=%s",
                 symbol, reclaim.reclaim_candle_index,
                 reclaim.reclaim_strength, reclaim.mode_used)

    # ----------------------------------------------------------
    # 4. DETECT DISPLACEMENT
    # ----------------------------------------------------------
    displacement = detect_displacement(
        exec_candles, range_data,
        sweep_direction=sweep.direction,
        reclaim_index=reclaim.reclaim_candle_index,
        atr_value=atr_value,
    )

    if not displacement.detected:
        return _skip_result("no_displacement_after_reclaim",
                           failed_stage="displacement_pending", symbol=symbol)

    if displacement.score < config.MIN_DISPLACEMENT_SCORE:
        return _skip_result(f"displacement_score_{displacement.score}_<_{config.MIN_DISPLACEMENT_SCORE}",
                           failed_stage="displacement_pending", symbol=symbol)

    LOGGER.debug("[%s] FALLBACK4 DISPLACEMENT | idx=%s score=%s body=%.2f atr_ratio=%.2f",
                 symbol, displacement.candle_index, displacement.score,
                 displacement.body_ratio, displacement.range_atr_ratio)

    # ----------------------------------------------------------
    # 5. CONFIRM STRUCTURE CHANGE (CHOCH / BOS)
    # ----------------------------------------------------------
    structure_change = confirm_structure_change(
        exec_candles, range_data, displacement,
        direction=sweep.direction,
        atr_value=atr_value,
        point=point,
    )

    if not structure_change.confirmed:
        return _skip_result(f"no_structure_change: {structure_change.rejection_reason}",
                           failed_stage="structure_change_confirmed", symbol=symbol)

    if structure_change.invalidated:
        return _skip_result("structure_change_invalidated_by_next_candle",
                           failed_stage="structure_change_confirmed", symbol=symbol)

    LOGGER.debug("[%s] FALLBACK4 STRUCTURE | method=%s level=%.5f close=%.5f body=%.2f",
                 symbol, structure_change.method, structure_change.swing_level,
                 structure_change.close_level, structure_change.body_ratio)

    # ----------------------------------------------------------
    # 6. CALCULATE ENTRY ZONE
    # ----------------------------------------------------------
    entry = calculate_entry_zone(
        exec_candles, range_data, displacement, reclaim, structure_change,
        sweep_direction=sweep.direction,
        entry_model=entry_model,
        atr_value=atr_value,
        point=point,
        is_m1=is_m1,
    )

    if not entry.confirmed:
        # If model A fails, try model B, then model C
        if entry_model == "A":
            LOGGER.debug("[%s] FALLBACK4 | model A failed, trying model B", symbol)
            entry = calculate_entry_zone(
                exec_candles, range_data, displacement, reclaim, structure_change,
                sweep_direction=sweep.direction,
                entry_model="B",
                atr_value=atr_value, point=point, is_m1=is_m1,
            )
        if not entry.confirmed and entry_model in ("A", "B"):
            LOGGER.debug("[%s] FALLBACK4 | model B failed, trying model C", symbol)
            entry = calculate_entry_zone(
                exec_candles, range_data, displacement, reclaim, structure_change,
                sweep_direction=sweep.direction,
                entry_model="C",
                atr_value=atr_value, point=point, is_m1=is_m1,
            )

    if not entry.confirmed:
        return _skip_result(f"no_entry: {entry.rejection_reason}",
                           failed_stage="entry_zone_calculated", symbol=symbol)

    LOGGER.debug("[%s] FALLBACK4 ENTRY | model=%s price=%.5f zone=[%.5f-%.5f]",
                 symbol, entry.model, entry.entry_price, entry.zone_low, entry.zone_high)

    # Use the entry price
    entry_price = entry.entry_price

    # ----------------------------------------------------------
    # 7. CALCULATE STOP LOSS AND TAKE PROFIT
    # ----------------------------------------------------------
    sl_price, risk, tp1, tp2, tp3, final_tp, targets = calculate_sl_tp(
        entry_price=entry_price,
        direction=sweep.direction.replace("bullish", "buy").replace("bearish", "sell"),
        sweep_extreme=sweep.extreme_price,
        range_data=range_data,
        atr_value=atr_value,
        point=point,
        spread=spread,
    )

    reward_to_tp1 = abs(tp1 - entry_price)
    reward = abs(final_tp - entry_price)
    risk_reward = reward / risk if risk > 0 else 0.0
    rr_to_tp1 = reward_to_tp1 / risk if risk > 0 else 0.0

    # ----------------------------------------------------------
    # 8. CHECK SPREAD
    # ----------------------------------------------------------
    spread_ok, spread_reason = check_spread_allowed(spread, is_m1)
    if not spread_ok:
        return _skip_result(f"spread: {spread_reason}",
                           failed_stage="order_approval", symbol=symbol)

    # ----------------------------------------------------------
    # 9. Check MINIMUM RR
    # ----------------------------------------------------------
    if risk_reward < minimum_rr:
        return _skip_result(f"risk_reward_{risk_reward:.2f}_<_{minimum_rr:.2f}",
                           failed_stage="order_approval", symbol=symbol)

    if risk_reward < config.MIN_RR:
        return _skip_result(f"risk_reward_{risk_reward:.2f}_<_{config.MIN_RR:.2f}_config",
                           failed_stage="order_approval", symbol=symbol)

    # ----------------------------------------------------------
    # 10. POSITION SIZE
    # ----------------------------------------------------------
    risk_amount = calculate_position_size(entry_price, sl_price, account, risk_percent, is_m1)

    lot = 0.0
    if mt5_connector and hasattr(mt5_connector, 'calculate_volume_for_risk'):
        from execution.mt5_connector import calculate_volume_for_risk as _calc_vol
        try:
            lot = _calc_vol(symbol, entry_price, sl_price, risk_amount)
        except Exception as exc:
            LOGGER.warning("[%s] FALLBACK4 | volume calc failed: %s", symbol, exc)

    if lot <= 0:
        return _skip_result("position_size_zero_or_below_minimum",
                           failed_stage="order_approval", symbol=symbol)

    # ----------------------------------------------------------
    # 11. DUPLICATE CHECK
    # ----------------------------------------------------------
    dup_ok, dup_reason = check_duplicate_range_setup(
        symbol=symbol,
        direction=sweep.direction,
        range_high=range_data.range_high,
        range_low=range_data.range_low,
        sweep_side=sweep.side or "",
        fallback3_setup=fallback3_setup,
    )
    if not dup_ok:
        return _skip_result(f"duplicate: {dup_reason}",
                           failed_stage="order_approval", symbol=symbol)

    # ----------------------------------------------------------
    # 12. GLOBAL RISK PROTECTION CHECK
    # ----------------------------------------------------------
    from risk.protection import can_trade
    identity = setup_identity(
        symbol=symbol,
        direction=sweep.direction.replace("bullish", "buy").replace("bearish", "sell"),
        range_high=range_data.range_high,
        range_low=range_data.range_low,
        sweep_side=sweep.side or "",
        sweep_extreme=sweep.extreme_price,
    )
    if not can_trade(symbol, identity, cooldown=config.PER_SETUP_COOLDOWN):
        return _skip_result("global_risk_rejected_duplicate_setup",
                           failed_stage="order_approval", symbol=symbol)

    # ----------------------------------------------------------
    # 13. PRE-TRADE SAFETY VALIDATION
    # ----------------------------------------------------------
    from execution.pre_trade_validator import validate_execution_safety
    trade_dir = sweep.direction.replace("bullish", "buy").replace("bearish", "sell")
    safe, safety = validate_execution_safety(
        symbol, trade_dir, entry_price, sl_price,
        final_tp, lot, account, positions,
    )
    if not safe:
        return None, {
            "strategy": "fallback4",
            "executable": True,
            "reason": safety.get("reason", "pre_trade_rejected"),
            "score": 0,
            "states": [],
        }, safety

    # ----------------------------------------------------------
    # 14. CALCULATE SCORE
    # ----------------------------------------------------------
    score, score_components = calculate_score(
        range_data=range_data,
        sweep=sweep,
        reclaim=reclaim,
        displacement=displacement,
        structure_change=structure_change,
        entry=entry,
        context_bias=context_bias,
        risk_reward=risk_reward,
        is_m1=is_m1,
    )

    if score < config.SCORE_MINIMUM:
        return _skip_result(f"score_{score}_<_{config.SCORE_MINIMUM}",
                           failed_stage="order_approval", symbol=symbol)

    # ----------------------------------------------------------
    # 15. BUILD UNIQUE SETUP ID
    # ----------------------------------------------------------
    setup_id = hashlib.sha256(
        f"{symbol}|{range_data.range_high:.8f}|{range_data.range_low:.8f}|"
        f"{sweep.side}|{sweep.extreme_price:.8f}|{execution_tf}|"
        f"{int(time.time())}".encode()
    ).hexdigest()[:16]

    # ----------------------------------------------------------
    # 16. BUILD TRADE REQUEST
    # ----------------------------------------------------------
    range_target_objects = [
        RangeTarget(level=t["level"], label=t["label"], allocation=t["allocation"])
        for t in targets
    ]

    fb4_result = Fallback4SetupResult(
        symbol=symbol,
        direction=trade_dir,
        executable=True,
        score=score,
        score_components=score_components,
        range_data=range_data,
        sweep=sweep,
        reclaim=reclaim,
        displacement=displacement,
        structure_change=structure_change,
        entry=entry,
        entry_price=entry_price,
        stop_loss=sl_price,
        take_profit_primary=final_tp,
        risk_reward=risk_reward,
        position_size=lot,
        targets=range_target_objects,
        setup_id=setup_id,
        activated=True,
        context_bias=context_bias,
        execution_timeframe=execution_tf,
        context_timeframe=context_tf,
        source_strategy="fallback4",
    )

    # Run state machine for logging
    sm = Fallback4StateMachine()
    fb4_result = sm.process(
        symbol=symbol,
        direction=trade_dir,
        range_data=range_data,
        sweep=sweep,
        reclaim=reclaim,
        displacement=displacement,
        structure_change=structure_change,
        entry=entry,
        score=score,
        score_components=score_components,
        ict_setup=ict_setup,
        kingsbalfx_setup=kingsbalfx_setup,
        fallback3_setup=fallback3_setup,
        account=account,
        positions=positions,
        context_bias=context_bias,
        execution_timeframe=execution_tf,
        context_timeframe=context_tf,
    )

    fb4_result.executable = True
    fb4_result.entry_price = entry_price
    fb4_result.stop_loss = sl_price
    fb4_result.take_profit_primary = final_tp
    fb4_result.risk_reward = risk_reward
    fb4_result.position_size = lot
    fb4_result.targets = range_target_objects
    fb4_result.setup_id = setup_id
    fb4_result.activated = True

    # ----------------------------------------------------------
    # 17. GENERATE SIGNAL
    # ----------------------------------------------------------
    request = generate_fallback4_signal(
        result=fb4_result,
        entry_price=entry_price,
        stop_loss=sl_price,
        take_profit=final_tp,
        lot=lot,
        targets=[{"level": t.level, "label": t.label, "allocation": t.allocation}
                  for t in range_target_objects],
    )
    request.identity = identity
    request.identity_context["identity"] = identity

    # Register the trade setup
    register_fallback4_trade(
        symbol=symbol,
        direction=trade_dir,
        range_high=range_data.range_high,
        range_low=range_data.range_low,
        sweep_side=sweep.side or "",
    )

    # Register with global risk
    from risk.protection import register_trade
    register_trade(symbol, identity)

    # ----------------------------------------------------------
    # 18. LOG THE RESULT
    # ----------------------------------------------------------
    log_fallback4_result(fb4_result)
    LOGGER.info(
        "[%s] FALLBACK4 | FINAL DECISION=%s | score=%s RR=%.2f model=%s "
        "range=%.5f-%.5f sweep=%s entry=%.5f sl=%.5f tp=%.5f lot=%.4f",
        symbol,
        trade_dir.upper(),
        score,
        risk_reward,
        entry.model,
        range_data.range_low,
        range_data.range_high,
        sweep.side,
        entry_price,
        sl_price,
        final_tp,
        lot,
    )

    # Build the response dict for main.py
    setup_dict = fb4_result.to_dict()
    setup_dict["states"] = fb4_result.states
    setup_dict["evidence"] = fb4_result.evidence

    return request.to_dict(), setup_dict, {"approved": True, "reason": "all_checks_passed"}
