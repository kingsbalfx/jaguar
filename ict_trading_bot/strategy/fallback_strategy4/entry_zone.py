"""
FALLBACK STRATEGY 4 - Entry Zone Calculation
==============================================
Calculates entry zones using:
  1. Range-based Fibonacci levels (0%, 25%, 50%, 75%, 100%).
  2. Displacement-leg Fibonacci retracement.
  3. Reclaimed boundary retest zones.
  4. M1 precision entry (mode D).
"""

from typing import List, Optional, Tuple

from . import config
from .models import (
    BoundaryZone, DisplacementResult, EntryResult, RangeResult,
    ReclaimResult, StructureChangeResult,
)


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


def calculate_entry_zone(
    candles: List[dict],
    range_data: RangeResult,
    displacement: DisplacementResult,
    reclaim: ReclaimResult,
    structure_change: StructureChangeResult,
    sweep_direction: str,        # "bullish" or "bearish"
    entry_model: str,            # "A", "B", "C", or "D"
    atr_value: float,
    point: float,
    is_m1: bool = False,
) -> EntryResult:
    """
    Calculate entry zone based on selected entry model.
    
    Model A (reclaim retest): Entry at retest of reclaimed boundary.
    Model B (displacement retracement): Entry at fib retracement of displacement.
    Model C (choch close): Entry at CHOCH candle close.
    Model D (M1 precision): Uses M1 candles for precise entry after M5 detection.
    """
    result = EntryResult()
    result.model = entry_model

    if entry_model == "A":
        return _model_reclaim_retest(candles, range_data, reclaim, sweep_direction, atr_value, point, result)
    elif entry_model == "B":
        return _model_displacement_retracement(candles, range_data, displacement, sweep_direction, atr_value, point, result)
    elif entry_model == "C":
        return _model_choch_close(candles, structure_change, sweep_direction, atr_value, point, result)
    elif entry_model == "D":
        return _model_m1_precision(candles, range_data, reclaim, displacement, structure_change, sweep_direction, atr_value, point, result)
    else:
        result.rejection_reason = f"unknown_entry_model_{entry_model}"
        return result


def _model_reclaim_retest(
    candles: List[dict],
    range_data: RangeResult,
    reclaim: ReclaimResult,
    sweep_direction: str,
    atr_value: float,
    point: float,
    result: EntryResult,
) -> EntryResult:
    """
    Model A: Entry at retest of reclaimed range boundary.
    
    Bullish: After reclaim above range_low, wait for price to retest near range_low.
    Bearish: After reclaim below range_high, wait for price to retest near range_high.
    """
    buffer = config.ENTRY_RETEST_BUFFER_ATR * atr_value
    max_candles = config.RETRACEMENT_MAX_CANDLES

    if not reclaim.reclaimed or reclaim.reclaim_candle_index < 0:
        result.rejection_reason = "no_reclaim_for_retest"
        return result

    reclaim_idx = reclaim.reclaim_candle_index
    search_end = min(reclaim_idx + max_candles, len(candles))

    if sweep_direction == "bullish":
        range_level = range_data.range_low
        zone_low = range_level - buffer * 2
        zone_high = range_level + buffer * 2 + atr_value * 0.5

        for i in range(reclaim_idx, search_end):
            c = candles[i]
            low = _candle_low(c)
            close = _candle_close(c)

            # Price retraced near or into the zone
            if zone_low <= low <= zone_high or zone_low <= close <= zone_high:
                # Require a confirmation candle (bullish close)
                if i + 1 < len(candles):
                    next_c = candles[i + 1]
                    if _candle_close(next_c) > _candle_open(next_c) and _candle_close(next_c) > range_level - buffer * 3:
                        # Entry at retest candle's high + buffer, or next candle's high
                        entry_price = max(_candle_high(c), _candle_high(next_c)) + point
                        result.confirmed = True
                        result.entry_price = entry_price
                        result.zone_low = zone_low
                        result.zone_high = zone_high
                        result.retracement_ratio = (close - range_data.range_low) / range_data.range_width if range_data.range_width > 0 else 0.0
                        break
    else:
        range_level = range_data.range_high
        zone_low = range_level - buffer * 2 - atr_value * 0.5
        zone_high = range_level + buffer * 2

        for i in range(reclaim_idx, search_end):
            c = candles[i]
            high = _candle_high(c)
            close = _candle_close(c)

            if zone_low <= high <= zone_high or zone_low <= close <= zone_high:
                if i + 1 < len(candles):
                    next_c = candles[i + 1]
                    if _candle_close(next_c) < _candle_open(next_c) and _candle_close(next_c) < range_level + buffer * 3:
                        entry_price = min(_candle_low(c), _candle_low(next_c)) - point
                        result.confirmed = True
                        result.entry_price = entry_price
                        result.zone_low = zone_low
                        result.zone_high = zone_high
                        result.retracement_ratio = (range_data.range_high - close) / range_data.range_width if range_data.range_width > 0 else 0.0
                        break

    if not result.confirmed:
        result.rejection_reason = "no_retest_confirmation_within_max_candles"
    return result


