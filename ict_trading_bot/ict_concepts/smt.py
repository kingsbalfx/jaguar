def detect_smt(pair_a, pair_b):
    """
    pair_a / pair_b:
    {
        "high": float,
        "low": float,
        "prev_high": float,
        "prev_low": float
    }
    """

    # Bearish SMT (distribution)
    if pair_a["high"] > pair_a["prev_high"] and pair_b["high"] <= pair_b["prev_high"]:
        return "bearish"

    # Bullish SMT (accumulation)
    if pair_a["low"] < pair_a["prev_low"] and pair_b["low"] >= pair_b["prev_low"]:
        return "bullish"

    return None
