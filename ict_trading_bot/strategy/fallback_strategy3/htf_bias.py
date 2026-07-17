"""
FALLBACK STRATEGY 3 - Higher Timeframe Bias
=============================================
Determines directional bias from higher timeframe (H1/H4) market structure.
Only returns bias when structure is clear, not ranging or conflicting.
"""

from typing import List, Optional, Tuple

from . import config
from .indicators import find_swing_points, atr, candle_direction
from .models import Direction


def determine_htf_bias(
    htf_candles: List[dict],
    htf_swings: List[dict],
    htf_trend: Optional[str],          # From existing analysis, if available
    htf_market_structure: Optional[dict],  # From existing analysis
) -> Tuple[Optional[str], float]:
    """
    Determine higher-timeframe (H1/H4) directional bias using objective market structure.
    
    Returns:
        (direction: "bullish"/"bearish"/None, confidence_score: 0.0-1.0)
    """
    # If we already have a market structure analysis with clear trend, use it
    if htf_market_structure:
        structure_trend = str(htf_market_structure.get("trend") or "").lower()
        if structure_trend in ("bullish", "bearish"):
            events = htf_market_structure.get("events") or []
            last_event = htf_market_structure.get("last_event") or {}
            bos_count = sum(1 for e in events if e.get("event") == "BOS")
            mss_count = sum(1 for e in events if e.get("event") in ("CHOCH", "MSS"))
            confidence = 0.5  # base confidence
            if bos_count >= 2:
                confidence += 0.2
            if structure_trend in ("bullish", "bearish"):
                confidence += 0.1
            if last_event and last_event.get("event") in ("BOS", "CHOCH", "MSS"):
                confidence += 0.2
            return structure_trend, min(confidence, 1.0)

    # Fall back to candle-based analysis
    if not htf_candles or len(htf_candles) < 10:
        return None, 0.0

    # Calculate swings if not provided
    swings = htf_swings if htf_swings else find_swing_points(htf_candles, lookback=2)
    if len(swings) < 4:
        return None, 0.0

    highs = [s for s in swings if s["type"] == "high"]
    lows = [s for s in swings if s["type"] == "low"]

    if len(highs) < 2 or len(lows) < 2:
        # Try directional candle count
        return _candle_bias(htf_candles)

    last_two_highs = highs[-2:]
    last_two_lows = lows[-2:]

    higher_high = float(last_two_highs[-1]["price"]) > float(last_two_highs[-2]["price"])
    higher_low = float(last_two_lows[-1]["price"]) > float(last_two_lows[-2]["price"])
    lower_high = float(last_two_highs[-1]["price"]) < float(last_two_highs[-2]["price"])
    lower_low = float(last_two_lows[-1]["price"]) < float(last_two_lows[-2]["price"])

    # Bullish criteria
    if higher_high and higher_low:
        return "bullish", 0.8
    if higher_high:
        return "bullish", 0.6

    # Bearish criteria
    if lower_high and lower_low:
        return "bearish", 0.8
    if lower_low:
        return "bearish", 0.6

    # Check for bullish BOS / displacement
    atr_value = atr(htf_candles, period=14)
    if atr_value > 0:
        recent = htf_candles[-3:]
        bullish_candles = sum(1 for c in recent if candle_direction(c) == "bullish")
        bearish_candles = sum(1 for c in recent if candle_direction(c) == "bearish")
        if bullish_candles >= 2 and bearish_candles == 0:
            # Check for displacement
            last_body = _body_percent(recent[-1]) if recent else 0
            if last_body >= 0.45:
                return "bullish", 0.55
        if bearish_candles >= 2 and bullish_candles == 0:
            last_body = _body_percent(recent[-1]) if recent else 0
            if last_body >= 0.45:
                return "bearish", 0.55

    # Check if price is in discount/premium based on swing range
    if highs and lows:
        high_price = float(highs[-1]["price"])
        low_price = float(lows[-1]["price"])
        if high_price > low_price:
            midpoint = (high_price + low_price) / 2.0
            current = _to_float(htf_candles[-1].get("close"))
            # Discount = below midpoint (bullish bias)
            if current < midpoint * 0.98:
                return "bullish", 0.4  # Weak bullish — price in discount
            # Premium = above midpoint (bearish bias)
            if current > midpoint * 1.02:
                return "bearish", 0.4  # Weak bearish — price in premium

    return None, 0.0


def _candle_bias(candles: List[dict]) -> Tuple[Optional[str], float]:
    """Fallback bias from candle counting."""
    if len(candles) < 8:
        return None, 0.0
    recent = candles[-8:]
    bullish = sum(1 for c in recent if candle_direction(c) == "bullish")
    bearish = sum(1 for c in recent if candle_direction(c) == "bearish")
    net_change = _to_float(recent[-1].get("close")) - _to_float(recent[0].get("open"))
    avg_range = sum(
        _to_float(c.get("high")) - _to_float(c.get("low")) for c in recent
    ) / len(recent)

    if bullish >= 5 and bearish <= 2 and net_change > avg_range * 0.5:
        return "bullish", 0.5
    if bearish >= 5 and bullish <= 2 and net_change < -avg_range * 0.5:
        return "bearish", 0.5
    return None, 0.0


def _body_percent(candle: dict) -> float:
    r = _to_float(candle.get("high")) - _to_float(candle.get("low"))
    b = abs(_to_float(candle.get("close")) - _to_float(candle.get("open")))
    return b / r if r > 0 else 0.0


def _to_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def htf_supports_reversal(
    htf_bias: Optional[str],
    trade_direction: Optional[str],
    countertrend_enabled: bool = False,
) -> bool:
    """
    Check that the HTF bias supports the intended trade direction.
    By default (countertrend disabled), trade direction must match HTF bias.
    """
    if not trade_direction or not htf_bias:
        return False

    # Normalize
    trade = "bullish" if trade_direction == "buy" else "bearish"
    bias = str(htf_bias).lower()

    if bias == trade:
        return True  # Same direction
    if countertrend_enabled:
        return True  # Countertrend allowed
    return False  # Opposing trend, countertrend disabled
