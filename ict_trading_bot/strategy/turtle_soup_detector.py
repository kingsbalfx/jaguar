"""
Turtle Soup (False Breakout) Detector
Break of structure that immediately reverses.
"""

def detect_turtle_soup(candles_m5, direction):
    """
    candles_m5: list of M5 candles (at least 8)
    direction: 'bullish' (buy) or 'bearish' (sell)
    """
    if len(candles_m5) < 8:
        return False

    recent = candles_m5[-8:]
    if direction == "bullish":
        # Find a prior swing low (lowest low in first half)
        lows = [c["low"] for c in recent[:4]]
        if not lows:
            return False
        swing_low = min(lows)
        # Check if price broke below swing_low in the second half
        for c in recent[-4:]:
            if c["low"] < swing_low:
                # Then immediate reversal: next candle bullish with strong body
                idx = recent.index(c)
                if idx + 1 < len(recent):
                    next_c = recent[idx+1]
                    body = next_c["close"] - next_c["open"]
                    if body > 0 and (body / max(next_c["high"]-next_c["low"], 1e-9) > 0.6):
                        return True
    else:
        highs = [c["high"] for c in recent[:4]]
        if not highs:
            return False
        swing_high = max(highs)
        for c in recent[-4:]:
            if c["high"] > swing_high:
                idx = recent.index(c)
                if idx + 1 < len(recent):
                    next_c = recent[idx+1]
                    body = next_c["open"] - next_c["close"]
                    if body > 0 and (body / max(next_c["high"]-next_c["low"], 1e-9) > 0.6):
                        return True
    return False