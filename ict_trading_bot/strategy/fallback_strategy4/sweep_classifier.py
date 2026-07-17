"""
FALLBACK STRATEGY 4 - Sweep vs Breakout Classifier
====================================================
Classifies price movement beyond a range boundary as:
  - Confirmed sweep (failed breakout)
  - Probable sweep
  - Probable genuine breakout
  - Genuine breakout
  - Uncertain

Measures penetration, candle structure, momentum, and price acceptance.
"""

from typing import List, Optional

from . import config
from .models import RangeResult, SweepResult


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


def classify_sweep(
    candles: List[dict],
    range_data: RangeResult,
    atr_value: float,
    point: float,
) -> SweepResult:
    """
    Classify price movement beyond a range boundary.
    
    Analyses candles from the end of the range window toward the present.
    
    Returns:
        SweepResult with classification and measurements.
    """
    result = SweepResult()
    if not range_data.detected:
        return result

    range_high = range_data.range_high
    range_low = range_data.range_low
    range_width = range_data.range_width
    start_idx = range_data.start_index

    # Analyse candles after the range
    post_range_candles = candles[start_idx:]
    if len(post_range_candles) < 2:
        return result

    # Determine which side was swept
    recent_high = max(_candle_high(c) for c in post_range_candles)
    recent_low = min(_candle_low(c) for c in post_range_candles)

    # Check for sweep above range high (bearish setup)
    bearish_setup = recent_high > range_high
    # Check for sweep below range low (bullish setup)
    bullish_setup = recent_low < range_low

    if not bearish_setup and not bullish_setup:
        result.classification = "uncertain"
        result.detected = False
        return result

    # Prefer recent sweep — pick the closest one
    last_idx = len(candles) - 1
    last_candle = candles[last_idx] if last_idx >= 0 else {}

    if bullish_setup and bearish_setup:
        # Both sides swept — pick the most recent or most pronounced
        last_low = _candle_low(last_candle)
        last_high = _candle_high(last_candle)
        if last_low <= range_low and last_high >= range_high:
            # Both in one candle — ambiguous
            result.classification = "uncertain"
            return result
        pen_bear = recent_high - range_high
        pen_bull = range_low - recent_low
        if pen_bull > pen_bear:
            bullish_setup = True
            bearish_setup = False
        else:
            bullish_setup = False
            bearish_setup = True

    if bullish_setup:
        return _classify_bullish_sweep(post_range_candles, candles, range_data, atr_value, point, result)
    else:
        return _classify_bearish_sweep(post_range_candles, candles, range_data, atr_value, point, result)


