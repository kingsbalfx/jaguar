"""
TRADING PAIRS CONFIGURATION - All Major Forex & Crypto
Production: kingsbalfx.name.ng
Updated: Feb 13, 2026
"""

import os
from dotenv import load_dotenv

load_dotenv()

class TradingPairs:
    """All supported forex and crypto trading pairs"""
    
    # ========== MAJOR FOREX PAIRS (8) ==========
    MAJOR_FOREX = [
        "EURUSD",  # Euro vs USD
        "GBPUSD",  # British Pound vs USD
        "USDJPY",  # USD vs Japanese Yen
        "USDCHF",  # USD vs Swiss Franc
        "AUDUSD",  # Australian Dollar vs USD
        "USDCAD",  # USD vs Canadian Dollar
        "NZDUSD",  # New Zealand Dollar vs USD
        "USDSEK",  # USD vs Swedish Krona
    ]
    
    # ========== MINOR FOREX PAIRS (16) ==========
    MINOR_FOREX = [
        "EURJPY",  # Euro vs Yen
        "EURGBP",  # Euro vs British Pound
        "EURCAD",  # Euro vs Canadian Dollar
        "EURCHF",  # Euro vs Swiss Franc
        "EURAUD",  # Euro vs Australian Dollar
        "GBPJPY",  # British Pound vs Yen
        "GBPCHF",  # British Pound vs Swiss Franc
        "GBPAUD",  # British Pound vs Australian Dollar
        "GBPCAD",  # British Pound vs Canadian Dollar
        "AUDJPY",  # Australian Dollar vs Yen
        "AUDCAD",  # Australian Dollar vs Canadian Dollar
        "AUDCHF",  # Australian Dollar vs Swiss Franc
        "CADJPY",  # Canadian Dollar vs Yen
        "CHFJPY",  # Swiss Franc vs Yen
        "NZDJPY",  # New Zealand Dollar vs Yen
        "NZDCAD",  # New Zealand Dollar vs Canadian Dollar
    ]
    
    # ========== EXOTICS & EMERGENT (12) ==========
    EXOTIC_PAIRS = [
        "USDZAR",  # USD vs South African Rand
        "USDHKD",  # USD vs Hong Kong Dollar
        "USDMXN",  # USD vs Mexican Peso
        "USDSGD",  # USD vs Singapore Dollar
        "USDTHB",  # USD vs Thai Baht
        "USDBRL",  # USD vs Brazilian Real
        "USDPLN",  # USD vs Polish Zloty
        "USDTRY",  # USD vs Turkish Lira
        "USDZWL",  # USD vs Zimbabwean Dollar
        "EURDKK",  # Euro vs Danish Krone
        "EURNOK",  # Euro vs Norwegian Krone
        "EURSEK",  # Euro vs Swedish Krona
    ]
    
    # ========== PRECIOUS METALS (4) ==========
    # Usually as XAUUSD (Gold), XAGUSD (Silver), XPTUSD (Platinum), XPDUSD (Palladium)
    PRECIOUS_METALS = [
        "XAUUSD",  # Gold vs USD
        "XAGUSD",  # Silver vs USD
        "XPTUSD",  # Platinum vs USD
        "XPDUSD",  # Palladium vs USD
    ]
    
    # ========== CRYPTOCURRENCIES (12) - CFD/Spot ==========
    # Note: Not all brokers support all crypto. Check MT5 availability
    CRYPTO = [
        "BTCUSD",  # Bitcoin vs USD
        "ETHUSD",  # Ethereum vs USD
        "LTCUSD",  # Litecoin vs USD
        "BCHUSD",  # Bitcoin Cash vs USD
        "XRPUSD",  # Ripple vs USD
        "EOSUSD",  # EOS vs USD
        "ADAUSD",  # Cardano vs USD
        "SOLUSD",  # Solana vs USD
        "DOGUSD",  # Dogecoin vs USD
        "MATICUSD",  # Polygon vs USD
        "LINKUSD",  # Chainlink vs USD
        "UNIUSD",  # Uniswap vs USD
    ]
    
    # ========== INDICES (8) ==========
    # CFDs on major stock market indices
    INDICES = [
        "US500",   # S&P 500
        "NAS100",  # NASDAQ 100
        "DJ30",    # Dow Jones 30
        "FTSE",    # FTSE 100 (UK)
        "DAX40",   # DAX 40 (Germany)
        "CAC40",   # CAC 40 (France)
        "STOXX50", # Euro Stoxx 50
        "NIKKEI",  # Nikkei 225 (Japan)
    ]
    
    # ========== COMMODITIES (6) ==========
    # Oil, Gas, Agricultural
    COMMODITIES = [
        "CRUNOIL", # Crude Oil
        "BRENT",   # Brent Oil
        "NATGAS",  # Natural Gas
        "COMUSD",  # Copper
        "WHEATUSD",# Wheat
        "CORMUSD", # Corn
    ]
    
    @classmethod
    def get_all_pairs(cls):
        """Get all available trading pairs"""
        return (
            cls.MAJOR_FOREX
            + cls.MINOR_FOREX
            + cls.EXOTIC_PAIRS
            + cls.PRECIOUS_METALS
            + cls.CRYPTO
            + cls.INDICES
            + cls.COMMODITIES
        )
    
    @classmethod
    def get_pairs_by_category(cls, category):
        """Get pairs by category"""
        categories = {
            "major_forex": cls.MAJOR_FOREX,
            "minor_forex": cls.MINOR_FOREX,
            "exotic": cls.EXOTIC_PAIRS,
            "metals": cls.PRECIOUS_METALS,
            "crypto": cls.CRYPTO,
            "indices": cls.INDICES,
            "commodities": cls.COMMODITIES,
        }
        return categories.get(category.lower(), [])
    
    @classmethod
    def get_pairs_for_tier(cls, tier):
        """Get recommended pairs based on subscription tier"""
        if not tier or tier.lower() == "free":
            # Free tier: Only major forex
            return cls.MAJOR_FOREX[:3]  # EURUSD, GBPUSD, USDJPY
        
        elif tier.lower() == "premium":
            # Premium: Major + Minor forex + some metals
            return cls.MAJOR_FOREX + cls.MINOR_FOREX[:5] + ["XAUUSD"]
        
        elif tier.lower() == "vip":
            # VIP: Forex + Metals + Some crypto + indices
            return (
                cls.MAJOR_FOREX
                + cls.MINOR_FOREX
                + cls.PRECIOUS_METALS
                + cls.CRYPTO[:6]
                + cls.INDICES[:4]
            )
        
        elif tier.lower() in ["pro", "lifetime"]:
            # Pro/Lifetime: Everything
            return cls.get_all_pairs()
        
        return cls.MAJOR_FOREX  # Default to major forex


