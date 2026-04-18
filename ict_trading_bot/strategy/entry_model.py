from ict_concepts.fib import in_discount, in_premium
from strategy.ict_fvg import ict_liquidity_fvg_strategy
from strategy.breakout import breakout_retest_strategy

from utils.symbol_profile import get_entry_profile, infer_asset_class


def body_ratio(c):
    return abs(float(c["close"]) - float(c["open"])) / max((float(c["high"]) - float(c["low"])), 1e-9)


def _normalize_trend(value):
    v = str(value or "").lower().strip()
    if v in ("bullish", "buy", "long"):
        return "bullish"
    if v in ("bearish", "sell", "short"):
        return "bearish"
    return None


def confirm_price_action(data, trend):
    candles = (data or {}).get("candles") or []
    if not isinstance(candles, list) or len(candles) < 3:
        return False

    trend = _normalize_trend(trend) or ""
    c1, c2, c3 = candles[-3], candles[-2], candles[-1]

    if body_ratio(c2) < 0.6:
        return False

    if trend == "bullish":
        return (
            float(c3["close"]) > float(c3["open"])
            and float(c3["low"]) >= float(c2["low"])
            and float(c3["close"]) >= float(c2["close"]) * 0.98
        )
    return (
        float(c3["close"]) < float(c3["open"])
        and float(c3["high"]) <= float(c2["high"])
        and float(c3["close"]) <= float(c2["close"]) * 1.02
    )


def sniper_entry_trigger(data, trend):
    m5 = (data or {}).get("m5_candles") or []
    m1 = (data or {}).get("m1_candles") or []

    if not isinstance(m5, list) or len(m5) < 5:
        return False

    trend = _normalize_trend(trend) or ""
    prev_high = max(float(c["high"]) for c in m5[-5:-2])
    prev_low = min(float(c["low"]) for c in m5[-5:-2])
    last = m5[-1]

    if trend == "bullish":
        bos = float(last["close"]) > prev_high
    else:
        bos = float(last["close"]) < prev_low

    if not bos:
        return False

    if body_ratio(last) < 0.6:
        return False

    if isinstance(m1, list) and len(m1) >= 3:
        c1, c2, c3 = m1[-3], m1[-2], m1[-1]
        if trend == "bullish":
            return float(c3["close"]) > float(c3["open"]) and float(c3["low"]) >= float(c2["low"])
        return float(c3["close"]) < float(c3["open"]) and float(c3["high"]) <= float(c2["high"])

    return True


def m1_liquidity_sweep_entry(data, trend):
    m1 = (data or {}).get("m1_candles") or []
    if not isinstance(m1, list) or len(m1) < 5:
        return False

    trend = _normalize_trend(trend) or ""
    highs = [float(c["high"]) for c in m1[-5:-2]]
    lows = [float(c["low"]) for c in m1[-5:-2]]
    prev_high = max(highs)
    prev_low = min(lows)

    c1, c2, c3 = m1[-3], m1[-2], m1[-1]

    if trend == "bullish":
        sweep = float(c2["low"]) < prev_low
        reversal = (
            float(c3["close"]) > float(c3["open"])
            and float(c3["close"]) > float(c2["high"])
            and body_ratio(c3) > 0.6
        )
        return sweep and reversal

    sweep = float(c2["high"]) > prev_high
    reversal = (
        float(c3["close"]) < float(c3["open"])
        and float(c3["close"]) < float(c2["low"])
        and body_ratio(c3) > 0.6
    )
    return sweep and reversal


def valid_fvg_entry(price, fvg, trend=None):
    if not isinstance(fvg, dict):
        return False
    if fvg.get("low") is None or fvg.get("high") is None:
        return False
    if fvg.get("mitigated") or not fvg.get("active", True):
        return False
    if not fvg.get("size_ok", True) or not fvg.get("context_aligned", True):
        return False
    trend = _normalize_trend(trend)
    if trend and fvg.get("type") and fvg.get("type") != trend:
        return False
    return float(fvg["low"]) <= float(price) <= float(fvg["high"])


