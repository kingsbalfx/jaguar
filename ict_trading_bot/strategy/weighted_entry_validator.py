"""
Weighted Entry Validator
========================
Integrates comprehensive market intelligence for smarter trade decisions.
Replaces hard-gate filtering with intelligent weighted confidence scoring.

**Architecture:**
- Each signal component contributes a score (0-100) based on quality
- Weighted confidence combines all components
- Multiple execution paths based on confidence level
- Strong confirmations can bypass weak filters

**Execution Paths:**
1. **ELITE EXECUTION** (confidence > 85)
   - Direct execution, skip backtest
   - Can execute with minimal confirmations

2. **INTELLIGENT ALTERNATIVE** (confidence 75-85)
2. **STANDARD EXECUTION** (confidence 70-85)
   - Direct execution if HTF trend aligns
   - Fast path to reduce slippage

3. **CONSERVATIVE EXECUTION** (confidence 60-70)
   - Standard execution with backtest

4. **PROTECTED EXECUTION** (confidence 50-60)
   - High-conviction alternative: Price + BOS setup can execute
   - Must have strong technical confirmation

5. **SKIP** (confidence < 50)
   - Insufficient confidence, wait for better setup
"""

from typing import Dict, Tuple, List
from utils.symbol_profile import infer_asset_class
import os


