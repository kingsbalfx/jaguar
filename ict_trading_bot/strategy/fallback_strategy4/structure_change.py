"""
FALLBACK STRATEGY 4 - Structure Change Confirmation
=====================================================
Confirms CHOCH (Change of Character) or BOS (Break of Structure)
after sweep, reclaim, and displacement.

Reuses CHOCH logic patterns from Fallback 3 with range-specific context.
"""

from typing import List, Optional

from . import config
from .models import RangeResult, StructureChangeResult, DisplacementResult


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


def confirm_structure_change(
    candles: List[dict],
    range_data: RangeResult,
    displacement: DisplacementResult,
    direction: str,             # "bullish" or "bearish"
    atr_value: float,
    point: float,
) -> StructureChangeResult:
    """
    Confirm structure change after reclaim and displacement.
    
    For bullish (swept below range, now reversing up):
      - CHOCH: Identify swing high before displacement, close above it.
      - BOS: Break of internal swing high.
    
    For bearish (swept above range, now reversing down):
      - CHOCH: Identify swing low before displacement, close below it.
      - BOS: Break of internal swing low.
    """
    result = StructureChangeResult()
    result.direction = direction

    method = config.STRUCTURE_METHOD
    min_close_atr = config.MIN_CHOCH_CLOSE_ATR
    min_body_ratio = config.MIN_CHOCH_BODY_RATIO

    if displacement.detected and displacement.candle_index >= 0:
        displacement_idx = displacement.candle_index

        if method in ("choch", "either"):
            choch_result = _detect_choch(
                candles, displacement_idx, direction, range_data,
                atr_value, point, min_close_atr, min_body_ratio,
            )
            if choch_result["confirmed"]:
                result.confirmed = True
                result.method = "choch"
                result.swing_level = choch_result["swing_level"]
                result.close_level = choch_result["close_level"]
                result.break_candle_index = choch_result["break_index"]
                result.body_ratio = choch_result["body_ratio"]
                result.close_distance_atr = choch_result["close_distance_atr"]
                result.invalidated = choch_result["invalidated"]
                return result

        if method in ("bos", "either"):
            bos_result = _detect_bos(
                candles, displacement_idx, direction, range_data,
                atr_value, point,
            )
            if bos_result["confirmed"]:
                result.confirmed = True
                result.method = "bos"
                result.swing_level = bos_result["swing_level"]
                result.close_level = bos_result["close_level"]
                result.break_candle_index = bos_result["break_index"]
                result.body_ratio = bos_result["body_ratio"]
                result.close_distance_atr = bos_result["close_distance_atr"]
                return result

        if method == "either":
            result.rejection_reason = "neither_choch_nor_bos_confirmed"
        else:
            result.rejection_reason = f"{method}_not_confirmed"
    else:
        result.rejection_reason = "no_displacement_to_confirm_structure"

    return result


