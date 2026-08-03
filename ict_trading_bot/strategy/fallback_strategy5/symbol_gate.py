"""
FALLBACK STRATEGY 5 — Symbol Gate
===================================
Hard-restrict Fallback 5 to EURUSD, XAUUSD, BTCUSD, AUDJPY.
Supports broker symbol aliases via config.SYMBOL_ALIAS_MAP.
"""

from . import config


def resolve_symbol(raw_symbol: str) -> str:
    """
    Resolve a broker symbol to the canonical Fallback 5 approved instrument.
    Returns canonical symbol or empty string if not allowed.
    """
    canonical = config.resolve_canonical_symbol(raw_symbol)
    if canonical and canonical in config.ALLOWED_SYMBOLS:
        return canonical
    return ""


def is_allowed_symbol(raw_symbol: str) -> bool:
    """Check if a symbol is allowed for Fallback 5 trading."""
    return bool(resolve_symbol(raw_symbol))


def get_symbol_profile(raw_symbol: str) -> dict:
    """Return symbol-specific profile for the resolved symbol."""
    symbol = resolve_symbol(raw_symbol)
    if not symbol:
        return {}

    profiles = {
        "EURUSD": {
            "spread_max_pips": 15,
            "spread_max_points": 30,
            "atr_min_pips": 5,
            "stop_min_pips": 8,
            "tp_min_pips": 10,
            "default_risk_percent": 0.15,
            "max_risk_percent": 0.40,
            "single_point_value": 0.0001,
            "stop_buffer_points": 5,
        },
        "XAUUSD": {
            "spread_max_pips": 50,
            "spread_max_points": 500,
            "atr_min_pips": 50,
            "stop_min_pips": 60,
            "tp_min_pips": 80,
            "default_risk_percent": 0.10,
            "max_risk_percent": 0.30,
            "single_point_value": 0.01,
            "stop_buffer_points": 10,
        },
        "BTCUSD": {
            "spread_max_pips": 100,
            "spread_max_points": 1000,
            "atr_min_pips": 100,
            "stop_min_pips": 120,
            "tp_min_pips": 150,
            "default_risk_percent": 0.10,
            "max_risk_percent": 0.25,
            "single_point_value": 0.01,
            "stop_buffer_points": 20,
        },
        "AUDJPY": {
            "spread_max_pips": 12,
            "spread_max_points": 20,
            "atr_min_pips": 6,
            "stop_min_pips": 10,
            "tp_min_pips": 12,
            "default_risk_percent": 0.15,
            "max_risk_percent": 0.40,
            "single_point_value": 0.001,
            "stop_buffer_points": 5,
        },
    }
    return profiles.get(symbol, {})
