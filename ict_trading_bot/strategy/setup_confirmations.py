from utils.sessions import intelligence_session_open

CORE_CONFIRMATION_FLAGS = (
    "liquidity_setup",
    "bos",
    "displacement",
    "fvg",
)


def _direction_to_trend(direction):
    normalized = str(direction or "").lower()
    if normalized in ("buy", "bullish"):
        return "bullish"
    if normalized in ("sell", "bearish"):
        return "bearish"
    return normalized


def _filter_swings(swings, swing_type):
    if not isinstance(swings, list):
        return []
    return [s for s in swings if isinstance(s, dict) and s.get("type") == swing_type]


def _displacement_body_ratio(candles, direction):
    if not isinstance(candles, list) or len(candles) < 2:
        return 0.0

    last = candles[-1]
    prev = candles[-2]
    if not all(key in last and key in prev for key in ("open", "high", "low", "close")):
        return 0.0

    curr_body = abs(float(last["close"]) - float(last["open"]))
    curr_range = max(float(last["high"]) - float(last["low"]), 1e-9)
    body_ratio = curr_body / curr_range

    if str(direction or "").lower() in ("buy", "bullish"):
        if float(last["close"]) <= float(prev["high"]):
            return 0.0
    else:
        if float(last["close"]) >= float(prev["low"]):
            return 0.0

    return round(body_ratio, 3)


def recent_bos(swings, trend):
    highs = _filter_swings(swings, "high")
    lows = _filter_swings(swings, "low")

    if trend == "bullish":
        return len(highs) >= 2 and float(highs[-1]["price"]) > float(highs[-2]["price"])
    if trend == "bearish":
        return len(lows) >= 2 and float(lows[-1]["price"]) < float(lows[-2]["price"])
    return False


def recent_choch(swings, trend):
    highs = _filter_swings(swings, "high")
    lows = _filter_swings(swings, "low")

    if trend == "bullish":
        return len(lows) >= 2 and float(lows[-1]["price"]) < float(lows[-2]["price"])
    if trend == "bearish":
        return len(highs) >= 2 and float(highs[-1]["price"]) > float(highs[-2]["price"])
    return False


def swing_trend_confirmation(swings, trend):
    highs = _filter_swings(swings, "high")
    lows = _filter_swings(swings, "low")

    if trend == "bullish":
        higher_high = len(highs) >= 2 and float(highs[-1]["price"]) > float(highs[-2]["price"])
        higher_low = len(lows) >= 2 and float(lows[-1]["price"]) > float(lows[-2]["price"])
        return higher_high or higher_low

    if trend == "bearish":
        lower_high = len(highs) >= 2 and float(highs[-1]["price"]) < float(highs[-2]["price"])
        lower_low = len(lows) >= 2 and float(lows[-1]["price"]) < float(lows[-2]["price"])
        return lower_high or lower_low

    return False


def bos_setup(analysis, trend):
    trend = _direction_to_trend(trend)
    mtf_swings = (analysis.get("MTF") or {}).get("swings") or []
    ltf_swings = (analysis.get("LTF") or {}).get("swings") or []
    execution_swings = (analysis.get("EXECUTION") or {}).get("swings") or []

    mtf_bos = recent_bos(mtf_swings, trend)
    ltf_bos = recent_bos(ltf_swings, trend)
    execution_bos = recent_bos(execution_swings, trend)
    choch = recent_choch(execution_swings or ltf_swings, trend)

    confirmed = mtf_bos or ltf_bos or execution_bos
    if choch and not confirmed:
        confirmed = True

    return {
        "confirmed": confirmed,
        "mtf_bos": mtf_bos,
        "ltf_bos": ltf_bos,
        "execution_bos": execution_bos,
        "choch": choch,
        "structure_signal": "choch" if choch and not (mtf_bos or ltf_bos or execution_bos) else "bos",
    }


def _external_sweep_sequence(candles, liquidity, direction):
    side = "EQL" if direction == "buy" else "EQH"
    zones = [zone for zone in (liquidity or {}).get(side, []) if isinstance(zone, dict)]
    for sweep_idx in range(max(0, len(candles) - 10), len(candles) - 1):
        sweep_candle = candles[sweep_idx]
        for zone in zones:
            level = float(zone.get("level", 0.0) or 0.0)
            reclaimed = (
                float(sweep_candle["low"]) < level < float(sweep_candle["close"])
                if direction == "buy"
                else float(sweep_candle["high"]) > level > float(sweep_candle["close"])
            )
            if not reclaimed:
                continue
            displacement_idx = sweep_idx + 1
            displacement_candle = candles[displacement_idx]
            body = abs(float(displacement_candle["close"]) - float(displacement_candle["open"]))
            candle_range = max(float(displacement_candle["high"]) - float(displacement_candle["low"]), 1e-9)
            directional = (
                float(displacement_candle["close"]) > float(displacement_candle["open"])
                if direction == "buy"
                else float(displacement_candle["close"]) < float(displacement_candle["open"])
            )
            if directional and body / candle_range >= 0.60:
                return {
                    "confirmed": True,
                    "liquidity_sweep": True,
                    "displacement": True,
                    "displacement_body_ratio": round(body / candle_range, 3),
                    "sweep_index": sweep_idx,
                    "displacement_index": displacement_idx,
                    "swept_level": level,
                    "swept_source": zone.get("source"),
                    "swept_timeframe": zone.get("timeframe"),
                    "sweep_extreme": float(sweep_candle["low"] if direction == "buy" else sweep_candle["high"]),
                    "failed_step": None,
                }
    return _empty_sweep()


