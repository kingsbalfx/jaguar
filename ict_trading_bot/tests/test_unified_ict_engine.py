from ict_concepts.fib import fib_dealing_range, ote_zone
from ict_concepts.fvg import qualify_fvgs
from ict_concepts.liquidity import detect_liquidity_zones
from ict_concepts.order_blocks import qualify_order_blocks
from strategy.unified_ict_engine import evaluate_unified_setup


def _candles():
    return [
        {"open": 1.1000, "high": 1.1010, "low": 1.0990, "close": 1.1005, "volume": 100},
        {"open": 1.1005, "high": 1.1015, "low": 1.0995, "close": 1.1008, "volume": 100},
        {"open": 1.1008, "high": 1.1020, "low": 1.0980, "close": 1.1015, "volume": 130},
        {"open": 1.1015, "high": 1.1040, "low": 1.1010, "close": 1.1038, "volume": 200},
        {"open": 1.1038, "high": 1.1050, "low": 1.1030, "close": 1.1045, "volume": 180},
    ]


def test_fib_contains_ote_levels():
    fib = fib_dealing_range(1.2, 1.0)
    assert abs(fib["0.62"] - 1.124) < 1e-12
    low, high = ote_zone(fib, "buy")
    assert low < high < 1.2


def test_liquidity_requires_time_separation():
    swings = [
        {"type": "low", "price": 1.1, "index": 1, "weight": 1.2},
        {"type": "low", "price": 1.10001, "index": 2, "weight": 1.2},
        {"type": "low", "price": 1.10002, "index": 8, "weight": 1.2},
    ]
    result = detect_liquidity_zones(swings, atr=0.001, min_separation=3)
    assert result["EQL"]
    assert all(zone["separation"] >= 3 for zone in result["EQL"])


def test_zone_qualification_requires_narrative_evidence():
    fib = fib_dealing_range(1.2, 1.0)
    fvg = {"type": "bullish", "low": 1.05, "high": 1.08, "midpoint": 1.065, "active": True, "mitigated": False, "displacement_ok": True, "size_ok": True, "context_aligned": True, "quality": 0.9}
    qualified = qualify_fvgs([fvg], direction="buy", structure_break=True, liquidity_sweep=True, fib=fib)
    assert qualified[0]["true_fvg"]
    ob = {"type": "bullish", "low": 1.04, "high": 1.07, "midpoint": 1.055, "fresh": True, "mitigated": False, "institutional_footprint": True, "displacement": 0.8, "index": 4, "quality": 0.9}
    qualified_ob = qualify_order_blocks([ob], direction="buy", structure_break=True, liquidity_sweep=True, fvgs=[{**fvg, "origin_index": 5}], fib=fib)
    assert qualified_ob[0]["true_order_block"]


def test_unified_setup_returns_soft_route_not_binary_gate():
    candles = _candles()
    swings = [
        {"type": "low", "price": 1.0985, "index": 1, "weight": 1.5},
        {"type": "high", "price": 1.1020, "index": 2, "weight": 1.5},
        {"type": "low", "price": 1.0990, "index": 3, "weight": 1.5},
        {"type": "high", "price": 1.1050, "index": 4, "weight": 1.5},
    ]
    fib = fib_dealing_range(1.11, 1.09)
    fvg = {"type": "bullish", "low": 1.1000, "high": 1.1040, "midpoint": 1.1020, "active": True, "mitigated": False, "displacement_ok": True, "size_ok": True, "context_aligned": True, "quality": 0.9, "origin_index": 5}
    ob = {"type": "bullish", "low": 1.0995, "high": 1.1030, "midpoint": 1.10125, "fresh": True, "mitigated": False, "institutional_footprint": True, "displacement": 0.8, "index": 4, "quality": 0.9}
    state = {"trend": "bullish", "fib": fib, "swings": swings, "fvgs": [fvg], "order_blocks": [ob], "liquidity": {"EQH": [], "EQL": []}, "recent_candles": candles, "atr": 0.001}
    analysis = {"overall_trend": "bullish", "topdown": {"trend": "bullish", "context_alignment": "aligned"}, "HTF": state, "MTF": state, "LTF": state, "EXECUTION": state}
    result = evaluate_unified_setup("EURUSD", 1.1020, analysis, smt={"confirmed": False}, killzone_active=True)
    assert result["execution_route"] in ("elite", "standard", "conservative", "observe")
    assert result["confidence"] > 0
    assert "components" in result