def calculate_entry_confidence(
    signal: Dict,
    analysis: Dict,
    trend: str,
    price: float,
    confirmation_flags: Dict = None,
    cis_decision: Dict = None, # Pass the CIS decision here
) -> Dict:
    """
    Calculate comprehensive confidence score for entry signal WITH INTELLIGENT ALTERNATIVES.

    **Smart Execution Paths:**
    1. STANDARD: Strong topdown (30%) + trend (25%) → normal weights apply
    2. STRUCTURE STRONG: Weak price action BUT liquidity+BOS+FVG+OB all met → boost setup score
    3. INTELLIGENT ALTERNATIVE: Weak topdown/trend BUT exceptional structure → backtest or direct execute

    Args:
        signal: The price action signal
        analysis: Market analysis (topdown, HTF, MTF, LTF)
        trend: 'bullish' or 'bearish'
        price: Current market price
        confirmation_flags: Individual filter results {liquidity, bos, price_action, smt, rule_quality, ml}

    Returns:
        {
            "confidence": 0-100 (overall score),
            "execution_route": "elite" | "standard" | "conservative" | "protected" | "intelligent_alternative" | "skip",
            "component_scores": {...},
            "alternative_path": None | {"type": "strong_structure", "score": 85, ...},
            "reasoning": "explanation",
            "backtest_required": bool,
        }
    """

    if confirmation_flags is None:
        confirmation_flags = {}

    component_scores = {}
    alternative_path = None

    # Extract CIS scores if available
    cis_timing_score = cis_decision.get("component_scores", {}).get("timing", 0.5) if cis_decision else 0.5
    cis_setup_quality = cis_decision.get("component_scores", {}).get("setup_quality") if cis_decision else None

    # ===================================
    # COMPONENT 1: TOPDOWN ANALYSIS (Base - 30%)
    # ===================================
    topdown_score = _score_topdown(analysis, trend)
    component_scores["topdown"] = topdown_score

    # ===================================
    # COMPONENT 2: HTF/MTF TREND ALIGNMENT (Multiplier - 25%)
    # ===================================
    trend_alignment_score = _score_trend_alignment(analysis, trend)
    component_scores["trend_alignment"] = trend_alignment_score

    # ===================================
    # COMPONENT 3: PRICE ACTION CONFIRMATION (20%)
    # ===================================
    price_action_score = _score_price_action_confirmation(confirmation_flags, signal)
    component_scores["price_action"] = price_action_score

    # ===================================
    # COMPONENT 4: SETUP STRUCTURE (15%)
    # ===================================
    base_setup_score = _score_setup_structure(confirmation_flags)

    # Hybrid Integration: Align confirmation score with structural intelligence.
    # Combine analytical structure flags with intelligence-based quality assessment.
    if cis_setup_quality is None:
        setup_score = base_setup_score
        reported_cis_setup_quality = round(base_setup_score / 100.0, 3)
    else:
        setup_score = (base_setup_score * 0.6) + (cis_setup_quality * 100 * 0.4)
        reported_cis_setup_quality = cis_setup_quality
    component_scores["setup_structure"] = setup_score

    # ===================================
    # COMPONENT 5: CONFIRMATIONS (10%)
    # ===================================
    confirmations_score = _score_confirmation_count(confirmation_flags)
    component_scores["confirmations"] = confirmations_score

    # ===================================
    # CHECK FOR INTELLIGENT ALTERNATIVE PATHS
    # ===================================

    # MANDATORY GATE: Major Trend and Topdown must be established
    # Requirement: "market should always follow topdown analysis and the major trend"
    if topdown_score < 70 or trend_alignment_score < 70:
        return {
            "confidence": 0.0,
            "execution_route": "skip",
            "component_scores": component_scores,
            "alternative_path": None,
            "reasoning": f"PRECISION REJECT: Establishing Topdown ({topdown_score:.0f}) and Major Trend ({trend_alignment_score:.0f}) is mandatory.",
            "cis_timing_score": cis_timing_score,
            "cis_setup_quality": reported_cis_setup_quality,
            "backtest_required": False
        }

    # Mandatory Confirmations Check: "before accepting any two or more further confirmation"
    confirm_count = sum(1 for k, v in confirmation_flags.items()
                        if k in ["smt", "rule_quality", "ml", "liquidity_setup", "bos"]
                        and (v is True or (isinstance(v, dict) and v.get("confirmed", False))))

    if confirm_count < 2:
        return {
            "confidence": 0.0,
            "execution_route": "skip",
            "component_scores": component_scores,
            "alternative_path": None,
            "reasoning": f"PRECISION REJECT: Setup requires at least 2 confirmations (Found {confirm_count}).",
            "cis_timing_score": cis_timing_score,
            "cis_setup_quality": reported_cis_setup_quality,
            "backtest_required": False
        }

    # --- REGIME IQ: Volume + SMA + HTF Sweeps ---
    regime_bonus = 1.0
    regime_notes = []

    if analysis.get("volume_alignment") and analysis.get("sma_alignment"):
        regime_bonus *= 1.10
        regime_notes.append("Vol/SMA Alignment (+10%)")

    if analysis.get("htf_sweep"):
        regime_bonus *= 1.15
        regime_notes.append("HTF Sweep Detected (+15%)")

    # --- SESSION IQ: Peak Liquidity Boost ---
    if cis_timing_score >= 0.85:
        regime_bonus *= 1.05
        regime_notes.append("Session Peak Timing (+5%)")
    elif cis_timing_score < 0.4:
        regime_bonus *= 0.80
        regime_notes.append("Low Liquidity Penalty (-20%)")

    # PATH 1: Strong Structure Despite Weak Price Action
    # If: liquidity + BOS + FVG + OB all confirmed, but price_action weak
    if (price_action_score < 60 and setup_score >= 80 and
        _has_all_structure_elements(confirmation_flags)):
        alternative_path = {
            "type": "strong_structure_override",
            "setup_score": setup_score,
            "logic": "Structure exceptional (liquidity+BOS+FVG+OB), price action not required",
            "boost_factor": 1.15,  # Boost overall confidence by 15%
        }

    # PATH 2: Intelligent Alternative - Weak Topdown/Trend But Strong Structure
    # If: topdown/trend weak BUT liquidity+BOS+FVG+OB+price_action all met
    if ((topdown_score < 60 or trend_alignment_score < 60) and
        _has_exceptional_structure(confirmation_flags, setup_score)):
        alternative_path = {
            "type": "intelligent_structure_path",
            "topdown_score": topdown_score,
            "trend_score": trend_alignment_score,
            "structure_score": setup_score,
            "logic": "Topdown weak but market structure exceptional (FVG+Liquidity+BOS)",
            "action": "backtest_or_direct" if setup_score >= 85 else "backtest_required",
            "confidence_if_direct": min(100, (setup_score * 1.2) + (topdown_score * 0.5)),
        }

    # ===================================
    # WEIGHTED CONFIDENCE CALCULATION
    # ===================================
    base_confidence = (
        (topdown_score * 0.30) +
        (trend_alignment_score * 0.25) +
        (price_action_score * 0.20) +
        (setup_score * 0.15) +
        (confirmations_score * 0.10)
    )

    weighted_confidence = base_confidence * regime_bonus

    # Apply alternative path boost if applicable
    if alternative_path:
        boost_factor = alternative_path.get("boost_factor", 1.0)
        weighted_confidence = weighted_confidence * boost_factor

    # Normalize to 0-100 scale
    confidence = min(100, max(0, weighted_confidence))

    reasoning_add = " | ".join(regime_notes) if regime_notes else ""

    # ===================================
    # DETERMINE EXECUTION ROUTE
    # ===================================
    execution_route, backtest_required, reasoning = _determine_execution_route(
        confidence=confidence,
        component_scores=component_scores,
        confirmation_flags=confirmation_flags,
        trend_alignment=trend_alignment_score,
        alternative_path=alternative_path,
        cis_timing_score=cis_timing_score, # Pass timing score for reasoning
        reasoning_add=reasoning_add # Add news impact reasoning

    )

    return {
        "confidence": round(confidence, 1),
        "execution_route": execution_route,
        "component_scores": component_scores,
        "alternative_path": alternative_path,
        "reasoning": reasoning,
        "cis_timing_score": cis_timing_score,
        "cis_setup_quality": reported_cis_setup_quality,
        "backtest_required": backtest_required,
    }


