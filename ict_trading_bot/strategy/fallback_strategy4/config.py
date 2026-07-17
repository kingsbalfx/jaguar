"""
FALLBACK STRATEGY 4 - Configuration
====================================
All parameters configurable via environment variables.
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


def _csv_strs(name: str, default: str) -> List[str]:
    raw = os.getenv(name, default)
    return [x.strip().lower() for x in raw.split(",") if x.strip()]


# ============================================================
# Master switch
# ============================================================
FALLBACK4_ENABLED: bool = _bool_env("FALLBACK4_ENABLED", True)

# ============================================================
# Timeframe configuration
# ============================================================
EXECUTION_TIMEFRAME: str = os.getenv("FALLBACK4_EXECUTION_TIMEFRAME", "M5")
CONTEXT_TIMEFRAME: str = os.getenv("FALLBACK4_CONTEXT_TIMEFRAME", "M15")
VALID_MODES = ("A", "B", "C")
EXECUTION_MODE: str = os.getenv("FALLBACK4_MODE", "B").strip().upper()
if EXECUTION_MODE not in VALID_MODES:
    EXECUTION_MODE = "B"

# Entry model: A=reclaim_retest, B=displacement_retracement, C=choch_close, D=m1_precision
ENTRY_MODEL: str = os.getenv("FALLBACK4_ENTRY_MODEL", "A").strip().upper()
VALID_ENTRY_MODELS = ("A", "B", "C", "D")
if ENTRY_MODEL not in VALID_ENTRY_MODELS:
    ENTRY_MODEL = "A"

# ============================================================
# Range detection
# ============================================================
MIN_RANGE_DURATION_M5: int = _int_env("FALLBACK4_MIN_RANGE_DURATION_M5", 12, minimum=5, maximum=200)
MAX_RANGE_DURATION_M5: int = _int_env("FALLBACK4_MAX_RANGE_DURATION_M5", 96, minimum=12, maximum=500)
MIN_RANGE_DURATION_M1: int = _int_env("FALLBACK4_MIN_RANGE_DURATION_M1", 20, minimum=8, maximum=300)
MIN_RANGE_WIDTH_ATR: float = _float_env("FALLBACK4_MIN_RANGE_WIDTH_ATR", 1.5, minimum=0.5, maximum=20.0)
MAX_RANGE_WIDTH_ATR: float = _float_env("FALLBACK4_MAX_RANGE_WIDTH_ATR", 8.0, minimum=2.0, maximum=50.0)
MIN_UPPER_INTERACTIONS: int = _int_env("FALLBACK4_MIN_UPPER_INTERACTIONS", 2, minimum=1, maximum=20)
MIN_LOWER_INTERACTIONS: int = _int_env("FALLBACK4_MIN_LOWER_INTERACTIONS", 2, minimum=1, maximum=20)
MIN_ROTATIONS: int = _int_env("FALLBACK4_MIN_ROTATIONS", 2, minimum=0, maximum=50)
BOUNDARY_TOLERANCE_ATR: float = _float_env("FALLBACK4_BOUNDARY_TOLERANCE_ATR", 0.3, minimum=0.05, maximum=2.0)
MIN_RANGE_QUALITY_SCORE: int = _int_env("FALLBACK4_MIN_RANGE_QUALITY", 70, minimum=0, maximum=100)

# ============================================================
# Sweep / penetration
# ============================================================
MIN_SWEEP_PENETRATION_ATR: float = _float_env("FALLBACK4_MIN_SWEEP_PEN_ATR", 0.3, minimum=0.05, maximum=5.0)
MAX_SWEEP_PENETRATION_ATR: float = _float_env("FALLBACK4_MAX_SWEEP_PEN_ATR", 3.0, minimum=0.5, maximum=20.0)
SWEEP_LOOKBACK_CANDLES: int = _int_env("FALLBACK4_SWEEP_LOOKBACK", 30, minimum=10, maximum=200)
MIN_CANDLES_OUTSIDE: int = _int_env("FALLBACK4_MIN_CANDLES_OUTSIDE", 1, minimum=0, maximum=20)
MAX_CANDLES_OUTSIDE: int = _int_env("FALLBACK4_MAX_CANDLES_OUTSIDE", 10, minimum=1, maximum=50)

# ============================================================
# Price acceptance (genuine breakout detection)
# ============================================================
ACCEPTANCE_CANDLES: int = _int_env("FALLBACK4_ACCEPTANCE_CANDLES", 4, minimum=1, maximum=20)
ACCEPTANCE_BODY_RATIO: float = _float_env("FALLBACK4_ACCEPTANCE_BODY_RATIO", 0.6, minimum=0.2, maximum=1.0)
ACCEPTANCE_DISTANCE_ATR: float = _float_env("FALLBACK4_ACCEPTANCE_DIST_ATR", 2.0, minimum=0.5, maximum=10.0)

# ============================================================
# Reclaim
# ============================================================
RECLAIM_MODE: str = os.getenv("FALLBACK4_RECLAIM_MODE", "balanced").strip().lower()
VALID_RECLAIM_MODES = ("strict", "balanced", "aggressive")
if RECLAIM_MODE not in VALID_RECLAIM_MODES:
    RECLAIM_MODE = "balanced"
RECLAIM_BUFFER_ATR: float = _float_env("FALLBACK4_RECLAIM_BUFFER_ATR", 0.15, minimum=0.0, maximum=2.0)
RECLAIM_MAX_CANDLES: int = _int_env("FALLBACK4_RECLAIM_MAX_CANDLES", 8, minimum=1, maximum=50)
RECLAIM_MIN_BODY_RATIO: float = _float_env("FALLBACK4_RECLAIM_MIN_BODY_RATIO", 0.4, minimum=0.1, maximum=0.9)
RECLAIM_FOLLOW_THROUGH: bool = _bool_env("FALLBACK4_RECLAIM_FOLLOW_THROUGH", True)

# ============================================================
# Displacement
# ============================================================
MIN_DISPLACEMENT_BODY_RATIO: float = _float_env("FALLBACK4_MIN_DISP_BODY_RATIO", 0.55, minimum=0.2, maximum=0.9)
MIN_DISPLACEMENT_ATR_RATIO: float = _float_env("FALLBACK4_MIN_DISP_ATR_RATIO", 0.7, minimum=0.2, maximum=3.0)
MIN_DISPLACEMENT_SCORE: int = _int_env("FALLBACK4_MIN_DISP_SCORE", 65, minimum=0, maximum=100)

# ============================================================
# Structure change
# ============================================================
MIN_CHOCH_CLOSE_ATR: float = _float_env("FALLBACK4_MIN_CHOCH_CLOSE_ATR", 0.3, minimum=0.05, maximum=2.0)
MIN_CHOCH_BODY_RATIO: float = _float_env("FALLBACK4_MIN_CHOCH_BODY_RATIO", 0.40, minimum=0.15, maximum=0.8)
CHOCH_BUFFER_PIPS: float = _float_env("FALLBACK4_CHOCH_BUFFER_PIPS", 0.5, minimum=0.1, maximum=20.0)
STRUCTURE_METHOD: str = os.getenv("FALLBACK4_STRUCTURE_METHOD", "choch").strip().lower()
VALID_STRUCTURE_METHODS = ("choch", "bos", "either")
if STRUCTURE_METHOD not in VALID_STRUCTURE_METHODS:
    STRUCTURE_METHOD = "choch"

# ============================================================
# Optional MACD / SMA support (from Fallback 3 indicators)
# ============================================================
MACD_ENABLED: bool = _bool_env("FALLBACK4_MACD_ENABLED", False)
SMA_ENABLED: bool = _bool_env("FALLBACK4_SMA_ENABLED", False)
MACD_FAST: int = _int_env("FALLBACK4_MACD_FAST", 12, minimum=2, maximum=50)
MACD_SLOW: int = _int_env("FALLBACK4_MACD_SLOW", 26, minimum=5, maximum=100)
MACD_SIGNAL: int = _int_env("FALLBACK4_MACD_SIGNAL", 9, minimum=2, maximum=30)
SMA_FAST: int = _int_env("FALLBACK4_SMA_FAST", 9, minimum=2, maximum=50)
SMA_SLOW: int = _int_env("FALLBACK4_SMA_SLOW", 21, minimum=5, maximum=100)

# ============================================================
# Entry
# ============================================================
ENTRY_RETEST_BUFFER_ATR: float = _float_env("FALLBACK4_ENTRY_RETEST_BUFFER_ATR", 0.1, minimum=0.0, maximum=1.0)
RETRACEMENT_MAX_CANDLES: int = _int_env("FALLBACK4_RETRACEMENT_MAX_CANDLES", 10, minimum=1, maximum=50)
M1_STOP_SCALING: float = _float_env("FALLBACK4_M1_STOP_SCALING", 0.6, minimum=0.1, maximum=1.0)

# ============================================================
# Risk parameters
# ============================================================
RISK_PERCENT_M5: float = _float_env("FALLBACK4_RISK_PERCENT_M5", 0.35, minimum=0.05, maximum=5.0)
RISK_PERCENT_M1: float = _float_env("FALLBACK4_RISK_PERCENT_M1", 0.15, minimum=0.05, maximum=2.0)
MIN_RR: float = _float_env("FALLBACK4_MIN_RR", 1.5, minimum=0.5, maximum=10.0)
MAX_SPREAD_POINTS_M5: int = _int_env("FALLBACK4_MAX_SPREAD_POINTS_M5", 30, minimum=1, maximum=500)
MAX_SPREAD_POINTS_M1: int = _int_env("FALLBACK4_MAX_SPREAD_POINTS_M1", 15, minimum=1, maximum=200)
MAX_TRADES_PER_DAY: int = _int_env("FALLBACK4_MAX_TRADES_PER_DAY", 2, minimum=1, maximum=20)
MAX_LOSSES_PER_DAY: int = _int_env("FALLBACK4_MAX_LOSSES_PER_DAY", 2, minimum=1, maximum=20)
MAX_CONSECUTIVE_LOSSES: int = _int_env("FALLBACK4_MAX_CONSECUTIVE_LOSSES", 3, minimum=1, maximum=10)
MAX_DRAWDOWN_PERCENT: float = _float_env("FALLBACK4_MAX_DRAWDOWN_PERCENT", 5.0, minimum=1.0, maximum=50.0)
MAX_EXPOSURE_PERCENT: float = _float_env("FALLBACK4_MAX_EXPOSURE_PERCENT", 10.0, minimum=1.0, maximum=100.0)
PER_SYMBOL_COOLDOWN: int = _int_env("FALLBACK4_PER_SYMBOL_COOLDOWN", 3600, minimum=300, maximum=86400)
PER_SETUP_COOLDOWN: int = _int_env("FALLBACK4_PER_SETUP_COOLDOWN", 7200, minimum=600, maximum=172800)
DAILY_LOSS_LIMIT: float = _float_env("FALLBACK4_DAILY_LOSS_LIMIT", 2.0, minimum=0.5, maximum=20.0)
WEEKLY_LOSS_LIMIT: float = _float_env("FALLBACK4_WEEKLY_LOSS_LIMIT", 5.0, minimum=1.0, maximum=50.0)

# ============================================================
# Take profit — partial closes
# ============================================================
TP1_ALLOC: float = _float_env("FALLBACK4_TP1_ALLOC", 20.0, minimum=0.0, maximum=100.0)
TP2_ALLOC: float = _float_env("FALLBACK4_TP2_ALLOC", 30.0, minimum=0.0, maximum=100.0)
TP3_ALLOC: float = _float_env("FALLBACK4_TP3_ALLOC", 25.0, minimum=0.0, maximum=100.0)
TP4_ALLOC: float = _float_env("FALLBACK4_TP4_ALLOC", 25.0, minimum=0.0, maximum=100.0)

# ============================================================
# Session filters
# ============================================================
SESSIONS: List[str] = _csv_strs("FALLBACK4_SESSIONS", "london,ny,london_ny_overlap")

# ============================================================
# Countertrend mode
# ============================================================
COUNTERTREND_ENABLED: bool = _bool_env("FALLBACK4_COUNTERTREND_ENABLED", False)

# ============================================================
# Scoring weights (must total 100)
# ============================================================
WEIGHT_RANGE_QUALITY: int = _int_env("FALLBACK4_WEIGHT_RANGE_QUALITY", 15, minimum=0, maximum=100)
WEIGHT_BOUNDARY_LIQUIDITY: int = _int_env("FALLBACK4_WEIGHT_BOUNDARY_LIQ", 10, minimum=0, maximum=100)
WEIGHT_SWEEP_QUALITY: int = _int_env("FALLBACK4_WEIGHT_SWEEP", 15, minimum=0, maximum=100)
WEIGHT_FAILED_BREAKOUT: int = _int_env("FALLBACK4_WEIGHT_FAILED_BREAKOUT", 15, minimum=0, maximum=100)
WEIGHT_RECLAIM: int = _int_env("FALLBACK4_WEIGHT_RECLAIM", 15, minimum=0, maximum=100)
WEIGHT_DISPLACEMENT: int = _int_env("FALLBACK4_WEIGHT_DISPLACEMENT", 10, minimum=0, maximum=100)
WEIGHT_STRUCTURE_CHANGE: int = _int_env("FALLBACK4_WEIGHT_STRUCTURE_CHANGE", 10, minimum=0, maximum=100)
WEIGHT_ENTRY_ZONE: int = _int_env("FALLBACK4_WEIGHT_ENTRY_ZONE", 5, minimum=0, maximum=100)
WEIGHT_RISK_REWARD: int = _int_env("FALLBACK4_WEIGHT_RISK_REWARD", 5, minimum=0, maximum=100)

SCORE_MINIMUM: int = _int_env("FALLBACK4_SCORE_MINIMUM", 80, minimum=0, maximum=100)
SCORE_WATCH: int = _int_env("FALLBACK4_SCORE_WATCH", 70, minimum=0, maximum=100)


def validate() -> List[str]:
    """Validate configuration and return list of warnings."""
    warnings = []
    if MIN_SWEEP_PENETRATION_ATR >= MAX_SWEEP_PENETRATION_ATR:
        warnings.append(f"MIN_SWEEP_PENETRATION_ATR ({MIN_SWEEP_PENETRATION_ATR}) >= MAX ({MAX_SWEEP_PENETRATION_ATR})")
    if MIN_RANGE_WIDTH_ATR >= MAX_RANGE_WIDTH_ATR:
        warnings.append(f"MIN_RANGE_WIDTH_ATR ({MIN_RANGE_WIDTH_ATR}) >= MAX ({MAX_RANGE_WIDTH_ATR})")
    if MACD_ENABLED and MACD_FAST >= MACD_SLOW:
        warnings.append(f"MACD_FAST ({MACD_FAST}) >= MACD_SLOW ({MACD_SLOW})")
    if SMA_ENABLED and SMA_FAST >= SMA_SLOW:
        warnings.append(f"SMA_FAST ({SMA_FAST}) >= SMA_SLOW ({SMA_SLOW})")
    total_weight = WEIGHT_RANGE_QUALITY + WEIGHT_BOUNDARY_LIQUIDITY + WEIGHT_SWEEP_QUALITY + \
                   WEIGHT_FAILED_BREAKOUT + WEIGHT_RECLAIM + WEIGHT_DISPLACEMENT + \
                   WEIGHT_STRUCTURE_CHANGE + WEIGHT_ENTRY_ZONE + WEIGHT_RISK_REWARD
    if total_weight != 100:
        warnings.append(f"Scoring weights total {total_weight}, expected 100")
    if RECLAIM_MODE == "aggressive" and not COUNTERTREND_ENABLED:
        warnings.append("Aggressive reclaim mode may produce false signals; consider strict or balanced")
    return warnings
