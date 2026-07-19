"""
FALLBACK STRATEGY 4 - Logging
===============================
Structured logging for Fallback 4 analysis steps.
Generates detailed log lines compatible with the existing bot logging system.
"""

import logging
from typing import Any, Dict, Optional

from .models import Fallback4SetupResult

LOGGER = logging.getLogger("ict_state_machine.fallback4")


def log_fallback4_result(result: Fallback4SetupResult) -> None:
    """
    Log the complete Fallback 4 analysis result in a structured format.
    Follows the logging schema from the spec.
    """
    if not result:
        return

    symbol = result.symbol
    decision = "BUY" if result.direction == "buy" and result.executable else (
        "SELL" if result.direction == "sell" and result.executable else "SKIP"
    )

    # Build the detailed log line
    log_data = _build_log_dict(result)

    if result.executable and result.entry_price:
        LOGGER.info(
            "[%s] FALLBACK4 | DECISION=%s | SCORE=%s | RANGE_H=%.5f RANGE_L=%.5f | "
            "SWEEP=%s PEN=%.2fATR | RECLAIM=%s | DISP=%s | CHOCH=%s | "
            "ENTRY=%.5f SL=%.5f TP=%.5f RR=%.2f | SESSION=%s | REASON=%s",
            symbol,
            decision,
            result.score,
            result.range_data.range_high,
            result.range_data.range_low,
            result.sweep.side or "none",
            result.sweep.penetration_atr,
            result.reclaim.mode_used if result.reclaim.reclaimed else "none",
            result.displacement.score if result.displacement.detected else 0,
            result.structure_change.method if result.structure_change.confirmed else "none",
            result.entry_price,
            result.stop_loss or 0,
            result.take_profit_primary or 0,
            result.risk_reward,
            result.context_bias or "unknown",
            result.reason,
        )

        # Log targets
        if result.targets:
            target_info = " | ".join(
                f"{t.label}={t.level:.5f}@{t.allocation:.0f}%"
                for t in result.targets
            )
            LOGGER.info("[%s] FALLBACK4 TARGETS | %s", symbol, target_info)

        # Log score components
        if result.score_components:
            comp_info = " ".join(
                f"{k}={v}" for k, v in result.score_components.items()
                if k != "total"
            )
            LOGGER.info("[%s] FALLBACK4 SCORE | total=%s | %s", symbol, result.score, comp_info)
    else:
        LOGGER.debug(
            "[%s] FALLBACK4 SKIP | SCORE=%s | failed=%s | reason=%s",
            symbol,
            result.score,
            result.failed_stage or "none",
            result.rejection_reason or result.reason or "no_valid_setup",
        )

    # Always log range and context info
    range_data = result.range_data
    if range_data.detected:
        LOGGER.debug(
            "[%s] FALLBACK4 RANGE | high=%.5f low=%.5f width=%.5f width_atr=%.1f "
            "duration=%s quality=%s rotations=%s upper_int=%s lower_int=%s",
            symbol,
            range_data.range_high,
            range_data.range_low,
            range_data.range_width,
            range_data.range_width_atr,
            range_data.duration,
            range_data.quality_score,
            range_data.rotations,
            range_data.upper_interactions,
            range_data.lower_interactions,
        )

    # Sweep info
    sweep = result.sweep
    if sweep.detected:
        LOGGER.debug(
            "[%s] FALLBACK4 SWEEP | side=%s extreme=%.5f pen_atr=%.2f "
            "candles_out=%s class=%s sweep_score=%.2f momentum_dec=%s",
            symbol,
            sweep.side,
            sweep.extreme_price,
            sweep.penetration_atr,
            sweep.candles_outside,
            sweep.classification,
            sweep.sweep_score,
            sweep.momentum_decelerated,
        )


def _build_log_dict(result: Fallback4SetupResult) -> Dict[str, Any]:
    """Build the complete structured log dict matching the spec."""
    rd = result.range_data
    sw = result.sweep
    rc = result.reclaim
    dp = result.displacement
    sc = result.structure_change
    en = result.entry

    return {
        "SYMBOL": result.symbol,
        "TIMESTAMP": __import__("time").strftime("%Y-%m-%d %H:%M:%S", __import__("time").gmtime()),
        "EXECUTION_TIMEFRAME": result.execution_timeframe,
        "CONTEXT_TIMEFRAME": result.context_timeframe,
        "STRATEGY_1_RESULT": result.strategy_1_result,
        "STRATEGY_2_RESULT": result.strategy_2_result,
        "FALLBACK_3_RESULT": result.fallback_3_result,
        "FALLBACK_4_ACTIVATED": "TRUE" if result.activated else "FALSE",
        "RANGE_STATUS": "CONFIRMED" if rd.is_valid else "REJECTED",
        "RANGE_START": rd.start_index,
        "RANGE_HIGH": rd.range_high,
        "RANGE_LOW": rd.range_low,
        "RANGE_WIDTH": rd.range_width,
        "RANGE_WIDTH_ATR": rd.range_width_atr,
        "RANGE_DURATION": rd.duration,
        "RANGE_INTERACTIONS_HIGH": rd.upper_interactions,
        "RANGE_INTERACTIONS_LOW": rd.lower_interactions,
        "RANGE_ROTATIONS": rd.rotations,
        "RANGE_QUALITY_SCORE": rd.quality_score,
        "SWEEP_SIDE": sw.side or "none",
        "SWEEP_EXTREME": sw.extreme_price,
        "SWEEP_PENETRATION": sw.penetration,
        "SWEEP_PENETRATION_ATR": sw.penetration_atr,
        "CANDLES_OUTSIDE_RANGE": sw.candles_outside,
        "SWEEP_SCORE": sw.sweep_score,
        "BREAKOUT_SCORE": sw.breakout_score,
        "RECLAIM_STATUS": "CONFIRMED" if rc.reclaimed else "NONE",
        "RECLAIM_CANDLE": rc.reclaim_candle_index,
        "RECLAIM_STRENGTH": rc.reclaim_strength,
        "DISPLACEMENT_SCORE": dp.score if dp.detected else 0,
        "CHOCH_STATUS": f"CONFIRMED_{sc.direction.upper()}" if sc.confirmed else "NONE",
        "CHOCH_LEVEL": sc.swing_level if sc.confirmed else 0,
        "BOS_STATUS": "CONFIRMED" if sc.confirmed and sc.method == "bos" else "NONE",
        "ENTRY_MODEL": en.model,
        "ENTRY_ZONE": f"{en.zone_low:.5f}-{en.zone_high:.5f}" if en.confirmed else "none",
        "ENTRY_PRICE": result.entry_price or 0,
        "STOP_LOSS": result.stop_loss or 0,
        "TP1": result.targets[0].level if len(result.targets) > 0 else 0,
        "TP2": result.targets[1].level if len(result.targets) > 1 else 0,
        "TP3": result.targets[2].level if len(result.targets) > 2 else 0,
        "FINAL_TARGET": result.targets[3].level if len(result.targets) > 3 else 0,
        "RISK_REWARD": result.risk_reward,
        "POSITION_SIZE": result.position_size,
        "SESSION": result.context_bias or "unknown",
        "SPREAD": 0,
        "FALLBACK_4_SCORE": result.score,
        "FINAL_DECISION": (
            "BUY" if result.direction == "buy" and result.executable else
            "SELL" if result.direction == "sell" and result.executable else
            "SKIP"
        ),
        "FAILED_STAGE": result.failed_stage or "none",
        "REJECTION_REASON": result.rejection_reason or "",
    }
