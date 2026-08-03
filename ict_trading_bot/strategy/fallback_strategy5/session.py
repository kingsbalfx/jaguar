"""
FALLBACK STRATEGY 5 — Session Schedule Manager
================================================
Handles the strict session schedule: 08:00-12:00, sleep 12:00-14:00, 14:00-20:00.
Timezone configurable via config.SESSION_TIMEZONE.
"""

from datetime import datetime, timezone, timedelta
from typing import Tuple, Optional

import pytz

from . import config


# Session state constants
SESSION_CLOSED = "closed"
SESSION_1 = "session_1"
SLEEP = "sleep"
SESSION_2 = "session_2"
SESSION_CUTOFF = "cutoff"


def _get_timezone() -> pytz.BaseTzInfo:
    """Return the configured timezone object."""
    tz_name = config.SESSION_TIMEZONE or "UTC"
    try:
        return pytz.timezone(tz_name)
    except (pytz.UnknownTimeZoneError, AttributeError):
        return pytz.UTC


def _now_in_tz(tz: Optional[pytz.BaseTzInfo] = None) -> datetime:
    """Get current time in the specified timezone."""
    if tz is None:
        tz = _get_timezone()
    return datetime.now(tz)


def get_session_timestamps() -> dict:
    """Return current timestamps in all relevant timezones for logging."""
    utc_now = datetime.now(timezone.utc)
    broker_tz = _get_timezone()
    broker_now = utc_now.astimezone(broker_tz)
    return {
        "utc": utc_now.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "broker": broker_now.strftime("%Y-%m-%d %H:%M:%S"),
        "strategy": broker_now.strftime("%Y-%m-%d %H:%M:%S"),
        "broker_tz": config.SESSION_TIMEZONE,
    }


def classify_session(dt: Optional[datetime] = None) -> str:
    """
    Determine which session we're in based on the configured timezone time.
    Returns SESSION_CLOSED, SESSION_1, SLEEP, SESSION_2, or SESSION_CUTOFF.
    """
    tz = _get_timezone()
    if dt is None:
        dt = _now_in_tz(tz)
    elif dt.tzinfo is None:
        dt = tz.localize(dt)
    else:
        dt = dt.astimezone(tz)

    hour = dt.hour
    minute = dt.minute
    total_minutes = hour * 60 + minute

    # SESSION 1: 08:00:00 through 11:59:59 (with cut-off)
    s1_start = config.SESSION_1_START_HOUR * 60
    s1_end = config.SESSION_1_END_HOUR * 60
    s1_cutoff = s1_end - config.SESSION_1_CUTOFF_MINUTES

    # SLEEP: 12:00:00 through 13:59:59
    sleep_start = config.SLEEP_START_HOUR * 60
    sleep_end = config.SLEEP_END_HOUR * 60

    # SESSION 2: 14:00:00 through 19:59:59 (with cut-off)
    s2_start = config.SESSION_2_START_HOUR * 60
    s2_end = config.SESSION_2_END_HOUR * 60
    s2_cutoff = s2_end - config.SESSION_2_CUTOFF_MINUTES

    if s1_start <= total_minutes < s1_cutoff:
        return SESSION_1
    if s1_cutoff <= total_minutes < s1_end:
        return SESSION_CUTOFF
    if sleep_start <= total_minutes < sleep_end:
        return SLEEP
    if s2_start <= total_minutes < s2_cutoff:
        return SESSION_2
    if s2_cutoff <= total_minutes < s2_end:
        return SESSION_CUTOFF
    return SESSION_CLOSED


def is_session_open(dt: Optional[datetime] = None) -> bool:
    """Check if new entries are permitted right now."""
    session = classify_session(dt)
    return session in (SESSION_1, SESSION_2)


def is_in_sleep(dt: Optional[datetime] = None) -> bool:
    """Check if we're in the mandatory sleep window."""
    return classify_session(dt) == SLEEP


def is_entry_cutoff(dt: Optional[datetime] = None) -> bool:
    """Check if we're in the entry cut-off period before session end."""
    return classify_session(dt) == SESSION_CUTOFF


def minutes_until_session_end(dt: Optional[datetime] = None) -> int:
    """Return minutes remaining in the current trading session (0 if closed)."""
    tz = _get_timezone()
    if dt is None:
        dt = _now_in_tz(tz)
    elif dt.tzinfo is None:
        dt = tz.localize(dt)
    else:
        dt = dt.astimezone(tz)

    total_minutes = dt.hour * 60 + dt.minute
    s1_end = config.SESSION_1_END_HOUR * 60
    s2_end = config.SESSION_2_END_HOUR * 60

    if config.SESSION_1_START_HOUR * 60 <= total_minutes < s1_end:
        return s1_end - total_minutes
    if config.SESSION_2_START_HOUR * 60 <= total_minutes < s2_end:
        return s2_end - total_minutes
    return 0


def current_session_name(dt: Optional[datetime] = None) -> str:
    """Human-readable session name."""
    session = classify_session(dt)
    names = {
        SESSION_1: "Session 1 (08:00-12:00)",
        SESSION_2: "Session 2 (14:00-20:00)",
        SLEEP: "Sleep (12:00-14:00)",
        SESSION_CUTOFF: "Entry Cut-off",
        SESSION_CLOSED: "Closed",
    }
    return names.get(session, "Unknown")


def next_session_open_minutes(dt: Optional[datetime] = None) -> Tuple[Optional[str], int]:
    """
    Return (next_session_name, minutes_until_open) or (None, 0) if currently open.
    """
    tz = _get_timezone()
    if dt is None:
        dt = _now_in_tz(tz)
    elif dt.tzinfo is None:
        dt = tz.localize(dt)
    else:
        dt = dt.astimezone(tz)

    total_minutes = dt.hour * 60 + dt.minute
    s1_end = config.SESSION_1_END_HOUR * 60
    s2_start = config.SESSION_2_START_HOUR * 60
    s2_end = config.SESSION_2_END_HOUR * 60
    day_end = 24 * 60

    if is_session_open(dt):
        return (None, 0)

    if total_minutes < config.SESSION_1_START_HOUR * 60:
        return ("Session 1", config.SESSION_1_START_HOUR * 60 - total_minutes)
    if total_minutes < s2_start:
        return ("Session 2", s2_start - total_minutes)
    if total_minutes < day_end:
        # Next day Session 1
        minutes_to_midnight = day_end - total_minutes
        return ("Session 1 (tomorrow)", minutes_to_midnight + config.SESSION_1_START_HOUR * 60)
    return ("Session 1 (tomorrow)", config.SESSION_1_START_HOUR * 60)


def get_day_id(dt: Optional[datetime] = None) -> str:
    """Return a day identifier string for session/day tracking."""
    tz = _get_timezone()
    if dt is None:
        dt = _now_in_tz(tz)
    elif dt.tzinfo is None:
        dt = tz.localize(dt)
    else:
        dt = dt.astimezone(tz)
    return dt.strftime("%Y-%m-%d")
