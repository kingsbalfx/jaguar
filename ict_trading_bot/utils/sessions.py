from datetime import datetime
import os
import numbers

import pytz


UTC = pytz.UTC


def _utc_now():
    return datetime.now(UTC)


def _coerce_utc(dt=None):
    if dt is None:
        return _utc_now()

    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            return UTC.localize(dt)
        return dt.astimezone(UTC)

    # Numeric epochs (MT5 / numpy scalars). Handle ms/us/ns automatically.
    if isinstance(dt, numbers.Number) and not isinstance(dt, bool):
        try:
            ts = float(dt)
            abs_ts = abs(ts)
            if abs_ts >= 1e18:  # ns
                ts /= 1e9
            elif abs_ts >= 1e15:  # us
                ts /= 1e6
            elif abs_ts >= 1e12:  # ms
                ts /= 1e3
            return datetime.fromtimestamp(ts, tz=UTC)
        except Exception:
            return _utc_now()

    # numpy.datetime64 and timestamp-like scalars
    if hasattr(dt, "to_pydatetime"):
        try:
            return _coerce_utc(dt.to_pydatetime())
        except Exception:
            pass

    if hasattr(dt, "astype"):
        try:
            dtype = str(getattr(dt, "dtype", ""))
            if "datetime64" in dtype:
                # convert to epoch seconds
                ts = float(dt.astype("datetime64[ns]").astype("int64")) / 1e9
                return datetime.fromtimestamp(ts, tz=UTC)
        except Exception:
            pass

    # Last-chance: attempt float coercion, otherwise fall back to "now" to avoid crashing the bot loop.
    try:
        return datetime.fromtimestamp(float(dt), tz=UTC)
    except Exception:
        return _utc_now()


def _hour(dt=None):
    return _coerce_utc(dt).hour


def in_london_session(dt=None):
    """STRICT London Kill Zone: 07:00-10:00 UTC (3-hour window)"""
    hour = _hour(dt)
    return 7 <= hour < 10  # Strict Kill Zone only


def in_newyork_session(dt=None):
    """STRICT New York Kill Zone: 12:00-15:00 UTC (3-hour window)"""
    hour = _hour(dt)
    return 12 <= hour < 15  # Strict Kill Zone only


def in_asia_session(dt=None):
    """Asia session for reference only - NOT primary trading window"""
    hour = _hour(dt)
    return hour >= 22 or hour < 7


def session_name(dt=None):
    if in_london_session(dt):
        return "london"
    if in_newyork_session(dt):
        return "newyork"
    if in_asia_session(dt):
        return "asia"
    return "off_session"


def trading_session_open(dt=None):
    return in_asia_session(dt) or in_london_session(dt) or in_newyork_session(dt)


def intelligence_session_open(dt=None):
    if os.getenv("TRADE_ALL_SESSIONS", "false").lower() in ("1", "true", "yes"):
        return trading_session_open(dt)
    return in_london_session(dt) or in_newyork_session(dt)


def asset_trading_open(asset_class: str, dt=None) -> bool:
    """
    Trading-days awareness:
    - crypto: 7/7
    - forex/metals/other: 5/7 (weekend closed, plus Friday late close / Sunday late open)

    Uses UTC for consistency with broker/server feeds.
    """
    asset = str(asset_class or "").lower().strip()
    if asset == "crypto":
        return True

    now = _coerce_utc(dt)
    weekday = now.weekday()  # Mon=0 .. Sun=6
    hour = now.hour

    # Weekend closed for 5/7 markets.
    if weekday == 5:  # Saturday
        return False
    if weekday == 6 and hour < 22:  # Sunday before open
        return False
    if weekday == 4 and hour >= 22:  # Friday after close
        return False

    return True
