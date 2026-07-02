"""
Visual Fibonacci Levels - Price Action Based
==============================================
Replaces mathematical fibonacci with visual price action analysis.

Core concept: Instead of calculating fib levels mathematically,
we identify price zones visually based on:
- Recent swing highs/lows
- Price clustering zones
- Areas of consolidation
- Previous day high/low (PDH/PDL)

NO complex mathematics - pure price action observation.
"""

try:
    import MetaTrader5 as mt5
except Exception:
    mt5 = None

from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import pytz


def _tf_label(timeframe: str = None) -> str:
    return str(timeframe or "CURRENT").upper()


def _price_zone(low: float, high: float, label: str, timeframe: str, source: str) -> Dict:
    low_value = float(min(low, high))
    high_value = float(max(low, high))
    midpoint = (low_value + high_value) / 2.0
    return {
        "low": low_value,
        "high": high_value,
        "midpoint": midpoint,
        "label": label,
        "timeframe": _tf_label(timeframe),
        "source": source,
        "levels": {
            "25": low_value + (high_value - low_value) * 0.25,
            "50": midpoint,
            "75": low_value + (high_value - low_value) * 0.75,
        },
    }


def get_recent_swing_zones(candles: List[Dict], lookback: int = 50, timeframe: str = None) -> Dict:
    """
    Identify swing highs and lows visually from recent price action.
    Returns visual zones where price historically reacted.
    """
    if not candles or len(candles) < 3:
        return {
            "timeframe": _tf_label(timeframe),
            "premium_zone": None,
            "discount_zone": None,
            "equilibrium": None,
            "swing_high": None,
            "swing_low": None,
        }
    
    # Get recent swing high and low
    highs = [c["high"] for c in candles[-lookback:]]
    lows = [c["low"] for c in candles[-lookback:]]
    
    swing_high = max(highs)
    swing_low = min(lows)
    
    # Visual zones (not mathematical fib)
    equilibrium = (swing_high + swing_low) / 2
    
    return {
        "timeframe": _tf_label(timeframe),
        "swing_high": swing_high,
        "swing_low": swing_low,
        "equilibrium": equilibrium,
        "premium_zone": _price_zone(equilibrium, swing_high, "visual_premium", timeframe, "recent_swing_range"),
        "discount_zone": _price_zone(swing_low, equilibrium, "visual_discount", timeframe, "recent_swing_range"),
    }


def get_pdh_pdl(symbol: str, current_time: datetime = None) -> Dict:
    """
    Get Previous Day High (PDH) and Previous Day Low (PDL).
    These are visual reference points for intraday trading.
    """
    if mt5 is None:
        return {"pdh": None, "pdl": None}
    
    try:
        # Get previous day's D1 candle
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 1, 2)
        if rates is None or len(rates) < 2:
            return {"pdh": None, "pdl": None}
        
        prev_day = rates[0]  # Yesterday's candle
        
        return {
            "pdh": float(prev_day["high"]),
            "pdl": float(prev_day["low"]),
            "pdc": float(prev_day["close"]),  # Previous Day Close
            "pdo": float(prev_day["open"])    # Previous Day Open
        }
    except Exception:
        return {"pdh": None, "pdl": None}


def get_old_highs_lows(candles: List[Dict], periods: List[int] = [20, 50, 100], timeframe: str = None) -> Dict:
    """
    Track old highs and lows at different periods.
    These act as visual magnets for price and liquidity pools.
    """
    old_levels = {
        "old_highs": [],
        "old_lows": []
    }
    
    if not candles:
        return old_levels
    
    for period in periods:
        if len(candles) >= period:
            window = candles[-period:]
            old_high = max(c["high"] for c in window)
            old_low = min(c["low"] for c in window)
            
            old_levels["old_highs"].append({
                "price": old_high,
                "period": period,
                "label": f"{_tf_label(timeframe)} {period}-bar high",
                "timeframe": _tf_label(timeframe),
                "source": "visual_old_high",
            })
            old_levels["old_lows"].append({
                "price": old_low,
                "period": period,
                "label": f"{_tf_label(timeframe)} {period}-bar low",
                "timeframe": _tf_label(timeframe),
                "source": "visual_old_low",
            })
    
    return old_levels


def is_price_in_discount_visual(price: float, zones: Dict) -> bool:
    """
    Visual check: Is price in discount zone?
    Discount = Below equilibrium (cheap area for buyers)
    """
    if not zones or zones.get("equilibrium") is None:
        return False
    
    equilibrium = zones["equilibrium"]
    discount_zone = zones.get("discount_zone", {})
    
    if not discount_zone or discount_zone.get("low") is None:
        return price < equilibrium
    
    return discount_zone["low"] <= price <= equilibrium


def is_price_in_premium_visual(price: float, zones: Dict) -> bool:
    """
    Visual check: Is price in premium zone?
    Premium = Above equilibrium (expensive area for sellers)
    """
    if not zones or zones.get("equilibrium") is None:
        return False
    
    equilibrium = zones["equilibrium"]
    premium_zone = zones.get("premium_zone", {})
    
    if not premium_zone or premium_zone.get("high") is None:
        return price > equilibrium
    
    return equilibrium <= price <= premium_zone["high"]


