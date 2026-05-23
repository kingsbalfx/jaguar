"""
Adaptive ICT Trade Manager – Trail stop behind the strongest structural level.

Prioritises:
1. Fresh Order Block (unmitigated, closest to price)
2. Mitigated FVG (origin candle acts as support/resistance)
3. Strong swing point (volume‑confirmed)
4. Weak swing point (fallback, but only when nothing else exists)

Always moves stop to breakeven at 0.5R.
Never moves stop away from profit.
"""

def _atr_buffer(price):
    """0.05% of price – tight but safe."""
    return price * 0.0005


def _closest_ob(obs, price, direction):
    """
    Return the most relevant unmitigated OB.
    For buys: highest bullish OB below price.
    For sells: lowest bearish OB above price.
    """
    if not obs:
        return None
    relevant = []
    for ob in obs:
        if not isinstance(ob, dict):
            continue
        if ob.get("mitigated", False):
            continue
        if ob.get("type") != ("bullish" if direction == "buy" else "bearish"):
            continue
        try:
            low = float(ob["low"])
            high = float(ob["high"])
        except Exception:
            continue
        if direction == "buy" and low < price:
            # The top of the OB is the resistance/support? For trailing a buy, we want the OB's low as support.
            relevant.append(low)
        elif direction == "sell" and high > price:
            relevant.append(high)
    if not relevant:
        return None
    return max(relevant) if direction == "buy" else min(relevant)


def _mitigated_fvg_level(fvgs, price, direction):
    """
    If an FVG has been mitigated (filled), the candle that created it
    (the origin) is a structural level. Return that level.
    For bullish FVG: origin is the low of the preceding candle.
    For bearish FVG: origin is the high of the preceding candle.
    Here we approximate: use the FVG's reference_low/reference_high if available,
    otherwise the FVG boundary.
    """
    if not fvgs:
        return None
    for fvg in fvgs:
        if not isinstance(fvg, dict):
            continue
        if not fvg.get("mitigated", False):
            continue
        if fvg.get("type") != ("bullish" if direction == "buy" else "bearish"):
            continue
        # Use reference level if stored
        ref = fvg.get("reference_low" if direction == "buy" else "reference_high")
        if ref is None:
            ref = fvg.get("low" if direction == "buy" else "high")
        try:
            return float(ref)
        except Exception:
            continue
    return None


def _strong_swings(swings, swing_type, price, direction):
    """Return swing prices that are strong (volume‑confirmed) and on the correct side."""
    candidates = []
    for s in swings:
        if s.get("type") != swing_type:
            continue
        try:
            p = float(s["price"])
        except Exception:
            continue
        # Filter to correct side
        if direction == "buy" and p >= price:
            continue
        if direction == "sell" and p <= price:
            continue
        # Prefer strong swings, but accept normal ones; ignore explicitly weak
        if s.get("strength") == "weak":
            continue
        candidates.append(p)
    return candidates


def manage_trade(trade, price, swings=None, order_blocks=None, fvgs=None, atr=None):
    """
    Main trade management call.
    Returns dict with action 'move_sl' or None.
    """
    if not trade:
        return None

    direction = str(trade.get("direction", "")).lower()
    try:
        entry = float(trade.get("entry", 0))
        current_sl = float(trade.get("sl", 0))
        price = float(price)
    except Exception:
        return None

    risk = abs(entry - current_sl)
    if risk <= 0:
        return None

    # 1. Breakeven early (0.5R)
    if direction == "buy":
        if price >= entry + risk * 0.5:
            new_sl = entry + _atr_buffer(price)
            if new_sl > current_sl:
                trade["sl"] = new_sl
                return {"action": "move_sl", "sl": new_sl}
    else:
        if price <= entry - risk * 0.5:
            new_sl = entry - _atr_buffer(price)
            if new_sl < current_sl:
                trade["sl"] = new_sl
                return {"action": "move_sl", "sl": new_sl}

    # 2. Determine best trail level
    candidate_levels = []

    # ---- Order Blocks ----
    if order_blocks:
        ob_level = _closest_ob(order_blocks, price, direction)
        if ob_level is not None:
            candidate_levels.append(("OB", ob_level))

    # ---- Mitigated FVGs ----
    if fvgs:
        fvg_level = _mitigated_fvg_level(fvgs, price, direction)
        if fvg_level is not None:
            candidate_levels.append(("FVG", fvg_level))

    # ---- Strong swing points ----
    if swings:
        swing_type = "low" if direction == "buy" else "high"
        strong = _strong_swings(swings, swing_type, price, direction)
        for p in strong[-3:]:
            candidate_levels.append(("Swing", p))

    if not candidate_levels:
        return None

    # Pick the level that gives the tightest (highest for buy, lowest for sell) stop
    if direction == "buy":
        best_level = max(c[1] for c in candidate_levels)
        best_level -= _atr_buffer(price)
    else:
        best_level = min(c[1] for c in candidate_levels)
        best_level += _atr_buffer(price)

    # Never move stop backwards
    if direction == "buy" and best_level > current_sl and best_level < price:
        trade["sl"] = best_level
        return {"action": "move_sl", "sl": best_level}
    elif direction == "sell" and best_level < current_sl and best_level > price:
        trade["sl"] = best_level
        return {"action": "move_sl", "sl": best_level}

    return None