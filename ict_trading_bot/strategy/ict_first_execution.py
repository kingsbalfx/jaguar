"""Binary ICT-first compatibility checks.

The live bot executes through `strategy.unified_strategy` first and Kingsbalfx as
fallback. This module keeps old override imports working, but it no longer uses
partial scores, weights, or probabilities. A path is confirmed only when every
required condition is present.
"""

import logging
from typing import Any, Dict, Tuple

from utils.sessions import in_london_session, in_newyork_session

logger = logging.getLogger(__name__)


def _confirmed(value: Any) -> bool:
    if isinstance(value, dict):
        return bool(value.get("confirmed") or value.get("passed") or value.get("executable"))
    return bool(value)


def _has_items(value: Any) -> bool:
    if isinstance(value, list):
        return bool(value)
    return _confirmed(value)


def _smt_confirmed(data: Dict[str, Any]) -> bool:
    smt = data.get("smt") or data.get("smt_divergence")
    if isinstance(smt, dict):
        return bool(smt.get("confirmed") and smt.get("direction_aligned", True))
    return bool(data.get("smt_confirmed"))


def _killzone_active(data: Dict[str, Any]) -> bool:
    session = data.get("session") or data.get("session_analysis") or {}
    return bool(
        data.get("killzone_active")
        or session.get("killzone_active")
        or session.get("london_killzone")
        or session.get("newyork_killzone")
        or in_london_session()
        or in_newyork_session()
    )


def check_ict_core_rules(data: Dict, symbol: str) -> Tuple[bool, Dict]:
    del symbol
    data = data or {}
    breakdown = {
        "liquidity_sweep": _confirmed(data.get("liquidity_sweep") or data.get("liq") or data.get("sweep")),
        "market_structure_shift": _confirmed(data.get("market_structure_shift") or data.get("mss") or data.get("bos") or data.get("break_of_structure")),
        "entry_zone": _has_items(data.get("fvg") or data.get("fvgs") or data.get("order_block") or data.get("htf_ob") or data.get("htf_order_blocks")),
        "kill_zone": _killzone_active(data),
        "displacement": _confirmed(data.get("displacement") or data.get("strong_displacement")),
        "smt_divergence": _smt_confirmed(data),
    }
    required = ("liquidity_sweep", "market_structure_shift", "entry_zone", "kill_zone", "displacement")
    missing = [name for name in required if not breakdown[name]]
    breakdown["missing"] = missing
    breakdown["all_rules_met"] = not missing
    return breakdown["all_rules_met"], breakdown


def should_override_with_ict_first(
    data: Dict,
    symbol: str,
    weighted_decision: str = "",
    intelligence_decision: str = "",
    classic_decision: bool = False,
) -> Tuple[bool, Dict]:
    del weighted_decision, intelligence_decision, classic_decision
    confirmed, breakdown = check_ict_core_rules(data, symbol)
    details = {
        "ict_rules_met": confirmed,
        "breakdown": breakdown,
        "override_applied": confirmed,
        "reason": "ICT core rules satisfied" if confirmed else "ICT core rules not fully satisfied",
    }
    if confirmed:
        logger.info("[ICT-FIRST] %s: %s", symbol, details["reason"])
    return confirmed, details


def check_smt_only_rules(data: Dict, symbol: str) -> Tuple[bool, Dict]:
    del symbol
    data = data or {}
    breakdown = {
        "smt_divergence": _smt_confirmed(data),
        "market_structure_shift": _confirmed(data.get("market_structure_shift") or data.get("mss") or data.get("bos") or data.get("break_of_structure")),
        "entry_zone": _has_items(data.get("fvg") or data.get("fvgs") or data.get("order_block") or data.get("htf_ob") or data.get("htf_order_blocks")),
        "kill_zone": _killzone_active(data),
        "trend_clear": str(data.get("trend") or data.get("direction") or "").lower() in ("bullish", "bearish", "buy", "sell"),
    }
    required = tuple(breakdown.keys())
    missing = [name for name in required if not breakdown[name]]
    breakdown["missing"] = missing
    breakdown["all_rules_met"] = not missing
    return breakdown["all_rules_met"], breakdown


def should_override_with_smt_only(
    data: Dict,
    symbol: str,
    weighted_decision: str = "",
    intelligence_decision: str = "",
    classic_decision: bool = False,
) -> Tuple[bool, Dict]:
    del weighted_decision, intelligence_decision, classic_decision
    confirmed, rule_breakdown = check_smt_only_rules(data, symbol)
    details = {
        "smt_rules_met": confirmed,
        "breakdown": rule_breakdown,
        "override_applied": confirmed,
        "reason": "SMT path fully satisfied" if confirmed else "SMT-only core rules not satisfied",
    }
    if confirmed:
        logger.info("[SMT-ONLY] %s: %s", symbol, details["reason"])
    return confirmed, details


def calculate_ict_first_confidence(breakdown: Dict) -> float:
    """Legacy API: binary completion only, no partial score."""
    return 1.0 if (breakdown or {}).get("all_rules_met") else 0.0


def get_ict_first_execution_details(data: Dict, symbol: str) -> Dict:
    confirmed, breakdown = check_ict_core_rules(data, symbol)
    return {
        "ict_rules_met": confirmed,
        "complete": confirmed,
        "breakdown": breakdown,
        "execution_decision": "EXECUTE_FULL" if confirmed else "INSUFFICIENT",
        "timestamp": (data or {}).get("timestamp"),
        "symbol": symbol,
    }
