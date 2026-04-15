from typing import Dict, Optional


MIN_DISPLACEMENT = 0.70


def _valid_fvg(data: Dict) -> Optional[Dict]:
    fvg = data.get("fvg")
    if not isinstance(fvg, dict):
        return None
    if fvg.get("mitigated") or not fvg.get("active", True):
        return None
    if not fvg.get("size_ok", True) or not fvg.get("context_aligned", True):
        return None

    low = fvg.get("low")
    high = fvg.get("high")
    if low is None or high is None:
        return None

    price = float(data.get("price") or 0.0)
    if not (float(low) <= price <= float(high)):
        return None
    return fvg


def ict_liquidity_fvg_strategy(data: Dict) -> Optional[Dict]:
    """Strict ICT liquidity sweep + BOS + displacement + active FVG entry."""
    if not data.get("liquidity_sweep"):
        return None

    if not data.get("bos"):
        return None

    displacement = float(data.get("displacement") or 0.0)
    if displacement < MIN_DISPLACEMENT:
        return None

    fvg = _valid_fvg(data)
    if not fvg:
        return None

    trend = str(data.get("trend") or "").lower()
    if trend not in ("bullish", "bearish"):
        return None

    price = float(data.get("price") or 0.0)
    if trend == "bullish":
        sl = float(data.get("swing_low") or fvg["low"])
    else:
        sl = float(data.get("swing_high") or fvg["high"])

    return {
        "type": "ICT_FVG",
        "entry": price,
        "sl": sl,
        "tp": "next_liquidity",
        "fvg": fvg,
        "trend": trend,
        "liquidity_sweep": True,
        "bos": True,
        "displacement": displacement,
        "valid_fvg": True,
    }
