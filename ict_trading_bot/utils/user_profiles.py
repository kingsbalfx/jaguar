"""
User Profile System for Trading Bot

Provides different risk profiles (aggressive/balanced/conservative) that control:
- Minimum CIS score required for trades (0-100)
- Risk multiplier for position sizing
- Maximum concurrent trades
- Execution route preferences
"""

import os
import time
from typing import Dict, Any, Optional
from enum import Enum

class RiskProfile(Enum):
    AGGRESSIVE = "aggressive"
    BALANCED = "balanced"
    CONSERVATIVE = "conservative"

# Default profile configurations
PROFILE_CONFIGS = {
    RiskProfile.AGGRESSIVE: {
        "min_score": 50,  # Lower threshold for more trades
        "risk_multiplier": 1.2,  # Higher risk per trade
        "max_trades": 5,  # More concurrent positions
        "max_exposure": 10.0,  # Total exposure cap (%)
        "trade_frequency": "high",
        "execution_route_preference": ["elite", "standard", "conservative"],
        "correlation_penalty_multiplier": 0.8,  # Less penalty for correlation
        "market_rhythm_sensitivity": 0.7,  # Less sensitive to rhythm warnings
        "description": "High frequency, higher risk trading"
    },
    RiskProfile.BALANCED: {
        "min_score": 60,  # Moderate threshold
        "risk_multiplier": 1.0,  # Standard risk
        "max_trades": 3,  # Moderate concurrent positions
        "max_exposure": 6.0,
        "trade_frequency": "medium",
        "execution_route_preference": ["standard", "elite", "conservative"],
        "correlation_penalty_multiplier": 1.0,  # Standard correlation penalty
        "market_rhythm_sensitivity": 1.0,  # Standard rhythm sensitivity
        "description": "Balanced risk-reward approach"
    },
    RiskProfile.CONSERVATIVE: {
        "min_score": 70,  # Higher threshold for quality trades
        "risk_multiplier": 0.7,  # Lower risk per trade
        "max_trades": 2,  # Fewer concurrent positions
        "max_exposure": 4.0,
        "trade_frequency": "low",
        "execution_route_preference": ["conservative", "standard", "elite"],
        "correlation_penalty_multiplier": 1.3,  # Higher penalty for correlation
        "market_rhythm_sensitivity": 1.5,  # More sensitive to rhythm warnings
        "description": "Low frequency, high quality trading"
    }
}

_REMOTE_PROFILE_CACHE = {"user_id": None, "profile": None, "fetched_at": 0.0}


def _fetch_remote_profile_name(user_id: str) -> Optional[str]:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key or not user_id:
        return None

    try:
        from supabase import create_client
    except Exception:
        return None

    try:
        client = create_client(url, key)
        res = client.table("profiles").select("trading_profile").eq("id", user_id).limit(1).execute()
        rows = getattr(res, "data", None) or []
        if not rows:
            return None
        raw = str(rows[0].get("trading_profile") or "").strip().lower()
        return raw or None
    except Exception:
        # Missing column, RLS, or other schema mismatches should fail open.
        return None


def _resolve_profile_name() -> str:
    # 1) Explicit env override (per-bot instance)
    for name in ("BOT_USER_PROFILE", "TRADING_PROFILE"):
        raw = os.getenv(name, "").strip().lower()
        if raw:
            return raw

    # 2) Supabase profile-driven setting (per user)
    user_id = (os.getenv("BOT_USER_ID") or os.getenv("SIGNAL_USER_ID") or "").strip()
    if user_id:
        ttl = max(5, int(os.getenv("TRADING_PROFILE_CACHE_SECONDS", "30") or 30))
        now = time.time()
        cached = _REMOTE_PROFILE_CACHE
        if cached.get("user_id") == user_id and (now - float(cached.get("fetched_at", 0.0) or 0.0)) < ttl:
            return cached.get("profile") or "balanced"

        remote = _fetch_remote_profile_name(user_id)
        _REMOTE_PROFILE_CACHE.update({"user_id": user_id, "profile": remote or "balanced", "fetched_at": now})
        return remote or "balanced"

    return "balanced"


