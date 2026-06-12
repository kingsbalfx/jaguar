"""Strict liquidity-sweep validation used by top-down analysis."""

import os

from ict_concepts.liquidity import confirm_liquidity_sweep
from ict_concepts.liquidity_analysis import validate_liquidity_zone
from utils.sessions import intelligence_session_open, session_name


def _has_displacement(recent_candles, direction):
    if not isinstance(recent_candles, list) or len(recent_candles) < 2:
        return False
    current = recent_candles[-1]
    previous = recent_candles[-2]
    if not all(key in current and key in previous for key in ("open", "high", "low", "close")):
        return False
    body = abs(float(current["close"]) - float(current["open"]))
    candle_range = max(float(current["high"]) - float(current["low"]), 1e-9)
    if body / candle_range < 0.6:
        return False
    if str(direction or "").lower() == "buy":
        return float(current["close"]) > float(previous["high"])
    return float(current["close"]) < float(previous["low"])


def liquidity_taken(price, liquidity, direction, recent_candles=None):
    """Require session, sweep, valid zone, and displacement; otherwise reject."""
    if not isinstance(liquidity, dict) or not intelligence_session_open(
        (recent_candles or [{}])[-1].get("time")
    ):
        return False
    tolerance = float(os.getenv("LIQUIDITY_TOLERANCE_RATIO", "0.0015"))
    if not confirm_liquidity_sweep(price, liquidity, direction, tolerance=tolerance):
        return False
    if not _has_displacement(recent_candles or [], direction):
        return False

    zones = liquidity.get("EQL", []) if str(direction).lower() == "buy" else liquidity.get("EQH", [])
    for zone in zones:
        if isinstance(zone, dict) and validate_liquidity_zone(zone, recent_candles or [], direction):
            zone["session_checked"] = session_name((recent_candles or [{}])[-1].get("time"))
            zone["sweep_confirmed"] = True
            return True
    return False
