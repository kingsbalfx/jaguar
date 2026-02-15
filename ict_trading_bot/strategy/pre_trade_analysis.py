from ict_concepts.fib import calculate_fib_levels
from ict_concepts.market_structure import get_market_trend
from ict_concepts.fvg import detect_fvgs
from ict_concepts.order_blocks import detect_htf_order_blocks
from ict_concepts.liquidity import detect_liquidity_zones
from ict_concepts.market_structure import get_swings

def analyze_market_top_down(
    symbol,
    price,
    htf="H4",
    mtf="H1",
    ltf="M15"
):
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
            "liquidity": liquidity
        }

    # -------------------------
    # OVERALL BIAS (TOP DOWN)
    # -------------------------
    overall_trend = analysis[htf]["trend"]

    return {
        "overall_trend": overall_trend,
        "price": price,
        "HTF": analysis[htf],
        "MTF": analysis[mtf],
        "LTF": analysis[ltf],
        # placeholder for correlated instruments (not implemented fully)
        "correlated": {}
    }
