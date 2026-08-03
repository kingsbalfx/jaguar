"""
FALLBACK STRATEGY 5 — Trend Classification
============================================
Multi-timeframe trend classification using:
- HH/HL sequence, LH/LL sequence
- Protected highs/lows
- EMA alignment and slope
- ADX trend strength
- Price position relative to averages
"""

from typing import List, Optional, Tuple, Dict

from . import config
from .indicators import (
    ema, ema_values, atr, find_swing_points,
    ema_slope, ema_alignment, adx, _to_float,
)
from .logging import log_trend_analysis


# Trend direction constants
BULLISH = "bullish"
BEARISH = "bearish"
NEUTRAL = "neutral"
TRANSITIONING = "transitioning"
CONFLICTING = "conflicting"

# Trend strength constants
STRONG = "strong"
MODERATE = "moderate"
WEAK = "weak"
EXHAUSTED = "exhausted"


def classify_trend(
    symbol: str,
    htf_candles: List[dict],
    mtf_candles: List[dict],
    setup_candles: List[dict],
    exec_candles: List[dict],
    mode: str = "B",
) -> Tuple[Optional[str], str, dict]:
    """
    Multi-timeframe trend classification.
    
    Returns:
        (direction, strength, evidence_dict)
    where direction is "bullish", "bearish", or None.
    """
    evidence = {
        "htf": {},
        "mtf": {},
        "ema": {},
        "adx": {},
        "structure": {},
    }

    if not htf_candles or len(htf_candles) < 20:
        return None, WEAK, evidence

    # ============================================================
    # 1. HTF Structure Analysis (H1)
    # ============================================================
    htf_swings = find_swing_points(htf_candles, lookback=2)
    htf_score, htf_details = _score_swing_structure(htf_swings, "htf")
    evidence["structure"]["htf_score"] = htf_score
    evidence["structure"]["htf_details"] = htf_details

    # ============================================================
    # 2. MTF Structure Analysis (M15)
    # ============================================================
    mtf_swings = find_swing_points(mtf_candles, lookback=2) if mtf_candles else []
    mtf_score, mtf_details = _score_swing_structure(mtf_swings, "mtf")
    evidence["structure"]["mtf_score"] = mtf_score
    evidence["structure"]["mtf_details"] = mtf_details

    # ============================================================
    # 3. EMA Alignment
    # ============================================================
    ema_fast = config.EMA_FAST
    ema_mid = config.EMA_MEDIUM
    ema_slow = config.EMA_SLOW

    # Use the context/setup timeframe for EMA analysis depending on mode
    if mode == "A":
        ema_candles = mtf_candles or htf_candles
    elif mode == "B":
        ema_candles = setup_candles or mtf_candles or htf_candles
    else:  # Mode C
        ema_candles = setup_candles or mtf_candles or htf_candles

    if len(ema_candles) >= ema_slow + 2:
        fast_vals = ema_values(ema_candles, ema_fast)
        mid_vals = ema_values(ema_candles, ema_mid)
        slow_vals = ema_values(ema_candles, ema_slow)

        alignment = ema_alignment(fast_vals, mid_vals, slow_vals)
        fast_slope_val = ema_slope(fast_vals, 5)
        mid_slope_val = ema_slope(mid_vals, 5)
        slow_slope_val = ema_slope(slow_vals, 5)

        # Price position relative to EMAs
        current_close = _to_float(ema_candles[-1].get("close"))
        fast_val = fast_vals[-1] if fast_vals else 0.0
        mid_val = mid_vals[-1] if mid_vals else 0.0
        slow_val = slow_vals[-1] if slow_vals else 0.0

        price_above_fast = current_close > fast_val if fast_val > 0 else False
        price_above_mid = current_close > mid_val if mid_val > 0 else False
        price_above_slow = current_close > slow_val if slow_val > 0 else False

        evidence["ema"] = {
            "alignment": alignment,
            "fast": fast_val,
            "mid": mid_val,
            "slow": slow_val,
            "fast_slope": round(fast_slope_val, 8),
            "mid_slope": round(mid_slope_val, 8),
            "slow_slope": round(slow_slope_val, 8),
            "price_above_fast": price_above_fast,
            "price_above_mid": price_above_mid,
            "price_above_slow": price_above_slow,
            "current_close": current_close,
        }
    else:
        alignment = "tangled"
        evidence["ema"] = {"alignment": "tangled", "reason": "insufficient_candles"}
        fast_slope_val = 0.0
        mid_slope_val = 0.0
        slow_slope_val = 0.0

    # Score from EMA (max +3 for bullish, -3 for bearish)
    ema_score = 0
    if alignment == "bullish":
        ema_score = 3
        if fast_slope_val > 0 and mid_slope_val > 0:
            ema_score = 4  # Both sloping up
        if fast_slope_val > 0 and mid_slope_val > 0 and slow_slope_val > 0:
            ema_score = 5  # All sloping up
    elif alignment == "bearish":
        ema_score = -3
        if fast_slope_val < 0 and mid_slope_val < 0:
            ema_score = -4
        if fast_slope_val < 0 and mid_slope_val < 0 and slow_slope_val < 0:
            ema_score = -5

    evidence["ema"]["score"] = ema_score

    # ============================================================
    # 4. ADX Trend Strength
    # ============================================================
    adx_value = adx(mtf_candles or htf_candles, config.ADX_PERIOD)
    evidence["adx"]["value"] = adx_value

    adx_strength = WEAK
    if adx_value <= config.ADX_WEAK_THRESHOLD:
        adx_strength = WEAK
        adx_score = 0
    elif adx_value <= config.ADX_MINIMUM_FOR_TRADE:
        adx_strength = WEAK
        adx_score = 1
    elif adx_value <= config.ADX_STRONG_THRESHOLD:
        adx_strength = MODERATE
        adx_score = 2
    elif adx_value <= config.ADX_EXTREME_THRESHOLD:
        adx_strength = STRONG
        adx_score = 3
    else:
        adx_strength = EXHAUSTED
        adx_score = 1  # Strong but exhaustion risk

    evidence["adx"]["strength"] = adx_strength
    evidence["adx"]["score"] = adx_score

    # ============================================================
    # 5. Combined Score
    # ============================================================
    # Weight: structure 50%, EMA 30%, ADX 20%
    htf_weighted = htf_score * 0.35
    mtf_weighted = mtf_score * 0.15
    combined_structure = htf_weighted + mtf_weighted

    combined = combined_structure + ema_score * 0.3 + adx_score * 0.2

    # ============================================================
    # 6. Final Classification
    # ============================================================
    direction = None
    strength = WEAK

    if combined >= 2.5:
        direction = BULLISH
        if combined >= 4.0:
            strength = STRONG
        else:
            strength = MODERATE
    elif combined <= -2.5:
        direction = BEARISH
        if combined <= -4.0:
            strength = STRONG
        else:
            strength = MODERATE
    else:
        # Check if conflicting
        if (htf_score > 0 and mtf_score < 0) or (htf_score < 0 and mtf_score > 0):
            direction = CONFLICTING
        else:
            direction = NEUTRAL

    # Check exhaustion
    if direction in (BULLISH, BEARISH) and adx_strength == EXHAUSTED:
        # Check if price is overextended
        atr_val = atr(htf_candles, 14)
        if atr_val > 0:
            close = _to_float(htf_candles[-1].get("close"))
            fast_val = evidence["ema"].get("fast", 0)
            if fast_val > 0:
                distance = abs(close - fast_val) / atr_val
                if distance > 2.0:
                    strength = EXHAUSTED

    evidence["combined_score"] = round(combined, 2)
    evidence["direction"] = direction
    evidence["strength"] = strength

    log_trend_analysis(symbol, str(direction), strength, adx_value, alignment)
    return direction, strength, evidence


