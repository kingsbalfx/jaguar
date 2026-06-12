def detect_smt(pair_a, pair_b, expected_direction=None):
    """
    pair_a / pair_b:
    {
        "high": float,
        "low": float,
        "prev_high": float,
        "prev_low": float,
        "timeframe": "M15"
    }
    """

    if not isinstance(pair_a, dict) or not isinstance(pair_b, dict):
        return {"confirmed": False, "direction": None, "timeframe_synced": False}

    timeframe_synced = pair_a.get("timeframe") == pair_b.get("timeframe")
    direction = None

    if pair_a["high"] > pair_a["prev_high"] and pair_b["high"] <= pair_b["prev_high"]:
        direction = "bearish"

    if pair_a["low"] < pair_a["prev_low"] and pair_b["low"] >= pair_b["prev_low"]:
        direction = "bullish"

    expected = str(expected_direction or "").lower()
    if expected in ("buy", "long"):
        expected = "bullish"
    elif expected in ("sell", "short"):
        expected = "bearish"
    direction_aligned = not expected or direction == expected
    confirmed = direction is not None and timeframe_synced and direction_aligned

    return {
        "confirmed": confirmed,
        "direction": direction,
        "timeframe_synced": timeframe_synced,
        "direction_aligned": direction_aligned,
    }