def _classify_bullish_sweep(
    post_candles: List[dict],
    all_candles: List[dict],
    range_data: RangeResult,
    atr_value: float,
    point: float,
    result: SweepResult,
) -> SweepResult:
    """Classify a sweep below the range low (bullish reversal setup)."""
    range_low = range_data.range_low
    range_width = range_data.range_width

    # Find the lowest price below range
    outside_candles = []
    lowest_price = range_low
    momentum_weakening = False

    for c in post_candles:
        low = _candle_low(c)
        if low < range_low:
            outside_candles.append(c)
            if low < lowest_price:
                lowest_price = low

    if not outside_candles:
        result.detected = False
        result.classification = "uncertain"
        return result

    # Measure penetration
    penetration = range_low - lowest_price
    penetration_atr = penetration / atr_value if atr_value > 0 else 0.0
    penetration_ratio = penetration / range_width if range_width > 0 else 0.0

    result.side = "sell_side"
    result.direction = "bullish"
    result.extreme_price = lowest_price
    result.penetration = penetration
    result.penetration_atr = penetration_atr
    result.penetration_ratio = penetration_ratio
    result.candles_outside = len(outside_candles)

    # Check penetration limits
    if penetration_atr < config.MIN_SWEEP_PENETRATION_ATR:
        result.classification = "uncertain"
        result.detected = False
        return result

    if penetration_atr > config.MAX_SWEEP_PENETRATION_ATR:
        result.classification = "genuine_breakout"
        result.detected = True
        result.failed_outside_acceptance = True
        return result

    # Check candle limit outside
    if len(outside_candles) > config.MAX_CANDLES_OUTSIDE:
        result.classification = "genuine_breakout"
        result.detected = True
        result.failed_outside_acceptance = True
        return result

    # Check momentum — look at last few outside candles
    if len(outside_candles) >= 2:
        recent_outside = outside_candles[-2:]
        if len(recent_outside) >= 2:
            prev_range = _candle_range(recent_outside[0])
            curr_range = _candle_range(recent_outside[1])
            if curr_range < prev_range * 0.7:
                momentum_weakening = True

    result.momentum_decelerated = momentum_weakening
    result.average_body_outside = sum(_candle_body(c) for c in outside_candles) / len(outside_candles)

    # Check price acceptance (genuine breakout detection)
    if _check_acceptance_below(all_candles, range_low, atr_value, penetration_atr):
        result.classification = "genuine_breakout"
        result.failed_outside_acceptance = True
        result.detected = True
        return result

    # Classify the sweep
    if momentum_weakening and _has_return_inside(post_candles, range_low):
        result.classification = "sweep"
        result.sweep_score = _calculate_sweep_confidence(penetration_atr, penetration_ratio, momentum_weakening, True)
        result.breakout_score = 1.0 - result.sweep_score
        result.detected = True
    elif momentum_weakening:
        result.classification = "probable_sweep"
        result.sweep_score = _calculate_sweep_confidence(penetration_atr, penetration_ratio, momentum_weakening, False)
        result.breakout_score = 1.0 - result.sweep_score
        result.detected = True
    elif _has_return_inside(post_candles, range_low):
        result.classification = "probable_breakout"
        result.sweep_score = _calculate_sweep_confidence(penetration_atr, penetration_ratio, False, True)
        result.breakout_score = 1.0 - result.sweep_score
        result.detected = True
    else:
        result.classification = "probable_breakout"
        result.sweep_score = 0.3
        result.breakout_score = 0.7
        result.detected = True

    return result


def _classify_bearish_sweep(
    post_candles: List[dict],
    all_candles: List[dict],
    range_data: RangeResult,
    atr_value: float,
    point: float,
    result: SweepResult,
) -> SweepResult:
    """Classify a sweep above the range high (bearish reversal setup)."""
    range_high = range_data.range_high
    range_width = range_data.range_width

    outside_candles = []
    highest_price = range_high
    momentum_weakening = False

    for c in post_candles:
        high = _candle_high(c)
        if high > range_high:
            outside_candles.append(c)
            if high > highest_price:
                highest_price = high

    if not outside_candles:
        result.detected = False
        result.classification = "uncertain"
        return result

    penetration = highest_price - range_high
    penetration_atr = penetration / atr_value if atr_value > 0 else 0.0
    penetration_ratio = penetration / range_width if range_width > 0 else 0.0

    result.side = "buy_side"
    result.direction = "bearish"
    result.extreme_price = highest_price
    result.penetration = penetration
    result.penetration_atr = penetration_atr
    result.penetration_ratio = penetration_ratio
    result.candles_outside = len(outside_candles)

    if penetration_atr < config.MIN_SWEEP_PENETRATION_ATR:
        result.classification = "uncertain"
        result.detected = False
        return result

    if penetration_atr > config.MAX_SWEEP_PENETRATION_ATR:
        result.classification = "genuine_breakout"
        result.detected = True
        result.failed_outside_acceptance = True
        return result

    if len(outside_candles) > config.MAX_CANDLES_OUTSIDE:
        result.classification = "genuine_breakout"
        result.detected = True
        result.failed_outside_acceptance = True
        return result

    if len(outside_candles) >= 2:
        recent_outside = outside_candles[-2:]
        if len(recent_outside) >= 2:
            prev_range = _candle_range(recent_outside[0])
            curr_range = _candle_range(recent_outside[1])
            if curr_range < prev_range * 0.7:
                momentum_weakening = True

    result.momentum_decelerated = momentum_weakening
    result.average_body_outside = sum(_candle_body(c) for c in outside_candles) / len(outside_candles)

    if _check_acceptance_above(all_candles, range_high, atr_value, penetration_atr):
        result.classification = "genuine_breakout"
        result.failed_outside_acceptance = True
        result.detected = True
        return result

    if momentum_weakening and _has_return_inside_bearish(post_candles, range_high):
        result.classification = "sweep"
        result.sweep_score = _calculate_sweep_confidence(penetration_atr, penetration_ratio, momentum_weakening, True)
        result.breakout_score = 1.0 - result.sweep_score
        result.detected = True
    elif momentum_weakening:
        result.classification = "probable_sweep"
        result.sweep_score = _calculate_sweep_confidence(penetration_atr, penetration_ratio, momentum_weakening, False)
        result.breakout_score = 1.0 - result.sweep_score
        result.detected = True
    elif _has_return_inside_bearish(post_candles, range_high):
        result.classification = "probable_breakout"
        result.sweep_score = _calculate_sweep_confidence(penetration_atr, penetration_ratio, False, True)
        result.breakout_score = 1.0 - result.sweep_score
        result.detected = True
    else:
        result.classification = "probable_breakout"
        result.sweep_score = 0.3
        result.breakout_score = 0.7
        result.detected = True

    return result


