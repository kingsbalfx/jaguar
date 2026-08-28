"""
FALLBACK STRATEGY 5 — Risk & Position Sizing
==============================================
Risk gates, position sizing with profit-step scaling, loss streak management,
and temporary symbol pause on consecutive losses.
"""

import os
import time
from datetime import datetime, timezone
from typing import Optional, Tuple, Dict, Any

from . import config
from .daily_stats import DailyStatsTracker
from .fb5_logging import log_skip


# In-memory symbol pause tracking
_symbol_pause: Dict[str, float] = {}  # symbol -> pause_until_timestamp


def reset_symbol_pause(symbol: str) -> None:
    """Clear symbol pause for a symbol."""
    _symbol_pause.pop(symbol, None)


def _check_symbol_paused(symbol: str) -> Tuple[bool, str]:
    """Check if a symbol is temporarily paused."""
    pause_until = _symbol_pause.get(symbol)
    if pause_until and time.time() < pause_until:
        remaining = int(pause_until - time.time())
        return True, f"symbol_paused:{remaining}s_remaining"
    return False, ""


def set_symbol_pause(symbol: str, minutes: int = 60) -> None:
    """Pause a symbol for the specified number of minutes."""
    _symbol_pause[symbol] = time.time() + minutes * 60


def check_risk_gate(
    symbol: str,
    direction: str,
    account: Dict[str, Any],
    positions: list,
    stats: DailyStatsTracker,
) -> Tuple[bool, str]:
    """
    Check all risk gates before allowing a new trade.
    Returns (passed, reason).
    """
    # 1. Master switch
    if not config.FALLBACK5_ENABLED:
        return False, "fallback5_disabled"

    # 2. Symbol paused?
    paused, reason = _check_symbol_paused(symbol)
    if paused:
        return False, reason

    # 3. Max trades per symbol per session
    symbol_trades = stats.get_symbol_trades(symbol)
    if symbol_trades >= config.MAX_TRADES_PER_SYMBOL_PER_SESSION:
        return False, f"max_symbol_trades_{symbol_trades}>={config.MAX_TRADES_PER_SYMBOL_PER_SESSION}"

    # 4. Max trades per session
    session_trades = stats.get_session_trade_count()
    if session_trades >= config.MAX_TRADES_PER_SESSION:
        return False, f"max_session_trades_{session_trades}>={config.MAX_TRADES_PER_SESSION}"

    # 5. Max daily trades
    daily_trades = stats.get_daily_trade_count()
    if daily_trades >= config.MAX_DAILY_TRADES:
        return False, f"max_daily_trades_{daily_trades}>={config.MAX_DAILY_TRADES}"

    # 6. Max session loss in R
    session_loss_r = abs(stats.get_session_r())
    if session_loss_r >= config.MAX_SESSION_LOSS_R:
        return False, f"session_loss_r_{session_loss_r:.2f}>={config.MAX_SESSION_LOSS_R:.2f}"

    # 7. Max daily loss in R
    daily_loss_r = abs(stats.get_daily_r()) if stats.get_daily_r() < 0 else 0
    if daily_loss_r >= config.MAX_DAILY_LOSS_R:
        return False, f"daily_loss_r_{daily_loss_r:.2f}>={config.MAX_DAILY_LOSS_R:.2f}"

    # 8. Consecutive losses pause
    consecutive_losses = stats.get_consecutive_losses()
    if consecutive_losses >= config.MAX_CONSECUTIVE_LOSSES:
        set_symbol_pause(symbol, 60)
        return False, f"consecutive_losses_{consecutive_losses}>={config.MAX_CONSECUTIVE_LOSSES}"

    # 9. Free margin check
    margin_free = float(account.get("margin_free", 0) or 0)
    if margin_free <= 0:
        return False, "no_free_margin"

    # 10. Existing position check
    if not config.PYRAMIDING_ENABLED:
        for pos in (positions or []):
            if str(pos.get("symbol") or "").upper().replace("/", "") == symbol:
                return False, "position_already_open"

    return True, "risk_gate_passed"


