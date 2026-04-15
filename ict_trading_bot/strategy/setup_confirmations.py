from strategy.liquidity_filter import liquidity_taken
from utils.sessions import intelligence_session_open
from utils.symbol_profile import get_confirmation_profile


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


def _displacement_score(candles, direction):
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


def liquidity_sweep_or_swing(price, analysis, direction):
    trend = _direction_to_trend(direction)
    mtf = analysis.get("MTF") or {}
    ltf = analysis.get("LTF") or {}
    execution = analysis.get("EXECUTION") or {}
    session_ok = intelligence_session_open()
    execution_candles = execution.get("recent_candles") or []
    displacement_score = _displacement_score(execution_candles, trend)

    mtf_sweep = liquidity_taken(price, mtf.get("liquidity"), trend, recent_candles=execution_candles)
    execution_sweep = liquidity_taken(price, execution.get("liquidity"), trend, recent_candles=execution_candles)
    mtf_swing = swing_trend_confirmation(mtf.get("swings") or [], trend)
    ltf_swing = swing_trend_confirmation(ltf.get("swings") or [], trend)
    execution_swing = swing_trend_confirmation(execution.get("swings") or [], trend)

    strict_sweep = bool(session_ok and displacement_score >= 0.70 and (mtf_sweep or execution_sweep))
    failed_step = None
    if not session_ok:
        failed_step = "session"
    elif displacement_score < 0.70:
        failed_step = "displacement"
    elif not (mtf_sweep or execution_sweep):
        failed_step = "liquidity_sweep"

    return {
        "confirmed": strict_sweep,
        "liquidity_sweep": strict_sweep,
        "mtf_liquidity_sweep": mtf_sweep,
        "execution_liquidity_sweep": execution_sweep,
        "mtf_swing": mtf_swing,
        "ltf_swing": ltf_swing,
        "execution_swing": execution_swing,
        "displacement": displacement_score >= 0.70,
        "displacement_score": displacement_score,
        "session_ok": session_ok,
        "failed_step": failed_step,
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

    mtf_state = _timeframe_price_action(_recent_candles(mtf), trend)
    ltf_state = _timeframe_price_action(_recent_candles(ltf), trend)
    execution_state = _timeframe_price_action(_recent_candles(execution), trend)

    confirmed = execution_state["confirmed"] or ltf_state["confirmed"] or mtf_state["confirmed"]
    trigger = (
        "execution" if execution_state["confirmed"] else "ltf" if ltf_state["confirmed"] else "mtf" if mtf_state["confirmed"] else None
    )

    return {
        "confirmed": confirmed,
        "trigger": trigger,
        "mtf_confirmed": mtf_state["confirmed"],
        "ltf_confirmed": ltf_state["confirmed"],
        "execution_confirmed": execution_state["confirmed"],
        "mtf_engulfing": mtf_state["engulfing"],
        "ltf_engulfing": ltf_state["engulfing"],
        "execution_engulfing": execution_state["engulfing"],
        "mtf_rejection": mtf_state["rejection"],
        "ltf_rejection": ltf_state["rejection"],
        "execution_rejection": execution_state["rejection"],
        "mtf_momentum": mtf_state["momentum"],
        "ltf_momentum": ltf_state["momentum"],
        "execution_momentum": execution_state["momentum"],
        "mtf_volume_confirmed": mtf_state["volume_confirmed"],
        "ltf_volume_confirmed": ltf_state["volume_confirmed"],
        "execution_volume_confirmed": execution_state["volume_confirmed"],
        "mtf_patterns": mtf_state["patterns"],
        "ltf_patterns": ltf_state["patterns"],
        "execution_patterns": execution_state["patterns"],
    }


def _confirmation_passed(flag):
    if isinstance(flag, bool):
        return flag
    if isinstance(flag, dict):
        return bool(flag.get("confirmed", flag.get("passed", False)))
    return False


def evaluate_confirmation_quality(confirmation_flags, symbol=None):
    profile = get_confirmation_profile(symbol)
    weights = profile["weights"]

    met_flags = {
        name: _confirmation_passed(flag)
        for name, flag in (confirmation_flags or {}).items()
    }

    missing_core = [name for name in CORE_CONFIRMATION_FLAGS if not met_flags.get(name, False)]
    if not _confirmation_passed((confirmation_flags or {}).get("order_block_confirmed", False)):
        missing_core.append("order_block_confirmed")

    weighted_flags = {
        name: float(weights.get(name, 1.0))
        for name, passed in sorted(met_flags.items())
        if passed
    }
    score = sum(weighted_flags.values())
    min_score = max(float(profile["min_score"]), 4.0)

    if missing_core:
        score = 0.0

    return {
        "asset_class": profile["asset_class"],
        "score": score,
        "min_score": min_score,
        "passed": score >= min_score and not missing_core,
        "met_flags": sorted(name for name, passed in met_flags.items() if passed),
        "weighted_flags": weighted_flags,
        "missing_core": missing_core,
        "core_ready": not missing_core,
    }
