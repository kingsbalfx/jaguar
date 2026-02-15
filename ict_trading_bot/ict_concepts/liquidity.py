def detect_liquidity_zones(swings, tolerance=0.0003):
    """
    swings: list of swing highs/lows
    Returns EQH / EQL zones
    """

    eqh = []
    eql = []

    for i in range(len(swings) - 1):
        a = swings[i]
        b = swings[i + 1]

        if abs(a["price"] - b["price"]) <= tolerance:
            if a["type"] == "high":
                eqh.append((a["price"], b["price"]))
            else:
                eql.append((a["price"], b["price"]))

    return {
        "EQH": eqh,
        "EQL": eql
    }
