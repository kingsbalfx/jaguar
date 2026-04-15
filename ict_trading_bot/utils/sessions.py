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
    if isinstance(dt, (numbers.Integral, numbers.Real)):
        return datetime.fromtimestamp(float(dt), tz=UTC)
    if hasattr(dt, "astype"):
        try:
            # Handle numpy datetime64 and similar timestamp-like scalars
            return datetime.fromtimestamp(float(dt), tz=UTC)
        except Exception:
            pass
    if dt.tzinfo is None:
        return UTC.localize(dt)
    return dt.astimezone(UTC)


def _hour(dt=None):
    return _coerce_utc(dt).hour


def in_london_session(dt=None):
    hour = _hour(dt)
    return 7 <= hour < 12


def in_newyork_session(dt=None):
    hour = _hour(dt)
    return 12 <= hour < 17


def in_asia_session(dt=None):
    hour = _hour(dt)
    return hour >= 22 or hour < 6


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
