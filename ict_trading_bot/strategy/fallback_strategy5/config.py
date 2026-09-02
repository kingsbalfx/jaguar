"""
FALLBACK STRATEGY 5 — Configuration
=====================================
All configurable parameters for the session-based day-trend continuation scalper.
"""

import os
from typing import Dict, Any


# ============================================================
# Master Switch
# ============================================================
FALLBACK5_ENABLED: bool = os.getenv("FALLBACK5_ENABLED", "true").lower() in ("1", "true", "yes")


# ============================================================
# Allowed Symbols & Alias Map
# ============================================================
ALLOWED_SYMBOLS: tuple = ("EURUSD", "XAUUSD", "BTCUSD", "AUDJPY")

SYMBOL_ALIAS_MAP: Dict[str, str] = {
    # EURUSD aliases
    "EURUSD": "EURUSD",
    "EURUSD.A": "EURUSD",
    "EURUSDM": "EURUSD",
    "EUR/USD": "EURUSD",
    # XAUUSD aliases
    "XAUUSD": "XAUUSD",
    "XAUUSD.A": "XAUUSD",
    "XAUUSDM": "XAUUSD",
    "GOLD": "XAUUSD",
    "GOLDUSD": "XAUUSD",
    "XAU/USD": "XAUUSD",
    # BTCUSD aliases
    "BTCUSD": "BTCUSD",
    "BTCUSDM": "BTCUSD",
    "XBTUSD": "BTCUSD",
    "BTC/USD": "BTCUSD",
    "BTC": "BTC",
    # AUDJPY aliases
    "AUDJPY": "AUDJPY",
    "AUDJPYM": "AUDJPY",
    "AUD/JPY": "AUDJPY",
}


def resolve_canonical_symbol(raw_symbol: str) -> str:
    """Map a broker symbol to one of the four approved instruments, or return empty string."""
    clean = str(raw_symbol or "").strip().upper().replace("/", "").replace("-", "").replace("_", "").replace(".", "")
    return SYMBOL_ALIAS_MAP.get(clean, "")


# ============================================================
# Session Schedule (in configured timezone)
# ============================================================
SESSION_TIMEZONE: str = os.getenv("FALLBACK5_TIMEZONE", "UTC")

SESSION_1_START_HOUR: int = int(os.getenv("FALLBACK5_SESSION1_START", "8"))
SESSION_1_END_HOUR: int = int(os.getenv("FALLBACK5_SESSION1_END", "12"))
SLEEP_START_HOUR: int = int(os.getenv("FALLBACK5_SLEEP_START", "12"))
SLEEP_END_HOUR: int = int(os.getenv("FALLBACK5_SLEEP_END", "14"))
SESSION_2_START_HOUR: int = int(os.getenv("FALLBACK5_SESSION2_START", "14"))
SESSION_2_END_HOUR: int = int(os.getenv("FALLBACK5_SESSION2_END", "20"))

# Entry cut-off before session ends (minutes)
SESSION_1_CUTOFF_MINUTES: int = int(os.getenv("FALLBACK5_SESSION1_CUTOFF_MIN", "15"))
SESSION_2_CUTOFF_MINUTES: int = int(os.getenv("FALLBACK5_SESSION2_CUTOFF_MIN", "30"))


# ============================================================
# Timeframe Architecture
# ============================================================
# Mode A: H1 trend + M15 context + M5 entry
# Mode B: M15 trend + M5 setup + M1 entry
# Mode C: H1 trend + M5 setup + M1 execution
# Per-symbol mode override
TREND_MODE_BY_SYMBOL: Dict[str, str] = {
    "EURUSD": "B",
    "XAUUSD": "C",
    "BTCUSD": "C",
    "AUDJPY": "B",
}

TREND_TIMEFRAME: str = "H1"       # Primary trend analysis
CONTEXT_TIMEFRAME: str = "M15"    # Pullback context & session structure
SETUP_TIMEFRAME: str = "M5"       # Setup detection
EXECUTION_TIMEFRAME: str = "M1"   # Precision execution timing


# ============================================================
# EMA Trend Filter
 EMA_FAST: int = int(os.getenv("FALLBACK5_EMA_FAST", "20"))
