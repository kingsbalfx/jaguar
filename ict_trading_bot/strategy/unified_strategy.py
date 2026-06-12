"""Strict ordered ICT state machine shared by live trading and backtesting."""

from typing import Any, Dict, List, Optional

from ict_concepts.fib import ote_zone, price_zone
from ict_concepts.fvg import qualify_fvgs
from ict_concepts.liquidity import rank_liquidity_zones
from ict_concepts.order_blocks import qualify_order_blocks
from strategy.setup_confirmations import bos_setup, liquidity_sweep_or_swing, price_action_setup


SEQUENCE = (
    "narrative",
    "external_liquidity",
    "liquidity_sweep",
    "displacement",
    "mss_bos",
    "true_fvg",
    "true_order_block",
    "premium_discount_target",
    "retracement",
    "m1_m5_confirmation",
)


def _state(name: str, confirmed: bool, evidence: Dict[str, Any], reason: str) -> Dict[str, Any]:
    return {"name": name, "confirmed": bool(confirmed), "evidence": evidence, "reason": reason}


def _inside(price: float, zone: Dict[str, Any]) -> bool:
    try:
        return float(zone["low"]) <= float(price) <= float(zone["high"])
    except (KeyError, TypeError, ValueError):
        return False


def _overlap(left: Dict[str, Any], right: Dict[str, Any]) -> Optional[Dict[str, float]]:
    try:
        low = max(float(left["low"]), float(right["low"]))
        high = min(float(left["high"]), float(right["high"]))
    except (KeyError, TypeError, ValueError):
        return None
    return {"low": low, "high": high, "midpoint": (low + high) / 2.0} if low <= high else None


def _narrative(analysis: Dict[str, Any]) -> tuple[str, str, Dict[str, Any]]:
    htf = analysis.get("HTF") or {}
    topdown = analysis.get("topdown") or {}
    daily = analysis.get("DAILY") or analysis.get("D1") or {}
    h4_context = analysis.get("H4_CONTEXT") or {}
    d1 = str(
        htf.get("D1")
        or htf.get("daily_trend")
        or daily.get("trend")
        or topdown.get("daily_trend")
        or analysis.get("daily_trend")
        or ""
    ).lower()
    h4 = str(
        htf.get("H4")
        or h4_context.get("trend")
        or topdown.get("h4_trend")
        or htf.get("trend")
        or ""
    ).lower()
    overall = str(analysis.get("overall_trend") or "").lower()
    directions = (d1, h4, overall)
    trend = d1 if all(item in ("bullish", "bearish") and item == d1 for item in directions) else "neutral"
    return trend, "buy" if trend == "bullish" else "sell" if trend == "bearish" else "", {
        "D1": d1,
        "H4": h4,
        "overall": overall,
    }


def _retracement(
    price: float,
    order_blocks: List[Dict[str, Any]],
    fvgs: List[Dict[str, Any]],
    ote: tuple[float, float],
) -> Dict[str, Any]:
    for order_block in order_blocks:
        for fvg in fvgs:
            shared = _overlap(order_block, fvg)
            if shared and _inside(price, shared) and not (shared["high"] < ote[0] or shared["low"] > ote[1]):
                return {**shared, "kind": "ob_fvg_ote", "order_block": order_block, "fvg": fvg, "confirmed": True}
    return {"confirmed": False}