def _score_topdown(analysis: Dict, trend: str) -> float:
    """
    Score topdown analysis alignment with current trend.

    HIGH SCORE if:
    - Topdown trend matches signal trend
    - Clear market structure breaks identified
    - Multiple timeframes aligned

    Returns: 0-100 score
    """
    if not analysis or not isinstance(analysis, dict):
        return 30.0  # Neutral if analysis missing

    topdown = analysis.get("topdown") or {}

    # Check if topdown trend exists and aligns
    topdown_trend = topdown.get("trend") or analysis.get("overall_trend")
    context_alignment = topdown.get("context_alignment")

    if topdown_trend == trend:
        if context_alignment == "aligned":
            return 90.0
        if context_alignment == "mixed":
            return 75.0
        if context_alignment == "opposed":
            return 55.0
        return 85.0  # High score - topdown confirmed
    elif topdown_trend is None or topdown_trend == "unknown":
        return 50.0  # Neutral - topdown uncertain
    else:
        return 20.0  # Low score - topdown conflicts

    return 50.0


def _score_trend_alignment(analysis: Dict, trend: str) -> float:
    """
    Score multi-timeframe trend alignment (HTF + MTF + LTF).

    HIGH SCORE if:
    - HTF trend matches signal
    - MTF trend aligns with signal
    - LTF doesn't conflict with direction

    MEDIUM SCORE if:
    - 2 of 3 timeframes aligned

    Returns: 0-100 score
    """
    if not analysis or not isinstance(analysis, dict):
        return 40.0  # Neutral if analysis missing

    aligned_count = 0
    total_checked = 0

    # Check HTF (Higher TF)
    htf = analysis.get("HTF") or {}
    htf_trend = htf.get("trend")
    if htf_trend:
        total_checked += 1
        if htf_trend == trend:
            aligned_count += 1

    # Check MTF (Middle TF)
    mtf = analysis.get("MTF") or {}
    mtf_trend = mtf.get("trend")
    if mtf_trend:
        total_checked += 1
        if mtf_trend == trend:
            aligned_count += 1

    # Check LTF (Lower TF)
    ltf = analysis.get("LTF") or {}
    ltf_trend = ltf.get("trend")
    if ltf_trend:
        total_checked += 1
        if ltf_trend == trend:
            aligned_count += 1

    if total_checked == 0:
        return 50.0  # No data available

    alignment_ratio = aligned_count / total_checked

    if alignment_ratio == 1.0:  # All aligned
        return 95.0
    elif alignment_ratio >= 0.67:  # 2 of 3 aligned
        return 75.0
    elif alignment_ratio >= 0.33:  # 1 of 3+ aligned
        return 50.0
    else:
        return 25.0


def _score_price_action_confirmation(confirmation_flags: Dict, signal: Dict) -> float:
    """
    Score price action confirmation (candle patterns, rejection, momentum).

    HIGH SCORE if:
    - Engulfing pattern present
    - Rejection candle formed
    - Momentum buildup detected

    Returns: 0-100 score
    """
    price_action = confirmation_flags.get("price_action", {})

    if not isinstance(price_action, dict):
        return 40.0  # Neutral

    if not price_action.get("confirmed"):
        return 30.0  # No price action confirmation

    # Count pattern types
    patterns = price_action.get("patterns", [])
    pattern_count = len(patterns)

    if pattern_count >= 2:
        return 90.0  # Multiple patterns
    elif pattern_count == 1:
        return 70.0  # Single pattern
    else:
        return 40.0  # Minimal patterns

    return 50.0


