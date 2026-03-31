#!/usr/bin/env python3
"""
OPTION 2: Confidence Bottleneck Diagnostic Script

Run this script to diagnose why confidence scores are stuck at ~57%
and find the exact bottleneck in your entry model.

Usage:
    python diagnose_confidence.py              # Diagnose all symbols
    python diagnose_confidence.py EURUSD       # Diagnose specific symbol
    python diagnose_confidence.py EURUSD GBPUSD USDJPY  # Multiple symbols
"""

import sys
from risk.intelligent_execution import diagnose_confidence_bottleneck, diagnose_all_symbols

def main():
    print("\n" + "=" * 100)
    print("[OPTION 2: CONFIDENCE BOTTLENECK DIAGNOSIS]")
    print("=" * 100)
    
    if len(sys.argv) > 1:
        # Diagnose specific symbols
        symbols = sys.argv[1:]
        print(f"\nDiagnosing {len(symbols)} symbol(s)...\n")
        
        for symbol in symbols:
            diagnosis = diagnose_confidence_bottleneck(symbol)
            
            print(f"\n{'=' * 80}")
            print(f"SYMBOL: {diagnosis['symbol']}")
            print(f"{'=' * 80}")
            print(f"Max Confidence:    {diagnosis['max_observed']:.0%}")
            print(f"Avg Confidence:    {diagnosis['avg_observed']:.0%}")
            print(f"Min Confidence:    {diagnosis['min_observed']:.0%}")
            print(f"Required:          {diagnosis['required_threshold']:.0%}")
            print(f"Gap:               {diagnosis['gap']:.0%}")
            print(f"Total Skips:       {diagnosis['skip_count']}")
            
            if diagnosis['skip_reason_breakdown']:
                print(f"\nTop Skip Reasons:")
                for reason, count in sorted(diagnosis['skip_reason_breakdown'].items(), key=lambda x: x[1], reverse=True):
                    print(f"  - {reason}: {count}")
            
            print(f"\nRecommendations:")
            for rec in diagnosis['recommendations']:
                print(f"  {rec}")
            
            if diagnosis['full_analysis']:
                print(f"\nRecent Attempts (last 3):")
                for entry in diagnosis['full_analysis'][-3:]:
                    print(f"  Attempt {entry['attempt']}: {entry['confidence']} ({entry['reason']})")
                    for factor in entry['factors']:
                        print(f"    → {factor}")
    else:
        # Diagnose all symbols
        report = diagnose_all_symbols()
        print(report)
    
    print("\n" + "=" * 100)
    print("[END DIAGNOSIS]")
    print("=" * 100 + "\n")
    print("Next Steps:")
    print("1. Look at TOP SKIP REASONS - that's your bottleneck")
    print("2. If 'intelligence': Confidence calculation is too conservative")
    print("3. If 'confirmation_score': Entry requirements too strict")
    print("4. If 'entry_fib_zone': Entry zone/fibonacci not aligning")
    print("\n")

if __name__ == "__main__":
    main()
