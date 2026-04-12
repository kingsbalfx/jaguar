from typing import Dict, List


TIMEFRAME_WEIGHTS = {
    "HTF": 1.35,
    "MTF": 1.15,
    "LTF": 0.95,
    "EXECUTION": 0.85,
}


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def _safe_state(analysis: Dict, key: str) -> Dict:
    state = (analysis or {}).get(key) or {}
    return state if isinstance(state, dict) else {}


def _recent_candles(state: Dict, limit: int = 6) -> List[Dict]:
    candles = (state or {}).get("recent_candles") or []
    if not isinstance(candles, list):
        return []
    valid = []
    for candle in candles[-limit:]:
        if isinstance(candle, dict) and all(key in candle for key in ("open", "high", "low", "close")):
            valid.append(candle)
    return valid


def _candle_metrics(candle: Dict) -> Dict:
    open_price = _safe_float(candle.get("open"))
    high_price = _safe_float(candle.get("high"))
    low_price = _safe_float(candle.get("low"))
    close_price = _safe_float(candle.get("close"))
    candle_range = max(high_price - low_price, 1e-9)
    body = abs(close_price - open_price)
    return {
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "close": close_price,
        "range": candle_range,
        "body": body,
        "body_ratio": body / candle_range,
        "upper_wick": max(high_price - max(open_price, close_price), 0.0),
        "lower_wick": max(min(open_price, close_price) - low_price, 0.0),
        "close_position": (close_price - low_price) / candle_range,
        "bullish": close_price > open_price,
        "bearish": close_price < open_price,
    }


def _swing_prices(swings: List[Dict], swing_type: str) -> List[float]:
    if not isinstance(swings, list):
        return []
    prices = []
    for swing in swings:
        if not isinstance(swing, dict) or swing.get("type") != swing_type:
            continue
        prices.append(_safe_float(swing.get("price")))
    return prices


def _assess_swing_structure(swings: List[Dict], trend: str) -> Dict:
    continuation = 0.0
    reversal = 0.0
    reasons = []

    highs = _swing_prices(swings, "high")
    lows = _swing_prices(swings, "low")

    if trend == "bullish":
        if len(highs) >= 2 and highs[-1] > highs[-2]:
            continuation += 8
            reasons.append("higher highs holding")
        elif len(highs) >= 2 and highs[-1] < highs[-2]:
            reversal += 8
            reasons.append("highs no longer expanding")

        if len(lows) >= 2 and lows[-1] > lows[-2]:
            continuation += 10
            reasons.append("higher lows defending trend")
        elif len(lows) >= 2 and lows[-1] < lows[-2]:
            reversal += 12
            reasons.append("lower low warns of reversal")

    elif trend == "bearish":
        if len(lows) >= 2 and lows[-1] < lows[-2]:
            continuation += 8
            reasons.append("lower lows holding")
        elif len(lows) >= 2 and lows[-1] > lows[-2]:
            reversal += 8
            reasons.append("lows no longer extending")

        if len(highs) >= 2 and highs[-1] < highs[-2]:
            continuation += 10
            reasons.append("lower highs capping rallies")
        elif len(highs) >= 2 and highs[-1] > highs[-2]:
            reversal += 12
            reasons.append("higher high warns of reversal")

    return {
        "continuation": continuation,
        "reversal": reversal,
        "reasons": reasons,
    }


def _assess_candle_rhythm(candles: List[Dict], trend: str, atr: float, volume_boost: bool) -> Dict:
    continuation = 0.0
    reversal = 0.0
    compression = 0.0
    reasons = []

    if not candles:
        return {
            "continuation": continuation,
            "reversal": reversal,
            "compression": compression,
            "reasons": reasons,
        }

    metrics = [_candle_metrics(candle) for candle in candles]
    last = metrics[-1]
    recent = metrics[-min(3, len(metrics)) :]
    avg_range = sum(item["range"] for item in recent) / max(len(recent), 1)

    if atr > 0:
        if avg_range < atr * 0.65:
            compression += 18
            reasons.append("volatility compression")
        elif avg_range > atr * 1.20:
            reasons.append("range expansion active")

    if trend == "bullish":
        if last["bullish"] and last["body_ratio"] >= 0.55 and last["close_position"] >= 0.65:
            continuation += 16
            reasons.append("buyers closed strong")
        if last["bearish"] and last["body_ratio"] >= 0.55 and last["close_position"] <= 0.35:
            reversal += 18
            reasons.append("sellers pressing into close")
        if last["upper_wick"] >= max(last["body"] * 1.6, last["range"] * 0.35):
            reversal += 10
            reasons.append("upper-wick exhaustion")
        if last["lower_wick"] >= max(last["body"] * 1.2, last["range"] * 0.25) and last["bullish"]:
            continuation += 7
            reasons.append("dip buying defended low")

        if len(recent) >= 2 and all(item["bearish"] and item["body_ratio"] >= 0.5 for item in recent[-2:]):
            reversal += 16
            reasons.append("two bearish impulse candles")
        elif len(recent) >= 2 and all(item["bullish"] and item["body_ratio"] >= 0.45 for item in recent[-2:]):
            continuation += 10
            reasons.append("follow-through buying")

    elif trend == "bearish":
        if last["bearish"] and last["body_ratio"] >= 0.55 and last["close_position"] <= 0.35:
            continuation += 16
            reasons.append("sellers closed strong")
        if last["bullish"] and last["body_ratio"] >= 0.55 and last["close_position"] >= 0.65:
            reversal += 18
            reasons.append("buyers pressing into close")
        if last["lower_wick"] >= max(last["body"] * 1.6, last["range"] * 0.35):
            reversal += 10
            reasons.append("lower-wick exhaustion")
        if last["upper_wick"] >= max(last["body"] * 1.2, last["range"] * 0.25) and last["bearish"]:
            continuation += 7
            reasons.append("sellers rejected rally")

        if len(recent) >= 2 and all(item["bullish"] and item["body_ratio"] >= 0.5 for item in recent[-2:]):
            reversal += 16
            reasons.append("two bullish impulse candles")
        elif len(recent) >= 2 and all(item["bearish"] and item["body_ratio"] >= 0.45 for item in recent[-2:]):
            continuation += 10
            reasons.append("follow-through selling")

    if volume_boost:
        if continuation > reversal:
            continuation += 8
            reasons.append("volume supports current move")
        elif reversal > continuation:
            reversal += 8
            reasons.append("volume supports reversal pressure")
        else:
            compression += 4

    return {
        "continuation": continuation,
        "reversal": reversal,
        "compression": compression,
        "reasons": reasons[:4],
    }