def _detect_choch(
    candles: List[dict],
    displacement_idx: int,
    direction: str,
    range_data: RangeResult,
    atr_value: float,
    point: float,
    min_close_atr: float,
    min_body_ratio: float,
) -> dict:
    """
    Detect Change of Character (CHOCH).
    
    For bullish: Identify a swing high before displacement, then a close above it.
    For bearish: Identify a swing low before displacement, then a close below it.
    """
    result = {
        "confirmed": False,
        "swing_level": 0.0,
        "close_level": 0.0,
        "break_index": -1,
        "body_ratio": 0.0,
        "close_distance_atr": 0.0,
        "invalidated": False,
    }

    if displacement_idx < 3:
        return result

    # Find the most relevant swing point before displacement
    search_start = max(0, displacement_idx - 15)
    swing_level = None

    if direction == "bullish":
        # Find last meaningful swing high before displacement
        for i in range(displacement_idx - 1, search_start, -1):
            if i + 1 < len(candles) and i - 1 >= 0:
                high = _candle_high(candles[i])
                prev_high = _candle_high(candles[i - 1])
                next_high = _candle_high(candles[i + 1])
                if high > prev_high and high >= next_high:
                    swing_level = high
                    break
    else:
        # Find last meaningful swing low before displacement
        for i in range(displacement_idx - 1, search_start, -1):
            if i + 1 < len(candles) and i - 1 >= 0:
                low = _candle_low(candles[i])
                prev_low = _candle_low(candles[i - 1])
                next_low = _candle_low(candles[i + 1])
                if low < prev_low and low <= next_low:
                    swing_level = low
                    break

    if swing_level is None:
        return result

    # Look for a candle that closes beyond the swing level
    buffer = max(point * config.CHOCH_BUFFER_PIPS, atr_value * 0.05)
    for i in range(displacement_idx, min(displacement_idx + 5, len(candles))):
        c = candles[i]
        close = _candle_close(c)
        body = _candle_body(c)
        c_range = _candle_range(c)
        body_ratio = body / c_range if c_range > 0 else 0.0

        if direction == "bullish":
            break_above = close > swing_level + buffer
            if not break_above:
                continue
            close_distance = close - swing_level
        else:
            break_below = close < swing_level - buffer
            if not break_below:
                continue
            close_distance = swing_level - close

        close_distance_atr = close_distance / atr_value if atr_value > 0 else 0.0

        if close_distance_atr < min_close_atr:
            continue
        if body_ratio < min_body_ratio:
            continue

        # Check not immediately invalidated
        invalidated = False
        if i + 1 < len(candles):
            next_close = _candle_close(candles[i + 1])
            if direction == "bullish" and next_close < swing_level:
                invalidated = True
            elif direction == "bearish" and next_close > swing_level:
                invalidated = True

        result["confirmed"] = True
        result["swing_level"] = swing_level
        result["close_level"] = close
        result["break_index"] = i
        result["body_ratio"] = body_ratio
        result["close_distance_atr"] = close_distance_atr
        result["invalidated"] = invalidated
        break

    return result


def _detect_bos(
    candles: List[dict],
    displacement_idx: int,
    direction: str,
    range_data: RangeResult,
    atr_value: float,
    point: float,
) -> dict:
    """
    Detect Break of Structure (BOS).
    
    For bullish: Break of an internal swing high.
    For bearish: Break of an internal swing low.
    """
    result = {
        "confirmed": False,
        "swing_level": 0.0,
        "close_level": 0.0,
        "break_index": -1,
        "body_ratio": 0.0,
        "close_distance_atr": 0.0,
    }

    if displacement_idx < 2:
        return result

    # Identify the last swing high/low within the range before displacement
    range_low = range_data.range_low
    range_high = range_data.range_high
    search_start = range_data.start_index

    best_swing = None
    best_swing_idx = -1

    if direction == "bullish":
        for i in range(displacement_idx - 1, search_start, -1):
            if i + 1 < len(candles) and i - 1 >= 0:
                high = _candle_high(candles[i])
                if range_low < high < range_high:
                    if _candle_high(candles[i - 1]) < high and _candle_high(candles[i + 1]) <= high:
                        if best_swing is None or high > best_swing:
                            best_swing = high
                            best_swing_idx = i
    else:
        for i in range(displacement_idx - 1, search_start, -1):
            if i + 1 < len(candles) and i - 1 >= 0:
                low = _candle_low(candles[i])
                if range_low < low < range_high:
                    if _candle_low(candles[i - 1]) > low and _candle_low(candles[i + 1]) >= low:
                        if best_swing is None or low < best_swing:
                            best_swing = low
                            best_swing_idx = i

    if best_swing is None:
        return result

    # Look for break candle
    buffer = max(point * config.CHOCH_BUFFER_PIPS, atr_value * 0.05)
    for i in range(displacement_idx, min(displacement_idx + 5, len(candles))):
        c = candles[i]
        close = _candle_close(c)
        body = _candle_body(c)
        c_range = _candle_range(c)
        body_ratio = body / c_range if c_range > 0 else 0.0

        if direction == "bullish":
            if close > best_swing + buffer:
                result["confirmed"] = True
                result["swing_level"] = best_swing
                result["close_level"] = close
                result["break_index"] = i
                result["body_ratio"] = body_ratio
                result["close_distance_atr"] = (close - best_swing) / atr_value if atr_value > 0 else 0.0
                break
        else:
            if close < best_swing - buffer:
                result["confirmed"] = True
                result["swing_level"] = best_swing
                result["close_level"] = close
                result["break_index"] = i
                result["body_ratio"] = body_ratio
                result["close_distance_atr"] = (best_swing - close) / atr_value if atr_value > 0 else 0.0
                break

    return result
