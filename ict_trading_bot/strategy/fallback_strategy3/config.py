"""
FALLBACK STRATEGY 3 - Configuration
====================================
All configurable parameters via environment variables.
Defaults are set for conservative initial testing.
"""

import os
from typing import List


def _bool_env(name: str, default: bool) -> bool:
    return os.getenv(name, str(default).lower()).lower() in ("1", "true", "yes", "on")


def _int_env(name: str, default: int, minimum: int = None, maximum: int = None) -> int:
    try:
        value = int(os.getenv(name, str(default)).strip())
    except (TypeError, ValueError):
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _float_env(name: str, default: float, minimum: float = None, maximum: float = None) -> float:
    try:
        value = float(os.getenv(name, str(default)).strip())
    except (TypeError, ValueError):
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _csv_floats(name: str, default: str) -> List[float]:
    raw = os.getenv(name, default)
    return [float(x.strip()) for x in raw.split(",") if x.strip()]


# ============================================================
# Master switch
# ============================================================
FALLBACK3_ENABLED: bool = _bool_env("FALLBACK3_ENABLED", True)

# ============================================================
# Activation mode: "strict", "balanced", "score"
# ============================================================
ACTIVATION_MODE: str = os.getenv("FALLBACK3_ACTIVATION_MODE", "balanced").strip().lower()
VALID_MODES = ("strict", "balanced", "score")
if ACTIVATION_MODE not in VALID_MODES:
    ACTIVATION_MODE = "balanced"

# ============================================================
# Timeframe structure
# ============================================================
HTF_TIMEFRAME: str = os.getenv("FALLBACK3_HTF_TIMEFRAME", "H1")
STRUCTURE_TIMEFRAME: str = os.getenv("FALLBACK3_STRUCTURE_TIMEFRAME", "M15")
EXECUTION_TIMEFRAME: str = os.getenv("FALLBACK3_EXECUTION_TIMEFRAME", "M5")

# ============================================================
# MACD settings (on execution timeframe)
# ============================================================
MACD_FAST: int = _int_env("FALLBACK3_MACD_FAST", 12, minimum=2, maximum=50)
MACD_SLOW: int = _int_env("FALLBACK3_MACD_SLOW", 26, minimum=5, maximum=100)
MACD_SIGNAL: int = _int_env("FALLBACK3_MACD_SIGNAL", 9, minimum=2, maximum=30)
MACD_MAX_CANDLES_BEFORE_CHOCH: int = _int_env("FALLBACK3_MACD_MAX_BEFORE", 3, minimum=0, maximum=20)
MACD_MAX_CANDLES_AFTER_CHOCH: int = _int_env("FALLBACK3_MACD_MAX_AFTER", 3, minimum=0, maximum=20)

# ============================================================
# SMA settings (on execution timeframe)
# ============================================================
SMA_FAST: int = _int_env("FALLBACK3_SMA_FAST", 9, minimum=2, maximum=50)
SMA_SLOW: int = _int_env("FALLBACK3_SMA_SLOW", 21, minimum=5, maximum=100)
SMA_MAX_CANDLES_BEFORE_CHOCH: int = _int_env("FALLBACK3_SMA_MAX_BEFORE", 5, minimum=0, maximum=30)
SMA_MAX_CANDLES_AFTER_CHOCH: int = _int_env("FALLBACK3_SMA_MAX_AFTER", 5, minimum=0, maximum=30)

# ============================================================
# Sweep / CHOCH parameters
# ============================================================
SWEEP_LOOKBACK_CANDLES: int = _int_env("FALLBACK3_SWEEP_LOOKBACK", 20, minimum=5, maximum=100)
CHOCH_MIN_CLOSE_ABOVE_ATR_RATIO: float = _float_env("FALLBACK3_CHOCH_MIN_CLOSE_ATR", 0.3, minimum=0.1, maximum=1.0)
CHOCH_MIN_BODY_RATIO: float = _float_env("FALLBACK3_CHOCH_MIN_BODY", 0.40, minimum=0.2, maximum=0.8)
CHOCH_CLOSE_DISTANCE_PIPS: float = _float_env("FALLBACK3_CHOCH_CLOSE_DIST_PIPS", 0.5, minimum=0.1, maximum=10.0)

# ============================================================
# Entry zones - Fibonacci retracement levels
# ============================================================
FIB_LEVELS: List[float] = _csv_floats("FALLBACK3_FIB_LEVELS", "0.382,0.5,0.618,0.705,0.75,0.786")
ENTRY_METHOD: str = os.getenv("FALLBACK3_ENTRY_METHOD", "confirmation").strip().lower()
VALID_ENTRY_METHODS = ("confirmation", "microstructure", "limit")
if ENTRY_METHOD not in VALID_ENTRY_METHODS:
    ENTRY_METHOD = "confirmation"

