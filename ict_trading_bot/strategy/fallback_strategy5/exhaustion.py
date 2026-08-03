"""
FALLBACK STRATEGY 5 — Trend Exhaustion Filter
================================================
Detects when a trend is overextended or exhausted.
Prevents late entries and impulse chasing.
"""

from typing import List, Tuple

from . import config
from .indicators import (
    ema_values, atr, candle_range, candle_direction, candle_body_ratio, _to_float,
)


def check_exhaustion(
    setup_candles: List[dict],
    exec_candles: List[dict],
    direction: str,
    atr_value: float,
) -> Tuple[bool, str]:
    """
    Check if the trend shows signs of exhaustion.
    Returns (exhausted, reason).
    """
    trading_candles = exec_candles if len(exec_candles) >= 20 else setup_candles
    if len(trading_candles) < 15:
        return False, "insufficient_data"

    reasons = []

    # ============================================================
    # 1. Anti-chase filter: price too far from EMA20
    # ============================================================
    if len(trading_candles) >= config.EMA_FAST + 5:
        fast_vals = ema_values(trading_candles, config.EMA_FAST)
        if fast_vals and fast_vals[-1] > 0:
            current_close = _to_float(trading_candles[-1].get("close"))
            distance = abs(current_close - fast_vals[-1]) / (atr_value if atr_value > 0 else 1)
            if distance > config.MAX_DISTANCE_FROM_EMA20_ATR:
                reasons.append(f"price_{distance:.2f}atr_from_ema20")

    # ============================================================
    # 2. Impulse chasing filter: 3 consecutive strong candles
    # ============================================================
    recent = trading_candles[-min(10, len(trading_candles)):]
    impulse_count = 0
    for c in recent[-5:]:
        c_direction = candle_direction(c)
        c_range = candle_range(c)
        c_body_ratio_val = candle_body_ratio(c)

        impulse = (
            (direction == "buy" and c_direction == "bullish" and c_range > atr_value * 0.5 and c_body_ratio_val > 0.4)
            or (direction == "sell" and c_direction == "bearish" and c_range > atr_value * 0.5 and c_body_ratio_val > 0.4)
        )
        if impulse:
            impulse_count += 1
        else:
            impulse_count = 0

        if impulse_count >= 3:
            reasons.append("impulse_chasing:3_strong_candles")
            break

    # ============================================================
    # 3. Exhaustion wick check: recent candles with long wicks
    # ============================================================
    long_wick_count = 0
    for c in recent[-5:]:
        body_ratio = candle_body_ratio(c)
        if body_ratio < 0.2:
            long_wick_count += 1
            if long_wick_count >= 3:
                reasons.append("long_wicks:exhaustion")
                break

    # ============================================================
    # 4. Range compression / low volume
    # ============================================================
    if len(recent) >= 5:
        recent_ranges = [candle_range(c) for c in recent[-5:]]
        avg_range = sum(recent_ranges) / len(recent_ranges)
        if avg_range < atr_value * 0.3:
            reasons.append(f"range_compression:avg_range_{avg_range/atr_value:.2f}atr")

    if reasons:
        return True, ";".join(reasons)
    return False, "no_exhaustion"


def check_minimum_target_room(
    entry_price: float,
    stop_loss: float,
    direction: str,
    setup_candles: List[dict],
    atr_value: float,
) -> Tuple[bool, float]:
    """
    Check if there's enough room for the target.
    Returns (enough_room, max_target_distance).
    """
    if atr_value <= 0:
        return False, 0

    risk_distance = abs(entry_price - stop_loss)
    min_target = risk_distance * config.MIN_RR

    # Check that target room exists in the price action context
    if direction == "buy":
        if setup_candles:
            recent_high = max(
                _to_float(c.get("high")) for c in setup_candles[-min(30, len(setup_candles)):]
            )
            target_room = (recent_high - entry_price) * 2  # assume we can reach at least 2x recent range
        else:
            target_room = atr_value * 2
    else:
        if setup_candles:
            recent_low = min(
                _to_float(c.get("low")) for c in setup_candles[-min(30, len(setup_candles)):]
            )
            target_room = (entry_price - recent_low) * 2
        else:
            target_room = atr_value * 2

    return target_room >= min_target, target_room