def liquidity_sweep_or_swing(price, analysis, direction, external_liquidity=None):
    """
    Strict ICT liquidity sweep detection.
    Requires: a structural swing point, a break (stop‑hunt), a displacement reversal,
    and the swept level must be a significant swing on the H1 (higher timeframe).
    """
    trend = _direction_to_trend(direction)
    mtf = analysis.get("MTF") or {}
    ltf = analysis.get("LTF") or {}
    execution = analysis.get("EXECUTION") or {}
    htf = analysis.get("HTF") or {}

    execution_candles = execution.get("recent_candles") or []
    if len(execution_candles) < 5:
        return _empty_sweep()
    if external_liquidity is not None:
        return _external_sweep_sequence(execution_candles, external_liquidity, direction)

    # Get swing points
    mtf_swings = mtf.get("swings", []) or ltf.get("swings", [])
    if not mtf_swings:
        return _empty_sweep()

    # Find relevant swing level
    if direction == "buy":
        # Find the most recent swing low that is below current price
        swing_lows = [s for s in mtf_swings if s.get("type") == "low"]
        if not swing_lows:
            return _empty_sweep()
        last_low = swing_lows[-1]
        swing_price = float(last_low["price"])
        # Price must have recently (last 3 candles) broken below this low
        recent_lows = [float(c["low"]) for c in execution_candles[-3:]]
        if min(recent_lows) > swing_price:
            return _empty_sweep()
        # Sweep candle is the one that broke the low
        sweep_candle = None
        for c in reversed(execution_candles[-3:]):
            if float(c["low"]) < swing_price:
                sweep_candle = c
                break
        if sweep_candle is None:
            return _empty_sweep()
        # After sweep candle, we need a displacement candle that closes above the swing price
        sweep_idx = execution_candles.index(sweep_candle)
        if sweep_idx + 1 >= len(execution_candles):
            return _empty_sweep()
        disp_candle = execution_candles[sweep_idx + 1]
        disp_body = abs(float(disp_candle["close"]) - float(disp_candle["open"]))
        disp_range = max(float(disp_candle["high"]) - float(disp_candle["low"]), 1e-9)
        if disp_body / disp_range < 0.6:
            return _empty_sweep()
        if float(disp_candle["close"]) <= swing_price:
            return _empty_sweep()
        displacement_body_ratio = disp_body / disp_range
        displacement_idx = sweep_idx + 1
        sweep_extreme = float(sweep_candle["low"])

        # ---- HTF SWING VERIFICATION ----
        htf_swings = htf.get("swings", [])
        if htf_swings:
            htf_lows = [float(s["price"]) for s in htf_swings if s.get("type") == "low"]
            if not any(abs(swing_price - hl) / swing_price < 0.002 for hl in htf_lows):
                return _empty_sweep()
    else:
        swing_highs = [s for s in mtf_swings if s.get("type") == "high"]
        if not swing_highs:
            return _empty_sweep()
        last_high = swing_highs[-1]
        swing_price = float(last_high["price"])
        recent_highs = [float(c["high"]) for c in execution_candles[-3:]]
        if max(recent_highs) < swing_price:
            return _empty_sweep()
        sweep_candle = None
        for c in reversed(execution_candles[-3:]):
            if float(c["high"]) > swing_price:
                sweep_candle = c
                break
        if sweep_candle is None:
            return _empty_sweep()
        sweep_idx = execution_candles.index(sweep_candle)
        if sweep_idx + 1 >= len(execution_candles):
            return _empty_sweep()
        disp_candle = execution_candles[sweep_idx + 1]
        disp_body = abs(float(disp_candle["close"]) - float(disp_candle["open"]))
        disp_range = max(float(disp_candle["high"]) - float(disp_candle["low"]), 1e-9)
        if disp_body / disp_range < 0.6:
            return _empty_sweep()
        if float(disp_candle["close"]) >= swing_price:
            return _empty_sweep()
        displacement_body_ratio = disp_body / disp_range
        displacement_idx = sweep_idx + 1
        sweep_extreme = float(sweep_candle["high"])

        # ---- HTF SWING VERIFICATION ----
        htf_swings = htf.get("swings", [])
        if htf_swings:
            htf_highs = [float(s["price"]) for s in htf_swings if s.get("type") == "high"]
            if not any(abs(swing_price - hh) / swing_price < 0.002 for hh in htf_highs):
                return _empty_sweep()

    return {
        "confirmed": True,
        "liquidity_sweep": True,
        "mtf_liquidity_sweep": True,
        "execution_liquidity_sweep": True,
        "mtf_swing": True,
        "ltf_swing": True,
        "execution_swing": True,
        "displacement": True,
        "displacement_body_ratio": round(displacement_body_ratio, 3),
        "sweep_index": sweep_idx,
        "displacement_index": displacement_idx,
        "swept_level": swing_price,
        "sweep_extreme": sweep_extreme,
        "session_ok": True,
        "killzone_active": True,
        "failed_step": None,
    }


