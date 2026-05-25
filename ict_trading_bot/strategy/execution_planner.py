"""
ICT EXECUTION PLANNER
Places stop loss behind liquidity sweep; no fixed take profit.
Forces SL to be safely below entry (buys) / above entry (sells).
"""

def plan_execution(symbol, direction, current_price, features, topdown_analysis):
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
            "tp": 0.0,
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

    return {
        "entry_zone": (current_price * 0.999, current_price * 1.001),
        "sl": round(float(sl), 5),
        "tp": 0.0,
        "method": "liquidity"
    }