"""
FALLBACK STRATEGY 4 - Signal Generation
=========================================
Generates final trade signal with unique range-based setup fingerprint.
Provides identity context for duplicate detection across all 4 strategies.
"""

import hashlib
import time
from typing import Any, Dict, List, Optional

from . import config
from .models import Fallback4SetupResult, Fallback4TradeRequest


def generate_fallback4_signal(
    result: Fallback4SetupResult,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    lot: float,
    targets: List[Dict[str, Any]],
) -> Fallback4TradeRequest:
    """
    Generate a trade request from a successful Fallback 4 setup.
    
    Returns Fallback4TradeRequest compatible with main.py execution pipeline.
    Includes comprehensive identity_context for duplicate prevention
    across all 4 strategies.
    """
    if not result.direction:
        raise ValueError("Cannot generate signal without direction")

    range_data = result.range_data
    sweep = result.sweep

    setup_id = result.setup_id or _build_fingerprint(
        symbol=result.symbol,
        direction=result.direction,
        range_high=range_data.range_high,
        range_low=range_data.range_low,
        sweep_side=sweep.side or "none",
        sweep_extreme=sweep.extreme_price,
        execution_tf=result.execution_timeframe,
    )

    identity_context = {
        "strategy": "fallback4",
        "mode": config.EXECUTION_MODE,
        "entry_model": config.ENTRY_MODEL,
        "setup_id": setup_id,
        "execution_timeframe": result.execution_timeframe,
        "context_timeframe": result.context_timeframe,
        "score": result.score,
        "range_high": range_data.range_high,
        "range_low": range_data.range_low,
        "range_width_atr": range_data.range_width_atr,
        "range_quality": range_data.quality_score,
        "sweep_side": sweep.side,
        "sweep_extreme": sweep.extreme_price,
        "sweep_classification": sweep.classification,
        "sweep_penetration_atr": sweep.penetration_atr,
        "reclaim_mode": result.reclaim.mode_used,
        "reclaim_strength": result.reclaim.reclaim_strength,
        "displacement_score": result.displacement.score,
        "structure_change_method": result.structure_change.method,
        "structure_change_level": result.structure_change.swing_level,
        "entry_model_used": result.entry.model,
        "target_tp1": result.targets[0].level if len(result.targets) > 0 else None,
        "target_tp2": result.targets[1].level if len(result.targets) > 1 else None,
        "target_tp3": result.targets[2].level if len(result.targets) > 2 else None,
        "target_final": result.targets[3].level if len(result.targets) > 3 else None,
        "context_bias": result.context_bias,
    }

    request = Fallback4TradeRequest(
        symbol=result.symbol,
        direction=result.direction,
        entry=entry_price,
        sl=stop_loss,
        tp=take_profit,
        lot=lot,
        order_type="market",
        strategy="fallback4",
        identity_context=identity_context,
    )

    return request


def _build_fingerprint(
    symbol: str,
    direction: str,
    range_high: float,
    range_low: float,
    sweep_side: str,
    sweep_extreme: float,
    execution_tf: str,
) -> str:
    """
    Build a unique setup fingerprint for duplicate detection
    across ALL strategies including Fallback 3.
    
    Combines range identity + sweep details so the same range event
    cannot be traded twice by any strategy.
    """
    raw = (
        f"{symbol}|{direction}|"
        f"{range_high:.8f}|{range_low:.8f}|"
        f"{sweep_side}|{sweep_extreme:.8f}|"
        f"{execution_tf}|"
        f"fb4|{int(time.time() / 86400)}"
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def setup_identity(
    symbol: str,
    direction: str,
    range_high: float,
    range_low: float,
    sweep_side: str,
    sweep_extreme: float,
) -> str:
    """
    Generate unique identity string for risk protection system.
    Compatible with risk.protection.setup_identity() format.
    
    Uses range boundaries so the global risk system can detect
    overlapping setups across different strategies.
    """
    zone_low = min(float(range_low), float(sweep_extreme))
    zone_high = max(float(range_high), float(sweep_extreme))
    if zone_low == zone_high:
        zone_low -= 0.00001
        zone_high += 0.00001

    return f"{symbol}|{direction}|{zone_low:.8f}|{zone_high:.8f}|fb4"
