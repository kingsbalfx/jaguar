"""
FALLBACK STRATEGY 3 - Technical Indicators
===========================================
Pure-function MACD, SMA, EMA, ATR calculations operating on candle data.
All functions use only completed (closed) candles — no repainting.
"""

from typing import List, Optional, Tuple, Callable

from . import config


def _to_floats(candles: List[dict], field: str) -> List[float]:
    """Extract a numeric field from candle dicts."""
    return [float(c[field]) for c in candles if isinstance(c, dict) and field in c]


def _to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ============================================================
# Simple Moving Average (SMA)
# ============================================================
def sma(candles: List[dict], period: int, field: str = "close") -> float:
    """
    Calculate SMA over the last `period` closed candles.
    Returns 0.0 if insufficient data.
    """
    values = _to_floats(candles[-period:], field)
    if len(values) < period:
        return 0.0
    return sum(values) / period


def sma_values(candles: List[dict], period: int, field: str = "close") -> List[float]:
    """
    Calculate SMA for every valid position in the candle list.
    Returns list of SMA values with the same length as candles (0-padded at front).
    """
    result: List[float] = []
    for i in range(len(candles)):
        if i < period - 1:
            result.append(0.0)
        else:
            window = _to_floats(candles[i - period + 1 : i + 1], field)
            result.append(sum(window) / period if len(window) == period else 0.0)
    return result


# ============================================================
# Exponential Moving Average (EMA)
# ============================================================
def ema(candles: List[dict], period: int, field: str = "close") -> float:
    """
    Calculate the current EMA value over closed candles.
    Uses SMA seed followed by recursive EMA.
    Returns 0.0 if insufficient data.
    """
    values = _to_floats(candles, field)
    if len(values) < period:
        return 0.0

    # Seed with SMA
    seed = sum(values[:period]) / period
    if len(values) == period:
        return seed

    multiplier = 2.0 / (period + 1)
    current_ema = seed
    for value in values[period:]:
        current_ema = (value - current_ema) * multiplier + current_ema
    return current_ema


def ema_values(candles: List[dict], period: int, field: str = "close") -> List[float]:
    """
    Calculate EMA for every position in the candle list.
    Returns list of EMA values (0-padded at front).
    """
    values = _to_floats(candles, field)
    result: List[float] = [0.0] * len(values)

    if len(values) < period:
        return result

    # Seed with SMA
    seed = sum(values[:period]) / period
    result[period - 1] = seed

    multiplier = 2.0 / (period + 1)
    for i in range(period, len(values)):
        result[i] = (values[i] - result[i - 1]) * multiplier + result[i - 1]

    return result


# ============================================================
# MACD
# ============================================================
def macd(
    candles: List[dict],
    fast_period: int = None,
    slow_period: int = None,
    signal_period: int = None,
) -> Tuple[float, float, float]:
    """
    Calculate MACD line, signal line, and histogram for the most recent closed candle.
    
    Returns:
        (macd_line, signal_line, histogram)
        All 0.0 if insufficient data.
    """
    fast = fast_period if fast_period is not None else config.MACD_FAST
    slow = slow_period if slow_period is not None else config.MACD_SLOW
    signal = signal_period if signal_period is not None else config.MACD_SIGNAL

    if len(candles) < slow + signal:
        return 0.0, 0.0, 0.0

    fast_ema = ema(candles, fast)
    slow_ema = ema(candles, slow)
    macd_line = fast_ema - slow_ema

    # Need enough data for signal line EMA
    # Build MACD line series
    values = _to_floats(candles, "close")
    fast_emas = ema_values(candles, fast)
    slow_emas = ema_values(candles, slow)

    macd_values: List[float] = []
    for i in range(len(values)):
        if fast_emas[i] != 0.0 and slow_emas[i] != 0.0:
            macd_values.append(fast_emas[i] - slow_emas[i])
        else:
            macd_values.append(0.0)

    # Compute signal line as EMA of MACD line
    valid_macd = [v for v in macd_values if v != 0.0]
    if len(valid_macd) < signal:
        return macd_line, 0.0, 0.0

    signal_seed = sum(valid_macd[:signal]) / signal
    if len(valid_macd) == signal:
        signal_line = signal_seed
    else:
        multiplier = 2.0 / (signal + 1)
        current_signal = signal_seed
        for mv in valid_macd[signal:]:
            current_signal = (mv - current_signal) * multiplier + current_signal
        signal_line = current_signal

    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def macd_series(candles: List[dict], fast_period: int = None, slow_period: int = None, signal_period: int = None):
    """
    Calculate complete MACD series over all candles.
    Returns lists of (macd_line, signal_line, histogram) tuples.
    """
    fast = fast_period if fast_period is not None else config.MACD_FAST
    slow = slow_period if slow_period is not None else config.MACD_SLOW
    signal = signal_period if signal_period is not None else config.MACD_SIGNAL

    values = _to_floats(candles, "close")
    if len(values) < slow + signal:
        return [], [], []

    fast_emas = ema_values(candles, fast)
    slow_emas = ema_values(candles, slow)

    macd_values: List[float] = []
    for i in range(len(values)):
        if fast_emas[i] != 0.0 and slow_emas[i] != 0.0:
            macd_values.append(fast_emas[i] - slow_emas[i])
        else:
            macd_values.append(0.0)

    # Signal line as EMA of MACD values
    signal_values: List[float] = [0.0] * len(macd_values)
    valid_macd = [v for v in macd_values if v != 0.0]
    if len(valid_macd) >= signal:
        signal_seed = sum(valid_macd[:signal]) / signal
        signal_values[fast - 1] = signal_seed  # approximate start index
        multiplier = 2.0 / (signal + 1)
        current_signal = signal_seed
        si = 0
        for i in range(len(macd_values)):
            if macd_values[i] != 0.0:
                if si >= signal:
                    current_signal = (macd_values[i] - current_signal) * multiplier + current_signal
                signal_values[i] = current_signal
                si += 1

    histograms = [macd_values[i] - signal_values[i] if macd_values[i] != 0.0 else 0.0 for i in range(len(macd_values))]
    return macd_values, signal_values, histograms


