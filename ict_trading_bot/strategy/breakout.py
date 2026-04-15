from typing import Dict, Optional


def breakout_retest_strategy(data: Dict) -> Optional[Dict]:
    """Strict breakout-retest fallback that still respects the ICT core gates."""
    if not data.get("liquidity_sweep"):
        return None
    if not data.get("bos"):
        return None
    if float(data.get("displacement") or 0.0) < 0.70:
        return None

    price = float(data.get("price") or 0.0)
    direction = str(data.get("trend") or "").lower()
    breakout_level = data.get("breakout_level")
    if breakout_level is None:
        return None

    try:
        breakout_level = float(breakout_level)
    except Exception:
        return None

    retest_tolerance = abs(float(data.get("retest_tolerance") or 0.0))
    if retest_tolerance <= 0:
        retest_tolerance = breakout_level * 0.001

    if direction == "bullish" and abs(price - breakout_level) <= retest_tolerance:
        return {
            "type": "BREAKOUT_RETEST",
            "entry": price,
            "sl": float(data.get("swing_low") or price - retest_tolerance),
            "tp": "next_liquidity",
            "breakout_level": breakout_level,
            "liquidity_sweep": True,
            "bos": True,
            "displacement": float(data.get("displacement") or 0.0),
        }

    if direction == "bearish" and abs(price - breakout_level) <= retest_tolerance:
        return {
            "type": "BREAKOUT_RETEST",
            "entry": price,
            "sl": float(data.get("swing_high") or price + retest_tolerance),
            "tp": "next_liquidity",
            "breakout_level": breakout_level,
            "liquidity_sweep": True,
            "bos": True,
            "displacement": float(data.get("displacement") or 0.0),
        }

    return None
