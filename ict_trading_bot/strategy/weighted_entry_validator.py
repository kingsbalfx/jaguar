"""
Weighted Entry Validator
========================
Strict confidence scoring that cannot override the mandatory ICT sequence.
"""

from typing import Dict, Tuple


def _confirmation_passed(flag) -> bool:
    if isinstance(flag, bool):
        return flag
    if isinstance(flag, dict):
        return bool(flag.get("confirmed", flag.get("passed", False)))
    return False


def _displacement_score(flag) -> float:
    if isinstance(flag, (int, float)):
        return float(flag)
    if isinstance(flag, dict):
        return float(flag.get("score", flag.get("displacement_score", 0.0)) or 0.0)
    return 0.0


def calculate_entry_confidence(
    signal: Dict,
    analysis: Dict,
    trend: str,
    price: float,
    confirmation_flags: Dict = None,
    cis_decision: Dict = None,
) -> Dict:
    if confirmation_flags is None:
        confirmation_flags = {}

    component_scores = {}
    market_rhythm = (analysis or {}).get("market_rhythm") or {}
    cis_history = int((cis_decision or {}).get("history_count", 0) or 0)
    cis_timing_score = float((cis_decision or {}).get("component_scores", {}).get("timing", 0.5) or 0.5)
    cis_setup_quality = float((cis_decision or {}).get("component_scores", {}).get("setup_quality", 0.0) or 0.0)

    has_liquidity = _confirmation_passed(confirmation_flags.get("liquidity_setup"))
    has_bos = _confirmation_passed(confirmation_flags.get("bos"))
    displacement_score = max(
        _displacement_score(confirmation_flags.get("displacement")),
        float((confirmation_flags.get("liquidity_setup") or {}).get("displacement_score", 0.0) or 0.0),
        float(signal.get("displacement", 0.0) or 0.0),
    )
    has_displacement = displacement_score >= 0.70
    has_fvg = _confirmation_passed(confirmation_flags.get("fvg")) or bool(signal.get("valid_fvg"))
    has_order_block = _confirmation_passed(confirmation_flags.get("order_block_confirmed")) or bool(signal.get("valid_order_block"))

    component_scores["core_liquidity"] = 100.0 if has_liquidity else 0.0
    component_scores["core_bos"] = 100.0 if has_bos else 0.0
    component_scores["core_displacement"] = round(min(100.0, displacement_score * 100.0), 1)
    component_scores["core_fvg"] = 100.0 if has_fvg else 0.0
    component_scores["core_order_block"] = 100.0 if has_order_block else 0.0

    missing_core = []
    if not has_liquidity:
        missing_core.append("liquidity_sweep")
    if not has_bos:
        missing_core.append("bos")
    if not has_displacement:
        missing_core.append("displacement")
    if not has_fvg:
        missing_core.append("valid_fvg")
    if not has_order_block:
        missing_core.append("valid_order_block")

    if market_rhythm.get("should_avoid_entry"):
        return {
            "confidence": 0.0,
            "execution_route": "skip",
            "component_scores": component_scores,
            "alternative_path": None,
            "reasoning": market_rhythm.get("summary", "Market rhythm rejects new entries."),
            "cis_timing_score": cis_timing_score,
            "cis_setup_quality": cis_setup_quality,
            "backtest_required": False,
            "market_rhythm": market_rhythm,
            "missing_core": missing_core,
        }

    if missing_core:
        return {
            "confidence": 0.0,
            "execution_route": "skip",
            "component_scores": component_scores,
            "alternative_path": None,
            "reasoning": f"STRICT ICT REJECT: missing {', '.join(missing_core)}.",
            "cis_timing_score": cis_timing_score,
            "cis_setup_quality": cis_setup_quality,
            "backtest_required": False,
            "market_rhythm": market_rhythm,
            "missing_core": missing_core,
        }

    topdown_score = _score_topdown(analysis, trend)
    trend_alignment_score = _score_trend_alignment(analysis, trend)
    price_action_score = _score_price_action_confirmation(confirmation_flags)
    setup_score = _score_setup_structure(confirmation_flags, signal)
    confirmation_score = _score_confirmation_count(confirmation_flags)
    market_rhythm_score = _score_market_rhythm(analysis)

    component_scores.update(
        {
            "topdown": topdown_score,
            "trend_alignment": trend_alignment_score,
            "price_action": price_action_score,
            "setup_structure": setup_score,
            "confirmations": confirmation_score,
            "market_rhythm": market_rhythm_score,
        }
    )

    if topdown_score < 70 or trend_alignment_score < 70:
        return {
            "confidence": 0.0,
            "execution_route": "skip",
            "component_scores": component_scores,
            "alternative_path": None,
            "reasoning": "STRICT ICT REJECT: higher-timeframe structure is not aligned.",
            "cis_timing_score": cis_timing_score,
            "cis_setup_quality": cis_setup_quality,
            "backtest_required": False,
            "market_rhythm": market_rhythm,
            "missing_core": [],
        }

    base_confidence = (
        (topdown_score * 0.24)
        + (trend_alignment_score * 0.24)
        + (setup_score * 0.22)
        + (price_action_score * 0.12)
        + (confirmation_score * 0.08)
        + (market_rhythm_score * 0.10)
    )

    if cis_decision:
        cis_verdict = str(cis_decision.get("final_verdict", "")).upper()
        cis_confidence = float(cis_decision.get("confidence_score", 0.0) or 0.0)
        component_scores["cis_confidence"] = round(cis_confidence * 100.0, 1)
        if cis_verdict == "TRADE":
            base_confidence += max(0.0, (cis_confidence - 0.5) * 12.0)
        elif cis_verdict in ("WAIT", "AVOID"):
            base_confidence -= 10.0

    confidence = max(0.0, min(100.0, base_confidence))
    force_backtest = cis_history < 100
    execution_route, backtest_required, reasoning = _determine_execution_route(confidence, force_backtest)

    return {
        "confidence": round(confidence, 1),
        "execution_route": execution_route,
        "component_scores": component_scores,
        "alternative_path": None,
        "reasoning": reasoning,
        "cis_timing_score": cis_timing_score,
        "cis_setup_quality": cis_setup_quality,
        "backtest_required": backtest_required,
        "market_rhythm": market_rhythm,
        "missing_core": [],
    }