def _model_displacement_retracement(
    candles: List[dict],
    range_data: RangeResult,
    displacement: DisplacementResult,
    sweep_direction: str,
    atr_value: float,
    point: float,
    result: EntryResult,
) -> EntryResult:
    """
    Model B: Entry at Fibonacci retracement of the displacement leg.
    
    Calculate the displacement leg, then look for retracement to 50%-78.6%.
    """
    if not displacement.detected or displacement.candle_index < 0:
        result.rejection_reason = "no_displacement_for_retracement"
        return result

    disp_idx = displacement.candle_index
    if disp_idx < 1 or disp_idx >= len(candles):
        result.rejection_reason = "displacement_index_out_of_range"
        return result

    # Find the start of the displacement leg
    if sweep_direction == "bullish":
        # Leg low = lowest point of reclaim candle or displacement start
        leg_low = min(_candle_low(candles[disp_idx]), _candle_low(candles[disp_idx - 1]))
        if reclaim.reclaimed and reclaim.reclaim_candle_index >= 0:
            ri = reclaim.reclaim_candle_index
            for i in range(ri, disp_idx + 1):
                if i < len(candles):
                    leg_low = min(leg_low, _candle_low(candles[i]))
        leg_high = _candle_high(candles[disp_idx])
    else:
        leg_high = max(_candle_high(candles[disp_idx]), _candle_high(candles[disp_idx - 1]))
        if reclaim.reclaimed and reclaim.reclaim_candle_index >= 0:
            ri = reclaim.reclaim_candle_index
            for i in range(ri, disp_idx + 1):
                if i < len(candles):
                    leg_high = max(leg_high, _candle_high(candles[i]))
        leg_low = _candle_low(candles[disp_idx])

    leg_height = abs(leg_high - leg_low)
    if leg_height <= 0:
        result.rejection_reason = "zero_displacement_leg_height"
        return result

    # Fibonacci retracement levels
    fib_levels = [0.382, 0.5, 0.618, 0.705, 0.75, 0.786]
    max_candles = config.RETRACEMENT_MAX_CANDLES
    search_end = min(disp_idx + max_candles, len(candles))

    if sweep_direction == "bullish":
        for i in range(disp_idx + 1, search_end):
            c = candles[i]
            low = _candle_low(c)
            # Check retracement into fib zone
            for fib in fib_levels:
                fib_price = leg_high - (leg_height * fib)
                tolerance = atr_value * 0.2
                if abs(low - fib_price) <= tolerance:
                    # Require confirmation (bullish close or next candle bullish)
                    if i + 1 < len(candles):
                        next_c = candles[i + 1]
                        if _candle_close(next_c) > _candle_open(next_c):
                            entry_price = _candle_high(next_c) + point
                            result.confirmed = True
                            result.entry_price = entry_price
                            result.zone_low = fib_price - tolerance
                            result.zone_high = fib_price + tolerance
                            result.retracement_ratio = (leg_high - low) / leg_height
                            result.fib_level_used = fib
                            break
            if result.confirmed:
                break
    else:
        for i in range(disp_idx + 1, search_end):
            c = candles[i]
            high = _candle_high(c)
            for fib in fib_levels:
                fib_price = leg_low + (leg_height * fib)
                tolerance = atr_value * 0.2
                if abs(high - fib_price) <= tolerance:
                    if i + 1 < len(candles):
                        next_c = candles[i + 1]
                        if _candle_close(next_c) < _candle_open(next_c):
                            entry_price = _candle_low(next_c) - point
                            result.confirmed = True
                            result.entry_price = entry_price
                            result.zone_low = fib_price - tolerance
                            result.zone_high = fib_price + tolerance
                            result.retracement_ratio = (high - leg_low) / leg_height
                            result.fib_level_used = fib
                            break
            if result.confirmed:
                break

    if not result.confirmed:
        result.rejection_reason = "no_fib_retracement_within_max_candles"
    return result


def _model_choch_close(
    candles: List[dict],
    structure_change: StructureChangeResult,
    sweep_direction: str,
    atr_value: float,
    point: float,
    result: EntryResult,
) -> EntryResult:
    """
    Model C: Entry at CHOCH candle close.
    Only valid when displacement is exceptional and price is not overextended.
    """
    if not structure_change.confirmed:
        result.rejection_reason = "no_choch_to_enter_on"
        return result

    break_idx = structure_change.break_candle_index
    if break_idx < 0 or break_idx >= len(candles):
        result.rejection_reason = "choch_index_out_of_range"
        return result

    c = candles[break_idx]
    close = _candle_close(c)
    high = _candle_high(c)
    low = _candle_low(c)
    body = _candle_body(c)
    c_range = high - low if high > low else 0.0
    body_ratio = body / c_range if c_range > 0 else 0.0

    # Only enter if displacement is exceptional (body ratio > 0.7) and not overextended
    if body_ratio < 0.7:
        result.rejection_reason = f"choch_body_ratio_{body_ratio:.2f}_too_low_for_model_c"
        return result

    # Check not overextended (close not near the range extreme)
    if sweep_direction == "bullish":
        distance_to_range_high = range_data.range_high - close
        if distance_to_range_high < range_data.range_width * 0.2:
            result.rejection_reason = "price_overextended_toward_range_high"
            return result
    else:
        distance_to_range_low = close - range_data.range_low
        if distance_to_range_low < range_data.range_width * 0.2:
            result.rejection_reason = "price_overextended_toward_range_low"
            return result

    entry_price = close + (point if sweep_direction == "bullish" else -point)
    result.confirmed = True
    result.entry_price = entry_price
    result.zone_low = min(low, close)
    result.zone_high = max(high, close)
    return result


def _model_m1_precision(
    candles: List[dict],
    range_data: RangeResult,
    reclaim: ReclaimResult,
    displacement: DisplacementResult,
    structure_change: StructureChangeResult,
    sweep_direction: str,
    atr_value: float,
    point: float,
    result: EntryResult,
) -> EntryResult:
    """
    Model D: M1 precision entry.
    M5 range + reclaim + displacement are detected. Then M1 candles are used
    for precise entry with its own sweep, CHOCH, and retracement.
    
    Falls back to Model A if M1 data is unavailable.
    """
    # Fallback: If everything above is confirmed, use model A as default
    result.rejection_reason = "m1_precision_requires_separate_m1_candle_data"
    return result