def get_user_profile() -> Dict[str, Any]:
    """
    Get the current user profile configuration based on environment variable.

    Returns:
        Dict containing profile settings
    """
    profile_name = _resolve_profile_name()

    try:
        profile_enum = RiskProfile(profile_name)
        config = PROFILE_CONFIGS[profile_enum].copy()

        # Allow environment overrides for fine-tuning
        if "MIN_SCORE" in os.environ:
            config["min_score"] = int(os.getenv("MIN_SCORE"))
        if "MIN_CIS_SCORE" in os.environ:
            config["min_score"] = int(os.getenv("MIN_CIS_SCORE"))
        if "RISK_MULTIPLIER" in os.environ:
            config["risk_multiplier"] = float(os.getenv("RISK_MULTIPLIER"))
        if "MAX_TRADES" in os.environ:
            config["max_trades"] = int(os.getenv("MAX_TRADES"))
        if "MAX_CONCURRENT_TRADES" in os.environ:
            config["max_trades"] = int(os.getenv("MAX_CONCURRENT_TRADES"))
        if "MAX_EXPOSURE" in os.environ:
            config["max_exposure"] = float(os.getenv("MAX_EXPOSURE"))

        config["profile_name"] = profile_enum.value
        # Backwards-compatible aliases used in logs and older modules.
        config["min_cis_score"] = config.get("min_score")
        config["max_concurrent_trades"] = config.get("max_trades")
        return config

    except ValueError:
        # Invalid profile name, default to balanced
        print(f"Warning: Invalid TRADING_PROFILE '{profile_name}', using 'balanced'")
        config = PROFILE_CONFIGS[RiskProfile.BALANCED].copy()
        config["profile_name"] = RiskProfile.BALANCED.value
        config["min_cis_score"] = config.get("min_score")
        config["max_concurrent_trades"] = config.get("max_trades")
        return config

def validate_cis_score_for_profile(cis_score: float, profile: Optional[Dict] = None) -> bool:
    """
    Check if a CIS score meets the minimum requirement for the current profile.

    Args:
        cis_score: The CIS score (0-100)
        profile: Optional profile config, will get current if not provided

    Returns:
        True if score meets minimum requirement
    """
    if profile is None:
        profile = get_user_profile()

    return cis_score >= float(profile.get("min_score", profile.get("min_cis_score", 0)) or 0)

def get_profile_adjusted_risk(base_risk: float, profile: Optional[Dict] = None) -> float:
    """
    Adjust base risk percentage based on user profile.

    Args:
        base_risk: Base risk percentage
        profile: Optional profile config

    Returns:
        Adjusted risk percentage
    """
    if profile is None:
        profile = get_user_profile()

    return base_risk * profile["risk_multiplier"]

def get_profile_max_trades(profile: Optional[Dict] = None) -> int:
    """
    Get maximum concurrent trades allowed for the profile.

    Args:
        profile: Optional profile config

    Returns:
        Maximum number of concurrent trades
    """
    if profile is None:
        profile = get_user_profile()

    return int(profile.get("max_trades", profile.get("max_concurrent_trades", 0)) or 0)

def get_profile_correlation_penalty(base_penalty: float, profile: Optional[Dict] = None) -> float:
    """
    Adjust correlation penalty based on user profile.

    Args:
        base_penalty: Base correlation penalty
        profile: Optional profile config

    Returns:
        Adjusted correlation penalty
    """
    if profile is None:
        profile = get_user_profile()

    return base_penalty * profile["correlation_penalty_multiplier"]

def get_profile_rhythm_sensitivity(profile: Optional[Dict] = None) -> float:
    """
    Get market rhythm sensitivity multiplier for the profile.

    Args:
        profile: Optional profile config

    Returns:
        Rhythm sensitivity multiplier
    """
    if profile is None:
        profile = get_user_profile()

    return profile["market_rhythm_sensitivity"]

def get_execution_route_preference(profile: Optional[Dict] = None) -> list:
    """
    Get preferred execution routes in order of preference.

    Args:
        profile: Optional profile config

    Returns:
        List of execution routes in preference order
    """
    if profile is None:
        profile = get_user_profile()

    return profile["execution_route_preference"]

def log_profile_info(profile: Optional[Dict] = None) -> str:
    """
    Generate a human-readable description of the current profile.

    Args:
        profile: Optional profile config

    Returns:
        Profile description string
    """
    if profile is None:
        profile = get_user_profile()

    return (
        f"Profile: {profile['profile_name'].title()} - {profile['description']}. "
        f"Min CIS: {profile.get('min_score', profile.get('min_cis_score'))}, Risk Multiplier: {profile['risk_multiplier']:.1f}x, "
        f"Max Trades: {profile.get('max_trades', profile.get('max_concurrent_trades'))}"
    )
