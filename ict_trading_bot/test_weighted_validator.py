#!/usr/bin/env python
"""Test script for weighted entry validator with intelligent alternative paths"""

from strategy.weighted_entry_validator import (
    calculate_entry_confidence,
    format_confidence_report,
)

# Sample signal data
signal = {
    "direction": "buy",
    "price": 1.1050,
    "fib_zone": "discount",
}

# Sample analysis data
analysis = {
    "overall_trend": "bullish",
    "topdown": {"trend": "bullish"},
    "HTF": {"trend": "bullish", "atr": 0.002},
    "MTF": {"trend": "bullish", "atr": 0.001},
    "LTF": {"trend": "bullish", "atr": 0.0005},
}

print("\n" + "="*100)
print("WEIGHTED ENTRY VALIDATOR - INTELLIGENT ALTERNATIVE PATHS")
print("="*100 + "\n")

# ============================================================================
# TEST 1: STRONG STRUCTURE DESPITE WEAK PRICE ACTION
# ============================================================================
print("TEST 1: Strong Structure Override (Liquidity+BOS+FVG+OB all met, price action weak)")
print("-" * 100)

confirmation_flags_structure = {
    "liquidity_setup": {"confirmed": True},
    "bos": {"confirmed": True},
    "fvg": {"confirmed": True},
    "order_block_confirmed": True,
    "price_action": {"confirmed": False, "patterns": []},  # WEAK
    "smt": True,
    "rule_quality": True,
    "ml": True,
}

confidence_data_structure = calculate_entry_confidence(
    signal=signal,
    analysis=analysis,
    trend="bullish",
    price=1.1050,
    confirmation_flags=confirmation_flags_structure,
)

print(format_confidence_report(confidence_data_structure))
print(f"\n✓ Execution Route: {confidence_data_structure['execution_route'].upper()}")
print(f"✓ Backtest Required: {confidence_data_structure['backtest_required']}")
print(f"✓ Alternative Path: {confirmation_flags_structure.get('price_action', {}).get('confirmed')} → {confidence_data_structure.get('alternative_path', {}).get('type')}")

# ============================================================================
# TEST 2: INTELLIGENT ALTERNATIVE PATH - Weak Topdown But Exceptional Structure
# ============================================================================
print("\n\nTEST 2: Intelligent Alternative (Weak Topdown BUT Liquidity+BOS+FVG+OB+Price Strong)")
print("-" * 100)

analysis_weak_topdown = {
    "overall_trend": "bullish",
    "topdown": {"trend": "bearish"},  # CONFLICTING TOPDOWN
    "HTF": {"trend": "bullish", "atr": 0.002},
    "MTF": {"trend": "bullish", "atr": 0.001},
    "LTF": {"trend": "bullish", "atr": 0.0005},
}

confirmation_flags_exceptional = {
    "liquidity_setup": {"confirmed": True},
    "bos": {"confirmed": True},
    "fvg": {"confirmed": True},
    "order_block_confirmed": True,
    "price_action": {"confirmed": True, "patterns": ["engulfing", "momentum"]},
    "smt": True,
    "rule_quality": True,
    "ml": True,
}

confidence_data_intelligent = calculate_entry_confidence(
    signal=signal,
    analysis=analysis_weak_topdown,
    trend="bullish",
    price=1.1050,
    confirmation_flags=confirmation_flags_exceptional,
)

print(format_confidence_report(confidence_data_intelligent))
print(f"\n✓ Execution Route: {confidence_data_intelligent['execution_route'].upper()}")
print(f"✓ Backtest Required: {confidence_data_intelligent['backtest_required']}")
print(f"✓ Alternative Path Type: {confidence_data_intelligent.get('alternative_path', {}).get('type')}")
print(f"✓ Smart Confidence: {confidence_data_intelligent.get('alternative_path', {}).get('confidence_if_direct', 0):.1f}/100")

# ============================================================================
# TEST 3: WEAK TOPDOWN & TREND + WEAK STRUCTURE = SKIP
# ============================================================================
print("\n\nTEST 3: Weak on All Fronts (Should Skip)")
print("-" * 100)

analysis_weak = {
    "overall_trend": "bullish",
    "topdown": {"trend": "bearish"},
    "HTF": {"trend": "bearish"},
    "MTF": {"trend": "bullish"},
    "LTF": {"trend": "bullish"},
}

confirmation_flags_weak = {
    "liquidity_setup": {"confirmed": False},
    "bos": {"confirmed": False},
    "fvg": {"confirmed": False},
    "order_block_confirmed": False,
    "price_action": {"confirmed": False},
    "smt": False,
    "rule_quality": False,
    "ml": False,
}

confidence_data_weak = calculate_entry_confidence(
    signal=signal,
    analysis=analysis_weak,
    trend="bullish",
    price=1.1050,
    confirmation_flags=confirmation_flags_weak,
)

print(format_confidence_report(confidence_data_weak))
print(f"\n✓ Execution Route: {confidence_data_weak['execution_route'].upper()}")
print(f"✓ Backtest Required: {confidence_data_weak['backtest_required']}")

# ============================================================================
# TEST 4: PERFECT SCENARIO
# ============================================================================
print("\n\nTEST 4: Perfect Scenario (All Strong)")
print("-" * 100)

confirmation_flags_perfect = {
    "liquidity_setup": {"confirmed": True},
    "bos": {"confirmed": True},
    "fvg": {"confirmed": True},
    "order_block_confirmed": True,
    "price_action": {"confirmed": True, "patterns": ["engulfing", "momentum"]},
    "smt": True,
    "rule_quality": True,
    "ml": True,
}

confidence_data_perfect = calculate_entry_confidence(
    signal=signal,
    analysis=analysis,
    trend="bullish",
    price=1.1050,
    confirmation_flags=confirmation_flags_perfect,
)

print(format_confidence_report(confidence_data_perfect))
print(f"\n✓ Execution Route: {confidence_data_perfect['execution_route'].upper()}")
print(f"✓ Backtest Required: {confidence_data_perfect['backtest_required']}")

print("\n" + "="*100)
print("All tests completed successfully!")
print("="*100 + "\n")

