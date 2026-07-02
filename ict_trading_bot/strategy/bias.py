"""Deterministic bias helpers shared by ICT and Kingsbalfx modules."""

from typing import Any, Dict, Iterable, List, Optional


def normalize_direction(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in ("buy", "bullish", "long", "up"):
        return "buy"
    if normalized in ("sell", "bearish", "short", "down"):
        return "sell"
    return ""


def direction_to_trend(direction: Any) -> str:
    normalized = normalize_direction(direction)
    if normalized == "buy":
        return "bullish"
    if normalized == "sell":
        return "bearish"
    return "neutral"


def trend_to_direction(trend: Any) -> str:
    return normalize_direction(trend)


def _valid_candles(candles: Iterable[Dict[str, Any]]) -> List[Dict[str, float]]:
    result = []
    for candle in candles or []:
        if not isinstance(candle, dict):
            continue
        try:
            result.append({
                "open": float(candle["open"]),
                "high": float(candle["high"]),
                "low": float(candle["low"]),
                "close": float(candle["close"]),
            })
        except (KeyError, TypeError, ValueError):
            continue
    return result


def candle_bias(candles: Iterable[Dict[str, Any]], lookback: int = 3) -> str:
    valid = _valid_candles(candles)[-max(1, int(lookback)):]
    if not valid:
        return "neutral"
    bullish = sum(1 for candle in valid if candle["close"] > candle["open"])
    bearish = sum(1 for candle in valid if candle["close"] < candle["open"])
    if bullish > bearish:
        return "bullish"
    if bearish > bullish:
        return "bearish"
    return "neutral"


def structure_bias(state: Dict[str, Any]) -> str:
    state = state or {}
    structure = state.get("market_structure") or {}
    trend = structure.get("trend") or state.get("trend")
    normalized = direction_to_trend(trend)
    if normalized in ("bullish", "bearish"):
        return normalized
    return candle_bias(state.get("recent_candles") or [])


def h1_m15_bias(analysis: Dict[str, Any]) -> Dict[str, Any]:
    analysis = analysis or {}
    explicit = analysis.get("h1_m15_alignment") or (analysis.get("topdown") or {}).get("h1_m15_alignment")
    if isinstance(explicit, dict):
        direction = normalize_direction(explicit.get("direction"))
        return {
            "confirmed": bool(explicit.get("confirmed") and direction),
            "direction": direction,
            "trend": direction_to_trend(direction),
            "h1": explicit.get("h1_trend"),
            "m15": explicit.get("m15_trend"),
            "source": "h1_m15_alignment",
        }

    h1 = structure_bias(analysis.get("HTF") or {})
    m15 = structure_bias(analysis.get("MTF") or {})
    confirmed = h1 in ("bullish", "bearish") and h1 == m15
    return {
        "confirmed": confirmed,
        "direction": trend_to_direction(h1) if confirmed else "",
        "trend": h1 if confirmed else "neutral",
        "h1": h1,
        "m15": m15,
        "source": "state_structure_bias",
    }


def daily_background_bias(analysis: Dict[str, Any]) -> Dict[str, Any]:
    context = (analysis or {}).get("previous_day_context") or ((analysis or {}).get("topdown") or {}).get("previous_day_context") or {}
    direction = normalize_direction(
        context.get("direction")
        or context.get("previous_day_direction")
        or context.get("bias")
        or context.get("trend")
    )
    return {
        "direction": direction,
        "trend": direction_to_trend(direction),
        "source_timeframe": context.get("source_timeframe"),
        "fallback_used": bool(context.get("fallback_used")),
        "context": context,
    }


def resolve_trade_bias(analysis: Dict[str, Any], preferred_direction: Optional[str] = None) -> Dict[str, Any]:
    preferred = normalize_direction(preferred_direction)
    intraday = h1_m15_bias(analysis)
    background = daily_background_bias(analysis)
    direction = preferred or intraday.get("direction") or background.get("direction")
    confirmed = bool(direction and (not preferred or intraday.get("confirmed", False) or background.get("direction") == preferred))
    return {
        "confirmed": confirmed,
        "direction": direction,
        "trend": direction_to_trend(direction),
        "intraday": intraday,
        "background": background,
        "reason": "bias resolved" if confirmed else "bias not confirmed by H1/M15 or background context",
    }