def get_visual_entry_zones(
    candles: List[Dict],
    trend: str,
    symbol: str = None,
    timeframe: str = None,
    reference_levels: Dict = None,
    include_pdh_pdl: bool = True,
) -> Dict:
    """
    Identify visual entry zones based on price action (not mathematics).
    
    For BULLISH trend:
    - Look for discount zones (below equilibrium)
    - PDL area
    - Old lows that held
    
    For BEARISH trend:
    - Look for premium zones (above equilibrium)
    - PDH area
    - Old highs that held
    """
    timeframe_label = _tf_label(timeframe)
    swing_zones = get_recent_swing_zones(candles, timeframe=timeframe_label)
    pdh_pdl = reference_levels if reference_levels is not None else get_pdh_pdl(symbol) if symbol and include_pdh_pdl else {}
    old_levels = get_old_highs_lows(candles, timeframe=timeframe_label)
    
    entry_zones = {
        "timeframe": timeframe_label,
        "trend": trend,
        "swing_zones": swing_zones,
        "pdh_pdl": pdh_pdl,
        "old_levels": old_levels,
        "recommended_entry": None,
        "model": "visual_price_action",
    }
    
    # Recommend entry zone based on trend
    if trend and trend.lower() in ["bullish", "buy", "long"]:
        # For buys, look for discount/support areas
        entry_zones["recommended_entry"] = {
            "type": "discount",
            "timeframe": timeframe_label,
            "zones": [
                swing_zones.get("discount_zone"),
                {"price": pdh_pdl.get("pdl"), "label": "PDL"} if pdh_pdl.get("pdl") else None,
                *old_levels.get("old_lows", [])[:2],
            ],
            "description": f"Look for price to react at {timeframe_label} visual discount zones, old lows, or PDL"
        }
    elif trend and trend.lower() in ["bearish", "sell", "short"]:
        # For sells, look for premium/resistance areas
        entry_zones["recommended_entry"] = {
            "type": "premium",
            "timeframe": timeframe_label,
            "zones": [
                swing_zones.get("premium_zone"),
                {"price": pdh_pdl.get("pdh"), "label": "PDH"} if pdh_pdl.get("pdh") else None,
                *old_levels.get("old_highs", [])[:2],
            ],
            "description": f"Look for price to react at {timeframe_label} visual premium zones, old highs, or PDH"
        }
    
    return entry_zones


def visual_price_position(price: float, zones: Dict, direction: str = None, tolerance: float = 0.0005) -> Dict:
    """
    Summarize whether price is in the correct visual half for the current direction.
    This works on H1/M15/M5 visual zones, not only daily references.
    """
    in_discount = is_price_in_discount_visual(price, zones.get("swing_zones") or zones)
    in_premium = is_price_in_premium_visual(price, zones.get("swing_zones") or zones)
    at_visual_zone = check_price_at_visual_zone(price, zones, tolerance=tolerance)
    context = str(direction or "").lower()
    correct_half = (
        in_discount if context in ("buy", "bullish", "long")
        else in_premium if context in ("sell", "bearish", "short")
        else False
    )
    return {
        "price": float(price),
        "timeframe": zones.get("timeframe"),
        "in_discount": bool(in_discount),
        "in_premium": bool(in_premium),
        "correct_visual_half": bool(correct_half),
        "at_visual_zone": bool(at_visual_zone.get("at_zone")),
        "zones": at_visual_zone.get("zones", []),
    }


def check_price_at_visual_zone(price: float, zones: Dict, tolerance: float = 0.0005) -> Dict:
    """
    Check if current price is at any visual zone (PDH/PDL, old high/low, etc.)
    Returns which zone price is at, if any.
    """
    at_zones = []
    
    # Check PDH/PDL
    pdh_pdl = zones.get("pdh_pdl", {})
    if pdh_pdl.get("pdh"):
        if abs(price - pdh_pdl["pdh"]) / price <= tolerance:
            at_zones.append({"type": "PDH", "price": pdh_pdl["pdh"]})
    if pdh_pdl.get("pdl"):
        if abs(price - pdh_pdl["pdl"]) / price <= tolerance:
            at_zones.append({"type": "PDL", "price": pdh_pdl["pdl"]})
    
    # Check old highs/lows
    old_levels = zones.get("old_levels", {})
    for level in old_levels.get("old_highs", []):
        if abs(price - level["price"]) / price <= tolerance:
            at_zones.append({"type": "Old High", "price": level["price"], "label": level["label"]})
    for level in old_levels.get("old_lows", []):
        if abs(price - level["price"]) / price <= tolerance:
            at_zones.append({"type": "Old Low", "price": level["price"], "label": level["label"]})
    
    return {
        "at_zone": len(at_zones) > 0,
        "zones": at_zones
    }


# Backward compatibility with old fib.py
def in_discount(price: float, fib_or_zones: Dict) -> bool:
    """Compatibility function - works with both old fib dict or new visual zones"""
    # Check if it's old fib format (has "0.0", "0.5" keys)
    if "0.0" in fib_or_zones:
        return fib_or_zones["0.0"] <= price <= fib_or_zones.get("0.5", fib_or_zones["1.0"])
    # New visual format
    return is_price_in_discount_visual(price, fib_or_zones)


def in_premium(price: float, fib_or_zones: Dict) -> bool:
    """Compatibility function - works with both old fib dict or new visual zones"""
    # Check if it's old fib format
    if "0.5" in fib_or_zones and "1.0" in fib_or_zones:
        return fib_or_zones["0.5"] <= price <= fib_or_zones["1.0"]
    # New visual format
    return is_price_in_premium_visual(price, fib_or_zones)
