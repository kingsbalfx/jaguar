from ict_concepts.market_structure import get_daily_trend


def rule_quality_filter(signal):
    if not isinstance(signal, dict):
        return False

    if signal.get("fib_zone") not in ["discount", "premium"]:
        return False
    if not signal.get("valid_fvg"):
        return False
    if not signal.get("valid_order_block"):
        return False

    fvg = signal.get("fvg")
    if not isinstance(fvg, dict) or fvg.get("timeframe") not in ["M1", "M5", "M15", "M30"]:
        return False

    htf_ob = signal.get("htf_ob")
    if not isinstance(htf_ob, dict) or htf_ob.get("timeframe") not in ["M15", "M30", "H1", "H4", "D1"]:
        return False

    try:
        if signal.get("symbol") and signal.get("trend"):
            daily_trend = get_daily_trend(signal["symbol"])
            return daily_trend == signal.get("trend")
    except Exception:
        return False

    return False
