"""Market-only routing for confirmed strict-state-machine entries."""


def _candle_confirmation(direction, candles):
    if not isinstance(candles, list) or len(candles) < 2:
        return False
    previous, current = candles[-2], candles[-1]
    if not all(key in current and key in previous for key in ("open", "high", "low", "close")):
        return False
    direction = str(direction or "").lower()
    candle_range = max(float(current["high"]) - float(current["low"]), 1e-12)
    body = abs(float(current["close"]) - float(current["open"]))
    if direction == "buy":
        rejection = float(current["close"]) > float(current["open"]) and min(float(current["open"]), float(current["close"])) - float(current["low"]) >= body
        engulfing = float(previous["close"]) < float(previous["open"]) and float(current["open"]) <= float(previous["close"]) and float(current["close"]) >= float(previous["open"])
        strong_close = float(current["close"]) > float(current["open"]) and (float(current["close"]) - float(current["low"])) / candle_range >= 0.75
    else:
        rejection = float(current["close"]) < float(current["open"]) and float(current["high"]) - max(float(current["open"]), float(current["close"])) >= body
        engulfing = float(previous["close"]) > float(previous["open"]) and float(current["open"]) >= float(previous["close"]) and float(current["close"]) <= float(previous["open"])
        strong_close = float(current["close"]) < float(current["open"]) and (float(current["high"]) - float(current["close"])) / candle_range >= 0.75
    return rejection or engulfing or strong_close


def choose_order_type(price, fvg=None, mode="market", direction=None, candles=None):
    """Return market only after price is in-zone and lower-timeframe action confirms."""
    del mode
    if isinstance(fvg, dict):
        try:
            if not float(fvg["low"]) <= float(price) <= float(fvg["high"]):
                return None
        except (KeyError, TypeError, ValueError):
            return None
    if candles is not None and not _candle_confirmation(direction, candles):
        return None
    return "market"


def choose_entry_price(price, retracement=None, direction=None):
    """A market-only system always uses the current executable price."""
    del retracement, direction
    return float(price)