# ============================================================
# Risk parameters (fallback uses less risk than primary)
# ============================================================
RISK_PERCENT: float = _float_env("FALLBACK3_RISK_PERCENT", 0.5, minimum=0.05, maximum=5.0)
MIN_RR: float = _float_env("FALLBACK3_MIN_RR", 1.5, minimum=0.5, maximum=10.0)
MAX_TRADES_PER_DAY: int = _int_env("FALLBACK3_MAX_TRADES_PER_DAY", 3, minimum=1, maximum=20)
MAX_LOSSES_PER_DAY: int = _int_env("FALLBACK3_MAX_LOSSES_PER_DAY", 2, minimum=1, maximum=20)
MAX_CONSECUTIVE_LOSSES: int = _int_env("FALLBACK3_MAX_CONSECUTIVE_LOSSES", 3, minimum=1, maximum=10)
MAX_DRAWDOWN_PERCENT: float = _float_env("FALLBACK3_MAX_DRAWDOWN_PERCENT", 5.0, minimum=1.0, maximum=50.0)
MAX_EXPOSURE_PERCENT: float = _float_env("FALLBACK3_MAX_EXPOSURE_PERCENT", 10.0, minimum=1.0, maximum=100.0)
PER_SYMBOL_COOLDOWN: int = _int_env("FALLBACK3_PER_SYMBOL_COOLDOWN", 3600, minimum=300, maximum=86400)
PER_SETUP_COOLDOWN: int = _int_env("FALLBACK3_PER_SETUP_COOLDOWN", 7200, minimum=600, maximum=172800)
DAILY_LOSS_LIMIT: float = _float_env("FALLBACK3_DAILY_LOSS_LIMIT", 2.0, minimum=0.5, maximum=20.0)
WEEKLY_LOSS_LIMIT: float = _float_env("FALLBACK3_WEEKLY_LOSS_LIMIT", 5.0, minimum=1.0, maximum=50.0)

# ============================================================
# Spread threshold (in points/pips)
# ============================================================
MAX_SPREAD_POINTS: int = _int_env("FALLBACK3_MAX_SPREAD_POINTS", 30, minimum=1, maximum=500)

# ============================================================
# Score mode settings
# ============================================================
SCORE_MINIMUM: int = _int_env("FALLBACK3_SCORE_MINIMUM", 75, minimum=0, maximum=100)
SCORE_WATCH_MINIMUM: int = _int_env("FALLBACK3_SCORE_WATCH", 65, minimum=0, maximum=100)

WEIGHT_HTF: int = _int_env("FALLBACK3_WEIGHT_HTF", 15, minimum=0, maximum=100)
WEIGHT_LIQUIDITY: int = _int_env("FALLBACK3_WEIGHT_LIQUIDITY", 15, minimum=0, maximum=100)
WEIGHT_SWEEP: int = _int_env("FALLBACK3_WEIGHT_SWEEP", 15, minimum=0, maximum=100)
WEIGHT_DISPLACEMENT: int = _int_env("FALLBACK3_WEIGHT_DISPLACEMENT", 10, minimum=0, maximum=100)
WEIGHT_CHOCH: int = _int_env("FALLBACK3_WEIGHT_CHOCH", 15, minimum=0, maximum=100)
WEIGHT_MACD: int = _int_env("FALLBACK3_WEIGHT_MACD", 10, minimum=0, maximum=100)
WEIGHT_SMA: int = _int_env("FALLBACK3_WEIGHT_SMA", 10, minimum=0, maximum=100)
WEIGHT_ENTRY_ZONE: int = _int_env("FALLBACK3_WEIGHT_ENTRY_ZONE", 5, minimum=0, maximum=100)
WEIGHT_RISK_REWARD: int = _int_env("FALLBACK3_WEIGHT_RISK_REWARD", 5, minimum=0, maximum=100)

# ============================================================
# Countertrend mode (disabled by default)
# ============================================================
COUNTERTREND_ENABLED: bool = _bool_env("FALLBACK3_COUNTERTREND_ENABLED", False)

# ============================================================
# Consolidation detection
# ============================================================
CONSOLIDATION_ATR_PERCENT: float = _float_env("FALLBACK3_CONSOLIDATION_ATR_PCT", 15.0, minimum=5.0, maximum=50.0)
CONSOLIDATION_SMA_DISTANCE_PIPS: float = _float_env("FALLBACK3_CONSOLIDATION_SMA_DIST", 1.0, minimum=0.1, maximum=20.0)


def validate() -> List[str]:
    """Validate configuration and return list of warnings."""
    warnings = []
    if MACD_FAST >= MACD_SLOW:
        warnings.append(f"MACD_FAST ({MACD_FAST}) must be < MACD_SLOW ({MACD_SLOW})")
    if SMA_FAST >= SMA_SLOW:
        warnings.append(f"SMA_FAST ({SMA_FAST}) must be < SMA_SLOW ({SMA_SLOW})")
    total_weight = sum([
        WEIGHT_HTF, WEIGHT_LIQUIDITY, WEIGHT_SWEEP, WEIGHT_DISPLACEMENT,
        WEIGHT_CHOCH, WEIGHT_MACD, WEIGHT_SMA, WEIGHT_ENTRY_ZONE, WEIGHT_RISK_REWARD,
    ])
    if total_weight != 100 and ACTIVATION_MODE == "score":
        warnings.append(f"Score weights total {total_weight}, expected 100")
    if ENTRY_METHOD == "limit" and ACTIVATION_MODE == "strict":
        warnings.append("Limit entry + strict mode may rarely trigger")
    return warnings
