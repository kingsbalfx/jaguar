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


def fib_dealing_range(high, low):
    high = float(high)
    low = float(low)
    if high < low:
        high, low = low, high
    spread = high - low
    return {
        "0.0": low,
        "0.21": low + 0.21 * spread,
        "0.25": low + 0.25 * spread,
        "0.382": low + 0.382 * spread,
        "0.5": low + 0.5 * spread,
        "0.62": low + 0.62 * spread,
        "0.705": low + 0.705 * spread,
        "0.79": low + 0.79 * spread,
        "0.75": low + 0.75 * spread,
        "1.0": high,
        "range": spread,
    }


def in_discount(price, fib):
    return fib["0.0"] <= price <= fib["0.5"]


def in_premium(price, fib):
    return fib["0.5"] <= price <= fib["1.0"]


def discount_zone(fib):
    return float(fib["0.0"]), float(fib["0.5"])


def premium_zone(fib):
    return float(fib["0.5"]), float(fib["1.0"])


def ote_zone(fib, direction):
    """Return the directional 62%-79% optimal-trade-entry retracement."""
    low = float(fib["0.0"])
    high = float(fib["1.0"])
    spread = high - low
    if str(direction or "").lower() in ("buy", "bullish", "long"):
        return high - (spread * 0.79), high - (spread * 0.62)
    return low + (spread * 0.62), low + (spread * 0.79)


def price_zone(price, fib):
    price = float(price)
    if in_discount(price, fib):
        return "discount"
    if in_premium(price, fib):
        return "premium"
    return "outside"


def calculate_fib_levels(symbol, timeframe, bars=200):
    """Fetch recent bars for symbol/timeframe and return fib levels dict."""
    _require_mt5()
    tf = _tf_to_mt5(timeframe)
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, bars)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"No rates for {symbol} {timeframe}")

    df = pd.DataFrame(rates)
    high = df['high'].max()
    low = df['low'].min()

    return fib_dealing_range(high, low)


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
