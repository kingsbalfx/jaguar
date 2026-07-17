"""
FALLBACK STRATEGY 3 - Signal Generation
=========================================
Generates final trade signal with unique setup fingerprint.
Provides identity context for duplicate detection.
"""

import hashlib
import time
from typing import Any, Dict, List, Optional

from . import config
from .models import FallbackSetupResult, FallbackTradeRequest


def generate_fallback3_signal(
    result: FallbackSetupResult,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    lot: float,
) -> FallbackTradeRequest:
    """
    Generate a trade request from a successful Fallback 3 setup.
    
    Returns FallbackTradeRequest compatible with main.py execution pipeline.
    """
    if not result.direction:
        raise ValueError("Cannot generate signal without direction")

    setup_id = result.setup_id or _build_fingerprint(
        result.symbol,
        result.direction,
        result.sweep.sweep_level,
        result.choch.close_level,
    )

    identity_context = {
        "strategy": "fallback3",
        "mode": config.ACTIVATION_MODE if hasattr(config, 'ACTIVATION_MODE') else "balanced",
        "setup_id": setup_id,
        "score": result.score,
        "sweep_classification": result.sweep.classification,
        "choch_detected": result.choch.detected,
        "macd_confirmed": result.macd.confirmed,
        "sma_confirmed": result.sma.confirmed,
        "entry_zone_midpoint": result.entry_zone.midpoint,
        "entry_zone_fib_level": result.entry_zone.fib_level,
        "entry_trigger": result.entry_trigger,
    }

    request = FallbackTradeRequest(
        symbol=result.symbol,
        direction=result.direction,
        entry=entry_price,
        sl=stop_loss,
        tp=take_profit,
        lot=lot,
        order_type="market",
        strategy="fallback3",
        identity_context=identity_context,
    )

    return request


def _build_fingerprint(
    symbol: str,
    direction: str,
    liquidity_level: Optional[float],
    choch_level: Optional[float],
) -> str:
    """
    Build a unique setup fingerprint for duplicate detection.
    """
    raw = f"{symbol}|{direction}|{liquidity_level or 0.0}|{choch_level or 0.0}|fb3|{int(time.time() / 86400)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def setup_identity(
    symbol: str,
    direction: str,
    liquidity_level: Optional[float],
    choch_level: Optional[float],
    entry_zone_midpoint: Optional[float] = None,
) -> str:
    """
    Generate unique identity string for risk protection system.
    Compatible with risk.protection.setup_identity() format.
    """
    zone_low = min(float(liquidity_level or 0.0), float(choch_level or 0.0))
    zone_high = max(float(liquidity_level or 0.0), float(choch_level or 0.0))
    if entry_zone_midpoint is not None:
        zone_low = min(zone_low, float(entry_zone_midpoint))
        zone_high = max(zone_high, float(entry_zone_midpoint))
    if zone_low == zone_high and entry_zone_midpoint is not None:
        zone_low -= 0.00001
        zone_high += 0.00001

    return f"{symbol}|{direction}|{zone_low:.8f}|{zone_high:.8f}|fb3"