def valid_ob_entry(price, ob, trend=None):
    if not isinstance(ob, dict):
        return False
    if ob.get("low") is None or ob.get("high") is None:
        return False
    if ob.get("mitigated") or ob.get("fresh") is False:
        return False
    if float(ob.get("quality", 0.0) or 0.0) < 0.70:
        return False
    trend = _normalize_trend(trend)
    if trend and ob.get("type") and ob.get("type") != trend:
        return False
    if not ob.get("liquidity_sweep_confirmed", False):
        return False
    if not ob.get("institutional_footprint", False):
        return False
    if float(ob.get("displacement", 0.0) or 0.0) < 0.70:
        return False
    return float(ob["low"]) <= float(price) <= float(ob["high"])


def entry_debug_snapshot(data):
    trend = _normalize_trend((data or {}).get("trend"))
    price_action_ok = confirm_price_action(data, trend) if trend else False
    return {
        "liq": bool((data or {}).get("liquidity_sweep")),
        "bos": bool((data or {}).get("bos")),
        "disp": float((data or {}).get("displacement", 0.0) or 0.0),
        "fvg": bool((data or {}).get("fvg") or (data or {}).get("fvgs")),
        "ob": bool((data or {}).get("htf_ob") or (data or {}).get("htf_order_blocks")),
        "price_action": bool(price_action_ok),
    }


def explain_hybrid_failure(data):
    trend = _normalize_trend((data or {}).get("trend"))
    if not trend:
        return "trend"

    if float((data or {}).get("trend_strength", 0.0) or 0.0) < 0.60:
        return "trend_strength"

    if not (data or {}).get("liquidity_sweep"):
        return "no_liquidity_sweep"

    if not (data or {}).get("bos"):
        return "no_bos"

    if float((data or {}).get("displacement", 0.0) or 0.0) < 0.70:
        return "weak_displacement"

    price = float((data or {}).get("price", 0.0) or 0.0)
    fvg = (data or {}).get("fvg")
    ob = (data or {}).get("htf_ob")
    if not valid_fvg_entry(price, fvg, trend):
        fvg = next((item for item in ((data or {}).get("fvgs") or []) if valid_fvg_entry(price, item, trend)), None)
    if not valid_ob_entry(price, ob, trend):
        ob = next(
            (item for item in ((data or {}).get("htf_order_blocks") or []) if valid_ob_entry(price, item, trend)),
            None,
        )
    if not (valid_fvg_entry(price, fvg, trend) or valid_ob_entry(price, ob, trend)):
        return "zone"

    if not confirm_price_action(data, trend):
        return "price_action"

    if not sniper_entry_trigger(data, trend):
        return "m5_sniper"

    if not m1_liquidity_sweep_entry(data, trend):
        return "m1_sweep"

    return "ready"


def _dynamic_stop_loss(data, trend, price):
    trend = _normalize_trend(trend) or ""
    atr = abs(float((data or {}).get("atr", 0.0) or 0.0))
    market_condition = str((data or {}).get("market_condition") or "").lower()
    buffer_atr = atr * (0.35 if market_condition == "volatile" else 0.15)

    sweep_low = None
    sweep_high = None
    m1 = (data or {}).get("m1_candles") or []
    if isinstance(m1, list) and len(m1) >= 3:
        c2 = m1[-2]
        sweep_low = float(c2.get("low")) if c2.get("low") is not None else None
        sweep_high = float(c2.get("high")) if c2.get("high") is not None else None

    swing_low = (data or {}).get("swing_low")
    swing_high = (data or {}).get("swing_high")
    try:
        swing_low = float(swing_low) if swing_low is not None else None
    except Exception:
        swing_low = None
    try:
        swing_high = float(swing_high) if swing_high is not None else None
    except Exception:
        swing_high = None

    if trend == "bullish":
        candidates = [x for x in (sweep_low, swing_low) if isinstance(x, (int, float))]
        anchor = min(candidates) if candidates else (price - max(atr * 2.0, 0.0))
        return round(anchor - buffer_atr, 5)

    candidates = [x for x in (sweep_high, swing_high) if isinstance(x, (int, float))]
    anchor = max(candidates) if candidates else (price + max(atr * 2.0, 0.0))
    return round(anchor + buffer_atr, 5)