def _score_topdown(analysis: Dict, trend: str) -> float:
    topdown = (analysis or {}).get("topdown") or {}
    topdown_trend = topdown.get("trend") or (analysis or {}).get("overall_trend")
    context_alignment = topdown.get("context_alignment")

    if topdown_trend == trend:
        if context_alignment == "aligned":
            return 95.0
        if context_alignment == "mixed":
            return 80.0
        return 90.0
    if topdown_trend in (None, "range", "unknown", "neutral"):
        return 50.0
    return 20.0


def _score_trend_alignment(analysis: Dict, trend: str) -> float:
    states = [(analysis or {}).get("HTF") or {}, (analysis or {}).get("MTF") or {}, (analysis or {}).get("LTF") or {}]
    aligned = 0
    checked = 0
    for state in states:
        state_trend = state.get("trend")
        if state_trend:
            checked += 1
            if state_trend == trend:
                aligned += 1
    if checked == 0:
        return 50.0
    ratio = aligned / checked
    if ratio == 1.0:
        return 95.0
    if ratio >= 0.67:
        return 80.0
    if ratio >= 0.34:
        return 55.0
    return 25.0


def _score_price_action_confirmation(confirmation_flags: Dict) -> float:
    price_action = confirmation_flags.get("price_action") or {}
    if not isinstance(price_action, dict):
        return 35.0
    if not price_action.get("confirmed"):
        return 35.0
    patterns = list(price_action.get("patterns") or [])
    if len(patterns) >= 2:
        return 88.0
    if len(patterns) == 1:
        return 72.0
    return 60.0


