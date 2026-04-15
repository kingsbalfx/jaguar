from utils.sessions import intelligence_session_open


def _candle_confirmation(direction, candles):
    if not isinstance(candles, list) or len(candles) < 2:
        return False

    current = candles[-1]
    previous = candles[-2]
    if not all(key in current and key in previous for key in ("open", "high", "low", "close")):
        return False

    direction = str(direction or "").lower()
    current_open = float(current["open"])
    current_close = float(current["close"])
    current_high = float(current["high"])
    current_low = float(current["low"])
    candle_range = max(current_high - current_low, 1e-9)
    body = abs(current_close - current_open)
    upper_wick = max(current_high - max(current_open, current_close), 0.0)
    lower_wick = max(min(current_open, current_close) - current_low, 0.0)

    bullish_rejection = current_close > current_open and lower_wick >= body
    bearish_rejection = current_close < current_open and upper_wick >= body
    bullish_momentum = current_close > float(previous["high"]) and body / candle_range >= 0.5
    bearish_momentum = current_close < float(previous["low"]) and body / candle_range >= 0.5

    if direction == "buy":
        return bullish_rejection or bullish_momentum
    return bearish_rejection or bearish_momentum


def choose_order_type(price, fvg, mode="auto", direction=None, candles=None, timing_score=None):
    if mode == "market":
        return "market"

    if mode == "limit":
        return "limit"

    if not isinstance(fvg, dict):
        return "limit"

    low = fvg.get("low")
    high = fvg.get("high")
    if low is None or high is None:
        return "limit"

    if not intelligence_session_open():
        return "limit"

    if timing_score is not None and float(timing_score or 0.0) < 0.60:
        return "limit"

    if float(low) <= float(price) <= float(high) and _candle_confirmation(direction, candles):
        return "market"

    return "limit"
