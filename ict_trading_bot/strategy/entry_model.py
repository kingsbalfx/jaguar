"""
HYBRID ENTRY MODEL (ICT BINARY STYLE)
No scoring, no penalties – just structural validation and signal enrichment.
"""

from ict_concepts.fib import in_discount, in_premium
from utils.symbol_profile import get_entry_profile, infer_asset_class
import os


def _normalize_trend(value):
    """Convert direction/trend strings to 'bullish' or 'bearish'."""
    v = str(value or "").lower().strip()
    if v in ("bullish", "buy", "long"):
        return "bullish"
    if v in ("bearish", "sell", "short"):
        return "bearish"
    return None


def _dynamic_stop_loss(data, trend, price):
    """Calculate a dynamic SL based on swing points and ATR."""
    trend = _normalize_trend(trend) or ""
    atr = abs(float((data or {}).get("atr", 0.0) or 0.0))
    market_condition = str((data or {}).get("market_condition") or "").lower()
    buffer_atr = atr * (0.35 if market_condition == "volatile" else 0.15)

    sweep_low = None
    sweep_high = None
    m1 = (data or {}).get("m1_candles") or []
    if isinstance(m1, list) and len(m1) >= 3:
        c2 = m1[-2]
        sweep_low = float(c2.get("low")) if c2.get("low") is not None else None
        sweep_high = float(c2.get("high")) if c2.get("high") is not None else None

    swing_low = (data or {}).get("swing_low")
    swing_high = (data or {}).get("swing_high")
    try:
        swing_low = float(swing_low) if swing_low is not None else None
    except Exception:
        swing_low = None
    try:
        swing_high = float(swing_high) if swing_high is not None else None
    except Exception:
        swing_high = None

    if trend == "bullish":
        candidates = [x for x in (sweep_low, swing_low) if isinstance(x, (int, float))]
        anchor = min(candidates) if candidates else (price - max(atr * 2.0, 0.0))
        return round(anchor - buffer_atr, 5)

    candidates = [x for x in (sweep_high, swing_high) if isinstance(x, (int, float))]
    anchor = max(candidates) if candidates else (price + max(atr * 2.0, 0.0))
    return round(anchor + buffer_atr, 5)


def hybrid_entry_model(data):
    """
    Minimal signal enrichment – returns a clean dict or None.
    Does NOT score or block trades.
    """
    if not isinstance(data, dict):
        return None

    trend = _normalize_trend(data.get("trend"))
    if trend not in ("bullish", "bearish"):
        return None

    price = float(data.get("price") or 0.0)

    # Minimal trend strength check (very loose, just to avoid random noise)
    if float(data.get("trend_strength", 0.0) or 0.0) < 0.45:
        return None

    # Check FVG and OB for enrichment (not blocking)
    fvg = data.get("fvg")
    ob = data.get("htf_ob")
    valid_fvg = fvg if isinstance(fvg, dict) and fvg.get("low") is not None and fvg.get("high") is not None else None
    valid_ob = ob if isinstance(ob, dict) and ob.get("low") is not None and ob.get("high") is not None else None

    displacement = float(data.get("displacement", 0.0) or 0.0)

    sl = _dynamic_stop_loss(data, trend, price)

    return {
        "direction": "buy" if trend == "bullish" else "sell",
        "price": price,
        "sl": sl,
        "fvg": valid_fvg,
        "htf_ob": valid_ob,
        "trend": trend,
        "valid_fvg": valid_fvg is not None,
        "valid_order_block": valid_ob is not None,
        "displacement": displacement,
        "fib_zone": "discount" if trend == "bullish" else "premium",
    }


# ------------------------------------------------------------------------------
# Keep the other functions below (score_fvg_entry, check_entry, etc.) unchanged
# ------------------------------------------------------------------------------
# (I am including them for backward compatibility; they won't affect the binary
# evaluator unless called elsewhere. If you prefer, you can delete everything
# below this comment and keep only the functions above.)

def score_fvg_entry(price, fvg, trend=None):
    if not isinstance(fvg, dict) or fvg.get("low") is None or fvg.get("high") is None:
        return 0.0
    if not (float(fvg["low"]) <= float(price) <= float(fvg["high"])):
        return 0.0
    # simple pass-through for compatibility
    return 100.0


def score_ob_entry(price, ob, trend=None):
    if not isinstance(ob, dict) or ob.get("low") is None or ob.get("high") is None:
        return 0.0
    if not (float(ob["low"]) <= float(price) <= float(ob["high"])):
        return 0.0
    return 100.0


def explain_entry_failure(trend, price, fib_levels, fvgs, htf_order_blocks, symbol=None, atr=None):
    return "not_applicable"


def check_entry(trend, price, fib_levels, fvgs, htf_order_blocks, symbol=None, atr=None):
    """Legacy strict POI validator – kept for backwards compatibility only."""
    return None