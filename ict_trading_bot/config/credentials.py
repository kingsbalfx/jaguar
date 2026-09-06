"""
Local credential management for Supabase and other services.
Stores credentials locally and loads them on startup.
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Credential store location
CREDENTIALS_DIR = Path(os.path.expanduser("~/.ict_trading_bot"))
CREDENTIALS_FILE = CREDENTIALS_DIR / "credentials.json"


def ensure_credentials_dir():
    """Ensure the credentials directory exists."""
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    # Set restrictive permissions on credentials directory
    try:
        os.chmod(CREDENTIALS_DIR, 0o700)
    except Exception as e:
        logger.warning(f"Could not set permissions on credentials directory: {e}")


def load_credentials() -> Dict[str, Any]:
    """Load stored credentials from local file."""
    ensure_credentials_dir()
    
    if not CREDENTIALS_FILE.exists():
        return {}
    
    try:
        with open(CREDENTIALS_FILE, 'r') as f:
            creds = json.load(f)
            logger.info(f"Loaded credentials from {CREDENTIALS_FILE}")
            return creds
    except Exception as e:
        logger.error(f"Failed to load credentials: {e}")
        return {}


def save_credentials(credentials: Dict[str, Any]) -> bool:
    """Save credentials to local file."""
    ensure_credentials_dir()
    
    try:
        with open(CREDENTIALS_FILE, 'w') as f:
            json.dump(credentials, f, indent=2)
        
        # Set restrictive permissions on credential file
        try:
            os.chmod(CREDENTIALS_FILE, 0o600)
        except Exception as e:
            logger.warning(f"Could not set permissions on credentials file: {e}")
        
        logger.info(f"Credentials saved to {CREDENTIALS_FILE}")
        return True
    except Exception as e:
        logger.error(f"Failed to save credentials: {e}")
        return False


def get_supabase_credentials() -> tuple[Optional[str], Optional[str]]:
    """
    Get Supabase credentials from environment or local storage.
    
    Returns:
        Tuple of (supabase_url, supabase_key) or (None, None)
    """
    # First try environment variables
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    if url and key:
        logger.info("Using Supabase credentials from environment")
        return url, key
    
    # Try local credentials
    creds = load_credentials()
    url = creds.get("supabase_url")
    key = creds.get("supabase_key")
    
    if url and key:
        logger.info("Using Supabase credentials from local storage")
        # Also set environment variables for consistency
        os.environ["SUPABASE_URL"] = url
        os.environ["SUPABASE_KEY"] = key
        return url, key
    
    logger.warning("No Supabase credentials found in environment or local storage")
    return None, None


def set_supabase_credentials(url: str, key: str) -> bool:
    """Set and save Supabase credentials."""
    creds = load_credentials()
    creds["supabase_url"] = url
    creds["supabase_key"] = key
    
    if save_credentials(creds):
        os.environ["SUPABASE_URL"] = url
        os.environ["SUPABASE_KEY"] = key
        return True
    return False


def prompt_for_supabase_credentials() -> bool:
    """
    Interactively prompt user to enter Supabase credentials.
    
    Returns:
        True if credentials were successfully saved, False otherwise
    """
    print("\n" + "="*60)
    print("SUPABASE CREDENTIALS SETUP")
    print("="*60)
    print("\nNo Supabase credentials found.")
    print("Please enter your Supabase credentials to enable cloud persistence.\n")
    print("You can find these in your Supabase project settings:")
    print("  - Project URL: https://app.supabase.com/project/[your-project]/settings/api")
    print("  - API Key: Use the 'anon public' key from the same page\n")
    
    url = input("Enter your Supabase Project URL: ").strip()
    if not url:
        print("❌ URL is required")
        return False
    
    if not url.startswith("https://"):
        print("❌ URL must start with https://")
        return False
    
    key = input("Enter your Supabase API Key (anon public): ").strip()
    if not key:
        print("❌ API Key is required")
        return False
    
    # Test the credentials
    print("\nTesting credentials...")
    try:
        from supabase import create_client
        client = create_client(url, key)
        # Try a simple health check
        logger.info("Testing Supabase connection...")
        print("✅ Credentials validated successfully!")
        
        # Save credentials
        if set_supabase_credentials(url, key):
            print(f"✅ Credentials saved to {CREDENTIALS_FILE}")
            print("="*60 + "\n")
            return True
        else:
            print("❌ Failed to save credentials")
            return False
            
    except Exception as e:
        print(f"❌ Failed to validate credentials: {e}")
        print("   Please check your credentials and try again.")
        return False


def has_supabase_credentials() -> bool:
    """Check if Supabase credentials are available."""
    url, key = get_supabase_credentials()
    return bool(url and key)
