import os


def liquidity_taken(price, liquidity, direction, recent_candles=None):
    """
    direction: buy or sell
    """

    if not isinstance(liquidity, dict):
        return False

    tolerance = float(os.getenv("LIQUIDITY_TOLERANCE_RATIO", "0.0015"))
    relaxed_mode = os.getenv("RELAX_LIQUIDITY_RULE", "true").lower() in ("1", "true", "yes")

    # Displacement Check (Anti-Fake Sweep)
    displacement = True
    if recent_candles and len(recent_candles) >= 2:
        curr = recent_candles[-1]
        prev = recent_candles[-2]
        body_ratio = abs(curr["close"] - curr["open"]) / (curr["high"] - curr["low"] + 1e-9)
        # Valid sweep needs a "Displacement" candle (big body) moving away from the sweep
        if body_ratio < 0.5:
            displacement = False

    if direction == "buy":
        # sell-side liquidity must be taken
        for low in liquidity.get("EQL", []):
            try:
                level = float(low[0])
                if price < level:
                    return displacement
                if relaxed_mode and price <= level * (1 + tolerance):
                    return displacement
            except Exception:
                continue

    if direction == "sell":
        # buy-side liquidity must be taken
        for high in liquidity.get("EQH", []):
            try:
                level = float(high[0])
                if price > level:
                    # Must have displacement to be a "Real" sweep
                    return displacement
                if relaxed_mode and price >= level * (1 - tolerance):
                    return True
            except Exception:
                continue

    return False
