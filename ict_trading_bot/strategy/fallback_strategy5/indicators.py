"""
FALLBACK STRATEGY 5 — Technical Indicators
============================================
Pure-function calculations. Re-exports from Fallback 3's indicators where possible
and adds Fallback 5-specific calculations (ADX, etc).
"""

from typing import List, Optional, Tuple

from strategy.fallback_strategy3.indicators import (
    sma, sma_values, ema, ema_values,
    macd, macd_series,
    atr,
    candle_direction, candle_range, candle_body, candle_body_ratio,
    candle_upper_wick, candle_lower_wick,
    find_swing_points,
    _to_float as _to_float_base,
)

# Re-export
__all__ = [
    "sma", "sma_values", "ema", "ema_values",
    "macd", "macd_series",
    "atr",
    "candle_direction", "candle_range", "candle_body", "candle_body_ratio",
    "candle_upper_wick", "candle_lower_wick",
    "find_swing_points",
    "adx", "adx_values",
    "ema_slope", "ema_alignment",
    "true_range",
    "_to_float",
]


def _to_float(value, default=0.0) -> float:
    return _to_float_base(value, default)


def true_range(candle: dict, prev_candle: Optional[dict] = None) -> float:
    """Calculate the true range for a single candle."""
    high = _to_float(candle.get("high"))
    low = _to_float(candle.get("low"))
    close = _to_float(candle.get("close"))

    if prev_candle is None:
        return high - low

    prev_close = _to_float(prev_candle.get("close"))
    return max(
        high - low,
        abs(high - prev_close),
        abs(low - prev_close),
    )


def adx(candles: List[dict], period: int = 14) -> float:
    """
    Calculate ADX (Average Directional Index).
    Returns 0.0 if insufficient data.
    """
    if not candles or len(candles) < period + 1:
        return 0.0

    # Calculate +DM and -DM
    plus_dm: List[float] = []
    minus_dm: List[float] = []
    tr_values: List[float] = []

    for i in range(1, len(candles)):
        high = _to_float(candles[i].get("high"))
        low = _to_float(candles[i].get("low"))
        prev_high = _to_float(candles[i - 1].get("high"))
        prev_low = _to_float(candles[i - 1].get("low"))
        prev_close = _to_float(candles[i - 1].get("close"))

        up_move = high - prev_high
        down_move = prev_low - low

        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        tr_values.append(tr)

        if up_move > down_move and up_move > 0:
            plus_dm.append(up_move)
        else:
            plus_dm.append(0.0)

        if down_move > up_move and down_move > 0:
            minus_dm.append(down_move)
        else:
            minus_dm.append(0.0)

    if len(tr_values) < period:
        return 0.0

    # Smooth using Wilder's method (SMA first, then recursive)
    tr_period = tr_values[:period]
    tr_smooth = [sum(tr_period) / period]

    plus_dm_period = plus_dm[:period]
    plus_dm_smooth = [sum(plus_dm_period) / period]

    minus_dm_period = minus_dm[:period]
    minus_dm_smooth = [sum(minus_dm_period) / period]

    for i in range(period, len(tr_values)):
        tr_smooth.append(
            (tr_smooth[-1] * (period - 1) + tr_values[i]) / period
        )
        plus_dm_smooth.append(
            (plus_dm_smooth[-1] * (period - 1) + plus_dm[i]) / period
        )
        minus_dm_smooth.append(
            (minus_dm_smooth[-1] * (period - 1) + minus_dm[i]) / period
        )

    # Calculate +DI and -DI
    di_periods = []
    for i in range(len(tr_smooth)):
        if tr_smooth[i] > 0:
            pdi = (plus_dm_smooth[i] / tr_smooth[i]) * 100.0
            ndi = (minus_dm_smooth[i] / tr_smooth[i]) * 100.0
        else:
            pdi = 0.0
            ndi = 0.0
        dx = abs(pdi - ndi) / (pdi + ndi) * 100.0 if (pdi + ndi) > 0 else 0.0
        di_periods.append(dx)

    # ADX is smoothed DX
    if len(di_periods) < period:
        return 0.0

    adx_value = sum(di_periods[:period]) / period
    return round(adx_value, 1)


def adx_values(candles: List[dict], period: int = 14) -> List[float]:
    """
    Calculate ADX for every position in the candle list.
    Returns list of ADX values (0.0-padded at front).
    """
    if not candles or len(candles) < period + 1:
        return [0.0] * len(candles) if candles else []

    result: List[float] = []
    for i in range(period + 1, len(candles) + 1):
        result.append(adx(candles[:i], period))
    return [0.0] * (period + 1) + result


def ema_slope(ema_values_list: List[float], window: int = 5) -> float:
    """Calculate the slope of an EMA series over the last `window` values."""
    if len(ema_values_list) < window:
        return 0.0
    relevant = ema_values_list[-window:]
    n = len(relevant)
    x_mean = (n - 1) / 2.0
    y_mean = sum(relevant) / n
    numerator = sum((i - x_mean) * (relevant[i] - y_mean) for i in range(n))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    return numerator / denominator if denominator != 0 else 0.0


def ema_alignment(
    fast_values: List[float],
    mid_values: List[float],
    slow_values: List[float],
) -> str:
    """
    Classify EMA alignment:
    - "bullish": fast > mid > slow
    - "bearish": fast < mid < slow
    - "tangled": anything else
    """
    if not fast_values or not mid_values or not slow_values:
        return "tangled"

    fast = fast_values[-1]
    mid = mid_values[-1]
    slow = slow_values[-1]

    if fast > mid > slow:
        return "bullish"
    if fast < mid < slow:
        return "bearish"
    return "tangled"


def estimate_point(price: float) -> float:
    """Estimate point/tick size from price magnitude."""
    if price <= 0:
        return 0.0001
    if price < 1:
        return 0.0001
    if price < 100:
        return 0.001
    return 0.01


def signal_to_direction(signal: str) -> str:
    """Normalize signal strings to 'buy'/'sell'."""
    s = str(signal).lower().strip()
    if s in ("buy", "bullish", "long"):
        return "buy"
    if s in ("sell", "bearish", "short"):
        return "sell"
    return ""