def calculate_active_risk(
    stats: DailyStatsTracker,
) -> Tuple[float, float, float]:
    """
    Calculate active risk percent based on mode.
    Returns (base_risk_pct, active_risk_pct, session_r).
    """
    base_risk = config.BASE_RISK_PERCENT
    active_risk = base_risk
    session_r = stats.get_session_r()

    if config.RISK_MODE == "profit_step":
        # Profit-step scaling: increase risk only after realised session profit
        consecutive_wins = stats.get_consecutive_wins()
        consecutive_losses = stats.get_consecutive_losses()

        # After any loss, always reset to base
        if consecutive_losses >= 1:
            return base_risk, base_risk, session_r

        # Must have realised profit before scaling
        if session_r > 0:
            steps = 0
            profit_threshold = config.PROFIT_STEP_THRESHOLD_R
            step = config.PROFIT_STEP

            if session_r >= profit_threshold and consecutive_wins >= 1:
                steps = min(
                    int(session_r / profit_threshold),
                    consecutive_wins,
                )

            active_risk = min(
                base_risk + steps * step,
                config.MAX_RISK_PERCENT,
            )

    return base_risk, active_risk, session_r


def calculate_position_size(
    symbol: str,
    entry_price: float,
    stop_loss: float,
    account: Dict[str, Any],
    active_risk_pct: float,
    profile: dict,
    mt5_connector=None,
) -> Tuple[float, float]:
    """
    Calculate position size based on active risk.
    Returns (lot_size, risk_amount).
    """
    risk_amount = float(account.get("balance", 0) or 0) * (active_risk_pct / 100.0)

    if risk_amount <= 0:
        return 0.0, 0.0

    risk_in_price = abs(entry_price - stop_loss)
    if risk_in_price <= 0:
        return 0.0, 0.0

    # Try MT5 connector
    lot = 0.0
    if mt5_connector and hasattr(mt5_connector, "calculate_volume_for_risk"):
        try:
            lot = mt5_connector.calculate_volume_for_risk(
                symbol, entry_price, stop_loss, risk_amount,
            )
        except Exception:
            lot = 0.0

    if lot <= 0:
        # Fallback manual calculation
        single_point_value = profile.get("single_point_value", 0.0001)
        pip_value = risk_in_price / single_point_value * 0.1  # rough
        if pip_value > 0:
            lot = risk_amount / (pip_value * risk_in_price * 10)
            lot = max(0.01, min(round(lot, 2), 10.0))

    return max(0.0, lot), risk_amount


def calculate_stop_loss(
    model_result: dict,
    direction: str,
    entry_price: float,
    atr_value: float,
    profile: dict,
    trend_direction: str,
    htf_candles: list,
    point: float,
) -> Tuple[float, float, str]:
    """
    Calculate stop loss using hybrid method.
    Returns (stop_price, risk_distance, method_used).
    """
    # Method: Hybrid — best of structure, ATR, and sweep-based stops
    stop_options = []

    # 1. Structure-based: below the pullback/sweep extreme
    if model_result.get("pullback_to_level"):
        if direction == "buy":
            stop = model_result["pullback_to_level"] - profile.get("stop_buffer_points", 5) * point
        else:
            stop = model_result["pullback_to_level"] + profile.get("stop_buffer_points", 5) * point
        stop_options.append(("structure", stop))

    # 2. Sweep-based: below/above the swept level
    if model_result.get("sweep_extreme"):
        if direction == "buy":
            stop = model_result["sweep_extreme"] - profile.get("stop_buffer_points", 5) * point
        else:
            stop = model_result["sweep_extreme"] + profile.get("stop_buffer_points", 5) * point
        stop_options.append(("sweep", stop))

    # 3. ATR-based
    if atr_value > 0:
        if direction == "buy":
            stop = entry_price - atr_value * 0.8
        else:
            stop = entry_price + atr_value * 0.8
        stop_options.append(("atr", stop))

    # 4. Protected structure level
    from .trend import get_protected_levels, BULLISH, BEARISH
    protected = get_protected_levels(htf_candles, trend_direction)
    if direction == "buy" and protected.get("protected_low"):
        stop_options.append(("protected_low", protected["protected_low"]))
    elif direction == "sell" and protected.get("protected_high"):
        stop_options.append(("protected_high", protected["protected_high"]))

    if not stop_options:
        return 0.0, 0.0, "no_stop"

    # Select: for hybrid, take the tightest valid stop
    valid_stops = []
    for method, price in stop_options:
        if price <= 0:
            continue
        if direction == "buy":
            if price < entry_price:
                valid_stops.append((method, price))
        else:
            if price > entry_price:
                valid_stops.append((method, price))

    if not valid_stops:
        return 0.0, 0.0, "no_valid_stop"

    # Pick the tightest (closest to entry) for buy, or furthest for sell
    if config.STOP_METHOD == "structure":
        choice = min(valid_stops, key=lambda x: x[1]) if direction == "buy" else max(valid_stops, key=lambda x: x[1])
    elif config.STOP_METHOD == "sweep":
        sweep_stops = [s for s in valid_stops if s[0] == "sweep"]
        choice = sweep_stops[0] if sweep_stops else valid_stops[0]
    elif config.STOP_METHOD == "atr":
        atr_stops = [s for s in valid_stops if s[0] == "atr"]
        choice = atr_stops[0] if atr_stops else valid_stops[0]
    else:  # hybrid (default)
        # Weight toward the tightest stop but ensure minimum distance
        if direction == "buy":
            candidate = min(valid_stops, key=lambda x: x[1])
        else:
            candidate = max(valid_stops, key=lambda x: x[1])
        choice = candidate

    method, stop_price = choice
    risk_distance = abs(entry_price - stop_price)

    return stop_price, risk_distance, method


