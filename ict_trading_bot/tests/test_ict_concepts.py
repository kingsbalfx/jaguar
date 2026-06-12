from datetime import datetime, timezone

import pandas as pd

from ict_concepts.fib import fib_dealing_range, ote_zone, price_zone
from ict_concepts.fvg import detect_fvg_from_df, qualify_fvgs
from ict_concepts.liquidity import detect_liquidity_zones, rank_liquidity_zones
from ict_concepts.order_blocks import qualify_order_blocks
from risk.backtest_engine import generate_setup_occurrence_report
from strategy.ict_setup_quality import validate_setup
from strategy.unified_strategy import SEQUENCE, evaluate_strategy


def _analysis():
    fib = fib_dealing_range(1.1200, 1.0900)
    candles = [
        {"open": 1.1010, "high": 1.1020, "low": 1.0990, "close": 1.1000, "volume": 100},
        {"open": 1.1000, "high": 1.1010, "low": 1.0980, "close": 1.0990, "volume": 120},
        {"open": 1.0990, "high": 1.1040, "low": 1.0975, "close": 1.1038, "volume": 200},
        {"open": 1.1038, "high": 1.1060, "low": 1.1030, "close": 1.1055, "volume": 180},
        {"open": 1.1055, "high": 1.1070, "low": 1.1040, "close": 1.1065, "volume": 170},
    ]
    swings = [
        {"type": "low", "price": 1.0980, "index": 1},
        {"type": "high", "price": 1.1040, "index": 2},
        {"type": "low", "price": 1.0990, "index": 3},
        {"type": "high", "price": 1.1080, "index": 8},
    ]
    fvg = {
        "type": "bullish",
        "low": 1.1000,
        "high": 1.1040,
        "midpoint": 1.1020,
        "active": True,
        "mitigated": False,
        "displacement_ok": True,
        "size_ok": True,
        "context_aligned": True,
        "origin_index": 5,
    }
    order_block = {
        "type": "bullish",
        "low": 1.0995,
        "high": 1.1030,
        "midpoint": 1.10125,
        "fresh": True,
        "mitigated": False,
        "institutional_footprint": True,
        "final_opposing_candle": True,
        "displacement": 0.85,
        "index": 4,
        "liquidity_sweep_confirmed": True,
    }
    state = {
        "trend": "bullish",
        "fib": fib,
        "swings": swings,
        "fvgs": [fvg],
        "order_blocks": [order_block],
        "liquidity": {"EQH": [{"type": "high", "level": 1.1080, "touches": 2, "separation": 7, "untaken": True}], "EQL": []},
        "recent_candles": candles,
        "atr": 0.001,
    }
    return {
        "overall_trend": "bullish",
        "daily_trend": "bullish",
        "HTF": {"D1": "bullish", "H4": "bullish", **state},
        "MTF": dict(state),
        "LTF": dict(state),
        "EXECUTION": dict(state),
        "m5_candles": candles,
    }


def test_fib_ote_and_premium_discount_are_directional():
    fib = fib_dealing_range(1.1100, 1.0900)
    low, high = ote_zone(fib, "buy")
    assert low < high
    assert price_zone(1.0950, fib) == "discount"
    assert price_zone(1.1050, fib) == "premium"


def test_liquidity_is_ranked_in_target_direction():
    swings = [
        {"type": "high", "price": 1.1080, "index": 1},
        {"type": "high", "price": 1.10801, "index": 8},
    ]
    zones = detect_liquidity_zones(swings, atr=0.001, min_separation=3)
    ranked = rank_liquidity_zones(zones, 1.1020, "buy")
    assert ranked[0]["level"] > 1.1020


def test_true_fvg_and_order_block_require_sequence_evidence():
    analysis = _analysis()
    fib = analysis["MTF"]["fib"]
    fvgs = qualify_fvgs(analysis["LTF"]["fvgs"], direction="buy", structure_break=True, liquidity_sweep=True, fib=fib)
    blocks = qualify_order_blocks(analysis["MTF"]["order_blocks"], direction="buy", structure_break=True, liquidity_sweep=True, fvgs=fvgs, fib=fib)
    assert fvgs[0]["true_fvg"]
    assert blocks[0]["true_order_block"]
    assert not qualify_fvgs(analysis["LTF"]["fvgs"], direction="buy", structure_break=False, liquidity_sweep=True, fib=fib)[0]["true_fvg"]


def test_three_candle_fvg_detection_requires_displacement():
    frame = pd.DataFrame(
        [
            {"open": 1.1000, "high": 1.1010, "low": 1.0990, "close": 1.1005},
            {"open": 1.1005, "high": 1.1050, "low": 1.1000, "close": 1.1048},
            {"open": 1.1040, "high": 1.1060, "low": 1.1030, "close": 1.1050},
        ]
    )
    assert detect_fvg_from_df(frame, trend="bullish")[0]["displacement_ok"]


def test_binary_setup_validation_rejects_first_missing_condition():
    features = {name: True for name in ("sweep", "displacement", "bos", "ob_exists", "fvg_exists", "retracement", "premium_discount", "target_liquidity", "smt")}
    features["bos"] = False
    result = validate_setup(features, "trending", True)
    assert not result["confirmed"]
    assert result["failed_step"] == "bos"


def test_unified_strategy_stops_at_first_missing_state():
    result = evaluate_strategy("EURUSD", 1.1020, _analysis(), killzone_active=True)
    assert result["failed_step"] == "liquidity_sweep"
    assert [state["name"] for state in result["states"]] == list(SEQUENCE[:3])
    assert not result["executable"]


def test_unified_strategy_executes_only_when_every_state_is_confirmed(monkeypatch):
    import strategy.unified_strategy as unified

    monkeypatch.setattr(unified, "liquidity_sweep_or_swing", lambda *_args, **_kwargs: {"confirmed": True, "displacement": True})
    monkeypatch.setattr(unified, "bos_setup", lambda *_args, **_kwargs: {"confirmed": True, "structure_signal": "bos"})
    monkeypatch.setattr(unified, "price_action_setup", lambda *_args, **_kwargs: {"confirmed": True})
    result = unified.evaluate_strategy(
        "EURUSD",
        1.1020,
        _analysis(),
        smt={"confirmed": True, "direction": "bullish"},
        killzone_active=True,
    )
    assert result["confirmed"]
    assert result["executable"]
    assert [state["name"] for state in result["states"]] == list(SEQUENCE)


def test_backtest_uses_observed_future_path():
    report = generate_setup_occurrence_report(
        "EURUSD",
        {"sequence_complete": True},
        [{
            "timestamp": datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc),
            "entry_price": 1.1000,
            "sl_price": 1.0980,
            "tp_price": 1.1040,
            "direction": "buy",
            "future_highs": [1.1010, 1.1045],
            "future_lows": [1.0995, 1.1000],
        }],
        {},
        {"session_filter_enabled": False, "spread_pips": 0.0, "slippage_pips": 0.0},
    )
    assert report["metrics"]["wins"] == 1
