from ict_concepts.fib import calculate_fib_levels
from ict_concepts.market_structure import get_market_trend
from ict_concepts.fvg import detect_fvgs
from ict_concepts.order_blocks import detect_htf_order_blocks
from ict_concepts.liquidity import detect_liquidity_zones
from ict_concepts.market_structure import get_swings
import os

from utils.symbol_profile import get_entry_profile

try:
    import MetaTrader5 as mt5
except Exception:
    mt5 = None


def _tf_to_mt5(tf):
    if mt5 is None:
        return None
    mapping = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
    }
    return mapping.get(tf)


def _fetch_recent_candles(symbol, timeframe, bars=32):
    tf = _tf_to_mt5(timeframe)
    if mt5 is None or tf is None:
        return []

    try:
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, bars)
    except Exception:
        return []

    if rates is None or len(rates) == 0:
        return []

    candles = []
    for candle in rates[-bars:]:
        candles.append(
            {
                "open": float(candle["open"]),
                "high": float(candle["high"]),
                "low": float(candle["low"]),
                "close": float(candle["close"]),
                "volume": float(candle["tick_volume"]),
            }
        )
    return candles


def _calculate_atr(candles, period=14):
    if not candles:
        return 0.0

    true_ranges = []
    previous_close = None
    for candle in candles:
        high_price = float(candle["high"])
        low_price = float(candle["low"])
        close_price = float(candle["close"])
        if previous_close is None:
            true_range = high_price - low_price
        else:
            true_range = max(
                high_price - low_price,
                abs(high_price - previous_close),
                abs(low_price - previous_close),
            )
        true_ranges.append(true_range)
        previous_close = close_price

    if not true_ranges:
        return 0.0
    window = true_ranges[-max(1, min(period, len(true_ranges))):]
    return sum(window) / len(window)

def _calculate_sma(candles, period=50):
    if period <= 0:
        return 0.0
    if len(candles) < period:
        return 0.0
    closes = [c["close"] for c in candles[-period:]]
    return sum(closes) / period


def _analyze_timeframe(symbol, timeframe, price, recent_candle_count, atr_period):
    try:
        trend = get_market_trend(symbol, timeframe=timeframe)
    except Exception:
        trend = "neutral"

    try:
        fib = calculate_fib_levels(symbol, timeframe=timeframe) or {}
    except Exception:
        fib = {}

    try:
        fvgs = detect_fvgs(symbol, timeframe=timeframe) or []
    except Exception:
        fvgs = []

    try:
        obs = detect_htf_order_blocks(symbol, timeframe=timeframe) or []
    except Exception:
        obs = []

    try:
        swings = get_swings(symbol, timeframe=timeframe) or []
    except Exception:
        swings = []

    try:
        liquidity = detect_liquidity_zones(swings) or {"EQL": [], "EQH": []}
    except Exception:
        liquidity = {"EQL": [], "EQH": []}

    discount = (fib.get("0.25", 0.0), fib.get("0.5", 0.0))
    premium = (fib.get("0.5", 0.0), fib.get("0.75", 0.0))
    recent_candles = _fetch_recent_candles(symbol, timeframe, bars=recent_candle_count)
    avg_volume = sum(c["volume"] for c in recent_candles) / len(recent_candles) if recent_candles else 0
    current_volume = recent_candles[-1]["volume"] if recent_candles else 0
    sma_50 = _calculate_sma(recent_candles, period=min(50, len(recent_candles)))

    return {
        "timeframe": timeframe,
        "trend": trend,
        "fib": fib,
        "discount": discount,
        "premium": premium,
        "fvgs": fvgs,
        "order_blocks": obs,
        "liquidity": liquidity,
        "swings": swings,
        "recent_candles": recent_candles,
        "atr": _calculate_atr(recent_candles, period=atr_period),
        "volume_boost": current_volume > (avg_volume * 1.5),
        "sma_50": sma_50,
        "above_sma": price > sma_50 if sma_50 > 0 else True,
    }


def _directional_trends(states):
    return [
        state.get("trend")
        for state in states
        if isinstance(state, dict) and state.get("trend") in ("bullish", "bearish")
    ]


def _majority_trend(states):
    trends = _directional_trends(states)
    if not trends:
        return "range"
    bullish = trends.count("bullish")
    bearish = trends.count("bearish")
    if bullish > bearish:
        return "bullish"
    if bearish > bullish:
        return "bearish"
    return "range"


