"""
FALLBACK STRATEGY 5 — Model C: Trend Liquidity Sweep Continuation
==================================================================
Bullish:
1. Confirmed bullish trend.
2. Price pulls back.
3. Price sweeps a minor lower-timeframe low or equal lows.
4. The sweep remains above the protected higher-timeframe trend low.
5. Bearish continuation fails.
6. Bullish displacement appears.
7. M1 or M5 bullish CHOCH confirms.
8. Entry occurs on reaction or retracement.
9. Target is trend-side internal liquidity or next swing high.

Bearish is inverse.

This is NOT a countertrend sweep — it's a trend continuation sweep.
"""

from typing import List, Tuple

from . import config
from .indicators import (
    atr, candle_body_ratio, candle_range, candle_direction, candle_body,
    _to_float,
)
from .trend import get_protected_levels, BULLISH, BEARISH
from .fb5_logging import log_setup_scan


def evaluate_model_c(
    symbol: str,
    direction: str,
    trend_direction: str,
    setup_candles: List[dict],
    exec_candles: List[dict],
    htf_candles: List[dict],
    atr_value: float,
) -> Tuple[bool, dict]:
    """
    Evaluate Model C: Trend Liquidity Sweep Continuation.
    
    Returns:
        (passed, result_dict)
    """
    result = {
        "model": "C",
        "detected": False,
        "sweep_detected": False,
        "sweep_extreme": None,
        "sweep_returned_inside": False,
        "sweep_depth_atr": 0.0,
        "protected_structure_preserved": False,
        "continue_failed": False,
        "displacement_confirmed": False,
        "choch_confirmed": False,
        "entry_price": None,
        "stop_loss": None,
        "score": 0,
        "rejection_reason": "",
    }

    if direction == "buy" and trend_direction != BULLISH:
        result["rejection_reason"] = "trend_not_bullish"
        return False, result
    if direction == "sell" and trend_direction != BEARISH:
        result["rejection_reason"] = "trend_not_bearish"
        return False, result

    trading_candles = exec_candles if len(exec_candles) >= 20 else setup_candles
    if len(trading_candles) < 20:
        result["rejection_reason"] = f"insufficient_candles:{len(trading_candles)}<20"
        return False, result

    # ============================================================
    # 1. Find protected structure level
    # ============================================================
    protected = get_protected_levels(htf_candles, trend_direction)

    # ============================================================
    # 2. Find the sweep
    # ============================================================
    recent = trading_candles[-min(30, len(trading_candles)):]
    sweep_idx = None
    sweep_extreme_price = None
    preceding_low = None
    preceding_high = None

    if direction == "buy":
        # Look for a sweep of a minor low (sell-side liquidity)
        # Find the most recent local low that was broken to the downside
        for i in range(len(recent) - 1, 2, -1):
            if i + 1 < len(recent):
                current_low = _to_float(recent[i].get("low"))
                prev_low = _to_float(recent[i - 1].get("low"))
                next_low = _to_float(recent[i + 1].get("low"))
                # A swing low
                if prev_low >= current_low <= next_low:
                    # Check if any subsequent candle breaks below this low
                    for j in range(i + 1, len(recent)):
                        if _to_float(recent[j].get("low")) < current_low:
                            sweep_idx = j
                            sweep_extreme_price = min(
                                _to_float(c.get("low")) for c in recent[i:j + 1]
                            )
                            preceding_low = current_low
                            break
                    if sweep_idx:
                        break
    else:
        # Look for a sweep of a minor high (buy-side liquidity)
        for i in range(len(recent) - 1, 2, -1):
            if i + 1 < len(recent):
                current_high = _to_float(recent[i].get("high"))
                prev_high = _to_float(recent[i - 1].get("high"))
                next_high = _to_float(recent[i + 1].get("high"))
                if prev_high <= current_high >= next_high:
                    for j in range(i + 1, len(recent)):
                        if _to_float(recent[j].get("high")) > current_high:
                            sweep_idx = j
                            sweep_extreme_price = max(
                                _to_float(c.get("high")) for c in recent[i:j + 1]
                            )
                            preceding_high = current_high
                            break
                    if sweep_idx:
                        break

    if sweep_idx is None or sweep_extreme_price is None:
        result["rejection_reason"] = "no_sweep_detected"
        return False, result

    result["sweep_detected"] = True
    result["sweep_extreme"] = sweep_extreme_price

    # ============================================================
    # 3. Check sweep remains above protected structure
    # ============================================================
    if direction == "buy":
        protected_low = protected.get("protected_low")
        if protected_low and sweep_extreme_price <= protected_low:
            result["rejection_reason"] = f"sweep_below_protected_low:{sweep_extreme_price:.5f}_<={protected_low:.5f}"
            return False, result
        result["protected_structure_preserved"] = True
    else:
        protected_high = protected.get("protected_high")
        if protected_high and sweep_extreme_price >= protected_high:
            result["rejection_reason"] = f"sweep_above_protected_high:{sweep_extreme_price:.5f}_>={protected_high:.5f}"
            return False, result
        result["protected_structure_preserved"] = True

    # ============================================================
    # 4. Check sweep depth
    # ============================================================
    if direction == "buy":
        # Swept below a minor low, now check depth
        if preceding_low:
            sweep_depth = preceding_low - sweep_extreme_price
            sweep_depth_atr = sweep_depth / atr_value if atr_value > 0 else 0
            result["sweep_depth_atr"] = round(sweep_depth_atr, 3)

            if sweep_depth_atr > 1.0:
                result["rejection_reason"] = f"sweep_too_deep:{sweep_depth_atr:.2f}atr"
                return False, result
    else:
        if preceding_high:
            sweep_depth = sweep_extreme_price - preceding_high
            sweep_depth_atr = sweep_depth / atr_value if atr_value > 0 else 0
            result["sweep_depth_atr"] = round(sweep_depth_atr, 3)

            if sweep_depth_atr > 1.0:
                result["rejection_reason"] = f"sweep_too_deep:{sweep_depth_atr:.2f}atr"
                return False, result

    # ============================================================
    # 5. Check price returned inside (bearish failure)
    # ============================================================
    post_sweep = recent[sweep_idx + 1:]
    if not post_sweep:
        result["rejection_reason"] = "no_candles_after_sweep"
        return False, result

    returned_inside = False
    for c in post_sweep[:min(5, len(post_sweep))]:
        if direction == "buy":
            # Price returned above the swept low
            if _to_float(c.get("close")) > (preceding_low or sweep_extreme_price):
                returned_inside = True
                break
        else:
            if _to_float(c.get("close")) < (preceding_high or sweep_extreme_price):
                returned_inside = True
                break

    result["sweep_returned_inside"] = returned_inside
    if not returned_inside:
        result["rejection_reason"] = "price_not_returned_after_sweep"
        return False, result

    # ============================================================
    # 6. Check bearish continuation failed / bullish displacement
    # ============================================================
    displacement_found = False
    choch_found = False
    for i, c in enumerate(post_sweep[:min(5, len(post_sweep))]):
        c_dir = candle_direction(c)
        body_ratio = candle_body_ratio(c)
        c_range = candle_range(c)

        if direction == "buy":
            # Bullish displacement
            if c_dir == "bullish" and body_ratio >= config.CONFIRMATION_MIN_BODY_RATIO and c_range >= atr_value * 0.5:
                displacement_found = True
                # CHOCH: close above previous candle high
                if i > 0 and _to_float(c.get("close")) > _to_float(post_sweep[i - 1].get("high")):
                    choch_found = True
                break
        else:
            if c_dir == "bearish" and body_ratio >= config.CONFIRMATION_MIN_BODY_RATIO and c_range >= atr_value * 0.5:
                displacement_found = True
                if i > 0 and _to_float(c.get("close")) < _to_float(post_sweep[i - 1].get("low")):
                    choch_found = True
                break

    result["displacement_confirmed"] = displacement_found
    result["choch_confirmed"] = choch_found

    if not displacement_found:
        result["rejection_reason"] = "no_displacement_after_sweep"
        return False, result

    # ============================================================
    # 7. Score
    # ============================================================
    score = 0
    if result["sweep_detected"]:
        score += 15
    if result["sweep_returned_inside"]:
        score += 15
    if result["protected_structure_preserved"]:
        score += 15
    if 0.2 <= result.get("sweep_depth_atr", 0) <= 0.5:
        score += 10  # Ideal sweep depth
    if displacement_found:
        score += 15
    if choch_found:
        score += 15

    result["score"] = score
    result["detected"] = score >= 50

    if not result["detected"]:
        result["rejection_reason"] = f"score_{score}_below_50"

    log_setup_scan(symbol, "C", result["detected"], result.get("rejection_reason", ""), score)
    return result["detected"], result
