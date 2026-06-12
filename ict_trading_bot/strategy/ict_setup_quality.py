"""Binary ICT setup validation helpers."""

from typing import Any, Dict


REQUIRED_FLAGS = (
    "sweep",
    "displacement",
    "bos",
    "ob_exists",
    "fvg_exists",
    "retracement",
    "premium_discount",
    "target_liquidity",
    "smt",
)


def _confirmed(value: Any) -> bool:
    return bool(value.get("confirmed")) if isinstance(value, dict) else bool(value)


def validate_setup(features: Dict[str, Any], regime: str, killzone_active: bool = False) -> Dict[str, Any]:
    features = features or {}
    checks = {name: _confirmed(features.get(name)) for name in REQUIRED_FLAGS}
    checks["trend_regime"] = str(regime or "").lower() == "trending"
    checks["killzone"] = bool(killzone_active)
    failed = next((name for name, confirmed in checks.items() if not confirmed), None)
    return {
        "confirmed": failed is None,
        "failed_step": failed,
        "checks": checks,
        "reason": "all setup conditions confirmed" if failed is None else f"missing condition: {failed}",
    }
