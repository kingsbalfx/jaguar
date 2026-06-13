"""Backward-compatible binary entry validation."""

from typing import Any, Dict


REQUIRED_STATES = (
    "narrative",
    "external_liquidity",
    "liquidity_sweep",
    "displacement",
    "bos",
    "fvg",
    "order_block_confirmed",
    "premium_discount",
    "target_liquidity",
    "retracement",
    "lower_timeframe_confirmation",
)


def _confirmed(value: Any) -> bool:
    if isinstance(value, dict):
        return bool(value.get("confirmed", value.get("passed", False)))
    return bool(value)


def validate_strict_entry(analysis: Dict = None, confirmation_flags: Dict = None, signal: Dict = None, **_ignored) -> Dict:
    analysis = analysis or {}
    flags = confirmation_flags or {}
    signal = signal or {}
    checks = {
        "narrative": bool(analysis.get("context_alignment") == "aligned" or analysis.get("narrative_confirmed")),
        "external_liquidity": _confirmed(flags.get("external_liquidity", signal.get("target_liquidity"))),
        "liquidity_sweep": _confirmed(flags.get("liquidity_sweep", flags.get("liquidity_setup"))),
        "displacement": _confirmed(flags.get("displacement")),
        "bos": _confirmed(flags.get("bos")),
        "fvg": _confirmed(flags.get("fvg")),
        "order_block_confirmed": _confirmed(flags.get("order_block_confirmed")),
        "premium_discount": _confirmed(flags.get("premium_discount", signal.get("premium_discount"))),
        "target_liquidity": _confirmed(flags.get("target_liquidity", signal.get("target_liquidity"))),
        "retracement": _confirmed(flags.get("retracement", signal.get("retracement"))),
        "lower_timeframe_confirmation": _confirmed(flags.get("lower_timeframe_confirmation", flags.get("price_action"))),
    }
    failed = next((name for name in REQUIRED_STATES if not checks[name]), None)
    return {
        "passed": failed is None,
        "executable": failed is None,
        "failed_step": failed,
        "checks": checks,
        "execution_route": "market" if failed is None else "reject",
        "reason": "all strict states confirmed" if failed is None else f"missing mandatory state: {failed}",
    }
