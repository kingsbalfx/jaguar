"""Deterministic SMT divergence detection."""


def _breaks(snapshot):
    return {
        "higher_high": float(snapshot["high"]) > float(snapshot["prev_high"]),
        "lower_low": float(snapshot["low"]) < float(snapshot["prev_low"]),
    }


def _expected(value):
    normalized = str(value or "").lower()
    if normalized in ("buy", "long", "bullish"):
        return "bullish"
    if normalized in ("sell", "short", "bearish"):
        return "bearish"
    return None


def detect_smt(pair_a, pair_b, expected_direction=None, correlation_mode="positive"):
    """Detect SMT for positive or inverse correlation and explain the divergence."""
    required = {"high", "low", "prev_high", "prev_low", "timeframe"}
    if not isinstance(pair_a, dict) or not isinstance(pair_b, dict):
        return {"confirmed": False, "direction": None, "timeframe_synced": False, "reason": "invalid snapshots"}
    if not required.issubset(pair_a) or not required.issubset(pair_b):
        return {"confirmed": False, "direction": None, "timeframe_synced": False, "reason": "incomplete snapshots"}

    timeframe_synced = pair_a["timeframe"] == pair_b["timeframe"]
    mode = str(correlation_mode or "positive").lower()
    if mode not in ("positive", "inverse"):
        return {"confirmed": False, "direction": None, "timeframe_synced": timeframe_synced, "reason": "unsupported correlation mode"}

    left = _breaks(pair_a)
    right = _breaks(pair_b)
    direction = None
    divergence = None

    if mode == "positive":
        if left["higher_high"] != right["higher_high"]:
            direction, divergence = "bearish", "only one positively-correlated market made a higher high"
        elif left["lower_low"] != right["lower_low"]:
            direction, divergence = "bullish", "only one positively-correlated market made a lower low"
    else:
        if left["higher_high"] == right["lower_low"] and (left["higher_high"] or right["lower_low"]):
            divergence = None
        elif left["lower_low"] == right["higher_high"] and (left["lower_low"] or right["higher_high"]):
            divergence = None
        elif left["higher_high"] or right["lower_low"]:
            direction, divergence = "bearish", "inverse markets failed to confirm high-side expansion"
        elif left["lower_low"] or right["higher_high"]:
            direction, divergence = "bullish", "inverse markets failed to confirm low-side expansion"

    expected = _expected(expected_direction)
    direction_aligned = expected is None or direction == expected
    confirmed = bool(direction and timeframe_synced and direction_aligned)
    return {
        "confirmed": confirmed,
        "direction": direction,
        "timeframe_synced": timeframe_synced,
        "direction_aligned": direction_aligned,
        "correlation_mode": mode,
        "left_breaks": left,
        "right_breaks": right,
        "reason": divergence or "no SMT divergence",
    }
