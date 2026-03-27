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
    entry_profile = get_entry_profile(symbol)
    recent_candle_count = max(16, int(entry_profile["recent_candles"]))
    atr_period = max(5, int(os.getenv("ENTRY_ATR_PERIOD", "14")))

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

        recent_candles = _fetch_recent_candles(symbol, tf, bars=recent_candle_count)

        analysis[tf] = {
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
