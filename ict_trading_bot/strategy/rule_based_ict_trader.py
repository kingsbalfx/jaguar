"""Backward-compatible strict ICT rule checker.

The live strategy is `strategy.unified_strategy.evaluate_strategy`. This module
keeps the older `RuleBasedICTTrader` API working by validating the same ordered
12-gate concept model without probabilities, weights, or mandatory SMT.
"""

import logging
from typing import Any, Dict, Tuple

from strategy.unified_strategy import SEQUENCE

logger = logging.getLogger(__name__)


STATE_TO_FEATURE = {
    "higher_timeframe_narrative": ("narrative", "higher_timeframe_narrative", "context_alignment"),
    "external_liquidity": ("external_liquidity", "target_liquidity"),
    "liquidity_sweep": ("liquidity_sweep", "sweep", "liquidity_setup"),
    "strong_displacement": ("strong_displacement", "displacement"),
    "market_structure_shift": ("market_structure_shift", "bos", "mss", "break_of_structure"),
    "displacement_fvg": ("displacement_fvg", "fvg", "fvg_exists"),
    "true_order_block": ("true_order_block", "order_block_confirmed", "ob_exists"),
    "premium_discount": ("premium_discount",),
    "opposing_liquidity_target": ("opposing_liquidity_target", "target_liquidity"),
    "fvg_or_order_block_retracement": ("fvg_or_order_block_retracement", "retracement"),
    "lower_timeframe_confirmation": ("lower_timeframe_confirmation", "price_action", "execution_confirmed"),
    "market_order_execution": ("market_order_execution", "market_order", "executable"),
}


def _confirmed(value: Any) -> bool:
    if isinstance(value, dict):
        return bool(value.get("confirmed") or value.get("passed") or value.get("executable"))
    if isinstance(value, str):
        return value.lower() in ("aligned", "confirmed", "true", "yes", "execute")
    return bool(value)


class RuleBasedICTTrader:
    """Validate the strict ICT sequence using the older class interface."""

    def evaluate_trade_signal(self, analysis: Dict, symbol: str, direction: str) -> Tuple[bool, str]:
        del symbol
        analysis = analysis or {}
        expected_direction = str(direction or analysis.get("direction") or "").lower()
        result_direction = str(analysis.get("direction") or "").lower()
        if expected_direction in ("buy", "sell") and result_direction in ("buy", "sell") and expected_direction != result_direction:
            return False, f"direction mismatch: expected {expected_direction}, got {result_direction}"

        states = analysis.get("states")
        if isinstance(states, list) and states:
            observed = [state.get("name") for state in states if isinstance(state, dict)]
            if observed != list(SEQUENCE[: len(observed)]):
                return False, "ICT state sequence order is invalid"
            failed = next((state for state in states if isinstance(state, dict) and not state.get("confirmed")), None)
            if failed:
                return False, failed.get("reason") or f"missing mandatory state: {failed.get('name')}"
            if len(states) == len(SEQUENCE):
                return True, "all twelve ICT states confirmed"
            return False, f"incomplete ICT sequence: {len(states)}/{len(SEQUENCE)} states present"

        checks = self._checks_from_features(analysis)
        failed = next((name for name in SEQUENCE if not checks.get(name)), None)
        if failed:
            return False, f"missing mandatory state: {failed}"
        return True, "all twelve ICT feature states confirmed"

    def _checks_from_features(self, analysis: Dict) -> Dict[str, bool]:
        checks = {}
        for state_name, keys in STATE_TO_FEATURE.items():
            checks[state_name] = any(_confirmed(analysis.get(key)) for key in keys)
        return checks

    def breakdown(self, analysis: Dict) -> Dict[str, Any]:
        checks = self._checks_from_features(analysis or {})
        failed = next((name for name in SEQUENCE if not checks.get(name)), None)
        return {
            "confirmed": failed is None,
            "failed_step": failed,
            "checks": checks,
            "reason": "all twelve ICT feature states confirmed" if failed is None else f"missing mandatory state: {failed}",
        }


rule_based_trader = RuleBasedICTTrader()
