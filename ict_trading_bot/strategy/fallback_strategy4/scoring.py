"""
FALLBACK STRATEGY 4 - Scoring System
======================================
Calculates the overall Fallback 4 score (0-100) from individual component scores.
"""

from typing import Dict, Tuple

from . import config
from .models import (
    DisplacementResult, EntryResult, RangeResult, ReclaimResult,
    StructureChangeResult, SweepResult,
)


def calculate_score(
    range_data: RangeResult,
    sweep: SweepResult,
    reclaim: ReclaimResult,
    displacement: DisplacementResult,
    structure_change: StructureChangeResult,
    entry: EntryResult,
    context_bias: str,
    risk_reward: float,
    is_m1: bool,
) -> Tuple[int, Dict[str, int]]:
    """
    Calculate the overall Fallback 4 score from component scores.
    
    Returns:
        (total_score, component_scores_dict)
    """
    components = {}

    # 1. Range quality score (0-15)
    range_score = _score_range_quality(range_data)
    components["range_quality"] = range_score

    # 2. Boundary liquidity quality (0-10)
    liquidity_score = _score_boundary_liquidity(range_data, sweep)
    components["boundary_liquidity"] = liquidity_score

    # 3. Sweep quality (0-15)
    sweep_score = _score_sweep_quality(sweep)
    components["sweep_quality"] = sweep_score

    # 4. Failed-breakout confidence (0-15)
    breakout_score = _score_failed_breakout(sweep)
    components["failed_breakout"] = breakout_score

    # 5. Range reclaim quality (0-15)
    reclaim_score = _score_reclaim_quality(reclaim)
    components["reclaim"] = reclaim_score

    # 6. Displacement (0-10)
    displacement_score = _score_displacement(displacement)
    components["displacement"] = displacement_score

    # 7. Structure change (0-10) — MANDATORY
    structure_score = _score_structure_change(structure_change)
    components["structure_change"] = structure_score

    # 8. Entry zone quality (0-5)
    entry_score = _score_entry_quality(entry)
    components["entry_zone"] = entry_score

    # 9. Risk-to-reward (0-5)
    rr_score = _score_risk_reward(risk_reward)
    components["risk_reward"] = rr_score

    # 10. Session quality (0-5)
    session_score = _score_session_quality(context_bias, is_m1)
    components["session"] = session_score

    # 11. Optional MACD/SMA confirmation (0-5 bonus)
    indicator_score = 0
    if config.MACD_ENABLED or config.SMA_ENABLED:
        indicator_score = 3
    components["indicator"] = indicator_score

    # Apply weights
    weighted_total = (
        range_score * config.WEIGHT_RANGE_QUALITY +
        liquidity_score * config.WEIGHT_BOUNDARY_LIQUIDITY +
        sweep_score * config.WEIGHT_SWEEP_QUALITY +
        breakout_score * config.WEIGHT_FAILED_BREAKOUT +
        reclaim_score * config.WEIGHT_RECLAIM +
        displacement_score * config.WEIGHT_DISPLACEMENT +
        structure_score * config.WEIGHT_STRUCTURE_CHANGE +
        entry_score * config.WEIGHT_ENTRY_ZONE +
        rr_score * config.WEIGHT_RISK_REWARD +
        indicator_score * 5
    )

    total_weight = (
        config.WEIGHT_RANGE_QUALITY + config.WEIGHT_BOUNDARY_LIQUIDITY +
        config.WEIGHT_SWEEP_QUALITY + config.WEIGHT_FAILED_BREAKOUT +
        config.WEIGHT_RECLAIM + config.WEIGHT_DISPLACEMENT +
        config.WEIGHT_STRUCTURE_CHANGE + config.WEIGHT_ENTRY_ZONE +
        config.WEIGHT_RISK_REWARD
    )

    total_score = weighted_total // total_weight if total_weight > 0 else 0
    total_score = max(0, min(100, total_score))

    components["total"] = total_score
    return total_score, components


