"""Strict structural execution planning with no synthetic fallback levels."""


def _target(target_liquidity, entry, direction, risk):
    levels = []
    for zone in target_liquidity or []:
        if not isinstance(zone, dict):
            continue
        try:
            level = float(zone["level"])
        except (KeyError, TypeError, ValueError):
            continue
        correct_side = level > entry if direction == "buy" else level < entry
        if correct_side and abs(level - entry) >= risk * 1.5:
            levels.append(level)
    if not levels:
        return None
    return min(levels) if direction == "buy" else max(levels)


def plan_execution(symbol, direction, current_price, features, topdown_analysis, target_liquidity=None):
    """Return SL/TP only when swept and opposing external liquidity are explicit."""
    del symbol, features
    direction = str(direction or "").lower()
    if direction not in ("buy", "sell"):
        return None
    entry = float(current_price)
    setup = topdown_analysis.get("strict_setup") or topdown_analysis.get("plan") or {}
    sweep = setup.get("swept_liquidity") or topdown_analysis.get("swept_liquidity") or {}
    try:
        stop = float(sweep["sweep_extreme"])
    except (KeyError, TypeError, ValueError):
        return None
    geometry = stop < entry if direction == "buy" else stop > entry
    risk = abs(entry - stop)
    if not geometry or risk <= 0:
        return None
    take_profit = _target(target_liquidity, entry, direction, risk)
    if take_profit is None:
        return None
    return {
        "entry": entry,
        "entry_zone": (entry, entry),
        "sl": stop,
        "tp": take_profit,
        "order_type": "market",
        "method": "swept_to_opposing_external_liquidity",
    }
