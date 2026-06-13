"""Silver Bullet window adapter for the same strict M1 state machine."""

import datetime as dt

from strategy.entry_model import get_lower_timeframe_entry


def detect_silver_bullet_entry(symbol, current_price, topdown, trend):
    del current_price, topdown
    now = dt.datetime.now(dt.timezone.utc)
    if not 14 <= now.hour < 15:
        return None
    direction = "buy" if str(trend).lower() in ("bullish", "buy") else "sell" if str(trend).lower() in ("bearish", "sell") else None
    if direction is None:
        return None
    return get_lower_timeframe_entry(symbol, direction, tf="M1")
