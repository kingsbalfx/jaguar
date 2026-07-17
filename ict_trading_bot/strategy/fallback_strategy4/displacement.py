"""
FALLBACK STRATEGY 4 - Displacement Detection
==============================================
Detects and scores opposing displacement after range reclaim.
"""

from typing import List, Optional

from . import config
from .models import DisplacementResult, RangeResult


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


def _candle_direction(c: dict) -> Optional[str]:
    close = _candle_close(c)
    open_p = _candle_open(c)
    if close > open_p:
        return "bullish"
    if close < open_p:
        return "bearish"
    return None


def detect_displacement(
    candles: List[dict],
    range_data: RangeResult,
    sweep_direction: str,    # "bullish" or "bearish" — expected reversal direction
    reclaim_index: int,
    atr_value: float,
) -> DisplacementResult:
    """
    Detect opposing displacement after range reclaim.
    
    For a bullish setup (swept below, reclaim back inside):
      - Look for a strong bullish candle(s) after reclaim.
    
    For a bearish setup (swept above, reclaim back inside):
      - Look for a strong bearish candle(s) after reclaim.
    """
    result = DisplacementResult()

    if reclaim_index < 0 or reclaim_index >= len(candles):
        return result

    # Search for displacement in candles after reclaim
    search_start = reclaim_index
    # Also allow displacement ON the reclaim candle itself
    search_candles = candles[search_start:]

    if len(search_candles) < 1:
        return result

    min_body_ratio = config.MIN_DISPLACEMENT_BODY_RATIO
    min_atr_ratio = config.MIN_DISPLACEMENT_ATR_RATIO

    for idx_offset, c in enumerate(search_candles):
        abs_idx = search_start + idx_offset
        direction = _candle_direction(c)
        body = _candle_body(c)
        c_range = _candle_range(c)
        body_ratio = body / c_range if c_range > 0 else 0.0
        atr_ratio = c_range / atr_value if atr_value > 0 else 0.0

        # Check direction matches expected reversal
        if sweep_direction == "bullish" and direction != "bullish":
            continue
        if sweep_direction == "bearish" and direction != "bearish":
            continue

        # Check body ratio
        if body_ratio < min_body_ratio:
            continue

        # Check range relative to ATR
        if atr_ratio < min_atr_ratio:
            continue

        # Close quality: close near high (bullish) or near low (bearish)
        if sweep_direction == "bullish":
            close_position = (_candle_close(c) - _candle_low(c)) / c_range if c_range > 0 else 0.0
        else:
            close_position = (_candle_high(c) - _candle_close(c)) / c_range if c_range > 0 else 0.0

        # Check if a swing was broken
        swing_broken = _check_swing_broken(candles, abs_idx, sweep_direction, range_data)

        # Check if FVG was created
        fvg_created = _check_fvg_created(candles, abs_idx, sweep_direction)

        # Calculate score
        score = 0
        score += min(40, int(body_ratio / 1.0 * 40))
        score += min(30, int(atr_ratio / 2.0 * 30))
        score += min(20, int(close_position * 20))
        if swing_broken:
            score += 10

        result.detected = True
        result.direction = sweep_direction
        result.candle_index = abs_idx
        result.body_ratio = body_ratio
        result.range_atr_ratio = atr_ratio
        result.close_position_quality = close_position
        result.score = min(100, score)
        result.fvg_created = fvg_created
        result.swing_broken = swing_broken
        break

    return result


def _check_swing_broken(
    candles: List[dict],
    displacement_idx: int,
    direction: str,
    range_data: RangeResult,
) -> bool:
    """
    Check if displacement broke a meaningful swing point inside the range.
    """
    if displacement_idx < 2:
        return False

    # Find recent swing points before displacement
    high = _candle_high(candles[displacement_idx])
    low = _candle_low(candles[displacement_idx])

    for i in range(max(0, displacement_idx - 10), displacement_idx):
        c = candles[i]
        if direction == "bullish" and _candle_high(c) < high:
            # Check if this was a swing high
            if i >= 2 and i + 1 < displacement_idx:
                if (_candle_high(c) > _candle_high(candles[i - 1]) and
                        _candle_high(c) > _candle_high(candles[i + 1])):
                    return True
        elif direction == "bearish" and _candle_low(c) > low:
            if i >= 2 and i + 1 < displacement_idx:
                if (_candle_low(c) < _candle_low(candles[i - 1]) and
                        _candle_low(c) < _candle_low(candles[i + 1])):
                    return True

    return False


def _check_fvg_created(
    candles: List[dict],
    displacement_idx: int,
    direction: str,
) -> bool:
    """Check if displacement created a fair value gap."""
    if displacement_idx < 2 or displacement_idx >= len(candles):
        return False

    prev = candles[displacement_idx - 1]
    curr = candles[displacement_idx]

    if direction == "bullish":
        # Bullish FVG: current low > previous high
        return _candle_low(curr) > _candle_high(prev)
    else:
        # Bearish FVG: current high < previous low
        return _candle_high(curr) < _candle_low(prev)


def calculate_displacement_score(
    body_ratio: float,
    atr_ratio: float,
    close_quality: float,
    swing_broken: bool,
    fvg_created: bool,
) -> int:
    """Calculate displacement quality score (0-100)."""
    score = 0
    score += min(40, int(body_ratio / 1.0 * 40))
    score += min(30, int(atr_ratio / 2.0 * 30))
    score += min(20, int(max(0.0, min(1.0, close_quality)) * 20))
    if swing_broken:
        score += 5
    if fvg_created:
        score += 5
    return min(100, score)
