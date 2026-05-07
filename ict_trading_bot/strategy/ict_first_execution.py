"""
ICT-First Execution Logic
=========================
PRIORITY OVERRIDE when core ICT rules are satisfied:

If ALL core conditions are met, execute immediately with 100% confidence:
1. Liquidity Sweep confirmed
2. SMT Divergence detected (PRIMARY filter)
3. Market Structure Shift (BOS/MSS)
4. FVG or Order Block entry zone
5. Within Kill Zone (London 07:00-10:00 UTC or NY 12:00-15:00 UTC)

This bypasses weighted scoring, penalty systems, and module disagreement.

PURPOSE: Remove over-filtering that prevents valid ICT setups from executing.
"""

import logging
from typing import Dict, Optional, Tuple
from utils.sessions import in_london_session, in_newyork_session

logger = logging.getLogger(__name__)


def check_ict_core_rules(data: Dict, symbol: str) -> Tuple[bool, Dict]:
    """
    Check if ALL core ICT rules are satisfied.
    
    Returns:
        (ict_rules_met: bool, breakdown: dict with individual checks)
    """
    breakdown = {
        "liquidity_sweep": False,
        "smt_divergence": False,
        "market_structure_shift": False,
        "entry_zone": False,
        "kill_zone": False,
        "displacement": False,
        "all_rules_met": False
    }
    
    try:
        # 1. Liquidity Sweep
        liquidity_sweep = data.get("liquidity_sweep", False) or data.get("liq", False)
        breakdown["liquidity_sweep"] = bool(liquidity_sweep)
        
        # 2. SMT Divergence (PRIMARY FILTER)
        smt_score = float(data.get("smt_divergence", 0.0) or 0.0)
        smt_confirmed = data.get("smt_confirmed", False)
        breakdown["smt_divergence"] = bool(smt_score >= 0.7 or smt_confirmed)
        
        # 3. Market Structure Shift (BOS/MSS)
        bos = data.get("bos", False) or data.get("break_of_structure", False)
        mss = data.get("mss", False) or data.get("market_structure_shift", False)
        breakdown["market_structure_shift"] = bool(bos or mss)
        
        # 4. Entry Zone (FVG or Order Block)
        fvg = data.get("fvg") or (data.get("fvgs") and len(data.get("fvgs", [])) > 0)
        ob = data.get("htf_ob") or (data.get("htf_order_blocks") and len(data.get("htf_order_blocks", [])) > 0)
        breakdown["entry_zone"] = bool(fvg or ob)
        
        # 5. Kill Zone timing
        is_london = in_london_session()
        is_ny = in_newyork_session()
        breakdown["kill_zone"] = bool(is_london or is_ny)
        
        # 6. Displacement (optional but strong signal)
        displacement = float(data.get("displacement", 0.0) or 0.0)
        breakdown["displacement"] = bool(displacement >= 0.60)
        
        # ALL CORE RULES MUST BE MET
        breakdown["all_rules_met"] = all([
            breakdown["liquidity_sweep"],
            breakdown["smt_divergence"],
            breakdown["market_structure_shift"],
            breakdown["entry_zone"],
            breakdown["kill_zone"]
        ])
        
        return breakdown["all_rules_met"], breakdown
        
    except Exception as e:
        logger.error(f"ICT core rules check error: {e}")
        return False, breakdown


def should_override_with_ict_first(data: Dict, symbol: str, weighted_decision: str, 
                                     intelligence_decision: str, classic_decision: bool) -> Tuple[bool, Dict]:
    """
    Determine if ICT-first rules should override module decisions.
    
    If core ICT rules are met, override any SKIP/REJECT decisions.
    
    Returns:
        (should_override: bool, override_details: dict)
    """
    ict_rules_met, breakdown = check_ict_core_rules(data, symbol)
    
    override_details = {
        "ict_rules_met": ict_rules_met,
        "breakdown": breakdown,
        "override_applied": False,
        "reason": None,
        "confidence": 0.0
    }
    
    if not ict_rules_met:
        override_details["reason"] = "ICT core rules not fully satisfied"
        return False, override_details
    
    # If ICT rules met, check if any module is blocking execution
    weighted_blocking = weighted_decision in ["skip", "SKIP", "WATCH"]
    intelligence_blocking = intelligence_decision in ["SKIP", "AVOID", "WAIT"]
    classic_blocking = not classic_decision
    
    any_module_blocking = weighted_blocking or intelligence_blocking or classic_blocking
    
    if ict_rules_met and any_module_blocking:
        override_details["override_applied"] = True
        override_details["confidence"] = 100.0  # ICT rules met = 100% confidence
        override_details["reason"] = (
            f"ICT core rules satisfied - overriding module disagreement. "
            f"Liquidity Sweep + SMT + MSS + Entry Zone + Kill Zone = EXECUTE"
        )
        
        logger.info(f"[ICT-FIRST OVERRIDE] {symbol}: {override_details['reason']}")
        logger.info(f"[ICT-FIRST BREAKDOWN] {breakdown}")
        
        return True, override_details
    
    elif ict_rules_met:
        # All modules agree and ICT rules met - amplify confidence
        override_details["override_applied"] = True
        override_details["confidence"] = 100.0
        override_details["reason"] = "ICT core rules + all modules agree = maximum confidence"
        return True, override_details
    
    return False, override_details


def calculate_ict_first_confidence(breakdown: Dict) -> float:
    """
    Calculate confidence based on ICT rule satisfaction.
    
    Returns 0-100 confidence score.
    """
    if breakdown.get("all_rules_met"):
        return 100.0
    
    # Partial scoring if not all rules met
    score = 0.0
    if breakdown.get("liquidity_sweep"):
        score += 20.0
    if breakdown.get("smt_divergence"):
        score += 30.0  # SMT is PRIMARY - highest weight
    if breakdown.get("market_structure_shift"):
        score += 20.0
    if breakdown.get("entry_zone"):
        score += 15.0
    if breakdown.get("kill_zone"):
        score += 10.0
    if breakdown.get("displacement"):
        score += 5.0
    
    return min(100.0, score)


def get_ict_first_execution_details(data: Dict, symbol: str) -> Dict:
    """
    Get complete ICT-first execution analysis for logging/debugging.
    """
    ict_rules_met, breakdown = check_ict_core_rules(data, symbol)
    confidence = calculate_ict_first_confidence(breakdown)
    
    return {
        "ict_rules_met": ict_rules_met,
        "confidence": confidence,
        "breakdown": breakdown,
        "execution_decision": "EXECUTE_FULL" if ict_rules_met else "INSUFFICIENT",
        "timestamp": data.get("timestamp"),
        "symbol": symbol
    }