def _score_setup_structure(confirmation_flags: Dict, signal: Dict) -> float:
    score = 0.0
    if _confirmation_passed(confirmation_flags.get("liquidity_setup")):
        score += 25.0
    if _confirmation_passed(confirmation_flags.get("bos")):
        score += 25.0
    if _confirmation_passed(confirmation_flags.get("fvg")) or signal.get("valid_fvg"):
        score += 25.0
    if _confirmation_passed(confirmation_flags.get("order_block_confirmed")) or signal.get("valid_order_block"):
        score += 25.0
    return min(100.0, score)


def _score_confirmation_count(confirmation_flags: Dict) -> float:
    weights = {
        "liquidity_setup": 20,
        "bos": 20,
        "displacement": 15,
        "fvg": 20,
        "order_block_confirmed": 15,
        "price_action": 5,
        "smt": 3,
        "rule_quality": 1,
        "ml": 1,
    }

    earned = 0.0
    total = 0.0
    for name, weight in weights.items():
        total += weight
        if _confirmation_passed(confirmation_flags.get(name)) or (
            name == "displacement" and _displacement_score(confirmation_flags.get(name)) >= 0.70
        ):
            earned += weight
    return (earned / total) * 100.0 if total else 0.0


def _score_market_rhythm(analysis: Dict) -> float:
    market_rhythm = (analysis or {}).get("market_rhythm") or {}
    if not isinstance(market_rhythm, dict):
        return 50.0
    score = float(market_rhythm.get("entry_score", 60.0) or 60.0)
    if market_rhythm.get("entry_bias") == "avoid":
        return min(score, 20.0)
    if market_rhythm.get("entry_bias") == "cautious":
        return min(score, 55.0)
    return min(100.0, max(0.0, score))


def _determine_execution_route(confidence: float, force_backtest: bool) -> Tuple[str, bool, str]:
    if confidence >= 85:
        if force_backtest:
            return "standard_validated", True, "High-confidence setup, but 100+ real CIS trades are required before direct execution."
        return "elite", False, f"Elite confidence ({confidence:.1f}) with full structural alignment."

    if confidence >= 70:
        if force_backtest:
            return "standard_validated", True, "Strong setup, but direct execution is blocked until 100+ real CIS trades exist."
        return "standard", False, f"Standard confidence ({confidence:.1f}) with strict ICT alignment."

    if confidence >= 60:
        return "conservative", True, f"Conservative confidence ({confidence:.1f}); backtest validation required."

    return "skip", False, f"Confidence too low ({confidence:.1f}); skip the setup."


def calculate_smart_risk_params(
    account_balance: float,
    confidence: float,
    base_risk_percent: float = 1.0,
    execution_route: str = "standard",
) -> Dict:
    route_multiplier = {
        "elite": 1.2,
        "standard": 1.0,
        "standard_validated": 0.8,
        "conservative": 0.6,
        "skip": 0.0,
    }.get(execution_route, 1.0)

    conf_multiplier = 0.8 + ((confidence - 50) / 50.0) * 0.3
    conf_multiplier = max(0.5, min(1.2, conf_multiplier))
    final_risk_percent = min(2.0, base_risk_percent * route_multiplier * conf_multiplier)
    risk_amount = account_balance * (final_risk_percent / 100.0)

    return {
        "risk_percent": round(final_risk_percent, 2),
        "risk_amount": round(risk_amount, 2),
        "route_multiplier": route_multiplier,
        "conf_multiplier": round(conf_multiplier, 2),
    }


def should_execute_immediately(execution_route: str) -> bool:
    return execution_route in ("elite", "standard")


def should_skip_signal(execution_route: str) -> bool:
    return execution_route == "skip"


def format_confidence_report(confidence_data: Dict) -> str:
    scores = confidence_data.get("component_scores", {})
    return (
        f"Confidence {confidence_data.get('confidence', 0)}/100 | "
        f"Route {str(confidence_data.get('execution_route', 'skip')).upper()} | "
        f"Reason {confidence_data.get('reasoning', 'n/a')} | "
        f"Topdown {scores.get('topdown', 0):.1f} | "
        f"Trend {scores.get('trend_alignment', 0):.1f} | "
        f"Setup {scores.get('setup_structure', 0):.1f}"
    )
