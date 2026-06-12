from ict_concepts.fib import fib_dealing_range
from ict_concepts.fvg import qualify_fvgs
from ict_concepts.liquidity import detect_liquidity_zones
from ict_concepts.order_blocks import qualify_order_blocks
from strategy.unified_ict_engine import SEQUENCE, evaluate_unified_setup


def test_liquidity_requires_time_separation():
    swings = [
        {"type": "low", "price": 1.1, "index": 1},
        {"type": "low", "price": 1.10001, "index": 2},
        {"type": "low", "price": 1.10002, "index": 8},
    ]
    result = detect_liquidity_zones(swings, atr=0.001, min_separation=3)
    assert result["EQL"]
    assert all(zone["separation"] >= 3 for zone in result["EQL"])


def test_zone_validation_requires_prior_sequence():
    fib = fib_dealing_range(1.2, 1.0)
    fvg = {"type": "bullish", "low": 1.05, "high": 1.08, "midpoint": 1.065, "active": True, "mitigated": False, "displacement_ok": True, "size_ok": True, "context_aligned": True, "origin_index": 5}
    assert qualify_fvgs([fvg], direction="buy", structure_break=True, liquidity_sweep=True, fib=fib)[0]["true_fvg"]
    block = {"type": "bullish", "low": 1.04, "high": 1.07, "midpoint": 1.055, "fresh": True, "mitigated": False, "institutional_footprint": True, "final_opposing_candle": True, "displacement": 0.8, "index": 4}
    assert qualify_order_blocks([block], direction="buy", structure_break=True, liquidity_sweep=True, fvgs=[fvg], fib=fib)[0]["true_order_block"]


def test_unified_engine_is_strict_wrapper():
    result = evaluate_unified_setup("EURUSD", 1.1, {"overall_trend": "neutral"})
    assert result["failed_step"] == SEQUENCE[0]
    assert not result["executable"]
