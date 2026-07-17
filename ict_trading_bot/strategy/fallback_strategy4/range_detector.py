"""
FALLBACK STRATEGY 4 - Range Detector
======================================
Objective range detection using swing points, boundary clustering, and quality scoring.
Rejects weak, poorly-formed, or trending ranges.
"""

from typing import List, Optional, Tuple

from . import config
from .models import BoundaryZone, RangeResult


def _to_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _candle_high(candle: dict) -> float:
    return _to_float(candle.get("high"))


def _candle_low(candle: dict) -> float:
    return _to_float(candle.get("low"))


def _candle_close(candle: dict) -> float:
    return _to_float(candle.get("close"))


def _estimate_point_value(price: float) -> float:
    """Estimate point/tick size from price magnitude."""
    if price <= 0:
        return 0.0001
    if price < 1:
        return 0.0001
    if price < 100:
        return 0.001
    return 0.01


def detect_range(
    candles: List[dict],
    atr_value: float,
    point: float,
    is_m1: bool = False,
) -> RangeResult:
    """
    Detect a valid intraday range from closed candle data.
    
    Returns:
        RangeResult with detected=True if a valid range is found.
    """
    result = RangeResult()

    if len(candles) < 15:
        result.rejected = True
        result.rejection_reason = "insufficient_candles"
        return result

    # Find swing points
    swings = _find_swings(candles)
    if len(swings) < 4:
        result.rejected = True
        result.rejection_reason = "insufficient_swing_points"
        return result

    # Cluster swing highs and lows
    tolerance = max(atr_value * config.BOUNDARY_TOLERANCE_ATR, point * 5)
    swing_highs = [s for s in swings if s["type"] == "high"]
    swing_lows = [s for s in swings if s["type"] == "low"]

    high_clusters = _cluster_points(swing_highs, tolerance)
    low_clusters = _cluster_points(swing_lows, tolerance)

    if not high_clusters or not low_clusters:
        result.rejected = True
        result.rejection_reason = "no_boundary_clusters"
        return result

    # Evaluate each high/low cluster pair as a potential range
    best_pair = None
    best_score = -1

    for h_cluster in high_clusters:
        for l_cluster in low_clusters:
            if l_cluster["price"] >= h_cluster["price"]:
                continue  # low must be below high

            pair_result = _evaluate_range_pair(
                candles, h_cluster, l_cluster,
                atr_value, point, is_m1,
            )
            if pair_result["score"] > best_score:
                best_score = pair_result["score"]
                best_pair = pair_result

    if best_pair is None or best_score < config.MIN_RANGE_QUALITY_SCORE:
        result.rejected = True
        result.rejection_reason = f"best_range_score_{best_score}_below_{config.MIN_RANGE_QUALITY_SCORE}"
        return result

    # Populate the result
    h_prices = sorted(best_pair["high_prices"])
    l_prices = sorted(best_pair["low_prices"])
    result.range_high = h_prices[-1]
    result.range_low = l_prices[0]
    result.range_width = result.range_high - result.range_low
    result.range_width_atr = result.range_width / atr_value if atr_value > 0 else 0.0
    result.range_midpoint = result.range_low + result.range_width * 0.5
    result.range_25 = result.range_low + result.range_width * 0.25
    result.range_75 = result.range_low + result.range_width * 0.75
    result.start_index = best_pair["start_index"]
    result.end_index = best_pair["end_index"]
    result.duration = best_pair["duration"]
    result.upper_interactions = best_pair["upper_interactions"]
    result.lower_interactions = best_pair["lower_interactions"]
    result.rotations = best_pair["rotations"]
    result.quality_score = best_pair["score"]
    result.slope = best_pair["slope"]

    # Build boundary zones
    result.upper_zone = BoundaryZone(
        price=result.range_high,
        zone_low=result.range_high - tolerance,
        zone_high=result.range_high + tolerance,
        interaction_count=result.upper_interactions,
        swing_prices=h_prices,
        liquidity_quality=min(1.0, result.upper_interactions / 5.0),
    )
    result.lower_zone = BoundaryZone(
        price=result.range_low,
        zone_low=result.range_low - tolerance,
        zone_high=result.range_low + tolerance,
        interaction_count=result.lower_interactions,
        swing_prices=l_prices,
        liquidity_quality=min(1.0, result.lower_interactions / 5.0),
    )

    result.detected = True
    result.is_valid = True
    return result


