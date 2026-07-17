"""
FALLBACK STRATEGY 3 - SMA Crossover Confirmation
=================================================
Evaluates SMA crossover to confirm or reject a CHOCH-based setup.
SMA is supporting evidence — it cannot create a trade independently.
"""

from typing import List, Optional, Tuple

from .indicators import sma_values
from .models import SMAResult
from . import config


def _to_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def confirm_sma(
    execution_candles: List[dict],
    choch_candle_index: int,
    choch_direction: Optional[str],     # "bullish" or "bearish"
    fast_period: int = None,
    slow_period: int = None,
) -> SMAResult:
    """
    Evaluate SMA crossover confirmation relative to a confirmed CHOCH.
    
    For bullish CHOCH:
    - Fast SMA crossed above slow SMA within timing window
    - Both SMAs sloping upward (preferred)
    - Price closes above both SMAs
    - Distance between SMAs expanding
    
    For bearish CHOCH: inverse.
    
    Returns SMAResult.
    """
    result = SMAResult()

    if not execution_candles or len(execution_candles) < max(
        fast_period or config.SMA_FAST, slow_period or config.SMA_SLOW
    ) + 2:
        return result

    fast = fast_period if fast_period is not None else config.SMA_FAST
    slow = slow_period if slow_period is not None else config.SMA_SLOW

    fast_values = sma_values(execution_candles, fast)
    slow_values = sma_values(execution_candles, slow)

    if not fast_values or not slow_values:
        return result

    # Current values
    result.fast_sma = fast_values[-1] if fast_values else 0.0
    result.slow_sma = slow_values[-1] if slow_values else 0.0

    # Current price position
    current_close = _to_float(execution_candles[-1].get("close"))
    result.price_above_both = current_close > result.fast_sma and current_close > result.slow_sma
    result.price_below_both = current_close < result.fast_sma and current_close < result.slow_sma
    result.price_trapped = (
        (result.fast_sma < result.slow_sma and result.fast_sma < current_close < result.slow_sma) or
        (result.fast_sma > result.slow_sma and result.slow_sma < current_close < result.fast_sma)
    )

    # SMA slopes using linear regression over last 5 values
    result.fast_slope = _calculate_slope(fast_values, 5)
    result.slow_slope = _calculate_slope(slow_values, 5)

    result.both_sloping_up = result.fast_slope > 0 and result.slow_slope > 0
    result.both_sloping_down = result.fast_slope < 0 and result.slow_slope < 0

    # Flat detection
    point = _estimate_point_value(current_close)
    result.both_flat = (
        abs(result.fast_slope) < point * 2 and
        abs(result.slow_slope) < point * 2
    )

    # Compression detection
    sma_gap = abs(result.fast_sma - result.slow_sma)
    result.compression_detected = sma_gap < point * config.CONSOLIDATION_SMA_DISTANCE_PIPS

    # Find crossover
    cross_index = -1
    cross_direction = None
    for i in range(len(fast_values) - 1, max(1, int(choch_candle_index) - abs(config.SMA_MAX_CANDLES_BEFORE_CHOCH) - 5), -1):
        if i <= 0 or fast_values[i] == 0.0 or slow_values[i] == 0.0:
            continue
        prev_fast = fast_values[i - 1]
        prev_slow = slow_values[i - 1]
        curr_fast = fast_values[i]
        curr_slow = slow_values[i]

        if prev_fast <= prev_slow and curr_fast > curr_slow:
            cross_index = i
            cross_direction = "bullish"
            break
        if prev_fast >= prev_slow and curr_fast < curr_slow:
            cross_index = i
            cross_direction = "bearish"
            break

    if cross_index >= 0:
        result.cross_detected = True
        result.cross_direction = cross_direction
        result.cross_age = len(fast_values) - 1 - cross_index

        # Distance expanding after cross
        if cross_index > 0 and cross_index < len(fast_values) - 2:
            gap_now = abs(fast_values[-1] - slow_values[-1])
            gap_at_cross = abs(fast_values[cross_index] - slow_values[cross_index])
            result.distance_expanding = gap_now > gap_at_cross * 1.05

    # ============================================================
    # Confirmation logic
    # ============================================================
    if choch_direction == "bullish":
        result = _evaluate_bullish(result, cross_direction, cross_index, choch_candle_index)
    elif choch_direction == "bearish":
        result = _evaluate_bearish(result, cross_direction, cross_index, choch_candle_index)

    return result


