"""
FALLBACK STRATEGY 3 - Sweep vs Breakout Classification
=======================================================
Classifies price movement through a liquidity level as:
- Likely liquidity sweep
- Likely genuine breakout
- Uncertain
"""

from typing import List, Optional

from .indicators import candle_direction, candle_range, candle_body_ratio, atr, candle_body
from .models import SweepResult
from . import config


def _to_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def classify_sweep(
    candles: List[dict],
    direction: str,                     # "buy" or "sell" — which direction we want to trade
    liquidity_level: float,
    structure_candles: List[dict],
) -> SweepResult:
    """
    Analyze whether a move through a liquidity level is a sweep or a breakout.
    
    For buy direction: we want sell-side liquidity swept below a level.
    For sell direction: we want buy-side liquidity swept above a level.
    
    Returns SweepResult with classification.
    """
    result = SweepResult(
        sweep_direction=direction,
        sweep_level=liquidity_level,
    )

    if not candles or len(candles) < 5:
        return result

    avg_rng = atr(candles, period=14)
    if avg_rng <= 0:
        avg_rng = 10  # fallback

    target_index = None
    penetration_distance = 0.0
    candles_beyond = 0
    max_beyond_idx = -1

    # Scan candles for interaction with the level
    for i in range(len(candles)):
        candle = candles[i]
        high = _to_float(candle.get("high"))
        low = _to_float(candle.get("low"))

        if direction == "buy":
            # Looking for price going below liquidity_level (sell-side sweep)
            if low < liquidity_level:
                penetration = liquidity_level - low
                if penetration > penetration_distance:
                    penetration_distance = penetration
                    max_beyond_idx = i
                candles_beyond += 1
                if target_index is None:
                    target_index = i
        else:
            # Looking for price going above liquidity_level (buy-side sweep)
            if high > liquidity_level:
                penetration = high - liquidity_level
                if penetration > penetration_distance:
                    penetration_distance = penetration
                    max_beyond_idx = i
                candles_beyond += 1
                if target_index is None:
                    target_index = i

    if target_index is None:
        # No interaction with the liquidity level
        return result

    result.detected = True
    result.penetration_distance = penetration_distance

    # Classify sweep type
    wick_beyond = False
    body_beyond = False
    displacement_type = False

    if direction == "buy":
        wick_beyond = candles[max_beyond_idx] and _to_float(candles[max_beyond_idx].get("low")) < liquidity_level
        body_beyond = candles[max_beyond_idx] and _to_float(candles[max_beyond_idx].get("close")) < liquidity_level
    else:
        wick_beyond = candles[max_beyond_idx] and _to_float(candles[max_beyond_idx].get("high")) > liquidity_level
        body_beyond = candles[max_beyond_idx] and _to_float(candles[max_beyond_idx].get("close")) > liquidity_level

    if body_beyond:
        result.sweep_type = "displacement"  # price fully displaced beyond
    elif wick_beyond:
        result.sweep_type = "wick"
    elif candles_beyond >= 3:
        result.sweep_type = "multi_candle"

    result.candle_count_beyond = candles_beyond

    # Check if price returned inside the prior range
    return_inside = False
    if max_beyond_idx >= 0 and max_beyond_idx < len(candles) - 1:
        subsequent = candles[max_beyond_idx + 1:]
        if direction == "buy":
            return_inside = any(_to_float(c.get("close")) > liquidity_level for c in subsequent)
        else:
            return_inside = any(_to_float(c.get("close")) < liquidity_level for c in subsequent)
    result.return_inside = return_inside

    # Check momentum weakening beyond the level
    beyond_candles = candles[target_index:max_beyond_idx + 1] if max_beyond_idx >= target_index else []
    if len(beyond_candles) >= 2:
        first_after = beyond_candles[-1] if beyond_candles else None
        if first_after:
            body_r = candle_body_ratio(first_after)
            result.momentum_weak_beyond = body_r < 0.35
    else:
        result.momentum_weak_beyond = True  # Only wick = weak

    # ============================================================
    # Classification: Sweep vs Breakout
    # ============================================================
    sweep_score = 0.0  # 0 = breakout, 1 = sweep
    breakout_score = 0.0

    # Criteria for sweep
    if return_inside:
        sweep_score += 0.30  # Major: returned inside
    if candles_beyond <= 2:
        sweep_score += 0.15  # Quick spike
    if result.sweep_type == "wick":
        sweep_score += 0.20  # Wick only
    if result.momentum_weak_beyond:
        sweep_score += 0.10
    if not body_beyond:
        sweep_score += 0.10  # Body didn't fully cross
    if penetration_distance < avg_rng * 0.5:
        sweep_score += 0.15  # Shallow penetration

    # Criteria for breakout
    if candles_beyond >= 4:
        breakout_score += 0.20
    if body_beyond:
        breakout_score += 0.25
    if penetration_distance >= avg_rng * 1.0:
        breakout_score += 0.20
    if not return_inside:
        breakout_score += 0.15
    if result.sweep_type == "displacement":
        breakout_score += 0.20

    # Classification
    if sweep_score > breakout_score and sweep_score >= 0.40:
        result.classification = "sweep"
        result.classification_score = sweep_score
    elif breakout_score > sweep_score and breakout_score >= 0.40:
        result.classification = "breakout"
        result.classification_score = -breakout_score
    else:
        result.classification = "uncertain"
        result.classification_score = sweep_score - breakout_score

    # ============================================================
    # Check for opposing displacement after sweep
    # ============================================================
    if result.classification == "sweep" and max_beyond_idx >= 0 and max_beyond_idx < len(candles) - 1:
        subsequent = candles[max_beyond_idx + 1:]
        if len(subsequent) >= 2:
            # Look for displacement in the opposite/return direction
            if direction == "buy":
                # Bullish displacement: close > open, large body, moves up
                for sc in subsequent[:5]:
                    dir_c = candle_direction(sc)
                    if dir_c == "bullish":
                        body_r = candle_body_ratio(sc)
                        rng = candle_range(sc)
                        if body_r >= 0.50 and rng >= avg_rng * 0.5:
                            result.displacement_detected = True
                            result.displacement_index = max_beyond_idx + 1
                            result.displacement_body_ratio = body_r
                            result.displacement_range_ratio = rng / avg_rng if avg_rng > 0 else 0
                            result.displaced_high = _to_float(sc.get("high"))
                            result.displaced_low = _to_float(sc.get("low"))
                            break
            else:
                for sc in subsequent[:5]:
                    dir_c = candle_direction(sc)
                    if dir_c == "bearish":
                        body_r = candle_body_ratio(sc)
                        rng = candle_range(sc)
                        if body_r >= 0.50 and rng >= avg_rng * 0.5:
                            result.displacement_detected = True
                            result.displacement_index = max_beyond_idx + 1
                            result.displacement_body_ratio = body_r
                            result.displacement_range_ratio = rng / avg_rng if avg_rng > 0 else 0
                            result.displaced_high = _to_float(sc.get("high"))
                            result.displaced_low = _to_float(sc.get("low"))
                            break

    return result
