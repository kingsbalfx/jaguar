"""Binary ICT setup validation helpers."""

from typing import Any, Dict


REQUIRED_FLAGS = (
    "sweep",
    "displacement",
    "bos",
    "fvg_exists",
    "ob_exists",
    "premium_discount",
    "target_liquidity",
    "retracement",
    "lower_timeframe_confirmation",
)


def _confirmed(value: Any) -> bool:
    return bool(value.get("confirmed")) if isinstance(value, dict) else bool(value)


def validate_setup(features: Dict[str, Any], regime: str, killzone_active: bool = False) -> Dict[str, Any]:
    del regime, killzone_active
    features = features or {}
    checks = {name: _confirmed(features.get(name)) for name in REQUIRED_FLAGS}
    failed = next((name for name, confirmed in checks.items() if not confirmed), None)
    return {
        "confirmed": failed is None,
        "failed_step": failed,
        "checks": checks,
        "reason": "all setup conditions confirmed" if failed is None else f"missing condition: {failed}",
    }