def _evaluate_bullish(result: SMAResult, cross_direction: Optional[str], cross_index: int, choch_index: int) -> SMAResult:
    """Evaluate SMA confirmation for bullish setup."""
    # Fast SMA must be above slow SMA (or just crossed)
    fast_above_slow = result.fast_sma > result.slow_sma

    if not fast_above_slow and not (cross_direction == "bullish" and abs(result.fast_sma - result.slow_sma) < abs(result.fast_sma) * 0.02):
        result.contradiction = True
        return result

    # Check crossover direction
    valid_cross = cross_direction == "bullish" or (cross_direction is None and fast_above_slow)
    if not valid_cross:
        result.contradiction = True
        return result

    # Timing check
    if cross_index >= 0:
        age_from_choch = abs(cross_index - choch_index)
        if age_from_choch > config.SMA_MAX_CANDLES_BEFORE_CHOCH + config.SMA_MAX_CANDLES_AFTER_CHOCH:
            return result  # Too far
        if cross_index < choch_index - config.SMA_MAX_CANDLES_BEFORE_CHOCH:
            return result  # Stale
        if cross_index > choch_index + config.SMA_MAX_CANDLES_AFTER_CHOCH:
            return result  # Too late

    # Reject if both flat
    if result.both_flat:
        result.contradiction = True
        return result

    # Reject if strongly compressed
    if result.compression_detected and not result.distance_expanding:
        return result  # Not confirmed but not contradicting

    # Reject if price trapped between SMAs
    if result.price_trapped:
        return result

    # Reject if strong bearish SMA slope
    if result.fast_slope < -_estimate_point_value(result.fast_sma) * 3 and result.slow_slope < 0:
        result.contradiction = True
        return result

    result.confirmed = True
    return result


def _evaluate_bearish(result: SMAResult, cross_direction: Optional[str], cross_index: int, choch_index: int) -> SMAResult:
    """Evaluate SMA confirmation for bearish setup."""
    fast_below_slow = result.fast_sma < result.slow_sma

    if not fast_below_slow and not (cross_direction == "bearish" and abs(result.fast_sma - result.slow_sma) < abs(result.fast_sma) * 0.02):
        result.contradiction = True
        return result

    valid_cross = cross_direction == "bearish" or (cross_direction is None and fast_below_slow)
    if not valid_cross:
        result.contradiction = True
        return result

    if cross_index >= 0:
        age_from_choch = abs(cross_index - choch_index)
        if age_from_choch > config.SMA_MAX_CANDLES_BEFORE_CHOCH + config.SMA_MAX_CANDLES_AFTER_CHOCH:
            return result
        if cross_index < choch_index - config.SMA_MAX_CANDLES_BEFORE_CHOCH:
            return result
        if cross_index > choch_index + config.SMA_MAX_CANDLES_AFTER_CHOCH:
            return result

    if result.both_flat:
        result.contradiction = True
        return result

    if result.compression_detected and not result.distance_expanding:
        return result

    if result.price_trapped:
        return result

    if result.fast_slope > _estimate_point_value(result.fast_sma) * 3 and result.slow_slope > 0:
        result.contradiction = True
        return result

    result.confirmed = True
    return result


def _calculate_slope(values: List[float], window: int = 5) -> float:
    """Simple linear slope approximation over last `window` values."""
    if len(values) < window:
        return 0.0
    relevant = values[-window:]
    n = len(relevant)
    x_mean = (n - 1) / 2.0
    y_mean = sum(relevant) / n
    numerator = sum((i - x_mean) * (relevant[i] - y_mean) for i in range(n))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    return numerator / denominator if denominator != 0 else 0.0


def _estimate_point_value(price: float) -> float:
    if price >= 1000:
        return 0.01
    if price >= 100:
        return 0.01
    if price >= 10:
        return 0.001
    return 0.0001
