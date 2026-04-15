def _normalize_swings(swings):
    normalized = []
    for swing in swings or []:
        if isinstance(swing, dict):
            normalized.append(swing)
        elif isinstance(swing, (list, tuple)) and len(swing) >= 3:
            normalized.append({"type": swing[0], "index": swing[1], "price": swing[2]})
    return normalized


def detect_structure(swings):
    events = []
    normalized = _normalize_swings(swings)
    highs = [s for s in normalized if s.get("type") == "high"]
    lows = [s for s in normalized if s.get("type") == "low"]

    for index in range(1, len(highs)):
        current = highs[index]
        previous = highs[index - 1]
        event_type = "BOS" if float(current["price"]) > float(previous["price"]) else "CHOCH"
        if float(current["price"]) != float(previous["price"]):
            events.append(
                {
                    "event": event_type,
                    "direction": "bullish" if event_type == "BOS" else "bearish",
                    "index": current["index"],
                    "price": float(current["price"]),
                }
            )

    for index in range(1, len(lows)):
        current = lows[index]
        previous = lows[index - 1]
        event_type = "BOS" if float(current["price"]) < float(previous["price"]) else "CHOCH"
        if float(current["price"]) != float(previous["price"]):
            events.append(
                {
                    "event": event_type,
                    "direction": "bearish" if event_type == "BOS" else "bullish",
                    "index": current["index"],
                    "price": float(current["price"]),
                }
            )

    events.sort(key=lambda item: int(item["index"]))
    return events
