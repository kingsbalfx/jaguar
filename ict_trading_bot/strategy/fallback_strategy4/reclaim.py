"""
FALLBACK STRATEGY 4 - Range Reclaim
=====================================
Confirms that price has reclaimed the swept range boundary with a closed candle.
Supports strict, balanced, and aggressive reclaim modes.
"""

from typing import List, Optional

from . import config
from .models import RangeResult, ReclaimResult


def _to_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _candle_high(c: dict) -> float:
    return _to_float(c.get("high"))


def _candle_low(c: dict) -> float:
    return _to_float(c.get("low"))


def _candle_close(c: dict) -> float:
    return _to_float(c.get("close"))


def _candle_open(c: dict) -> float:
    return _to_float(c.get("open"))


def _candle_body(c: dict) -> float:
    return abs(_candle_close(c) - _candle_open(c))


def _candle_range(c: dict) -> float:
    return max(0.0, _candle_high(c) - _candle_low(c))


def _candle_direction(c: dict) -> Optional[str]:
    close = _candle_close(c)
    open_p = _candle_open(c)
    if close > open_p:
        return "bullish"
    if close < open_p:
        return "bearish"
    return None


def confirm_reclaim(
    candles: List[dict],
    range_data: RangeResult,
    sweep_side: str,          # "sell_side" (swept below) or "buy_side" (swept above)
    sweep_direction: str,     # "bullish" or "bearish"
    atr_value: float,
) -> ReclaimResult:
    """
    Confirm that price has reclaimed the swept boundary.
    
    For sell_side sweep (bullish setup):
      - Price swept below range_low.
      - Reclaim = candle close >= range_low (or range_low + buffer).
    
    For buy_side sweep (bearish setup):
      - Price swept above range_high.
      - Reclaim = candle close <= range_high (or range_high - buffer).
    """
    result = ReclaimResult()
    result.side = sweep_side

    if sweep_side == "sell_side":
        return _check_bullish_reclaim(candles, range_data, atr_value, result, sweep_direction)
    elif sweep_side == "buy_side":
        return _check_bearish_reclaim(candles, range_data, atr_value, result, sweep_direction)

    result.failure_reason = "unknown_sweep_side"
    return result


def _check_bullish_reclaim(
    candles: List[dict],
    range_data: RangeResult,
    atr_value: float,
    result: ReclaimResult,
    sweep_direction: str,
) -> ReclaimResult:
    """
    Check bullish range reclaim: price swept below range_low, now closes back above it.
    """
    range_low = range_data.range_low
    range_high = range_data.range_high
    buffer = config.RECLAIM_BUFFER_ATR * atr_value

    mode = config.RECLAIM_MODE
    max_candles = config.RECLAIM_MAX_CANDLES
    min_body_ratio = config.RECLAIM_MIN_BODY_RATIO

    # Scan from the end backward to find reclaim candle
    check_limit = min(max_candles, len(candles))
    reclaim_found = False
    reclaim_idx = -1

    for i in range(len(candles) - 1, max(0, len(candles) - check_limit - 1), -1):
        c = candles[i]
        close = _candle_close(c)
        body = _candle_body(c)
        c_range = _candle_range(c)
        body_ratio = body / c_range if c_range > 0 else 0.0

        reclaim_target = range_low + buffer if mode == "strict" else range_low

        if close >= reclaim_target:
            reclaim_found = True
            reclaim_idx = i
            result.reclaim_candle_index = i
            result.reclaim_candle_close = close
            result.reclaim_candle_body_ratio = body_ratio
            result.mode_used = mode

            # Check buffer
            if mode == "strict":
                result.reclaim_buffer_met = close >= range_low + buffer
            else:
                result.reclaim_buffer_met = close >= range_low

            # Check body ratio
            if mode == "strict" and body_ratio < min_body_ratio:
                result.failure_reason = f"reclaim_body_ratio_{body_ratio:.2f}_<_{min_body_ratio}"
                continue

            # Check follow-through (next candle doesn't close back below)
            if config.RECLAIM_FOLLOW_THROUGH and i + 1 < len(candles):
                next_close = _candle_close(candles[i + 1])
                if next_close < range_low:
                    result.failure_reason = "reclaim_invalidated_by_next_candle"
                    continue

            # Aggressive mode: allow wick-based reclaim + immediate displacement
            if mode == "aggressive" and body_ratio < 0.3:
                # Aggressive requires immediate displacement — allow wick
                pass  # Accept with lower body ratio

            reclaim_found = True
            break

    if not reclaim_found:
        result.reclaimed = False
        result.failure_reason = f"no_reclaim_candle_within_{max_candles}_candles"
        return result

    # Calculate reclaim strength
    distance_pct = min(1.0, (result.reclaim_candle_close - range_low) / (range_high - range_low) if (range_high - range_low) > 0 else 1.0)
    strength = 0
    strength += min(40, int(distance_pct * 40))
    strength += min(30, int(result.reclaim_candle_body_ratio * 30))
    if result.reclaim_buffer_met:
        strength += 20
    if reclaim_idx >= len(candles) - 2:  # Recent reclaim
        strength += 10
    result.reclaim_strength = min(100, strength)

    result.reclaimed = True
    result.follow_through_confirmed = config.RECLAIM_FOLLOW_THROUGH

    return result


