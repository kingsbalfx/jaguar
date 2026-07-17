"""
FALLBACK STRATEGY 3 - Liquidity Mapping
=========================================
Identifies meaningful HH, LL, swing points, and liquidity levels.
"""

from typing import List, Optional, Tuple

from .indicators import find_swing_points, atr, candle_range
from . import config


def _to_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def identify_key_levels(
    candles: List[dict],
    swings: Optional[List[dict]] = None,
) -> dict:
    """
    Identify meaningful market levels from swing points.
    
    Returns:
        {
            "swing_highs": [...],
            "swing_lows": [...],
            "last_high": {...},
            "last_low": {...},
            "equal_highs": [...],
            "equal_lows": [...],
            "external_highs": [...],   # Beyond recent range
            "external_lows": [...],
            "protected_high": None,
            "protected_low": None,
        }
    """
    if not candles or len(candles) < 10:
        return {
            "swing_highs": [],
            "swing_lows": [],
            "last_high": None,
            "last_low": None,
            "equal_highs": [],
            "equal_lows": [],
            "external_highs": [],
            "external_lows": [],
            "protected_high": None,
            "protected_low": None,
        }

    local_swings = swings if swings else find_swing_points(candles, lookback=2)
    point = _estimate_point(candles)
    avg_rng = atr(candles, period=14)

    swing_highs = [s for s in local_swings if s["type"] == "high"]
    swing_lows = [s for s in local_swings if s["type"] == "low"]

    # Classify: significant vs minor based on ATR and points
    significant_highs = []
    significant_lows = []
    min_move = max(avg_rng * 0.3, point * 10)

    for sh in swing_highs:
        if significant_highs:
            prev = significant_highs[-1]
            if abs(float(sh["price"]) - float(prev["price"])) >= min_move:
                significant_highs.append(sh)
        else:
            significant_highs.append(sh)

    for sl in swing_lows:
        if significant_lows:
            prev = significant_lows[-1]
            if abs(float(sl["price"]) - float(prev["price"])) >= min_move:
                significant_lows.append(sl)
        else:
            significant_lows.append(sl)

    # Detect equal highs/lows (within tolerance)
    equal_highs = []
    equal_lows = []
    tolerance = max(avg_rng * 0.12, point * 15)

    for i, sh in enumerate(swing_highs):
        for j in range(i + 1, len(swing_highs)):
            if abs(float(swing_highs[i]["price"]) - float(swing_highs[j]["price"])) <= tolerance:
                eq_level = (float(swing_highs[i]["price"]) + float(swing_highs[j]["price"])) / 2.0
                equal_highs.append({
                    "level": eq_level,
                    "indices": (swing_highs[i]["index"], swing_highs[j]["index"]),
                    "source": "equal_highs",
                })

    for i, sl in enumerate(swing_lows):
        for j in range(i + 1, len(swing_lows)):
            if abs(float(swing_lows[i]["price"]) - float(swing_lows[j]["price"])) <= tolerance:
                eq_level = (float(swing_lows[i]["price"]) + float(swing_lows[j]["price"])) / 2.0
                equal_lows.append({
                    "level": eq_level,
                    "indices": (swing_lows[i]["index"], swing_lows[j]["index"]),
                    "source": "equal_lows",
                })

    # External liquidity (beyond the recent visible range)
    recent = candles[-min(30, len(candles)):]
    external_high = max(_to_float(c.get("high")) for c in recent) if recent else 0.0
    external_low = min(_to_float(c.get("low")) for c in recent) if recent else 0.0

    external_highs = []
    external_lows = []
    for sh in swing_highs:
        if float(sh["price"]) > external_high:
            external_highs.append(sh)
    for sl in swing_lows:
        if float(sl["price"]) < external_low:
            external_lows.append(sl)

    # Protected high/low = the last swing that is "protected" by the other side
    protected_high = None
    protected_low = None
    if significant_highs and significant_lows:
        last_sh = significant_highs[-1]
        last_sl = significant_lows[-1]
        # A protected high means the last swing low is higher than the prior swing low
        if len(significant_lows) >= 2:
            if _to_float(significant_lows[-1]["price"]) > _to_float(significant_lows[-2]["price"]):
                protected_low = {
                    "level": _to_float(significant_lows[-1]["price"]),
                    "index": significant_lows[-1]["index"],
                    "source": "protected_low",
                }
        if len(significant_highs) >= 2:
            if _to_float(significant_highs[-1]["price"]) < _to_float(significant_highs[-2]["price"]):
                protected_high = {
                    "level": _to_float(significant_highs[-1]["price"]),
                    "index": significant_highs[-1]["index"],
                    "source": "protected_high",
                }

    return {
        "swing_highs": significant_highs,
        "swing_lows": significant_lows,
        "all_swing_highs": swing_highs,
        "all_swing_lows": swing_lows,
        "last_high": significant_highs[-1] if significant_highs else None,
        "last_low": significant_lows[-1] if significant_lows else None,
        "equal_highs": equal_highs,
        "equal_lows": equal_lows,
        "external_highs": external_highs,
        "external_lows": external_lows,
        "protected_high": protected_high,
        "protected_low": protected_low,
        "recent_range_high": external_high,
        "recent_range_low": external_low,
        "avt_rng": avg_rng,
        "tolerance": tolerance,
        "point": point,
    }


