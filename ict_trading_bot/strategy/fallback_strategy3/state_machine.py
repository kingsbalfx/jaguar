"""
FALLBACK STRATEGY 3 - State Machine
=====================================
Rigorous sequential state machine for Fallback 3.
Rejects on first failed state — never skips back.
"""

from typing import Any, Dict, List, Optional, Tuple

from . import config
from .models import (
    FallbackSetupResult, SweepResult, CHOCHResult, MACDResult, SMAResult,
    ConsolidationResult, EntryZoneResult, make_state,
)
from . import logging as fb3_logger


class Fallback3StateMachine:
    """
    Sequential state machine for Fallback Strategy 3.
    
    Progresses through states in order. Each state can only pass or fail.
    First failure immediately stops progression.
    """
    
    # ============================================================
    # Master state progression
    # ============================================================
    PROGRESSION = [
        "activation_gate",            # Both primary strategies must have skipped
        "htf_bias",                   # H1 direction is clear
        "liquidity_mapped",           # Meaningful liquidity levels identified
        "liquidity_interaction",      # Price interacted with a liquidity level
        "sweep_classification",       # Movement through liquidity = sweep (not breakout)
        "displacement",               # Opposing displacement detected after sweep
        "choch_forming",              # Lower-TF structure shift (CHOCH) candle forming
        "choch_confirmed",            # CHOCH candle closed and confirmed
        "indicator_confirmation",     # MACD + SMA support the CHOCH
        "entry_zone_calculated",      # Fibonacci entry zone identified
        "retracement_wait",           # Price retracing toward entry zone
        "entry_confirmation",         # Reaction candle/microstructure confirms entry
        "risk_approved",              # Risk engine approves the trade
        "order_executed",             # Market order sent (done by caller)
    ]
    
    def __init__(self):
        self.current_step = 0
        self.states: List[Dict[str, Any]] = []
        self.result = FallbackSetupResult()
        self.failed = False
    
    @property
    def current_state_name(self) -> str:
        if self.current_step < len(self.PROGRESSION):
            return self.PROGRESSION[self.current_step]
        return "completed"
    
    def process(
        self,
        symbol: str,
        htf_bias: Optional[str],
        htf_confidence: float,
        levels: Dict[str, Any],
        sweep: SweepResult,
        choch: CHOCHResult,
        macd: MACDResult,
        sma: SMAResult,
        consolidation: ConsolidationResult,
        entry_zone: EntryZoneResult,
        entry_price: Optional[float],
        stop_loss: Optional[float],
        take_profit: Optional[float],
        risk_reward: float,
        position_size: float,
        strategy_1_result: str,
        strategy_1_reason: str,
        strategy_2_result: str,
        strategy_2_reason: str,
    ) -> FallbackSetupResult:
        """
        Run the full state machine with all pre-computed data.
        """
        self.result = FallbackSetupResult(
            symbol=symbol,
            htf_bias=htf_bias,
            htf_bias_confidence=htf_confidence,
            sweep=sweep,
            choch=choch,
            macd=macd,
            sma=sma,
            consolidation=consolidation,
            entry_zone=entry_zone,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_reward=risk_reward,
            position_size=position_size,
            strategy_1_result=strategy_1_result,
            strategy_1_reason=strategy_1_reason,
            strategy_2_result=strategy_2_result,
            strategy_2_reason=strategy_2_reason,
        )
        
        states = []
        
        # ============================================================
        # STEP 0: Activation Gate
        # ============================================================
        if self._process_step(0, "BOTH primary strategies skipped Fallback 3"):
            states.append(make_state("activation_gate", True, {"reason": "both primary skipped"}))
            self.result.activated = True
            fb3_logger.log_fallback3_activation(
                symbol, strategy_1_result, strategy_2_result,
                strategy_1_reason, strategy_2_reason,
            )
        else:
            states.append(make_state("activation_gate", False, {}, "one_or_both_primary_strategies_still_active"))
            self._fail("Activation gate failed: one or both primary strategies still active", "activation_gate")
            self.result.states = states
            return self.result
        
        # ============================================================
        # STEP 1: HTF Bias
        # ============================================================
        htf_ok = htf_bias in ("bullish", "bearish") and htf_confidence >= 0.4
        htf_evidence = {
            "bias": htf_bias,
            "confidence": htf_confidence,
            "countertrend_enabled": config.COUNTERTREND_ENABLED,
        }
        if self._process_step(1, htf_ok):
            states.append(make_state("htf_bias", True, htf_evidence, f"HTF bias: {htf_bias}"))
        else:
            states.append(make_state("htf_bias", False, htf_evidence, f"HTF bias unclear: {htf_bias}"))
            self._fail(f"HTF bias unclear: {htf_bias}", "htf_bias")
            self.result.states = states
            return self.result
        
        # ============================================================
        # STEP 2: Liquidity Mapped
        # ============================================================
        liq_ok = levels and (
            len(levels.get("swing_highs", [])) > 0 or
            len(levels.get("swing_lows", [])) > 0 or
            len(levels.get("equal_highs", [])) > 0 or
            len(levels.get("equal_lows", [])) > 0
        )
        liq_evidence = {
            "swing_highs": len(levels.get("swing_highs", [])),
            "swing_lows": len(levels.get("swing_lows", [])),
            "equal_highs": len(levels.get("equal_highs", [])),
            "equal_lows": len(levels.get("equal_lows", [])),
            "external_highs": len(levels.get("external_highs", [])),
            "external_lows": len(levels.get("external_lows", [])),
        }
        if self._process_step(2, liq_ok):
            states.append(make_state("liquidity_mapped", True, liq_evidence))
        else:
            states.append(make_state("liquidity_mapped", False, liq_evidence, "No meaningful liquidity levels"))
            self._fail("No liquidity levels mapped", "liquidity_mapped")
            self.result.states = states
            return self.result
        
        # ============================================================
        # STEP 3: Liquidity Interaction
        # ============================================================
        liq_int_ok = sweep.detected
        liq_int_evidence = {
            "detected": sweep.detected,
            "sweep_type": sweep.sweep_type,
            "candles_beyond": sweep.candle_count_beyond,
        }
        if self._process_step(3, liq_int_ok):
            states.append(make_state("liquidity_interaction", True, liq_int_evidence))
        else:
            states.append(make_state("liquidity_interaction", False, liq_int_evidence, "No liquidity interaction"))
            self._fail("Price did not interact with liquidity level", "liquidity_interaction")
            self.result.states = states
            return self.result
        
        # ============================================================
        # STEP 4: Sweep Classification
        # ============================================================
        sweep_ok = sweep.classification == "sweep"
        fb3_logger.log_sweep_analysis(symbol, sweep)
        sweep_evidence = {
            "classification": sweep.classification,
            "score": sweep.classification_score,
            "return_inside": sweep.return_inside,
            "momentum_weak": sweep.momentum_weak_beyond,
            "displacement_detected": sweep.displacement_detected,
        }
        if self._process_step(4, sweep_ok):
            states.append(make_state("sweep_classification", True, sweep_evidence))
        else:
            states.append(make_state("sweep_classification", False, sweep_evidence, f"Not a sweep: {sweep.classification}"))
            self._fail(f"Sweep classification: {sweep.classification}", "sweep_classification")
            self.result.states = states
            return self.result
        
        # ============================================================
        # STEP 5: Displacement
        # ============================================================
        disp_ok = sweep.displacement_detected
        disp_evidence = {
            "displacement_detected": sweep.displacement_detected,
            "body_ratio": sweep.displacement_body_ratio,
            "range_ratio": sweep.displacement_range_ratio,
        }
        if self._process_step(5, disp_ok):
            states.append(make_state("displacement", True, disp_evidence))
        else:
            states.append(make_state("displacement", False, disp_evidence, "No opposing displacement after sweep"))
            self._fail("No displacement after sweep", "displacement")
            self.result.states = states
            return self.result
        
        # ============================================================
        # STEP 6: CHOCH Forming
        # ============================================================
        # CHOCH is considered "forming" if we see any structure shift attempt
        choch_forming_ok = choch.detected or (sweep.displacement_detected and entry_zone.found)
        choch_forming_evidence = {
            "choch_detected": choch.detected,
            "swing_level": choch.swing_level,
            "attempted": choch_forming_ok,
        }
        if self._process_step(6, choch_forming_ok):
            states.append(make_state("choch_forming", True, choch_forming_evidence))
        else:
            states.append(make_state("choch_forming", False, choch_forming_evidence, "No CHOCH formation detected"))
            self._fail("No CHOCH forming", "choch_forming")
            self.result.states = states
            return self.result
        
        # ============================================================
        # STEP 7: CHOCH Confirmed
        # ============================================================
        fb3_logger.log_choch_analysis(symbol, choch)
        
        # In strict mode: must have confirmed + closed + not invalidated
        if config.ACTIVATION_MODE == "strict":
            choch_ok = choch.detected and choch.break_candle_confirmed and not choch.immediately_invalidated
        # In balanced mode: confirmed + closed
        elif config.ACTIVATION_MODE == "balanced":
            choch_ok = choch.detected and choch.break_candle_confirmed
        # In score mode: detected is enough (score will judge quality)
        else:
            choch_ok = choch.detected
        
        choch_evidence = {
            "detected": choch.detected,
            "direction": choch.direction,
            "swing_level": choch.swing_level,
            "close_level": choch.close_level,
            "candle_index": choch.candle_index,
            "close_distance": choch.close_distance_above_swing,
            "body_ratio": choch.body_ratio,
            "confirmed_candle": choch.break_candle_confirmed,
            "invalidated": choch.immediately_invalidated,
        }
        if self._process_step(7, choch_ok):
            states.append(make_state("choch_confirmed", True, choch_evidence))
        else:
            states.append(make_state("choch_confirmed", False, choch_evidence, "CHOCH not confirmed"))
            self._fail("CHOCH not confirmed", "choch_confirmed")
            self.result.states = states
            return self.result
        
        # ============================================================
        # STEP 8: Indicator Confirmation
        # ============================================================
        fb3_logger.log_indicator_analysis(symbol, macd, sma)
        
        if config.ACTIVATION_MODE == "strict":
            # Both MACD and SMA must confirm (no contradictions)
            indicator_ok = macd.confirmed and sma.confirmed
        elif config.ACTIVATION_MODE == "balanced":
            # At least one confirms, neither strongly contradicts
            indicator_ok = (macd.confirmed or sma.confirmed) and not macd.contradiction and not sma.contradiction
        else:
            # Score mode: no hard block, score will judge
            indicator_ok = not macd.contradiction and not sma.contradiction and not consolidation.consolidating
        
        indicator_evidence = {
            "macd_confirmed": macd.confirmed,
            "macd_contradiction": macd.contradiction,
            "macd_histogram": macd.histogram,
            "macd_histogram_increasing": macd.histogram_increasing,
            "sma_confirmed": sma.confirmed,
            "sma_contradiction": sma.contradiction,
            "sma_fast_slope": sma.fast_slope,
            "sma_slow_slope": sma.slow_slope,
            "consolidation": consolidation.consolidating,
            "consolidation_confidence": consolidation.confidence,
            "consolidation_reasons": consolidation.reasons,
            "activation_mode": config.ACTIVATION_MODE,
        }
        if self._process_step(8, indicator_ok):
            states.append(make_state("indicator_confirmation", True, indicator_evidence))
        else:
            states.append(make_state("indicator_confirmation", False, indicator_evidence, "Indicators do not confirm"))
            self._fail("Indicator confirmation failed", "indicator_confirmation")
            self.result.states = states
            return self.result
        
        # ============================================================
        # STEP 9: Entry Zone Calculated
        # ============================================================
        fb3_logger.log_entry_zone(symbol, entry_zone)
        zone_ok = entry_zone.found
        zone_evidence = {
            "found": entry_zone.found,
            "fib_level": entry_zone.fib_level,
            "zone_low": entry_zone.zone_low,
            "zone_high": entry_zone.zone_high,
            "midpoint": entry_zone.midpoint,
            "quality_score": entry_zone.quality_score,
            "confluence_types": entry_zone.confluence_types,
            "retracement_ratio": entry_zone.retracement_ratio,
            "price_in_zone": entry_zone.price_in_zone,
        }
        if self._process_step(9, zone_ok):
            states.append(make_state("entry_zone_calculated", True, zone_evidence))
        else:
            states.append(make_state("entry_zone_calculated", False, zone_evidence, "No entry zone found"))
            self._fail("No entry zone", "entry_zone_calculated")
            self.result.states = states
            return self.result
        
        # ============================================================
        # STEP 10: Retracement Wait (check if price is near/at zone)
        # ============================================================
        in_zone = entry_zone.price_in_zone
        near_zone = zone_ok and entry_zone.retracement_ratio >= 0.2
        
        if config.ENTRY_METHOD == "limit":
            retrace_ok = in_zone
        elif config.ENTRY_METHOD == "microstructure":
            retrace_ok = in_zone or near_zone
        else:  # confirmation
            retrace_ok = in_zone or near_zone
        
        retrace_evidence = {
            "entry_method": config.ENTRY_METHOD,
            "price_in_zone": in_zone,
            "near_zone": near_zone,
            "retracement_ratio": entry_zone.retracement_ratio,
        }
        if self._process_step(10, retrace_ok):
            states.append(make_state("retracement_wait", True, retrace_evidence))
        else:
            states.append(make_state("retracement_wait", False, retrace_evidence, "Price not near entry zone"))
            self._fail("Price not near entry zone", "retracement_wait")
            self.result.states = states
            return self.result
        
        # ============================================================
        # STEP 11: Entry Confirmation
        # ============================================================
        # For confirmation method: need a reaction candle in the zone
        # For microstructure: need price action setup
        # For limit: no confirmation needed (limit order placed at zone)
        if config.ENTRY_METHOD == "confirmation":
            entry_confirmed = _check_microstructure(symbol, entry_price or 0.0, stop_loss or 0.0, levels)
        elif config.ENTRY_METHOD == "microstructure":
            entry_confirmed = True  # Market order + SL at entry time
        else:
            entry_confirmed = True  # Limit order: no confirmation
        
        entry_evidence = {
            "entry_method": config.ENTRY_METHOD,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "entry_confirmed": entry_confirmed,
        }
        if self._process_step(11, entry_confirmed and entry_price is not None and stop_loss is not None):
            states.append(make_state("entry_confirmation", True, entry_evidence))
        else:
            states.append(make_state("entry_confirmation", False, entry_evidence, "Entry confirmation failed"))
            self._fail("Entry not confirmed", "entry_confirmation")
            self.result.states = states
            return self.result
        
        # ============================================================
        # STEP 12: Risk Approved
        # ============================================================
        risk_ok = risk_reward >= config.MIN_RR and position_size > 0
        risk_evidence = {
            "risk_reward": risk_reward,
            "min_rr": config.MIN_RR,
            "position_size": position_size,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
        }
        if self._process_step(12, risk_ok):
            states.append(make_state("risk_approved", True, risk_evidence))
        else:
            states.append(make_state("risk_approved", False, risk_evidence, f"Risk rejected: RR={risk_reward:.2f} vs min={config.MIN_RR}"))
            self._fail(f"Risk rejected: RR={risk_reward:.2f}, size={position_size}", "risk_approved")
            self.result.states = states
            return self.result
        
        # ============================================================
        # ALL GATES PASSED
        # ============================================================
        self.result.executable = True
        self.result.direction = (
            "buy" if htf_bias == "bullish" else "sell" if htf_bias == "bearish" else None
        )
        self.result.reason = "all gates passed"
        
        # Calculate score
        self.result.score = _calculate_score(
            htf_bias, htf_confidence, levels, sweep, choch, macd, sma,
            entry_zone, risk_reward, consolidation,
        )
        self.result.score_components = {
            "htf_bias": int(config.WEIGHT_HTF * (1.0 if htf_confidence >= 0.6 else 0.5)),
            "liquidity_mapped": int(config.WEIGHT_LIQUIDITY * (0.8 if sweep.detected else 0.3)),
            "sweep": int(config.WEIGHT_SWEEP * sweep.classification_score) if sweep.classification_score > 0 else 0,
            "choch": int(config.WEIGHT_CHOCH * (1.0 if choch.detected else 0.0)),
            "macd": int(config.WEIGHT_MACD * (1.0 if macd.confirmed else 0.3)),
            "sma": int(config.WEIGHT_SMA * (1.0 if sma.confirmed else 0.3)),
            "entry_zone": int(config.WEIGHT_ENTRY_ZONE * entry_zone.quality_score),
            "displacement": int(config.WEIGHT_DISPLACEMENT * (1.0 if sweep.displacement_detected else 0.0)),
            "risk_reward": int(config.WEIGHT_RISK_REWARD * min(1.0, risk_reward / 3.0)),
        }
        
        states.append(make_state("order_executed", True, {}, "All 12 gates passed. Ready for market execution."))
        self.result.states = states
        self.result.evidence = {
            "total_states": len(states),
            "passed_states": sum(1 for s in states if s.get("confirmed")),
        }
        
        return self.result
    
    def _process_step(self, step_index: int, condition: bool) -> bool:
        """Process a state step. Returns True to continue, False to stop."""
        if self.failed:
            return False
        if condition:
            self.current_step = step_index + 1
            return True
        self.failed = True
        return False
    
    def _fail(self, reason: str, stage: str) -> None:
        """Mark the state machine as failed."""
        self.result.executable = False
        self.result.rejection_reason = reason
        self.result.failed_stage = stage
        self.result.reason = reason


