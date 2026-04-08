"""
Confirmation Aggregator
=======================
Calculates structural ratings across 7 timeframes for the CIS.
"""
from strategy.pre_trade_analysis import analyze_market_top_down

def get_all_confirmations_for_pair(symbol: str, timeframe: str, analysis: dict = None) -> dict:
    """
    Analyzes structural alignment across all major timeframes.
    Returns a rating (0.0 - 1.0) for each TF.
    """
    # We leverage the existing top-down analysis to build the ratings.
    analysis = analysis or analyze_market_top_down(symbol, 0.0)
    if not analysis:
        return {}

    htf_trend = (analysis.get("topdown") or {}).get("trend") or analysis.get("overall_trend", "neutral")

    def _rate_state(tf_data):
        trend = (tf_data or {}).get("trend")
        if trend == htf_trend:
            return 0.85
        if trend in (None, "neutral", "range", "unknown"):
            return 0.5
        return 0.4

    brief_context = analysis.get("brief_context") or {}
    daily_state = analysis.get("DAILY") or brief_context.get("daily") or {}
    h4_state = analysis.get("H4_CONTEXT") or brief_context.get("h4") or {}

    return {
        "w1_rating": _rate_state(daily_state),  # Kept for compatibility; daily is the brief macro proxy.
        "d1_rating": _rate_state(daily_state),
        "h4_rating": _rate_state(h4_state),
        "h1_rating": _rate_state(analysis.get("HTF")),
        "m30_rating": _rate_state(analysis.get("MTF")),
        "m15_rating": _rate_state(analysis.get("LTF")),
        "m5_rating": _rate_state(analysis.get("EXECUTION")),
        "m1_rating": 0.5  # Neutral default for micro
    }
