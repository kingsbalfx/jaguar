"""
FALLBACK STRATEGY 3 - MACD Confirmation
=========================================
Evaluates MACD momentum to confirm or reject a CHOCH-based setup.
MACD is supporting evidence — it cannot create a trade independently.
"""

from typing import List, Optional

from .indicators import macd, macd_series
from .models import MACDResult
from . import config


def confirm_macd(
    execution_candles: List[dict],
    choch_candle_index: int,
    choch_direction: Optional[str],     # "bullish" or "bearish"
    fast_period: int = None,
    slow_period: int = None,
    signal_period: int = None,
) -> MACDResult:
    """
    Evaluate MACD confirmation relative to a confirmed CHOCH.
    
    For bullish CHOCH:
    - MACD line crossed above signal line
    - Histogram moving from negative to positive
    - Crossover within configurable window around CHOCH
    
    For bearish CHOCH: inverse.
    
    Returns MACDResult.
    """
    result = MACDResult()

    if not execution_candles or len(execution_candles) < config.MACD_SLOW + config.MACD_SIGNAL:
        result.data_complete = False
        return result

    fast = fast_period if fast_period is not None else config.MACD_FAST
    slow = slow_period if slow_period is not None else config.MACD_SLOW
    signal = signal_period if signal_period is not None else config.MACD_SIGNAL

    # Get MACD series for analysis
    macd_values, signal_values, histograms = macd_series(execution_candles, fast, slow, signal)
    if not macd_values or not signal_values:
        result.data_complete = False
        return result

    # Current values
    result.macd_line = macd_values[-1] if macd_values else 0.0
    result.signal_line = signal_values[-1] if signal_values else 0.0
    result.histogram = histograms[-1] if histograms else 0.0
    result.histogram_positive = result.histogram > 0
    result.histogram_negative = result.histogram < 0

    # Histogram trend
    if len(histograms) >= 2:
        result.histogram_increasing = histograms[-1] > histograms[-2]
        result.histogram_decreasing = histograms[-1] < histograms[-2]

    # Find the most recent crossover
    cross_index = -1
    cross_direction = None
    for i in range(len(macd_values) - 1, max(int(choch_candle_index) - abs(config.MACD_MAX_CANDLES_BEFORE_CHOCH) - 5, 0), -1):
        if i <= 0:
            break
        prev_macd = macd_values[i - 1]
        prev_sig = signal_values[i - 1]
        curr_macd = macd_values[i]
        curr_sig = signal_values[i]

        # Bullish cross: MACD line crossed above signal
        if prev_macd <= prev_sig and curr_macd > curr_sig:
            cross_index = i
            cross_direction = "bullish"
            break
        # Bearish cross: MACD line crossed below signal
        if prev_macd >= prev_sig and curr_macd < curr_sig:
            cross_index = i
            cross_direction = "bearish"
            break

    if cross_index >= 0:
        result.cross_detected = True
        result.cross_direction = cross_direction
        result.cross_age = len(macd_values) - 1 - cross_index

    # Check zero line cross
    for i in range(len(macd_values) - 1, max(0, len(macd_values) - 5), -1):
        if i <= 0:
            break
        if (macd_values[i - 1] <= 0 and macd_values[i] > 0) or (macd_values[i - 1] >= 0 and macd_values[i] < 0):
            result.zero_cross = True
            break

    # ============================================================
    # Confirmation logic based on CHOCH direction
    # ============================================================
    if choch_direction == "bullish":
        result = _evaluate_bullish(result, cross_direction, cross_index, choch_candle_index)
    elif choch_direction == "bearish":
        result = _evaluate_bearish(result, cross_direction, cross_index, choch_candle_index)

    return result


def _evaluate_bullish(result: MACDResult, cross_direction: Optional[str], cross_index: int, choch_index: int) -> MACDResult:
    """Evaluate MACD confirmation for bullish setup."""
    # Must have: MACD line above signal line (or recent cross)
    macd_above_signal = result.macd_line > result.signal_line

    # Cross must be in the right direction
    valid_cross = cross_direction == "bullish" or (cross_direction is None and macd_above_signal)

    if not macd_above_signal and not (cross_direction == "bullish" and result.histogram_positive):
        result.contradiction = True
        return result

    if not valid_cross:
        result.contradiction = True
        return result

    # Check timing: crossover must be within window of CHOCH
    if cross_index >= 0:
        age_from_choch = abs(cross_index - choch_index)
        if age_from_choch > config.MACD_MAX_CANDLES_BEFORE_CHOCH + config.MACD_MAX_CANDLES_AFTER_CHOCH:
            # Crossover too far from CHOCH
            return result

        # Check if cross was before CHOCH (stale) or after CHOCH (fresh)
        if cross_index < choch_index - config.MACD_MAX_CANDLES_BEFORE_CHOCH:
            # Too stale — cross happened way before CHOCH
            return result
        if cross_index > choch_index + config.MACD_MAX_CANDLES_AFTER_CHOCH:
            # Cross happened too long after CHOCH — price may be extended
            return result

    # Histogram agreement
    histogram_ok = result.histogram >= 0 or result.histogram_increasing
    if not histogram_ok:
        # Histogram descending and negative — weakening bullish momentum
        result.contradiction = True
        return result

    # Harmonic contradiction check: MACD line strongly below signal = strong contradiction
    if result.signal_line > result.macd_line and abs(result.macd_line - result.signal_line) > abs(result.macd_line) * 0.1:
        result.contradiction = True
        return result

    result.confirmed = True
    return result


def _evaluate_bearish(result: MACDResult, cross_direction: Optional[str], cross_index: int, choch_index: int) -> MACDResult:
    """Evaluate MACD confirmation for bearish setup."""
    macd_below_signal = result.macd_line < result.signal_line
    valid_cross = cross_direction == "bearish" or (cross_direction is None and macd_below_signal)

    if not macd_below_signal and not (cross_direction == "bearish" and result.histogram_negative):
        result.contradiction = True
        return result

    if not valid_cross:
        result.contradiction = True
        return result

    # Timing check
    if cross_index >= 0:
        age_from_choch = abs(cross_index - choch_index)
        if age_from_choch > config.MACD_MAX_CANDLES_BEFORE_CHOCH + config.MACD_MAX_CANDLES_AFTER_CHOCH:
            return result
        if cross_index < choch_index - config.MACD_MAX_CANDLES_BEFORE_CHOCH:
            return result
        if cross_index > choch_index + config.MACD_MAX_CANDLES_AFTER_CHOCH:
            return result

    histogram_ok = result.histogram <= 0 or result.histogram_decreasing
    if not histogram_ok:
        result.contradiction = True
        return result

    if result.macd_line > result.signal_line and abs(result.macd_line - result.signal_line) > abs(result.signal_line) * 0.1:
        result.contradiction = True
        return result

    result.confirmed = True
    return result
