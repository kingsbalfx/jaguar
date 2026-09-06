#!/usr/bin/env python3
"""
Quick startup script for ICT Trading Bot.
Validates configuration and starts the bot with proper error handling.

Usage:
    python quick_start.py
    
First run:
    1. python configure_credentials.py  (optional, for Supabase)
    2. python quick_start.py
"""

import os
import sys
import time
import subprocess
from pathlib import Path

def print_banner():
    """Print startup banner."""
    print("\n" + "="*70)
    print("  ICT TRADING BOT - QUICK START")
    print("="*70 + "\n")

def check_prerequisites():
    """Check if bot can start."""
    print("Checking prerequisites...\n")
    
    # Check Python version
    if sys.version_info < (3, 9):
        print(f"❌ Python 3.9+ required, found {sys.version_info.major}.{sys.version_info.minor}")
        return False
    print("✅ Python version OK")
    
    # Check for virtual environment
    in_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    if in_venv:
        print("✅ Running in virtual environment")
    else:
        print("⚠️  Not in virtual environment (recommended to use .venv)")
    
    # Check for main.py
    if not Path("main.py").exists():
        print("❌ main.py not found. Please run from bot directory.")
        return False
    print("✅ main.py found")
    
    # Check for required packages
    try:
        import MetaTrader5
        import supabase
        import dotenv
        import requests
        import flask
        print("✅ Required packages installed")
    except ImportError as e:
        print(f"❌ Missing package: {e}")
        print("   Run: pip install -r requirements.txt")
        return False
    
    return True

def load_credentials():
    """Load credentials from local storage."""
    print("Loading credentials...\n")
    
    from dotenv import load_dotenv
    load_dotenv()
    
    from config.credentials import get_supabase_credentials, load_credentials as load_local
    
    # Check if credentials are available
    url, key = get_supabase_credentials()
    
    if url and key:
        print("✅ Supabase credentials found")
        return True
    
    local = load_local()
    if local:
        print("✅ Local credentials loaded")
        return True
    
    print("⚠️  No Supabase credentials configured")
    print("   Bot will run in local-only mode")
    print("   To enable cloud features, run: python configure_credentials.py\n")
    return True

def start_bot():
    """Start the bot."""
    print("="*70)
    print("  STARTING BOT")
    print("="*70 + "\n")
    
    try:
        # Start main.py in the current process
        subprocess.run(
            [sys.executable, "main.py"],
            check=False
        )
    except KeyboardInterrupt:
        print("\n\n⚠️  Bot stopped by user")
        return False
    except Exception as e:
        print(f"\n❌ Error starting bot: {e}")
        return False
    
    return True

def show_recovery_options():
    """Show recovery options if startup failed."""
    print("\n" + "="*70)
    print("  TROUBLESHOOTING")
    print("="*70 + "\n")
    
    print("If the bot fails to start, try:\n")
    
    print("1. Check health status:")
    print("   python check_bot_health.py\n")
    
    print("2. Configure credentials:")
    print("   python configure_credentials.py\n")
    
    print("3. Check the logs:")
    print("   Get-Content bot.log -Tail 100\n")
    
    print("4. Enable debug logging:")
    print("   Set LOG_LEVEL=DEBUG in .env\n")
    
    print("5. Verify MT5 is running and connected\n")
    
    print("For more help, see:")
    print("   SETUP_CREDENTIALS_GUIDE.md")
    print("   README.md\n")

def main():
    """Main entry point."""
    print_banner()
    
    # Check prerequisites
    if not check_prerequisites():
        print("\n❌ Prerequisites not met. Cannot start bot.")
        show_recovery_options()
        return 1
    
    # Load credentials
    if not load_credentials():
        print("\n❌ Failed to load credentials.")
        show_recovery_options()
        return 1
    
    # Start the bot
    print("\n")
    if start_bot():
        print("\n✅ Bot completed successfully")
        return 0
    else:
        print("\n❌ Bot failed to start or exited with error")
        show_recovery_options()
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