def _empty_sweep():
    return {
        "confirmed": False,
        "liquidity_sweep": False,
        "mtf_liquidity_sweep": False,
        "execution_liquidity_sweep": False,
        "mtf_swing": False,
        "ltf_swing": False,
        "execution_swing": False,
        "displacement": False,
        "displacement_body_ratio": 0.0,
        "session_ok": True,
        "killzone_active": False,
        "failed_step": "liquidity_sweep",
    }


def _recent_candles(timeframe_state):
    candles = (timeframe_state or {}).get("recent_candles") or []
    if not isinstance(candles, list):
        return []
    return [
        candle
        for candle in candles
        if isinstance(candle, dict)
        and all(key in candle for key in ("open", "high", "low", "close"))
    ]


def _candle_metrics(candle):
    open_price = float(candle["open"])
    high_price = float(candle["high"])
    low_price = float(candle["low"])
    close_price = float(candle["close"])
    candle_range = max(high_price - low_price, 1e-9)
    body = abs(close_price - open_price)
    upper_wick = max(high_price - max(open_price, close_price), 0.0)
    lower_wick = max(min(open_price, close_price) - low_price, 0.0)
    close_position = (close_price - low_price) / candle_range
    return {
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "close": close_price,
        "range": candle_range,
        "body": body,
        "upper_wick": upper_wick,
        "lower_wick": lower_wick,
        "close_position": close_position,
    }


def _bullish_engulfing(previous_candle, current_candle):
    prev = _candle_metrics(previous_candle)
    curr = _candle_metrics(current_candle)
    return (
        prev["close"] < prev["open"]
        and curr["close"] > curr["open"]
        and curr["open"] <= prev["close"]
        and curr["close"] >= prev["open"]
    )


def _bearish_engulfing(previous_candle, current_candle):
    prev = _candle_metrics(previous_candle)
    curr = _candle_metrics(current_candle)
    return (
        prev["close"] > prev["open"]
        and curr["close"] < curr["open"]
        and curr["open"] >= prev["close"]
        and curr["close"] <= prev["open"]
    )


def _bullish_rejection(candle):
    current = _candle_metrics(candle)
    return (
        current["close"] > current["open"]
        and current["lower_wick"] >= current["body"] * 1.2
        and current["close_position"] >= 0.6
    )


def _bearish_rejection(candle):
    current = _candle_metrics(candle)
    return (
        current["close"] < current["open"]
        and current["upper_wick"] >= current["body"] * 1.2
        and current["close_position"] <= 0.4
    )


def _bullish_momentum(candle):
    current = _candle_metrics(candle)
    return (
        current["close"] > current["open"]
        and current["body"] / current["range"] >= 0.55
        and current["close_position"] >= 0.7
    )


def _bearish_momentum(candle):
    current = _candle_metrics(candle)
    return (
        current["close"] < current["open"]
        and current["body"] / current["range"] >= 0.55
        and current["close_position"] <= 0.3
    )


