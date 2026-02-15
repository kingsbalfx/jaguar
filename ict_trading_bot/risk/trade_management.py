def manage_trade(trade, price):
    """
    trade = {
        entry, sl, tp,
        lot,
        direction,
        stage: 0
    }
    """

    r = abs(trade["entry"] - trade["sl"])

    # 🔹 1R → Move SL to BE
    if trade["stage"] == 0:
        if abs(price - trade["entry"]) >= r:
            trade["sl"] = trade["entry"]
            trade["stage"] = 1
            return {"action": "move_sl", "sl": trade["sl"]}

    # 🔹 2R → Partial TP
    if trade["stage"] == 1:
        if abs(price - trade["entry"]) >= 2 * r:
            trade["stage"] = 2
            return {"action": "partial_close", "percent": 0.5}

    # 🔹 3R+ → Trailing
    if trade["stage"] >= 2:
        if trade["direction"] == "buy":
            trade["sl"] = max(trade["sl"], price - r)
        else:
            trade["sl"] = min(trade["sl"], price + r)

        return {"action": "trail", "sl": trade["sl"]}

    return None
