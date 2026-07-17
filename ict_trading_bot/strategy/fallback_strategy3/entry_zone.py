"""
FALLBACK STRATEGY 3 - Entry Zone Calculation
=============================================
Calculates Fibonacci retracement entry zones after confirmed CHOCH.
Also identifies confluence with FVG, order blocks, and SMA levels.
"""

from typing import List, Optional, Tuple

from .indicators import atr, candle_range, candle_direction
from .models import EntryZoneResult
from . import config


def _to_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def calculate_entry_zone(
    candles: List[dict],
    direction: str,                         # "buy" or "sell"
    choch_candle_index: int,               # Index of the CHOCH confirmation candle
    displacement_level: Optional[float],    # Level of displacement start
    entry_method: str = None,
) -> EntryZoneResult:
    """
    Calculate Fibonacci retracement entry zone after confirmed CHOCH.
    
    For buy: looks for retracement INTO discount zone (38.2-50%) of the impulse leg.
    For sell: looks for retracement INTO premium zone (50-61.8%).
    
    Returns EntryZoneResult.
    """
    result = EntryZoneResult()
    result.direction = direction

    entry_method = entry_method or config.ENTRY_METHOD

    if not candles or len(candles) < 5 or choch_candle_index < 0:
        return result

    avg_rng = atr(candles, period=14)
    if avg_rng <= 0:
        avg_rng = sum(candle_range(c) for c in candles[-10:]) / 10.0

    # Find the impulse leg: the move from sweep to CHOCH
    if direction == "buy":
        impulse_result = _find_bullish_impulse(candles, choch_candle_index)
    else:
        impulse_result = _find_bearish_impulse(candles, choch_candle_index)

    if not impulse_result:
        return result

    impulse_low, impulse_high = impulse_result

    if impulse_high <= impulse_low:
        return result

    distance = impulse_high - impulse_low

    # Calculate Fibonacci levels
    fib_zones = []
    for level_pct in config.FIB_LEVELS:
        if level_pct <= 0 or level_pct >= 1.0:
            continue
        if direction == "buy":
            fib_price = impulse_high - (distance * level_pct)
            # For buys, we want retracement down (discount)
            fib_low = fib_price - avg_rng * 0.1
            fib_high = fib_price + avg_rng * 0.1
        else:
            fib_price = impulse_low + (distance * level_pct)
            # For sells, retracement up (premium)
            fib_low = fib_price - avg_rng * 0.1
            fib_high = fib_price + avg_rng * 0.1
        fib_zones.append({
            "level": level_pct,
            "price": fib_price,
            "low": fib_low,
            "high": fib_high,
        })

    # Check current price position
    current_price = _to_float(candles[-1].get("close"))
    result.price_in_zone = False

    for fz in fib_zones:
        if fz["low"] <= current_price <= fz["high"]:
            result.found = True
            result.fib_level = fz["level"]
            result.zone_low = fz["low"]
            result.zone_high = fz["high"]
            result.midpoint = fz["price"]
            result.price_in_zone = True
            break

    if not result.found:
        # Check if price is near any zone (within 1 ATR)
        for fz in fib_zones:
            nearest_zone_price = fz["price"]
            distance_to_zone = abs(current_price - nearest_zone_price)
            if distance_to_zone <= avg_rng * 1.0:
                result.found = True
                result.fib_level = fz["level"]
                result.zone_low = min(fz["low"], current_price)
                result.zone_high = max(fz["high"], current_price)
                result.midpoint = nearest_zone_price
                break

    # Calculate retracement ratio
    if distance > 0:
        if direction == "buy":
            retraced = impulse_high - current_price
        else:
            retraced = current_price - impulse_low
        result.retracement_ratio = max(0.0, min(1.0, retraced / distance))

    # Check confluence
    confluence = _check_confluence(candles, direction, result, avg_rng)
    result.confluence_types = confluence
    result.quality_score = _quality_score(result, confluence, entry_method)

    return result


def _find_bullish_impulse(candles: List[dict], choch_index: int) -> Optional[Tuple[float, float]]:
    """Find the impulse leg low and high for a bullish setup."""
    start = max(0, choch_index - config.SWEEP_LOOKBACK_CANDLES)
    segment = candles[start:choch_index + 1]
    if not segment:
        return None

    # The impulse low is the lowest point in the segment
    impulse_low = min(_to_float(c.get("low")) for c in segment)
    # The impulse high is the CHOCH break level (the close of the CHOCH candle or the swing high)
    impulse_high = _to_float(candles[choch_index].get("close"))

    # Better: the impulse high should be the high of the CHOCH candle
    impulse_high = max(impulse_high, _to_float(candles[choch_index].get("high")))

    return impulse_low, impulse_high


