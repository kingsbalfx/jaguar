"""Binary direct-execution compatibility helpers.

Direct execution here means a named path is fully confirmed. There is no score,
probability, or weighted override. Live trading still uses unified ICT first and
Kingsbalfx fallback from `main.py`.
"""

from typing import Any, Dict, List, Tuple

from ict_concepts.judas_swing import detect_judas_swing, should_enter_on_judas_reversal
from ict_concepts.sweet_zone import detect_sweet_zone, should_enter_on_continuation
from utils.sessions import in_london_session, in_newyork_session


def _confirmed(value: Any) -> bool:
    if isinstance(value, dict):
        return bool(value.get("confirmed") or value.get("passed") or value.get("executable"))
    return bool(value)


def _has_items(value: Any) -> bool:
    if isinstance(value, list):
        return bool(value)
    return _confirmed(value)


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


def _missing(checklist: Dict[str, bool]) -> List[str]:
    return [name for name, confirmed in checklist.items() if not confirmed]


def check_direct_execution_triggers(data: Dict, symbol: str, candles: list = None) -> Tuple[bool, Dict]:
    data = data or {}

    full_ict, ict_details = _check_full_ict_setup(data)
    if full_ict:
        return True, {
            "trigger": "FULL_ICT_SETUP",
            "confirmed": True,
            "details": ict_details,
            "reason": "All ICT core rules satisfied",
        }

    full_smt, smt_details = _check_full_smt_setup(data)
    if full_smt:
        return True, {
            "trigger": "FULL_SMT_DIVERGENCE",
            "confirmed": True,
            "details": smt_details,
            "reason": "SMT divergence path fully confirmed",
        }

    if candles:
        trend = str(data.get("trend") or data.get("direction") or "").lower()
        sweet_zone = detect_sweet_zone(candles, trend)
        if sweet_zone.get("in_sweet_zone") and should_enter_on_continuation(sweet_zone, data.get("price", 0), data.get("structure_level")):
            return True, {
                "trigger": "SWEET_ZONE_CONTINUATION",
                "confirmed": True,
                "details": sweet_zone,
                "reason": sweet_zone.get("reason") or "Sweet Zone continuation confirmed",
            }

        judas_swing = detect_judas_swing(candles, symbol)
        if judas_swing.get("is_judas_swing") and judas_swing.get("purge_confirmed") and should_enter_on_judas_reversal(judas_swing, data.get("price", 0)):
            return True, {
                "trigger": "JUDAS_SWING_REVERSAL",
                "confirmed": True,
                "details": judas_swing,
                "reason": judas_swing.get("reason") or "Judas Swing reversal confirmed",
            }

    return False, {
        "trigger": None,
        "confirmed": False,
        "reason": "No direct execution path fully confirmed",
        "ict_missing": ict_details.get("missing", []),
        "smt_missing": smt_details.get("missing", []),
    }


def _check_full_ict_setup(data: Dict) -> Tuple[bool, Dict]:
    checklist = {
        "liquidity_sweep": _confirmed(data.get("liquidity_sweep") or data.get("liq") or data.get("sweep")),
        "bos_mss": _confirmed(data.get("bos") or data.get("mss") or data.get("break_of_structure") or data.get("market_structure_shift")),
        "fvg_or_ob": _has_items(data.get("fvg") or data.get("fvgs") or data.get("order_block") or data.get("order_blocks")),
        "displacement": _confirmed(data.get("displacement") or data.get("strong_displacement")),
        "kill_zone": _killzone_active(data),
    }
    missing = _missing(checklist)
    return not missing, {**checklist, "missing": missing, "all_rules_met": not missing}


def _check_full_smt_setup(data: Dict) -> Tuple[bool, Dict]:
    smt = data.get("smt") or data.get("smt_divergence")
    smt_confirmed = bool(smt.get("confirmed") and smt.get("direction_aligned", True)) if isinstance(smt, dict) else bool(data.get("smt_confirmed"))
    checklist = {
        "smt_divergence": smt_confirmed,
        "trend_clear": str(data.get("trend") or data.get("direction") or "").lower() in ("bullish", "bearish", "buy", "sell"),
        "structure_shift": _confirmed(data.get("bos") or data.get("mss") or data.get("break_of_structure") or data.get("market_structure_shift")),
    }
    missing = _missing(checklist)
    return not missing, {**checklist, "missing": missing, "all_rules_met": not missing}


def get_direct_execution_summary(data: Dict, symbol: str, candles: list = None) -> str:
    should_execute, details = check_direct_execution_triggers(data, symbol, candles)
    if should_execute:
        return f"DIRECT EXECUTION: {details.get('trigger')} - {details.get('reason')}"
    ict_missing = ", ".join(details.get("ict_missing") or []) or "none"
    smt_missing = ", ".join(details.get("smt_missing") or []) or "none"
    return f"No direct execution path. ICT missing: {ict_missing}. SMT missing: {smt_missing}."