def hybrid_entry_model(data):
    """
    FINAL ENTRY LOGIC (Strict, multi-stage):
      1) Liquidity sweep required
      2) BOS required
      3) Displacement strength required (>= 0.7)
      4) Retest into FVG or OB zone (body, not wick)
      5) Multi-candle price action confirmation
      6) Sniper timing: M5 micro BOS + displacement
      7) Final trigger: M1 liquidity sweep reversal
    """

    if not isinstance(data, dict):
        return None

    trend = _normalize_trend(data.get("trend"))
    if trend not in ("bullish", "bearish"):
        return None

    price = float(data.get("price", 0.0) or 0.0)

    # ADAPTIVE TREND STRENGTH: Allow slightly lower strength (0.50) if market condition is 'normal' or 'pullback'
    # This prevents the "Wait for entry: trend strength" spam during valid ICT retracements.
    min_strength = 0.50 if data.get("market_condition") in ("normal", "pullback") else 0.60
    
    if float(data.get("trend_strength", 0.0) or 0.0) < min_strength:
        return None

    if not data.get("liquidity_sweep"):
        return None

    if not data.get("bos"):
        return None

    if float(data.get("displacement", 0.0) or 0.0) < 0.70:
        return None

    # Zone validation: FVG OR OB (accept either pre-selected zones or full lists)
    fvg = data.get("fvg")
    ob = data.get("htf_ob")

    if not valid_fvg_entry(price, fvg, trend):
        fvg = next((item for item in (data.get("fvgs") or []) if valid_fvg_entry(price, item, trend)), None)
    if not valid_ob_entry(price, ob, trend):
        ob = next((item for item in (data.get("htf_order_blocks") or []) if valid_ob_entry(price, item, trend)), None)
    if not (valid_fvg_entry(price, fvg, trend) or valid_ob_entry(price, ob, trend)):
        return None

    if not confirm_price_action(data, trend):
        return None

    if not sniper_entry_trigger(data, trend):
        return None

    if not m1_liquidity_sweep_entry(data, trend):
        return None

    sl = _dynamic_stop_loss(data, trend, price)

    return {
        "type": "HYBRID_ENTRY",
        "direction": "buy" if trend == "bullish" else "sell",
        "price": price,
        "sl": sl,
        "fvg": fvg,
        "htf_ob": ob,
        "trend": trend,
        "reason": "Liquidity + BOS + Displacement + Zone Retest + Multi-candle PA + Sniper Timing",
    }


def _resolve_zone_bounds(trend, fib_levels, symbol=None, atr=None):
    f00 = fib_levels.get("0.0") if isinstance(fib_levels, dict) else None
    f05 = fib_levels.get("0.5") if isinstance(fib_levels, dict) else None
    f10 = fib_levels.get("1.0") if isinstance(fib_levels, dict) else None
    profile = get_entry_profile(symbol)
    fib_buffer_ratio = profile["fib_buffer_ratio"]
    atr_buffer_multiplier = profile["atr_buffer_multiplier"]
    atr = abs(float(atr or 0.0))

    if trend == "bullish":
        if f00 is None or f05 is None:
            return None
        lower = float(f00)
        upper = float(f05)
    elif trend == "bearish":
        if f05 is None or f10 is None:
            return None
        lower = float(f05)
        upper = float(f10)
    else:
        return None

    zone_size = max(upper - lower, 0.0)
    adaptive_buffer = max(zone_size * fib_buffer_ratio, atr * atr_buffer_multiplier)
    return {
        "lower": lower - adaptive_buffer,
        "upper": upper + adaptive_buffer,
        "buffer": adaptive_buffer,
    }


