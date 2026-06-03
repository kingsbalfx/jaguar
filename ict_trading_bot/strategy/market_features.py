"""
MARKET FEATURE EXTRACTION (ICT → MATH)
Adds AMD, Turtle Soup, Silver Bullet, Opening Candle Bias,
Weekly Opening Gap, Daily Opening Gap, Weekly Profile, and True Daily Bias.
"""

from strategy.amd_detector import detect_amd
from strategy.turtle_soup_detector import detect_turtle_soup
from utils.sessions import in_newyork_session
import datetime as dt

try:
    import MetaTrader5 as mt5
except Exception:
    mt5 = None


def _opening_candle_bias(symbol, current_price, trend, topdown_analysis):
    from utils.symbol_profile import infer_asset_class
    if infer_asset_class(symbol) == "crypto":
        return True

    daily_state = topdown_analysis.get("DAILY") or {}
    candles = daily_state.get("recent_candles") or []
    if len(candles) < 1:
        return True

    last_daily = candles[-1]
    try:
        high = float(last_daily["high"])
        low = float(last_daily["low"])
    except Exception:
        return True

    if high <= low:
        return True

    midpoint = (high + low) / 2.0
    return current_price > midpoint if trend == "bullish" else current_price < midpoint


def _detect_weekly_opening_gap(symbol):
    if mt5 is None:
        return {"direction": "none", "filled": True}

    try:
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_W1, 0, 2)
        if rates is None or len(rates) < 2:
            return {"direction": "none", "filled": True}

        prev_close = float(rates[0]["close"])
        current_open = float(rates[1]["open"])
        if current_open > prev_close:
            direction = "bullish"
            gap_low = prev_close
            gap_high = current_open
        elif current_open < prev_close:
            direction = "bearish"
            gap_low = current_open
            gap_high = prev_close
        else:
            return {"direction": "none", "filled": True}

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return {"direction": "none", "filled": True}
        current_price = (tick.ask + tick.bid) / 2.0

        filled = (gap_low <= current_price <= gap_high)
        return {
            "direction": direction,
            "gap_low": round(gap_low, 5),
            "gap_high": round(gap_high, 5),
            "filled": filled,
            "current_price": current_price,
        }
    except Exception:
        return {"direction": "none", "filled": True}


def _detect_daily_opening_gap(symbol):
    from utils.symbol_profile import infer_asset_class
    if infer_asset_class(symbol) == "crypto":
        return {"direction": "none", "filled": True}

    if mt5 is None:
        return {"direction": "none", "filled": True}

    try:
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 2)
        if rates is None or len(rates) < 2:
            return {"direction": "none", "filled": True}

        prev_close = float(rates[0]["close"])
        current_open = float(rates[1]["open"])
        if current_open > prev_close:
            direction = "bullish"
            gap_low = prev_close
            gap_high = current_open
        elif current_open < prev_close:
            direction = "bearish"
            gap_low = current_open
            gap_high = prev_close
        else:
            return {"direction": "none", "filled": True}

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return {"direction": "none", "filled": True}
        current_price = (tick.ask + tick.bid) / 2.0

        filled = (gap_low <= current_price <= gap_high)
        return {
            "direction": direction,
            "gap_low": round(gap_low, 5),
            "gap_high": round(gap_high, 5),
            "filled": filled,
            "current_price": current_price,
        }
    except Exception:
        return {"direction": "none", "filled": True}


def _weekly_profile(symbol):
    """
    Determine the weekly bias from the previous completed weekly candle.
    Returns a dict with 'bias' (bullish/bearish) and 'expansion' (True if range > average).
    """
    if mt5 is None:
        return {"bias": "neutral", "expansion": False}
    try:
        # Get last 4 weekly candles to compute average range
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_W1, 0, 5)
        if rates is None or len(rates) < 2:
            return {"bias": "neutral", "expansion": False}

        # Last completed week is rates[-2] (current week is rates[-1] if incomplete)
        prev_week = rates[-2]
        open_p = float(prev_week["open"])
        close_p = float(prev_week["close"])
        high_p = float(prev_week["high"])
        low_p = float(prev_week["low"])

        bias = "bullish" if close_p > open_p else "bearish" if close_p < open_p else "neutral"

        # Average range of last 4 weeks (excluding current)
        ranges = []
        for i in range(-4, -1):
            r = rates[i]
            ranges.append(float(r["high"]) - float(r["low"]))
        avg_range = sum(ranges) / len(ranges) if ranges else 0.0
        current_range = high_p - low_p
        expansion = current_range > avg_range * 1.1

        return {
            "bias": bias,
            "expansion": expansion,
            "weekly_high": high_p,
            "weekly_low": low_p,
            "weekly_close": close_p,
        }
    except Exception:
        return {"bias": "neutral", "expansion": False}


