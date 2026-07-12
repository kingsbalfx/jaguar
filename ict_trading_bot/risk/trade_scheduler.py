"""Session-based trade scheduler with auto-close at session ends.

All times are in LOCAL timezone, configured via LOCAL_UTC_OFFSET env var.

Default schedule (local time):
  Session 1: 01:00 - 06:00 (trade open)
             07:00       (force close any open trades)
  Session 2: 09:20 - 12:00 (trade open)
             12:00       (force close any open trades)
  Session 3: 14:15 - 20:00 (trade open)
             21:30       (force close any open trades)
"""

import os
from datetime import datetime, timezone, timedelta
from typing import List, Tuple, Optional


def _local_utc_offset() -> int:
    """Get local timezone offset in hours from UTC."""
    raw = os.getenv("LOCAL_UTC_OFFSET", "").strip()
    if raw:
        try:
            return int(raw)
        except ValueError:
            pass
    # Auto-detect: return 0 (UTC) as fallback
    # User should set LOCAL_UTC_OFFSET in .env
    return 0


def _local_now() -> datetime:
    """Return current time in local timezone."""
    utc_now = datetime.now(timezone.utc)
    offset = _local_utc_offset()
    return utc_now + timedelta(hours=offset)


def _minutes_since_midnight(dt: Optional[datetime] = None) -> int:
    """Return minutes since midnight for a given local time."""
    now = dt if dt is not None else _local_now()
    return now.hour * 60 + now.minute


def _parse_time(time_str: str) -> int:
    """Parse 'HH:MM' string into minutes since midnight."""
    parts = time_str.strip().split(":")
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 else 0
    return hour * 60 + minute


# --- TRADING SESSIONS (Local Time) ---

TRADING_SESSIONS: List[Tuple[str, str]] = [
    ("01:00", "06:01"),   # Session 1: early morning (until 6:01 so 6:00 is included)
    ("09:20", "12:01"),   # Session 2: mid-day (until 12:01 so 12:00 is included)
    ("14:15", "20:01"),   # Session 3: afternoon-evening (until 20:01 so 20:00 is included)
]

# Force-close times (local time)
FORCE_CLOSE_TIMES: List[str] = [
    "07:00",    # After Session 1
    "12:00",    # After Session 2
    "21:30",    # After Session 3
]


def is_trading_allowed(minutes: Optional[int] = None) -> bool:
    """Check if current local time falls within any trading session."""
    if minutes is None:
        minutes = _minutes_since_midnight()
    
    for start_str, end_str in TRADING_SESSIONS:
        start = _parse_time(start_str)
        end = _parse_time(end_str)
        if start <= minutes < end:
            return True
    return False


def is_force_close_time(minutes: Optional[int] = None, tolerance: int = 5) -> bool:
    """
    Check if current local time is within tolerance of a force-close time.
    Returns True for 5 minutes before and 5 minutes after each force close time.
    """
    if minutes is None:
        minutes = _minutes_since_midnight()
    
    for close_str in FORCE_CLOSE_TIMES:
        close = _parse_time(close_str)
        if abs(minutes - close) <= tolerance:
            return True
    return False


def should_close_positions_now(minutes: Optional[int] = None) -> bool:
    """
    Check if we're at a force-close threshold.
    Returns True if within the close window (5 min before to 1 min after).
    """
    if minutes is None:
        minutes = _minutes_since_midnight()
    
    for close_str in FORCE_CLOSE_TIMES:
        close = _parse_time(close_str)
        # Close window: 5 minutes before to 1 minute after the exact time
        if close - 5 <= minutes <= close + 1:
            return True
    return False


def next_force_close_time(minutes: Optional[int] = None) -> Optional[int]:
    """Return minutes until next force close, or None if none remaining today."""
    if minutes is None:
        minutes = _minutes_since_midnight()
    
    for close_str in FORCE_CLOSE_TIMES:
        close = _parse_time(close_str)
        if minutes < close:
            return close - minutes
    return None


def next_session_start(minutes: Optional[int] = None) -> Optional[int]:
    """Return minutes until next trading session starts, or None if none today."""
    if minutes is None:
        minutes = _minutes_since_midnight()
    
    for start_str, _ in TRADING_SESSIONS:
        start = _parse_time(start_str)
        if minutes < start:
            return start - minutes
    return None


def current_session_name(minutes: Optional[int] = None) -> str:
    """Return name of current trading session, or 'closed'."""
    if minutes is None:
        minutes = _minutes_since_midnight()
    
    for idx, (start_str, end_str) in enumerate(TRADING_SESSIONS, 1):
        start = _parse_time(start_str)
        end = _parse_time(end_str)
        if start <= minutes < end:
            return f"session_{idx}"
    return "closed"


def force_close_reason(minutes: Optional[int] = None) -> Optional[str]:
    """Return the reason if we should force close, else None."""
    if minutes is None:
        minutes = _minutes_since_midnight()
    
    for close_str in FORCE_CLOSE_TIMES:
        close = _parse_time(close_str)
        if close - 5 <= minutes <= close + 1:
            return f"session_end_force_close_at_{close_str}"
    return None
