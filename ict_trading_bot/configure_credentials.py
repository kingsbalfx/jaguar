#!/usr/bin/env python3
"""
Interactive credential configuration tool for ICT Trading Bot.
Allows admins to set up Supabase and MT5 credentials locally.
Run this ONCE after installing the bot to set up cloud persistence.

Usage:
    python configure_credentials.py
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any

def print_header(text: str):
    """Print a formatted header."""
    print("\n" + "="*70)
    print(f" {text}")
    print("="*70 + "\n")

def print_info(text: str):
    """Print info message."""
    print(f"ℹ️  {text}")

def print_success(text: str):
    """Print success message."""
    print(f"✅ {text}")

def print_error(text: str):
    """Print error message."""
    print(f"❌ {text}")

def print_warning(text: str):
    """Print warning message."""
    print(f"⚠️  {text}")

def load_local_credentials() -> Dict[str, Any]:
    """Load existing credentials from local storage."""
    from config.credentials import load_credentials
    return load_credentials()

def save_local_credentials(credentials: Dict[str, Any]) -> bool:
    """Save credentials to local storage."""
    from config.credentials import save_credentials
    return save_credentials(credentials)

def setup_supabase_credentials():
    """Interactively set up Supabase credentials."""
    print_header("SUPABASE CONFIGURATION")
    
    print_info("Supabase provides cloud-based data persistence for:")
    print("  • Trade signals and execution logs")
    print("  • Mirror trading coordination across accounts")
    print("  • Trading statistics and performance analytics")
    print()
    print_info("You can find your credentials at:")
    print("  https://app.supabase.com/project/[your-project]/settings/api")
    print()
    
    while True:
        url = input("Enter Supabase Project URL (https://...supabase.co): ").strip()
        
        if not url:
            print_error("URL is required")
            continue
        
        if not url.startswith("https://"):
            print_error("URL must start with https://")
            continue
        
        if "supabase" not in url.lower():
            if input("URL doesn't look like Supabase. Continue anyway? (y/n): ").lower() != "y":
                continue
        
        break
    
    while True:
        key = input("Enter Supabase API Key (anon public key): ").strip()
        
        if not key:
            print_error("API Key is required")
            continue
        
        if len(key) < 20:
            print_error("API Key seems too short. Check that you copied it correctly.")
            continue
        
        break
    
    # Test the credentials
    print_info("Testing connection to Supabase...")
    try:
        from supabase import create_client
        
        client = create_client(url, key)
        print_success("✓ Successfully connected to Supabase!")
        
        # Save credentials
        creds = load_local_credentials()
        creds["supabase_url"] = url
        creds["supabase_key"] = key
        
        if save_local_credentials(creds):
            print_success("Credentials saved successfully!")
            print_info(f"Location: {Path.home() / '.ict_trading_bot' / 'credentials.json'}")
            return True
        else:
            print_error("Failed to save credentials. Check file permissions.")
            return False
            
    except Exception as e:
        print_error(f"Failed to connect: {e}")
        print_info("Please check your credentials and try again.")
        return False

def setup_mt5_credentials():
    """Interactively set up MT5 broker credentials."""
    print_header("MT5 BROKER CREDENTIALS")
    
    print_info("These credentials are for your MetaTrader 5 account.")
    print("They are stored locally and used to authenticate with your broker.\n")
    
    creds = load_local_credentials()
    existing_login = creds.get("mt5_login")
    existing_server = creds.get("mt5_server")
    
    if existing_login and existing_server:
        use_existing = input(f"Use existing MT5 credentials? (login={existing_login}, server={existing_server}) (y/n): ").lower()
        if use_existing == "y":
            return True
    
    print()
    login = input("Enter MT5 Account Login (numeric): ").strip()
    if not login:
        print_warning("MT5 login skipped")
        return True
    
    server = input("Enter MT5 Server (e.g., Headway-Demo, Headway-Live): ").strip()
    if not server:
        print_warning("MT5 server skipped")
        return True
    
    password = input("Enter MT5 Account Password: ").strip()
    if not password:
        print_warning("MT5 password skipped")
        return True
    
    # Save MT5 credentials (these should be handled carefully)
    creds = load_local_credentials()
    creds["mt5_login"] = login
    creds["mt5_server"] = server
    creds["mt5_password"] = password
    
    if save_local_credentials(creds):
        print_success("MT5 credentials saved successfully!")
        return True
    else:
        print_error("Failed to save MT5 credentials")
        return False

def setup_mirror_trading():
    """Configure mirror trading settings."""
    print_header("MIRROR TRADING CONFIGURATION")
    
    print_info("Mirror trading coordinates trade signals across multiple MT5 accounts.")
    print("Settings to configure:")
    print("  • Enable/disable mirror trading")
    print("  • Risk percentage per trade")
    print("  • API communication timeout")
    print()
    
    creds = load_local_credentials()
    
    enable_mirror = input("Enable mirror trading? (y/n): ").lower()
    if enable_mirror == "y":
        creds["mirror_enabled"] = True
        print_success("Mirror trading enabled")
        
        risk_str = input("Risk percentage per trade (default 1.0%): ").strip() or "1.0"
        try:
            risk = float(risk_str)
            if 0.01 <= risk <= 2.0:
                creds["mirror_risk_percent"] = risk
                print_success(f"Risk per trade set to {risk}%")
            else:
                print_error("Risk must be between 0.01% and 2.0%")
        except ValueError:
            print_error("Invalid risk percentage")
    else:
        creds["mirror_enabled"] = False
        print_warning("Mirror trading disabled")
    
    if save_local_credentials(creds):
        return True
    else:
        print_error("Failed to save mirror trading settings")
        return False

def show_credentials_summary():
    """Show summary of configured credentials."""
    print_header("CREDENTIALS SUMMARY")
    
    creds = load_local_credentials()
    
    if not creds:
        print_warning("No credentials configured yet")
        return
    
    if creds.get("supabase_url"):
        url = creds["supabase_url"]
        # Mask the URL for security
        masked_url = url[:20] + "..." + url[-10:] if len(url) > 30 else url
        print_success(f"✓ Supabase configured: {masked_url}")
    else:
        print_warning("⊘ Supabase not configured")
    
    if creds.get("mt5_login"):
        print_success(f"✓ MT5 account configured: {creds['mt5_login']}")
    else:
        print_warning("⊘ MT5 credentials not configured")
    
    if creds.get("mirror_enabled"):
        risk = creds.get("mirror_risk_percent", 1.0)
        print_success(f"✓ Mirror trading enabled (risk: {risk}%)")
    else:
        print_warning("⊘ Mirror trading disabled")
    
    creds_path = Path.home() / ".ict_trading_bot" / "credentials.json"
    print_info(f"Credentials stored at: {creds_path}")
    print_info("File permissions: 0600 (read/write for owner only)")

def reset_credentials():
    """Optionally reset/clear all credentials."""
    print_header("RESET CREDENTIALS")
    
    confirm = input("This will delete all stored credentials. Continue? (type 'yes' to confirm): ")
    if confirm.lower() != "yes":
        print_warning("Reset cancelled")
        return
    
    from config.credentials import CREDENTIALS_DIR
    creds_file = CREDENTIALS_DIR / "credentials.json"
    
    try:
        if creds_file.exists():
            creds_file.unlink()
            print_success("Credentials deleted successfully")
        else:
            print_warning("No credentials file to delete")
    except Exception as e:
        print_error(f"Failed to delete credentials: {e}")

def main():
    """Main menu loop."""
    print_header("ICT TRADING BOT - CREDENTIAL MANAGER")
    
    print("This tool allows you to securely configure:")
    print("  1. Supabase cloud credentials (for persistence and analytics)")
    print("  2. MT5 broker credentials (for trading)")
    print("  3. Mirror trading settings (for multi-account sync)")
    print()
    
    while True:
        show_credentials_summary()
        print()
        print("OPTIONS:")
        print("  1. Configure Supabase credentials")
        print("  2. Configure MT5 credentials")
        print("  3. Configure mirror trading")
        print("  4. Reset all credentials")
        print("  5. Exit")
        print()
        
        choice = input("Select an option (1-5): ").strip()
        
        if choice == "1":
            setup_supabase_credentials()
        elif choice == "2":
            setup_mt5_credentials()
        elif choice == "3":
            setup_mirror_trading()
        elif choice == "4":
            reset_credentials()
        elif choice == "5":
            print_success("Exiting credential manager")
            break
        else:
            print_error("Invalid option. Please try again.")
        
        input("\nPress Enter to continue...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting...")
        sys.exit(0)
    except Exception as e:
        print_error(f"Error: {e}")
        sys.exit(1)
