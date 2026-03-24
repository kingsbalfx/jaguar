import os


def liquidity_taken(price, liquidity, direction):
    """
    direction: buy or sell
    """

    if not isinstance(liquidity, dict):
        return False

    tolerance = float(os.getenv("LIQUIDITY_TOLERANCE_RATIO", "0.0015"))
    relaxed_mode = os.getenv("RELAX_LIQUIDITY_RULE", "true").lower() in ("1", "true", "yes")

    if direction == "buy":
        # sell-side liquidity must be taken
        for low in liquidity.get("EQL", []):
            try:
                level = float(low[0])
                if price < level:
                    return True
                if relaxed_mode and price <= level * (1 + tolerance):
                    return True
            except Exception:
                continue

    if direction == "sell":
        # buy-side liquidity must be taken
        for high in liquidity.get("EQH", []):
            try:
                level = float(high[0])
                if price > level:
                    return True
                if relaxed_mode and price >= level * (1 - tolerance):
                    return True
            except Exception:
                continue

    return False
