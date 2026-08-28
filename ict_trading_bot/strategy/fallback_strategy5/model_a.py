"""
FALLBACK STRATEGY 5 — Model A: Trend Pullback Continuation
=============================================================
Bullish:
1. Confirmed bullish trend on higher timeframe.
2. Price pulls back toward EMA20, EMA50, prior breakout level, FVG, order block, 38.2-61.8% retracement.
3. Pullback remains above protected trend low.
4. Bearish pullback momentum weakens.
5. Sell-side liquidity may be taken beneath a minor internal low.
6. Bullish rejection or displacement develops.
7. M1 or M5 confirms bullish CHOCH/BOS.
8. Entry trigger closes.

Bearish is inverse.
"""

from typing import List, Optional, Tuple, Dict

from . import config
from .indicators import (
    ema, ema_values, atr, find_swing_points,
    candle_direction, candle_body_ratio, candle_range, candle_body,
    _to_float, find_swing_points,
)
from .trend import get_protected_levels, BULLISH, BEARISH
from .fb5_logging import log_setup_scan


def evaluate_model_a(
    symbol: str,
    direction: str,
    trend_direction: str,
    setup_candles: List[dict],
    exec_candles: List[dict],
    htf_candles: List[dict],
    atr_value: float,
    trend_evidence: dict,
    mode: str,
) -> Tuple[bool, dict]:
    """
    Evaluate Model A: Trend Pullback Continuation.
    
    Returns:
        (passed, result_dict)
    """
    result = {
        "model": "A",
        "detected": False,
        "pullback_detected": False,
        "pullback_to_level": None,
        "pullback_depth": 0.0,
        "retracement_ratio": 0.0,
        "protected_structure_preserved": False,
        "momentum_exhaustion": False,
        "liquidity_swept": False,
        "rejection_confirmed": False,
        "displacement_confirmed": False,
        "choch_bos_confirmed": False,
        "entry_price": None,
        "stop_loss": None,
        "score": 0,
        "rejection_reason": "",
    }

    # Need enough candles
    if direction == "buy" and trend_direction != BULLISH:
        result["rejection_reason"] = "trend_not_bullish"
        return False, result
    if direction == "sell" and trend_direction != BEARISH:
        result["rejection_reason"] = "trend_not_bearish"
        return False, result

    min_candles = max(config.EMA_MEDIUM, 30)
    trading_candles = exec_candles if mode in ("B", "C") else setup_candles
    if len(trading_candles) < min_candles:
        result["rejection_reason"] = f"insufficient_candles:{len(trading_candles)}<{min_candles}"
        return False, result

    # ============================================================
    # 1. Identify current trend impulse
    # ============================================================
    recent = trading_candles[-min(20, len(trading_candles)):]
    if direction == "buy":
        impulse_high = max(_to_float(c.get("high")) for c in recent)
        impulse_low = min(_to_float(c.get("low")) for c in recent)
    else:
        impulse_high = max(_to_float(c.get("high")) for c in recent)
        impulse_low = min(_to_float(c.get("low")) for c in recent)

    impulse_range = impulse_high - impulse_low
    if impulse_range <= 0:
        result["rejection_reason"] = "invalid_impulse_range"
        return False, result

    # ============================================================
    # 2. Detect pullback
    # ============================================================
    # A pullback is a counter-trend move after an impulse
    lookback = min(15, len(trading_candles) - 5)
    pullback_start_idx = None
    pullback_low_idx = None
    pullback_high_idx = None

    if direction == "buy":
        # Find the most recent swing low that is below the previous swing highs
        for i in range(len(trading_candles) - 1, max(5, len(trading_candles) - lookback), -1):
            candle = trading_candles[i]
            prev = trading_candles[i - 1] if i > 0 else None
            if prev and _to_float(candle.get("low")) < _to_float(prev.get("low")):
                pullback_low_idx = i
                break
        # Find the start of the pullback (the high before the decline)
        if pullback_low_idx is not None:
            for i in range(pullback_low_idx, max(1, pullback_low_idx - 10), -1):
                if _to_float(trading_candles[i].get("high")) > _to_float(trading_candles[pullback_low_idx].get("high")):
                    pullback_start_idx = i
                    break
    else:
        # Bearish: find the most recent swing high above previous swing lows
        for i in range(len(trading_candles) - 1, max(5, len(trading_candles) - lookback), -1):
            candle = trading_candles[i]
            prev = trading_candles[i - 1] if i > 0 else None
            if prev and _to_float(candle.get("high")) > _to_float(prev.get("high")):
                pullback_high_idx = i
                break
        if pullback_high_idx is not None:
            for i in range(pullback_high_idx, max(1, pullback_high_idx - 10), -1):
                if _to_float(trading_candles[i].get("low")) < _to_float(trading_candles[pullback_high_idx].get("low")):
                    pullback_start_idx = i
                    break

    if pullback_start_idx is None:
        result["rejection_reason"] = "no_pullback_detected"
        return False, result

    result["pullback_detected"] = True

    # ============================================================
    # 3. Calculate pullback depth & retracement ratio
    # ============================================================
    if direction == "buy" and pullback_low_idx is not None:
        pullback_low_price = _to_float(trading_candles[pullback_low_idx].get("low"))
        pullback_high_price = max(
            _to_float(c.get("high"))
            for c in trading_candles[pullback_start_idx:pullback_low_idx + 1]
        )
        pullback_depth = pullback_high_price - pullback_low_price
        retracement_ratio = pullback_depth / impulse_range if impulse_range > 0 else 0
        result["pullback_depth"] = pullback_depth
        result["retracement_ratio"] = round(retracement_ratio, 3)
        result["pullback_to_level"] = pullback_low_price

        # Check if retracement is in the ideal 38.2-61.8% range
        if retracement_ratio < 0.2 or retracement_ratio > 0.8:
            result["rejection_reason"] = f"retracement_ratio_{retracement_ratio:.2f}_outside_ideal"
            return False, result
    elif direction == "sell" and pullback_high_idx is not None:
        pullback_high_price = _to_float(trading_candles[pullback_high_idx].get("high"))
        pullback_low_price = min(
            _to_float(c.get("low"))
            for c in trading_candles[pullback_start_idx:pullback_high_idx + 1]
        )
        pullback_depth = pullback_high_price - pullback_low_price
        retracement_ratio = pullback_depth / impulse_range if impulse_range > 0 else 0
        result["pullback_depth"] = pullback_depth
        result["retracement_ratio"] = round(retracement_ratio, 3)
        result["pullback_to_level"] = pullback_high_price

        if retracement_ratio < 0.2 or retracement_ratio > 0.8:
            result["rejection_reason"] = f"retracement_ratio_{retracement_ratio:.2f}_outside_ideal"
            return False, result

    # ============================================================
    # 4. Check protected structure
    # ============================================================
    protected = get_protected_levels(htf_candles, trend_direction)
    if direction == "buy":
        protected_low = protected.get("protected_low")
        pullback_extreme = _to_float(trading_candles[pullback_low_idx].get("low")) if pullback_low_idx else 0
        if protected_low and pullback_extreme < protected_low:
            result["rejection_reason"] = f"pullback_broke_protected_low:{pullback_extreme:.5f}_<_{protected_low:.5f}"
            return False, result
        result["protected_structure_preserved"] = True
        result["protected_level"] = protected_low
    else:
        protected_high = protected.get("protected_high")
        pullback_extreme = _to_float(trading_candles[pullback_high_idx].get("high")) if pullback_high_idx else 0
        if protected_high and pullback_extreme > protected_high:
            result["rejection_reason"] = f"pullback_broke_protected_high:{pullback_extreme:.5f}_>_{protected_high:.5f}"
            return False, result
        result["protected_structure_preserved"] = True
        result["protected_level"] = protected_high

    # ============================================================
    # 5. Check pullback momentum exhaustion
    # ============================================================
    exhaustion_start = pullback_low_idx if direction == "buy" else pullback_high_idx
    if exhaustion_start:
        exhaustion_candles = trading_candles[exhaustion_start:exhaustion_start + min(5, len(trading_candles) - exhaustion_start)]
        if len(exhaustion_candles) >= 2:
            # Check for reducing range or direction change
            last_dir = candle_direction(exhaustion_candles[-1])
            prev_dir = candle_direction(exhaustion_candles[-2]) if len(exhaustion_candles) >= 2 else None
            last_range = candle_range(exhaustion_candles[-1])
            prev_range = candle_range(exhaustion_candles[-2]) if len(exhaustion_candles) >= 2 else last_range

            if direction == "buy":
                # Look for bullish rejection at the pullback low
                momentum_exhausted = (
                    (last_dir == "bullish" and prev_dir in ("bearish", None))
                    or (last_range < prev_range * 0.7)
                    or (candle_body_ratio(exhaustion_candles[-1]) > 0.5)
                )
            else:
                momentum_exhausted = (
                    (last_dir == "bearish" and prev_dir in ("bullish", None))
                    or (last_range < prev_range * 0.7)
                    or (candle_body_ratio(exhaustion_candles[-1]) > 0.5)
                )
            result["momentum_exhaustion"] = momentum_exhausted
            if not momentum_exhausted:
                result["rejection_reason"] = "pullback_momentum_not_exhausted"
                return False, result

    # ============================================================
    # 6. Check liquidity sweep at pullback extreme
    # ============================================================
    if direction == "buy" and pullback_low_idx is not None:
        # Check if the pullback low swept a minor low (internal swing low)
        lookback_candles = trading_candles[:pullback_low_idx]
        if len(lookback_candles) >= 5:
            for i in range(pullback_low_idx - 2, max(0, pullback_low_idx - 10), -1):
                if _to_float(trading_candles[i].get("low")) < _to_float(trading_candles[pullback_low_idx].get("low")):
                    result["liquidity_swept"] = True
                    result["swept_level"] = _to_float(trading_candles[i].get("low"))
                    break
    elif direction == "sell" and pullback_high_idx is not None:
        lookback_candles = trading_candles[:pullback_high_idx]
        if len(lookback_candles) >= 5:
            for i in range(pullback_high_idx - 2, max(0, pullback_high_idx - 10), -1):
                if _to_float(trading_candles[i].get("high")) > _to_float(trading_candles[pullback_high_idx].get("high")):
                    result["liquidity_swept"] = True
                    result["swept_level"] = _to_float(trading_candles[i].get("high"))
                    break

    # ============================================================
    # 7. Check displacement and CHOCH/BOS
    # ============================================================
    if pullback_low_idx is not None:
        post_pullback = trading_candles[pullback_low_idx: pullback_low_idx + min(6, len(trading_candles) - pullback_low_idx)]
    elif pullback_high_idx is not None:
        post_pullback = trading_candles[pullback_high_idx: pullback_high_idx + min(6, len(trading_candles) - pullback_high_idx)]
    else:
        post_pullback = []

    if len(post_pullback) >= 2:
        # Check displacement (strong trend-direction candle)
        displacement_candle = None
        for i, c in enumerate(post_pullback):
            body_ratio = candle_body_ratio(c)
            c_range = candle_range(c)
            c_dir = candle_direction(c)

            if direction == "buy" and c_dir == "bullish" and body_ratio >= config.CONFIRMATION_MIN_BODY_RATIO and c_range >= atr_value * 0.5:
                displacement_candle = c
                result["displacement_confirmed"] = True
                break
            elif direction == "sell" and c_dir == "bearish" and body_ratio >= config.CONFIRMATION_MIN_BODY_RATIO and c_range >= atr_value * 0.5:
                displacement_candle = c
                result["displacement_confirmed"] = True
                break

        if displacement_candle:
            # Check for CHOCH/BOS after displacement
            if len(post_pullback) >= 3:
                if direction == "buy":
                    # BOS: price breaks above the pullback high
                    pullback_high = max(_to_float(c.get("high")) for c in post_pullback)
                    if _to_float(post_pullback[-1].get("close")) > pullback_high * 0.999:
                        result["choch_bos_confirmed"] = True
                else:
                    pullback_low = min(_to_float(c.get("low")) for c in post_pullback)
                    if _to_float(post_pullback[-1].get("close")) < pullback_low * 1.001:
                        result["choch_bos_confirmed"] = True

    # ============================================================
    # 8. Score the setup
    # ============================================================
    score = 0
    if result["pullback_detected"]:
        score += 10
    if 0.382 <= retracement_ratio <= 0.618:
        score += 15  # Ideal retracement
    elif 0.2 <= retracement_ratio <= 0.8:
        score += 8
    if result["protected_structure_preserved"]:
        score += 10
    if result["momentum_exhaustion"]:
        score += 10
    if result["liquidity_swept"]:
        score += 10
    if result["displacement_confirmed"]:
        score += 15
    if result["choch_bos_confirmed"]:
        score += 15

    result["score"] = score
    result["detected"] = score >= 50

    if not result["detected"]:
        result["rejection_reason"] = f"score_{score}_below_50"

    log_setup_scan(symbol, "A", result["detected"], result.get("rejection_reason", ""), score)
    return result["detected"], result
