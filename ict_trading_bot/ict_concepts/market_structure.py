try:
    import MetaTrader5 as mt5
except Exception:
    mt5 = None


def _require_mt5():
    if mt5 is None:
        raise RuntimeError(
            "MetaTrader5 package not available on this platform. "
            "Run the bot on Windows with MT5 installed."
        )


def _tf_to_mt5(tf):
    _require_mt5()
    mapping = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
    }
    return mapping.get(tf, tf)


def get_swings(symbol, timeframe, bars=200):
    _require_mt5()
    tf = _tf_to_mt5(timeframe)
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, bars)
    swings = []

    if rates is None or len(rates) == 0:
        return swings

    average_range = sum(float(rate["high"] - rate["low"]) for rate in rates) / max(1, len(rates))
    average_volume = sum(float(rate["tick_volume"]) for rate in rates) / max(1, len(rates))

    for i in range(2, len(rates) - 2):
        current = rates[i]
        high = float(current["high"])
        low = float(current["low"])
        candle_range = float(current["high"] - current["low"])
        volume = float(current["tick_volume"])
        weight = min(
            3.0,
            ((candle_range / max(average_range, 1e-9)) * 0.6)
            + ((volume / max(average_volume, 1e-9)) * 0.4),
        )
        strength = "strong" if weight >= 1.2 else "weak"

        current_time = current["time"] if "time" in current.dtype.names else None
        if high > float(rates[i - 1]["high"]) and high > float(rates[i + 1]["high"]):
            swings.append(
                {
                    "type": "high",
                    "price": high,
                    "index": i,
                    "weight": round(weight, 3),
                    "strength": strength,
                    "time": current_time,
                }
            )

        if low < float(rates[i - 1]["low"]) and low < float(rates[i + 1]["low"]):
            swings.append(
                {
                    "type": "low",
                    "price": low,
                    "index": i,
                    "weight": round(weight, 3),
                    "strength": strength,
                    "time": current_time,
                }
            )

    return swings


def analyze_structure(swings):
    highs = [s for s in swings if s["type"] == "high"]
    lows = [s for s in swings if s["type"] == "low"]
    result = {
        "trend": "range",
        "bos": False,
        "choch": False,
        "last_event": None,
    }

    if len(highs) >= 2 and len(lows) >= 2:
        higher_high = float(highs[-1]["price"]) > float(highs[-2]["price"])
        higher_low = float(lows[-1]["price"]) > float(lows[-2]["price"])
        lower_high = float(highs[-1]["price"]) < float(highs[-2]["price"])
        lower_low = float(lows[-1]["price"]) < float(lows[-2]["price"])

        if higher_high and higher_low:
            result.update({"trend": "bullish", "bos": True, "last_event": "bullish_bos"})
        elif lower_high and lower_low:
            result.update({"trend": "bearish", "bos": True, "last_event": "bearish_bos"})
        elif higher_high or higher_low:
            result.update({"trend": "bullish", "choch": True, "last_event": "bullish_choch"})
        elif lower_high or lower_low:
            result.update({"trend": "bearish", "choch": True, "last_event": "bearish_choch"})

    return result


def detect_structure(swings):
    return analyze_structure(swings)["trend"]


def get_market_trend(symbol, timeframe):
    swings = get_swings(symbol, timeframe)
    return detect_structure(swings)


def get_daily_trend(symbol):
    return get_market_trend(symbol, "D1")
