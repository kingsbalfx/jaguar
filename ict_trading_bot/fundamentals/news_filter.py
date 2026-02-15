from fundamentals.news_api import is_high_impact_news_soon
from fundamentals.news_manual import is_manual_news_block

def news_allows_trade(symbol: str) -> bool:
    """
    Example:
    EURUSD → checks EUR + USD
    """

    base = symbol[:3]
    quote = symbol[3:]

    if is_high_impact_news_soon(base) or is_high_impact_news_soon(quote):
        return False

    if is_manual_news_block(base) or is_manual_news_block(quote):
        return False

    return True