def _find_swings(candles: List[dict], lookback: int = 2) -> List[dict]:
    """Find swing highs and lows."""
    swings: List[dict] = []
    if len(candles) < lookback * 2 + 1:
        return swings
    for i in range(lookback, len(candles) - lookback):
        left = candles[i - lookback:i]
        right = candles[i + 1:i + 1 + lookback]
        current = candles[i]
        high = _candle_high(current)
        low = _candle_low(current)

        if all(high > _candle_high(c) for c in left + right):
            swings.append({"type": "high", "price": high, "index": i})
        if all(low < _candle_low(c) for c in left + right):
            swings.append({"type": "low", "price": low, "index": i})
    return swings


def _cluster_points(swings: List[dict], tolerance: float) -> List[dict]:
    """Cluster nearby swing points into zones."""
    if not swings:
        return []
    sorted_swings = sorted(swings, key=lambda x: x["price"])
    clusters = []
    current_cluster = {
        "price": sorted_swings[0]["price"],
        "prices": [sorted_swings[0]["price"]],
        "indices": [sorted_swings[0]["index"]],
    }
    for sw in sorted_swings[1:]:
        if abs(sw["price"] - current_cluster["price"]) <= tolerance:
            current_cluster["prices"].append(sw["price"])
            current_cluster["indices"].append(sw["index"])
            current_cluster["price"] = sum(current_cluster["prices"]) / len(current_cluster["prices"])
        else:
            clusters.append(current_cluster)
            current_cluster = {
                "price": sw["price"],
                "prices": [sw["price"]],
                "indices": [sw["index"]],
            }
    clusters.append(current_cluster)
    # Keep only clusters with meaningful price and at least min interactions
    return [c for c in clusters if len(c["indices"]) >= 1]


def _evaluate_range_pair(
    candles: List[dict],
    high_cluster: dict,
    low_cluster: dict,
    atr_value: float,
    point: float,
    is_m1: bool,
) -> dict:
    """Evaluate a potential range between a high cluster and low cluster."""
    range_high = max(high_cluster["prices"])
    range_low = min(low_cluster["prices"])
    range_width = range_high - range_low
    range_width_atr = range_width / atr_value if atr_value > 0 else 0.0

    all_indices = sorted(set(high_cluster["indices"] + low_cluster["indices"]))
    start_idx = min(all_indices)
    end_idx = max(all_indices)
    duration = end_idx - start_idx + 1

    # Check duration constraints
    min_dur = config.MIN_RANGE_DURATION_M1 if is_m1 else config.MIN_RANGE_DURATION_M5
    max_dur = config.MAX_RANGE_DURATION_M5
    if duration < min_dur:
        return {"score": -1, "reason": f"duration_{duration}_<_{min_dur}"}
    if duration > max_dur:
        return {"score": -1, "reason": f"duration_{duration}_>_{max_dur}"}

    # Check width constraints
    if range_width_atr < config.MIN_RANGE_WIDTH_ATR:
        return {"score": -1, "reason": f"width_{range_width_atr:.1f}atr_<_{config.MIN_RANGE_WIDTH_ATR}atr"}
    if range_width_atr > config.MAX_RANGE_WIDTH_ATR:
        return {"score": -1, "reason": f"width_{range_width_atr:.1f}atr_>_{config.MAX_RANGE_WIDTH_ATR}atr"}

    # Count boundary interactions
    upper_zone_low = range_high - max(atr_value * config.BOUNDARY_TOLERANCE_ATR, point * 5)
    upper_zone_high = range_high + max(atr_value * config.BOUNDARY_TOLERANCE_ATR, point * 5)
    lower_zone_low = range_low - max(atr_value * config.BOUNDARY_TOLERANCE_ATR, point * 5)
    lower_zone_high = range_low + max(atr_value * config.BOUNDARY_TOLERANCE_ATR, point * 5)

    upper_interactions = 0
    lower_interactions = 0
    last_touch = None  # Track for rotations: "upper" or "lower"
    rotations = 0

    for idx in range(start_idx, end_idx + 1):
        if idx >= len(candles):
            break
        c = candles[idx]
        high = _candle_high(c)
        low = _candle_low(c)

        # Upper boundary interaction: candle high >= upper zone low
        touched_upper = high >= upper_zone_low and low <= upper_zone_high
        # Lower boundary interaction: candle low <= lower zone high
        touched_lower = low <= lower_zone_high and high >= lower_zone_low

        if touched_upper:
            upper_interactions += 1
            if last_touch == "lower":
                rotations += 1
            last_touch = "upper"
        elif touched_lower:
            lower_interactions += 1
            if last_touch == "upper":
                rotations += 1
            last_touch = "lower"

    # Check interaction constraints
    if upper_interactions < config.MIN_UPPER_INTERACTIONS:
        return {"score": -1, "reason": f"upper_interactions_{upper_interactions}_<_{config.MIN_UPPER_INTERACTIONS}"}
    if lower_interactions < config.MIN_LOWER_INTERACTIONS:
        return {"score": -1, "reason": f"lower_interactions_{lower_interactions}_<_{config.MIN_LOWER_INTERACTIONS}"}
    if rotations < config.MIN_ROTATIONS:
        return {"score": -1, "reason": f"rotations_{rotations}_<_{config.MIN_ROTATIONS}"}

    # Calculate directional slope (linear regression through midpoints)
    slope = _calculate_slope(candles, start_idx, end_idx)

    # Check for excessive trend (strong slope invalidates a range)
    max_slope = range_width * 0.3 / duration  # slope threshold
    if abs(slope) > max_slope:
        return {"score": -1, "reason": f"excessive_slope_{slope:.5f}"}

    # Check sustained closes outside range
    closes_outside_high = sum(
        1 for i in range(start_idx, end_idx + 1)
        if i < len(candles) and _candle_close(candles[i]) > range_high
    )
    closes_outside_low = sum(
        1 for i in range(start_idx, end_idx + 1)
        if i < len(candles) and _candle_close(candles[i]) < range_low
    )
    total_candles = min(duration, len(candles) - start_idx)
    if total_candles > 0:
        outside_ratio = max(closes_outside_high, closes_outside_low) / total_candles
        if outside_ratio > 0.25:
            return {"score": -1, "reason": f"excessive_closes_outside_{outside_ratio:.2f}"}

    # Calculate quality score
    score = _calculate_quality_score(
        upper_interactions=upper_interactions,
        lower_interactions=lower_interactions,
        rotations=rotations,
        duration=duration,
        range_width_atr=range_width_atr,
        slope=slope,
        max_slope=max_slope,
        closes_outside_high=closes_outside_high,
        closes_outside_low=closes_outside_low,
        total_candles=total_candles,
    )

    return {
        "score": score,
        "high_prices": high_cluster["prices"],
        "low_prices": low_cluster["prices"],
        "start_index": start_idx,
        "end_index": end_idx,
        "duration": duration,
        "upper_interactions": upper_interactions,
        "lower_interactions": lower_interactions,
        "rotations": rotations,
        "slope": slope,
    }


