"""
FALLBACK STRATEGY 5 — Setup Scoring Engine
=============================================
Scores a setup from 0-100 using weighted criteria.
Minimum score (default 80) required for trading.
"""

from typing import Dict, Any

from . import config
from .trend import BULLISH, BEARISH, STRONG, MODERATE, WEAK, EXHAUSTED


def calculate_score(
    model_result: dict,
    trend_direction: str,
    trend_strength: str,
    trend_evidence: dict,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    risk_reward: float,
    spread: float,
    atr_value: float,
    session_quality: str,
) -> Dict[str, Any]:
    """
    Calculate total setup score (0-100).
    
    Returns:
        score_dict with "total", "components", "thresholds"
    """
    components = {}
    total = 0

    # ============================================================
    # 1. HTF Trend Quality (max 15)
    # ============================================================
    htf_trend_score = 0
    if trend_direction in (BULLISH, BEARISH):
        htf_trend_score += 8
        if trend_strength in (STRONG, MODERATE):
            htf_trend_score += 4
        if trend_evidence.get("combined_score", 0) >= 4:
            htf_trend_score += 3
        elif trend_evidence.get("combined_score", 0) >= 3:
            htf_trend_score += 2
        elif trend_evidence.get("combined_score", 0) >= 2:
            htf_trend_score += 1
    components["htf_trend"] = min(htf_trend_score, config.SCORE_WEIGHTS["htf_trend"])

    # ============================================================
    # 2. Structure Alignment (max 15)
    # ============================================================
    structure = trend_evidence.get("structure", {})
    htf_detail = structure.get("htf_details", {})
    mtf_detail = structure.get("mtf_details", {})
    
    structure_score = 0
    if htf_detail.get("score", 0) >= 3:
        structure_score += 7
    elif htf_detail.get("score", 0) > 0:
        structure_score += 4
    if mtf_detail.get("score", 0) >= 3:
        structure_score += 5
    elif mtf_detail.get("score", 0) > 0:
        structure_score += 3
    if htf_detail.get("higher_high") and htf_detail.get("higher_low"):
        structure_score += 3
    elif htf_detail.get("lower_high") and htf_detail.get("lower_low"):
        structure_score += 3
    components["structure_alignment"] = min(structure_score, config.SCORE_WEIGHTS["structure_alignment"])

    # ============================================================
    # 3. Trend Strength (ADX) (max 10)
    # ============================================================
    adx_info = trend_evidence.get("adx", {})
    adx_score = 0
    if adx_info.get("strength") == STRONG:
        adx_score = 8
    elif adx_info.get("strength") == MODERATE:
        adx_score = 5
    elif adx_info.get("strength") == WEAK:
        adx_score = 2
    if adx_info.get("strength") == EXHAUSTED:
        adx_score = 0
    components["trend_strength"] = min(adx_score, config.SCORE_WEIGHTS["trend_strength"])

    # ============================================================
    # 4. Pullback/Setup Quality (model-specific) (max 10)
    # ============================================================
    model = model_result.get("model", "?")
    model_score = model_result.get("score", 0)
    if model_score >= 80:
        pullback_score = 10
    elif model_score >= 70:
        pullback_score = 8
    elif model_score >= 60:
        pullback_score = 5
    elif model_score >= 50:
        pullback_score = 3
    else:
        pullback_score = 0
    components["pullback_quality"] = min(pullback_score, config.SCORE_WEIGHTS["pullback_quality"])

    # ============================================================
    # 5. Entry Zone Quality (max 10)
    # ============================================================
    entry_zone_score = 0
    if model_result.get("retest_confirmed", False):
        entry_zone_score += 5
    if model_result.get("choch_bos_confirmed", False) or model_result.get("choch_confirmed", False):
        entry_zone_score += 3
    if model_result.get("continuation_confirmed", False):
        entry_zone_score += 2
    if model_result.get("momentum_exhaustion", False):
        entry_zone_score += 2
    components["entry_zone"] = min(entry_zone_score, config.SCORE_WEIGHTS["entry_zone"])

    # ============================================================
    # 6. Liquidity Quality (max 10)
    # ============================================================
    liquidity_score = 0
    if model_result.get("liquidity_swept", False):
        liquidity_score += 5
        if model_result.get("sweep_returned_inside", False):
            liquidity_score += 3
        depth = abs(model_result.get("sweep_depth_atr", 0))
        if 0.2 <= depth <= 0.5:
            liquidity_score += 2
    if model_result.get("sweep_detected", False):
        liquidity_score += 3
    components["liquidity_quality"] = min(liquidity_score, config.SCORE_WEIGHTS["liquidity_quality"])

    # ============================================================
    # 7. Displacement Quality (max 10)
    # ============================================================
    displacement_score = 0
    if model_result.get("displacement_confirmed", False):
        displacement_score += 6
        displacement_ratio = model_result.get("breakout_displacement", 0)
        if 0.5 <= displacement_ratio <= 1.5:
            displacement_score += 2
        if model_result.get("choch_bos_confirmed", False) or model_result.get("choch_confirmed", False):
            displacement_score += 2
    components["displacement"] = min(displacement_score, config.SCORE_WEIGHTS["displacement"])

    # ============================================================
    # 8. Confirmation Quality (max 10)
    # ============================================================
    confirmation_score = 0
    if model_result.get("continuation_confirmed", False):
        confirmation_score += 4
    if model_result.get("rejection_confirmed", False):
        confirmation_score += 3
    if model_result.get("breakout_detected", False) and not model_result.get("breakout_extended", False):
        confirmation_score += 3
    components["confirmation_quality"] = min(confirmation_score, config.SCORE_WEIGHTS["confirmation_quality"])

    # ============================================================
    # 9. Target Room (max 5)
    # ============================================================
    target_room_score = 0
    if risk_reward >= 2.0:
        target_room_score = 5
    elif risk_reward >= config.MIN_RR:
        target_room_score = 3
    elif risk_reward >= 1.0:
        target_room_score = 1
    components["target_room"] = min(target_room_score, config.SCORE_WEIGHTS["target_room"])

    # ============================================================
    # 10. Spread Quality (max 5)
    # ============================================================
    spread_score = 0
    if atr_value > 0 and spread > 0:
        spread_ratio = spread / atr_value
        if spread_ratio < 0.01:
            spread_score = 5
        elif spread_ratio < 0.03:
            spread_score = 4
        elif spread_ratio < 0.05:
            spread_score = 2
        elif spread_ratio < 0.08:
            spread_score = 1
    components["spread_quality"] = min(spread_score, config.SCORE_WEIGHTS["spread_quality"])

    # ============================================================
    # 11. Session Quality (max 5)
    # ============================================================
    session_score = 0
    if session_quality == "optimal":
        session_score = 5
    elif session_quality == "acceptable":
        session_score = 3
    elif session_quality == "suboptimal":
        session_score = 1
    components["session_quality"] = min(session_score, config.SCORE_WEIGHTS["session_quality"])

    # ============================================================
    # 12. Risk/Reward Quality (max 5)
    # ============================================================
    rr_score = 0
    if risk_reward >= 3.0:
        rr_score = 5
    elif risk_reward >= 2.0:
        rr_score = 4
    elif risk_reward >= config.MIN_RR:
        rr_score = 3
    elif risk_reward >= 1.0:
        rr_score = 1
    components["risk_reward"] = min(rr_score, config.SCORE_WEIGHTS["risk_reward"])

    # ============================================================
    # Total
    # ============================================================
    total = sum(components.values())

    return {
        "total": total,
        "components": components,
        "meets_minimum": total >= config.SCORE_MINIMUM,
        "minimum_required": config.SCORE_MINIMUM,
        "model": model,
    }