def extract_features(symbol, current_price, topdown_analysis):
    mtf = topdown_analysis.get("MTF") or {}
    ltf = topdown_analysis.get("LTF") or {}
    exec_ = topdown_analysis.get("EXECUTION") or {}

    candles = exec_.get("recent_candles") or ltf.get("recent_candles") or []
    if len(candles) < 3:
        return None

    last = candles[-1]
    body = abs(float(last["close"]) - float(last["open"]))
    candle_range = max(float(last["high"]) - float(last["low"]), 1e-9)
    body_ratio = body / candle_range

    ranges = [float(c["high"]) - float(c["low"]) for c in candles[-10:]]
    avg_range = sum(ranges) / len(ranges) if ranges else candle_range
    range_percentile = candle_range / max(avg_range, 1e-9)

    upper_wick = max(float(last["high"]) - max(float(last["open"]), float(last["close"])), 0)
    lower_wick = max(min(float(last["open"]), float(last["close"])) - float(last["low"]), 0)
    wick_upper_ratio = upper_wick / max(body, 1e-9)
    wick_lower_ratio = lower_wick / max(body, 1e-9)

    volumes = [float(c.get("tick_volume", c.get("volume", 0))) for c in candles[-10:]]
    avg_vol = sum(volumes) / len(volumes) if volumes else 1.0
    last_vol = volumes[-1] if volumes else 1.0
    volume_spike = last_vol >= avg_vol * 1.3

    atr = float(topdown_analysis.get("HTF", {}).get("atr", 0) or 0)

    from strategy.setup_confirmations import liquidity_sweep_or_swing, bos_setup
    trend = topdown_analysis.get("overall_trend", "neutral")
    direction = "buy" if trend == "bullish" else "sell"

    liq_state = liquidity_sweep_or_swing(current_price, topdown_analysis, direction)
    sweep = bool(liq_state.get("confirmed") or liq_state.get("liquidity_sweep"))
    displacement = bool(liq_state.get("displacement"))

    bos_state = bos_setup(topdown_analysis, trend)
    bos = bool(bos_state.get("confirmed"))

    fvgs = ltf.get("fvgs", []) or exec_.get("fvgs", [])
    fvg_exists = any(fvg.get("active") for fvg in fvgs if isinstance(fvg, dict))

    obs = mtf.get("order_blocks", []) or ltf.get("order_blocks", [])
    ob_exists = any(ob.get("fresh") for ob in obs if isinstance(ob, dict))

    # Silver Bullet window (NY 10:00‑11:00 AM UTC)
    now_utc = dt.datetime.now(dt.timezone.utc)
    silver_bullet = (now_utc.hour == 14 and 10 <= now_utc.minute < 60)

    # AMD detection using M15 candles
    m15_candles = topdown_analysis.get("m15_candles") or ltf.get("recent_candles") or []
    amd = detect_amd(m15_candles, direction) if m15_candles else False

    # Turtle Soup on M5
    m5_candles = topdown_analysis.get("m5_candles") or []
    turtle = detect_turtle_soup(m5_candles, direction) if m5_candles else False

    # Opening candle bias (midnight open midpoint)
    opening_bias = _opening_candle_bias(symbol, current_price, trend, topdown_analysis)

    # Weekly opening gap
    weekly_gap = _detect_weekly_opening_gap(symbol)

    # Daily opening gap
    daily_gap = _detect_daily_opening_gap(symbol)

    # Weekly profile
    weekly_profile = _weekly_profile(symbol)

    return {
        "body_ratio": round(body_ratio, 3),
        "range_percentile": round(range_percentile, 3),
        "wick_upper_ratio": round(wick_upper_ratio, 3),
        "wick_lower_ratio": round(wick_lower_ratio, 3),
        "volume_spike": volume_spike,
        "atr": round(atr, 6),
        "sweep": sweep,
        "displacement": displacement,
        "bos": bos,
        "fvg_exists": fvg_exists,
        "ob_exists": ob_exists,
        "smt": False,
        "silver_bullet_window": silver_bullet,
        "amd_setup": amd,
        "turtle_soup": turtle,
        "opening_bias_aligned": opening_bias,
        "weekly_gap": weekly_gap,
        "daily_gap": daily_gap,
        "weekly_profile": weekly_profile,
    }