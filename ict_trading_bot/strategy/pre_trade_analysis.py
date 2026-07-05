from ict_concepts.fib import calculate_fib_levels
from ict_concepts.market_structure import analyze_structure, get_market_trend
from ict_concepts.fvg import detect_fvgs
from ict_concepts.order_blocks import detect_htf_order_blocks
from ict_concepts.liquidity import detect_liquidity_zones
from ict_concepts.market_structure import get_swings
from ict_concepts.fib_visual import get_visual_entry_zones, visual_price_position
from ict_concepts.judas_swing import detect_judas_swing, should_enter_on_judas_reversal
from ict_concepts.sweet_zone import detect_sweet_zone, should_enter_on_continuation
import os

from utils.timeframe_cache import get_cached, set_cache
from utils.symbol_profile import get_entry_profile
from utils.sessions import (
    in_asia_session,
    in_london_session,
    in_newyork_session,
    intelligence_session_open,
    session_name,
)

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
        "fetch_per_timeframe": _env_int("CANDLE_FETCH_PER_TIMEFRAME", 1000, minimum=500, maximum=5000),
        "htf_context": _env_int("HTF_CONTEXT_CANDLES", 120, minimum=50, maximum=500),
        "external_liquidity": _env_int("EXTERNAL_LIQUIDITY_CANDLES", 200, minimum=50, maximum=500),
        "structure": _env_int("STRUCTURE_CANDLES", 80, minimum=20, maximum=250),
        "true_fvg_ob_context": _env_int("TRUE_FVG_OB_CONTEXT_CANDLES", 100, minimum=20, maximum=250),
        "smt": _env_int("SMT_CANDLES", 20, minimum=10, maximum=50),
        "sweep": _env_int("SWEEP_CANDLES", 20, minimum=5, maximum=50),
        "displacement": _env_int("DISPLACEMENT_CANDLES", 10, minimum=3, maximum=30),
        "execution_confirmation": _env_int("EXECUTION_CONFIRMATION_CANDLES", 50, minimum=10, maximum=100),
    }


_STANDARD_FETCH_BARS = {
    "W1": 260,
    "D1": 370,
    "H4": 720,
    "H1": 1000,
    "M30": 1000,
    "M15": 1500,
    "M5": 2000,
    "M1": 2000,
}


def _standard_fetch_bars(timeframe, requested=None):
    timeframe = str(timeframe or "").upper()
    standard = int(_STANDARD_FETCH_BARS.get(timeframe, 1000))
    try:
        requested_value = int(requested) if requested is not None else standard
    except (TypeError, ValueError):
        requested_value = standard
    env_key = f"{timeframe}_FETCH_CANDLES" if timeframe else "CANDLE_FETCH_PER_TIMEFRAME"
    configured = _env_int(env_key, max(standard, requested_value), minimum=standard, maximum=5000)
    return max(standard, requested_value, configured)


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
        "W1": mt5.TIMEFRAME_W1,
        "D1": mt5.TIMEFRAME_D1,
    }
    return mapping.get(tf)


