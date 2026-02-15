from ict_concepts.market_structure import get_daily_trend

def rule_quality_filter(signal):
    score = 0
    
    if not isinstance(signal, dict):
        return False

    # 1️⃣ Fib zone
    if signal.get("fib_zone") in ["discount", "premium"]:
        score += 1

    # 2️⃣ FVG timeframe
    fvg = signal.get("fvg")
    if isinstance(fvg, dict) and fvg.get("timeframe") == "M15":
        score += 1

    # 3️⃣ HTF Order Block
    htf_ob = signal.get("htf_ob")
    if isinstance(htf_ob, dict) and htf_ob.get("timeframe") in ["H1", "H4"]:
        score += 1

    # 4️⃣ DAILY TREND CONFIRMATION (MANDATORY) - skip if 'trend' or 'symbol' missing
    try:
        if signal.get("symbol") and signal.get("trend"):
            daily_trend = get_daily_trend(signal["symbol"])
            if daily_trend == signal.get("trend"):
                score += 1
    except Exception:
        pass

    return score >= 3
