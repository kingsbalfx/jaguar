"""
FALLBACK STRATEGY 3 - Lower-Timeframe CHOCH Confirmation
=========================================================
Confirms Change of Character (CHOCH) on the execution timeframe.
Only uses closed candles — no repainting, no open-candle confirmation.
"""

from typing import List, Optional, Tuple

from .indicators import find_swing_points, atr, candle_body_ratio, candle_range
from .models import CHOCHResult
from . import config


def _to_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def detect_choch(
    execution_candles: List[dict],
    direction: str,                     # "buy" or "sell" — intended trade direction
    sweep_index: Optional[int],         # Index where sweep was detected
    structure_candles: List[dict],      # For swing detection
) -> CHOCHResult:
    """
    Detect and confirm a lower-timeframe CHOCH after liquidity sweep.
    
    For buy direction:
    1. Price swept sell-side liquidity
    2. Price formed a meaningful internal swing high
    3. Bullish displacement breaks that swing high
    4. Closed candle confirms above swing high
    
    For sell direction:
    (inverse)
    
    Returns CHOCHResult.
    """
    result = CHOCHResult()

    if not execution_candles or len(execution_candles) < 10:
        return result

    avg_rng = atr(execution_candles, period=14)
    if avg_rng <= 0:
        avg_rng = _estimate_range(execution_candles)

    # Find local swing points on execution timeframe
    local_swings = find_swing_points(execution_candles, lookback=2)
    if len(local_swings) < 2:
        return result

    # For buy: find swing lows that were swept, then check for swing high break
    if direction == "buy":
        return _detect_bullish_choch(execution_candles, local_swings, avg_rng, sweep_index)

    # For sell: find swing highs that were swept, then check for swing low break
    return _detect_bearish_choch(execution_candles, local_swings, avg_rng, sweep_index)


def _detect_bullish_choch(
    execution_candles: List[dict],
    local_swings: List[dict],
    avg_rng: float,
    sweep_index: Optional[int],
) -> CHOCHResult:
    """Detect a bullish CHOCH after sell-side liquidity sweep."""
    result = CHOCHResult()
    result.direction = "bullish"

    # Find the most recent swing low that was swept
    swing_lows = [s for s in local_swings if s["type"] == "low"]
    if not swing_lows:
        return result

    # The executed sweep is below the most recent swing low
    last_swing_low = swing_lows[-1]
    swing_low_level = _to_float(last_swing_low["price"])
    low_index = last_swing_low.get("index", 0)

    # Look for swing highs after the swing low
    swing_highs = [s for s in local_swings if s["type"] == "high" and s.get("index", 0) > low_index]
    if not swing_highs:
        return result

    # The nearest (first) swing high after the sweep
    target_swing_high = swing_highs[0]
    sh_index = target_swing_high.get("index", 0)
    sh_level = _to_float(target_swing_high["price"])

    # Check for displacement breaking this swing high
    for i in range(sh_index, min(len(execution_candles), sh_index + 8)):
        candle = execution_candles[i]
        high = _to_float(candle.get("high"))
        close = _to_float(candle.get("close"))
        low = _to_float(candle.get("low"))
        body_r = candle_body_ratio(candle)

        # The break candle must close above the swing high
        if close > sh_level:
            # This is a closed candle — confirmed break
            close_distance = close - sh_level
            body_r = candle_body_ratio(candle)
            break_rng = candle_range(candle)

            # Minimum close distance threshold
            min_distance = max(avg_rng * config.CHOCH_MIN_CLOSE_ABOVE_ATR_RATIO, config.CHOCH_CLOSE_DISTANCE_PIPS * _estimate_point_value(close))
            if close_distance >= min_distance and body_r >= config.CHOCH_MIN_BODY_RATIO:
                result.detected = True
                result.swing_level = sh_level
                result.close_level = close
                result.candle_index = i
                result.close_distance_above_swing = close_distance
                result.body_ratio = body_r
                result.close_above_proportion = close_distance / avg_rng if avg_rng > 0 else 0
                result.break_candle_confirmed = True

                # Check for immediate invalidation (next candle reverses)
                if i + 1 < len(execution_candles):
                    next_candle = execution_candles[i + 1]
                    next_close = _to_float(next_candle.get("close"))
                    next_dir = candle_direction(next_candle)
                    # Invalid if the very next candle closes below the swing high
                    if next_close < sh_level and next_dir == "bearish":
                        result.immediately_invalidated = True
                break

        # Early termination: if we see a candle close and it didn't break
        # and we've checked enough candles, give up
        if i - sh_index >= 5 and not result.detected:
            break

    return result


def _detect_bearish_choch(
    execution_candles: List[dict],
    local_swings: List[dict],
    avg_rng: float,
    sweep_index: Optional[int],
) -> CHOCHResult:
    """Detect a bearish CHOCH after buy-side liquidity sweep."""
    result = CHOCHResult()
    result.direction = "bearish"

    # Find the most recent swing high that was swept
    swing_highs = [s for s in local_swings if s["type"] == "high"]
    if not swing_highs:
        return result

    last_swing_high = swing_highs[-1]
    swing_high_level = _to_float(last_swing_high["price"])
    high_index = last_swing_high.get("index", 0)

    # Look for swing lows after the swing high
    swing_lows = [s for s in local_swings if s["type"] == "low" and s.get("index", 0) > high_index]
    if not swing_lows:
        return result

    target_swing_low = swing_lows[0]
    sl_index = target_swing_low.get("index", 0)
    sl_level = _to_float(target_swing_low["price"])

    for i in range(sl_index, min(len(execution_candles), sl_index + 8)):
        candle = execution_candles[i]
        low = _to_float(candle.get("low"))
        close = _to_float(candle.get("close"))
        high = _to_float(candle.get("high"))

        if close < sl_level:
            close_distance = sl_level - close
            body_r = candle_body_ratio(candle)

            min_distance = max(avg_rng * config.CHOCH_MIN_CLOSE_ABOVE_ATR_RATIO, config.CHOCH_CLOSE_DISTANCE_PIPS * _estimate_point_value(close))
            if close_distance >= min_distance and body_r >= config.CHOCH_MIN_BODY_RATIO:
                result.detected = True
                result.swing_level = sl_level
                result.close_level = close
                result.candle_index = i
                result.close_distance_above_swing = close_distance
                result.body_ratio = body_r
                result.close_above_proportion = close_distance / avg_rng if avg_rng > 0 else 0
                result.break_candle_confirmed = True

                if i + 1 < len(execution_candles):
                    next_candle = execution_candles[i + 1]
                    next_close = _to_float(next_candle.get("close"))
                    next_dir = candle_direction(next_candle)
                    if next_close > sl_level and next_dir == "bullish":
                        result.immediately_invalidated = True
                break

        if i - sl_index >= 5 and not result.detected:
            break

    return result


def _estimate_range(candles: List[dict]) -> float:
    """Fallback ATR estimate when ATR is zero."""
    if not candles:
        return 1.0
    ranges = [candle_range(c) for c in candles[-20:]]
    return sum(ranges) / len(ranges) if ranges else 1.0


def _estimate_point_value(price: float) -> float:
    """Estimate point value from price level."""
    if price >= 1000:
        return 0.01
    if price >= 100:
        return 0.01
    if price >= 10:
        return 0.001
    return 0.0001


def candle_direction(candle: dict) -> Optional[str]:
    """Return 'bullish', 'bearish', or None."""
    open_p = _to_float(candle.get("open"))
    close_p = _to_float(candle.get("close"))
    if close_p > open_p:
        return "bullish"
    if close_p < open_p:
        return "bearish"
    return None
