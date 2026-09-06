#!/usr/bin/env python3
"""
Bot Health Check - Validates bot configuration and connectivity before running.
Run this before starting main.py to ensure everything is properly configured.

Usage:
    python check_bot_health.py
"""

import os
import sys
from pathlib import Path
from typing import Tuple, List

def print_check(status: str, message: str):
    """Print a check result."""
    symbols = {"✅": "✅", "❌": "❌", "⚠️": "⚠️", "ℹ️": "ℹ️"}
    print(f"{symbols.get(status, status)} {message}")

def check_venv():
    """Check if running in virtual environment."""
    in_venv = hasattr(sys, 'real_prefix') or (
        hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
    )
    if in_venv:
        print_check("✅", f"Running in virtual environment: {sys.prefix}")
        return True
    else:
        print_check("⚠️", "Not running in virtual environment (recommended but not required)")
        return True

def check_python_version():
    """Check Python version."""
    version = sys.version_info
    if version.major == 3 and version.minor >= 9:
        print_check("✅", f"Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print_check("❌", f"Python 3.9+ required, found {version.major}.{version.minor}")
        return False

def check_env_file():
    """Check if .env file exists."""
    env_file = Path.cwd() / ".env"
    if env_file.exists():
        print_check("✅", f".env file found")
        return True
    else:
        print_check("⚠️", ".env file not found (using environment variables)")
        return True

def check_imports():
    """Check if required packages are installed."""
    required_packages = [
        ('MetaTrader5', 'MetaTrader5'),
        ('dotenv', 'python-dotenv'),
        ('supabase', 'supabase'),
        ('requests', 'requests'),
        ('flask', 'Flask'),
        ('psutil', 'psutil'),
    ]
    
    all_ok = True
    for module_name, package_name in required_packages:
        try:
            __import__(module_name)
            print_check("✅", f"{package_name} installed")
        except ImportError:
            print_check("❌", f"{package_name} NOT installed")
            all_ok = False
    
    return all_ok

def check_config_files():
    """Check for required configuration files."""
    required_files = [
        "config/trading_pairs.py",
        "config/credentials.py",
        "config/symbol_mappings.py",
        "execution/mt5_connector.py",
        "risk/protection.py",
        "risk/mirror_trading.py",
        "dashboard/bridge.py",
    ]
    
    all_ok = True
    for file_path in required_files:
        full_path = Path.cwd() / file_path
        if full_path.exists():
            print_check("✅", f"Found {file_path}")
        else:
            print_check("❌", f"Missing {file_path}")
            all_ok = False
    
    return all_ok

def check_directories():
    """Check if required directories exist."""
    dirs = ["config", "execution", "risk", "dashboard", "data", "logs"]
    all_ok = True
    for dir_name in dirs:
        dir_path = Path.cwd() / dir_name
        if dir_path.exists():
            print_check("✅", f"Directory {dir_name}/ exists")
        else:
            print_check("⚠️", f"Directory {dir_name}/ doesn't exist (will be created if needed)")
    
    return all_ok

def check_supabase_credentials() -> Tuple[bool, str]:
    """Check Supabase credential configuration."""
    from config.credentials import get_supabase_credentials, has_supabase_credentials
    
    if has_supabase_credentials():
        url, key = get_supabase_credentials()
        # Mask the credentials for security
        masked_url = url[:20] + "..." if len(url) > 20 else url
        masked_key = key[:10] + "..." if len(key) > 10 else key
        print_check("✅", f"Supabase configured: {masked_url}")
        
        # Try to validate credentials
        try:
            from supabase import create_client
            client = create_client(url, key)
            print_check("✅", "Supabase connection successful")
            return True, "connected"
        except Exception as e:
            print_check("⚠️", f"Supabase connection failed: {e}")
            print_check("ℹ️", "Bot will use local-only mode")
            return True, "local_only"
    else:
        print_check("ℹ️", "No Supabase credentials configured")
        print_check("ℹ️", "Bot will use local-only mode")
        return True, "local_only"

def check_mt5_setup():
    """Check MT5 configuration."""
    try:
        import MetaTrader5 as mt5
        print_check("✅", "MetaTrader5 module available")
        return True
    except ImportError:
        print_check("❌", "MetaTrader5 not installed (required for trading)")
        return False

def check_local_credentials():
    """Check local credential storage."""
    from config.credentials import CREDENTIALS_DIR, CREDENTIALS_FILE, load_credentials
    
    creds_dir = Path(CREDENTIALS_DIR)
    if creds_dir.exists():
        print_check("✅", f"Credential directory exists: {creds_dir}")
        
        if Path(CREDENTIALS_FILE).exists():
            creds = load_credentials()
            if creds:
                print_check("✅", "Local credentials file found and readable")
                return True
            else:
                print_check("ℹ️", "Local credentials file exists but is empty")
                return True
        else:
            print_check("ℹ️", "No local credentials file yet (can be created with configure_credentials.py)")
            return True
    else:
        print_check("ℹ️", "Credential directory doesn't exist yet (will be created on first save)")
        return True

def check_environment_variables():
    """Check important environment variables."""
    important_vars = [
        "SUPABASE_URL",
        "SUPABASE_KEY",
        "RISK_PER_TRADE",
        "MAX_OPEN_TRADES",
        "BOT_ENABLED",
        "MT5_PATH",
    ]
    
    found_count = 0
    for var in important_vars:
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if "KEY" in var or "PASSWORD" in var:
                masked = value[:5] + "..." if len(value) > 5 else value
            else:
                masked = value
            print_check("✅", f"{var}: {masked[:50]}")
            found_count += 1
        else:
            print_check("ℹ️", f"{var}: not set (will use default or local config)")
    
    return found_count > 0

def check_mirror_trading():
    """Check mirror trading configuration."""
    from config.credentials import load_credentials
    
    enabled = os.getenv("MIRROR_TRADING_ENABLED", "true").lower() in ("1", "true", "yes")
    if enabled:
        print_check("✅", "Mirror trading enabled")
        
        creds = load_credentials()
        if creds.get("mirror_enabled"):
            print_check("✅", "Mirror trading configured")
        else:
            print_check("⚠️", "Mirror trading not configured (can use configure_credentials.py)")
        
        return True
    else:
        print_check("ℹ️", "Mirror trading disabled")
        return True

def main():
    """Run all health checks."""
    print("\n" + "="*70)
    print(" ICT TRADING BOT - HEALTH CHECK")
    print("="*70 + "\n")
    
    checks = [
        ("Python Version", check_python_version),
        ("Virtual Environment", check_venv),
        ("Required Packages", check_imports),
        ("Config Files", check_config_files),
        ("Directories", check_directories),
        ("MT5 Setup", check_mt5_setup),
        ("Local Credentials", check_local_credentials),
        ("Supabase Credentials", lambda: check_supabase_credentials()[0]),
        ("Environment Variables", check_environment_variables),
        ("Mirror Trading", check_mirror_trading),
    ]
    
    results = []
    for check_name, check_func in checks:
        print(f"\n--- {check_name} ---")
        try:
            result = check_func()
            results.append((check_name, result))
        except Exception as e:
            print_check("❌", f"Check failed: {e}")
            results.append((check_name, False))
    
    print("\n" + "="*70)
    print(" SUMMARY")
    print("="*70 + "\n")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for check_name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {check_name}")
    
    print(f"\n{passed}/{total} checks passed\n")
    
    if passed == total:
        print_check("✅", "Bot is ready to start!")
        print("\nStart the bot with:")
        print("  python main.py")
        return 0
    elif passed >= total - 2:
        print_check("⚠️", "Some checks failed, but bot may still run")
        print("\nRecommendations:")
        for check_name, result in results:
            if not result:
                print(f"  • Fix: {check_name}")
        return 1
    else:
        print_check("❌", "Critical issues found. Please fix before running.")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print_check("❌", f"Health check failed: {e}")
        sys.exit(1)