# ============================================================
# ATR (Average True Range)
# ============================================================
def atr(candles: List[dict], period: int = 14) -> float:
    """
    Calculate ATR over the last N closed candles.
    """
    if len(candles) < period + 1:
        return 0.0

    true_ranges: List[float] = []
    prev_close: Optional[float] = None

    for candle in candles[-(period + 1):]:
        high = _to_float(candle.get("high"))
        low = _to_float(candle.get("low"))
        close = _to_float(candle.get("close"))

        if prev_close is None:
            tr = high - low
        else:
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)
        prev_close = close

    if not true_ranges:
        return 0.0

    # First ATR is SMA of true ranges, then recursive
    seed = sum(true_ranges[:period]) / period
    if len(true_ranges) <= period:
        return seed

    current_atr = seed
    multiplier = 1.0 / period
    for tr in true_ranges[period:]:
        current_atr = (tr - current_atr) * multiplier + current_atr
    return current_atr


# ============================================================
# Candle analysis helpers
# ============================================================
def candle_direction(candle: dict) -> Optional[str]:
    """Return 'bullish', 'bearish', or None."""
    open_p = _to_float(candle.get("open"))
    close_p = _to_float(candle.get("close"))
    if close_p > open_p:
        return "bullish"
    if close_p < open_p:
        return "bearish"
    return None


def candle_range(candle: dict) -> float:
    return _to_float(candle.get("high")) - _to_float(candle.get("low"))


def candle_body(candle: dict) -> float:
    return abs(_to_float(candle.get("close")) - _to_float(candle.get("open")))


def candle_body_ratio(candle: dict) -> float:
    r = candle_range(candle)
    return candle_body(candle) / r if r > 0 else 0.0


def candle_upper_wick(candle: dict) -> float:
    high = _to_float(candle.get("high"))
    open_p = _to_float(candle.get("open"))
    close_p = _to_float(candle.get("close"))
    return high - max(open_p, close_p)


def candle_lower_wick(candle: dict) -> float:
    low = _to_float(candle.get("low"))
    open_p = _to_float(candle.get("open"))
    close_p = _to_float(candle.get("close"))
    return min(open_p, close_p) - low


def find_swing_points(candles: List[dict], lookback: int = 2) -> List[dict]:
    """
    Identify swing highs and lows from candlestick data.
    Returns list of dicts with keys: type, price, index, time.
    """
    swings: List[dict] = []
    if len(candles) < lookback * 2 + 1:
        return swings

    for i in range(lookback, len(candles) - lookback):
        left = candles[i - lookback : i]
        right = candles[i + 1 : i + 1 + lookback]
        current = candles[i]

        high = _to_float(current.get("high"))
        low = _to_float(current.get("low"))

        # Swing high
        if all(high > _to_float(c.get("high")) for c in left + right):
            swings.append({
                "type": "high",
                "price": high,
                "index": i,
                "time": current.get("time"),
            })

        # Swing low
        if all(low < _to_float(c.get("low")) for c in left + right):
            swings.append({
                "type": "low",
                "price": low,
                "index": i,
                "time": current.get("time"),
            })

    return swings
