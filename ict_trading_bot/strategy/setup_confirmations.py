from strategy.liquidity_filter import liquidity_taken


def _direction_to_trend(direction):
    return "bullish" if direction == "buy" else "bearish"


def _filter_swings(swings, swing_type):
    if not isinstance(swings, list):
        return []
    return [s for s in swings if isinstance(s, dict) and s.get("type") == swing_type]


def recent_bos(swings, trend):
    highs = _filter_swings(swings, "high")
    lows = _filter_swings(swings, "low")

    if trend == "bullish":
        return len(highs) >= 2 and float(highs[-1]["price"]) > float(highs[-2]["price"])
    if trend == "bearish":
        return len(lows) >= 2 and float(lows[-1]["price"]) < float(lows[-2]["price"])
    return False


def swing_trend_confirmation(swings, trend):
    highs = _filter_swings(swings, "high")
    lows = _filter_swings(swings, "low")

    if trend == "bullish":
        higher_high = len(highs) >= 2 and float(highs[-1]["price"]) > float(highs[-2]["price"])
        higher_low = len(lows) >= 2 and float(lows[-1]["price"]) > float(lows[-2]["price"])
        return higher_high or higher_low

    if trend == "bearish":
        lower_high = len(highs) >= 2 and float(highs[-1]["price"]) < float(highs[-2]["price"])
        lower_low = len(lows) >= 2 and float(lows[-1]["price"]) < float(lows[-2]["price"])
        return lower_high or lower_low

    return False


def bos_setup(analysis, trend):
    mtf_swings = (analysis.get("MTF") or {}).get("swings") or []
    ltf_swings = (analysis.get("LTF") or {}).get("swings") or []
    mtf_bos = recent_bos(mtf_swings, trend)
    ltf_bos = recent_bos(ltf_swings, trend)
    return {
        "confirmed": mtf_bos or ltf_bos,
        "mtf_bos": mtf_bos,
        "ltf_bos": ltf_bos,
    }


def liquidity_sweep_or_swing(price, analysis, direction):
    trend = _direction_to_trend(direction)
    mtf = analysis.get("MTF") or {}
    ltf = analysis.get("LTF") or {}

    sweep = liquidity_taken(price, mtf.get("liquidity"), direction)
    mtf_swing = swing_trend_confirmation(mtf.get("swings") or [], trend)
    ltf_swing = swing_trend_confirmation(ltf.get("swings") or [], trend)

    return {
        "confirmed": sweep or mtf_swing or ltf_swing,
        "liquidity_sweep": sweep,
        "mtf_swing": mtf_swing,
        "ltf_swing": ltf_swing,
    }