def _score_swing_structure(
    swings: List[dict],
    label: str,
) -> Tuple[int, dict]:
    """
    Score swing structure.
    Returns (score, details_dict) where score ranges from -5 (strong bearish)
    to +5 (strong bullish).
    """
    details = {"swings_used": len(swings), "label": label}
    if len(swings) < 4:
        return 0, {**details, "reason": "insufficient_swings"}

    highs = [s for s in swings if s.get("type") == "high"]
    lows = [s for s in swings if s.get("type") == "low"]

    if len(highs) < 2 or len(lows) < 2:
        return 0, {**details, "reason": "insufficient_highs_lows"}

    # HH/HL analysis
    last_two_highs = highs[-2:]
    last_two_lows = lows[-2:]

    higher_high = _to_float(last_two_highs[-1].get("price")) > _to_float(last_two_highs[-2].get("price"))
    higher_low = _to_float(last_two_lows[-1].get("price")) > _to_float(last_two_lows[-2].get("price"))
    lower_high = _to_float(last_two_highs[-1].get("price")) < _to_float(last_two_highs[-2].get("price"))
    lower_low = _to_float(last_two_lows[-1].get("price")) < _to_float(last_two_lows[-2].get("price"))

    score = 0

    # Bullish structure
    if higher_high and higher_low:
        score = 5  # Strong uptrend
    elif higher_high:
        score = 3  # Bullish but making new highs
    elif higher_low:
        score = 1  # Mild bullish

    # Bearish structure
    if lower_high and lower_low:
        score = -5  # Strong downtrend
    elif lower_low:
        score = -3  # Bearish
    elif lower_high:
        score = -1  # Mild bearish

    # Check for protected HH/HL (more recent low > previous low while highs rising)
    if len(highs) >= 3 and len(lows) >= 3:
        third_last_high = _to_float(highs[-3].get("price"))
        third_last_low = _to_float(lows[-3].get("price"))
        last_low_price = _to_float(lows[-1].get("price"))
        second_last_low = _to_float(lows[-2].get("price"))

        # Protected higher low: recent low > previous low > previous-previous low
        if last_low_price > second_last_low > third_last_low:
            score += 1  # Extra bullish points for protected structure
        elif last_low_price < second_last_low < third_last_low:
            score -= 1  # Extra bearish points

    details["higher_high"] = higher_high
    details["higher_low"] = higher_low
    details["lower_high"] = lower_high
    details["lower_low"] = lower_low
    details["score"] = score

    return score, details


