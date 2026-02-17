try:
    import MetaTrader5 as mt5
except Exception:
    mt5 = None
import pandas as pd


def _require_mt5():
    if mt5 is None:
        raise RuntimeError(
            "MetaTrader5 package not available on this platform. "
            "Run the bot on Windows with MT5 installed."
        )


def _tf_to_mt5(tf):
    _require_mt5()
    mapping = {
        'M1': mt5.TIMEFRAME_M1,
        'M5': mt5.TIMEFRAME_M5,
        'M15': mt5.TIMEFRAME_M15,
        'M30': mt5.TIMEFRAME_M30,
        'H1': mt5.TIMEFRAME_H1,
        'H4': mt5.TIMEFRAME_H4,
        'D1': mt5.TIMEFRAME_D1,
    }
    return mapping.get(tf, tf)


def get_swings(symbol, timeframe, bars=200):
    _require_mt5()
    tf = _tf_to_mt5(timeframe)
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, bars)
    swings = []

    if rates is None or len(rates) == 0:
        return swings

    for i in range(2, len(rates) - 2):
        high = rates[i]['high']
        low = rates[i]['low']

        if high > rates[i-1]['high'] and high > rates[i+1]['high']:
            swings.append({"type": "high", "price": high, "index": i})

        if low < rates[i-1]['low'] and low < rates[i+1]['low']:
            swings.append({"type": "low", "price": low, "index": i})

    return swings


def detect_structure(swings):
    highs = [s for s in swings if s["type"] == "high"]
    lows = [s for s in swings if s["type"] == "low"]

    if len(highs) < 2 or len(lows) < 2:
        return None

    if highs[-1]["price"] > highs[-2]["price"] and lows[-1]["price"] > lows[-2]["price"]:
        return "bullish"

    if highs[-1]["price"] < highs[-2]["price"] and lows[-1]["price"] < lows[-2]["price"]:
        return "bearish"

    return "range"


def get_market_trend(symbol, timeframe):
    swings = get_swings(symbol, timeframe)
    return detect_structure(swings)


def get_daily_trend(symbol):
    return get_market_trend(symbol, 'D1')
