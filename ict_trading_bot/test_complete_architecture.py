"""
Comprehensive validation for the strict ICT architecture.
"""

import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from strategy.weighted_entry_validator import calculate_entry_confidence


BASE_SIGNAL = {
    "direction": "buy",
    "price": 1.2040,
    "fib_zone": "discount",
    "valid_fvg": True,
    "valid_order_block": True,
    "displacement": 0.84,
}

BASE_ANALYSIS = {
    "overall_trend": "bullish",
    "topdown": {"trend": "bullish", "context_alignment": "aligned"},
    "HTF": {"trend": "bullish"},
    "MTF": {"trend": "bullish"},
    "LTF": {"trend": "bullish"},
}

BASE_CONFIRMATIONS = {
    "liquidity_setup": {"confirmed": True, "displacement_score": 0.84},
    "bos": {"confirmed": True},
    "displacement": {"confirmed": True, "score": 0.84},
    "fvg": {"confirmed": True},
    "order_block_confirmed": True,
    "price_action": {"confirmed": True, "patterns": ["engulfing", "rejection"]},
    "smt": True,
    "rule_quality": True,
    "ml": True,
}

STRONG_CIS = {
    "final_verdict": "TRADE",
    "confidence_score": 0.85,
    "history_count": 140,
    "component_scores": {"timing": 0.90, "setup_quality": 0.88},
}


def print_result(name, passed, result):
    status = "PASS" if passed else "FAIL"
    print(f"{status}: {name} -> confidence={result['confidence']} route={result['execution_route']}")


def run_test(name, signal, analysis, confirmations, cis, predicate):
    result = calculate_entry_confidence(
        signal=signal,
        analysis=analysis,
        trend="bullish",
        price=signal["price"],
        confirmation_flags=confirmations,
        cis_decision=cis,
    )
    passed = predicate(result)
    print_result(name, passed, result)
    return passed


results = [
    run_test(
        "Perfect strict setup",
        BASE_SIGNAL,
        BASE_ANALYSIS,
        BASE_CONFIRMATIONS,
        STRONG_CIS,
        lambda result: result["execution_route"] in ("elite", "standard") and not result["backtest_required"],
    ),
    run_test(
        "Missing liquidity sweep blocks",
        BASE_SIGNAL,
        BASE_ANALYSIS,
        {**BASE_CONFIRMATIONS, "liquidity_setup": {"confirmed": False, "displacement_score": 0.84}},
        STRONG_CIS,
        lambda result: result["execution_route"] == "skip",
    ),
    run_test(
        "Missing BOS blocks",
        BASE_SIGNAL,
        BASE_ANALYSIS,
        {**BASE_CONFIRMATIONS, "bos": {"confirmed": False}},
        STRONG_CIS,
        lambda result: result["execution_route"] == "skip",
    ),
    run_test(
        "Weak displacement blocks",
        {**BASE_SIGNAL, "displacement": 0.40},
        BASE_ANALYSIS,
        {**BASE_CONFIRMATIONS, "displacement": {"confirmed": False, "score": 0.40}, "liquidity_setup": {"confirmed": True, "displacement_score": 0.40}},
        STRONG_CIS,
        lambda result: result["execution_route"] == "skip",
    ),
    run_test(
        "Topdown conflict blocks",
        BASE_SIGNAL,
        {**BASE_ANALYSIS, "topdown": {"trend": "bearish", "context_alignment": "opposed"}},
        BASE_CONFIRMATIONS,
        STRONG_CIS,
        lambda result: result["execution_route"] == "skip",
    ),
    run_test(
        "Insufficient live history forces backtest",
        BASE_SIGNAL,
        BASE_ANALYSIS,
        BASE_CONFIRMATIONS,
        {"final_verdict": "TRADE", "confidence_score": 0.80, "history_count": 30, "component_scores": {"timing": 0.82, "setup_quality": 0.85}},
        lambda result: result["backtest_required"] and result["execution_route"] in ("standard_validated", "conservative"),
    ),
]

print(f"\nSUMMARY: {sum(results)}/{len(results)} tests passed")
raise SystemExit(0 if all(results) else 1)