def _context_alignment(overall_trend, context_states):
    if overall_trend not in ("bullish", "bearish"):
        return "unclear"
    context_trends = _directional_trends(context_states)
    if not context_trends:
        return "unclear"
    aligned = sum(1 for trend in context_trends if trend == overall_trend)
    if aligned == len(context_trends):
        return "aligned"
    if aligned == 0:
        return "opposed"
    return "mixed"


def _detect_htf_liquidity_sweep(symbol, htf_tf, price, direction):
    """Check if a sweep is currently happening on the HTF."""
    from ict_concepts.liquidity import detect_liquidity_zones
    from ict_concepts.market_structure import get_swings
    swings = get_swings(symbol, timeframe=htf_tf)
    liquidity = detect_liquidity_zones(swings) or {"EQL": [], "EQH": []}
    from strategy.liquidity_filter import liquidity_taken
    return liquidity_taken(price, liquidity, direction)

def analyze_market_top_down(
    symbol,
    price,
    htf=None,
    mtf=None,
    ltf=None
):
    daily_tf = os.getenv("DAILY_TIMEFRAME", os.getenv("CONTEXT_DAILY_TIMEFRAME", "D1"))
    h4_tf = os.getenv("FOUR_HOUR_TIMEFRAME", os.getenv("CONTEXT_4H_TIMEFRAME", "H4"))
    htf = htf or os.getenv("HTF_TIMEFRAME", "H1")
    mtf = mtf or os.getenv("MTF_TIMEFRAME", "M30")
    ltf = ltf or os.getenv("LTF_TIMEFRAME", "M15")
    execution_tf = os.getenv("EXECUTION_TIMEFRAME", "M5")
    entry_profile = get_entry_profile(symbol)
    recent_candle_count = max(16, int(entry_profile["recent_candles"]))
    atr_period = max(5, int(os.getenv("ENTRY_ATR_PERIOD", "14")))

    requested_timeframes = []
    for tf in [daily_tf, h4_tf, htf, mtf, ltf, execution_tf]:
        if tf and tf not in requested_timeframes:
            requested_timeframes.append(tf)

    analysis = {
        tf: _analyze_timeframe(symbol, tf, price, recent_candle_count, atr_period)
        for tf in requested_timeframes
    }

    # -------------------------
    # OVERALL BIAS (TOP DOWN)
    # -------------------------
    daily_state = analysis[daily_tf]
    h4_state = analysis[h4_tf]
    h1_state = analysis[htf]
    m30_state = analysis[mtf]
    m15_state = analysis[ltf]
    execution_state = analysis[execution_tf]

    overall_trend = _majority_trend([h1_state, m30_state, m15_state])
    if overall_trend not in ("bullish", "bearish") and os.getenv("ALLOW_LTF_TREND_FALLBACK", "true").lower() in ("1", "true", "yes"):
        execution_trend = execution_state.get("trend")
        if execution_trend in ("bullish", "bearish"):
            overall_trend = execution_trend

    context_alignment = _context_alignment(overall_trend, [daily_state, h4_state])

    # HTF Sweep Check
    htf_sweep = _detect_htf_liquidity_sweep(symbol, htf, price, "buy" if overall_trend == "bullish" else "sell")

    return {
        "overall_trend": overall_trend,
        "topdown": {
            "trend": overall_trend,
            "daily_trend": daily_state.get("trend"),
            "h4_trend": h4_state.get("trend"),
            "h1_trend": h1_state.get("trend"),
            "m30_trend": m30_state.get("trend"),
            "m15_trend": m15_state.get("trend"),
            "execution_trend": execution_state.get("trend"),
            "context_alignment": context_alignment,
        },
        "price": price,
        "timeframes": {
            "DAILY": daily_tf,
            "H4": h4_tf,
            "HTF": htf,
            "MTF": mtf,
            "LTF": ltf,
            "EXECUTION": execution_tf,
        },
        "brief_context": {
            "daily": daily_state,
            "h4": h4_state,
            "alignment": context_alignment,
        },
        "DAILY": daily_state,
        "H4_CONTEXT": h4_state,
        "HTF": h1_state,
        "MTF": m30_state,
        "LTF": m15_state,
        "EXECUTION": execution_state,
        "htf_sweep": htf_sweep,
        "volume_alignment": execution_state["volume_boost"],
        "sma_alignment": execution_state["above_sma"] if overall_trend == "bullish" else not execution_state["above_sma"],
        # placeholder for correlated instruments (not implemented fully)
        "correlated": {}
    }