def _timeframe_price_action(candles, trend):
    if len(candles) < 2:
        return {
            "confirmed": False,
            "engulfing": False,
            "rejection": False,
            "momentum": False,
            "volume_confirmed": False,
            "patterns": [],
        }

    previous_candle = candles[-2]
    current_candle = candles[-1]
    volume_window = candles[-10:]
    avg_vol = sum(c.get("volume", c.get("tick_volume", 0)) for c in volume_window) / max(1, len(volume_window))
    curr_vol = current_candle.get("volume", current_candle.get("tick_volume", 0))
    volume_confirmed = curr_vol >= avg_vol if avg_vol > 0 else True

    if trend == "bullish":
        engulfing = _bullish_engulfing(previous_candle, current_candle)
        rejection = _bullish_rejection(current_candle)
        momentum = _bullish_momentum(current_candle)
    elif trend == "bearish":
        engulfing = _bearish_engulfing(previous_candle, current_candle)
        rejection = _bearish_rejection(current_candle)
        momentum = _bearish_momentum(current_candle)
    else:
        engulfing = False
        rejection = False
        momentum = False

    patterns = []
    if engulfing:
        patterns.append("engulfing")
    if rejection:
        patterns.append("rejection")
    if momentum:
        patterns.append("momentum")

    return {
        "confirmed": bool(patterns) and volume_confirmed,
        "engulfing": engulfing,
        "rejection": rejection,
        "momentum": momentum,
        "volume_confirmed": volume_confirmed,
        "patterns": patterns,
    }


def price_action_setup(analysis, trend):
    trend = _direction_to_trend(trend)
    mtf = analysis.get("MTF") or {}
    ltf = analysis.get("LTF") or {}
    execution = analysis.get("EXECUTION") or {}
    m1 = analysis.get("M1") or {"recent_candles": analysis.get("m1_candles") or []}

    mtf_state = _timeframe_price_action(_recent_candles(mtf), trend)
    ltf_state = _timeframe_price_action(_recent_candles(ltf), trend)
    execution_state = _timeframe_price_action(_recent_candles(execution), trend)
    m1_state = _timeframe_price_action(_recent_candles(m1), trend)

    m1_fallback_confirmed = bool((not execution_state["confirmed"]) and m1_state["confirmed"])
    execution_or_m1_confirmed = bool(execution_state["confirmed"] or m1_fallback_confirmed)
    confirmed = execution_or_m1_confirmed or ltf_state["confirmed"] or mtf_state["confirmed"]
    trigger = (
        "execution"
        if execution_state["confirmed"]
        else "m1_fallback"
        if m1_fallback_confirmed
        else "ltf"
        if ltf_state["confirmed"]
        else "mtf"
        if mtf_state["confirmed"]
        else None
    )
    execution_timeframe = "M5" if execution_state["confirmed"] else "M1" if m1_fallback_confirmed else None

    return {
        "confirmed": confirmed,
        "trigger": trigger,
        "execution_timeframe": execution_timeframe,
        "mtf_confirmed": mtf_state["confirmed"],
        "ltf_confirmed": ltf_state["confirmed"],
        "execution_confirmed": execution_state["confirmed"],
        "m1_confirmed": m1_state["confirmed"],
        "m1_fallback_confirmed": m1_fallback_confirmed,
        "execution_or_m1_confirmed": execution_or_m1_confirmed,
        "mtf_engulfing": mtf_state["engulfing"],
        "ltf_engulfing": ltf_state["engulfing"],
        "execution_engulfing": execution_state["engulfing"],
        "m1_engulfing": m1_state["engulfing"],
        "mtf_rejection": mtf_state["rejection"],
        "ltf_rejection": ltf_state["rejection"],
        "execution_rejection": execution_state["rejection"],
        "m1_rejection": m1_state["rejection"],
        "mtf_momentum": mtf_state["momentum"],
        "ltf_momentum": ltf_state["momentum"],
        "execution_momentum": execution_state["momentum"],
        "m1_momentum": m1_state["momentum"],
        "mtf_volume_confirmed": mtf_state["volume_confirmed"],
        "ltf_volume_confirmed": ltf_state["volume_confirmed"],
        "execution_volume_confirmed": execution_state["volume_confirmed"],
        "m1_volume_confirmed": m1_state["volume_confirmed"],
        "mtf_patterns": mtf_state["patterns"],
        "ltf_patterns": ltf_state["patterns"],
        "execution_patterns": execution_state["patterns"],
        "m1_patterns": m1_state["patterns"],
    }


def _confirmation_passed(flag):
    if isinstance(flag, bool):
        return flag
    if isinstance(flag, dict):
        return bool(flag.get("confirmed", flag.get("passed", False)))
    return False


def validate_confirmations(confirmation_flags, symbol=None):
    del symbol
    met_flags = {
        name: _confirmation_passed(flag)
        for name, flag in (confirmation_flags or {}).items()
    }

    missing_core = [name for name in CORE_CONFIRMATION_FLAGS if not met_flags.get(name, False)]
    if not _confirmation_passed((confirmation_flags or {}).get("order_block_confirmed", False)):
        missing_core.append("order_block_confirmed")

    return {
        "passed": not missing_core and all(met_flags.values()),
        "met_flags": sorted(name for name, passed in met_flags.items() if passed),
        "missing_core": missing_core,
        "core_ready": not missing_core,
    }