def _score_setup_structure(confirmation_flags: Dict) -> float:
    """
    Score setup structure (BOS + Liquidity + Order Block).

    HIGH SCORE if:
    - BOS (Break of Structure) confirmed
    - Liquidity setup found
    - Order block provides support/resistance

    Returns: 0-100 score
    """
    bos_confirmed = confirmation_flags.get("bos", {}).get("confirmed", False)
    liquidity_confirmed = confirmation_flags.get("liquidity_setup", {}).get("confirmed", False)

    setup_score = 0.0

    if bos_confirmed:
        setup_score += 50.0  # BOS is critical

    if liquidity_confirmed:
        setup_score += 40.0  # Liquidity support

    # Order block score (from entry_model check_entry)
    if confirmation_flags.get("order_block_confirmed", False):
        setup_score += 30.0

    # Cap at 100
    return min(100.0, setup_score)


def _score_confirmation_count(confirmation_flags: Dict) -> float:
    """
    Score based on number of confirmations passing.

    Weights each confirmation:
    - liquidity_setup: 20
    - bos: 20
    - price_action: 20
    - smt: 15
    - rule_quality: 15
    - ml: 10

    Returns: 0-100 score
    """
    if not isinstance(confirmation_flags, dict):
        return 30.0

    score = 0.0
    max_score = 0.0

    weights = {
        "liquidity_setup": 20,
        "bos": 20,
        "price_action": 20,
        "smt": 15,
        "rule_quality": 15,
        "ml": 10,
    }

    for key, weight in weights.items():
        max_score += weight
        flag = confirmation_flags.get(key, {})

        # Handle both dict and bool formats
        if isinstance(flag, bool):
            if flag:
                score += weight
        elif isinstance(flag, dict):
            if flag.get("confirmed", flag.get("passed", False)):
                score += weight

    if max_score == 0:
        return 50.0

    # Normalize to 0-100
    return (score / max_score) * 100.0


