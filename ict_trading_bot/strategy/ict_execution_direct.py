"""
Direct ICT/SMT Execution - NO SCORING
======================================
When ICT or SMT setups are FULLY satisfied, execute DIRECTLY.
NO scoring, NO penalties, NO complex validation.

DIRECT EXECUTION TRIGGERS:

1. FULL ICT SETUP:
   - Liquidity Sweep ✓
   - BOS/MSS ✓
   - FVG ✓
   - Displacement ✓
   → EXECUTE IMMEDIATELY

2. FULL SMT DIVERGENCE:
   - SMT confirmed on correlated pair ✓
   - Trend direction clear ✓
   - Structure shift ✓
   → EXECUTE IMMEDIATELY

3. SWEET ZONE:
   - Pure trend continuation ✓
   - No pullback needed ✓
   → EXECUTE IMMEDIATELY

4. JUDAS SWING:
   - Price purge confirmed ✓
   - Strong reversal ✓
   → EXECUTE IMMEDIATELY

For ALL OTHER setups → Use normal scoring/validation
"""

from typing import Dict, Tuple
from ict_concepts.sweet_zone import detect_sweet_zone, should_enter_on_continuation
from ict_concepts.judas_swing import detect_judas_swing, should_enter_on_judas_reversal
from ict_concepts.fvg_encroachment import is_price_encroaching_fvg, check_fvg_fill_consequence
from ict_concepts.fib_visual import get_visual_entry_zones
from utils.sessions import in_london_session, in_newyork_session
import logging

logger = logging.getLogger(__name__)


def check_direct_execution_triggers(data: Dict, symbol: str, candles: list = None) -> Tuple[bool, Dict]:
    """
    Check if ANY direct execution trigger is satisfied.
    Returns (should_execute_directly, execution_details)
    
    Direct execution = 100% confidence, bypass all other checks
    """
    
    # 1. Check FULL ICT SETUP (original logic)
    full_ict, ict_details = _check_full_ict_setup(data)
    if full_ict:
        return True, {
            "trigger": "FULL_ICT_SETUP",
            "confidence": 100,
            "details": ict_details,
            "reason": "All ICT core rules satisfied - DIRECT EXECUTION"
        }
    
    # 2. Check FULL SMT DIVERGENCE
    full_smt, smt_details = _check_full_smt_setup(data)
    if full_smt:
        return True, {
            "trigger": "FULL_SMT_DIVERGENCE",
            "confidence": 100,
            "details": smt_details,
            "reason": "SMT divergence fully confirmed - DIRECT EXECUTION"
        }
    
    # 3. Check SWEET ZONE
    if candles:
        trend = data.get("trend", "").lower()
        sweet_zone = detect_sweet_zone(candles, trend)
        if sweet_zone.get("in_sweet_zone"):
            price = data.get("price", 0)
            structure_level = data.get("structure_level")
            if should_enter_on_continuation(sweet_zone, price, structure_level):
                return True, {
                    "trigger": "SWEET_ZONE_CONTINUATION",
                    "confidence": 100,
                    "details": sweet_zone,
                    "reason": f"Sweet Zone: {sweet_zone.get('reason')} - DIRECT EXECUTION"
                }
    
    # 4. Check JUDAS SWING
    if candles:
        judas_swing = detect_judas_swing(candles, symbol)
        if judas_swing.get("is_judas_swing") and judas_swing.get("purge_confirmed"):
            price = data.get("price", 0)
            if should_enter_on_judas_reversal(judas_swing, price):
                return True, {
                    "trigger": "JUDAS_SWING_REVERSAL",
                    "confidence": 100,
                    "details": judas_swing,
                    "reason": f"Judas Swing: Purged {judas_swing.get('purge_type')} - DIRECT EXECUTION"
                }
    
    # NO direct execution trigger - use normal scoring
    return False, {
        "trigger": None,
        "confidence": 0,
        "reason": "No direct execution trigger - proceed to normal validation"
    }


def _check_full_ict_setup(data: Dict) -> Tuple[bool, Dict]:
    """
    Check if FULL ICT setup is present (all core rules).
    If YES → Execute directly, no scoring needed.
    """
    checklist = {
        "liquidity_sweep": False,
        "bos_mss": False,
        "fvg": False,
        "displacement": False,
        "kill_zone": False
    }
    
    # 1. Liquidity Sweep
    liq = data.get("liquidity_sweep", False) or data.get("liq", False)
    checklist["liquidity_sweep"] = bool(liq)
    
    # 2. BOS/MSS
    bos = data.get("bos", False) or data.get("break_of_structure", False)
    mss = data.get("mss", False) or data.get("market_structure_shift", False)
    checklist["bos_mss"] = bool(bos or mss)
    
    # 3. FVG
    fvg = data.get("fvg") or (data.get("fvgs") and len(data.get("fvgs", [])) > 0)
    checklist["fvg"] = bool(fvg)
    
    # 4. Displacement
    displacement = float(data.get("displacement", 0.0) or 0.0)
    checklist["displacement"] = displacement >= 0.60
    
    # 5. Kill Zone
    is_london = in_london_session()
    is_ny = in_newyork_session()
    checklist["kill_zone"] = bool(is_london or is_ny)
    
    # ALL must be satisfied for direct execution
    all_satisfied = all(checklist.values())
    
    return all_satisfied, checklist


def _check_full_smt_setup(data: Dict) -> Tuple[bool, Dict]:
    """
    Check if FULL SMT setup is present.
    If YES → Execute directly, no scoring needed.
    """
    checklist = {
        "smt_divergence": False,
        "trend_clear": False,
        "structure_shift": False
    }
    
    # 1. SMT Divergence
    smt_score = float(data.get("smt_divergence", 0.0) or 0.0)
    smt_confirmed = data.get("smt_confirmed", False)
    checklist["smt_divergence"] = bool(smt_score >= 0.8 or smt_confirmed)
    
    # 2. Trend Clear
    trend = data.get("trend", "").lower()
    checklist["trend_clear"] = trend in ["bullish", "bearish", "buy", "sell"]
    
    # 3. Structure Shift
    bos = data.get("bos", False) or data.get("break_of_structure", False)
    mss = data.get("mss", False) or data.get("market_structure_shift", False)
    checklist["structure_shift"] = bool(bos or mss)
    
    # ALL must be satisfied for direct SMT execution
    all_satisfied = all(checklist.values())
    
    return all_satisfied, checklist


def get_direct_execution_summary(data: Dict, symbol: str, candles: list = None) -> str:
    """
    Generate a summary of available direct execution paths.
    """
    should_execute, details = check_direct_execution_triggers(data, symbol, candles)
    
    if should_execute:
        trigger = details.get("trigger")
        reason = details.get("reason")
        return f"✓ DIRECT EXECUTION: {trigger} - {reason}"
    else:
        # Check what's missing
        full_ict, ict_check = _check_full_ict_setup(data)
        full_smt, smt_check = _check_full_smt_setup(data)
        
        missing_ict = [k for k, v in ict_check.items() if not v]
        missing_smt = [k for k, v in smt_check.items() if not v]
        
        return (
            f"⊘ No direct execution trigger. "
            f"ICT missing: {', '.join(missing_ict) if missing_ict else 'None'}. "
            f"SMT missing: {', '.join(missing_smt) if missing_smt else 'None'}. "
            f"Proceeding to normal validation."
        )
