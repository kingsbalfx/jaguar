#!/usr/bin/env python
"""Smoke tests for the strict weighted entry validator."""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from strategy.weighted_entry_validator import calculate_entry_confidence, format_confidence_report


BASE_SIGNAL = {
    "direction": "buy",
    "price": 1.1050,
    "fib_zone": "discount",
    "valid_fvg": True,
    "valid_order_block": True,
    "displacement": 0.82,
}

BASE_ANALYSIS = {
    "overall_trend": "bullish",
    "topdown": {"trend": "bullish", "context_alignment": "aligned"},
    "HTF": {"trend": "bullish"},
    "MTF": {"trend": "bullish"},
    "LTF": {"trend": "bullish"},
}

BASE_CONFIRMATIONS = {
    "liquidity_setup": {"confirmed": True, "displacement_score": 0.82},
    "bos": {"confirmed": True},
    "displacement": {"confirmed": True, "score": 0.82},
    "fvg": {"confirmed": True},
    "order_block_confirmed": True,
    "price_action": {"confirmed": True, "patterns": ["rejection", "momentum"]},
    "smt": True,
    "rule_quality": True,
    "ml": True,
}

STRONG_CIS = {
    "final_verdict": "TRADE",
    "confidence_score": 0.84,
    "history_count": 150,
    "component_scores": {"timing": 0.88, "setup_quality": 0.86},
}


def run_case(title, signal, analysis, confirmations, cis=None):
    result = calculate_entry_confidence(
        signal=signal,
        analysis=analysis,
        trend="bullish",
        price=signal["price"],
        confirmation_flags=confirmations,
        cis_decision=cis,
    )
    print(f"\n{title}")
    print(format_confidence_report(result))
    return result


perfect = run_case("PERFECT STRICT SETUP", BASE_SIGNAL, BASE_ANALYSIS, BASE_CONFIRMATIONS, STRONG_CIS)
assert perfect["execution_route"] in ("elite", "standard")
assert not perfect["backtest_required"]

missing_liquidity = run_case(
    "MISSING LIQUIDITY SWEEP",
    BASE_SIGNAL,
    BASE_ANALYSIS,
    {**BASE_CONFIRMATIONS, "liquidity_setup": {"confirmed": False, "displacement_score": 0.82}},
    STRONG_CIS,
)
assert missing_liquidity["confidence"] < perfect["confidence"]
assert "liquidity_sweep" in missing_liquidity["missing_core"]

insufficient_history = run_case(
    "GOOD SETUP BUT <100 REAL CIS TRADES",
    BASE_SIGNAL,
    BASE_ANALYSIS,
    BASE_CONFIRMATIONS,
    {"final_verdict": "TRADE", "confidence_score": 0.80, "history_count": 20, "component_scores": {"timing": 0.82, "setup_quality": 0.84}},
)
assert insufficient_history["backtest_required"]

print("\nWeighted validator smoke tests passed.")