def _check_bearish_reclaim(
    candles: List[dict],
    range_data: RangeResult,
    atr_value: float,
    result: ReclaimResult,
    sweep_direction: str,
) -> ReclaimResult:
    """
    Check bearish range reclaim: price swept above range_high, now closes back below it.
    """
    range_high = range_data.range_high
    range_low = range_data.range_low
    buffer = config.RECLAIM_BUFFER_ATR * atr_value

    mode = config.RECLAIM_MODE
    max_candles = config.RECLAIM_MAX_CANDLES
    min_body_ratio = config.RECLAIM_MIN_BODY_RATIO

    check_limit = min(max_candles, len(candles))
    reclaim_found = False
    reclaim_idx = -1

    for i in range(len(candles) - 1, max(0, len(candles) - check_limit - 1), -1):
        c = candles[i]
        close = _candle_close(c)
        body = _candle_body(c)
        c_range = _candle_range(c)
        body_ratio = body / c_range if c_range > 0 else 0.0

        reclaim_target = range_high - buffer if mode == "strict" else range_high

        if close <= reclaim_target:
            reclaim_found = True
            reclaim_idx = i
            result.reclaim_candle_index = i
            result.reclaim_candle_close = close
            result.reclaim_candle_body_ratio = body_ratio
            result.mode_used = mode

            if mode == "strict":
                result.reclaim_buffer_met = close <= range_high - buffer
            else:
                result.reclaim_buffer_met = close <= range_high

            if mode == "strict" and body_ratio < min_body_ratio:
                result.failure_reason = f"reclaim_body_ratio_{body_ratio:.2f}_<_{min_body_ratio}"
                continue

            if config.RECLAIM_FOLLOW_THROUGH and i + 1 < len(candles):
                next_close = _candle_close(candles[i + 1])
                if next_close > range_high:
                    result.failure_reason = "reclaim_invalidated_by_next_candle"
                    continue

            reclaim_found = True
            break

    if not reclaim_found:
        result.reclaimed = False
        result.failure_reason = f"no_reclaim_candle_within_{max_candles}_candles"
        return result

    distance_pct = min(1.0, (range_high - result.reclaim_candle_close) / (range_high - range_low) if (range_high - range_low) > 0 else 1.0)
    strength = 0
    strength += min(40, int(distance_pct * 40))
    strength += min(30, int(result.reclaim_candle_body_ratio * 30))
    if result.reclaim_buffer_met:
        strength += 20
    if reclaim_idx >= len(candles) - 2:
        strength += 10
    result.reclaim_strength = min(100, strength)

    result.reclaimed = True
    result.follow_through_confirmed = config.RECLAIM_FOLLOW_THROUGH

    return result
