"""
FALLBACK STRATEGY 5 — Volatility Regime Classification
========================================================
Classifies volatility using ATR and rolling percentiles.
Rejects trades when volatility is unsuitable.
"""

from typing import List, Tuple

from . import config
from .indicators import atr, _to_float


# Regime constants
TOO_LOW = "too_low"
TRADABLE = "tradable"
ELEVATED = "elevated"
EXTREME = "extreme"
DISLOCATED = "dislocated"


def classify_volatility(
    candles: List[dict],
    atr_value: float,
    price: float,
) -> Tuple[str, float, dict]:
    """
    Classify the current volatility regime.
    
    Returns:
        (regime_label, atr_value, evidence_dict)
    """
    evidence = {
        "atr": atr_value,
        "atr_as_fraction_of_price": 0.0,
        "rolling_atr_percentile": 0.0,
        "recent_candle_max_range": 0.0,
    }

    if atr_value <= 0:
        return TOO_LOW, atr_value, evidence

    evidence["atr_as_fraction_of_price"] = atr_value / price if price > 0 else 0

    # Check if ATR is too low relative to price
    if evidence["atr_as_fraction_of_price"] < config.VOLATILITY_LOW_ATR_RATIO:
        return TOO_LOW, atr_value, evidence

    # Calculate recent max candle range
    recent = candles[-min(30, len(candles)):] if candles else []
    if recent:
        evidence["recent_candle_max_range"] = max(
            _to_float(c.get("high", 0)) - _to_float(c.get("low", 0))
            for c in recent
        )

    # Rolling ATR percentile
    if len(candles) >= config.ATR_PERIOD * (config.VOLATILITY_LOOKBACK_DAYS + 1):
        all_atrs = []
        for i in range(config.ATR_PERIOD * config.VOLATILITY_LOOKBACK_DAYS, len(candles)):
            lookback_candles = candles[i - config.ATR_PERIOD: i]
            all_atrs.append(atr(lookback_candles, config.ATR_PERIOD))

        if all_atrs and atr_value > 0:
            below_count = sum(1 for a in all_atrs if a <= atr_value)
            percentile = below_count / len(all_atrs)
            evidence["rolling_atr_percentile"] = round(percentile, 3)

            if percentile >= config.VOLATILITY_EXTREME_PERCENTILE:
                return EXTREME, atr_value, evidence
            if percentile >= config.VOLATILITY_HIGH_PERCENTILE:
                return ELEVATED, atr_value, evidence

    return TRADABLE, atr_value, evidence


def check_spread(
    spread: float,
    atr_value: float,
    target_distance: float,
    symbol_profile: dict,
) -> Tuple[bool, str]:
    """
    Check if spread is acceptable for trading.
    Returns (passes, reason).
    """
    if spread <= 0:
        return False, "spread_zero_or_negative"

    # Check spread as fraction of ATR
    if atr_value > 0 and spread / atr_value > config.SPREAD_MAX_ATR_FRACTION:
        return False, f"spread_to_atr_ratio_{spread/atr_value:.4f}_>_{config.SPREAD_MAX_ATR_FRACTION}"

    # Check spread as fraction of target
    if target_distance > 0 and spread / target_distance > config.SPREAD_MAX_AS_TARGET_FRACTION:
        return False, f"spread_consumes_{spread/target_distance:.1%}_of_target"

    # Check against symbol profile
    max_points = symbol_profile.get("spread_max_points", 100)
    if spread > max_points * 0.0001:  # rough conversion
        return False, f"spread_{spread:.5f}_exceeds_symbol_max"

    return True, "spread_acceptable"


def check_execution_quality(
    requested_price: float,
    filled_price: float,
    slippage_allowed: float,
) -> Tuple[bool, float]:
    """
    Check if execution quality is acceptable.
    Returns (passes, actual_slippage).
    """
    if requested_price <= 0 or filled_price <= 0:
        return False, 0
    slippage = abs(filled_price - requested_price)
    if slippage > slippage_allowed:
        return False, slippage
    return True, slippage
