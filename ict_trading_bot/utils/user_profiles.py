"""
User Profile System for Trading Bot

Provides different risk profiles (aggressive/balanced/conservative) that control:
- Minimum CIS score required for trades
- Risk multiplier for position sizing
- Maximum concurrent trades
- Execution route preferences
"""

import os
from typing import Dict, Any, Optional
from enum import Enum

class RiskProfile(Enum):
    AGGRESSIVE = "aggressive"
    BALANCED = "balanced"
    CONSERVATIVE = "conservative"

# Default profile configurations
PROFILE_CONFIGS = {
    RiskProfile.AGGRESSIVE: {
        "min_cis_score": 60,  # Lower threshold for more trades
        "risk_multiplier": 1.5,  # Higher risk per trade
        "max_concurrent_trades": 8,  # More concurrent positions
        "execution_route_preference": ["elite", "standard", "conservative"],  # Prefer higher routes
        "correlation_penalty_multiplier": 0.8,  # Less penalty for correlation
        "market_rhythm_sensitivity": 0.7,  # Less sensitive to rhythm warnings
        "description": "High frequency, higher risk trading"
    },
    RiskProfile.BALANCED: {
        "min_cis_score": 75,  # Moderate threshold
        "risk_multiplier": 1.0,  # Standard risk
        "max_concurrent_trades": 5,  # Moderate concurrent positions
        "execution_route_preference": ["standard", "elite", "conservative"],  # Balanced routes
        "correlation_penalty_multiplier": 1.0,  # Standard correlation penalty
        "market_rhythm_sensitivity": 1.0,  # Standard rhythm sensitivity
        "description": "Balanced risk-reward approach"
    },
    RiskProfile.CONSERVATIVE: {
        "min_cis_score": 85,  # Higher threshold for quality trades
        "risk_multiplier": 0.7,  # Lower risk per trade
        "max_concurrent_trades": 3,  # Fewer concurrent positions
        "execution_route_preference": ["conservative", "standard", "elite"],  # Prefer safer routes
        "correlation_penalty_multiplier": 1.3,  # Higher penalty for correlation
        "market_rhythm_sensitivity": 1.5,  # More sensitive to rhythm warnings
        "description": "Low frequency, high quality trading"
    }
}

def get_user_profile() -> Dict[str, Any]:
    """
    Get the current user profile configuration based on environment variable.

    Returns:
        Dict containing profile settings
    """
    profile_name = os.getenv("TRADING_PROFILE", "balanced").lower()

    try:
        profile_enum = RiskProfile(profile_name)
        config = PROFILE_CONFIGS[profile_enum].copy()

        # Allow environment overrides for fine-tuning
        if "MIN_CIS_SCORE" in os.environ:
            config["min_cis_score"] = int(os.getenv("MIN_CIS_SCORE"))
        if "RISK_MULTIPLIER" in os.environ:
            config["risk_multiplier"] = float(os.getenv("RISK_MULTIPLIER"))
        if "MAX_CONCURRENT_TRADES" in os.environ:
            config["max_concurrent_trades"] = int(os.getenv("MAX_CONCURRENT_TRADES"))

        config["profile_name"] = profile_enum.value
        return config

    except ValueError:
        # Invalid profile name, default to balanced
        print(f"Warning: Invalid TRADING_PROFILE '{profile_name}', using 'balanced'")
        config = PROFILE_CONFIGS[RiskProfile.BALANCED].copy()
        config["profile_name"] = RiskProfile.BALANCED.value
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

    return cis_score >= profile["min_cis_score"]

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

    return profile["max_concurrent_trades"]

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
        f"Min CIS: {profile['min_cis_score']}, Risk Multiplier: {profile['risk_multiplier']:.1f}x, "
        f"Max Trades: {profile['max_concurrent_trades']}"
    )