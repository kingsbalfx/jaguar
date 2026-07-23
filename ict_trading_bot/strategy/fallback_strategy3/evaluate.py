"""
FALLBACK STRATEGY 3 - Main Evaluation Pipeline
================================================
Public entry point for Fallback 3 evaluation.
Called from __init__ which is called from main.py.
Contains the actual evaluate_fallback3 function that orchestrates
the entire sequence of analysis steps.
"""

from typing import Any, Dict, List, Optional, Tuple

from . import config
from . import logging as fb3_logger
from .models import (
    FallbackSetupResult, SweepResult, CHOCHResult, MACDResult, SMAResult,
    ConsolidationResult, EntryZoneResult, make_state,
)
from .htf_bias import determine_htf_bias, htf_supports_reversal
from .liquidity import identify_key_levels, identify_liquidity_zones
from .sweep_classifier import classify_sweep
from .choch import detect_choch
from .macd_confirmation import confirm_macd
from .sma_confirmation import confirm_sma
from .consolidation_filter import detect_consolidation
from .entry_zone import calculate_entry_zone
from .risk import (
    check_risk_gate, check_duplicate_setup, register_fallback3_trade,
    calculate_sl, calculate_tp,
)
from .signal import generate_fallback3_signal, setup_identity as fb3_identity
from .state_machine import Fallback3StateMachine
from .indicators import atr, find_swing_points, sma_values

import logging
LOGGER = logging.getLogger("fallback3")


