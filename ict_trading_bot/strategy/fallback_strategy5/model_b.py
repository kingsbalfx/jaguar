"""
FALLBACK STRATEGY 5 — Model B: Micro Consolidation Breakout and Retest
=======================================================================
Bullish:
1. Confirmed bullish intraday trend.
2. Price pauses in a compact M1 or M5 consolidation.
3. Consolidation does not break protected bullish structure.
4. Consolidation width and duration pass minimum rules.
5. Price closes above the consolidation high with displacement.
6. Breakout is not excessively extended.
7. Price retests the breakout boundary or a nearby FVG.
8. Boundary holds.
9. Bullish continuation candle closes.
10. Enter buy.

Bearish is inverse.
"""

from typing import List, Optional, Tuple

from . import config
from .indicators import (
    atr, candle_body_ratio, candle_range, candle_direction, candle_body,
    _to_float,
)
from .trend import get_protected_levels, BULLISH, BEARISH
from .logging import log_setup_scan


def evaluate_model_b(
    symbol: str,
    direction: str,
    trend_direction: str,
    setup_candles: List[dict],
    exec_candles: List[dict],
    atr_value: float,
) -> Tuple[bool, dict]:
    """
    Evaluate Model B: Micro Consolidation Breakout and Retest.
    
    Returns:
        (passed, result_dict)
    """
    result = {
        "model": "B",
        "detected": False,
        "consolidation_detected": False,
        "consolidation_high": None,
        "consolidation_low": None,
        "consolidation_width": 0.0,
        "consolidation_width_atr": 0.0,
        "consolidation_duration": 0,
        "breakout_detected": False,
        "breakout_displacement": 0.0,
        "breakout_extended": False,
        "retest_confirmed": False,
        "continuation_confirmed": False,
        "entry_price": None,
        "stop_loss": None,
        "score": 0,
        "rejection_reason": "",
    }

    if direction == "buy" and trend_direction != BULLISH:
        result["rejection_reason"] = "trend_not_bullish"
        return False, result
    if direction == "sell" and trend_direction != BEARISH:
        result["rejection_reason"] = "trend_not_bearish"
        return False, result

    trading_candles = exec_candles if len(exec_candles) >= 20 else setup_candles
    if len(trading_candles) < 20:
        result["rejection_reason"] = f"insufficient_candles:{len(trading_candles)}<20"
        return False, result

    # ============================================================
    # 1. Detect consolidation (range-bound price action)
    # ============================================================
    lookback = min(25, len(trading_candles) - 5)
    recent = trading_candles[-lookback:]

    # Find the most recent consolidation: look for compact range
    best_range = None
    best_start = None
    best_duration = 0

    for start_idx in range(0, len(recent) - 5):
        for end_idx in range(start_idx + 5, min(start_idx + 20, len(recent))):
            window = recent[start_idx:end_idx]
            window_high = max(_to_float(c.get("high")) for c in window)
            window_low = min(_to_float(c.get("low")) for c in window)
            window_width = window_high - window_low
            window_width_atr = window_width / atr_value if atr_value > 0 else 999

            # Ideal consolidation: 0.2 to 0.5 ATR width
            if 0.15 <= window_width_atr <= 0.8:
                duration = len(window)
                if duration > best_duration:
                    best_range = (window_low, window_high)
                    best_start = start_idx
                    best_duration = duration
                    result["consolidation_width"] = window_width
                    result["consolidation_width_atr"] = round(window_width_atr, 2)

    if best_range is None or best_duration < 5:
        result["rejection_reason"] = f"no_consolidation_found:best_duration={best_duration or 0}"
        return False, result

    result["consolidation_high"] = best_range[1]
    result["consolidation_low"] = best_range[0]
    result["consolidation_duration"] = best_duration
    result["consolidation_detected"] = True

    # ============================================================
    # 2. Check breakout
    # ============================================================
    # Look for a candle that closes outside the consolidation
    post_consol = recent[best_start + best_duration:]
    if not post_consol:
        result["rejection_reason"] = "no_candles_after_consolidation"
        return False, result

    breakout_candle = None
    breakout_idx = None
    for i, c in enumerate(post_consol):
        close = _to_float(c.get("close"))
        high = _to_float(c.get("high"))
        low = _to_float(c.get("low"))
        c_dir = candle_direction(c)

        if direction == "buy":
            # Bullish breakout: close above consolidation high
            if close > best_range[1] and c_dir == "bullish":
                # Check not a wick-only break
                body_low = min(_to_float(c.get("close")), _to_float(c.get("open")))
                if body_low > best_range[1]:
                    breakout_candle = c
                    breakout_idx = i
                    break
        else:
            # Bearish breakout: close below consolidation low
            if close < best_range[0] and c_dir == "bearish":
                body_high = max(_to_float(c.get("close")), _to_float(c.get("open")))
                if body_high < best_range[0]:
                    breakout_candle = c
                    breakout_idx = i
                    break

    if breakout_candle is None:
        result["rejection_reason"] = "no_breakout_candle"
        return False, result

    result["breakout_detected"] = True

    # Check displacement
    breakout_range = candle_range(breakout_candle)
    breakout_body = candle_body(breakout_candle)
    result["breakout_displacement"] = breakout_range / atr_value if atr_value > 0 else 0

    if breakout_body < candle_range(breakout_candle) * 0.5:
        result["rejection_reason"] = "breakout_body_too_small"
        return False, result

    # Check not overly extended
    if result["breakout_displacement"] > 2.0:
        result["breakout_extended"] = True
        result["rejection_reason"] = "breakout_overextended"
        return False, result

    # ============================================================
    # 3. Check retest
    # ============================================================
    post_breakout = post_consol[breakout_idx + 1:]
    if not post_breakout:
        result["rejection_reason"] = "no_candles_after_breakout_for_retest"
        return False, result

    retest_confirmed = False
    for c in post_breakout[:min(5, len(post_breakout))]:
        if direction == "buy":
            low = _to_float(c.get("low"))
            close = _to_float(c.get("close"))
            c_dir = candle_direction(c)
            # Retest of breakout boundary (consolidation high)
            # Boundary holds if low touches/breaks briefly but close is back above
            if abs(low - best_range[1]) / (atr_value if atr_value > 0 else 1) < 0.5 and close > best_range[1]:
                retest_confirmed = True
                # Check continuation
                if c_dir == "bullish" and candle_body_ratio(c) >= config.CONFIRMATION_MIN_BODY_RATIO:
                    result["continuation_confirmed"] = True
                break
        else:
            high = _to_float(c.get("high"))
            close = _to_float(c.get("close"))
            c_dir = candle_direction(c)
            if abs(high - best_range[0]) / (atr_value if atr_value > 0 else 1) < 0.5 and close < best_range[0]:
                retest_confirmed = True
                if c_dir == "bearish" and candle_body_ratio(c) >= config.CONFIRMATION_MIN_BODY_RATIO:
                    result["continuation_confirmed"] = True
                break

    result["retest_confirmed"] = retest_confirmed
    if not retest_confirmed:
        result["rejection_reason"] = "retest_not_confirmed"
        return False, result

    result["entry_price"] = _to_float(post_breakout[min(len(post_breakout) - 1, 0)].get("close"))

    # ============================================================
    # 4. Score
    # ============================================================
    score = 0
    if result["consolidation_detected"]:
        score += 15
    if result["breakout_detected"]:
        score += 15
    if not result["breakout_extended"]:
        score += 5
    if retest_confirmed:
        score += 15
    if result["continuation_confirmed"]:
        score += 15
    if result["consolidation_duration"] >= 10:
        score += 5
    if 0.2 <= result["consolidation_width_atr"] <= 0.5:
        score += 10

    result["score"] = score
    result["detected"] = score >= 50

    if not result["detected"]:
        result["rejection_reason"] = f"score_{score}_below_50"

    log_setup_scan(symbol, "B", result["detected"], result.get("rejection_reason", ""), score)
    return result["detected"], result
