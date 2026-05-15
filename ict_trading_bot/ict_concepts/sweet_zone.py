"""
Sweet Zone - Pure Trend Continuation
=====================================
Identifies when price is in a pure continuation trend that doesn't need
pullbacks, retracements, or complex setups.

CONCEPT: When trend is strong and structure is clean, price continues
without needing to retest FVGs or wait for deep pullbacks.

Sweet Zone Criteria:
1. Strong directional momentum (consecutive higher highs/lows)
2. No significant opposing wicks
3. Price staying above/below key structure
4. Volume confirmation
5. NO complex scoring - it's either a Sweet Zone or it's not

If in Sweet Zone → Execute directly, no pullback needed
"""

from typing import Dict, List, Optional


def detect_sweet_zone(candles: List[Dict], trend: str, lookback: int = 10) -> Dict:
    """
    Detect if price is in a Sweet Zone (pure trend continuation).
    
    Returns:
        {
            "in_sweet_zone": bool,
            "direction": str,  # "bullish" or "bearish"
            "strength": float,  # 0-1
            "consecutive_moves": int,
            "reason": str
        }
    """
    if not candles or len(candles) < lookback:
        return {
            "in_sweet_zone": False,
            "direction": None,
            "strength": 0.0,
            "consecutive_moves": 0,
            "reason": "Insufficient data"
        }
    
    recent_candles = candles[-lookback:]
    
    # Check for consecutive higher highs/lower lows
    if trend and trend.lower() in ["bullish", "buy", "long"]:
        return _check_bullish_sweet_zone(recent_candles)
    elif trend and trend.lower() in ["bearish", "sell", "short"]:
        return _check_bearish_sweet_zone(recent_candles)
    
    return {
        "in_sweet_zone": False,
        "direction": None,
        "strength": 0.0,
        "consecutive_moves": 0,
        "reason": "No clear trend direction"
    }


def _check_bullish_sweet_zone(candles: List[Dict]) -> Dict:
    """Check for bullish Sweet Zone (consecutive higher lows)"""
    consecutive_hh = 0
    consecutive_hl = 0
    strong_candles = 0
    total_body_ratio = 0.0
    
    prev_high = None
    prev_low = None
    
    for candle in candles:
        high = candle["high"]
        low = candle["low"]
        open_price = candle["open"]
        close = candle["close"]
        
        # Check if bullish candle
        if close > open_price:
            strong_candles += 1
            body = close - open_price
            candle_range = high - low
            body_ratio = body / candle_range if candle_range > 0 else 0
            total_body_ratio += body_ratio
        
        # Check for higher highs and higher lows
        if prev_high is not None and high > prev_high:
            consecutive_hh += 1
        if prev_low is not None and low > prev_low:
            consecutive_hl += 1
        
        prev_high = high
        prev_low = low
    
    # Sweet Zone criteria
    avg_body_ratio = total_body_ratio / len(candles) if candles else 0
    bullish_candle_pct = strong_candles / len(candles)
    
    # SIMPLE CHECK: Are we seeing consecutive higher lows with strong candles?
    in_sweet_zone = (
        consecutive_hl >= 5 and  # At least 5 higher lows
        bullish_candle_pct >= 0.6 and  # At least 60% bullish candles
        avg_body_ratio >= 0.5  # Strong bodied candles (not wicks)
    )
    
    strength = min(1.0, (consecutive_hl / len(candles)) * bullish_candle_pct * avg_body_ratio)
    
    return {
        "in_sweet_zone": in_sweet_zone,
        "direction": "bullish",
        "strength": round(strength, 2),
        "consecutive_moves": consecutive_hl,
        "reason": f"Bullish Sweet Zone: {consecutive_hl} higher lows, {bullish_candle_pct*100:.0f}% bullish candles" if in_sweet_zone else "Not in Sweet Zone"
    }


def _check_bearish_sweet_zone(candles: List[Dict]) -> Dict:
    """Check for bearish Sweet Zone (consecutive lower highs)"""
    consecutive_ll = 0
    consecutive_lh = 0
    strong_candles = 0
    total_body_ratio = 0.0
    
    prev_high = None
    prev_low = None
    
    for candle in candles:
        high = candle["high"]
        low = candle["low"]
        open_price = candle["open"]
        close = candle["close"]
        
        # Check if bearish candle
        if close < open_price:
            strong_candles += 1
            body = open_price - close
            candle_range = high - low
            body_ratio = body / candle_range if candle_range > 0 else 0
            total_body_ratio += body_ratio
        
        # Check for lower lows and lower highs
        if prev_low is not None and low < prev_low:
            consecutive_ll += 1
        if prev_high is not None and high < prev_high:
            consecutive_lh += 1
        
        prev_high = high
        prev_low = low
    
    # Sweet Zone criteria
    avg_body_ratio = total_body_ratio / len(candles) if candles else 0
    bearish_candle_pct = strong_candles / len(candles)
    
    # SIMPLE CHECK: Are we seeing consecutive lower highs with strong candles?
    in_sweet_zone = (
        consecutive_lh >= 5 and  # At least 5 lower highs
        bearish_candle_pct >= 0.6 and  # At least 60% bearish candles
        avg_body_ratio >= 0.5  # Strong bodied candles
    )
    
    strength = min(1.0, (consecutive_lh / len(candles)) * bearish_candle_pct * avg_body_ratio)
    
    return {
        "in_sweet_zone": in_sweet_zone,
        "direction": "bearish",
        "strength": round(strength, 2),
        "consecutive_moves": consecutive_lh,
        "reason": f"Bearish Sweet Zone: {consecutive_lh} lower highs, {bearish_candle_pct*100:.0f}% bearish candles" if in_sweet_zone else "Not in Sweet Zone"
    }


def should_enter_on_continuation(sweet_zone_data: Dict, price: float, structure_level: float = None) -> bool:
    """
    Determine if should enter on trend continuation (no pullback needed).
    
    In Sweet Zone, we don't wait for pullbacks - we enter on continuation.
    """
    if not sweet_zone_data or not sweet_zone_data.get("in_sweet_zone"):
        return False
    
    direction = sweet_zone_data.get("direction")
    strength = sweet_zone_data.get("strength", 0)
    
    # Need strong Sweet Zone (strength >= 0.7)
    if strength < 0.7:
        return False
    
    # If structure level provided, ensure price is on right side
    if structure_level is not None:
        if direction == "bullish" and price < structure_level:
            return False  # Price should be above structure for bullish
        if direction == "bearish" and price > structure_level:
            return False  # Price should be below structure for bearish
    
    # YES - enter on continuation
    return True
