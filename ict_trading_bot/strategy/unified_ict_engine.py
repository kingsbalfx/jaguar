"""Unified ICT setup evaluation shared by live execution and backtesting."""

from typing import Dict, List, Optional

from ict_concepts.fib import ote_zone, price_zone
from ict_concepts.fvg import qualify_fvgs
from ict_concepts.order_blocks import qualify_order_blocks
from ict_concepts.liquidity import rank_liquidity_zones
from strategy.setup_confirmations import bos_setup, liquidity_sweep_or_swing, price_action_setup


WEIGHTS = {
    "htf_narrative": 12.0,
    "liquidity_sweep": 13.0,
    "displacement": 12.0,
    "structure_shift": 12.0,
    "true_fvg": 11.0,
    "true_order_block": 11.0,
    "retracement": 10.0,
    "premium_discount": 7.0,
    "price_action": 6.0,
    "smt": 3.0,
    "killzone": 3.0,
}


def _inside(price: float, zone: Dict) -> bool:
    try:
        return float(zone["low"]) <= float(price) <= float(zone["high"])
    except Exception:
        return False


def _overlap(a: Dict, b: Dict) -> Optional[Dict]:
    try:
        low = max(float(a["low"]), float(b["low"]))
        high = min(float(a["high"]), float(b["high"]))
    except Exception:
        return None
    if low > high:
        return None
    return {"low": low, "high": high, "midpoint": (low + high) / 2.0}


def _best_retracement(price: float, obs: List[Dict], fvgs: List[Dict], ote: tuple) -> Dict:
    candidates = []
    for ob in obs[:8]:
        for fvg in fvgs[:8]:
            shared = _overlap(ob, fvg)
            if not shared:
                continue
            shared["kind"] = "ob_fvg_overlap"
            shared["ob"] = ob
            shared["fvg"] = fvg
            shared["score"] = 1.0 + float(ob.get("narrative_score", 0.0)) + float(fvg.get("narrative_score", 0.0))
            candidates.append(shared)
    for kind, zones in (("order_block", obs), ("fvg", fvgs)):
        for zone in zones[:8]:
            candidate = {
                "kind": kind,
                "low": float(zone["low"]),
                "high": float(zone["high"]),
                "midpoint": float(zone.get("midpoint", (float(zone["low"]) + float(zone["high"])) / 2.0)),
                "score": float(zone.get("narrative_score", zone.get("quality", 0.0))),
                kind: zone,
            }
            candidates.append(candidate)
    ote_low, ote_high = ote
    for candidate in candidates:
        candidate["ote_aligned"] = not (candidate["high"] < ote_low or candidate["low"] > ote_high)
        candidate["price_inside"] = candidate["low"] <= price <= candidate["high"]
        candidate["score"] += 0.75 if candidate["ote_aligned"] else 0.0
        candidate["score"] += 0.5 if candidate["price_inside"] else 0.0
    if not candidates:
        return {}
    return max(candidates, key=lambda item: item["score"])


def evaluate_unified_setup(
    symbol: str,
    price: float,
    analysis: Dict,
    *,
    smt: Dict = None,
    killzone_active: bool = False,
) -> Dict:
    """Evaluate an ICT narrative using soft confluence scoring."""
    trend = str((analysis or {}).get("overall_trend") or "neutral").lower()
    if trend not in ("bullish", "bearish"):
        return {"symbol": symbol, "direction": None, "confidence": 0.0, "execution_route": "skip", "reason": "no_directional_structure"}
    direction = "buy" if trend == "bullish" else "sell"
    mtf = (analysis or {}).get("MTF") or {}
    ltf = (analysis or {}).get("LTF") or {}
    execution = (analysis or {}).get("EXECUTION") or {}
    fib = mtf.get("fib") or (analysis or {}).get("HTF", {}).get("fib") or {}

    liquidity = liquidity_sweep_or_swing(price, analysis, direction)
    structure = bos_setup(analysis, trend)
    price_action = price_action_setup(analysis, trend)
    displacement_score = float(liquidity.get("displacement_score", 0.0) or 0.0)
    structure_shift = bool(structure.get("confirmed"))
    sweep = bool(liquidity.get("confirmed"))
    raw_fvgs = ltf.get("fvgs") or execution.get("fvgs") or []
    raw_obs = mtf.get("order_blocks") or ltf.get("order_blocks") or []
    fvgs = qualify_fvgs(raw_fvgs, direction=direction, structure_break=structure_shift, liquidity_sweep=sweep, fib=fib or None)
    obs = qualify_order_blocks(raw_obs, direction=direction, structure_break=structure_shift, liquidity_sweep=sweep, fvgs=fvgs, fib=fib or None)
    true_fvgs = [item for item in fvgs if item.get("true_fvg")]
    true_obs = [item for item in obs if item.get("true_order_block")]
    ote = ote_zone(fib, direction) if fib else (price, price)
    retracement = _best_retracement(float(price), true_obs or obs, true_fvgs or fvgs, ote)

    context_alignment = str((analysis.get("topdown") or {}).get("context_alignment") or "unclear")
    pd_zone = price_zone(price, fib) if fib else "unknown"
    pd_aligned = pd_zone == ("discount" if direction == "buy" else "premium")
    smt_aligned = bool((smt or {}).get("confirmed") and (smt or {}).get("direction") == trend)
    target_liquidity = rank_liquidity_zones(mtf.get("liquidity") or {}, price, direction)

    components = {
        "htf_narrative": context_alignment in ("aligned", "mixed"),
        "liquidity_sweep": sweep,
        "displacement": displacement_score >= 0.60,
        "structure_shift": structure_shift,
        "true_fvg": bool(true_fvgs),
        "true_order_block": bool(true_obs),
        "retracement": bool(retracement.get("price_inside")),
        "premium_discount": pd_aligned,
        "price_action": bool(price_action.get("confirmed")),
        "smt": smt_aligned,
        "killzone": bool(killzone_active),
    }
    score = sum(WEIGHTS[name] for name, passed in components.items() if passed)
    sequence_core = sum(1 for name in ("liquidity_sweep", "displacement", "structure_shift") if components[name])
    if sequence_core == 3:
        score += 5.0
    if retracement.get("kind") == "ob_fvg_overlap":
        score += 4.0
    if retracement.get("ote_aligned"):
        score += 3.0
    if target_liquidity:
        score += 3.0
    score = round(min(100.0, score), 1)

    if score >= 78:
        route, risk_multiplier = "elite", 1.0
    elif score >= 64:
        route, risk_multiplier = "standard", 0.75
    elif score >= 52:
        route, risk_multiplier = "conservative", 0.45
    else:
        route, risk_multiplier = "observe", 0.0

    return {
        "symbol": symbol,
        "trend": trend,
        "direction": direction,
        "confidence": score,
        "execution_route": route,
        "risk_multiplier": risk_multiplier,
        "components": components,
        "sequence_core_count": sequence_core,
        "liquidity_sweep": liquidity,
        "structure": structure,
        "price_action": price_action,
        "qualified_fvgs": fvgs,
        "qualified_order_blocks": obs,
        "retracement": retracement,
        "ote_zone": {"low": ote[0], "high": ote[1]},
        "premium_discount_zone": pd_zone,
        "target_liquidity": target_liquidity[:3],
        "smt": smt or {},
        "reason": f"{route} setup at {score}/100 with {sequence_core}/3 sweep-displacement-structure sequence",
    }
