from ict_concepts.market_structure import get_daily_trend


def rule_quality_filter(signal):
    score = 0

    if not isinstance(signal, dict):
        return False

    if signal.get("fib_zone") in ["discount", "premium"]:
        score += 1

    fvg = signal.get("fvg")
    if isinstance(fvg, dict) and fvg.get("timeframe") in ["M5", "M15", "M30"]:
        score += 1

    htf_ob = signal.get("htf_ob")
    if isinstance(htf_ob, dict) and htf_ob.get("timeframe") in ["M15", "M30", "H1", "H4", "D1"]:
        score += 1

    try:
        if signal.get("symbol") and signal.get("trend"):
            daily_trend = get_daily_trend(signal["symbol"])
            if daily_trend == signal.get("trend"):
                score += 1
    except Exception:
        pass

    return score >= 2