def evaluate_strategy(
    symbol: str,
    price: float,
    analysis: Dict[str, Any],
    *,
    smt: Optional[Dict[str, Any]] = None,
    killzone_active: bool = False,
) -> Dict[str, Any]:
    """Validate every ICT state in order and reject at the first missing state."""
    states: List[Dict[str, Any]] = []

    def require(name: str, confirmed: bool, evidence: Dict[str, Any], reason: str) -> bool:
        states.append(_state(name, confirmed, evidence, reason))
        return bool(confirmed)

    trend, direction, narrative = _narrative(analysis)
    if not require("narrative", bool(direction), narrative, "D1, H4, and overall trend must agree"):
        return _result(symbol, trend, direction, states)

    mtf = analysis.get("MTF") or {}
    ltf = analysis.get("LTF") or {}
    execution = analysis.get("EXECUTION") or {}
    fib = mtf.get("fib") or (analysis.get("HTF") or {}).get("fib") or {}
    liquidity = rank_liquidity_zones(mtf.get("liquidity") or {}, price, direction)
    target = liquidity[0] if liquidity else {}
    if not require("external_liquidity", bool(target), {"ranked": liquidity, "target": target}, "Opposing external liquidity must exist"):
        return _result(symbol, trend, direction, states)

    sweep = liquidity_sweep_or_swing(price, analysis, direction)
    if not require("liquidity_sweep", bool(sweep.get("confirmed")), sweep, "External liquidity must be swept and reclaimed"):
        return _result(symbol, trend, direction, states)

    displacement = bool(sweep.get("displacement"))
    if not require("displacement", displacement, sweep, "Directional displacement must occur after the sweep"):
        return _result(symbol, trend, direction, states)

    structure = bos_setup(analysis, trend)
    structure_confirmed = displacement and bool(structure.get("confirmed"))
    if not require("mss_bos", structure_confirmed, structure, "MSS/BOS must be caused by displacement"):
        return _result(symbol, trend, direction, states)

    fvgs = qualify_fvgs(
        ltf.get("fvgs") or execution.get("fvgs") or [],
        direction=direction,
        structure_break=structure_confirmed,
        liquidity_sweep=True,
        fib=fib or None,
    )
    true_fvgs = [zone for zone in fvgs if zone.get("true_fvg")]
    if not require("true_fvg", bool(true_fvgs), {"zones": true_fvgs}, "Displacement must create a fresh directional FVG"):
        return _result(symbol, trend, direction, states)

    order_blocks = qualify_order_blocks(
        mtf.get("order_blocks") or ltf.get("order_blocks") or [],
        direction=direction,
        structure_break=structure_confirmed,
        liquidity_sweep=True,
        fvgs=true_fvgs,
        fib=fib or None,
    )
    true_order_blocks = [zone for zone in order_blocks if zone.get("true_order_block")]
    if not require("true_order_block", bool(true_order_blocks), {"zones": true_order_blocks}, "Final opposing candle before displacement must be fresh"):
        return _result(symbol, trend, direction, states)

    zone = price_zone(price, fib) if fib else "unknown"
    pd_valid = zone == ("discount" if direction == "buy" else "premium")
    if not require("premium_discount_target", pd_valid and bool(target), {"price_zone": zone, "target": target}, "Entry must be in the correct dealing-range half with a valid target"):
        return _result(symbol, trend, direction, states)

    ote = ote_zone(fib, direction)
    retracement = _retracement(price, true_order_blocks, true_fvgs, ote)
    if not require("retracement", bool(retracement.get("confirmed")), {"zone": retracement, "ote": {"low": ote[0], "high": ote[1]}}, "Price must retrace into overlapping OB, FVG, and OTE"):
        return _result(symbol, trend, direction, states)

    price_action = price_action_setup(analysis, trend)
    smt_confirmed = bool((smt or {}).get("confirmed")) and str((smt or {}).get("direction", "")).lower() in (trend, direction)
    confirmation = bool(price_action.get("confirmed")) and smt_confirmed and bool(killzone_active)
    require("m1_m5_confirmation", confirmation, {"price_action": price_action, "smt": smt or {}, "killzone": killzone_active}, "M1/M5 price action, SMT, and killzone must confirm")
    return _result(symbol, trend, direction, states, retracement=retracement, target_liquidity=liquidity)


def _result(
    symbol: str,
    trend: str,
    direction: str,
    states: List[Dict[str, Any]],
    *,
    retracement: Optional[Dict[str, Any]] = None,
    target_liquidity: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    confirmed = len(states) == len(SEQUENCE) and all(state["confirmed"] for state in states)
    failed = next((state for state in states if not state["confirmed"]), None)
    return {
        "symbol": symbol,
        "trend": trend,
        "direction": direction,
        "confirmed": confirmed,
        "executable": confirmed,
        "status": "confirmed" if confirmed else "rejected",
        "failed_step": failed["name"] if failed else None,
        "reason": "all ICT sequence states confirmed" if confirmed else failed["reason"] if failed else "incomplete ICT sequence",
        "states": states,
        "retracement": retracement or {},
        "target_liquidity": target_liquidity or [],
    }


def evaluate_unified_setup(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    return evaluate_strategy(*args, **kwargs)
