"""
AMD (Accumulation‑Manipulation‑Distribution) Detector
Midnight open range (00:00‑01:00 UTC) → sweep → displacement
"""

def detect_amd(candles_m15, direction):
    """
    candles_m15: list of M15 candles with open,high,low,close
    direction: 'bullish' (buy) or 'bearish' (sell)
    Returns True if AMD pattern detected.
    """
    if len(candles_m15) < 16:
        return False

    # Midnight open range (first 4 M15 candles after 00:00)
    midnight_candles = candles_m15[:4]
    if not midnight_candles:
        return False
    midnight_high = max(c["high"] for c in midnight_candles)
    midnight_low = min(c["low"] for c in midnight_candles)

    # Subsequent candles after midnight
    subsequent = candles_m15[4:]
    if len(subsequent) < 4:
        return False

    if direction == "bullish":
        # Manipulation: price sweeps below the midnight low
        sweep = any(c["low"] < midnight_low for c in subsequent)
        if not sweep:
            return False
        # Distribution: price displaces above midnight high with strong body
        last_candles = subsequent[-3:]
        for c in last_candles:
            body = c["close"] - c["open"]
            if body > 0 and c["close"] > midnight_high and (body / max(c["high"]-c["low"], 1e-9) > 0.5):
                return True
    else:
        sweep = any(c["high"] > midnight_high for c in subsequent)
        if not sweep:
            return False
        last_candles = subsequent[-3:]
        for c in last_candles:
            body = c["open"] - c["close"]
            if body > 0 and c["close"] < midnight_low and (body / max(c["high"]-c["low"], 1e-9) > 0.5):
                return True
    return False