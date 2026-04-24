from utils.sessions import session_name


def _swing_price(swing):
    return float(swing["price"])


def _swing_session(swing, fallback_session=None):
    if not isinstance(swing, dict):
        return fallback_session or "unknown"
    if swing.get("session"):
        return swing["session"]
    if swing.get("time") is not None:
        return session_name(swing["time"])
    return fallback_session or "unknown"


def _zone_record(a, b, fallback_session=None):
    sessions = sorted(
        {
            _swing_session(a, fallback_session),
            _swing_session(b, fallback_session),
        }
    )
    prices = sorted([_swing_price(a), _swing_price(b)])
    return {
        "type": a["type"],
        "level": round(sum(prices) / len(prices), 6),
        "prices": tuple(prices),
        "touches": 2,
        "indices": [a.get("index"), b.get("index")],
        "sessions": sessions,
        "session": sessions[0] if len(sessions) == 1 else "mixed",
        "sweep_confirmed": False,
    }


def detect_liquidity_zones(swings, tolerance=0.0003, session=None):
    """
    swings: list of swing highs/lows
    Returns EQH / EQL zones with session metadata and sweep tracking flags.
    """

    eqh = []
    eql = []
    if not isinstance(swings, list):
        return {"EQH": eqh, "EQL": eql, "session": session}

    for i in range(len(swings) - 1):
        a = swings[i]
        b = swings[i + 1]
        if not isinstance(a, dict) or not isinstance(b, dict):
            continue
        if a.get("type") != b.get("type"):
            continue

        if abs(_swing_price(a) - _swing_price(b)) <= tolerance:
            zone = _zone_record(a, b, fallback_session=session)
            if a["type"] == "high":
                eqh.append(zone)
            else:
                eql.append(zone)

    return {
        "EQH": eqh,
        "EQL": eql,
        "session": session,
    }


def confirm_liquidity_sweep(price, liquidity, direction, tolerance=0.0015):
    if not isinstance(liquidity, dict):
        return False

    direction = str(direction or "").lower()
    if direction == "buy":
        for low_zone in liquidity.get("EQL", []):
            prices = low_zone.get("prices") if isinstance(low_zone, dict) else low_zone
            level = float(prices[0])
            if price < level * (1 - tolerance):   # must break clearly
                if isinstance(low_zone, dict):
                    low_zone["sweep_confirmed"] = True
                return True
    elif direction == "sell":
        for high_zone in liquidity.get("EQH", []):
            prices = high_zone.get("prices") if isinstance(high_zone, dict) else high_zone
            level = float(prices[-1])
            if price > level * (1 + tolerance):
                if isinstance(high_zone, dict):
                    high_zone["sweep_confirmed"] = True
                return True

    return False