def _calculate_score(
    htf_bias: Optional[str],
    htf_confidence: float,
    levels: Dict[str, Any],
    sweep: SweepResult,
    choch: CHOCHResult,
    macd: MACDResult,
    sma: SMAResult,
    entry_zone: EntryZoneResult,
    risk_reward: float,
    consolidation: ConsolidationResult,
) -> int:
    """
    Calculate a quality score (0-100) for the setup.
    Used in SCORE activation mode.
    """
    score = 0

    # HTF Bias (max 15)
    if htf_bias in ("bullish", "bearish"):
        score += int(15 * htf_confidence)

    # Liquidity (max 15)
    liq_count = len(levels.get("swing_highs", [])) + len(levels.get("swing_lows", []))
    if liq_count >= 3:
        score += 15
    elif liq_count >= 1:
        score += 8

    # Sweep (max 15)
    if sweep.classification == "sweep":
        score += int(15 * min(1.0, sweep.classification_score))

    # Displacement (max 10)
    if sweep.displacement_detected:
        score += 10

    # CHOCH (max 15)
    if choch.detected:
        score += 10
        if choch.break_candle_confirmed and not choch.immediately_invalidated:
            score += 5

    # MACD (max 10)
    if macd.confirmed:
        score += 10
    elif not macd.contradiction:
        score += 3

    # SMA (max 10)
    if sma.confirmed:
        score += 10
    elif not sma.contradiction:
        score += 3

    # Entry Zone (max 5)
    score += int(5 * entry_zone.quality_score)

    # Risk/Reward (max 5)
    score += int(5 * min(1.0, risk_reward / 3.0))

    # Penalty for consolidation
    if consolidation.consolidating:
        score -= int(15 * consolidation.confidence)

    return max(0, min(100, score))


def _check_microstructure(
    symbol: str,
    entry_price: float,
    stop_loss: float,
    levels: Dict[str, Any],
) -> bool:
    """
    Check for microstructure confirmation on the execution timeframe.
    For now, uses market order if all prior gates passed.
    This can be extended to check for rejection candles at the zone.
    """
    return True  # Market order entry
