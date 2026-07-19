"""
FALLBACK STRATEGY 4 - State Machine
=====================================
Rigorous sequential state machine for Fallback 4.
21 states that must pass in order. Rejects immediately at first failure.
"""

from typing import Any, Dict, List, Optional, Tuple

from . import config
from .models import Fallback4SetupResult, make_state


# ============================================================
# States in strict sequence
# ============================================================
FALLBACK4_STATES = [
    "fallback4_eligible",
    "risk_check",
    "context_analysis",
    "range_candidate",
    "range_confirmed",
    "boundary_liquidity_mapped",
    "boundary_interaction",
    "outside_range",
    "sweep_or_breakout_classification",
    "reclaim_pending",
    "range_reclaimed",
    "displacement_pending",
    "structure_change_pending",
    "structure_change_confirmed",
    "entry_zone_calculated",
    "entry_pending",
    "order_approval",
    "trade_active",
    "trade_complete",
    "setup_invalidated",
]


class Fallback4StateMachine:
    """
    Sequential state machine for Fallback Strategy 4.
    
    Progresses through states in order. Each state can only pass or fail.
    Once a state fails, all subsequent states are blocked.
    The machine records the exact failure reason and failed state name.
    """
    
    def __init__(self):
        self._states: List[Dict[str, Any]] = []
        self._failed = False
        self._failed_state = ""
        self._failed_reason = ""
        self._current_index = 0
    
    @property
    def states(self) -> List[Dict[str, Any]]:
        return list(self._states)
    
    @property
    def failed(self) -> bool:
        return self._failed
    
    @property
    def failed_state(self) -> str:
        return self._failed_state
    
    @property
    def failed_reason(self) -> str:
        return self._failed_reason
    
    @property
    def passed_count(self) -> int:
        return sum(1 for s in self._states if s.get("confirmed"))
    
    @property
    def all_passed(self) -> bool:
        return self.passed_count == len(FALLBACK4_STATES) and not self._failed
    
    def process(
        self,
        symbol: str,
        direction: str,
        range_data,
        sweep,
        reclaim,
        displacement,
        structure_change,
        entry,
        score: int,
        score_components: dict,
        ict_setup=None,
        kingsbalfx_setup=None,
        fallback3_setup=None,
        account=None,
        positions=None,
        tick=None,
        analysis=None,
        risk_percent=0.35,
        minimum_rr=1.5,
        context_bias="neutral",
        execution_timeframe="M5",
        context_timeframe="M15",
    ) -> Fallback4SetupResult:
        """
        Run the complete state machine for a single symbol.
        Returns a Fallback4SetupResult with full state information.
        """
        result = Fallback4SetupResult(
            symbol=symbol,
            direction=direction,
            execution_timeframe=execution_timeframe,
            context_timeframe=context_timeframe,
            context_bias=context_bias,
            range_data=range_data,
            sweep=sweep,
            reclaim=reclaim,
            displacement=displacement,
            structure_change=structure_change,
            entry=entry,
            score=score,
            score_components=score_components,
        )

        skip_to_trade = False

        # ----------------------------------------------------------
        # State 1: FALLBACK4_ELIGIBLE
        # ----------------------------------------------------------
        if self._check_or_fail("fallback4_eligible"):
            eligible = True
            reasons = []

            if ict_setup and ict_setup.get("executable"):
                eligible = False
                reasons.append(f"ICT_valid:{ict_setup.get('reason','')}")
            if kingsbalfx_setup and kingsbalfx_setup.get("executable"):
                eligible = False
                reasons.append(f"KBX_valid:{kingsbalfx_setup.get('reason','')}")
            if fallback3_setup and fallback3_setup.get("executable"):
                eligible = False
                reasons.append(f"FB3_valid:{fallback3_setup.get('reason','')}")

            if eligible:
                self._pass("fallback4_eligible", {"higher_priority_skipped": True})
            else:
                self._fail("fallback4_eligible", {"conflicts": reasons},
                           f"higher_priority_strategy_active: {', '.join(reasons)}")

        # ----------------------------------------------------------
        # State 2: RISK_CHECK
        # ----------------------------------------------------------
        if self._check_or_fail("risk_check"):
            from .risk import check_risk_gate
            risk_passed, risk_reason = check_risk_gate(
                symbol, direction or "", account or {},
                positions or [], ict_setup or {},
                kingsbalfx_setup or {}, fallback3_setup,
            )
            if risk_passed:
                self._pass("risk_check", {"risk_gate_passed": True})
            else:
                self._fail("risk_check", {"risk_reason": risk_reason}, risk_reason)

        # ----------------------------------------------------------
        # State 3: CONTEXT_ANALYSIS
        # ----------------------------------------------------------
        if self._check_or_fail("context_analysis"):
            if self._check_context(context_bias):
                self._pass("context_analysis", {"context_bias": context_bias})
            else:
                self._fail("context_analysis", {"context_bias": context_bias},
                           f"context_{context_bias}_not_supported_without_countertrend")

        # ----------------------------------------------------------
        # State 4: RANGE_CANDIDATE
        # ----------------------------------------------------------
        if self._check_or_fail("range_candidate"):
            if range_data.detected and not range_data.rejected:
                self._pass("range_candidate", {
                    "range_high": range_data.range_high,
                    "range_low": range_data.range_low,
                    "candidate_found": True,
                })
            else:
                self._fail("range_candidate", {"rejection": range_data.rejection_reason},
                           f"no_range_candidate: {range_data.rejection_reason}")

        # ----------------------------------------------------------
        # State 5: RANGE_CONFIRMED
        # ----------------------------------------------------------
        if self._check_or_fail("range_confirmed"):
            if range_data.is_valid:
                self._pass("range_confirmed", {
                    "quality_score": range_data.quality_score,
                    "width_atr": range_data.range_width_atr,
                    "duration": range_data.duration,
                    "upper_interactions": range_data.upper_interactions,
                    "lower_interactions": range_data.lower_interactions,
                    "rotations": range_data.rotations,
                })
            else:
                self._fail("range_confirmed", {"rejection": range_data.rejection_reason},
                           f"range_not_confirmed: {range_data.rejection_reason}")

        # ----------------------------------------------------------
        # State 6: BOUNDARY_LIQUIDITY_MAPPED
        # ----------------------------------------------------------
        if self._check_or_fail("boundary_liquidity_mapped"):
            has_upper = range_data.upper_zone is not None and range_data.upper_zone.interaction_count > 0
            has_lower = range_data.lower_zone is not None and range_data.lower_zone.interaction_count > 0
            if has_upper and has_lower:
                self._pass("boundary_liquidity_mapped", {
                    "upper_quality": range_data.upper_zone.liquidity_quality if range_data.upper_zone else 0,
                    "lower_quality": range_data.lower_zone.liquidity_quality if range_data.lower_zone else 0,
                })
            else:
                self._fail("boundary_liquidity_mapped", {},
                           "insufficient_boundary_liquidity")

        # ----------------------------------------------------------
        # State 7: BOUNDARY_INTERACTION
        # ----------------------------------------------------------
        if self._check_or_fail("boundary_interaction"):
            if sweep.detected:
                self._pass("boundary_interaction", {
                    "sweep_side": sweep.side,
                    "extreme_price": sweep.extreme_price,
                })
            else:
                self._fail("boundary_interaction", {},
                           "no_boundary_interaction_or_sweep")

        # ----------------------------------------------------------
        # State 8: OUTSIDE_RANGE (observational, not a gate)
        # ----------------------------------------------------------
        if self._check_or_fail("outside_range"):
            self._pass("outside_range", {
                "candles_outside": sweep.candles_outside,
                "penetration_atr": sweep.penetration_atr,
            })

        # ----------------------------------------------------------
        # State 9: SWEEP_OR_BREAKOUT_CLASSIFICATION
        # ----------------------------------------------------------
        if self._check_or_fail("sweep_or_breakout_classification"):
            if sweep.classification in ("sweep", "probable_sweep"):
                self._pass("sweep_or_breakout_classification", {
                    "classification": sweep.classification,
                    "sweep_score": sweep.sweep_score,
                    "breakout_score": sweep.breakout_score,
                })
            elif sweep.classification in ("genuine_breakout", "uncertain"):
                self._fail("sweep_or_breakout_classification",
                           {"classification": sweep.classification},
                           f"genuine_breakout_or_uncertain: {sweep.classification}")
            else:
                # probable_breakout — still not confident enough
                self._fail("sweep_or_breakout_classification",
                           {"classification": sweep.classification,
                            "sweep_score": sweep.sweep_score},
                           f"probable_breakout_sweep_score_{sweep.sweep_score:.2f}")

        # ----------------------------------------------------------
        # State 10: RECLAIM_PENDING
        # ----------------------------------------------------------
        if self._check_or_fail("reclaim_pending"):
            if reclaim.reclaimed:
                self._pass("reclaim_pending", {
                    "reclaim_candle_index": reclaim.reclaim_candle_index,
                    "mode_used": reclaim.mode_used,
                })
            else:
                self._fail("reclaim_pending", {"failure": reclaim.failure_reason},
                           f"range_not_reclaimed: {reclaim.failure_reason}")

        # ----------------------------------------------------------
        # State 11: RANGE_RECLAIMED
        # ----------------------------------------------------------
        if self._check_or_fail("range_reclaimed"):
            if reclaim.reclaimed and reclaim.reclaim_strength >= 30:
                self._pass("range_reclaimed", {
                    "reclaim_strength": reclaim.reclaim_strength,
                    "reclaim_body_ratio": reclaim.reclaim_candle_body_ratio,
                    "buffer_met": reclaim.reclaim_buffer_met,
                })
            elif reclaim.reclaimed:
                self._fail("range_reclaimed", {"reclaim_strength": reclaim.reclaim_strength},
                           f"reclaim_strength_{reclaim.reclaim_strength}_too_weak")
            else:
                self._fail("range_reclaimed", {}, "range_reclaim_not_confirmed")

        # ----------------------------------------------------------
        # State 12: DISPLACEMENT_PENDING
        # ----------------------------------------------------------
        if self._check_or_fail("displacement_pending"):
            if displacement.detected:
                self._pass("displacement_pending", {
                    "displacement_index": displacement.candle_index,
                    "displacement_score": displacement.score,
                })
            else:
                self._fail("displacement_pending", {},
                           "no_displacement_after_reclaim")

        # ----------------------------------------------------------
        # State 13: STRUCTURE_CHANGE_PENDING
        # ----------------------------------------------------------
        if self._check_or_fail("structure_change_pending"):
            if structure_change.confirmed:
                self._pass("structure_change_pending", {
                    "method": structure_change.method,
                    "swing_level": structure_change.swing_level,
                })
            else:
                self._fail("structure_change_pending",
                           {"rejection": structure_change.rejection_reason},
                           f"no_structure_change: {structure_change.rejection_reason}")

        # ----------------------------------------------------------
        # State 14: STRUCTURE_CHANGE_CONFIRMED
        # ----------------------------------------------------------
        if self._check_or_fail("structure_change_confirmed"):
            if structure_change.confirmed and not structure_change.invalidated:
                self._pass("structure_change_confirmed", {
                    "method": structure_change.method,
                    "body_ratio": structure_change.body_ratio,
                    "close_distance_atr": structure_change.close_distance_atr,
                })
            elif structure_change.invalidated:
                self._fail("structure_change_confirmed", {},
                           "structure_change_invalidated_by_next_candle")
            else:
                self._fail("structure_change_confirmed", {},
                           "structure_change_not_confirmed")

        # ----------------------------------------------------------
        # State 15: ENTRY_ZONE_CALCULATED
        # ----------------------------------------------------------
        if self._check_or_fail("entry_zone_calculated"):
            if entry.confirmed:
                self._pass("entry_zone_calculated", {
                    "model": entry.model,
                    "entry_price": entry.entry_price,
                    "zone_low": entry.zone_low,
                    "zone_high": entry.zone_high,
                    "fib_level": entry.fib_level_used,
                })
            else:
                self._fail("entry_zone_calculated",
                           {"rejection": entry.rejection_reason},
                           f"no_valid_entry_zone: {entry.rejection_reason}")

        # ----------------------------------------------------------
        # State 16: ENTRY_PENDING
        # ----------------------------------------------------------
        if self._check_or_fail("entry_pending"):
            # Entry zone is already confirmed by this point
            self._pass("entry_pending", {"entry_model": entry.model, "entry_confirmed": True})

        # ----------------------------------------------------------
        # State 17: ORDER_APPROVAL
        # ----------------------------------------------------------
        if self._check_or_fail("order_approval"):
            # This will be handled in evaluate.py with actual calculations
            self._pass("order_approval", {"pending_external_validation": True})

        # ----------------------------------------------------------
        # State 18: TRADE_ACTIVE (marked as passed, actual execution in main.py)
        # ----------------------------------------------------------
        if self._check_or_fail("trade_active"):
            self._pass("trade_active", {"ready_for_execution": True})

        # ----------------------------------------------------------
        # State 19: TRADE_COMPLETE (marked as passed)
        # ----------------------------------------------------------
        if self._check_or_fail("trade_complete"):
            self._pass("trade_complete", {})

        # ----------------------------------------------------------
        # State 20: SETUP_INVALIDATED (only triggers on failure)
        # ----------------------------------------------------------
        if self._check_or_fail("setup_invalidated"):
            # Only reached if all previous states passed
            self._pass("setup_invalidated", {"not_invalidated": True})

        # Build final result
        result.states = self.states
        if self._failed:
            result.executable = False
            result.failed_stage = self._failed_state
            result.rejection_reason = self._failed_reason
            result.reason = f"failed_at_{self._failed_state}: {self._failed_reason}"
        else:
            result.executable = True
            result.reason = "all_states_passed"

        return result

    def _check_context(self, context_bias: str) -> bool:
        """Check if context bias supports the trade direction."""
        if context_bias in ("bullish", "bearish"):
            return True
        if context_bias == "neutral":
            return True  # Range context supports range trading
        if context_bias == "conflicting":
            return config.COUNTERTREND_ENABLED
        return False

    def _check_or_fail(self, state_name: str) -> bool:
        """Check if we can evaluate this state (no prior failure)."""
        if self._failed:
            # Record blocked state
            self._states.append(make_state(state_name, False, {}, "BLOCKED: earlier state failed"))
            return False
        return True

    def _pass(self, state_name: str, evidence: dict, reason: str = ""):
        """Record a passed state."""
        self._states.append(make_state(state_name, True, evidence, reason or "passed"))

    def _fail(self, state_name: str, evidence: dict, reason: str):
        """Record a failed state and block all subsequent states."""
        self._states.append(make_state(state_name, False, evidence, reason))
        self._failed = True
        self._failed_state = state_name
        self._failed_reason = reason