def _is_valid_fvg(fvg, trend, price):
    if not isinstance(fvg, dict):
        return False
    if fvg.get("type") != trend:
        return False
    if fvg.get("low") is None or fvg.get("high") is None:
        return False
    if fvg.get("mitigated") or not fvg.get("active", True):
        return False
    if not fvg.get("size_ok", True) or not fvg.get("context_aligned", True):
        return False
    return float(fvg["low"]) <= float(price) <= float(fvg["high"])


def _is_valid_order_block(ob, trend, reference_fvg=None, price=None):
    if not isinstance(ob, dict):
        return False
    if ob.get("type") != trend:
        return False
    if ob.get("low") is None or ob.get("high") is None:
        return False
    if not ob.get("liquidity_sweep_confirmed", False):
        return False
    if not ob.get("institutional_footprint", False):
        return False
    if float(ob.get("displacement", 0.0) or 0.0) < 0.70:
        return False

    if isinstance(reference_fvg, dict):
        return float(ob["low"]) <= float(reference_fvg["low"]) and float(reference_fvg["high"]) <= float(ob["high"])

    if price is None:
        return False
    return float(ob["low"]) <= float(price) <= float(ob["high"])


def explain_entry_failure(trend, price, fib_levels, fvgs, htf_order_blocks, symbol=None, atr=None):
    if trend not in ("bullish", "bearish"):
        return "trend"

    bounds = _resolve_zone_bounds(trend, fib_levels, symbol=symbol, atr=atr)
    if not bounds:
        return "fib_missing"
    if not (bounds["lower"] <= price <= bounds["upper"]):
        return "fib_zone"

    valid_fvg = next((fvg for fvg in (fvgs or []) if _is_valid_fvg(fvg, trend, price)), None)
    if not valid_fvg:
        return "valid_fvg"

    valid_ob = next(
        (ob for ob in (htf_order_blocks or []) if _is_valid_order_block(ob, trend, reference_fvg=valid_fvg, price=price)),
        None,
    )
    if not valid_ob:
        return "valid_order_block"

    return "ready"


def generate_entry(data):
    signal = ict_liquidity_fvg_strategy(data)
    if signal:
        return signal

    signal = breakout_retest_strategy(data)
    if signal:
        return signal

    return None


def check_entry(
    trend,
    price,
    fib_levels,
    fvgs,
    htf_order_blocks,
    symbol=None,
    atr=None,
):
    """
    Strict POI validation after the higher-priority setup filters.
    """
    if trend not in ("bullish", "bearish"):
        return None

    bounds = _resolve_zone_bounds(trend, fib_levels, symbol=symbol, atr=atr)
    if not bounds or not (bounds["lower"] <= price <= bounds["upper"]):
        return None

    valid_fvg = next((fvg for fvg in (fvgs or []) if _is_valid_fvg(fvg, trend, price)), None)
    if not valid_fvg:
        return None

    valid_ob = next(
        (ob for ob in (htf_order_blocks or []) if _is_valid_order_block(ob, trend, reference_fvg=valid_fvg, price=price)),
        None,
    )
    if not valid_ob:
        return None

    fib_zone = "discount" if trend == "bullish" and in_discount(price, fib_levels) else "premium" if in_premium(price, fib_levels) else "equilibrium"
    return {
        "type": "ICT_STRUCTURAL_ENTRY",
        "direction": "buy" if trend == "bullish" else "sell",
        "price": price,
        "fvg": valid_fvg,
        "htf_ob": valid_ob,
        "fib_zone": fib_zone,
        "entry_buffer": bounds["buffer"],
        "asset_class": infer_asset_class(symbol),
        "trend": trend,
        "valid_fvg": True,
        "valid_order_block": True,
    }
