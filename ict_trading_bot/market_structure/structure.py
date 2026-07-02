"""Reusable ICT market-structure engine.

This module is intentionally data-only: it accepts already-built swings and
returns structure events. MT5 fetching stays in `ict_concepts.market_structure`.
"""


def _to_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_swings(swings):
    normalized = []
    for raw in swings or []:
        if isinstance(raw, dict):
            swing_type = str(raw.get("type") or "").lower()
            price = raw.get("price")
            index = raw.get("index", len(normalized))
            swing_time = raw.get("time")
        elif isinstance(raw, (list, tuple)) and len(raw) >= 3:
            swing_type = str(raw[0] or "").lower()
            index = raw[1]
            price = raw[2]
            swing_time = raw[3] if len(raw) > 3 else None
        else:
            continue

        if swing_type not in ("high", "low"):
            continue
        normalized.append(
            {
                "type": swing_type,
                "price": _to_float(price),
                "index": _to_int(index, len(normalized)),
                "time": swing_time,
            }
        )
    normalized.sort(key=lambda item: (int(item["index"]), 0 if item["type"] == "low" else 1))
    return normalized


def _dedupe_consecutive_same_type(swings):
    deduped = []
    for swing in swings:
        if not deduped or deduped[-1]["type"] != swing["type"]:
            deduped.append(dict(swing))
            continue
        previous = deduped[-1]
        if swing["type"] == "high" and float(swing["price"]) >= float(previous["price"]):
            deduped[-1] = dict(swing)
        elif swing["type"] == "low" and float(swing["price"]) <= float(previous["price"]):
            deduped[-1] = dict(swing)
    return deduped


def _classify_trend(highs, lows):
    if len(highs) < 2 or len(lows) < 2:
        return "range"
    higher_high = float(highs[-1]["price"]) > float(highs[-2]["price"])
    higher_low = float(lows[-1]["price"]) > float(lows[-2]["price"])
    lower_high = float(highs[-1]["price"]) < float(highs[-2]["price"])
    lower_low = float(lows[-1]["price"]) < float(lows[-2]["price"])
    if higher_high and higher_low:
        return "bullish"
    if lower_high and lower_low:
        return "bearish"
    return "range"


def _event(event, direction, swing, previous, label, prior_trend, timeframe=None):
    is_shift = event in ("CHOCH", "MSS")
    return {
        "event": event,
        "label": label,
        "direction": direction,
        "price": float(swing["price"]),
        "previous_price": float(previous["price"]) if previous else None,
        "index": int(swing["index"]),
        "time": swing.get("time"),
        "timeframe": timeframe,
        "prior_trend": prior_trend,
        "bos": event == "BOS",
        "choch": event in ("CHOCH", "MSS"),
        "mss": is_shift,
    }


def detect_structure_events(swings, timeframe=None):
    normalized = _dedupe_consecutive_same_type(_normalize_swings(swings))
    events = []
    last_high = None
    last_low = None
    rolling_trend = "range"

    for swing in normalized:
        if swing["type"] == "high":
            if last_high is None:
                last_high = swing
                continue
            if float(swing["price"]) > float(last_high["price"]):
                event_type = "MSS" if rolling_trend == "bearish" else "BOS"
                events.append(_event(event_type, "bullish", swing, last_high, "HH", rolling_trend, timeframe))
                rolling_trend = "bullish"
            elif float(swing["price"]) < float(last_high["price"]):
                events.append(_event("LH", "bearish", swing, last_high, "LH", rolling_trend, timeframe))
            last_high = swing
            continue

        if last_low is None:
            last_low = swing
            continue
        if float(swing["price"]) < float(last_low["price"]):
            event_type = "MSS" if rolling_trend == "bullish" else "BOS"
            events.append(_event(event_type, "bearish", swing, last_low, "LL", rolling_trend, timeframe))
            rolling_trend = "bearish"
        elif float(swing["price"]) > float(last_low["price"]):
            events.append(_event("HL", "bullish", swing, last_low, "HL", rolling_trend, timeframe))
        last_low = swing

    events.sort(key=lambda item: int(item["index"]))
    return events


def analyze_market_structure(swings, candles=None, direction=None, timeframe=None):
    normalized = _dedupe_consecutive_same_type(_normalize_swings(swings))
    highs = [swing for swing in normalized if swing["type"] == "high"]
    lows = [swing for swing in normalized if swing["type"] == "low"]
    events = detect_structure_events(normalized, timeframe=timeframe)
    trend = _classify_trend(highs, lows)
    last_directional_event = next(
        (
            event for event in reversed(events)
            if event.get("event") in ("BOS", "MSS", "CHOCH")
        ),
        None,
    )
    if trend == "range" and last_directional_event:
        trend = last_directional_event.get("direction") or "range"

    requested_direction = _normalize_direction(direction)
    confirms = structure_confirms_direction(
        {"trend": trend, "events": events, "last_event": last_directional_event},
        requested_direction,
        require_event=False,
    ) if requested_direction else False

    return {
        "timeframe": timeframe,
        "trend": trend,
        "bias": "buy" if trend == "bullish" else "sell" if trend == "bearish" else None,
        "bos": any(event.get("event") == "BOS" for event in events),
        "choch": any(event.get("event") in ("CHOCH", "MSS") for event in events),
        "mss": any(event.get("event") == "MSS" for event in events),
        "last_event": last_directional_event,
        "events": events,
        "swing_sequence": normalized,
        "last_high": highs[-1] if highs else None,
        "last_low": lows[-1] if lows else None,
        "high_count": len(highs),
        "low_count": len(lows),
        "confirms_requested_direction": confirms,
        "requested_direction": requested_direction,
    }


def _normalize_direction(direction):
    raw = str(direction or "").lower()
    if raw in ("buy", "bull", "bullish", "long"):
        return "buy"
    if raw in ("sell", "bear", "bearish", "short"):
        return "sell"
    return None


def _direction_from_event(event):
    direction = str((event or {}).get("direction") or "").lower()
    if direction == "bullish":
        return "buy"
    if direction == "bearish":
        return "sell"
    return None


def structure_confirms_direction(structure, direction, require_event=False):
    requested = _normalize_direction(direction)
    if not requested or not isinstance(structure, dict):
        return False

    event = structure.get("last_event") or {}
    if event and event.get("event") in ("BOS", "CHOCH", "MSS") and _direction_from_event(event) == requested:
        return True
    if require_event:
        return False

    trend = str(structure.get("trend") or "").lower()
    return (requested == "buy" and trend == "bullish") or (requested == "sell" and trend == "bearish")


def latest_structure_event(swings, direction=None, timeframe=None):
    structure = analyze_market_structure(swings, direction=direction, timeframe=timeframe)
    return structure.get("last_event")


def detect_structure(swings):
    """Backward-compatible event list."""
    return detect_structure_events(swings)


def detect_structure_trend(swings):
    return analyze_market_structure(swings).get("trend", "range")