def _fetch_recent_candles(symbol, timeframe, bars=500):
    """
    Fetch up to `bars` candles â€“ defaults to 500 for deep structure.
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
    # FIX 10: Use TTL cache to avoid redundant MT5 fetches within same scan cycle
    cached = get_cached(symbol, timeframe, price)
    if cached is not None:
        return cached
    candle_windows = candle_windows or _concept_candle_windows()
    fetch_bars = _standard_fetch_bars(timeframe, recent_candle_count)
    try:
        trend = get_market_trend(symbol, timeframe=timeframe, bars=fetch_bars)
    except Exception:
        trend = "neutral"

    try:
        fib = calculate_fib_levels(symbol, timeframe=timeframe, bars=fetch_bars) or {}
    except Exception:
        fib = {}

    try:
        fvgs = detect_fvgs(symbol, timeframe=timeframe, bars=fetch_bars, trend=trend) or []
    except Exception:
        fvgs = []

    try:
        obs = detect_htf_order_blocks(symbol, timeframe=timeframe, bars=fetch_bars) or []
    except Exception:
        obs = []

    try:
        swings = get_swings(symbol, timeframe=timeframe, bars=fetch_bars) or []
    except Exception:
        swings = []

    try:
        market_structure = analyze_structure(swings, direction=trend, timeframe=timeframe) or {}
    except Exception:
        market_structure = {
            "timeframe": timeframe,
            "trend": "range",
            "events": [],
            "last_event": None,
            "bos": False,
            "choch": False,
            "mss": False,
        }
    if trend not in ("bullish", "bearish") and market_structure.get("trend") in ("bullish", "bearish"):
        trend = market_structure["trend"]

    discount = (fib.get("0.25", 0.0), fib.get("0.5", 0.0))
    premium = (fib.get("0.5", 0.0), fib.get("0.75", 0.0))
    recent_candles = _fetch_recent_candles(symbol, timeframe, bars=fetch_bars)
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

    result = {
        "timeframe": timeframe,
        "fetch_bars": fetch_bars,
        "trend": trend,
        "fib": fib,
        "discount": discount,
        "premium": premium,
        "fvgs": fvgs,
        "order_blocks": obs,
        "liquidity": liquidity,
        "swings": swings,
        "market_structure": market_structure,
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
            "requested_fetch": fetch_bars,
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
    # FIX 10: Cache the result to avoid redundant MT5 fetches within scan cycle
    set_cache(symbol, timeframe, price, result)
    return result


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


def _child_candles_inside_current_parent(parent_candles, child_candles, fallback_count):
    if not child_candles:
        return []
    current_parent_start = _session_start(parent_candles[-1]) if parent_candles else None
    if current_parent_start is None:
        return child_candles[-fallback_count:]
    current_parent = [
        candle for candle in child_candles
        if (_session_start(candle) or 0) >= current_parent_start
    ]
    return current_parent or child_candles[-fallback_count:]


def _directional_trend_from_state(state):
    state = state or {}
    structure = state.get("market_structure") or {}
    for value in (
        structure.get("trend"),
        state.get("trend"),
    ):
        trend = str(value or "").lower()
        if trend in ("bullish", "bearish"):
            return trend
    event = structure.get("last_event") or {}
    event_direction = str(event.get("direction") or "").lower()
    if event.get("event") in ("BOS", "MSS", "CHOCH") and event_direction in ("bullish", "bearish"):
        return event_direction
    return None


def _h1_m15_candle_alignment(h1_state, m15_state):
    h1_candles = h1_state.get("recent_candles") or []
    m15_candles = m15_state.get("recent_candles") or []
    h1_window = h1_candles[-3:]
    m15_window = _child_candles_inside_current_parent(h1_candles, m15_candles, fallback_count=4)
    h1_bias = _window_bias(h1_window)
    m15_bias = _window_bias(m15_window)
    trend_h1 = _directional_trend_from_state(h1_state)
    trend_m15 = _directional_trend_from_state(m15_state)

    structural_alignment = bool(
        trend_h1 in ("bullish", "bearish")
        and trend_h1 == trend_m15
    )
    candle_alignment = bool(
        h1_bias in ("bullish", "bearish")
        and h1_bias == m15_bias
    )
    structural_opposition = bool(
        trend_h1 in ("bullish", "bearish")
        and trend_m15 in ("bullish", "bearish")
        and trend_h1 != trend_m15
    )
    m15_structure_incomplete = trend_m15 not in ("bullish", "bearish")
    h1_trend_with_m15_candle = bool(
        trend_h1 in ("bullish", "bearish")
        and trend_h1 == m15_bias
        and m15_structure_incomplete
    )
    candle_fallback = bool(
        candle_alignment
        and not structural_opposition
        and (trend_h1 in (None, h1_bias))
    )
    confirmed = structural_alignment or candle_fallback or h1_trend_with_m15_candle

    direction_trend = trend_h1 if structural_alignment or h1_trend_with_m15_candle else h1_bias if candle_fallback else None
    if structural_alignment:
        mode = "h1_m15_structural_trend"
        reason = "H1 structural trend agrees with M15 structural trend"
    elif structural_opposition:
        mode = "structural_trend_conflict"
        reason = "H1 structural trend and M15 structural trend disagree"
    elif h1_trend_with_m15_candle:
        mode = "h1_trend_current_m15_bias"
        reason = "H1 structural trend agrees with current-H1 M15 candle bias while M15 structure is incomplete"
    elif candle_fallback:
        mode = "candle_bias_fallback"
        reason = "H1 and current-H1 M15 candle bias agree while structural trend is incomplete"
    else:
        mode = "not_aligned"
        reason = "H1/M15 structure and current candle bias do not agree"

    return {
        "confirmed": confirmed,
        "direction": "buy" if confirmed and direction_trend == "bullish" else "sell" if confirmed and direction_trend == "bearish" else None,
        "h1_bias": h1_bias,
        "m15_current_h1_bias": m15_bias,
        "h1_trend": trend_h1,
        "m15_trend": trend_m15,
        "h1_candles_used": len(h1_window),
        "m15_candles_used": len(m15_window),
        "structural_alignment": structural_alignment,
        "structural_opposition": structural_opposition,
        "candle_alignment": candle_alignment,
        "candle_fallback": candle_fallback,
        "current_bias_agrees_with_trend": bool(direction_trend and direction_trend == h1_bias == m15_bias),
        "alignment_mode": mode,
        "alignment_reason": reason,
        "rule": "Standard alignment: H1 structural trend must align with M15 structural trend; current-H1 M15 candle bias is evidence and fallback, not an automatic hard block during pullback",
    }


def _zone_contains_price(zone, price):
    if not isinstance(zone, dict):
        return False
    if "low" in zone and "high" in zone:
        low = float(zone.get("low", 0.0) or 0.0)
        high = float(zone.get("high", 0.0) or 0.0)
        return min(low, high) <= price <= max(low, high)
    prices = zone.get("prices")
    if isinstance(prices, (list, tuple)) and len(prices) >= 2:
        low = float(prices[0])
        high = float(prices[1])
        return min(low, high) <= price <= max(low, high)
    level = zone.get("level")
    if level is not None:
        return abs(float(level) - price) <= max(abs(price) * 0.0005, 1e-9)
    return False


def _trade_direction(value):
    text = str(value or "").lower()
    if text in ("buy", "bullish", "long"):
        return "buy"
    if text in ("sell", "bearish", "short"):
        return "sell"
    return None


def _direction_matches(concept_direction, trade_direction):
    return bool(_trade_direction(concept_direction) and _trade_direction(concept_direction) == _trade_direction(trade_direction))


def _background_reference_levels(state):
    candles = (state or {}).get("recent_candles") or []
    if not candles:
        return {}
    previous = candles[-2] if len(candles) >= 2 else candles[-1]
    return {
        "pdh": float(previous.get("high", 0.0) or 0.0),
        "pdl": float(previous.get("low", 0.0) or 0.0),
        "pdc": float(previous.get("close", 0.0) or 0.0),
        "pdo": float(previous.get("open", 0.0) or 0.0),
        "source_timeframe": (state or {}).get("timeframe"),
        "source": "selected_background_context",
    }


def _opening_gap_from_state(state, price, label, timeframe):
    candles = (state or {}).get("recent_candles") or []
    timeframe = str(timeframe or (state or {}).get("timeframe") or "").upper()
    if len(candles) < 2:
        return {
            "available": False,
            "active": False,
            "label": label,
            "timeframe": timeframe,
            "reason": "not_enough_candles",
        }

    previous = candles[-2]
    current = candles[-1]
    previous_close = float(previous.get("close", 0.0) or 0.0)
    current_open = float(current.get("open", 0.0) or 0.0)
    current_high = float(current.get("high", current_open) or current_open)
    current_low = float(current.get("low", current_open) or current_open)
    if previous_close <= 0 or current_open <= 0:
        return {
            "available": False,
            "active": False,
            "label": label,
            "timeframe": timeframe,
            "reason": "invalid_open_or_previous_close",
        }
    if current_open == previous_close:
        return {
            "available": True,
            "active": False,
            "label": label,
            "timeframe": timeframe,
            "direction": "none",
            "filled": True,
            "reason": "no_opening_gap",
        }

    gap_low = min(previous_close, current_open)
    gap_high = max(previous_close, current_open)
    gap_range = gap_high - gap_low
    direction = "bullish" if current_open > previous_close else "bearish"
    price = float(price or 0.0)
    price_in_gap = gap_low <= price <= gap_high
    touched = current_high >= gap_low and current_low <= gap_high
    filled = current_low <= gap_low and current_high >= gap_high
    return {
        "available": True,
        "active": True,
        "label": label,
        "timeframe": timeframe,
        "direction": direction,
        "previous_close": previous_close,
        "current_open": current_open,
        "low": gap_low,
        "high": gap_high,
        "midpoint": gap_low + gap_range * 0.5,
        "levels": {
            "0.0": gap_low,
            "0.25": gap_low + gap_range * 0.25,
            "0.5": gap_low + gap_range * 0.5,
            "0.75": gap_low + gap_range * 0.75,
            "1.0": gap_high,
        },
        "price_in_gap": price_in_gap,
        "touched": touched,
        "filled": filled,
        "current_price": price,
        "source": f"{label}_{timeframe}_previous_close_to_current_open",
    }


def _visual_live_concepts(symbol, price, overall_trend, timeframe_states, reference_levels=None):
    """Compute live visual Fib, Sweet Zone, and Judas Swing on H1/M15/M5."""
    visual_by_timeframe = {}
    sweet_candidates = []
    judas_candidates = []
    seen = set()
    trade_direction = _trade_direction(overall_trend)
    tolerance = float(os.getenv("VISUAL_ZONE_TOLERANCE_RATIO", os.getenv("LIQUIDITY_TOLERANCE_RATIO", "0.0015")))
    sweet_lookback = _env_int("SWEET_ZONE_LOOKBACK", 10, minimum=5, maximum=30)
    timeframe_priority = {"H1": 0, "M15": 1, "M5": 2, "M1": 3}

    for timeframe, state in timeframe_states:
        timeframe = str(timeframe or "").upper()
        if not timeframe or timeframe in seen or not isinstance(state, dict):
            continue
        seen.add(timeframe)
        candles = (
            (state.get("concept_windows") or {}).get("htf_context")
            or state.get("recent_candles")
            or []
        )
        trend = state.get("trend") or overall_trend
        direction = _trade_direction(trend) or trade_direction
        visual = get_visual_entry_zones(
            candles,
            direction or trend,
            symbol=symbol,
            timeframe=timeframe,
            reference_levels=reference_levels if reference_levels is not None else None,
            include_pdh_pdl=True,
        )
        visual["price_position"] = visual_price_position(price, visual, direction, tolerance=tolerance)
        visual_by_timeframe[timeframe] = visual
        state["visual_fib"] = visual

        sweet = detect_sweet_zone(candles, direction or trend, lookback=sweet_lookback)
        sweet["timeframe"] = timeframe
        sweet["enter_now"] = should_enter_on_continuation(
            sweet,
            price,
            structure_level=(visual.get("swing_zones") or {}).get("equilibrium"),
        )
        sweet["direction_matches_trade"] = _direction_matches(sweet.get("direction"), trade_direction)
        state["sweet_zone"] = sweet
        sweet_candidates.append(sweet)

        judas = detect_judas_swing(candles, symbol=symbol, purge_tolerance=tolerance, timeframe=timeframe)
        judas["enter_now"] = should_enter_on_judas_reversal(judas, price)
        judas["direction_matches_trade"] = _direction_matches(judas.get("direction"), trade_direction)
        state["judas_swing"] = judas
        judas_candidates.append(judas)

    sweet_candidates = sorted(
        sweet_candidates,
        key=lambda item: (
            not bool(item.get("enter_now")),
            not bool(item.get("in_sweet_zone")),
            -float(item.get("strength", 0.0) or 0.0),
            timeframe_priority.get(str(item.get("timeframe") or "").upper(), 99),
        ),
    )
    judas_candidates = sorted(
        judas_candidates,
        key=lambda item: (
            not bool(item.get("enter_now")),
            not bool(item.get("is_judas_swing")),
            -float(item.get("reversal_strength", 0.0) or 0.0),
            timeframe_priority.get(str(item.get("timeframe") or "").upper(), 99),
        ),
    )
    return {
        "live": True,
        "source": "active_h1_m15_m5_schedule",
        "trade_direction": trade_direction,
        "timeframes": list(visual_by_timeframe.keys()),
        "visual_fib": visual_by_timeframe,
        "sweet_zone": sweet_candidates[0] if sweet_candidates else {},
        "judas_swing": judas_candidates[0] if judas_candidates else {},
        "sweet_zone_candidates": sweet_candidates,
        "judas_swing_candidates": judas_candidates,
    }


def _previous_day_context(daily_state, price, timeframe="D1", fallback_used=False, primary_timeframe="D1"):
    source_timeframe = str(timeframe or "D1").upper()
    primary_timeframe = str(primary_timeframe or "D1").upper()
    role = "background_fallback" if fallback_used else "background_only"
    candles = daily_state.get("recent_candles") or []
    if not candles:
        return {
            "available": False,
            "role": role,
            "source_timeframe": source_timeframe,
            "primary_timeframe": primary_timeframe,
            "fallback_used": bool(fallback_used),
            "background_candle_label": (
                "previous_day"
                if source_timeframe == "D1"
                else f"previous_{source_timeframe.lower()}_candle"
            ),
            "rule": (
                f"{source_timeframe} background context unavailable; "
                "H1 remains the highest active trading timeframe"
            ),
        }
    previous = candles[-2] if len(candles) >= 2 else candles[-1]
    before = candles[-3] if len(candles) >= 3 else None
    previous_close = float(previous.get("close", 0.0) or 0.0)
    previous_direction = _candle_direction(previous)
    before_direction = _candle_direction(before) if before else None
    previous_range = max(float(previous.get("high", 0.0) or 0.0) - float(previous.get("low", 0.0) or 0.0), 1e-9)
    close_position = (previous_close - float(previous.get("low", 0.0) or 0.0)) / previous_range
    swept_buy_side = bool(
        before
        and float(previous.get("high", 0.0) or 0.0) > float(before.get("high", 0.0) or 0.0)
        and previous_close < float(before.get("high", 0.0) or 0.0)
    )
    swept_sell_side = bool(
        before
        and float(previous.get("low", 0.0) or 0.0) < float(before.get("low", 0.0) or 0.0)
        and previous_close > float(before.get("low", 0.0) or 0.0)
    )
    trend = str(daily_state.get("trend") or "").lower()
    continuing = previous_direction == trend if trend in ("bullish", "bearish") else False
    reversing = bool((swept_buy_side or swept_sell_side) and previous_direction and previous_direction != before_direction)
    chasing_liquidity = bool(
        (previous_direction == "bullish" and close_position >= 0.75)
        or (previous_direction == "bearish" and close_position <= 0.25)
    )
    fvg_hits = [
        {**zone, "timeframe": zone.get("timeframe", source_timeframe)}
        for zone in daily_state.get("fvgs") or []
        if _zone_contains_price(zone, previous_close)
    ]
    ob_hits = [
        {**zone, "timeframe": zone.get("timeframe", source_timeframe)}
        for zone in daily_state.get("order_blocks") or []
        if _zone_contains_price(zone, previous_close)
    ]
    return {
        "available": True,
        "role": role,
        "source_timeframe": source_timeframe,
        "primary_timeframe": primary_timeframe,
        "fallback_used": bool(fallback_used),
        "background_candle_label": (
            "previous_day"
            if source_timeframe == "D1"
            else f"previous_{source_timeframe.lower()}_candle"
        ),
        "previous_day_direction": previous_direction,
        "previous_day_close": previous_close,
        "previous_day_close_in_fvg": bool(fvg_hits),
        "previous_day_close_in_order_block": bool(ob_hits),
        "fvg_hits": fvg_hits[:3],
        "order_block_hits": ob_hits[:3],
        "swept_buy_side_liquidity": swept_buy_side,
        "swept_sell_side_liquidity": swept_sell_side,
        "chasing_liquidity": chasing_liquidity,
        "continuing_daily_trend": continuing,
        "reversing_after_daily_sweep": reversing,
        "daily_trend": trend or None,
        "rule": (
            f"{source_timeframe} checks the previous completed background candle for FVG/OB, "
            "liquidity chase, swept liquidity, continuation, or reversal; "
            "it does not replace H1 trend"
        ),
    }


def _select_background_context(primary_state, fallback_state, price, primary_timeframe="D1", fallback_timeframe="H4"):
    primary_context = _previous_day_context(
        primary_state,
        price,
        timeframe=primary_timeframe,
        fallback_used=False,
        primary_timeframe=primary_timeframe,
    )
    primary_has_signal = bool(
        primary_context.get("available")
        and (
            primary_context.get("previous_day_close_in_fvg")
            or primary_context.get("previous_day_close_in_order_block")
            or primary_context.get("swept_buy_side_liquidity")
            or primary_context.get("swept_sell_side_liquidity")
            or primary_context.get("chasing_liquidity")
            or primary_context.get("continuing_daily_trend")
            or primary_context.get("reversing_after_daily_sweep")
        )
    )
    if primary_has_signal:
        return primary_state, primary_context

    fallback_timeframe = str(fallback_timeframe or "").upper()
    fallback_candles = fallback_state.get("recent_candles") if isinstance(fallback_state, dict) else None
    if fallback_timeframe and fallback_candles:
        fallback_context = _previous_day_context(
            fallback_state,
            price,
            timeframe=fallback_timeframe,
            fallback_used=True,
            primary_timeframe=primary_timeframe,
        )
        fallback_has_signal = bool(
            fallback_context.get("available")
            and (
                fallback_context.get("previous_day_close_in_fvg")
                or fallback_context.get("previous_day_close_in_order_block")
                or fallback_context.get("swept_buy_side_liquidity")
                or fallback_context.get("swept_sell_side_liquidity")
                or fallback_context.get("chasing_liquidity")
                or fallback_context.get("continuing_daily_trend")
                or fallback_context.get("reversing_after_daily_sweep")
            )
        )
        if fallback_context.get("available") and (fallback_has_signal or not primary_context.get("available")):
            fallback_context["fallback_reason"] = (
                f"{str(primary_timeframe).upper()}_context_unavailable"
                if not primary_context.get("available")
                else f"{str(primary_timeframe).upper()}_context_has_no_actionable_background_signal"
            )
            return fallback_state, fallback_context

    if primary_context.get("available"):
        primary_context["fallback_attempted"] = bool(fallback_timeframe)
        primary_context["fallback_reason"] = f"{str(primary_timeframe).upper()}_context_has_no_actionable_background_signal"
    return primary_state, primary_context


def _external_liquidity(*states):
    """Build external liquidity from the active intraday schedule."""
    result = {"EQH": [], "EQL": []}
    seen = set()
    for timeframe, state in states:
        for swing in (state.get("swings") or [])[-30:]:
            if not isinstance(swing, dict) or swing.get("type") not in ("high", "low"):
                continue
            level = float(swing["price"])
            identity = (swing["type"], round(level, 10), timeframe)
            if identity in seen:
                continue
            seen.add(identity)
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
    return result


def _session_trade_analysis(symbol, execution_state):
    candles = execution_state.get("recent_candles") or []
    timestamp = candles[-1].get("time") if candles else None
    return {
        "symbol": symbol,
        "session": session_name(timestamp),
        "asia": in_asia_session(timestamp),
        "london_killzone": in_london_session(timestamp),
        "newyork_killzone": in_newyork_session(timestamp),
        "execution_session_open": intelligence_session_open(timestamp),
        "rule": "Session is analyzed per symbol; it supports timing but structure still controls execution",
    }


def _detect_htf_liquidity_sweep(symbol, htf_tf, price, direction):
    from ict_concepts.liquidity import detect_liquidity_zones
    from ict_concepts.market_structure import get_swings
    swings = get_swings(symbol, timeframe=htf_tf)
    liquidity = detect_liquidity_zones(swings) or {"EQL": [], "EQH": []}
    from strategy.liquidity_filter import liquidity_taken
    recent_candles = _fetch_recent_candles(symbol, htf_tf, bars=8)
    return liquidity_taken(price, liquidity, direction, recent_candles=recent_candles)


def _build_topdown_result(
    symbol, price,
    weekly_tf, daily_tf, daily_fallback_tf,
    htf, mtf, ltf, execution_tf, m1_fallback_tf,
    atr_period, candle_windows,
):
    """FIX 14: Extract core top-down analysis into a focused helper.

    Orchestrates per-timeframe analysis, alignment, background context,
    visual concepts, and result assembly.
    """
    requested_timeframes = []
    for tf in [weekly_tf, daily_tf, daily_fallback_tf, htf, mtf, ltf, execution_tf, m1_fallback_tf]:
        if tf and tf not in requested_timeframes:
            requested_timeframes.append(tf)

    analysis = {
        tf: _analyze_timeframe(symbol, tf, price, candle_windows["fetch_per_timeframe"], atr_period, candle_windows)
        for tf in requested_timeframes
    }

    weekly_state = analysis.get(weekly_tf, {}) if weekly_tf else {}
    daily_state = analysis[daily_tf]
    daily_fallback_state = analysis.get(daily_fallback_tf, {}) if daily_fallback_tf else {}
    h1_state = analysis[htf]
    m30_state = analysis[mtf]
    m15_state = analysis[ltf]
    execution_state = analysis[execution_tf]
    m1_state = analysis.get(m1_fallback_tf, {}) if m1_fallback_tf else {}

    liquidity_sources = []
    seen_liq = set()
    for tf_name, state in ((htf, h1_state), (mtf, m30_state), (ltf, m15_state), (execution_tf, execution_state)):
        key = str(tf_name).upper()
        if key in seen_liq:
            continue
        seen_liq.add(key)
        liquidity_sources.append((key, state))
    external_liquidity = _external_liquidity(*liquidity_sources)
    for state in (h1_state, m30_state, m15_state, execution_state):
        state["external_liquidity"] = external_liquidity
    h1_state["liquidity"] = external_liquidity

    h1_m15_alignment = _h1_m15_candle_alignment(h1_state, m30_state)
    if h1_m15_alignment.get("confirmed") and h1_m15_alignment.get("direction"):
        overall_trend = "bullish" if h1_m15_alignment["direction"] == "buy" else "bearish"
    else:
        h1_trend = h1_state.get("trend")
        overall_trend = h1_trend if h1_trend in ("bullish", "bearish") else _majority_trend([h1_state, m30_state, m15_state])

    context_alignment = "aligned" if h1_m15_alignment.get("confirmed") else "mixed"
    background_state, daily_context = _select_background_context(
        daily_state, daily_fallback_state, price,
        primary_timeframe=daily_tf, fallback_timeframe=daily_fallback_tf,
    )
    opening_gaps = {
        "NDOG": _opening_gap_from_state(daily_state, price, "NDOG", daily_tf),
        "NWOG": _opening_gap_from_state(weekly_state, price, "NWOG", weekly_tf),
    }
    h1_state["h1_m15_alignment"] = h1_m15_alignment
    m30_state["h1_m15_alignment"] = h1_m15_alignment

    htf_sweep = _detect_htf_liquidity_sweep(symbol, htf, price, "buy" if overall_trend == "bullish" else "sell")

    m5_candles = (
        execution_state.get("recent_candles")
        if execution_tf == "M5"
        else _fetch_recent_candles(symbol, "M5", bars=_standard_fetch_bars("M5", candle_windows["fetch_per_timeframe"]))
    )
    m1_candles = (
        m1_state.get("recent_candles")
        or _fetch_recent_candles(symbol, m1_fallback_tf, bars=_standard_fetch_bars(m1_fallback_tf, candle_windows["fetch_per_timeframe"]))
    )
    visual_concepts = _visual_live_concepts(
        symbol, price, overall_trend,
        ((htf, h1_state), (mtf, m30_state), (ltf, m15_state), (execution_tf, execution_state)),
        reference_levels=_background_reference_levels(background_state),
    )

    return {
        "overall_trend": overall_trend,
        "topdown": {
            "trend": overall_trend,
            "weekly_trend": weekly_state.get("trend"),
            "daily_trend": daily_state.get("trend"),
            "background_trend": background_state.get("trend"),
            "background_timeframe": daily_context.get("source_timeframe"),
            "h1_trend": h1_state.get("trend"),
            "m30_trend": m30_state.get("trend") if str(mtf).upper() == "M30" else "not_used",
            "m15_trend": (
                m30_state.get("trend") if str(mtf).upper() == "M15"
                else m15_state.get("trend") if str(ltf).upper() == "M15"
                else "not_used"
            ),
            "m5_trend": (
                execution_state.get("trend") if str(execution_tf).upper() == "M5"
                else m15_state.get("trend") if str(ltf).upper() == "M5"
                else "not_used"
            ),
            "execution_trend": execution_state.get("trend"),
            "context_alignment": context_alignment,
            "h1_m15_alignment": h1_m15_alignment,
            "previous_day_context": daily_context,
            "opening_gaps": opening_gaps,
            "visual_concepts": visual_concepts,
        },
        "price": price,
        "timeframes": {
            "WEEKLY": weekly_tf,
            "DAILY": daily_tf,
            "DAILY_CONTEXT_FALLBACK": daily_fallback_tf,
            "BACKGROUND_CONTEXT": daily_context.get("source_timeframe"),
            "HTF": htf,
            "MTF": mtf,
            "LTF": ltf,
            "EXECUTION": execution_tf,
            "M1_FALLBACK": m1_fallback_tf,
        },
        "candle_windows": candle_windows,
        "candle_window_usage": {
            "fetch_per_timeframe": candle_windows["fetch_per_timeframe"],
            "htf_narrative": candle_windows["htf_context"],
            "external_liquidity": candle_windows["external_liquidity"],
            "market_structure_mss_bos": candle_windows["structure"],
            "true_fvg_order_block_context": candle_windows["true_fvg_ob_context"],
            "smt_divergence": candle_windows["smt"],
            "liquidity_sweep": candle_windows["sweep"],
            "displacement": candle_windows["displacement"],
            "m1_m5_confirmation": candle_windows["execution_confirmation"],
        },
        "h1_m15_alignment": h1_m15_alignment,
        "previous_day_context": daily_context,
        "opening_gaps": opening_gaps,
        "visual_concepts": visual_concepts,
        "session_analysis": _session_trade_analysis(symbol, execution_state),
        "brief_context": {
            "weekly": weekly_state,
            "daily": daily_state,
            "background": background_state,
            "alignment": context_alignment,
            "previous_day": daily_context,
            "opening_gaps": opening_gaps,
            "visual_concepts": visual_concepts,
        },
        "WEEKLY": weekly_state,
        "DAILY": daily_state,
        "DAILY_CONTEXT": background_state,
        "DAILY_CONTEXT_FALLBACK": daily_fallback_state,
        "HTF": h1_state,
        "MTF": m30_state,
        "LTF": m15_state,
        "EXECUTION": execution_state,
        "M1": m1_state,
        "m5_candles": m5_candles,
        "m1_candles": m1_candles,
        "external_liquidity": external_liquidity,
        "htf_sweep": htf_sweep,
        "volume_alignment": execution_state["volume_boost"],
        "sma_alignment": execution_state["above_sma"] if overall_trend == "bullish" else not execution_state["above_sma"],
        "correlated": {},
    }


def analyze_market_top_down(
    symbol,
    price,
    htf=None,
    mtf=None,
    ltf=None
):
    """FIX 14: Delegates to _build_topdown_result for the heavy lifting."""
    weekly_tf = os.getenv("WEEKLY_TIMEFRAME", "W1")
    daily_tf = os.getenv("DAILY_TIMEFRAME", os.getenv("CONTEXT_DAILY_TIMEFRAME", "D1"))
    daily_fallback_tf = os.getenv("DAILY_CONTEXT_FALLBACK_TIMEFRAME", os.getenv("D1_CONTEXT_FALLBACK_TIMEFRAME", "H4"))
    htf = htf or os.getenv("HTF_TIMEFRAME", "H1")
    mtf = mtf or os.getenv("MTF_TIMEFRAME", "M15")
    ltf = ltf or os.getenv("LTF_TIMEFRAME", "M5")
    execution_tf = os.getenv("EXECUTION_TIMEFRAME", "M5")
    m1_fallback_tf = os.getenv("M1_FALLBACK_TIMEFRAME", "M1")
    candle_windows = _concept_candle_windows()
    atr_period = max(5, int(os.getenv("ENTRY_ATR_PERIOD", "14")))

    return _build_topdown_result(
        symbol=symbol,
        price=price,
        weekly_tf=weekly_tf,
        daily_tf=daily_tf,
        daily_fallback_tf=daily_fallback_tf,
        htf=htf,
        mtf=mtf,
        ltf=ltf,
        execution_tf=execution_tf,
        m1_fallback_tf=m1_fallback_tf,
        atr_period=atr_period,
        candle_windows=candle_windows,
    )
