"""
FALLBACK STRATEGY 5 — Signal Generation
==========================================
Generates the trade request dict compatible with main.py's execute_trade.
"""

import hashlib
import time
from typing import Dict, Any, Optional

from . import config
from .daily_stats import get_stats


def setup_identity(
    symbol: str,
    direction: str,
    model: str,
    setup_data: dict,
) -> str:
    """
    Generate a unique setup identity string.
    Used for duplicate detection and global risk registration.
    """
    raw = (
        f"{symbol}|{direction}|{model}|"
        f"{setup_data.get('entry_price', 0):.8f}|"
        f"{setup_data.get('pullback_to_level', 0):.8f}|"
        f"{setup_data.get('consolidation_high', 0):.8f}|"
        f"{int(time.time())}"
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def generate_fallback5_signal(
    symbol: str,
    direction: str,
    model: str,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    lot: float,
    rr: float,
    score: int,
    setup_data: dict,
    base_risk: float,
    active_risk: float,
    session_r: float,
) -> dict:
    """Generate the trade request dict compatible with main.py's execute_trade."""
    identity = setup_identity(symbol, direction, model, setup_data)

    return {
        "symbol": symbol,
        "direction": direction,
        "entry": entry_price,
        "sl": stop_loss,
        "tp": take_profit,
        "lot": lot,
        "order_type": "market",
        "identity": identity,
        "strategy": "fallback5",
        "model": model,
        "score": score,
        "risk_reward": round(rr, 2),
        "base_risk_percent": base_risk,
        "active_risk_percent": active_risk,
        "session_r": session_r,
        "setup_data": setup_data,
        "execution_timeframe": config.EXECUTION_TIMEFRAME,
        "timeframe": config.SETUP_TIMEFRAME,
        "confidence": score / 100.0,
    }
