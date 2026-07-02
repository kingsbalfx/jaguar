"""
Judas Swing / Stop Run Detection
=================================
Identifies when price makes a false move (Judas Swing) to sweep liquidity
before reversing in the true direction.

KEY REQUIREMENT: Price MUST PURGE (sweep) old highs/lows or PDH/PDL
before the reversal is valid.

Visual Identification:
1. Price sweeps above old high or PDH (for bearish reversal)
2. Price sweeps below old low or PDL (for bullish reversal)
3. PURGE confirmed by wick through level
4. Immediate reversal after purge
5. Strong momentum in opposite direction

NO scoring - it's either a Judas Swing or it's not.
"""

from typing import Dict, List, Optional
from ict_concepts.fib_visual import get_pdh_pdl, get_old_highs_lows


def detect_judas_swing(candles: List[Dict], symbol: str = None, purge_tolerance: float = 0.0001, timeframe: str = None) -> Dict:
    """
    Detect Judas Swing (Stop Run) with REQUIRED price purge.
    
    Returns:
        {
            "is_judas_swing": bool,
            "direction": str,  # "bullish" or "bearish" (reversal direction)
            "purge_confirmed": bool,  # Did price purge liquidity?
            "purged_level": float,  # What level was purged
            "purge_type": str,  # "PDH", "PDL", "old_high", "old_low"
            "reversal_strength": float  # How strong is the reversal
        }
    """
    if not candles or len(candles) < 5:
        return {
            "is_judas_swing": False,
            "direction": None,
            "timeframe": str(timeframe or "CURRENT").upper(),
            "purge_confirmed": False,
            "purged_level": None,
            "purge_type": None,
            "reversal_strength": 0.0
        }
    
    # Get reference levels for purge detection
    pdh_pdl = get_pdh_pdl(symbol) if symbol else {}
    old_levels = get_old_highs_lows(candles, periods=[20, 50], timeframe=timeframe)
    
    # Check recent candles for purge patterns
    recent = candles[-5:]
    
    # Detect bullish Judas Swing (purge below, reverse up)
    bullish_judas = _detect_bullish_judas_swing(recent, pdh_pdl, old_levels, purge_tolerance)
    if bullish_judas["is_judas_swing"]:
        bullish_judas["timeframe"] = str(timeframe or "CURRENT").upper()
        return bullish_judas
    
    # Detect bearish Judas Swing (purge above, reverse down)
    bearish_judas = _detect_bearish_judas_swing(recent, pdh_pdl, old_levels, purge_tolerance)
    if bearish_judas["is_judas_swing"]:
        bearish_judas["timeframe"] = str(timeframe or "CURRENT").upper()
        return bearish_judas
    
    return {
        "is_judas_swing": False,
        "direction": None,
        "timeframe": str(timeframe or "CURRENT").upper(),
        "purge_confirmed": False,
        "purged_level": None,
        "purge_type": None,
        "reversal_strength": 0.0
    }


def _detect_bullish_judas_swing(candles: List[Dict], pdh_pdl: Dict, old_levels: Dict, tolerance: float) -> Dict:
    """
    Detect bullish Judas Swing:
    1. Price sweeps BELOW PDL or old low
    2. Immediate reversal UP with strong candle
    """
    if len(candles) < 3:
        return {"is_judas_swing": False}
    
    # Check if we have a purge level
    pdl = pdh_pdl.get("pdl")
    old_lows = old_levels.get("old_lows", [])
    
    purge_levels = []
    if pdl:
        purge_levels.append({"price": pdl, "type": "PDL"})
    for level in old_lows:
        purge_levels.append({"price": level["price"], "type": f"old_low_{level['period']}"})
    
    if not purge_levels:
        return {"is_judas_swing": False}
    
    # Look for purge in recent candles
    purge_candle_idx = None
    purged_level = None
    purge_type = None
    
    for idx, candle in enumerate(candles[:-1]):  # Exclude last candle
        low = candle["low"]
        
        # Check if low purged any level
        for level in purge_levels:
            if low <= level["price"] * (1 + tolerance):  # Purged below
                purge_candle_idx = idx
                purged_level = level["price"]
                purge_type = level["type"]
                break
        
        if purge_candle_idx is not None:
            break
    
    if purge_candle_idx is None:
        return {"is_judas_swing": False}
    
    # Check for reversal after purge
    purge_candle = candles[purge_candle_idx]
    next_candles = candles[purge_candle_idx + 1:]
    
    if not next_candles:
        return {"is_judas_swing": False}
    
    # Reversal candle should be bullish and strong
    reversal_candle = next_candles[0]
    is_bullish = reversal_candle["close"] > reversal_candle["open"]
    
    if not is_bullish:
        return {"is_judas_swing": False}
    
    # Calculate reversal strength
    body = reversal_candle["close"] - reversal_candle["open"]
    candle_range = reversal_candle["high"] - reversal_candle["low"]
    body_ratio = body / candle_range if candle_range > 0 else 0
    
    # Check if reversal is above the purge candle's high
    reversal_above_purge = reversal_candle["close"] > purge_candle["high"]
    
    # Judas Swing confirmed if:
    # 1. Purge occurred
    # 2. Strong bullish reversal (body ratio > 0.6)
    # 3. Close above purge candle high
    is_judas_swing = body_ratio >= 0.6 and reversal_above_purge
    
    return {
        "is_judas_swing": is_judas_swing,
        "direction": "bullish",
        "purge_confirmed": True,
        "purged_level": purged_level,
        "purge_type": purge_type,
        "reversal_strength": round(body_ratio, 2),
        "reversal_candle_close": reversal_candle["close"],
        "purge_candle_low": purge_candle["low"]
    }