def _find_bearish_impulse(candles: List[dict], choch_index: int) -> Optional[Tuple[float, float]]:
    """Find the impulse leg low and high for a bearish setup."""
    start = max(0, choch_index - config.SWEEP_LOOKBACK_CANDLES)
    segment = candles[start:choch_index + 1]
    if not segment:
        return None

    impulse_high = max(_to_float(c.get("high")) for c in segment)
    impulse_low = _to_float(candles[choch_index].get("close"))
    impulse_low = min(impulse_low, _to_float(candles[choch_index].get("low")))

    return impulse_low, impulse_high


def _check_confluence(
    candles: List[dict],
    direction: str,
    entry_zone: EntryZoneResult,
    avg_rng: float,
) -> List[str]:
    """Check for additional confluence factors near the entry zone."""
    confluence = []

    if not entry_zone.found:
        return confluence

    midpoint = entry_zone.midpoint
    current_price = _to_float(candles[-1].get("close"))

    # FVG confluence: check if there's a fair value gap near the zone
    if len(candles) >= 5:
        for i in range(len(candles) - 5, len(candles)):
            if i < 2 or i >= len(candles):
                continue
            first = candles[i - 2]
            middle = candles[i - 1]
            third = candles[i]
            first_high = _to_float(first.get("high"))
            third_low = _to_float(third.get("low"))
            first_low = _to_float(first.get("low"))
            third_high = _to_float(third.get("high"))

            # Bullish FVG: gap up
            if first_high < third_low:
                fvg_low = first_high
                fvg_high = third_low
                if fvg_low <= midpoint <= fvg_high or abs(midpoint - fvg_low) <= avg_rng * 0.5:
                    confluence.append("fvg")
                    break

            # Bearish FVG: gap down
            if first_low > third_high:
                fvg_low = third_high
                fvg_high = first_low
                if fvg_low <= midpoint <= fvg_high or abs(midpoint - fvg_low) <= avg_rng * 0.5:
                    confluence.append("fvg")
                    break

    # Order block confluence
    if len(candles) >= 3:
        for i in range(len(candles) - 10, len(candles)):
            if i < 1:
                continue
            prev = candles[i - 1]
            cur = candles[i]
            prev_dir = candle_direction(prev)
            cur_dir = candle_direction(cur)

            # Bullish order block: last bearish candle before bullish move
            if direction == "buy" and prev_dir == "bearish" and cur_dir == "bullish":
                ob_low = _to_float(prev.get("low"))
                ob_high = _to_float(prev.get("high"))
                if ob_low <= midpoint <= ob_high or abs(midpoint - ob_low) <= avg_rng * 0.5:
                    confluence.append("order_block")
                    break

            # Bearish order block: last bullish candle before bearish move
            if direction == "sell" and prev_dir == "bullish" and cur_dir == "bearish":
                ob_low = _to_float(prev.get("low"))
                ob_high = _to_float(prev.get("high"))
                if ob_low <= midpoint <= ob_high or abs(midpoint - ob_high) <= avg_rng * 0.5:
                    confluence.append("order_block")
                    break

    # CHOCH level confluence
    confluence.append("choch_level")

    return confluence


def _quality_score(result: EntryZoneResult, confluence: List[str], entry_method: str) -> float:
    """Score the entry zone quality from 0 to 1."""
    if not result.found:
        return 0.0

    score = 0.5  # Base score for having a zone
    score += len(confluence) * 0.1  # +0.1 per confluence factor

    # Preferred retracement levels
    if result.fib_level:
        if 0.382 <= result.fib_level <= 0.618:
            score += 0.1
        if 0.45 <= result.fib_level <= 0.55:
            score += 0.1
        # OTE range (70-79%)
        if 0.70 <= result.fib_level <= 0.80:
            score += 0.15

    # Price in zone is best
    if result.price_in_zone:
        score += 0.1

    # Score entry method suitability
    if entry_method == "limit" and result.price_in_zone:
        score += 0.1  # Limit orders work well when already in zone
    if entry_method == "confirmation" and result.retracement_ratio > 0.3:
        score += 0.05  # Confirmation entry needs some retracement

    return min(1.0, score)
