"""
FALLBACK STRATEGY 5 — Position Management
============================================
Ongoing management of active F5 trades:
- Trail stop at 1 ATR
- Break-even move at configurable R
- Time-based exit
- Session-end close
"""

from typing import Dict, Optional, Any

from . import config
from .indicators import atr, _to_float
from .daily_stats import DailyStatsTracker, get_stats
from .logging import log_management_action


def manage_active_position(
    position: dict,
    current_price: float,
    analysis: dict,
    point: float,
    stats: DailyStatsTracker,
) -> Optional[Dict[str, Any]]:
    """
    Manage an active Fallback 5 position.
    Returns an action dict or None if no action needed.
    
    Action dict format:
    {"action": "trail"|"break_even"|"partial_close"|"close"|"modify", ...}
    """
    symbol = position.get("symbol", "")
    direction = str(position.get("direction") or "").lower()
    entry = _to_float(position.get("entry", 0))
    original_sl = _to_float(position.get("sl", 0))
    original_tp = _to_float(position.get("tp", 0))
    lot = _to_float(position.get("volume", position.get("lot", 0.01)))

    if entry <= 0 or current_price <= 0:
        return None

    risk_distance = abs(entry - original_sl)
    if risk_distance <= 0:
        return None

    # Calculate current R
    if direction == "buy":
        current_r = (current_price - entry) / risk_distance
    else:
        current_r = (entry - current_price) / risk_distance

    # Extract candles from analysis
    htf_candles = (analysis.get("HTF") or {}).get("recent_candles", [])
    setup_candles = (analysis.get("M5") or {}).get("recent_candles", [])
    exec_candles = (analysis.get("M1") or {}).get("recent_candles", [])

    atr_value = atr(setup_candles or exec_candles, 14)
    if atr_value <= 0:
        atr_value = risk_distance * 1.5  # fallback

    # ============================================================
    # 1. Check break-even
    # ============================================================
    if current_r >= config.BREAK_EVEN_AT_R:
        # Move SL to entry + buffer
        buffer = atr_value * config.BREAK_EVEN_COST_BUFFER_ATR
        if direction == "buy":
            new_sl = entry + buffer
            if original_sl < new_sl:
                action = {
                    "action": "break_even",
                    "sl": new_sl,
                    "reason": f"break_even_at_{current_r:.2f}R",
                }
                log_management_action(symbol, position.get("ticket", 0), "break_even", {
                    "current_r": round(current_r, 2),
                    "new_sl": new_sl,
                })
                return action
        else:
            new_sl = entry - buffer
            if original_sl > new_sl or original_sl == 0:
                action = {
                    "action": "break_even",
                    "sl": new_sl,
                    "reason": f"break_even_at_{current_r:.2f}R",
                }
                log_management_action(symbol, position.get("ticket", 0), "break_even", {
                    "current_r": round(current_r, 2),
                    "new_sl": new_sl,
                })
                return action

    # ============================================================
    # 2. Check trail stop
    # ============================================================
    activate_at = config.TRAIL_STOP_ACTIVATE_AT_ATR
    if current_r >= activate_at:
        # Trail using ATR
        atr_distance = atr_value * 0.5
        if direction == "buy":
            trail_sl = current_price - atr_distance
            if trail_sl > original_sl:
                action = {
                    "action": "trail",
                    "sl": trail_sl,
                    "reason": f"trail_at_{current_r:.2f}R",
                }
                log_management_action(symbol, position.get("ticket", 0), "trail", {
                    "current_r": round(current_r, 2),
                    "new_sl": trail_sl,
                })
                return action
        else:
            trail_sl = current_price + atr_distance
            if trail_sl < original_sl or original_sl == 0:
                action = {
                    "action": "trail",
                    "sl": trail_sl,
                    "reason": f"trail_at_{current_r:.2f}R",
                }
                log_management_action(symbol, position.get("ticket", 0), "trail", {
                    "current_r": round(current_r, 2),
                    "new_sl": trail_sl,
                })
                return action

    # ============================================================
    # 3. Check time-based exit (after max holding period)
    # ============================================================
    holding_candles = position.get("holding_candles", 0)
    holding_timeframe = position.get("execution_timeframe", "M1")

    if holding_timeframe == "M5":
        max_candles = config.MAX_HOLDING_CANDLES_M5
    else:
        max_candles = config.MAX_HOLDING_CANDLES_M1

    if holding_candles >= max_candles:
        action = {
            "action": "close",
            "reason": f"time_based_exit:{holding_candles}_candles",
        }
        log_management_action(symbol, position.get("ticket", 0), "time_exit", {
            "holding_candles": holding_candles,
            "max_candles": max_candles,
        })
        return action

    # ============================================================
    # 4. Check stop loss (should be handled by MT5, but verify)
    # ============================================================
    if direction == "buy" and current_price <= original_sl:
        return {"action": "close", "reason": "stop_hit"}
    if direction == "sell" and current_price >= original_sl:
        return {"action": "close", "reason": "stop_hit"}

    # ============================================================
    # 5. Check take profit (hard to hit perfectly, TP1 close)
    # ============================================================
    if config.TP_FULL_CLOSE_AT == "TP1":
        tp_target = original_tp
    else:
        # TP2: check if we're close enough
        tp_target = original_tp

    if direction == "buy" and current_price >= tp_target * 0.995:
        return {"action": "close", "reason": "tp_hit"}
    if direction == "sell" and current_price <= tp_target * 1.005:
        return {"action": "close", "reason": "tp_hit"}

    return None