def _determine_execution_route(
    confidence: float,
    component_scores: Dict,
    confirmation_flags: Dict,
    trend_alignment: float,
    alternative_path: Dict = None,
    cis_timing_score: float = 0.5, # Added for news impact
    reasoning_add: str = "" # Additional reasoning from CIS timing
) -> Tuple[str, bool, str]:
    """
    Determine execution route and backtest requirement based on confidence.

    **Intelligent Alternative Paths:**
    1. Strong structure override: Setup so strong (liquidity+BOS+FVG+OB) that weak
       price action doesn't matter → boost confidence, direct execution
    2. Intelligent structure path: Topdown/trend weak BUT structure exceptional
       (all elements met) → backtest if score < 85, else direct execute

    Returns:
        (execution_route, backtest_required, reasoning)
    """

    # Extract component scores for decision logic
    price_action_score = component_scores.get("price_action", 0)
    setup_score = component_scores.get("setup_structure", 0)
    topdown_score = component_scores.get("topdown", 0)

    # Base reasoning
    base_reasoning = f"IQ: {confidence:.1f}. {reasoning_add}"

    # ===================================
    # ALTERNATIVE PATH 1: STRONG STRUCTURE OVERRIDE
    # ===================================
    if alternative_path and alternative_path.get("type") == "strong_structure_override":
        # Structure is so exceptional that price action weakness doesn't matter
        return (
            "intelligent_alternative",
            False,
            f"IQ Path: Structure exceptional (liquidity+BOS+FVG+OB={setup_score:.0f}), " + base_reasoning +
            f"price_action weak={price_action_score:.0f}. Direct execution. Confidence: {confidence:.1f}"
        )

    # ===================================
    # ALTERNATIVE PATH 2: INTELLIGENT STRUCTURE PATH
    # ===================================
    if alternative_path and alternative_path.get("type") == "intelligent_structure_path":
        # Topdown/trend weak, but market structure is exceptional
        action = alternative_path.get("action", "backtest_required")
        intelligent_confidence = alternative_path.get("confidence_if_direct", confidence)

        if action == "backtest_or_direct" and intelligent_confidence >= 75:
            return (
                "intelligent_alternative",
                False,
                f"IQ Path: Topdown/trend weak ({topdown_score:.0f}), but structure exceptional. " + base_reasoning +
                f"Structure score={setup_score:.0f}. Smart confidence={intelligent_confidence:.1f}. "
                f"Direct execution based on market structure strength."
            )
        else:
            return (
                "intelligent_backtest_required",
                True,
                f"IQ Path: Topdown/trend weak ({topdown_score:.0f}), structure good ({setup_score:.0f}). " + base_reasoning +
                f"Backtest required to validate weak topdown. Smart confidence={intelligent_confidence:.1f}."
            )

    # ===================================
    # STANDARD PATHS (when no alternative detected)
    # ===================================

    # ELITE EXECUTION (confidence > 85)
    if confidence > 85:
        return (
            "elite",
            False,
            f"Elite confidence ({confidence:.1f}): Direct execution, strong topdown + trend + confirmations. " + base_reasoning
        )

    # STANDARD EXECUTION (confidence 70-85)
    if confidence >= 70:
        if trend_alignment >= 75:
            return (
                "standard",
                False,
                f"Standard confidence ({confidence:.1f}): Direct execution with HTF alignment. " + base_reasoning
            )
        else:
            return (
                "standard",
                True,
                f"Standard confidence ({confidence:.1f}): Execute with backtest validation. " + base_reasoning
            )

    # CONSERVATIVE EXECUTION (confidence 60-70)
    if confidence >= 60:
        return (
            "conservative",
            True,
            f"Conservative confidence ({confidence:.1f}): Backtest required before execution. " + base_reasoning
        )

    # PROTECTED EXECUTION (confidence 50-60)
    if confidence >= 50:
        # Check for strong technical setup (price + BOS) alternative path
        has_price_action = price_action_score >= 70
        has_bos = confirmation_flags.get("bos", {}).get("confirmed", False)
        # Smartness: If structure is very strong, it justifies a protected entry even with weak PA
        has_high_structure = setup_score >= 80
        has_strong_setup = (has_price_action and has_bos) or has_high_structure

        if has_strong_setup and topdown_score >= 50:
            reason = "High-conviction setup (price+BOS)" if has_price_action else "Strong structure override"
            return (
                "protected",
                True,
                f"Protected confidence ({confidence:.1f}): {reason}. Backtest required. " + base_reasoning
            )
        else:
            return (
                "skip",
                False,
                f"Insufficient alternative paths ({confidence:.1f}): Wait for stronger setup. " + base_reasoning
            )

    # SKIP (confidence < 50)
    return (
        "skip",
        False,
        f"Low confidence ({confidence:.1f}): Insufficient signal strength, skip this opportunity. " + base_reasoning
    )


def _has_all_structure_elements(confirmation_flags: Dict) -> bool:
    """
    Check if ALL structure elements are confirmed:
    - Liquidity setup
    - BOS (Break of Structure)
    - FVG (Fair Value Gap)
    - Order Block

    Returns:
        True if ALL elements confirmed
    """
    has_liquidity = confirmation_flags.get("liquidity_setup", {}).get("confirmed", False)
    has_bos = confirmation_flags.get("bos", {}).get("confirmed", False)
    has_fvg = confirmation_flags.get("fvg", {}).get("confirmed", False)
    has_ob = confirmation_flags.get("order_block_confirmed", False)

    # If FVG not explicitly flagged, check if it's in the structure
    if not has_fvg:
        # Look for FVG in LTF analysis or signal
        has_fvg = confirmation_flags.get("fvg", False)

    return has_liquidity and has_bos and has_fvg and has_ob


def _has_exceptional_structure(confirmation_flags: Dict, setup_score: float = 0) -> bool:
    """
    Check if structure is EXCEPTIONAL (3+ of 5 elements OR high setup score):
    - Liquidity setup confirmed
    - BOS confirmed
    - FVG confirmed
    - Order Block confirmed
    - Price action confirmed

    Returns:
        True if 3+ confirmed
    """
    # IQ Check: High score alone can signify exceptional structure
    if setup_score >= 85:
        return True

    confirmed_count = 0

    if confirmation_flags.get("liquidity_setup", {}).get("confirmed", False):
        confirmed_count += 1
    if confirmation_flags.get("bos", {}).get("confirmed", False):
        confirmed_count += 1
    if confirmation_flags.get("fvg", {}).get("confirmed", False) or confirmation_flags.get("fvg", False):
        confirmed_count += 1
    if confirmation_flags.get("order_block_confirmed", False):
        confirmed_count += 1
    if confirmation_flags.get("price_action", {}).get("confirmed", False):
        confirmed_count += 1

    return confirmed_count >= 3


