"""Backward-compatible imports for the unified ICT state machine."""

from strategy.unified_strategy import STATE_WEIGHTS, evaluate_strategy, evaluate_unified_setup

WEIGHTS = STATE_WEIGHTS

__all__ = ["STATE_WEIGHTS", "WEIGHTS", "evaluate_strategy", "evaluate_unified_setup"]