def _assess_timeframe(name: str, state: Dict, trend: str) -> Dict:
    continuation = 0.0
    reversal = 0.0
    compression = 0.0
    reasons = []

    tf_trend = (state or {}).get("trend")
    if tf_trend == trend:
        continuation += 34
        reasons.append(f"{name} trend aligned")
    elif tf_trend in ("bullish", "bearish"):
        reversal += 34
        reasons.append(f"{name} trend opposes")
    else:
        compression += 12
        reasons.append(f"{name} trend unclear")

    above_sma = state.get("above_sma")
    if above_sma is not None:
        if (trend == "bullish" and above_sma) or (trend == "bearish" and not above_sma):
            continuation += 10
        else:
            reversal += 10
            reasons.append(f"{name} price is on the wrong side of SMA")

    candle_assessment = _assess_candle_rhythm(
        _recent_candles(state),
        trend,
        _safe_float(state.get("atr")),
        bool(state.get("volume_boost")),
    )
    continuation += candle_assessment["continuation"]
    reversal += candle_assessment["reversal"]
    compression += candle_assessment["compression"]
    reasons.extend(candle_assessment["reasons"])

    swing_assessment = _assess_swing_structure((state or {}).get("swings") or [], trend)
    continuation += swing_assessment["continuation"]
    reversal += swing_assessment["reversal"]
    reasons.extend(swing_assessment["reasons"])

    continuation = min(100.0, continuation)
    reversal = min(100.0, reversal)
    compression = min(100.0, compression)

    if continuation >= reversal + 12:
        bias = "continuation"
    elif reversal >= continuation + 12:
        bias = "reversal"
    else:
        bias = "mixed"
        compression = max(compression, 25.0)

    return {
        "timeframe": name,
        "continuation": round(continuation, 1),
        "reversal": round(reversal, 1),
        "compression": round(compression, 1),
        "bias": bias,
        "reasons": reasons[:4],
    }


def _weighted_average(values: List[float], weights: List[float]) -> float:
    total_weight = sum(weights) or 1.0
    return sum(value * weight for value, weight in zip(values, weights)) / total_weight


def _build_management_plan(phase: str) -> Dict:
    plans = {
        "trend_continuation": {"breakeven_r": 1.0, "partial_r": 2.0, "trail_r": 3.0, "mode": "trend"},
        "healthy_pullback": {"breakeven_r": 0.8, "partial_r": 1.6, "trail_r": 2.4, "mode": "balanced"},
        "compression": {"breakeven_r": 0.7, "partial_r": 1.3, "trail_r": 1.8, "mode": "tight"},
        "transition": {"breakeven_r": 0.6, "partial_r": 1.1, "trail_r": 1.5, "mode": "defensive"},
        "reversal_risk": {"breakeven_r": 0.5, "partial_r": 1.0, "trail_r": 1.2, "mode": "protective"},
    }
    return plans.get(phase, plans["transition"])


