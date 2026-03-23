from fundamentals.news_api import is_high_impact_news_soon
from fundamentals.news_manual import is_manual_news_block


def _extract_currencies(symbol: str):
    clean = str(symbol or "").strip().upper()
    if len(clean) >= 6:
        return clean[:3], clean[-3:]
    return clean[:3], ""


def news_allows_trade(symbol: str) -> bool:
    """
    Example:
    EURUSD -> checks EUR + USD
    """

    base, quote = _extract_currencies(symbol)

    if is_high_impact_news_soon(base) or is_high_impact_news_soon(quote):
        return False

    if is_manual_news_block(base) or is_manual_news_block(quote):
        return False

    return True