EMA_MEDIUM: int = int(os.getenv("FALLBACK5_EMA_MEDIUM", "50"))
EMA_SLOW: int = int(os.getenv("FALLBACK5_EMA_SLOW", "200"))


# ============================================================
# ADX Trend Strength
# ============================================================
ADX_PERIOD: int = int(os.getenv("FALLBACK5_ADX_PERIOD", "14"))
ADX_WEAK_THRESHOLD: int = int(os.getenv("FALLBACK5_ADX_WEAK", "18"))
ADX_MINIMUM_FOR_TRADE: int = int(os.getenv("FALLBACK5_ADX_MINIMUM", "20"))
ADX_STRONG_THRESHOLD: int = int(os.getenv("FALLBACK5_ADX_STRONG", "25"))
ADX_EXTREME_THRESHOLD: int = int(os.getenv("FALLBACK5_ADX_EXTREME", "40"))


# ============================================================
# ATR / Volatility
# ============================================================
ATR_PERIOD: int = 14
VOLATILITY_LOW_ATR_RATIO: float = 0.0005   # Min ATR fraction of price
VOLATILITY_HIGH_PERCENTILE: float = 0.80   # Above this = elevated
VOLATILITY_EXTREME_PERCENTILE: float = 0.95
VOLATILITY_LOOKBACK_DAYS: int = 10


# ============================================================
# Spread Filter (scaled per symbol via profiles)
# ============================================================
SPREAD_MAX_AS_TARGET_FRACTION: float = 0.15  # Reject if spread > 15% of target
SPREAD_MAX_ATR_FRACTION: float = 0.05        # Reject if spread > 5% of ATR
SPREAD_ABRUPT_EXPANSION_FACTOR: float = 2.5  # Compared to rolling average


# ============================================================
# Entry Confirmation
# ============================================================
CONFIRMATION_MIN_CLOSED_CANDLES: int = 1       # At least 1 closed candle
CONFIRMATION_MIN_BODY_RATIO: float = 0.30     # Minimum body/range for confirmation candle
CONFIRMATION_MAX_WICK_RATIO: float = 0.70     # Maximum wick/range for confirmation


# ============================================================
# Anti-Chase Filter
# ============================================================
MAX_DISTANCE_FROM_EMA20_ATR: float = float(os.getenv("FALLBACK5_MAX_DISTANCE_ATR", "1.5"))
MIN_TARGET_ROOM_ATR: float = float(os.getenv("FALLBACK5_MIN_TARGET_ATR", "0.5"))


# ============================================================
# Stop Loss & Take Profit
# ============================================================
STOP_METHOD: str = "hybrid"   # "structure", "sweep", "atr", "hybrid"
TP1_MULTIPLIER: float = 0.75  # 0.75R
TP2_MULTIPLIER: float = 1.25  # 1.25R
TP_FULL_CLOSE_AT: str = "TP1"  # "TP1" or "TP2"
TRAIL_STOP_ACTIVATE_AT_ATR: float = 1.0  # Activate trail after price moves 1 ATR


# ============================================================
# Time-Based Exit
# ============================================================
MAX_HOLDING_CANDLES_M5: int = int(os.getenv("FALLBACK5_MAX_CANDLES_M5", "18"))    # ~90 min
MAX_HOLDING_CANDLES_M1: int = int(os.getenv("FALLBACK5_MAX_CANDLES_M1", "30"))    # ~30 min


# ============================================================
# Break-Even
# ============================================================
BREAK_EVEN_AT_R: float = float(os.getenv("FALLBACK5_BREAK_EVEN_R", "0.75"))
BREAK_EVEN_COST_BUFFER_ATR: float = 0.1


# ============================================================
# Risk Parameters
# ============================================================
RISK_MODE: str = os.getenv("FALLBACK5_RISK_MODE", "fixed").lower()  # "fixed" or "profit_step"
BASE_RISK_PERCENT: float = float(os.getenv("FALLBACK5_BASE_RISK", "0.15"))
MAX_RISK_PERCENT: float = float(os.getenv("FALLBACK5_MAX_RISK", "0.50"))
PROFIT_STEP: float = float(os.getenv("FALLBACK5_PROFIT_STEP", "0.025"))
PROFIT_STEP_THRESHOLD_R: float = float(os.getenv("FALLBACK5_STEP_THRESHOLD", "1.0"))
MIN_RR: float = float(os.getenv("FALLBACK5_MIN_RR", "1.2"))


