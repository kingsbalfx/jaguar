from strategy.liquidity_filter import liquidity_taken
from utils.symbol_profile import get_confirmation_profile


def _direction_to_trend(direction):
    return "bullish" if direction == "buy" else "bearish"


def _filter_swings(swings, swing_type):
    if not isinstance(swings, list):
        return []
    return [s for s in swings if isinstance(s, dict) and s.get("type") == swing_type]


def recent_bos(swings, trend):
    highs = _filter_swings(swings, "high")
    lows = _filter_swings(swings, "low")

    if trend == "bullish":
        return len(highs) >= 2 and float(highs[-1]["price"]) > float(highs[-2]["price"])
    if trend == "bearish":
        return len(lows) >= 2 and float(lows[-1]["price"]) < float(lows[-2]["price"])
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
    mtf_swings = (analysis.get("MTF") or {}).get("swings") or []
    ltf_swings = (analysis.get("LTF") or {}).get("swings") or []
    execution_swings = (analysis.get("EXECUTION") or {}).get("swings") or []
    mtf_bos = recent_bos(mtf_swings, trend)
    ltf_bos = recent_bos(ltf_swings, trend)
    execution_bos = recent_bos(execution_swings, trend)
    return {
        "confirmed": mtf_bos or ltf_bos or execution_bos,
        "mtf_bos": mtf_bos,
        "ltf_bos": ltf_bos,
        "execution_bos": execution_bos,
    }


def liquidity_sweep_or_swing(price, analysis, direction):
    trend = _direction_to_trend(direction)
    mtf = analysis.get("MTF") or {}
    ltf = analysis.get("LTF") or {}
    execution = analysis.get("EXECUTION") or {}

    sweep = liquidity_taken(price, mtf.get("liquidity"), direction)
    execution_sweep = liquidity_taken(price, execution.get("liquidity"), direction)
    mtf_swing = swing_trend_confirmation(mtf.get("swings") or [], trend)
    ltf_swing = swing_trend_confirmation(ltf.get("swings") or [], trend)
    execution_swing = swing_trend_confirmation(execution.get("swings") or [], trend)

    return {
        "confirmed": sweep or execution_sweep or mtf_swing or ltf_swing or execution_swing,
        "liquidity_sweep": sweep,
        "execution_liquidity_sweep": execution_sweep,
        "mtf_swing": mtf_swing,
        "ltf_swing": ltf_swing,
        "execution_swing": execution_swing,
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
            "patterns": [],
        }

    previous_candle = candles[-2]
    current_candle = candles[-1]

    # Volume confirmation for Price Action
    volume_window = candles[-10:]
    avg_vol = sum(c.get("volume", 0) for c in volume_window) / max(1, len(volume_window))
    curr_vol = current_candle.get("volume", 0)
    volume_confirmed = curr_vol > avg_vol

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
        "patterns": patterns,
    }


def price_action_setup(analysis, trend):
    mtf = analysis.get("MTF") or {}
    ltf = analysis.get("LTF") or {}
    execution = analysis.get("EXECUTION") or {}

    mtf_state = _timeframe_price_action(_recent_candles(mtf), trend)
    ltf_state = _timeframe_price_action(_recent_candles(ltf), trend)
    execution_state = _timeframe_price_action(_recent_candles(execution), trend)

    return {
        "confirmed": mtf_state["confirmed"] or ltf_state["confirmed"] or execution_state["confirmed"],
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
        "mtf_patterns": mtf_state["patterns"],
        "ltf_patterns": ltf_state["patterns"],
        "execution_patterns": execution_state["patterns"],
    }


def evaluate_confirmation_quality(confirmation_flags, symbol=None):
    profile = get_confirmation_profile(symbol)
    weights = profile["weights"]
    met_flags = {
        name: bool(passed)
        for name, passed in (confirmation_flags or {}).items()
        if bool(passed)
    }
    weighted_flags = {
        name: float(weights.get(name, 1.0))
        for name in sorted(met_flags)
    }
    score = sum(weighted_flags.values())
    min_score = float(profile["min_score"])
    return {
        "asset_class": profile["asset_class"],
        "score": score,
        "min_score": min_score,
        "passed": score >= min_score,
        "met_flags": sorted(met_flags),
        "weighted_flags": weighted_flags,
    }