def _has_return_inside(candles: List[dict], range_low: float) -> bool:
    """Check if any candle has returned inside/above the range low."""
    return any(_candle_close(c) >= range_low for c in candles)


def _has_return_inside_bearish(candles: List[dict], range_high: float) -> bool:
    """Check if any candle has returned inside/below the range high."""
    return any(_candle_close(c) <= range_high for c in candles)


def _check_acceptance_below(
    candles: List[dict],
    range_low: float,
    atr_value: float,
    penetration_atr: float,
) -> bool:
    """Check if price is accepted below the range (genuine breakout)."""
    # Distance-based acceptance
    if penetration_atr >= config.ACCEPTANCE_DISTANCE_ATR:
        return True

    # Consecutive closes below
    recent_closes_below = 0
    for c in reversed(candles[-config.ACCEPTANCE_CANDLES:]):
        if _candle_close(c) < range_low:
            recent_closes_below += 1
        else:
            break
    if recent_closes_below >= config.ACCEPTANCE_CANDLES:
        return True

    # Average body outside threshold
    bodies_below = [_candle_body(c) for c in candles[-config.ACCEPTANCE_CANDLES * 2:] if _candle_close(c) < range_low]
    if bodies_below:
        avg_body = sum(bodies_below) / len(bodies_below)
        if avg_body >= config.ACCEPTANCE_BODY_RATIO * atr_value:
            return True

    return False


def _check_acceptance_above(
    candles: List[dict],
    range_high: float,
    atr_value: float,
    penetration_atr: float,
) -> bool:
    """Check if price is accepted above the range (genuine breakout)."""
    if penetration_atr >= config.ACCEPTANCE_DISTANCE_ATR:
        return True

    recent_closes_above = 0
    for c in reversed(candles[-config.ACCEPTANCE_CANDLES:]):
        if _candle_close(c) > range_high:
            recent_closes_above += 1
        else:
            break
    if recent_closes_above >= config.ACCEPTANCE_CANDLES:
        return True

    bodies_above = [_candle_body(c) for c in candles[-config.ACCEPTANCE_CANDLES * 2:] if _candle_close(c) > range_high]
    if bodies_above:
        avg_body = sum(bodies_above) / len(bodies_above)
        if avg_body >= config.ACCEPTANCE_BODY_RATIO * atr_value:
            return True

    return False


def _calculate_sweep_confidence(
    penetration_atr: float,
    penetration_ratio: float,
    momentum_weakening: bool,
    returned_inside: bool,
) -> float:
    """Calculate sweep confidence score (0.0 to 1.0)."""
    confidence = 0.0

    # Penalise too-shallow or too-deep penetration
    if 0.3 <= penetration_atr <= 1.5:
        confidence += 0.4
    elif penetration_atr < 0.5:
        confidence += 0.2
    else:
        confidence += 0.3

    # Penalise very high penetration ratio
    if penetration_ratio <= 0.15:
        confidence += 0.2
    elif penetration_ratio <= 0.30:
        confidence += 0.1

    # Momentum weakening
    if momentum_weakening:
        confidence += 0.2

    # Return inside
    if returned_inside:
        confidence += 0.2

    return min(1.0, confidence)
