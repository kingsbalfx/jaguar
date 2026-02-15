def liquidity_taken(price, liquidity, direction):
    """
    direction: buy or sell
    """

    if not isinstance(liquidity, dict):
        return False

    if direction == "buy":
        # sell-side liquidity must be taken
        for low in liquidity.get("EQL", []):
            try:
                if price < low[0]:
                    return True
            except Exception:
                continue

    if direction == "sell":
        # buy-side liquidity must be taken
        for high in liquidity.get("EQH", []):
            try:
                if price > high[0]:
                    return True
            except Exception:
                continue

    return False
