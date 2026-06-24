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


def _env_int(name, default, minimum=1, maximum=None):
    try:
        value = int(str(os.getenv(name, str(default))).strip())
    except (TypeError, ValueError):
        value = default
    value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _window(candles, size):
    if not candles:
        return []
    return candles[-max(1, min(int(size), len(candles))):]


def _concept_candle_windows():
    return {
        "fetch_per_timeframe": _env_int("CANDLE_FETCH_PER_TIMEFRAME", 500, minimum=120, maximum=2000),
        "htf_context": _env_int("HTF_CONTEXT_CANDLES", 120, minimum=50, maximum=500),
        "external_liquidity": _env_int("EXTERNAL_LIQUIDITY_CANDLES", 200, minimum=50, maximum=500),
        "structure": _env_int("STRUCTURE_CANDLES", 80, minimum=20, maximum=250),
        "true_fvg_ob_context": _env_int("TRUE_FVG_OB_CONTEXT_CANDLES", 100, minimum=20, maximum=250),
        "smt": _env_int("SMT_CANDLES", 20, minimum=10, maximum=50),
        "sweep": _env_int("SWEEP_CANDLES", 20, minimum=5, maximum=50),
        "displacement": _env_int("DISPLACEMENT_CANDLES", 10, minimum=3, maximum=30),
        "execution_confirmation": _env_int("EXECUTION_CONFIRMATION_CANDLES", 50, minimum=10, maximum=100),
    }


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


