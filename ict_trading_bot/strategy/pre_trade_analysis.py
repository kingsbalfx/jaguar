from ict_concepts.fib import calculate_fib_levels
from ict_concepts.market_structure import get_market_trend
from ict_concepts.fvg import detect_fvgs
from ict_concepts.order_blocks import detect_htf_order_blocks
from ict_concepts.liquidity import detect_liquidity_zones
from ict_concepts.market_structure import get_swings
import os

def analyze_market_top_down(
    symbol,
    price,
    htf=None,
    mtf=None,
    ltf=None
):
    htf = htf or os.getenv("HTF_TIMEFRAME", "H4")
    mtf = mtf or os.getenv("MTF_TIMEFRAME", "H1")
    ltf = ltf or os.getenv("LTF_TIMEFRAME", "M15")
    analysis = {}

    for tf in [htf, mtf, ltf]:
        # Defensive calls: ensure each helper returns expected shape
        try:
            trend = get_market_trend(symbol, timeframe=tf)
        except Exception:
            trend = "neutral"

        try:
            fib = calculate_fib_levels(symbol, timeframe=tf) or {}
        except Exception:
            fib = {}

        try:
            fvgs = detect_fvgs(symbol, timeframe=tf) or []
        except Exception:
            fvgs = []

        try:
            obs = detect_htf_order_blocks(symbol, timeframe=tf) or []
        except Exception:
            obs = []

        try:
            swings = get_swings(symbol, timeframe=tf) or []
        except Exception:
            swings = []

        try:
            liquidity = detect_liquidity_zones(swings) or {"EQL": [], "EQH": []}
        except Exception:
            liquidity = {"EQL": [], "EQH": []}

        # Ensure fib defaults for indexing
        discount = (fib.get("0.25", 0.0), fib.get("0.5", 0.0))
        premium = (fib.get("0.5", 0.0), fib.get("0.75", 0.0))

        analysis[tf] = {
            "trend": trend,
            "fib": fib,
            "discount": discount,
            "premium": premium,
            "fvgs": fvgs,
            "order_blocks": obs,
            "liquidity": liquidity,
            "swings": swings,
        }

    # -------------------------
    # OVERALL BIAS (TOP DOWN)
    # -------------------------
    overall_trend = analysis[htf]["trend"]
    if overall_trend not in ("bullish", "bearish"):
        mtf_trend = analysis[mtf]["trend"]
        if mtf_trend in ("bullish", "bearish"):
            overall_trend = mtf_trend
        elif os.getenv("ALLOW_LTF_TREND_FALLBACK", "true").lower() in ("1", "true", "yes"):
            ltf_trend = analysis[ltf]["trend"]
            if ltf_trend in ("bullish", "bearish"):
                overall_trend = ltf_trend

    return {
        "overall_trend": overall_trend,
        "price": price,
        "timeframes": {"HTF": htf, "MTF": mtf, "LTF": ltf},
        "HTF": analysis[htf],
        "MTF": analysis[mtf],
        "LTF": analysis[ltf],
        # placeholder for correlated instruments (not implemented fully)
        "correlated": {}
    }