def _detect_bearish_judas_swing(candles: List[Dict], pdh_pdl: Dict, old_levels: Dict, tolerance: float) -> Dict:
    """
    Detect bearish Judas Swing:
    1. Price sweeps ABOVE PDH or old high
    2. Immediate reversal DOWN with strong candle
    """
    if len(candles) < 3:
        return {"is_judas_swing": False}
    
    # Check if we have a purge level
    pdh = pdh_pdl.get("pdh")
    old_highs = old_levels.get("old_highs", [])
    
    purge_levels = []
    if pdh:
        purge_levels.append({"price": pdh, "type": "PDH"})
    for level in old_highs:
        purge_levels.append({"price": level["price"], "type": f"old_high_{level['period']}"})
    
    if not purge_levels:
        return {"is_judas_swing": False}
    
    # Look for purge in recent candles
    purge_candle_idx = None
    purged_level = None
    purge_type = None
    
    for idx, candle in enumerate(candles[:-1]):  # Exclude last candle
        high = candle["high"]
        
        # Check if high purged any level
        for level in purge_levels:
            if high >= level["price"] * (1 - tolerance):  # Purged above
                purge_candle_idx = idx
                purged_level = level["price"]
                purge_type = level["type"]
                break
        
        if purge_candle_idx is not None:
            break
    
    if purge_candle_idx is None:
        return {"is_judas_swing": False}
    
    # Check for reversal after purge
    purge_candle = candles[purge_candle_idx]
    next_candles = candles[purge_candle_idx + 1:]
    
    if not next_candles:
        return {"is_judas_swing": False}
    
    # Reversal candle should be bearish and strong
    reversal_candle = next_candles[0]
    is_bearish = reversal_candle["close"] < reversal_candle["open"]
    
    if not is_bearish:
        return {"is_judas_swing": False}
    
    # Calculate reversal strength
    body = reversal_candle["open"] - reversal_candle["close"]
    candle_range = reversal_candle["high"] - reversal_candle["low"]
    body_ratio = body / candle_range if candle_range > 0 else 0
    
    # Check if reversal is below the purge candle's low
    reversal_below_purge = reversal_candle["close"] < purge_candle["low"]
    
    # Judas Swing confirmed if:
    # 1. Purge occurred
    # 2. Strong bearish reversal (body ratio > 0.6)
    # 3. Close below purge candle low
    is_judas_swing = body_ratio >= 0.6 and reversal_below_purge
    
    return {
        "is_judas_swing": is_judas_swing,
        "direction": "bearish",
        "purge_confirmed": True,
        "purged_level": purged_level,
        "purge_type": purge_type,
        "reversal_strength": round(body_ratio, 2),
        "reversal_candle_close": reversal_candle["close"],
        "purge_candle_high": purge_candle["high"]
    }


def should_enter_on_judas_reversal(judas_data: Dict, current_price: float) -> bool:
    """
    Determine if should enter based on Judas Swing reversal.
    
    Entry criteria:
    1. Judas Swing confirmed
    2. Purge confirmed
    3. Strong reversal (strength >= 0.7)
    4. Current price confirming direction
    """
    if not judas_data or not judas_data.get("is_judas_swing"):
        return False
    
    if not judas_data.get("purge_confirmed"):
        return False  # MUST have purge
    
    strength = judas_data.get("reversal_strength", 0)
    if strength < 0.7:
        return False  # Need strong reversal
    
    direction = judas_data.get("direction")
    reversal_close = judas_data.get("reversal_candle_close")
    
    if direction == "bullish":
        # For bullish Judas, enter if price is holding above reversal candle
        return current_price >= reversal_close
    elif direction == "bearish":
        # For bearish Judas, enter if price is holding below reversal candle
        return current_price <= reversal_close
    
    return False
