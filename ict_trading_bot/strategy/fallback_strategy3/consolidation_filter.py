"""
FALLBACK STRATEGY 3 - Consolidation Filter
===========================================
Detects sideways/consolidating market conditions where MACD and SMA
crossovers are unreliable. Uses ATR compression, SMA flatness, and
candle overlapping.
"""

from typing import List, Optional

from .indicators import atr, sma_values, candle_range, candle_direction
from .models import ConsolidationResult
from . import config


def _to_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def detect_consolidation(
    candles: List[dict],
    fast_sma_values: Optional[List[float]] = None,
    slow_sma_values: Optional[List[float]] = None,
) -> ConsolidationResult:
    """
    Detect if the market is in consolidation/sideways mode.
    
    Uses multiple criteria:
    - Low ATR relative to historical
    - Tight SMA distance
    - High crossover frequency
    - Repeated overlapping candles
    - No meaningful structure break
    
    Returns ConsolidationResult with confidence.
    """
    result = ConsolidationResult()

    if not candles or len(candles) < 20:
        return result

    # 1. ATR compression
    current_atr = atr(candles, period=14)
    # Compare to longer-term ATR
    if len(candles) >= 50:
        long_atr = atr(candles[:50], period=20)
        if long_atr > 0:
            result.atr_ratio = current_atr / long_atr
            if result.atr_ratio < (config.CONSOLIDATION_ATR_PERCENT / 100.0):
                result.reasons.append(f"ATR compression: {result.atr_ratio:.2f}x of long-term")

    # 2. SMA distance
    if fast_sma_values and slow_sma_values and len(fast_sma_values) >= 5 and len(slow_sma_values) >= 5:
        recent_gaps = []
        for i in range(-5, 0):
            if abs(i) <= len(fast_sma_values) and abs(i) <= len(slow_sma_values):
                fv = fast_sma_values[i]
                sv = slow_sma_values[i]
                if fv > 0 and sv > 0:
                    recent_gaps.append(abs(fv - sv))

        if recent_gaps:
            avg_gap = sum(recent_gaps) / len(recent_gaps)
            price = _to_float(candles[-1].get("close"))
            point = _estimate_point_value(price)
            result.sma_distance = avg_gap

            if avg_gap < point * config.CONSOLIDATION_SMA_DISTANCE_PIPS:
                result.reasons.append(f"SMA tight: {avg_gap:.5f}")

    # 3. Crossover frequency
    if fast_sma_values and slow_sma_values and len(fast_sma_values) > 20:
        cross_count = 0
        for i in range(1, min(len(fast_sma_values), 30)):
            if fast_sma_values[-i] == 0.0 or slow_sma_values[-i] == 0.0:
                continue
            if fast_sma_values[-i] is not None and slow_sma_values[-i] is not None:
                if i > 0:
                    prev_f = fast_sma_values[-(i + 1)] if -(i + 1) >= -len(fast_sma_values) else 0
                    prev_s = slow_sma_values[-(i + 1)] if -(i + 1) >= -len(slow_sma_values) else 0
                    if prev_f != 0 and prev_s != 0:
                        if (prev_f <= prev_s and fast_sma_values[-i] > slow_sma_values[-i]) or \
                           (prev_f >= prev_s and fast_sma_values[-i] < slow_sma_values[-i]):
                            cross_count += 1
        result.crossover_frequency = cross_count
        if cross_count >= 3:
            result.reasons.append(f"Frequent SMA crosses: {cross_count} in last 30")

    # 4. Candle overlapping
    if len(candles) >= 10:
        recent = candles[-10:]
        total_range = _to_float(recent[-1].get("close")) - _to_float(recent[0].get("open"))
        avg_candle_range = sum(candle_range(c) for c in recent) / len(recent)
        # If total range is small relative to average candle range → overlapping
        if avg_candle_range > 0 and total_range < avg_candle_range * 3:
            result.reasons.append(f"Overlapping candles: range={total_range:.5f}, avg_candle={avg_candle_range:.5f}")

    # 5. No meaningful structure break
    if len(candles) >= 15:
        recent = candles[-15:]
        highs = [_to_float(c.get("high")) for c in recent]
        lows = [_to_float(c.get("low")) for c in recent]
        range_high = max(highs)
        range_low = min(lows)
        if range_high > range_low:
            # Calculate net directional movement
            open_price = _to_float(recent[0].get("open"))
            close_price = _to_float(recent[-1].get("close"))
            net_move = abs(close_price - open_price)
            total_movement = range_high - range_low
            if total_movement > 0 and net_move / total_movement < 0.2:
                result.reasons.append("No meaningful structure break")

    # Overall confidence
    if len(result.reasons) >= 3:
        result.consolidating = True
        result.confidence = min(1.0, len(result.reasons) * 0.3)
    elif len(result.reasons) >= 2:
        result.consolidating = True
        result.confidence = 0.5
    elif len(result.reasons) >= 1:
        result.consolidating = True
        result.confidence = 0.3
    else:
        result.consolidating = False
        result.confidence = 0.0

    return result


def _estimate_point_value(price: float) -> float:
    if price >= 1000:
        return 0.01
    if price >= 100:
        return 0.01
    if price >= 10:
        return 0.001
    return 0.0001
