"""Transparent ICT setup scoring retained for legacy callers."""

from typing import Any, Dict, Tuple


QUALITY_WEIGHTS = {
    "sweep": 16.0,
    "displacement": 16.0,
    "bos": 14.0,
    "ob_exists": 12.0,
    "fvg_exists": 12.0,
    "retracement": 10.0,
    "premium_discount": 8.0,
    "target_liquidity": 6.0,
    "smt": 3.0,
    "killzone": 3.0,
}

REGIME_MULTIPLIERS = {
    "trending": 1.0,
    "volatile": 0.9,
    "ranging": 0.65,
    "compressing": 0.55,
    "unknown": 0.5,
}


def _truth(value: Any) -> bool:
    if isinstance(value, dict):
        return bool(value.get("confirmed", value.get("active", value)))
    return bool(value)


def calculate_setup_score(features: Dict[str, Any], regime: str, killzone_active: bool = False) -> Dict[str, Any]:
    features = features or {}
    evidence = {
        "sweep": _truth(features.get("sweep")),
        "displacement": _truth(features.get("displacement")),
        "bos": _truth(features.get("bos")),
        "ob_exists": _truth(features.get("ob_exists") or features.get("htf_ob")),
        "fvg_exists": _truth(features.get("fvg_exists") or features.get("fvg")),
        "retracement": _truth(features.get("retracement") or features.get("price_in_retracement")),
        "premium_discount": _truth(features.get("premium_discount") or features.get("pd_aligned")),
        "target_liquidity": _truth(features.get("target_liquidity")),
        "smt": _truth(features.get("smt")),
        "killzone": bool(killzone_active),
    }
    raw_score = sum(QUALITY_WEIGHTS[name] for name, confirmed in evidence.items() if confirmed)
    multiplier = REGIME_MULTIPLIERS.get(str(regime or "unknown").lower(), REGIME_MULTIPLIERS["unknown"])
    score = round(raw_score * multiplier, 2)
    return {
        "score": score,
        "raw_score": raw_score,
        "maximum": sum(QUALITY_WEIGHTS.values()),
        "regime": regime,
        "regime_multiplier": multiplier,
        "evidence": evidence,
        "weights": dict(QUALITY_WEIGHTS),
    }


def calculate_success_probability(features: Dict[str, Any], regime: str, killzone_active: bool = False) -> Tuple[float, float]:
    """Compatibility API returning normalized transparent score, not a forecast probability."""
    result = calculate_setup_score(features, regime, killzone_active)
    normalized = result["score"] / result["maximum"]
    return round(normalized, 4), result["score"]
