from ict_concepts.fib import in_discount, in_premium
import os

from utils.symbol_profile import get_entry_profile, infer_asset_class


def _resolve_zone_bounds(trend, fib_levels, symbol=None, atr=None):
    f025 = fib_levels.get("0.25") if isinstance(fib_levels, dict) else None
    f05 = fib_levels.get("0.5") if isinstance(fib_levels, dict) else None
    f075 = fib_levels.get("0.75") if isinstance(fib_levels, dict) else None
    profile = get_entry_profile(symbol)
    fib_buffer_ratio = profile["fib_buffer_ratio"]
    atr_buffer_multiplier = profile["atr_buffer_multiplier"]
    atr = abs(float(atr or 0.0))

    if trend == "bullish":
        if f025 is None or f05 is None:
            return None
        lower = float(f025)
        upper = float(f05)
    elif trend == "bearish":
        if f05 is None or f075 is None:
            return None
        lower = float(f05)
        upper = float(f075)
    else:
        return None

    zone_size = max(upper - lower, 0.0)
    adaptive_buffer = max(zone_size * fib_buffer_ratio, atr * atr_buffer_multiplier)
    return {
        "lower": lower - adaptive_buffer,
        "upper": upper + adaptive_buffer,
        "buffer": adaptive_buffer,
    }


def explain_entry_failure(trend, price, fib_levels, fvgs, htf_order_blocks, symbol=None, atr=None):
    if trend not in ("bullish", "bearish"):
        return "trend"

    bounds = _resolve_zone_bounds(trend, fib_levels, symbol=symbol, atr=atr)
    if not bounds:
        return "fib_missing"
    if not (bounds["lower"] <= price <= bounds["upper"]):
        return "fib_zone"

    valid_fvg = None
    try:
        for fvg in (fvgs or []):
            if not isinstance(fvg, dict):
                continue
            if fvg.get("type") == trend and fvg.get("low") is not None and fvg.get("high") is not None:
                if fvg["low"] <= price <= fvg["high"]:
                    valid_fvg = fvg
                    break
    except Exception:
        valid_fvg = None

    if not valid_fvg:
        if os.getenv("RELAX_FVG_REQUIREMENT", "true").lower() in ("1", "true", "yes"):
            return "order_block"
        return "fvg"

    try:
        for ob in (htf_order_blocks or []):
            if not isinstance(ob, dict):
                continue
            if ob.get("type") == trend and ob.get("low") is not None and ob.get("high") is not None:
                if ob["low"] <= valid_fvg["low"] and valid_fvg["high"] <= ob["high"]:
                    return "order_block_ok"
    except Exception:
        return "order_block"

    return "order_block"

def check_entry(
    trend,
    price,
    fib_levels,
    fvgs,
    htf_order_blocks,
    symbol=None,
    atr=None,
):
    """
    trend: 'bullish' or 'bearish'
    price: current market price
    fib_levels: dict { '0.25': x, '0.5': y, '0.75': z }
    fvgs: list of LTF FVGs
    htf_order_blocks: list of HTF Order Blocks
    """

    # -------------------------
    # 1️⃣ FIB FILTER
    # -------------------------
    # Defensive fib access
    if trend not in ("bullish", "bearish"):
        return None

    bounds = _resolve_zone_bounds(trend, fib_levels, symbol=symbol, atr=atr)
    if not bounds:
        return None
    if not (bounds["lower"] <= price <= bounds["upper"]):
        return None

    # -------------------------
    # 2️⃣ FIND VALID FVG
    # -------------------------
    # Defensive FVG lookup
    valid_fvg = None
    try:
        for fvg in (fvgs or []):
            if not isinstance(fvg, dict):
                continue
            if fvg.get("type") == trend and fvg.get("low") is not None and fvg.get("high") is not None:
                if fvg["low"] <= price <= fvg["high"]:
                    valid_fvg = fvg
                    break
    except Exception:
        valid_fvg = None

    relaxed_fvg = os.getenv("RELAX_FVG_REQUIREMENT", "true").lower() in ("1", "true", "yes")
    if not valid_fvg and not relaxed_fvg:
        return None

    # -------------------------
    # 3️⃣ HTF OB CONFIRMATION
    # -------------------------
    # Defensive OB lookup
    valid_ob = None
    try:
        for ob in (htf_order_blocks or []):
            if not isinstance(ob, dict):
                continue
            if ob.get("type") == trend and ob.get("low") is not None and ob.get("high") is not None:
                if valid_fvg:
                    if ob["low"] <= valid_fvg["low"] and valid_fvg["high"] <= ob["high"]:
                        valid_ob = ob
                        break
                else:
                    if ob["low"] <= price <= ob["high"]:
                        valid_ob = ob
                        break
    except Exception:
        valid_ob = None

    if not valid_ob:
        return None

    # -------------------------
    # ✅ ENTRY CONFIRMED
    # -------------------------
    return {
        "direction": "buy" if trend == "bullish" else "sell",
        "price": price,
        "fvg": valid_fvg,
        "htf_ob": valid_ob,
        "fib_zone": "discount" if trend == "bullish" else "premium",
        "entry_buffer": bounds["buffer"],
        "asset_class": infer_asset_class(symbol),
    }

