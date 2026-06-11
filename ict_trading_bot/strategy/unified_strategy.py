"""Deterministic ICT state machine shared by live trading and backtesting."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ict_concepts.fib import ote_zone, price_zone
from ict_concepts.fvg import qualify_fvgs
from ict_concepts.liquidity import rank_liquidity_zones
from ict_concepts.order_blocks import qualify_order_blocks
from strategy.setup_confirmations import bos_setup, liquidity_sweep_or_swing, price_action_setup


STATE_WEIGHTS = {
    "narrative": 10.0,
    "external_liquidity": 8.0,
    "sweep": 13.0,
    "displacement": 12.0,
    "mss_bos": 12.0,
    "true_fvg": 10.0,
    "true_order_block": 10.0,
    "premium_discount_target": 8.0,
    "retracement": 10.0,
    "confirmation": 7.0,
}


@dataclass
class StrategyState:
    name: str
    satisfied: bool
    score: float
    evidence: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "satisfied": self.satisfied,
            "score": round(self.score, 2),
            "maximum": STATE_WEIGHTS[self.name],
            "evidence": self.evidence,
            "reason": self.reason,
        }


def _inside(price: float, zone: Dict[str, Any]) -> bool:
    try:
        return float(zone["low"]) <= price <= float(zone["high"])
    except (KeyError, TypeError, ValueError):
        return False


def _overlap(left: Dict[str, Any], right: Dict[str, Any]) -> Optional[Dict[str, float]]:
    try:
        low = max(float(left["low"]), float(right["low"]))
        high = min(float(left["high"]), float(right["high"]))
    except (KeyError, TypeError, ValueError):
        return None
    if low > high:
        return None
    return {"low": low, "high": high, "midpoint": (low + high) / 2.0}


def _narrative(analysis: Dict[str, Any]) -> tuple[str, str, float, Dict[str, Any]]:
    htf = analysis.get("HTF") or {}
    topdown = analysis.get("topdown") or {}
    d1 = str(htf.get("D1") or htf.get("daily_trend") or analysis.get("daily_trend") or "").lower()
    h4 = str(htf.get("H4") or htf.get("trend") or analysis.get("overall_trend") or "").lower()
    overall = str(analysis.get("overall_trend") or "").lower()
    bullish = sum(item == "bullish" for item in (d1, h4, overall))
    bearish = sum(item == "bearish" for item in (d1, h4, overall))
    trend = "bullish" if bullish > bearish else "bearish" if bearish > bullish else "neutral"
    direction = "buy" if trend == "bullish" else "sell" if trend == "bearish" else ""
    alignment = str(topdown.get("context_alignment") or "")
    strength = max(bullish, bearish) / 3.0
    if alignment == "aligned":
        strength = max(strength, 1.0)
    elif alignment == "mixed":
        strength = max(strength, 0.67)
    return trend, direction, min(1.0, strength), {"d1": d1, "h4": h4, "overall": overall, "alignment": alignment}


def _best_retracement(
    price: float,
    order_blocks: List[Dict[str, Any]],
    fvgs: List[Dict[str, Any]],
    ote: tuple[float, float],
) -> Dict[str, Any]:
    candidates: List[Dict[str, Any]] = []
    for order_block in order_blocks[:10]:
        for fvg in fvgs[:10]:
            common = _overlap(order_block, fvg)
            if common:
                common.update({"kind": "ob_fvg_overlap", "order_block": order_block, "fvg": fvg})
                candidates.append(common)
    for kind, zones in (("order_block", order_blocks), ("fvg", fvgs)):
        for zone in zones[:10]:
            try:
                low = float(zone["low"])
                high = float(zone["high"])
            except (KeyError, TypeError, ValueError):
                continue
            candidates.append(
                {
                    "kind": kind,
                    "low": low,
                    "high": high,
                    "midpoint": float(zone.get("midpoint", (low + high) / 2.0)),
                    kind: zone,
                }
            )
    for candidate in candidates:
        candidate["price_inside"] = _inside(price, candidate)
        candidate["ote_aligned"] = not (candidate["high"] < ote[0] or candidate["low"] > ote[1])
        candidate["confluence_count"] = 1 + int(candidate["kind"] == "ob_fvg_overlap") + int(candidate["ote_aligned"])
    return max(candidates, key=lambda item: (item["price_inside"], item["confluence_count"]), default={})


def _partial_score(maximum: float, strength: float) -> float:
    return round(maximum * max(0.0, min(float(strength), 1.0)), 2)


def evaluate_strategy(
    symbol: str,
    price: float,
    analysis: Dict[str, Any],
    *,
    smt: Optional[Dict[str, Any]] = None,
    killzone_active: bool = False,
    minimum_score: float = 70.0,
) -> Dict[str, Any]:
    """Evaluate the complete ICT sequence without opaque probabilities."""
    price = float(price)
    trend, direction, narrative_strength, narrative_evidence = _narrative(analysis)
    mtf = analysis.get("MTF") or {}
    ltf = analysis.get("LTF") or {}
    execution = analysis.get("EXECUTION") or {}
    fib = mtf.get("fib") or (analysis.get("HTF") or {}).get("fib") or {}
    states: List[StrategyState] = []

    states.append(
        StrategyState(
            "narrative",
            bool(direction),
            _partial_score(STATE_WEIGHTS["narrative"], narrative_strength),
            narrative_evidence,
            "D1/H4 directional narrative",
        )
    )

    liquidity = rank_liquidity_zones(mtf.get("liquidity") or {}, price, direction)
    target = liquidity[0] if liquidity else {}
    states.append(
        StrategyState(
            "external_liquidity",
            bool(target),
            STATE_WEIGHTS["external_liquidity"] if target else 0.0,
            {"ranked": liquidity[:5], "target": target},
            "Ranked external liquidity target",
        )
    )

    sweep = liquidity_sweep_or_swing(price, analysis, direction)
    sweep_confirmed = bool(sweep.get("confirmed"))
    states.append(
        StrategyState(
            "sweep",
            sweep_confirmed,
            STATE_WEIGHTS["sweep"] if sweep_confirmed else 0.0,
            sweep,
            "Opposing external liquidity swept and reclaimed",
        )
    )

    displacement_strength = float(sweep.get("displacement_score", 0.0) or 0.0)
    displacement_confirmed = bool(sweep.get("displacement")) and displacement_strength >= 0.6
    states.append(
        StrategyState(
            "displacement",
            displacement_confirmed,
            _partial_score(STATE_WEIGHTS["displacement"], displacement_strength),
            {"strength": displacement_strength, "after_sweep": sweep_confirmed},
            "Directional displacement after the sweep",
        )
    )

    structure = bos_setup(analysis, trend)
    structure_confirmed = bool(structure.get("confirmed")) and displacement_confirmed
    states.append(
        StrategyState(
            "mss_bos",
            structure_confirmed,
            STATE_WEIGHTS["mss_bos"] if structure_confirmed else 0.0,
            structure,
            "MSS/BOS confirmed after displacement",
        )
    )

    raw_fvgs = ltf.get("fvgs") or execution.get("fvgs") or []
    fvgs = qualify_fvgs(
        raw_fvgs,
        direction=direction,
        structure_break=structure_confirmed,
        liquidity_sweep=sweep_confirmed,
        fib=fib or None,
    )
    true_fvgs = [zone for zone in fvgs if zone.get("true_fvg")]
    states.append(
        StrategyState(
            "true_fvg",
            bool(true_fvgs),
            STATE_WEIGHTS["true_fvg"] if true_fvgs else 0.0,
            {"zones": true_fvgs[:5]},
            "FVG created by the displacement sequence",
        )
    )

    raw_order_blocks = mtf.get("order_blocks") or ltf.get("order_blocks") or []
    order_blocks = qualify_order_blocks(
        raw_order_blocks,
        direction=direction,
        structure_break=structure_confirmed,
        liquidity_sweep=sweep_confirmed,
        fvgs=true_fvgs or fvgs,
        fib=fib or None,
    )
    true_order_blocks = [zone for zone in order_blocks if zone.get("true_order_block")]
    states.append(
        StrategyState(
            "true_order_block",
            bool(true_order_blocks),
            STATE_WEIGHTS["true_order_block"] if true_order_blocks else 0.0,
            {"zones": true_order_blocks[:5]},
            "Final opposing candle before displacement",
        )
    )

    zone = price_zone(price, fib) if fib else "unknown"
    pd_aligned = zone == ("discount" if direction == "buy" else "premium")
    target_valid = bool(target)
    states.append(
        StrategyState(
            "premium_discount_target",
            pd_aligned and target_valid,
            _partial_score(STATE_WEIGHTS["premium_discount_target"], (int(pd_aligned) + int(target_valid)) / 2.0),
            {"price_zone": zone, "target": target},
            "Entry side and opposing-liquidity target validation",
        )
    )

    ote = ote_zone(fib, direction) if fib and direction else (price, price)
    retracement = _best_retracement(price, true_order_blocks or order_blocks, true_fvgs or fvgs, ote)
    retracement_strength = min(float(retracement.get("confluence_count", 0)) / 3.0, 1.0)
    retracement_confirmed = bool(retracement.get("price_inside")) and retracement_strength >= (2.0 / 3.0)
    states.append(
        StrategyState(
            "retracement",
            retracement_confirmed,
            _partial_score(STATE_WEIGHTS["retracement"], retracement_strength if retracement.get("price_inside") else 0.0),
            {"zone": retracement, "ote": {"low": ote[0], "high": ote[1]}},
            "Price retraced into OB/FVG/OTE confluence",
        )
    )

    price_action = price_action_setup(analysis, trend)
    smt_aligned = bool((smt or {}).get("confirmed")) and str((smt or {}).get("direction", "")).lower() in (trend, direction)
    confirmation_strength = (
        int(bool(price_action.get("confirmed"))) + int(smt_aligned) + int(bool(killzone_active))
    ) / 3.0
    states.append(
        StrategyState(
            "confirmation",
            bool(price_action.get("confirmed")),
            _partial_score(STATE_WEIGHTS["confirmation"], confirmation_strength),
            {"price_action": price_action, "smt": smt or {}, "killzone": killzone_active},
            "M1/M5 confirmation with SMT/session modifiers",
        )
    )

    score = round(sum(state.score for state in states), 2)
    component_map = {state.name: state.satisfied for state in states}
    sequence_names = ("sweep", "displacement", "mss_bos", "true_fvg", "true_order_block")
    sequence_complete = all(next(state.satisfied for state in states if state.name == name) for name in sequence_names)
    all_states_satisfied = all(state.satisfied for state in states)
    executable = all_states_satisfied and score >= float(minimum_score)
    route = "execute" if executable else "watch" if score >= float(minimum_score) * 0.75 else "reject"

    return {
        "symbol": symbol,
        "trend": trend,
        "direction": direction,
        "score": score,
        "maximum_score": sum(STATE_WEIGHTS.values()),
        "minimum_score": float(minimum_score),
        "route": route,
        "executable": executable,
        "sequence_complete": sequence_complete,
        "all_states_satisfied": all_states_satisfied,
        "states": [state.as_dict() for state in states],
        "components": component_map,
        "liquidity_sweep": sweep,
        "structure": structure,
        "qualified_fvgs": fvgs,
        "qualified_order_blocks": order_blocks,
        "retracement": retracement,
        "ote_zone": {"low": ote[0], "high": ote[1]},
        "premium_discount_zone": zone,
        "target_liquidity": liquidity[:5],
        "reason": f"{route}: score={score:.2f}, strict_sequence={sequence_complete}, retracement={retracement_confirmed}",
    }


def evaluate_unified_setup(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    """Compatibility entry point for existing live and backtest callers."""
    result = evaluate_strategy(*args, **kwargs)
    route_map = {"execute": "elite", "watch": "conservative", "reject": "observe"}
    result["confidence"] = result["score"]
    result["execution_route"] = route_map[result["route"]]
    result["risk_multiplier"] = 1.0 if result["route"] == "execute" else 0.0
    return result