def evaluate_fallback3(
    symbol: str,
    direction: Optional[str],
    analysis: Dict[str, Any],
    tick: Dict[str, Any],
    account: Dict[str, Any],
    positions: List[Dict[str, Any]],
    mt5_connector: Any,
    ict_setup: Dict[str, Any],
    kingsbalfx_setup: Dict[str, Any],
    risk_percent: float = None,
    minimum_rr: float = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Main entry point for Fallback Strategy 3 evaluation.
    
    Called from main.py after both ICT and Kingsbalfx strategies skip.
    """
    # Check master switch
    if not config.FALLBACK3_ENABLED:
        LOGGER.debug("[%s] FALLBACK3 | disabled by config", symbol)
        return _skip_result("fallback3_disabled")
    
    # Validate config
    config_warnings = config.validate()
    if config_warnings:
        LOGGER.warning("[%s] FALLBACK3 config warnings: %s", symbol, "; ".join(config_warnings))
    
    risk_perc = risk_percent if risk_percent is not None else config.RISK_PERCENT
    min_rr = minimum_rr if minimum_rr is not None else config.MIN_RR
    
    if not isinstance(ict_setup, dict):
        ict_setup = {}
    if not isinstance(kingsbalfx_setup, dict):
        kingsbalfx_setup = {}

    # Debug: validate inputs before using them
    if not isinstance(ict_setup, dict):
        LOGGER.warning("[%s] FALLBACK3 | ict_setup type=%s value=%s", symbol, type(ict_setup).__name__, ict_setup)
    if not isinstance(kingsbalfx_setup, dict):
        LOGGER.warning("[%s] FALLBACK3 | kingsbalfx_setup type=%s value=%s", symbol, type(kingsbalfx_setup).__name__, kingsbalfx_setup)
    
    fb3_logger.log_fallback3_activation(
        symbol,
        "skip" if not ict_setup.get("executable") else "valid",
        "skip" if not kingsbalfx_setup.get("valid", False) else "valid",
        ict_setup.get("reason", ""),
        kingsbalfx_setup.get("reason", ""),
    )
    
    # ============================================================
    # STEP 0: Risk Gate (pre-checks before analysis)
    # ============================================================
    try:
        risk_passed, risk_reason = check_risk_gate(symbol, direction or "", account, positions, ict_setup, kingsbalfx_setup)
    except Exception as _rg_exc:
        LOGGER.warning("[%s] FALLBACK3 | check_risk_gate error: %s", symbol, _rg_exc, exc_info=True)
        return _skip_result(f"risk_gate_error: {_rg_exc}", {
            "risk_error": str(_rg_exc),
        })
    if not risk_passed:
        return _skip_result(f"risk_gate: {risk_reason}", {
            "risk_gate_passed": False,
            "risk_reason": risk_reason,
        })
    
    # ============================================================
    # Extract candle data from analysis dict
    # ============================================================
    price = (tick.get("bid", 0) + tick.get("ask", 0)) / 2.0 if tick else 0.0
    
    # HTF candles (H1)
    htf_timeframe = config.HTF_TIMEFRAME  # "H1"
    htf_state = analysis.get("HTF") or analysis.get(htf_timeframe) or {}
    htf_candles = htf_state.get("recent_candles", [])
    htf_swings = htf_state.get("swings", [])
    htf_trend = (
        htf_state.get("trend")
        or (analysis.get("topdown") or {}).get("h1_trend")
        or (analysis.get("h1_m15_alignment") or {}).get("h1_trend")
        or None
    )
    htf_market_structure = htf_state.get("market_structure", {})
    
    # Structure timeframe candles (M15)
    structure_tf = config.STRUCTURE_TIMEFRAME  # "M15"
    structure_state = analysis.get("MTF") or analysis.get(structure_tf) or {}
    structure_candles = structure_state.get("recent_candles", [])
    
    # Execution timeframe candles (M5)
    exec_tf = config.EXECUTION_TIMEFRAME  # "M5"
    exec_state = analysis.get("EXECUTION") or analysis.get(exec_tf) or {}
    exec_candles = exec_state.get("recent_candles", [])
    
    # Fallbacks
    if not exec_candles or not isinstance(exec_candles, list):
        exec_candles = analysis.get("m5_candles", [])
    if not htf_candles or not isinstance(htf_candles, list):
        htf_candles = (analysis.get("HTF") or {}).get("recent_candles", [])
    if not structure_candles or not isinstance(structure_candles, list):
        structure_candles = (analysis.get("MTF") or {}).get("recent_candles", []) or exec_candles
    
    # Sanitize: ensure we have a list of dicts, not raw floats
    def _ensure_candle_dicts(candles):
        """Convert list of floats to empty list (invalid data)."""
        if isinstance(candles, list) and candles and not isinstance(candles[0], dict):
            return []
        return candles
    
    exec_candles = _ensure_candle_dicts(exec_candles)
    htf_candles = _ensure_candle_dicts(htf_candles)
    structure_candles = _ensure_candle_dicts(structure_candles)
    working_candles = _ensure_candle_dicts(structure_candles or exec_candles)
    
    # ============================================================
    # STEP 1: Determine HTF Bias
    # ============================================================
    htf_bias, htf_confidence = determine_htf_bias(
        htf_candles, htf_swings, htf_trend, htf_market_structure,
    )
    
    trade_direction = _resolve_direction(direction, htf_bias)
    if not trade_direction:
        return _skip_result("no_trade_direction", {
            "htf_bias": htf_bias,
            "requested_direction": direction,
        })
    
    # Check HTF supports direction
    if not htf_supports_reversal(htf_bias, trade_direction, config.COUNTERTREND_ENABLED):
        return _skip_result(f"htf_bias_conflict: htf_bias={htf_bias} vs trade={trade_direction}", {
            "htf_bias": htf_bias,
            "trade_direction": trade_direction,
            "countertrend_enabled": config.COUNTERTREND_ENABLED,
        })
    
    # ============================================================
    # STEP 2: Map Liquidity Levels
    # ============================================================
    levels = identify_key_levels(working_candles)
    liq_zones = identify_liquidity_zones(levels, trade_direction, price)
    
    if not liq_zones:
        return _skip_result("no_liquidity_zones", {"direction": trade_direction})
    
    nearest_zone = liq_zones[0]
    liq_level = nearest_zone.get("level", 0.0)
    
    # ============================================================
    # STEP 3-5: Sweep Analysis
    # ============================================================
    sweep = classify_sweep(
        exec_candles or working_candles,
        trade_direction,
        liq_level,
        structure_candles,
    )
    
    if not sweep.detected:
        return _skip_result("no_sweep_interaction", {
            "liquidity_level": liq_level,
            "sweep_detected": False,
        })
    
    # ============================================================
    # STEP 6-7: CHOCH Detection
    # ============================================================
    choch = detect_choch(
        exec_candles or working_candles,
        trade_direction,
        sweep.candle_count_beyond > 0,
        structure_candles,
    )
    
    # ============================================================
    # STEP 8: MACD + SMA Confirmation
    # ============================================================
    choch_index = choch.candle_index if choch.detected else len(exec_candles or working_candles) - 1
    
    macd_result = confirm_macd(
        exec_candles or working_candles,
        choch_index,
        choch.direction if choch.detected else ("bullish" if trade_direction == "buy" else "bearish"),
    )
    
    fast_sma_vals = sma_values(exec_candles or working_candles, config.SMA_FAST)
    slow_sma_vals = sma_values(exec_candles or working_candles, config.SMA_SLOW)
    
    sma_result = confirm_sma(
        exec_candles or working_candles,
        choch_index,
        choch.direction if choch.detected else ("bullish" if trade_direction == "buy" else "bearish"),
    )
    
    consolidation = detect_consolidation(
        exec_candles or working_candles,
        fast_sma_vals,
        slow_sma_vals,
    )
    
    # ============================================================
    # STEP 9: Entry Zone
    # ============================================================
    entry_zone = calculate_entry_zone(
        exec_candles or working_candles,
        trade_direction,
        choch_index,
        sweep.displaced_high if trade_direction == "sell" else sweep.displaced_low,
    )
    
    # ============================================================
    # STEP 10-12: Entry, SL/TP, Risk
    # ============================================================
    point = tick.get("point", _estimate_point(price)) if tick else _estimate_point(price)
    spread = abs(tick.get("ask", 0) - tick.get("bid", 0)) if tick else 0.0
    avg_rng = atr(exec_candles or working_candles, period=14)
    
    # Entry price
    if config.ENTRY_METHOD == "limit" and entry_zone.found and entry_zone.price_in_zone:
        entry_price = entry_zone.midpoint
    else:
        entry_price = tick.get("ask", price) if trade_direction == "buy" else tick.get("bid", price)
    
    # Stop loss from structure
    structure_low = (
        levels.get("protected_low", {}).get("level", liq_level * 0.99) if trade_direction == "buy"
        else liq_level * 0.99
    )
    structure_high = (
        levels.get("protected_high", {}).get("level", liq_level * 1.01) if trade_direction == "sell"
        else liq_level * 1.01
    )
    
    sl, risk_dist = calculate_sl(
        entry_price, trade_direction, liq_level,
        structure_low, structure_high, avg_rng, point, spread,
    )
    
    # Take profit from nearest targets + zone edges
    target_prices = [z.get("level") for z in liq_zones if z.get("level")]
    if entry_zone.found:
        if trade_direction == "buy":
            target_prices.append(entry_zone.zone_high * 1.5)
        else:
            target_prices.append(entry_zone.zone_low * 0.67)
    
    tp, reward = calculate_tp(entry_price, trade_direction, target_prices, risk_dist, min_rr)
    rr = reward / risk_dist if risk_dist > 0 else 0.0
    
    # ============================================================
    # Run the State Machine with all pre-computed data
    # ============================================================
    state_machine = Fallback3StateMachine()
    result = state_machine.process(
        symbol=symbol,
        htf_bias=htf_bias,
        htf_confidence=htf_confidence,
        levels=levels,
        sweep=sweep,
        choch=choch,
        macd=macd_result,
        sma=sma_result,
        consolidation=consolidation,
        entry_zone=entry_zone,
        entry_price=entry_price,
        stop_loss=sl,
        take_profit=tp,
        risk_reward=rr,
        position_size=0.0,
        strategy_1_result="skip",
        strategy_1_reason=ict_setup.get("reason", ""),
        strategy_2_result="skip",
        strategy_2_reason=kingsbalfx_setup.get("reason", ""),
    )
    
    fb3_logger.log_setup_result(symbol, result)
    
    # If state machine says no-go
    if not result.executable:
        return _skip_result(result.rejection_reason, {
            "failed_stage": result.failed_stage,
            "score": result.score,
            "states": [s.get("name") for s in result.states],
        })
    
    # ============================================================
    # Duplicate check
    # ============================================================
    dup_passed, dup_reason = check_duplicate_setup(
        symbol, trade_direction, liq_level,
        entry_zone.midpoint if entry_zone.found else 0,
    )
    if not dup_passed:
        return _skip_result(f"duplicate: {dup_reason}", {
            "setup_id": result.setup_id,
        })
    
    # ============================================================
    # Check via global risk protection
    # ============================================================
    from risk.protection import can_trade, setup_identity as global_identity
    
    setup_id = fb3_identity(symbol, trade_direction, liq_level, entry_zone.midpoint if entry_zone.found else 0)
    if not can_trade(symbol, setup_id, cooldown=config.PER_SETUP_COOLDOWN):
        return _skip_result("global_duplicate_setup", {
            "setup_id": setup_id,
            "cooldown": config.PER_SETUP_COOLDOWN,
        })
    
    # ============================================================
    # Calculate volume
    # ============================================================
    risk_amount = float(account.get("balance", 0)) * (risk_perc / 100.0)
    volume = mt5_connector.calculate_volume_for_risk(symbol, entry_price, sl, risk_amount)
    if volume <= 0:
        return _skip_result("zero_volume", {
            "risk_amount": risk_amount, "entry": entry_price, "sl": sl,
        })
    
    # ============================================================
    # Pre-trade safety validation
    # ============================================================
    from execution.pre_trade_validator import validate_execution_safety
    safe, safety = validate_execution_safety(
        symbol, trade_direction, entry_price, sl, tp, volume, account, positions,
    )
    if not safe:
        return _skip_result(f"safety: {safety.get('reason', '')}", {"safety": safety})
    
    # ============================================================
    # ALL PASSED — register and return trade
    # ============================================================
    result.position_size = volume
    result.stop_loss = sl
    result.take_profit = tp
    result.entry_price = entry_price
    result.risk_reward = rr
    result.executable = True
    result.direction = trade_direction
    
    # Register in local risk tracker
    register_fallback3_trade(symbol, trade_direction, liq_level, entry_zone.midpoint if entry_zone.found else 0)
    
    # Register in global risk protection
    from risk.protection import register_trade as global_register
    global_register(symbol, setup_id)
    
    # Build trade request
    trade_request = generate_fallback3_signal(result, entry_price, sl, tp, volume)
    trade_request_dict = trade_request.to_dict()
    trade_request_dict["identity"] = setup_id
    
    LOGGER.info(
        "[%s] FALLBACK3 TRADE | direction=%s | entry=%.5f | sl=%.5f | tp=%.5f | rr=%.2f | lot=%.2f | score=%d",
        symbol, trade_direction, entry_price, sl, tp, rr, volume, result.score,
    )
    
    return (trade_request_dict, _build_fallback3_setup(result), safety)


def _resolve_direction(direction: Optional[str], htf_bias: Optional[str]) -> Optional[str]:
    if direction in ("buy", "sell"):
        return direction
    if htf_bias == "bullish":
        return "buy"
    if htf_bias == "bearish":
        return "sell"
    return None


def _estimate_point(price: float) -> float:
    if price >= 1000:
        return 0.01
    if price >= 100:
        return 0.01
    if price >= 10:
        return 0.001
    return 0.0001


def _skip_result(reason: str, evidence: Optional[Dict[str, Any]] = None) -> Tuple[None, Dict[str, Any], Dict[str, Any]]:
    skip_setup = {
        "strategy": "fallback3",
        "executable": False,
        "direction": None,
        "reason": reason,
        "evidence": evidence or {},
    }
    skip_safety = {"reason": reason}
    return None, skip_setup, skip_safety


def _build_fallback3_setup(result: FallbackSetupResult) -> Dict[str, Any]:
    """Build setup dict compatible with main.py reporting."""
    return {
        "strategy": "fallback3",
        "executable": result.executable,
        "direction": result.direction,
        "reason": result.reason,
        "score": result.score,
        "score_components": result.score_components,
        "states": result.states,
        "total_steps": len(Fallback3StateMachine.PROGRESSION),
        "evidence": {
            "sweep": {
                "classification": result.sweep.classification,
                "score": result.sweep.classification_score,
                "displacement": result.sweep.displacement_detected,
                "return_inside": result.sweep.return_inside,
            },
            "choch": {
                "detected": result.choch.detected,
                "direction": result.choch.direction,
                "confirmed_candle": result.choch.break_candle_confirmed,
                "close_level": result.choch.close_level,
                "candle_index": result.choch.candle_index,
            },
            "macd": {
                "confirmed": result.macd.confirmed,
                "contradiction": result.macd.contradiction,
            },
            "sma": {
                "confirmed": result.sma.confirmed,
                "contradiction": result.sma.contradiction,
            },
            "entry_zone": {
                "found": result.entry_zone.found,
                "fib_level": result.entry_zone.fib_level,
                "midpoint": result.entry_zone.midpoint,
                "quality_score": result.entry_zone.quality_score,
                "confluence": result.entry_zone.confluence_types,
            },
            "consolidation": {
                "consolidating": result.consolidation.consolidating,
                "confidence": result.consolidation.confidence,
            },
        },
        "plan": {
            "entry": result.entry_price,
            "sl": result.stop_loss,
            "tp": result.take_profit,
            "rr": result.risk_reward,
            "position_size": result.position_size,
        },
        "failed_step": result.failed_stage,
        "rejection_reason": result.rejection_reason,
    }