# ============================================================
# Trading Limits
# ============================================================
MAX_TRADES_PER_SYMBOL_PER_SESSION: int = int(os.getenv("FALLBACK5_MAX_PER_SYMBOL", "3"))
MAX_TRADES_PER_SESSION: int = int(os.getenv("FALLBACK5_MAX_PER_SESSION", "6"))
MAX_DAILY_TRADES: int = int(os.getenv("FALLBACK5_MAX_DAILY", "10"))
MAX_CONSECUTIVE_LOSSES: int = int(os.getenv("FALLBACK5_MAX_CONSECUTIVE_LOSSES", "2"))
MAX_SESSION_LOSS_R: float = float(os.getenv("FALLBACK5_SESSION_LOSS_R", "2.0"))
MAX_DAILY_LOSS_R: float = float(os.getenv("FALLBACK5_DAILY_LOSS_R", "3.0"))
PYRAMIDING_ENABLED: bool = False


# ============================================================
# Cooldown (in closed M1 candles)
# ============================================================
COOLDOWN_TP: int = int(os.getenv("FALLBACK5_COOLDOWN_TP", "3"))
COOLDOWN_BREAK_EVEN: int = int(os.getenv("FALLBACK5_COOLDOWN_BE", "5"))
COOLDOWN_SL: int = int(os.getenv("FALLBACK5_COOLDOWN_SL", "12"))
COOLDOWN_MANUAL: int = int(os.getenv("FALLBACK5_COOLDOWN_MANUAL", "15"))
COOLDOWN_2LOSS: int = int(os.getenv("FALLBACK5_COOLDOWN_2LOSS", "20"))


# ============================================================
# Session End Policy
# ============================================================
# "flat", "manage_only", "protected_hold"
SESSION_END_POLICY: str = os.getenv("FALLBACK5_SESSION_END_POLICY", "flat").lower()
PROTECTED_HOLD_MIN_PROFIT_R: float = float(os.getenv("FALLBACK5_PROTECTED_HOLD_R", "0.50"))


# ============================================================
# News Filter
# ============================================================
NEWS_BLACKOUT_MINUTES_BEFORE: int = int(os.getenv("FALLBACK5_NEWS_BEFORE", "30"))
NEWS_BLACKOUT_MINUTES_AFTER: int = int(os.getenv("FALLBACK5_NEWS_AFTER", "30"))


# ============================================================
# Setup Scoring Weights (total 100)
# ============================================================
SCORE_WEIGHTS: Dict[str, int] = {
    "htf_trend": 15,
    "structure_alignment": 15,
    "trend_strength": 10,
    "pullback_quality": 10,
    "entry_zone": 10,
    "liquidity_quality": 10,
    "displacement": 10,
    "confirmation_quality": 10,
    "target_room": 5,
    "spread_quality": 5,
    "session_quality": 5,
    "risk_reward": 5,
}

SCORE_MINIMUM: int = int(os.getenv("FALLBACK5_SCORE_MIN", "80"))
SCORE_WATCH: int = 70


# ============================================================
# Validation
# ============================================================
def validate() -> list:
    """Return list of config warnings."""
    warnings = []
    if not FALLBACK5_ENABLED:
        warnings.append("Fallback 5 is disabled")
    if RISK_MODE not in ("fixed", "profit_step"):
        warnings.append(f"RISK_MODE={RISK_MODE} not supported; using fixed")
    if RISK_MODE == "profit_step" and PROFIT_STEP <= 0:
        warnings.append("PROFIT_STEP <= 0; profit-step scaling disabled")
    if SESSION_END_POLICY not in ("flat", "manage_only", "protected_hold"):
        warnings.append(f"SESSION_END_POLICY={SESSION_END_POLICY} invalid; using flat")
    if BASE_RISK_PERCENT <= 0 or BASE_RISK_PERCENT > 2:
        warnings.append(f"BASE_RISK_PERCENT={BASE_RISK_PERCENT} out of range (0-2%)")
    if MAX_RISK_PERCENT < BASE_RISK_PERCENT:
        warnings.append(f"MAX_RISK_PERCENT={MAX_RISK_PERCENT} < BASE_RISK_PERCENT={BASE_RISK_PERCENT}")
    return warnings