def _fetch_recent_candles(symbol, timeframe, bars=500):
    """
    Fetch up to `bars` candles – defaults to 500 for deep structure.
    """
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
        candle_time = candle["time"] if "time" in candle.dtype.names else None
        candles.append(
            {
                "open": float(candle["open"]),
                "high": float(candle["high"]),
                "low": float(candle["low"]),
                "close": float(candle["close"]),
                "volume": float(candle["tick_volume"]),
                "time": candle_time,
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
    if period <= 0 or len(candles) < period:
        return 0.0
    closes = [c["close"] for c in candles[-period:]]
    return sum(closes) / period


def _analyze_timeframe(symbol, timeframe, price, recent_candle_count=500, atr_period=14, candle_windows=None):
    candle_windows = candle_windows or _concept_candle_windows()
    try:
        trend = get_market_trend(symbol, timeframe=timeframe)
    except Exception:
        trend = "neutral"

    try:
        fib = calculate_fib_levels(symbol, timeframe=timeframe) or {}
    except Exception:
        fib = {}

    try:
        fvgs = detect_fvgs(symbol, timeframe=timeframe, trend=trend) or []
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

    discount = (fib.get("0.25", 0.0), fib.get("0.5", 0.0))
    premium = (fib.get("0.5", 0.0), fib.get("0.75", 0.0))
    recent_candles = _fetch_recent_candles(symbol, timeframe, bars=recent_candle_count)
    context_candles = _window(recent_candles, candle_windows["htf_context"])
    liquidity_candles = _window(recent_candles, candle_windows["external_liquidity"])
    structure_candles = _window(recent_candles, candle_windows["structure"])
    fvg_ob_candles = _window(recent_candles, candle_windows["true_fvg_ob_context"])
    smt_candles = _window(recent_candles, candle_windows["smt"])
    sweep_candles = _window(recent_candles, candle_windows["sweep"])
    displacement_candles = _window(recent_candles, candle_windows["displacement"])
    execution_candles = _window(recent_candles, candle_windows["execution_confirmation"])
    try:
        liquidity = detect_liquidity_zones(
            swings,
            atr=_calculate_atr(liquidity_candles, period=atr_period),
        ) or {"EQL": [], "EQH": []}
    except Exception:
        liquidity = {"EQL": [], "EQH": []}
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
        "concept_windows": {
            "htf_context": context_candles,
            "external_liquidity": liquidity_candles,
            "structure": structure_candles,
            "true_fvg_ob_context": fvg_ob_candles,
            "smt": smt_candles,
            "sweep": sweep_candles,
            "displacement": displacement_candles,
            "execution_confirmation": execution_candles,
        },
        "candle_window_lengths": {
            "fetched": len(recent_candles),
            "htf_context": len(context_candles),
            "external_liquidity": len(liquidity_candles),
            "structure": len(structure_candles),
            "true_fvg_ob_context": len(fvg_ob_candles),
            "smt": len(smt_candles),
            "sweep": len(sweep_candles),
            "displacement": len(displacement_candles),
            "execution_confirmation": len(execution_candles),
        },
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


def _candle_direction(candle):
    if not isinstance(candle, dict):
        return None
    open_price = float(candle.get("open", 0.0) or 0.0)
    close_price = float(candle.get("close", 0.0) or 0.0)
    if close_price > open_price:
        return "bullish"
    if close_price < open_price:
        return "bearish"
    return None


def _session_start(candle):
    try:
        value = candle.get("time")
        return int(value) if value is not None else None
    except (TypeError, ValueError, AttributeError):
        return None


def _window_bias(candles):
    if not candles:
        return None
    bullish = sum(1 for candle in candles if _candle_direction(candle) == "bullish")
    bearish = sum(1 for candle in candles if _candle_direction(candle) == "bearish")
    first_open = float(candles[0].get("open", 0.0) or 0.0)
    last_close = float(candles[-1].get("close", 0.0) or 0.0)
    if bullish > bearish and last_close >= first_open:
        return "bullish"
    if bearish > bullish and last_close <= first_open:
        return "bearish"
    return None


def _current_day_h4_candles(daily_candles, h4_candles):
    if not h4_candles:
        return []
    current_day_start = _session_start(daily_candles[-1]) if daily_candles else None
    if current_day_start is None:
        return h4_candles[-6:]
    current_day = [
        candle for candle in h4_candles
        if (_session_start(candle) or 0) >= current_day_start
    ]
    return current_day or h4_candles[-6:]


def _daily_h4_candle_alignment(daily_state, h4_state):
    daily_candles = daily_state.get("recent_candles") or []
    h4_candles = h4_state.get("recent_candles") or []
    daily_window = daily_candles[-3:]
    h4_window = _current_day_h4_candles(daily_candles, h4_candles)
    daily_bias = _window_bias(daily_window)
    h4_bias = _window_bias(h4_window)
    trend_d1 = str(daily_state.get("trend") or "").lower()
    trend_h4 = str(h4_state.get("trend") or "").lower()
    confirmed = (
        daily_bias in ("bullish", "bearish")
        and daily_bias == h4_bias
        and trend_d1 == trend_h4 == daily_bias
    )
    return {
        "confirmed": confirmed,
        "direction": "buy" if confirmed and daily_bias == "bullish" else "sell" if confirmed and daily_bias == "bearish" else None,
        "daily_bias": daily_bias,
        "h4_current_day_bias": h4_bias,
        "daily_trend": trend_d1 or None,
        "h4_trend": trend_h4 or None,
        "daily_candles_used": len(daily_window),
        "h4_candles_used": len(h4_window),
        "rule": "D1 current/previous two candles must align with current-day H4 candles after D1/H4 trend confirmation",
    }


def _external_liquidity(*states):
    """Build external liquidity from D1, H4, H1, M30, and M15 context."""
    result = {"EQH": [], "EQL": []}
    for timeframe, state in states:
        for swing in (state.get("swings") or [])[-30:]:
            if not isinstance(swing, dict) or swing.get("type") not in ("high", "low"):
                continue
            level = float(swing["price"])
            zone = {
                "type": swing["type"],
                "level": level,
                "prices": (level, level),
                "source": f"{timeframe}_external_swing",
                "timeframe": timeframe,
                "touches": 1,
                "separation": 1,
                "untaken": True,
            }
            result["EQH" if swing["type"] == "high" else "EQL"].append(zone)

    daily_state = next((state for timeframe, state in states if timeframe == "D1"), {})
    daily = daily_state.get("recent_candles") or []
    if daily:
        previous_day = daily[-2] if len(daily) >= 2 else daily[-1]
        week = daily[-6:-1] if len(daily) >= 6 else daily
        levels = (
            ("EQH", max(float(item["high"]) for item in week), "previous_week_high"),
            ("EQL", min(float(item["low"]) for item in week), "previous_week_low"),
            ("EQH", float(previous_day["high"]), "previous_day_high"),
            ("EQL", float(previous_day["low"]), "previous_day_low"),
        )
        for key, level, source in levels:
            result[key].append(
                {
                    "type": "high" if key == "EQH" else "low",
                    "level": level,
                    "prices": (level, level),
                    "source": source,
                    "timeframe": "D1",
                    "touches": 1,
                    "separation": 1,
                    "untaken": True,
                }
            )
    return result


def _detect_htf_liquidity_sweep(symbol, htf_tf, price, direction):
    from ict_concepts.liquidity import detect_liquidity_zones
    from ict_concepts.market_structure import get_swings
    swings = get_swings(symbol, timeframe=htf_tf)
    liquidity = detect_liquidity_zones(swings) or {"EQL": [], "EQH": []}
    from strategy.liquidity_filter import liquidity_taken
    recent_candles = _fetch_recent_candles(symbol, htf_tf, bars=8)
    return liquidity_taken(price, liquidity, direction, recent_candles=recent_candles)


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
    candle_windows = _concept_candle_windows()
    recent_candle_count = candle_windows["fetch_per_timeframe"]
    atr_period = max(5, int(os.getenv("ENTRY_ATR_PERIOD", "14")))

    requested_timeframes = []
    for tf in [daily_tf, h4_tf, htf, mtf, ltf, execution_tf]:
        if tf and tf not in requested_timeframes:
            requested_timeframes.append(tf)

    analysis = {
        tf: _analyze_timeframe(symbol, tf, price, recent_candle_count, atr_period, candle_windows)
        for tf in requested_timeframes
    }

    daily_state = analysis[daily_tf]
    h4_state = analysis[h4_tf]
    h1_state = analysis[htf]
    m30_state = analysis[mtf]
    m15_state = analysis[ltf]
    execution_state = analysis[execution_tf]
    external_liquidity = _external_liquidity(
        ("D1", daily_state),
        ("H4", h4_state),
        (htf, h1_state),
        (mtf, m30_state),
        (ltf, m15_state),
    )
    for state in (daily_state, h4_state, h1_state, m30_state, m15_state):
        state["external_liquidity"] = external_liquidity
    h1_state["liquidity"] = external_liquidity

    overall_trend = _majority_trend([h1_state, m30_state, m15_state])

    context_alignment = _context_alignment(overall_trend, [daily_state, h4_state])
    daily_h4_alignment = _daily_h4_candle_alignment(daily_state, h4_state)
    daily_state["daily_h4_alignment"] = daily_h4_alignment
    h4_state["daily_h4_alignment"] = daily_h4_alignment

    htf_sweep = _detect_htf_liquidity_sweep(symbol, htf, price, "buy" if overall_trend == "bullish" else "sell")

    m5_candles = execution_state.get("recent_candles") if execution_tf == "M5" else _fetch_recent_candles(symbol, "M5", bars=recent_candle_count)
    m1_candles = _fetch_recent_candles(symbol, "M1", bars=recent_candle_count)

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
            "daily_h4_alignment": daily_h4_alignment,
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
        "candle_windows": candle_windows,
        "candle_window_usage": {
            "fetch_per_timeframe": recent_candle_count,
            "htf_narrative": candle_windows["htf_context"],
            "external_liquidity": candle_windows["external_liquidity"],
            "market_structure_mss_bos": candle_windows["structure"],
            "true_fvg_order_block_context": candle_windows["true_fvg_ob_context"],
            "smt_divergence": candle_windows["smt"],
            "liquidity_sweep": candle_windows["sweep"],
            "displacement": candle_windows["displacement"],
            "m1_m5_confirmation": candle_windows["execution_confirmation"],
        },
        "daily_h4_alignment": daily_h4_alignment,
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
        "m5_candles": m5_candles,
        "m1_candles": m1_candles,
        "external_liquidity": external_liquidity,
        "htf_sweep": htf_sweep,
        "volume_alignment": execution_state["volume_boost"],
        "sma_alignment": execution_state["above_sma"] if overall_trend == "bullish" else not execution_state["above_sma"],
        "correlated": {}
    }