def identify_liquidity_zones(levels: dict, direction: str, current_price: float) -> List[dict]:
    """
    Identify relevant liquidity zones for the given trade direction.
    
    For buy direction (= look for sell-side liquidity below):
    - Swing lows
    - Equal lows
    - External lows
    - Protected low
    
    For sell direction (= look for buy-side liquidity above):
    - Swing highs
    - Equal highs
    - External highs
    - Protected high
    """
    zones = []
    if direction == "buy":
        # Sell-side liquidity (below current price)
        for sl in levels.get("swing_lows", []):
            level = _to_float(sl["price"])
            if level < current_price:
                zones.append({
                    "type": "swing_low",
                    "level": level,
                    "source": f"swing_low_{sl.get('index', 0)}",
                    "index": sl.get("index", 0),
                })
        for el in levels.get("equal_lows", []):
            level = _to_float(el.get("level"))
            if level < current_price:
                zones.append({
                    "type": "equal_low",
                    "level": level,
                    "source": "equal_lows",
                    "index": el.get("indices", (0, 0))[0],
                })
        for ext in levels.get("external_lows", []):
            level = _to_float(ext["price"])
            if level < current_price:
                zones.append({
                    "type": "external_low",
                    "level": level,
                    "source": "external_low",
                    "index": ext.get("index", 0),
                })
        if levels.get("protected_low"):
            level = _to_float(levels["protected_low"]["level"])
            if level < current_price:
                zones.append(levels["protected_low"])
    else:
        # Buy-side liquidity (above current price)
        for sh in levels.get("swing_highs", []):
            level = _to_float(sh["price"])
            if level > current_price:
                zones.append({
                    "type": "swing_high",
                    "level": level,
                    "source": f"swing_high_{sh.get('index', 0)}",
                    "index": sh.get("index", 0),
                })
        for eh in levels.get("equal_highs", []):
            level = _to_float(eh.get("level"))
            if level > current_price:
                zones.append({
                    "type": "equal_high",
                    "level": level,
                    "source": "equal_highs",
                    "index": eh.get("indices", (0, 0))[0],
                })
        for ext in levels.get("external_highs", []):
            level = _to_float(ext["price"])
            if level > current_price:
                zones.append({
                    "type": "external_high",
                    "level": level,
                    "source": "external_high",
                    "index": ext.get("index", 0),
                })
        if levels.get("protected_high"):
            level = _to_float(levels["protected_high"]["level"])
            if level > current_price:
                zones.append(levels["protected_high"])

    # Sort by distance
    zones.sort(key=lambda z: abs(_to_float(z["level"]) - current_price))
    return zones


def _estimate_point(candles: List[dict]) -> float:
    """Estimate the point value (minimum price increment) from price data."""
    if not candles:
        return 0.0001
    avg_price = _to_float(candles[-1].get("close", candles[0].get("close", 1.0)))
    if avg_price >= 1000:
        return 0.01
    if avg_price >= 100:
        return 0.01
    if avg_price >= 10:
        return 0.001
    return 0.0001
