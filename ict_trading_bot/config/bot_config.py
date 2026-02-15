"""
BOT CONFIGURATION - Complete Production Settings
Domain: https://kingsbalfx.name.ng
Updated: Feb 13, 2026
"""

import os
from dotenv import load_dotenv
from .trading_pairs import BotConfig as DefaultBotConfig, TradingPairs

# Load secrets from .env file
load_dotenv()

class BotConfig(DefaultBotConfig):
    """Production bot configuration - inherits from trading_pairs.BotConfig"""
    
    # ========== PRODUCTION OVERRIDES ========== 
    # These override defaults when environment is set to production
    ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
    DOMAIN = "https://kingsbalfx.name.ng"
    
    # ========== TRADING SYMBOLS - All available pairs ====
    # Default: Major forex. Override per user tier in main.py
    SYMBOLS = TradingPairs.MAJOR_FOREX
    
    # How much to risk on each trade (%)
    RISK_PER_TRADE = float(os.getenv("RISK_PER_TRADE", "1.0"))
    
    # Max trades open at same time
    MAX_OPEN_TRADES = int(os.getenv("MAX_OPEN_TRADES", "5"))
    
    # Only trade during these hours (UTC)
    LONDON_START = 8      # 8 AM UTC
    LONDON_END = 16       # 4 PM UTC
    NY_START = 13         # 1 PM UTC
    NY_END = 21           # 9 PM UTC
    
    # ========== CONNECTION ==========
    # MT5 credentials are stored in Supabase (admin-managed), not env files.
    
    # ========== DATABASE ==========
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
    
    # ========== LOGGING ==========
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "bot.log")
    
    # ========== BOT ==========
    BOT_ENABLED = os.getenv("BOT_ENABLED", "true").lower() == "true"
    API_PORT = int(os.getenv("API_PORT", "8000"))
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    
    @classmethod
    def validate(cls):
        """Check if all required settings are present"""
        required = [
            "SUPABASE_URL",
            "SUPABASE_KEY"
        ]

        missing = []
        for field in required:
            if not getattr(cls, field, None):
                missing.append(field)

        if missing:
            print(f"⚠️  Missing required settings: {', '.join(missing)}")
            print("   Please fill in your .env file!")
            return False

        print("✅ All settings loaded!")
        return True


# Example of how to use:
# from config.bot_config import BotConfig
# BotConfig.validate()
# print(f"Will trade: {BotConfig.SYMBOLS}")
# print(f"Risk per trade: {BotConfig.RISK_PER_TRADE}%")
