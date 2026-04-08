from datetime import datetime, timedelta
import os
import json
import logging
try:
    import requests
except Exception:
    requests = None

logger = logging.getLogger(__name__)

# API Key and Endpoint for real economic calendar integration
# Recommended: FinancialModelingPrep (FMP) - https://site.financialmodelingprep.com/developer/docs/economic-calendar-api/
# Example Endpoint: https://financialmodelingprep.com/api/v3/economic_calendar
NEWS_API_ENDPOINT = os.getenv("NEWS_API_ENDPOINT")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

# Internal cache to save API credits
_NEWS_CACHE = {
    "data": None,
    "expiry": None,
    "disabled_until": None,
    "last_error": None,
}

def check_for_high_impact_news(symbol: str) -> str:
    """
    Checks for high-impact news events for a given symbol using a real economic calendar API.
    Implementation designed for FinancialModelingPrep (FMP) schema.

    Returns: "high", "medium", "low", or "none"
    """
    if not NEWS_API_KEY or not NEWS_API_ENDPOINT:
        return _get_fallback_simulation()
    if requests is None:
        return _get_fallback_simulation()

    global _NEWS_CACHE
    now = datetime.utcnow()

    disabled_until = _NEWS_CACHE.get("disabled_until")
    if disabled_until and disabled_until > now:
        return _get_fallback_simulation()

    # 1. Use Cache if valid (saves API credits)
    if _NEWS_CACHE["data"] and _NEWS_CACHE["expiry"] and _NEWS_CACHE["expiry"] > now:
        return _parse_impact_from_data(symbol, _NEWS_CACHE["data"])

    # 2. Fetch fresh news data
    try:
        start_date = now.strftime("%Y-%m-%d")
        end_date = (now + timedelta(days=1)).strftime("%Y-%m-%d")

        params = {
            "from": start_date,
            "to": end_date,
            "apikey": NEWS_API_KEY
        }

        response = requests.get(NEWS_API_ENDPOINT, params=params, timeout=10)
        if response.status_code in (401, 403):
            disabled_minutes = max(5, int(os.getenv("NEWS_API_DISABLE_MINUTES", "360")))
            _NEWS_CACHE["disabled_until"] = now + timedelta(minutes=disabled_minutes)
            _NEWS_CACHE["last_error"] = f"HTTP {response.status_code}"
            logger.warning(
                "News API authentication failed with HTTP %s. "
                "Disabling live economic calendar for %s minutes.",
                response.status_code,
                disabled_minutes,
            )
            return _get_fallback_simulation()

        response.raise_for_status()
        events = response.json()

        # Update cache (valid for 30 minutes)
        _NEWS_CACHE["data"] = events
        _NEWS_CACHE["expiry"] = now + timedelta(minutes=30)

        return _parse_impact_from_data(symbol, events)

    except Exception as e:
        _NEWS_CACHE["last_error"] = str(e)
        logger.warning("News API unavailable; using fallback news mode: %s", type(e).__name__)
        return _get_fallback_simulation()

def _parse_impact_from_data(symbol: str, events: list) -> str:
    """Logic to extract impact levels from API JSON response."""
    if not events or not isinstance(events, list):
        return "none"

    # Determine relevant currencies for the symbol (e.g. BTCUSD -> USD)
    base = symbol[:3].upper()
    quote = symbol[3:6].upper() if len(symbol) >= 6 else ""

    # Map common country codes to currencies
    country_to_currency = {"US": "USD", "EU": "EUR", "GB": "GBP", "JP": "JPY", "CH": "CHF", "AU": "AUD", "CA": "CAD", "NZ": "NZD"}

    highest_impact = "none"
    impact_ranks = {"high": 3, "medium": 2, "low": 1, "none": 0}

    now = datetime.utcnow()

    for event in events:
        country = event.get("country", "").upper()
        currency = country_to_currency.get(country, country)

        # Only check news for currencies matching our pair
        if currency in [base, quote]:
            try:
                # FMP format: "2024-05-22 14:00:00"
                event_time = datetime.strptime(event.get("date", ""), "%Y-%m-%d %H:%M:%S")
                # Only care if event is within +/- 2 hours of now
                if abs((now - event_time).total_seconds()) < 7200:
                    impact = event.get("impact", "none").lower()
                    if impact_ranks.get(impact, 0) > impact_ranks[highest_impact]:
                        highest_impact = impact
            except (ValueError, TypeError):
                continue

    return highest_impact

def _get_fallback_simulation() -> str:
    if os.getenv("NEWS_API_FALLBACK_SIMULATION", "false").lower() not in ("1", "true", "yes"):
        return "none"

    # Optional demo mode only. Keep disabled in live trading to avoid synthetic news penalties.
    current_hour = datetime.utcnow().hour
    if current_hour % 3 == 0: # Every 3 hours, simulate medium impact
        return "medium"
    return "none"
