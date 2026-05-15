"""
Visual FVG Encroachment Detection
==================================
Detects when price is actively entering (encroaching) a Fair Value Gap.

VISUAL APPROACH (not mathematical):
- Watch price action as it approaches FVG
- Confirm price is ACTIVELY moving into the gap
- Not just touching, but FILLING the imbalance

This is more dynamic than static zone checks.
"""

from typing import Dict, List, Optional


def is_price_encroaching_fvg(price: float, fvg: Dict, recent_candles: List[Dict] = None) -> Dict:
    """
    Visual check: Is price actively encroaching (entering) the FVG?
    
    Returns:
        {
            "is_encroaching": bool,
            "encroachment_pct": float,  # How much of FVG is filled
            "entry_side": str,  # "from_above" or "from_below"
            "active_fill": bool  # Is price actively filling (moving into gap)?
        }
    """
    if not isinstance(fvg, dict):
        return {"is_encroaching": False, "encroachment_pct": 0, "entry_side": None, "active_fill": False}
    
    fvg_low = fvg.get("low")
    fvg_high = fvg.get("high")
    
    if fvg_low is None or fvg_high is None:
        return {"is_encroaching": False, "encroachment_pct": 0, "entry_side": None, "active_fill": False}
    
    # Check if price is inside FVG
    is_inside = fvg_low <= price <= fvg_high
    
    if not is_inside:
        return {"is_encroaching": False, "encroachment_pct": 0, "entry_side": None, "active_fill": False}
    
    # Calculate encroachment percentage
    gap_size = fvg_high - fvg_low
    if gap_size == 0:
        return {"is_encroaching": False, "encroachment_pct": 0, "entry_side": None, "active_fill": False}
    
    encroachment_pct = (price - fvg_low) / gap_size
    
    # Determine entry side (from above or below)
    entry_side = None
    active_fill = False
    
    if recent_candles and len(recent_candles) >= 2:
        # Check previous price to determine direction
        prev_price = recent_candles[-2]["close"]
        current_price = recent_candles[-1]["close"]
        
        if prev_price > fvg_high and current_price <= fvg_high:
            entry_side = "from_above"
            active_fill = True  # Price moving down into gap
        elif prev_price < fvg_low and current_price >= fvg_low:
            entry_side = "from_below"
            active_fill = True  # Price moving up into gap
        elif fvg_low <= prev_price <= fvg_high:
            # Was already in gap, check movement direction
            if current_price < prev_price:
                entry_side = "from_above"
                active_fill = current_price > fvg_low  # Still filling
            else:
                entry_side = "from_below"
                active_fill = current_price < fvg_high  # Still filling
    
    return {
        "is_encroaching": True,
        "encroachment_pct": round(encroachment_pct, 2),
        "entry_side": entry_side,
        "active_fill": active_fill,
        "gap_size": gap_size,
        "distance_from_low": price - fvg_low,
        "distance_from_high": fvg_high - price
    }


def check_fvg_fill_consequence(fvg: Dict, price: float, trend: str) -> Dict:
    """
    Consequence of FVG encroachment:
    - Bullish FVG filled from above = potential rejection up
    - Bearish FVG filled from below = potential rejection down
    - Full fill = gap invalidated, may need new setup
    """
    encroachment = is_price_encroaching_fvg(price, fvg)
    
    if not encroachment["is_encroaching"]:
        return {"consequence": "no_fill", "action": "wait"}
    
    encroach_pct = encroachment["encroachment_pct"]
    entry_side = encroachment["entry_side"]
    fvg_type = fvg.get("type", "").lower()
    
    # Full fill (>80% filled)
    if encroach_pct > 0.8:
        return {
            "consequence": "full_fill",
            "action": "fvg_invalidated",
            "reason": "FVG over 80% filled - gap invalidated"
        }
    
    # Optimal fill (50-70%)
    if 0.5 <= encroach_pct <= 0.7:
        # Check if entry side matches FVG type for confluence
        if fvg_type == "bullish" and entry_side == "from_above":
            return {
                "consequence": "optimal_fill",
                "action": "enter_long",
                "reason": "Bullish FVG filled from above - expect rejection up"
            }
        elif fvg_type == "bearish" and entry_side == "from_below":
            return {
                "consequence": "optimal_fill",
                "action": "enter_short",
                "reason": "Bearish FVG filled from below - expect rejection down"
            }
    
    # Partial fill (<50%)
    if encroach_pct < 0.5:
        return {
            "consequence": "partial_fill",
            "action": "wait_for_deeper_fill",
            "reason": f"Only {encroach_pct*100:.0f}% filled - wait for 50-70% optimal fill"
        }
    
    return {
        "consequence": "in_gap",
        "action": "monitor",
        "reason": "Price in FVG - monitor for rejection or full fill"
    }
