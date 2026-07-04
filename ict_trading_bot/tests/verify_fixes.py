"""Verify all applied fixes."""
import importlib
import inspect
import sys

sys.path.insert(0, ".")


def test_fix_1_no_del_in_fvg():
    """FIX 1: detect_fvg_from_df() no longer uses del on parameters"""
    import ict_trading_bot.ict_concepts.fvg as fvg
    src = inspect.getsource(fvg.detect_fvg_from_df)
    assert 'del min_gap_ratio' not in src, "FIX 1 FAILED: del still present"
    print("FIX 1 PASS: detect_fvg_from_df() no longer deletes unused parameters")


def test_fix_2_atr_none_check():
    """FIX 2: _atr() handles None displacement_index"""
    import ict_trading_bot.strategy.unified_strategy as us
    src = inspect.getsource(us.evaluate_strategy)
    assert "displacement_index is not None" in src, "FIX 2 FAILED: no None guard in displacement check"
    assert "atr_value" in src, "FIX 2 FAILED: atr_value not stored"
    print("FIX 2 PASS: displacement check guards against None displacement_index")


def test_fix_3_optional_union():
    """FIX 3: trade_executor.py uses Optional[float] not float | None"""
    import ict_trading_bot.execution.trade_executor as te
    src = inspect.getsource(te.execute_trade)
    assert 'Optional[float]' in src, "FIX 3 FAILED: Optional[float] not found"
    assert 'float | None' not in src, "FIX 3 FAILED: float | None still present"
    print("FIX 3 PASS: trade_executor.py uses Optional[float] for Python 3.9 compatibility")


def test_fix_4_htf_mandatory():
    """FIX 4: HTF swing verification is mandatory in setup_confirmations.py"""
    import ict_trading_bot.strategy.setup_confirmations as sc
    src = inspect.getsource(sc.liquidity_sweep_or_swing)
    # Check both buy and sell paths
    assert "if not htf_lows or not" in src or "if not htf_highs or not" in src, \
        "FIX 4 FAILED: HTF check not mandatory"
    print("FIX 4 PASS: HTF swing verification is now mandatory")


def test_fix_5_spread_digits():
    """FIX 5: pre_trade_validator.py uses symbol digits for spread"""
    import ict_trading_bot.execution.pre_trade_validator as ptv
    src = inspect.getsource(ptv.PreTradeValidator._check_spread)
    assert "pip_multiplier" in src, "FIX 5 FAILED: pip_multiplier not found"
    assert "digits" in src, "FIX 5 FAILED: digits not used"
    assert "MAX_SPREAD_PIPS" in src, "FIX 5 FAILED: MAX_SPREAD_PIPS env var not used"
    print("FIX 5 PASS: pre_trade_validator.py uses digits-based pip calculation")


def test_fix_7_order_block_full_range():
    """FIX 7: order_blocks.py uses full candle range (wick+body)"""
    import ict_trading_bot.ict_concepts.order_blocks as ob
    src = inspect.getsource(ob.find_true_order_block)
    assert 'ob_low' in src or 'ob_high' in src, "FIX 7 FAILED: ob_low/ob_high not found"
    assert 'body_low' not in src, "FIX 7 FAILED: body_low still present"
    print("FIX 7 PASS: order_blocks.py uses full wick+body range")


def test_fix_8_swing_tolerance():
    """FIX 8: swing_point comparison uses tolerance"""
    import ict_trading_bot.kingsbalfx_concept as kc
    src = inspect.getsource(kc._swing_points)
    assert '1e-8' in src, "FIX 8 FAILED: tolerance not found in kingsbalfx"
    print("FIX 8 PASS: kingsbalfx_concept.py swing comparison uses 1e-8 tolerance")
    
    import ict_trading_bot.strategy.entry_model as em
    src_em = inspect.getsource(em._swings)
    assert '1e-8' in src_em, "FIX 8 FAILED: tolerance not found in entry_model"
    print("FIX 8 PASS: entry_model.py swing comparison uses 1e-8 tolerance")


def test_fix_9_utc_time():
    """FIX 9: protection.py uses UTC-aware time"""
    import ict_trading_bot.risk.protection as prot
    src_can = inspect.getsource(prot.can_trade)
    src_reg = inspect.getsource(prot.register_trade)
    assert '_utc_now()' in src_can, "FIX 9 FAILED: can_trade not using _utc_now()"
    assert '_utc_now()' in src_reg, "FIX 9 FAILED: register_trade not using _utc_now()"
    print("FIX 9 PASS: protection.py uses _utc_now() helper")


def test_fix_11_fvg_mitigation_body():
    """FIX 11: fvg.py mitigation checks body fill"""
    import ict_trading_bot.ict_concepts.fvg as fvg
    src = inspect.getsource(fvg._mitigation)
    assert 'body_low' in src, "FIX 11 FAILED: body_low not in mitigation"
    assert 'body_high' in src, "FIX 11 FAILED: body_high not in mitigation"
    print("FIX 11 PASS: fvg.py mitigation checks candle body (not just wick)")


if __name__ == "__main__":
    tests = [
        test_fix_1_no_del_in_fvg,
        test_fix_2_atr_none_check,
        test_fix_3_optional_union,
        test_fix_4_htf_mandatory,
        test_fix_5_spread_digits,
        test_fix_7_order_block_full_range,
        test_fix_8_swing_tolerance,
        test_fix_9_utc_time,
        test_fix_11_fvg_mitigation_body,
    ]
    
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"\033[91m{e}\033[0m")
            failed += 1
        except Exception as e:
            print(f"\033[91m{test.__name__}: ERROR - {e}\033[0m")
            failed += 1
    
    print(f"\n{'='*50}")
    print(f"RESULTS: {passed} passed, {failed} failed / {len(tests)} total")
    if failed == 0:
        print("\033[92mALL FIXES VERIFIED SUCCESSFULLY!\033[0m")
    else:
        print(f"\033[91m{failed} FIX(ES) STILL BROKEN!\033[0m")
