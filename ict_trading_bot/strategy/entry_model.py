from ict_concepts.fib import in_discount, in_premium
from strategy.ict_fvg import ict_liquidity_fvg_strategy
from strategy.breakout import breakout_retest_strategy

from utils.symbol_profile import get_entry_profile, infer_asset_class


def _resolve_zone_bounds(trend, fib_levels, symbol=None, atr=None):
    f00 = fib_levels.get("0.0") if isinstance(fib_levels, dict) else None
    f05 = fib_levels.get("0.5") if isinstance(fib_levels, dict) else None
    f10 = fib_levels.get("1.0") if isinstance(fib_levels, dict) else None
    profile = get_entry_profile(symbol)
    fib_buffer_ratio = profile["fib_buffer_ratio"]
    atr_buffer_multiplier = profile["atr_buffer_multiplier"]
    atr = abs(float(atr or 0.0))

    if trend == "bullish":
        if f00 is None or f05 is None:
            return None
        lower = float(f00)
        upper = float(f05)
    elif trend == "bearish":
        if f05 is None or f10 is None:
            return None
        lower = float(f05)
        upper = float(f10)
    else:
        return None

    zone_size = max(upper - lower, 0.0)
    adaptive_buffer = max(zone_size * fib_buffer_ratio, atr * atr_buffer_multiplier)
    return {
        "lower": lower - adaptive_buffer,
        "upper": upper + adaptive_buffer,
        "buffer": adaptive_buffer,
    }


def _is_valid_fvg(fvg, trend, price):
    if not isinstance(fvg, dict):
        return False
    if fvg.get("type") != trend:
        return False
    if fvg.get("low") is None or fvg.get("high") is None:
        return False
    if fvg.get("mitigated") or not fvg.get("active", True):
        return False
    if not fvg.get("size_ok", True) or not fvg.get("context_aligned", True):
        return False
    return float(fvg["low"]) <= float(price) <= float(fvg["high"])


def _is_valid_order_block(ob, trend, reference_fvg=None, price=None):
    if not isinstance(ob, dict):
        return False
    if ob.get("type") != trend:
        return False
    if ob.get("low") is None or ob.get("high") is None:
        return False
    if not ob.get("liquidity_sweep_confirmed", False):
        return False
    if not ob.get("institutional_footprint", False):
        return False
    if float(ob.get("displacement", 0.0) or 0.0) < 0.70:
        return False

    if isinstance(reference_fvg, dict):
        return float(ob["low"]) <= float(reference_fvg["low"]) and float(reference_fvg["high"]) <= float(ob["high"])

    if price is None:
        return False
    return float(ob["low"]) <= float(price) <= float(ob["high"])


def explain_entry_failure(trend, price, fib_levels, fvgs, htf_order_blocks, symbol=None, atr=None):
    if trend not in ("bullish", "bearish"):
        return "trend"

    bounds = _resolve_zone_bounds(trend, fib_levels, symbol=symbol, atr=atr)
    if not bounds:
        return "fib_missing"
    if not (bounds["lower"] <= price <= bounds["upper"]):
        return "fib_zone"

    valid_fvg = next((fvg for fvg in (fvgs or []) if _is_valid_fvg(fvg, trend, price)), None)
    if not valid_fvg:
        return "valid_fvg"

    valid_ob = next(
        (ob for ob in (htf_order_blocks or []) if _is_valid_order_block(ob, trend, reference_fvg=valid_fvg, price=price)),
        None,
    )
    if not valid_ob:
        return "valid_order_block"

    return "ready"


def generate_entry(data):
    signal = ict_liquidity_fvg_strategy(data)
    if signal:
        return signal

    signal = breakout_retest_strategy(data)
    if signal:
        return signal

    return None


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
    Strict POI validation after the higher-priority setup filters.
    """
    if trend not in ("bullish", "bearish"):
        return None

    bounds = _resolve_zone_bounds(trend, fib_levels, symbol=symbol, atr=atr)
    if not bounds or not (bounds["lower"] <= price <= bounds["upper"]):
        return None

    valid_fvg = next((fvg for fvg in (fvgs or []) if _is_valid_fvg(fvg, trend, price)), None)
    if not valid_fvg:
        return None

    valid_ob = next(
        (ob for ob in (htf_order_blocks or []) if _is_valid_order_block(ob, trend, reference_fvg=valid_fvg, price=price)),
        None,
    )
    if not valid_ob:
        return None

    fib_zone = "discount" if trend == "bullish" and in_discount(price, fib_levels) else "premium" if in_premium(price, fib_levels) else "equilibrium"
    return {
        "type": "ICT_STRUCTURAL_ENTRY",
        "direction": "buy" if trend == "bullish" else "sell",
        "price": price,
        "fvg": valid_fvg,
        "htf_ob": valid_ob,
        "fib_zone": fib_zone,
        "entry_buffer": bounds["buffer"],
        "asset_class": infer_asset_class(symbol),
        "trend": trend,
        "valid_fvg": True,
        "valid_order_block": True,
    }
