"""
ICT EXECUTION PLANNER
Places SL behind liquidity sweep and TP just BEFORE the next opposing liquidity.
Uses swing points, then OB, then FVG for TP placement.
"""

def _closest_opposing_level(swings, current_price, direction, atr):
    """Find the nearest swing point in the direction of profit."""
    if not swings:
        return None
    candidates = []
    for s in swings:
        try:
            p = float(s["price"])
        except Exception:
            continue
        if direction == "buy" and p > current_price:
            candidates.append(p)
        elif direction == "sell" and p < current_price:
            candidates.append(p)
    if not candidates:
        return None
    if direction == "buy":
        return min(candidates)
    else:
        return max(candidates)


def _ob_level(obs, current_price, direction):
    """Return the boundary of the nearest unmitigated OB in profit direction."""
    if not obs:
        return None
    relevant = []
    for ob in obs:
        if not isinstance(ob, dict) or ob.get("mitigated", False):
            continue
        if ob.get("type") != ("bullish" if direction == "buy" else "bearish"):
            continue
        try:
            low = float(ob["low"])
            high = float(ob["high"])
        except Exception:
            continue
        if direction == "buy" and high > current_price:
            relevant.append(high)
        elif direction == "sell" and low < current_price:
            relevant.append(low)
    if not relevant:
        return None
    if direction == "buy":
        return min(relevant)
    else:
        return max(relevant)


def _fvg_level(fvgs, current_price, direction):
    """Return the boundary of the nearest active FVG in profit direction."""
    if not fvgs:
        return None
    relevant = []
    for fvg in fvgs:
        if not isinstance(fvg, dict) or not fvg.get("active", True):
            continue
        try:
            low = float(fvg["low"])
            high = float(fvg["high"])
        except Exception:
            continue
        if direction == "buy" and high > current_price:
            relevant.append(high)
        elif direction == "sell" and low < current_price:
            relevant.append(low)
    if not relevant:
        return None
    if direction == "buy":
        return min(relevant)
    else:
        return max(relevant)


def plan_execution(symbol, direction, current_price, features, topdown_analysis, target_liquidity=None):
    try:
        current_price = float(current_price)
    except Exception:
        current_price = 0.0

    mtf = topdown_analysis.get("MTF") or {}
    ltf = topdown_analysis.get("LTF") or {}

    atr = features.get("atr", 0.001)
    try:
        atr = float(atr)
    except Exception:
        atr = current_price * 0.001 if current_price else 0.0001
    atr = max(atr, current_price * 0.0002)

    min_sl_distance = max(current_price * 0.0015, atr * 0.5)

    swings = mtf.get("swings", []) or ltf.get("swings", [])
    if not swings:
        if direction == "buy":
            sl = current_price - atr * 1.5
            if current_price - sl < min_sl_distance:
                sl = current_price - min_sl_distance
        else:
            sl = current_price + atr * 1.5
            if sl - current_price < min_sl_distance:
                sl = current_price + min_sl_distance
        return {
            "entry_zone": (current_price * 0.999, current_price * 1.001),
            "sl": round(float(sl), 5),
            "tp": round(float(current_price + atr * 3.0 if direction == "buy" else current_price - atr * 3.0), 5),
            "method": "atr_fallback"
        }

    highs = []
    lows = []
    for s in swings:
        try:
            price = float(s["price"])
        except Exception:
            continue
        if s.get("type") == "high":
            highs.append(price)
        elif s.get("type") == "low":
            lows.append(price)

    # --- Stop Loss ---
    if direction == "buy":
        valid_lows = [p for p in lows if p < current_price]
        if valid_lows:
            candidates = valid_lows[-5:] if len(valid_lows) >= 5 else valid_lows
            sl = min(candidates) - atr * 0.2
        else:
            sl = current_price - atr * 1.5
        if current_price - sl < min_sl_distance:
            sl = current_price - min_sl_distance
    else:
        valid_highs = [p for p in highs if p > current_price]
        if valid_highs:
            candidates = valid_highs[-5:] if len(valid_highs) >= 5 else valid_highs
            sl = max(candidates) + atr * 0.2
        else:
            sl = current_price + atr * 1.5
        if sl - current_price < min_sl_distance:
            sl = current_price + min_sl_distance

    # --- Take Profit (precise) ---
    tp_buffer = atr * 0.3   # small buffer to place TP just before the level

    # Priority: swing point → OB → FVG
    tp = None
    opposing_level = None
    for zone in target_liquidity or []:
        try:
            level = float(zone["level"])
        except (KeyError, TypeError, ValueError):
            continue
        if (direction == "buy" and level > current_price) or (direction == "sell" and level < current_price):
            opposing_level = level
            break
    if opposing_level is None:
        opposing_level = _closest_opposing_level(swings, current_price, direction, atr)
    if opposing_level is not None:
        tp = opposing_level - tp_buffer if direction == "buy" else opposing_level + tp_buffer
    else:
        obs = mtf.get("order_blocks", []) or ltf.get("order_blocks", [])
        ob_level = _ob_level(obs, current_price, direction)
        if ob_level is not None:
            tp = ob_level - tp_buffer if direction == "buy" else ob_level + tp_buffer
        else:
            fvgs = ltf.get("fvgs", []) or mtf.get("fvgs", [])
            fvg_level = _fvg_level(fvgs, current_price, direction)
            if fvg_level is not None:
                tp = fvg_level - tp_buffer if direction == "buy" else fvg_level + tp_buffer

    # If still no TP, use a default R:R of 2.0
    if tp is None:
        risk = abs(current_price - sl)
        if direction == "buy":
            tp = current_price + risk * 2.0
        else:
            tp = current_price - risk * 2.0

    # Ensure TP is always on the correct side and at least a minimum distance away
    if direction == "buy" and tp <= current_price:
        tp = current_price + atr * 2.0
    elif direction == "sell" and tp >= current_price:
        tp = current_price - atr * 2.0

    return {
        "entry_zone": (current_price * 0.999, current_price * 1.001),
        "sl": round(float(sl), 5),
        "tp": round(float(tp), 5),
        "method": "liquidity",
    }