def calculate_smart_risk_params(
    account_balance: float,
    confidence: float,
    base_risk_percent: float = 1.0,
    execution_route: str = "standard"
) -> Dict:
    """
    IQ-based risk management: Adjusts lot sizing and risk based on account balance
    and signal confidence level.
    """
    # Scale risk multiplier based on the chosen execution route
    route_multiplier = {
        "elite": 1.5,
        "standard": 1.0,
        "intelligent_alternative": 1.2,
        "conservative": 0.7,
        "protected": 0.5,
        "skip": 0.0
    }.get(execution_route, 1.0)

    # Conviction scaling: Higher confidence = slightly more risk (0.8x to 1.2x)
    conf_multiplier = 0.8 + ((confidence - 50) / 50.0) * 0.4
    conf_multiplier = max(0.5, min(1.5, conf_multiplier))

    final_risk_percent = base_risk_percent * route_multiplier * conf_multiplier
    final_risk_percent = min(3.0, final_risk_percent) # Safety cap at 3%

    risk_amount = account_balance * (final_risk_percent / 100.0)

    return {
        "risk_percent": round(final_risk_percent, 2),
        "risk_amount": round(risk_amount, 2),
        "route_multiplier": route_multiplier,
        "conf_multiplier": round(conf_multiplier, 2)
    }


def should_execute_immediately(execution_route: str) -> bool:
    """
    Determine if trade should execute immediately (no backtest).

    Args:
        execution_route: One of: elite, standard, conservative, protected, skip

    Returns:
        True if immediate execution allowed (skip backtest requirement)
    """
    return execution_route in ("elite", "standard")


def should_skip_signal(execution_route: str) -> bool:
    """
    Determine if signal should be skipped entirely.

    Args:
        execution_route: One of: elite, standard, conservative, protected, skip

    Returns:
        True if signal should be skipped
    """
    return execution_route == "skip"


def format_confidence_report(confidence_data: Dict) -> str:
    """
    Format confidence score data into readable report with alternative path details.

    Args:
        confidence_data: Output from calculate_entry_confidence()

    Returns:
        Formatted string for logging
    """
    alternative_path = confidence_data.get("alternative_path")

    report = f"""
    ┌─ WEIGHTED ENTRY CONFIDENCE
    ├─ Overall Score: {confidence_data.get('confidence', 0)}/100
    ├─ Execution Route: {confidence_data.get('execution_route', 'unknown').upper()}
    ├─ Reasoning: {confidence_data.get('reasoning', 'N/A')}
    └─ Components:
       ├─ Topdown: {confidence_data.get('component_scores', {}).get('topdown', 0):.1f}
       ├─ Trend Alignment: {confidence_data.get('component_scores', {}).get('trend_alignment', 0):.1f}
       ├─ Price Action: {confidence_data.get('component_scores', {}).get('price_action', 0):.1f}
       ├─ Setup Structure: {confidence_data.get('component_scores', {}).get('setup_structure', 0):.1f}
       └─ Confirmations: {confidence_data.get('component_scores', {}).get('confirmations', 0):.1f}"""

    # Add alternative path details if present
    if alternative_path:
        report += f"""

    ┌─ INTELLIGENT ALTERNATIVE PATH DETECTED
    ├─ Type: {alternative_path.get('type', 'unknown')}
    ├─ Logic: {alternative_path.get('logic', 'N/A')}"""

        if alternative_path.get("type") == "strong_structure_override":
            report += f"""
    ├─ Setup Score: {alternative_path.get('setup_score', 0):.0f}/100
    ├─ Boost Applied: {alternative_path.get('boost_factor', 1.0):.1%}
    └─ Reason: Structure (Liquidity+BOS+FVG+OB) so strong that weak price action acceptable"""

        elif alternative_path.get("type") == "intelligent_structure_path":
            report += f"""
    ├─ Topdown Score: {alternative_path.get('topdown_score', 0):.0f}/100
    ├─ Trend Score: {alternative_path.get('trend_score', 0):.0f}/100
    ├─ Structure Score: {alternative_path.get('structure_score', 0):.0f}/100
    ├─ Recommended Action: {alternative_path.get('action', 'unknown')}
    └─ Smart Confidence: {alternative_path.get('confidence_if_direct', 0):.1f}/100"""

    return report.strip()
