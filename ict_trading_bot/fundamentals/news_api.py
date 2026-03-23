from datetime import datetime, timedelta
import json
from pathlib import Path

HIGH_IMPACT_EVENTS = {
    "CPI",
    "NFP",
    "FOMC",
    "INTEREST RATE DECISION",
    "GDP",
}

NEWS_EVENTS_FILE = Path(__file__).with_name("news_events.json")


def _load_upcoming_events():
    if not NEWS_EVENTS_FILE.exists():
        return []

    try:
        raw = json.loads(NEWS_EVENTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []

    events = raw if isinstance(raw, list) else raw.get("events", [])
    normalized = []
    for item in events:
        if not isinstance(item, dict):
            continue

        currency = str(item.get("currency") or "").strip().upper()
        event_name = str(item.get("event") or "").strip()
        event_time_raw = str(item.get("time") or "").strip()
        impact = str(item.get("impact") or "high").strip().lower()
        if not currency or not event_name or not event_time_raw:
            continue

        try:
            event_time = datetime.fromisoformat(event_time_raw.replace("Z", "+00:00"))
        except Exception:
            continue

        normalized.append(
            {
                "currency": currency,
                "event": event_name,
                "impact": impact,
                "time": event_time,
            }
        )

    return normalized


def is_high_impact_news_soon(currency: str, minutes_before=30, minutes_after=15) -> bool:
    """
    Returns True if a nearby high-impact event exists for the currency.

    Events are loaded from fundamentals/news_events.json when present.
    If no file exists, this safely returns False.
    """

    now = datetime.utcnow().astimezone()
    target_currency = str(currency or "").strip().upper()
    if not target_currency:
        return False

    for event in _load_upcoming_events():
        if event["currency"] != target_currency:
            continue
        if event["impact"] != "high" and event["event"].upper() not in HIGH_IMPACT_EVENTS:
            continue

        event_time = event["time"]
        if event_time.tzinfo is None:
            event_time = event_time.astimezone()

        if now - timedelta(minutes=minutes_after) <= event_time <= now + timedelta(minutes=minutes_before):
            return True

    return False
