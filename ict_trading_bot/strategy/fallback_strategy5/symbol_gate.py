"""
FALLBACK STRATEGY 5 — Symbol Gate
===================================
Tradable symbols come from the LIVE MT5 universe.

Priority:
  1. ``FALLBACK5_SYMBOL_SOURCE=mt5`` (default)
     Any symbol the connected MT5 terminal exposes is eligible. The universe is
     synchronized by ``main.py`` at startup (and periodically) through
     :mod:`config.mt5_universe`.
  2. ``FALLBACK5_SYMBOL_SOURCE=custom``
     Only ``FALLBACK5_ALLOWED_SYMBOLS`` (CSV) is eligible.
  3. ``FALLBACK5_SYMBOL_SOURCE=core``
     Only the original four instruments (EURUSD, XAUUSD, BTCUSD, AUDJPY).

Broker aliases (XAUUSD.A, EURUSDm, ...) are resolved through
``config.SYMBOL_ALIAS_MAP`` plus the shared MT5-universe alias index.
"""

from . import config


def _explicit_allowlist() -> tuple:
    source = config.FALLBACK5_SYMBOL_SOURCE
    if source == "custom":
        return tuple(config.ALLOWED_SYMBOLS)
    if source == "core":
        return tuple(config.CORE_SYMBOLS)
    return ()


def _in_mt5_universe(raw_symbol: str, canonical: str) -> bool:
    try:
        from config.mt5_universe import is_available, universe_size

        if universe_size() == 0:
            return bool(config.ALLOW_WHEN_UNIVERSE_EMPTY)
        return is_available(raw_symbol) or is_available(canonical)
    except Exception:
        # Never block trading because the registry is unavailable.
        return bool(config.ALLOW_WHEN_UNIVERSE_EMPTY)


def resolve_symbol(raw_symbol: str) -> str:
    """
    Resolve a broker symbol to the canonical Fallback 5 instrument.
    Returns the canonical symbol, or an empty string when not allowed.
    """
    canonical = config.resolve_canonical_symbol(raw_symbol)
    if not canonical:
        return ""

    allowlist = _explicit_allowlist()
    if allowlist:
        raw = str(raw_symbol or "").strip().upper()
        permitted = canonical in allowlist or raw in allowlist
        return canonical if permitted else ""

    if _in_mt5_universe(str(raw_symbol or ""), canonical):
        return canonical
    return ""


def resolve_broker_symbol(raw_symbol: str) -> str:
    """Return the exact MT5 broker symbol for ``raw_symbol`` (or the input)."""
    raw = str(raw_symbol or "").strip()
    if not raw:
        return ""
    try:
        from config.mt5_universe import resolve_tradable

        return resolve_tradable(raw) or raw
    except Exception:
        return raw


def symbol_gate_reason(raw_symbol: str) -> str:
    """Return ``""`` when allowed, otherwise a machine-readable reason."""
    canonical = config.resolve_canonical_symbol(raw_symbol)
    if not canonical:
        return "symbol_unrecognized"
    if resolve_symbol(raw_symbol):
        return ""
    if _explicit_allowlist():
        return "symbol_not_allowed"
    return "symbol_not_available_in_mt5"


def is_allowed_symbol(raw_symbol: str) -> bool:
    """Check if a symbol is allowed for Fallback 5 trading."""
    return bool(resolve_symbol(raw_symbol))


def universe_snapshot() -> dict:
    """Diagnostics: which symbol source is driving the gate."""
    snapshot = {
        "symbol_source": config.FALLBACK5_SYMBOL_SOURCE,
        "explicit_allowlist": list(_explicit_allowlist()),
        "allow_when_universe_empty": bool(config.ALLOW_WHEN_UNIVERSE_EMPTY),
    }
    try:
        from config.mt5_universe import universe_snapshot as _snap

        snapshot["mt5_universe"] = _snap()
    except Exception:
        snapshot["mt5_universe"] = {}
    return snapshot


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
    return profiles.get(symbol, dict(config.DEFAULT_SYMBOL_PROFILE))
