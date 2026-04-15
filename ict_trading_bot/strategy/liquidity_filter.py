import os

from ict_concepts.liquidity import confirm_liquidity_sweep
from ict_concepts.liquidity_analysis import validate_liquidity_zone
from utils.sessions import intelligence_session_open, session_name


def _volume_value(candle):
    return float(candle.get("volume", candle.get("tick_volume", 0.0)) or 0.0)


def _displacement_score(recent_candles, direction):
    if not isinstance(recent_candles, list) or len(recent_candles) < 2:
        return 0.0

    current = recent_candles[-1]
    previous = recent_candles[-2]
    if not all(key in current and key in previous for key in ("open", "high", "low", "close")):
        return 0.0

    body = abs(float(current["close"]) - float(current["open"]))
    candle_range = max(float(current["high"]) - float(current["low"]), 1e-9)
    body_ratio = body / candle_range

    if str(direction or "").lower() == "buy" and float(current["close"]) <= float(previous["high"]):
        return 0.0
    if str(direction or "").lower() == "sell" and float(current["close"]) >= float(previous["low"]):
        return 0.0

    return round(body_ratio, 3)


def liquidity_taken(price, liquidity, direction, recent_candles=None):
    """
    Strict liquidity confirmation:
    1. Session must be inside the execution window.
    2. A true EQH/EQL sweep must occur.
    3. The sweep must show displacement and multi-candle participation.
    """

    if not isinstance(liquidity, dict):
        return False

    session_dt = None
    if isinstance(recent_candles, list) and recent_candles:
        session_dt = recent_candles[-1].get("time")

    if not intelligence_session_open(session_dt):
        return False

    tolerance = float(os.getenv("LIQUIDITY_TOLERANCE_RATIO", "0.0015"))
    direction = str(direction or "").lower()
    displacement = _displacement_score(recent_candles or [], direction)
    if displacement < 0.70:
        return False

    if not confirm_liquidity_sweep(price, liquidity, direction, tolerance=tolerance):
        return False

    zones = liquidity.get("EQL", []) if direction == "buy" else liquidity.get("EQH", [])
    active_zone = None
    for zone in zones:
        if not isinstance(zone, dict):
            continue
        prices = zone.get("prices") or ()
        if len(prices) < 2:
            continue
        low = float(min(prices))
        high = float(max(prices))
        if direction == "buy" and price <= high * (1 + tolerance):
            active_zone = zone
            break
        if direction == "sell" and price >= low * (1 - tolerance):
            active_zone = zone
            break

    if active_zone is None:
        return False

    active_zone["session_checked"] = session_name(session_dt)
    active_zone["sweep_confirmed"] = True
    return validate_liquidity_zone(active_zone, recent_candles or [], direction)