def _calculate_slope(candles: List[dict], start: int, end: int) -> float:
    """Calculate linear regression slope through candle midpoints."""
    n = min(end - start + 1, len(candles) - start)
    if n < 3:
        return 0.0
    xs = list(range(n))
    ys = [
        (_candle_high(candles[start + i]) + _candle_low(candles[start + i])) / 2.0
        for i in range(n)
    ]
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    den = sum((x - x_mean) ** 2 for x in xs)
    return num / den if den != 0 else 0.0


def _calculate_quality_score(
    upper_interactions: int,
    lower_interactions: int,
    rotations: int,
    duration: int,
    range_width_atr: float,
    slope: float,
    max_slope: float,
    closes_outside_high: int,
    closes_outside_low: int,
    total_candles: int,
) -> int:
    """Calculate range quality score (0-100)."""
    score = 0

    # Boundary interactions (max 25)
    interaction_score = min(25, (upper_interactions + lower_interactions) * 5)
    score += interaction_score

    # Rotations (max 20)
    rotation_score = min(20, rotations * 5)
    score += rotation_score

    # Duration (max 15)
    if duration >= 20:
        dur_score = 15
    elif duration >= 15:
        dur_score = 10
    else:
        dur_score = 5
    score += dur_score

    # Range width ATR (max 20)
    if 2.0 <= range_width_atr <= 5.0:
        width_score = 20
    elif 1.5 <= range_width_atr <= 7.0:
        width_score = 15
    else:
        width_score = 10
    score += width_score

    # Slope (max 10)
    slope_ratio = abs(slope) / max_slope if max_slope > 0 else 1.0
    slope_score = max(0, 10 - int(slope_ratio * 10))
    score += slope_score

    # Lack of sustained closes outside (max 10)
    if total_candles > 0:
        outside_pct = (closes_outside_high + closes_outside_low) / total_candles
        if outside_pct <= 0.05:
            outside_score = 10
        elif outside_pct <= 0.10:
            outside_score = 7
        elif outside_pct <= 0.15:
            outside_score = 4
        else:
            outside_score = 0
        score += outside_score

    return max(0, min(100, score))