def get_protected_levels(
    htf_candles: List[dict],
    direction: str,
) -> Dict[str, Optional[float]]:
    """
    Find the protected structural level for a given direction.
    For bullish: the last swing low that must hold.
    For bearish: the last swing high that must hold.
    """
    swings = find_swing_points(htf_candles, lookback=2)
    result = {"protected_low": None, "protected_high": None}

    if direction == BULLISH:
        lows = [s for s in swings if s.get("type") == "low"]
        if len(lows) >= 2:
            # Protected low is the second-to-last swing low
            result["protected_low"] = _to_float(lows[-2].get("price"))
        elif lows:
            result["protected_low"] = _to_float(lows[-1].get("price"))
    elif direction == BEARISH:
        highs = [s for s in swings if s.get("type") == "high"]
        if len(highs) >= 2:
            result["protected_high"] = _to_float(highs[-2].get("price"))
        elif highs:
            result["protected_high"] = _to_float(highs[-1].get("price"))

    return result


def trend_supports_direction(
    trend_direction: Optional[str],
    proposed_direction: str,
    countertrend_enabled: bool = False,
) -> bool:
    """
    Check if the trend supports the proposed trade direction.
    Countertrend disabled by default.
    """
    if not trend_direction or trend_direction in (NEUTRAL, TRANSITIONING, CONFLICTING):
        return False

    trend_buy = trend_direction == BULLISH
    trend_sell = trend_direction == BEARISH
    proposed_buy = proposed_direction == "buy"
    proposed_sell = proposed_direction == "sell"

    if (trend_buy and proposed_buy) or (trend_sell and proposed_sell):
        return True
    if countertrend_enabled:
        return True
    return False
