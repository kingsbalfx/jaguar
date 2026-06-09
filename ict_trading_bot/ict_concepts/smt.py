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
        return {"confirmed": False, "direction": None, "strength": 0.0, "timeframe_synced": False}

    timeframe_synced = pair_a.get("timeframe") == pair_b.get("timeframe")
    strength = 0.0
    direction = None

    if pair_a["high"] > pair_a["prev_high"] and pair_b["high"] <= pair_b["prev_high"]:
        direction = "bearish"
        divergence = abs(float(pair_a["high"]) - float(pair_a["prev_high"]))
        reference = max(abs(float(pair_b["prev_high"])), 1e-9)
        strength = min(1.0, divergence / reference)

    if pair_a["low"] < pair_a["prev_low"] and pair_b["low"] >= pair_b["prev_low"]:
        direction = "bullish"
        divergence = abs(float(pair_a["low"]) - float(pair_a["prev_low"]))
        reference = max(abs(float(pair_b["prev_low"])), 1e-9)
        strength = min(1.0, divergence / reference)

    expected = str(expected_direction or "").lower()
    if expected in ("buy", "long"):
        expected = "bullish"
    elif expected in ("sell", "short"):
        expected = "bearish"
    direction_aligned = not expected or direction == expected
    confirmed = direction is not None and timeframe_synced and strength > 0.0 and direction_aligned
    score = min(1.0, strength + (0.2 if timeframe_synced else 0.0))

    return {
        "confirmed": confirmed,
        "direction": direction,
        "strength": round(strength, 3),
        "score": round(score, 3),
        "timeframe_synced": timeframe_synced,
        "direction_aligned": direction_aligned,
    }
