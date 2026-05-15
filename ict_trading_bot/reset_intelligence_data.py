"""
Reset Intelligence Data Utility
================================
Resets all intelligence tracking data to zero.
Removes blacklisting and skip records.

Usage:
    python reset_intelligence_data.py [--confirm]
"""

import os
import json
import glob
from pathlib import Path

def reset_intelligence_files():
    """Reset all intelligence tracking JSON files"""
    data_dir = Path(__file__).parent / "data"
    
    if not data_dir.exists():
        print("✓ Data directory doesn't exist, nothing to reset")
        return
    
    # Files to reset
    patterns = [
        "intelligent_skip_tracking*.json",
        "intelligent_execution_stats*.json",
        "cis_decisions_history*.json",
        "symbol_confidence_runtime*.json",
        "symbol_stats*.json",
        "strategy_memory*.json"
    ]
    
    reset_count = 0
    for pattern in patterns:
        for file_path in data_dir.glob(pattern):
            # Skip tmp files
            if ".tmp" in str(file_path):
                continue
                
            try:
                # Reset to empty dict or appropriate structure
                with open(file_path, 'w') as f:
                    json.dump({}, f, indent=2)
                print(f"✓ Reset: {file_path.name}")
                reset_count += 1
            except Exception as e:
                print(f"✗ Failed to reset {file_path.name}: {e}")
    
    # Clean up tmp files
    tmp_count = 0
    for tmp_file in data_dir.glob("*.tmp"):
        try:
            tmp_file.unlink()
            tmp_count += 1
        except:
            pass
    
    if tmp_count > 0:
        print(f"✓ Removed {tmp_count} temporary files")
    
    print(f"\n✓ Reset {reset_count} intelligence data files")
    print("✓ All skip records cleared")
    print("✓ All blacklisting removed")
    print("✓ Intelligence system reset to zero")

if __name__ == "__main__":
    import sys
    
    if "--confirm" not in sys.argv:
        print("=" * 70)
        print("WARNING: This will reset ALL intelligence data!")
        print("=" * 70)
        print("\nThis will:")
        print("  - Clear all skip tracking records")
        print("  - Remove symbol blacklisting")
        print("  - Reset execution statistics")
        print("  - Clear strategy memory")
        print("  - Reset confidence tracking")
        print("\nRe-run with --confirm flag to proceed:")
        print("  python reset_intelligence_data.py --confirm")
        sys.exit(0)
    
    print("\nResetting intelligence data...\n")
    reset_intelligence_files()
    print("\n✓ Intelligence system reset complete!")