def analyze_market_rhythm(analysis: Dict, trend: str) -> Dict:
    """
    Read the market's current rhythm so the bot can adapt to continuation,
    pullbacks, compression, and possible reversals instead of trusting one setup.
    """
    if trend not in ("bullish", "bearish"):
        return {
            "phase": "unclear",
            "entry_bias": "avoid",
            "continuation_score": 35.0,
            "reversal_score": 35.0,
            "compression_score": 55.0,
            "entry_score": 35.0,
            "confidence_adjustment": -12.0,
            "risk_multiplier": 0.70,
            "regime_multiplier": 0.88,
            "should_avoid_entry": True,
            "summary": "Market rhythm unclear - avoid new entries until direction stabilizes.",
            "reasons": ["topdown trend is not clear enough"],
            "timeframe_breakdown": {},
            "management_plan": _build_management_plan("reversal_risk"),
        }

    weights = []
    continuation_values = []
    reversal_values = []
    compression_values = []
    timeframe_breakdown = {}

    for key, weight in TIMEFRAME_WEIGHTS.items():
        state = _safe_state(analysis, key)
        assessment = _assess_timeframe(key, state, trend)
        timeframe_breakdown[key] = assessment
        weights.append(weight)
        continuation_values.append(assessment["continuation"])
        reversal_values.append(assessment["reversal"])
        compression_values.append(assessment["compression"])

    continuation_score = _weighted_average(continuation_values, weights)
    reversal_score = _weighted_average(reversal_values, weights)
    compression_score = _weighted_average(compression_values, weights)

    topdown = (analysis or {}).get("topdown") or {}
    context_alignment = topdown.get("context_alignment")
    if context_alignment == "aligned":
        continuation_score += 5
    elif context_alignment == "opposed":
        reversal_score += 8
    elif context_alignment == "mixed":
        compression_score += 6

    if analysis.get("htf_sweep"):
        continuation_score += 6

    continuation_score = max(0.0, min(100.0, continuation_score))
    reversal_score = max(0.0, min(100.0, reversal_score))
    compression_score = max(0.0, min(100.0, compression_score))

    aligned_timeframes = sum(1 for item in timeframe_breakdown.values() if item["bias"] == "continuation")
    opposing_timeframes = sum(1 for item in timeframe_breakdown.values() if item["bias"] == "reversal")

    if reversal_score >= 70 and reversal_score >= continuation_score + 10:
        phase = "reversal_risk"
        entry_bias = "avoid"
        confidence_adjustment = -15.0
        risk_multiplier = 0.65
        regime_multiplier = 0.86
    elif continuation_score >= 72 and opposing_timeframes == 0:
        phase = "trend_continuation"
        entry_bias = "favorable"
        confidence_adjustment = 6.0
        risk_multiplier = 1.08
        regime_multiplier = 1.05
    elif continuation_score >= 58 and reversal_score < 58 and opposing_timeframes <= 1:
        phase = "healthy_pullback"
        entry_bias = "favorable"
        confidence_adjustment = 3.0
        risk_multiplier = 0.96
        regime_multiplier = 1.02
    elif compression_score >= 60 and abs(continuation_score - reversal_score) <= 12:
        phase = "compression"
        entry_bias = "cautious"
        confidence_adjustment = -5.0
        risk_multiplier = 0.84
        regime_multiplier = 0.94
    else:
        phase = "transition"
        entry_bias = "cautious"
        confidence_adjustment = -8.0
        risk_multiplier = 0.80
        regime_multiplier = 0.91

    entry_score = max(
        0.0,
        min(
            100.0,
            (continuation_score * 0.60)
            + ((100.0 - reversal_score) * 0.25)
            + ((100.0 - compression_score) * 0.15),
        ),
    )
    should_avoid_entry = entry_bias == "avoid" or (reversal_score >= 75 and continuation_score <= 45)

    reasons = []
    for timeframe in ("HTF", "MTF", "LTF", "EXECUTION"):
        reasons.extend(timeframe_breakdown.get(timeframe, {}).get("reasons", []))
    reasons = reasons[:6]

    summary = (
        f"Rhythm {phase}: continuation {continuation_score:.0f}, "
        f"reversal {reversal_score:.0f}, compression {compression_score:.0f}, "
        f"bias {entry_bias}."
    )

    return {
        "phase": phase,
        "entry_bias": entry_bias,
        "continuation_score": round(continuation_score, 1),
        "reversal_score": round(reversal_score, 1),
        "compression_score": round(compression_score, 1),
        "entry_score": round(entry_score, 1),
        "confidence_adjustment": round(confidence_adjustment, 1),
        "risk_multiplier": round(risk_multiplier, 3),
        "regime_multiplier": round(regime_multiplier, 3),
        "aligned_timeframes": aligned_timeframes,
        "opposing_timeframes": opposing_timeframes,
        "should_avoid_entry": should_avoid_entry,
        "summary": summary,
        "reasons": reasons,
        "timeframe_breakdown": timeframe_breakdown,
        "management_plan": _build_management_plan(phase),
    }


def build_market_rhythm_summary(rhythm: Dict) -> str:
    if not isinstance(rhythm, dict):
        return "Rhythm unavailable"
    return (
        f"{rhythm.get('phase', 'unknown')} | "
        f"bias={rhythm.get('entry_bias', 'unknown')} | "
        f"cont={rhythm.get('continuation_score', 0):.0f} "
        f"rev={rhythm.get('reversal_score', 0):.0f} "
        f"comp={rhythm.get('compression_score', 0):.0f}"
    )
