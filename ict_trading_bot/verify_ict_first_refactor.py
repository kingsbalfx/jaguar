"""
ICT-First Refactor Verification Script
========================================
Run this script to verify all changes are working correctly.

Usage:
    python verify_ict_first_refactor.py
"""

import sys
from datetime import datetime
import pytz

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(text):
    print(f"\n{BLUE}{'=' * 70}{RESET}")
    print(f"{BLUE}{text.center(70)}{RESET}")
    print(f"{BLUE}{'=' * 70}{RESET}\n")

def print_check(passed, message):
    symbol = f"{GREEN}✓{RESET}" if passed else f"{RED}✗{RESET}"
    color = GREEN if passed else RED
    print(f"{symbol} {color}{message}{RESET}")

def print_info(message):
    print(f"{YELLOW}ℹ {message}{RESET}")

def main():
    print_header("ICT-First Refactor Verification")
    
    total_checks = 0
    passed_checks = 0
    
    # ============================================
    # 1. CHECK KILL ZONE RESTRICTIONS
    # ============================================
    print_header("1. Kill Zone Restrictions")
    try:
        from utils.sessions import in_london_session, in_newyork_session, _hour
        
        # Test various hours
        test_hours = [
            (8, True, "London Kill Zone"),
            (13, True, "NY Kill Zone"),
            (11, False, "Between sessions"),
            (20, False, "After hours"),
            (5, False, "Early morning")
        ]
        
        for hour, should_be_active, description in test_hours:
            total_checks += 1
            # Create mock datetime for testing
            test_time = datetime.now(pytz.UTC).replace(hour=hour, minute=0)
            is_london = in_london_session(test_time)
            is_ny = in_newyork_session(test_time)
            is_active = is_london or is_ny
            
            if is_active == should_be_active:
                passed_checks += 1
                print_check(True, f"Hour {hour:02d}:00 UTC - {description}: {'ACTIVE' if is_active else 'INACTIVE'}")
            else:
                print_check(False, f"Hour {hour:02d}:00 UTC - {description}: Expected {'ACTIVE' if should_be_active else 'INACTIVE'}, got {'ACTIVE' if is_active else 'INACTIVE'}")
        
        # Check current time
        current_hour = _hour()
        is_london_now = in_london_session()
        is_ny_now = in_newyork_session()
        print_info(f"Current UTC hour: {current_hour:02d}:00 - London: {is_london_now}, NY: {is_ny_now}")
        
    except Exception as e:
        print_check(False, f"Kill Zone check failed: {e}")
    
    # ============================================
    # 2. CHECK ICT-FIRST MODULE EXISTS
    # ============================================
    print_header("2. ICT-First Module")
    try:
        from strategy.ict_first_execution import (
            check_ict_core_rules,
            should_override_with_ict_first,
            calculate_ict_first_confidence,
            get_ict_first_execution_details
        )
        
        total_checks += 1
        passed_checks += 1
        print_check(True, "ICT-first execution module loaded successfully")
        
        # Test with sample data
        sample_data = {
            "liquidity_sweep": True,
            "smt_divergence": 0.8,
            "bos": True,
            "fvgs": [{"low": 1.0, "high": 1.1}],
            "displacement": 0.7
        }
        
        total_checks += 1
        rules_met, breakdown = check_ict_core_rules(sample_data, "EURUSD")
        
        if breakdown:
            passed_checks += 1
            print_check(True, f"ICT core rules check functional - {breakdown}")
            
            # Test confidence calculation
            total_checks += 1
            confidence = calculate_ict_first_confidence(breakdown)
            if 0 <= confidence <= 100:
                passed_checks += 1
                print_check(True, f"Confidence calculation: {confidence:.1f}/100")
            else:
                print_check(False, f"Confidence out of range: {confidence}")
        else:
            print_check(False, "ICT core rules check returned invalid data")
            
    except Exception as e:
        print_check(False, f"ICT-first module check failed: {e}")
    
    # ============================================
    # 3. CHECK SMT WEIGHT IN INTELLIGENCE SYSTEM
    # ============================================
    print_header("3. SMT Primary Filter Weight")
    try:
        import re
        with open("ict_trading_bot/risk/intelligence_system.py", "r") as f:
            content = f.read()
        
        total_checks += 1
        # Look for SMT weight of 0.30
        if 'details["smt_divergence"] * 0.30' in content:
            passed_checks += 1
            print_check(True, "SMT divergence weighted at 30% (PRIMARY)")
        else:
            print_check(False, "SMT divergence weight not found at 30%")
        
        # Check that judas_swing is removed/zeroed
        total_checks += 1
        if 'details["judas_swing_context"] * 0.00' in content or 'judas_swing_context"] * 0.0' in content:
            passed_checks += 1
            print_check(True, "Judas swing context weight removed (0%)")
        else:
            print_check(False, "Judas swing context not properly removed")
            
    except Exception as e:
        print_check(False, f"SMT weight check failed: {e}")
    
    # ============================================
    # 4. CHECK PENALTY CAP IN ENTRY MODEL
    # ============================================
    print_header("4. Penalty Cap System")
    try:
        with open("ict_trading_bot/strategy/entry_model.py", "r") as f:
            content = f.read()
        
        total_checks += 1
        if 'min(60.0,' in content or 'min(60,' in content:
            passed_checks += 1
            print_check(True, "Penalty cap set to 60")
        else:
            print_check(False, "Penalty cap not found at 60")
        
        total_checks += 1
        if 'critical_penalties * 0.6' in content and 'supportive_penalties * 0.4' in content:
            passed_checks += 1
            print_check(True, "Weighted penalty system implemented")
        else:
            print_check(False, "Weighted penalty system not found")
            
    except Exception as e:
        print_check(False, f"Penalty cap check failed: {e}")
    
    # ============================================
    # 5. CHECK HYBRID DECISION INTEGRATION
    # ============================================
    print_header("5. Hybrid Decision Integration")
    try:
        with open("ict_trading_bot/main.py", "r") as f:
            content = f.read()
        
        total_checks += 1
        if 'from strategy.ict_first_execution import should_override_with_ict_first' in content:
            passed_checks += 1
            print_check(True, "ICT-first import added to main.py")
        else:
            print_check(False, "ICT-first import not found in main.py")
        
        total_checks += 1
        if 'if ict_override:' in content and 'decision_source = "ict_first_override"' in content:
            passed_checks += 1
            print_check(True, "ICT-first override logic integrated")
        else:
            print_check(False, "ICT-first override logic not properly integrated")
        
        total_checks += 1
        if 'engine_agreement = "ict_rules_satisfied"' in content:
            passed_checks += 1
            print_check(True, "ICT rules satisfaction engine agreement added")
        else:
            print_check(False, "ICT rules satisfaction not found")
            
        total_checks += 1
        if 'ict_first_override(confidence=100%' in content:
            passed_checks += 1
            print_check(True, "ICT-first 100% confidence logging added")
        else:
            print_check(False, "ICT-first confidence logging not found")
            
    except Exception as e:
        print_check(False, f"Hybrid decision check failed: {e}")
    
    # ============================================
    # 6. SUMMARY
    # ============================================
    print_header("Verification Summary")
    
    percentage = (passed_checks / total_checks * 100) if total_checks > 0 else 0
    color = GREEN if percentage >= 90 else YELLOW if percentage >= 70 else RED
    
    print(f"Total Checks: {total_checks}")
    print(f"Passed: {color}{passed_checks}{RESET}")
    print(f"Failed: {RED}{total_checks - passed_checks}{RESET}")
    print(f"Success Rate: {color}{percentage:.1f}%{RESET}\n")
    
    if percentage == 100:
        print(f"{GREEN}✓ All checks passed! Refactor is complete and ready for testing.{RESET}")
        return 0
    elif percentage >= 90:
        print(f"{YELLOW}⚠ Most checks passed. Review failed checks before deployment.{RESET}")
        return 0
    else:
        print(f"{RED}✗ Multiple checks failed. Review the refactor implementation.{RESET}")
        return 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        print(f"{RED}FATAL ERROR: {e}{RESET}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
