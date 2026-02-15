from datetime import datetime, timedelta

# Placeholder for real API integration
# Later you replace this with a real API call

HIGH_IMPACT_EVENTS = [
    "CPI",
    "NFP",
    "FOMC",
    "Interest Rate Decision",
    "GDP"
]


def is_high_impact_news_soon(
    currency: str,
    minutes_before=30,
    minutes_after=15
) -> bool:
    """
    Returns True if high-impact news is near.
    """

    now = datetime.utcnow()

    # MOCK EXAMPLE (replace with API data)
    upcoming_events = [
        {
            "currency": "USD" "GBP" "JPY" "EUR",
            "event": "CPI",
            "time": now + timedelta(minutes=20)
        }
    ]

    for event in upcoming_events:
        if event["currency"] != currency:
            continue

        event_time = event["time"]

        if now - timedelta(minutes=minutes_after) <= event_time <= now + timedelta(minutes=minutes_before):
            return True

    return False