class BotConfig:
    """Complete bot configuration for production kingsbalfx.name.ng"""
    
    # ========== ENVIRONMENT ==========
    ENVIRONMENT = os.getenv("ENVIRONMENT", "production")
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "bot_production.log")
    
    # ========== PRODUCTION DOMAIN ==========
    DOMAIN = "https://kingsbalfx.name.ng"
    
    # ========== MT5 CONNECTION ==========
    # Credentials are loaded from Supabase by the bot at runtime.
    MT5_TIMEOUT = 30  # Connection timeout in seconds
    
    # ========== TRADING CONFIGURATION ==========
    # Default trading pairs (can be overridden per user tier)
    SYMBOLS = TradingPairs.MAJOR_FOREX
    
    # Risk management
    RISK_PER_TRADE = float(os.getenv("RISK_PER_TRADE", "1.0"))
    MAX_DAILY_LOSS_PERCENT = float(os.getenv("MAX_DAILY_LOSS_PERCENT", "5.0"))
    MAX_CONCURRENT_TRADES = int(os.getenv("MAX_CONCURRENT_TRADES", "5"))
    MAX_TRADES_PER_SYMBOL = int(os.getenv("MAX_TRADES_PER_SYMBOL", "2"))
    MIN_LOT_SIZE = 0.01
    MAX_LOT_SIZE = 5.0
    
    # Trading hours (UTC)
    LONDON_START = 8
    LONDON_END = 16
    NY_START = 13
    NY_END = 21
    ASIA_START = 22  # Previous day
    ASIA_END = 6
    
    # Price action filters
    MIN_CANDLESTICK_SIZE = 0.0005  # Minimum pip movement
    MAX_SPREAD = 2.5  # Maximum spread in pips
    MIN_VOLUME_RATIO = 0.8  # Volume ratio threshold
    
    # ========== DATABASE (SUPABASE) ==========
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
    SUPABASE_TABLE_TRADES = "bot_logs"
    SUPABASE_TABLE_SIGNALS = "bot_signals"
    SUPABASE_TABLE_ERRORS = "bot_errors"
    
    # ========== BOT API SERVER ==========
    API_HOST = os.getenv("BOT_API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("BOT_API_PORT", "8000"))
    API_WORKERS = int(os.getenv("API_WORKERS", "4"))
    
    # ========== PRICING INTEGRATION ==========
    # Tier-based signal quality
    SIGNAL_QUALITY_FREE = "basic"
    SIGNAL_QUALITY_PREMIUM = "standard"
    SIGNAL_QUALITY_VIP = "premium"
    SIGNAL_QUALITY_PRO = "elite"
    SIGNAL_QUALITY_LIFETIME = "elite"
    
    # Tier-based max signals per day
    SIGNALS_PER_DAY_FREE = 3
    SIGNALS_PER_DAY_PREMIUM = 15
    SIGNALS_PER_DAY_VIP = 30
    SIGNALS_PER_DAY_PRO = 100
    SIGNALS_PER_DAY_LIFETIME = 1000  # Unlimited
    
    # Tier-based max concurrent trades
    MAX_TRADES_FREE = 0
    MAX_TRADES_PREMIUM = 5
    MAX_TRADES_VIP = 10
    MAX_TRADES_PRO = 20
    MAX_TRADES_LIFETIME = 1000  # Unlimited
    
    @classmethod
    def validate(cls):
        """Validate all required settings"""
        required = [
            ("SUPABASE_URL", cls.SUPABASE_URL),
            ("SUPABASE_KEY", cls.SUPABASE_KEY),
        ]

        missing = [name for name, value in required if not value]

        if missing:
            print(f"⚠️  PRODUCTION VALIDATION FAILED")
            print(f"   Missing environment variables: {', '.join(missing)}")
            print(f"   Update: ict_trading_bot/.env.production")
            return False

        print("✅ Production configuration valid!")
        print(f"   Domain: {cls.DOMAIN}")
        print(f"   Environment: {cls.ENVIRONMENT}")
        print(f"   Trading pairs available: {len(TradingPairs.get_all_pairs())}")
        return True
    
    @classmethod
    def get_config_for_tier(cls, tier):
        """Get bot configuration for user tier"""
        tier = (tier or "free").lower()
        
        pairs_by_tier = {
            "free": TradingPairs.get_pairs_for_tier("free"),
            "premium": TradingPairs.get_pairs_for_tier("premium"),
            "vip": TradingPairs.get_pairs_for_tier("vip"),
            "pro": TradingPairs.get_pairs_for_tier("pro"),
            "lifetime": TradingPairs.get_pairs_for_tier("lifetime"),
        }
        
        signals_by_tier = {
            "free": cls.SIGNALS_PER_DAY_FREE,
            "premium": cls.SIGNALS_PER_DAY_PREMIUM,
            "vip": cls.SIGNALS_PER_DAY_VIP,
            "pro": cls.SIGNALS_PER_DAY_PRO,
            "lifetime": cls.SIGNALS_PER_DAY_LIFETIME,
        }
        
        trades_by_tier = {
            "free": cls.MAX_TRADES_FREE,
            "premium": cls.MAX_TRADES_PREMIUM,
            "vip": cls.MAX_TRADES_VIP,
            "pro": cls.MAX_TRADES_PRO,
            "lifetime": cls.MAX_TRADES_LIFETIME,
        }
        
        quality_by_tier = {
            "free": cls.SIGNAL_QUALITY_FREE,
            "premium": cls.SIGNAL_QUALITY_PREMIUM,
            "vip": cls.SIGNAL_QUALITY_VIP,
            "pro": cls.SIGNAL_QUALITY_PRO,
            "lifetime": cls.SIGNAL_QUALITY_LIFETIME,
        }
        
        return {
            "pairs": pairs_by_tier.get(tier, pairs_by_tier["free"]),
            "max_signals_per_day": signals_by_tier.get(tier, signals_by_tier["free"]),
            "max_concurrent_trades": trades_by_tier.get(tier, trades_by_tier["free"]),
            "signal_quality": quality_by_tier.get(tier, quality_by_tier["free"]),
        }


# Export for use throughout bot
__all__ = ["BotConfig", "TradingPairs"]