def _score_range_quality(range_data: RangeResult) -> int:
    """Score range quality (0-15 based on internal quality score)."""
    if not range_data.detected or not range_data.is_valid:
        return 0
    return min(15, range_data.quality_score * 15 // 100)


def _score_boundary_liquidity(range_data: RangeResult, sweep: SweepResult) -> int:
    """Score boundary liquidity quality (0-10)."""
    if not range_data.detected:
        return 0

    score = 0
    if range_data.upper_zone:
        score += min(5, range_data.upper_zone.interaction_count * 2)
    if range_data.lower_zone:
        score += min(5, range_data.lower_zone.interaction_count * 2)
    if range_data.upper_zone and range_data.lower_zone:
        if range_data.rotations >= 4:
            score += 2

    return min(10, score)


def _score_sweep_quality(sweep: SweepResult) -> int:
    """Score sweep quality (0-15)."""
    if not sweep.detected:
        return 0

    score = 0

    if sweep.classification == "sweep":
        score += 8
    elif sweep.classification == "probable_sweep":
        score += 5
    elif sweep.classification == "probable_breakout":
        score += 2
    else:
        return 0

    if 0.5 <= sweep.penetration_atr <= 2.0:
        score += 4
    elif 0.3 <= sweep.penetration_atr <= 3.0:
        score += 2

    if sweep.momentum_decelerated:
        score += 3

    return min(15, score)


def _score_failed_breakout(sweep: SweepResult) -> int:
    """Score failed breakout confidence (0-15)."""
    if not sweep.detected:
        return 0

    sweep_conf = sweep.sweep_score
    if sweep_conf >= 0.8:
        return 15
    elif sweep_conf >= 0.6:
        return 10
    elif sweep_conf >= 0.4:
        return 5
    else:
        return 2


def _score_reclaim_quality(reclaim: ReclaimResult) -> int:
    """Score range reclaim quality (0-15)."""
    if not reclaim.reclaimed:
        return 0

    score = 0
    score += min(8, reclaim.reclaim_strength * 8 // 100)

    if reclaim.mode_used == "strict":
        score += 4
    elif reclaim.mode_used == "balanced":
        score += 3
    else:
        score += 1

    if reclaim.reclaim_candle_body_ratio >= 0.6:
        score += 3
    elif reclaim.reclaim_candle_body_ratio >= 0.4:
        score += 2

    if reclaim.follow_through_confirmed:
        score += 2

    return min(15, score)


def _score_displacement(displacement: DisplacementResult) -> int:
    """Score displacement quality (0-10)."""
    if not displacement.detected:
        return 0
    return min(10, displacement.score * 10 // 100)


def _score_structure_change(structure_change: StructureChangeResult) -> int:
    """Score structure change quality (0-10)."""
    if not structure_change.confirmed:
        return 0

    score = 5
    if structure_change.method == "choch":
        score += 2
        if structure_change.close_distance_atr >= 0.5:
            score += 1
    elif structure_change.method == "bos":
        score += 1

    if structure_change.body_ratio >= 0.6:
        score += 2
    elif structure_change.body_ratio >= 0.4:
        score += 1

    return min(10, score)


def _score_entry_quality(entry: EntryResult) -> int:
    """Score entry zone quality (0-5)."""
    if not entry.confirmed:
        return 0

    score = 2
    if entry.model == "A":
        score += 2
    elif entry.model == "B":
        score += 1
    elif entry.model == "D":
        score += 3

    if entry.fib_level_used and 0.5 <= entry.fib_level_used <= 0.786:
        score += 1

    return min(5, score)


def _score_risk_reward(risk_reward: float) -> int:
    """Score risk-to-reward (0-5)."""
    if risk_reward >= 3.0:
        return 5
    elif risk_reward >= 2.0:
        return 4
    elif risk_reward >= 1.5:
        return 3
    elif risk_reward >= 1.0:
        return 2
    elif risk_reward >= 0.5:
        return 1
    return 0


def _score_session_quality(context_bias: str, is_m1: bool) -> int:
    """Score session/context quality (0-5)."""
    if context_bias in ("bullish", "bearish"):
        return 5
    elif context_bias == "neutral":
        return 3
    elif context_bias == "conflicting":
        return 1 if not config.COUNTERTREND_ENABLED else 2
    return 0
