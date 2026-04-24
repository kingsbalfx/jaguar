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


def score_liquidity_confidence(price, liquidity, direction, recent_candles=None):
    """
    Soft liquidity scoring instead of hard rejection:
    Returns confidence score 0-100 based on liquidity quality
    """

    if not isinstance(liquidity, dict):
        return 0.0

    score = 100.0

    session_dt = None
    if isinstance(recent_candles, list) and recent_candles:
        session_dt = recent_candles[-1].get("time")

    # Session penalty instead of hard block
    if not intelligence_session_open(session_dt):
        score -= 30.0

    tolerance = float(os.getenv("LIQUIDITY_TOLERANCE_RATIO", "0.0015"))
    direction = str(direction or "").lower()
    displacement = _displacement_score(recent_candles or [], direction)

    # Displacement gradient instead of hard cutoff
    if displacement >= 0.75:
        pass  # Full score
    elif displacement >= 0.65:
        score -= 10.0
    elif displacement >= 0.55:
        score -= 25.0
    else:
        score -= 50.0

    # Sweep confirmation penalty
    if not confirm_liquidity_sweep(price, liquidity, direction, tolerance=tolerance):
        score -= 40.0

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
        score -= 50.0  # No active zone penalty
    else:
        # Zone validation bonus/penalty
        zone_valid = validate_liquidity_zone(active_zone, recent_candles or [], direction)
        if zone_valid:
            active_zone["session_checked"] = session_name(session_dt)
            active_zone["sweep_confirmed"] = True
        else:
            score -= 20.0

    return max(0.0, score)


def liquidity_taken(price, liquidity, direction, recent_candles=None):
    """
    Legacy function - now uses scoring internally
    """
    confidence = score_liquidity_confidence(price, liquidity, direction, recent_candles)
    return confidence >= 60.0  # Maintain backward compatibility with relaxed threshold
