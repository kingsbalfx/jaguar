from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from typing import Dict, List

import requests

HIGH_IMPACT_EVENTS = {
    "CPI",
    "NFP",
    "FOMC",
    "INTEREST RATE DECISION",
    "GDP",
}

NEWS_EVENTS_FILE = Path(__file__).with_name("news_events.json")
FOREX_FACTORY_WEEKLY_JSON_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

_EVENT_CACHE: Dict[str, object] = {
    "fetched_at": None,
    "events": [],
}


def _normalize_event(item: Dict[str, object]) -> Dict[str, object] | None:
    if not isinstance(item, dict):
        return None

    currency = str(item.get("currency") or item.get("country") or "").strip().upper()
    event_name = str(item.get("event") or item.get("title") or "").strip()
    event_time_raw = str(item.get("time") or item.get("date") or "").strip()
    impact = str(item.get("impact") or "high").strip().lower()
    if not currency or not event_name or not event_time_raw:
        return None

    try:
        event_time = datetime.fromisoformat(event_time_raw.replace("Z", "+00:00"))
    except Exception:
        return None

    if event_time.tzinfo is None:
        event_time = event_time.replace(tzinfo=timezone.utc)

    return {
        "currency": currency,
        "event": event_name,
        "impact": impact,
        "time": event_time.astimezone(),
    }


def _load_local_events() -> List[Dict[str, object]]:
    if not NEWS_EVENTS_FILE.exists():
        return []

    try:
        raw = json.loads(NEWS_EVENTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []

    events = raw if isinstance(raw, list) else raw.get("events", [])
    normalized = []
    for item in events:
        event = _normalize_event(item)
        if event:
            normalized.append(event)
    return normalized


def _fetch_forex_factory_events() -> List[Dict[str, object]]:
    if os.getenv("LIVE_NEWS_SOURCE_ENABLED", "true").lower() not in ("1", "true", "yes"):
        return []

    timeout_seconds = float(os.getenv("NEWS_HTTP_TIMEOUT_SECONDS", "10"))
    url = os.getenv("FOREX_FACTORY_CALENDAR_JSON_URL", FOREX_FACTORY_WEEKLY_JSON_URL)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JaguarBot/1.0",
        "Accept": "application/json,text/plain,*/*",
    }

    try:
        response = requests.get(url, headers=headers, timeout=timeout_seconds)
        response.raise_for_status()
        raw = response.json()
    except Exception:
        return []

    if not isinstance(raw, list):
        return []

    normalized = []
    for item in raw:
        event = _normalize_event(item)
        if event:
            normalized.append(event)
    return normalized


def _load_upcoming_events() -> List[Dict[str, object]]:
    ttl_seconds = max(30, int(os.getenv("NEWS_CACHE_TTL_SECONDS", "300")))
    now = datetime.now(timezone.utc)
    fetched_at = _EVENT_CACHE.get("fetched_at")
    cached_events = _EVENT_CACHE.get("events") or []

    if isinstance(fetched_at, datetime) and (now - fetched_at).total_seconds() < ttl_seconds:
        return list(cached_events)

    events = _fetch_forex_factory_events()
    local_events = _load_local_events()

    if local_events:
        events.extend(local_events)

    deduped = {}
    for event in events:
        key = (
            event["currency"],
            event["event"],
            event["impact"],
            event["time"].isoformat(),
        )
        deduped[key] = event

    normalized_events = list(deduped.values())
    _EVENT_CACHE["fetched_at"] = now
    _EVENT_CACHE["events"] = normalized_events
    return normalized_events


def is_high_impact_news_soon(currency: str, minutes_before=None, minutes_after=None) -> bool:
    """
    Returns True if a nearby high-impact event exists for the currency.

    Live events are fetched from Forex Factory's weekly JSON export when enabled,
    with a fallback to fundamentals/news_events.json.
    """

    now = datetime.now(timezone.utc).astimezone()
    target_currency = str(currency or "").strip().upper()
    if not target_currency:
        return False

    minutes_before = int(minutes_before if minutes_before is not None else os.getenv("NEWS_MINUTES_BEFORE", "30"))
    minutes_after = int(minutes_after if minutes_after is not None else os.getenv("NEWS_MINUTES_AFTER", "15"))

    for event in _load_upcoming_events():
        if event["currency"] != target_currency:
            continue
        if event["impact"] != "high" and event["event"].upper() not in HIGH_IMPACT_EVENTS:
            continue

        event_time = event["time"]
        if now - timedelta(minutes=minutes_after) <= event_time <= now + timedelta(minutes=minutes_before):
            return True

    return False
