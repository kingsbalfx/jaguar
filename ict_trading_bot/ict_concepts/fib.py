import MetaTrader5 as mt5
import pandas as pd


def fib_dealing_range(high, low):
    return {
        "0.0": low,
        "0.25": low + 0.25 * (high - low),
        "0.5": low + 0.5 * (high - low),
        "0.75": low + 0.75 * (high - low),
        "1.0": high,
    }


def in_discount(price, fib):
    return fib["0.0"] <= price <= fib["0.25"]


def in_premium(price, fib):
    return fib["0.75"] <= price <= fib["1.0"]


def calculate_fib_levels(symbol, timeframe, bars=200):
    """Fetch recent bars for symbol/timeframe and return fib levels dict."""
    tf = _tf_to_mt5(timeframe)
    rates = mt5.copy_rates_from_pos(symbol, tf, 0, bars)
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"No rates for {symbol} {timeframe}")

    df = pd.DataFrame(rates)
    high = df['high'].max()
    low = df['low'].min()

    return fib_dealing_range(high, low)


def _tf_to_mt5(tf):
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
