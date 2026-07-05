"""Simple TTL-based cache for _analyze_timeframe calls.

Prevents redundant MT5 fetches within a configurable time window.
This is a lightweight, thread-safe (per-call) cache — not a persistent store.
"""

import time
from typing import Any, Dict, Optional

_cache: Dict[str, Dict[str, Any]] = {}
TTL_SECONDS = 30  # Default: 30 seconds


def _make_key(symbol: str, timeframe: str, price: float) -> str:
    """Round price to 4 decimal places to avoid cache misses from tiny fluctuations."""
    try:
        rounded_price = round(float(price), 4)
    except (TypeError, ValueError):
        rounded_price = 0.0
    return f"{symbol.upper()}:{timeframe.upper()}:{rounded_price}"


def get_cached(symbol: str, timeframe: str, price: float) -> Optional[Dict[str, Any]]:
    """Return cached result if still within TTL, else None."""
    key = _make_key(symbol, timeframe, price)
    entry = _cache.get(key)
    if entry is None:
        return None
    elapsed = time.time() - entry.get("ts", 0)
    if elapsed >= TTL_SECONDS:
        del _cache[key]
        return None
    return entry.get("data")


def set_cache(symbol: str, timeframe: str, price: float, data: Dict[str, Any]) -> None:
    """Store result in cache."""
    key = _make_key(symbol, timeframe, price)
    _cache[key] = {"ts": time.time(), "data": data}


def clear_cache() -> None:
    """Clear all cached entries (e.g., on reconnect or manual reset)."""
    _cache.clear()


def configure_ttl(seconds: int) -> None:
    """Set global TTL; must be >= 5 seconds."""
    global TTL_SECONDS
    TTL_SECONDS = max(5, int(seconds))