def calculate_take_profit(
    entry_price: float,
    stop_loss: float,
    direction: str,
    atr_value: float,
    risk_distance: float,
    setup_candles: list,
) -> Tuple[float, float, float, dict]:
    """
    Calculate take profit levels.
    Returns (tp1, tp2, final_tp, targets_dict).
    """
    if risk_distance <= 0:
        risk_distance = atr_value * 0.5 if atr_value > 0 else 0.001

    tp1 = entry_price + (risk_distance * config.TP1_MULTIPLIER * (1 if direction == "buy" else -1))
    tp2 = entry_price + (risk_distance * config.TP2_MULTIPLIER * (1 if direction == "buy" else -1))

    rr1 = abs(tp1 - entry_price) / risk_distance if risk_distance > 0 else 0
    rr2 = abs(tp2 - entry_price) / risk_distance if risk_distance > 0 else 0

    if config.TP_FULL_CLOSE_AT == "TP1":
        final_tp = tp1
    else:
        final_tp = tp2

    targets = {
        "tp1": tp1,
        "tp2": tp2,
        "final_tp": final_tp,
        "rr1": round(rr1, 2),
        "rr2": round(rr2, 2),
    }

    return tp1, tp2, final_tp, targets


def check_duplicate_setup(
    symbol: str,
    direction: str,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    session_id: str,
    stats: DailyStatsTracker,
) -> Tuple[bool, str]:
    """
    Check for duplicate / same-setup re-entry.
    Returns (passes, reason).
    """
    # Check if we already have an active F5 position
    active = stats.get_active_setup(symbol)
    if active:
        return False, "active_setup_pending"

    # Check for recent same-direction setups within close range
    recent = stats.get_recent_setups(symbol, limit=3)
    for setup in recent:
        if setup.get("direction") != direction:
            continue
        prev_entry = setup.get("entry_price", 0)
        if prev_entry and abs(prev_entry - entry_price) / max(abs(entry_price), 0.0001) < 0.002:
            return False, "duplicate_entry_price"

    return True, "no_duplicate"


def check_spread_acceptable(
    spread: float,
    target_distance: float,
    atr_value: float,
    profile: dict,
) -> Tuple[bool, str]:
    """Check spread is acceptable relative to target and ATR."""
    if spread <= 0:
        return False, "spread_zero"

    if target_distance > 0 and spread / target_distance > config.SPREAD_MAX_AS_TARGET_FRACTION:
        return False, f"spread/{target_distance:.5f}={spread/target_distance:.2%}>{config.SPREAD_MAX_AS_TARGET_FRACTION:.0%}"

    if atr_value > 0 and spread / atr_value > config.SPREAD_MAX_ATR_FRACTION:
        return False, f"spread/atr={spread/atr_value:.4f}>{config.SPREAD_MAX_ATR_FRACTION:.4f}"

    max_points = profile.get("spread_max_points", 100)
    if spread > max_points * point_value(profile.get("single_point_value", 0.0001)):
        return False, f"spread_{spread:.5f}>symbol_max"

    return True, "spread_ok"


def point_value(pip: float) -> float:
    """Return point value from single_point_value."""
    return pip or 0.0001
