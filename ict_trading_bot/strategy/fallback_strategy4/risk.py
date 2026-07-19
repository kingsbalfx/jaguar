"""
FALLBACK STRATEGY 4 - Risk Management
======================================
Fallback 4-specific risk controls. Does not bypass the global risk manager.
"""

import time
from typing import Any, Dict, List, Optional, Tuple

from . import config


def _to_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int_env(name, default):
    import os
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


# In-memory trade tracking (per process)
_trade_record: Dict[str, Any] = {
    "daily_trades": 0,
    "daily_losses": 0,
    "consecutive_losses": 0,
    "daily_pl": 0.0,
    "weekly_pl": 0.0,
    "day": "",
    "week": "",
    "drawdown_peak": None,
    "active_exposure": 0.0,
    "symbol_setups": {},  # symbol -> timestamp of last setup
    "setup_ids": set(),   # Unique setup IDs
    "range_setup_ids": set(),  # Range-specific setup IDs
}


def check_risk_gate(
    symbol: str,
    direction: str,
    account: Dict[str, Any],
    positions: List[Dict[str, Any]],
    ict_setup: Dict[str, Any],
    kingsbalfx_setup: Dict[str, Any],
    fallback3_setup: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str]:
    """
    Check ALL risk gates before activating Fallback 4.
    
    Returns (passed: bool, reason: str).
    """
    # 1. Verify higher-priority strategies all skipped
    if ict_setup and ict_setup.get("executable"):
        return False, "ICT_has_valid_trade"
    
    if kingsbalfx_setup and kingsbalfx_setup.get("executable"):
        return False, "Kingsbalfx_has_valid_trade"
    
    if fallback3_setup and fallback3_setup.get("executable"):
        return False, "Fallback3_has_valid_trade"

    # 2. Daily risk limits
    passed, reason = _check_daily_limits(account)
    if not passed:
        return False, reason

    # 3. Weekly limits
    passed, reason = _check_weekly_limits(account)
    if not passed:
        return False, reason

    # 4. Max drawdown
    passed, reason = _check_drawdown(account)
    if not passed:
        return False, reason

    # 5. Max exposure
    passed, reason = _check_exposure(positions, account)
    if not passed:
        return False, reason

    # 6. Max trades per day
    if _trade_record["daily_trades"] >= config.MAX_TRADES_PER_DAY:
        return False, f"max_daily_fallback4_trades: {_trade_record['daily_trades']}/{config.MAX_TRADES_PER_DAY}"

    # 7. Max consecutive losses
    if _trade_record["consecutive_losses"] >= config.MAX_CONSECUTIVE_LOSSES:
        return False, f"max_consecutive_losses: {_trade_record['consecutive_losses']}"

    # 8. Per-symbol cooldown
    symbol_key = f"{symbol}_{direction}"
    last_setup = _trade_record["symbol_setups"].get(symbol_key, 0)
    if time.time() - last_setup < config.PER_SYMBOL_COOLDOWN:
        remaining = config.PER_SYMBOL_COOLDOWN - (time.time() - last_setup)
        return False, f"symbol_cooldown: {remaining:.0f}s"

    return True, "risk_gate_passed"


def _check_daily_limits(account: Dict[str, Any]) -> Tuple[bool, str]:
    """Check daily loss limit."""
    today = time.strftime("%Y-%m-%d", time.gmtime())
    if _trade_record["day"] != today:
        _trade_record["daily_trades"] = 0
        _trade_record["daily_losses"] = 0
        _trade_record["consecutive_losses"] = 0
        _trade_record["daily_pl"] = 0.0
        _trade_record["day"] = today

    balance = _to_float(account.get("balance", 0.0))
    if balance > 0:
        daily_loss_pct = abs(_trade_record["daily_pl"]) / balance * 100.0
        if daily_loss_pct >= config.DAILY_LOSS_LIMIT:
            return False, f"daily_loss_limit: {daily_loss_pct:.1f}% >= {config.DAILY_LOSS_LIMIT:.1f}%"

    if _trade_record["daily_losses"] >= config.MAX_LOSSES_PER_DAY:
        return False, f"max_daily_losses: {_trade_record['daily_losses']}/{config.MAX_LOSSES_PER_DAY}"

    return True, "daily_limits_ok"


def _check_weekly_limits(account: Dict[str, Any]) -> Tuple[bool, str]:
    """Check weekly loss limit."""
    week = time.strftime("%Y-W%W", time.gmtime())
    if _trade_record["week"] != week:
        _trade_record["weekly_pl"] = 0.0
        _trade_record["week"] = week

    balance = _to_float(account.get("balance", 0.0))
    if balance > 0:
        weekly_loss_pct = abs(_trade_record["weekly_pl"]) / balance * 100.0
        if weekly_loss_pct >= config.WEEKLY_LOSS_LIMIT:
            return False, f"weekly_loss_limit: {weekly_loss_pct:.1f}% >= {config.WEEKLY_LOSS_LIMIT:.1f}%"

    return True, "weekly_limits_ok"


def _check_drawdown(account: Dict[str, Any]) -> Tuple[bool, str]:
    """Check drawdown from peak."""
    equity = _to_float(account.get("equity", 0.0))
    if _trade_record["drawdown_peak"] is None or equity > _trade_record["drawdown_peak"]:
        _trade_record["drawdown_peak"] = equity

    peak = _trade_record["drawdown_peak"]
    if peak and peak > 0:
        dd_pct = (peak - equity) / peak * 100.0 if peak > 0 else 0.0
        if dd_pct >= config.MAX_DRAWDOWN_PERCENT:
            return False, f"max_drawdown: {dd_pct:.1f}% >= {config.MAX_DRAWDOWN_PERCENT:.1f}%"

    return True, "drawdown_ok"


def _check_exposure(positions: List[Dict[str, Any]], account: Dict[str, Any]) -> Tuple[bool, str]:
    """Check total exposure."""
    balance = _to_float(account.get("balance", 0.0))
    if balance <= 0:
        return True, "no_balance_to_check"

    total_exposure = sum(
        _to_float(p.get("volume", 0.0)) * _to_float(p.get("price", 0.0))
        for p in positions if p.get("symbol")
    )
    exposure_pct = total_exposure / balance * 100.0 if balance > 0 else 0.0

    if exposure_pct >= config.MAX_EXPOSURE_PERCENT:
        return False, f"max_exposure: {exposure_pct:.1f}% >= {config.MAX_EXPOSURE_PERCENT:.1f}%"

    return True, "exposure_ok"


def check_duplicate_range_setup(
    symbol: str,
    direction: str,
    range_high: float,
    range_low: float,
    sweep_side: str,
    fallback3_setup: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str]:
    """
    Check if this exact range setup was already traded.
    Also checks for overlap with Fallback 3 setups.
    """
    setup_id = _build_range_setup_id(symbol, direction, range_high, range_low, sweep_side)
    if setup_id in _trade_record["range_setup_ids"]:
        return False, "duplicate_range_setup"

    # Cross-check with Fallback 3 to prevent duplicate trades of same structural reversal
    if fallback3_setup and fallback3_setup.get("executable"):
        fb3_reason = fallback3_setup.get("reason", "")
        fb3_sweep = (fallback3_setup.get("evidence") or {}).get("sweep", {}).get("classification", "")
        fb3_symbol = fallback3_setup.get("symbol", "")
        if fb3_symbol == symbol and "sweep" in fb3_sweep.lower():
            # Fallback 3 detected a sweep on the same symbol — risk of overlap
            return False, "fallback3_overlap_same_symbol_sweep"

    return True, "unique_range_setup"


def register_fallback4_trade(
    symbol: str,
    direction: str,
    range_high: float,
    range_low: float,
    sweep_side: str,
    won: Optional[bool] = None,
    pl: float = 0.0,
) -> str:
    """
    Register a Fallback 4 trade in the risk tracker.
    Returns the setup ID.
    """
    today = time.strftime("%Y-%m-%d", time.gmtime())
    if _trade_record["day"] != today:
        _trade_record["daily_trades"] = 0
        _trade_record["daily_losses"] = 0
        _trade_record["consecutive_losses"] = 0
        _trade_record["daily_pl"] = 0.0
        _trade_record["day"] = today

    setup_id = _build_range_setup_id(symbol, direction, range_high, range_low, sweep_side)

    _trade_record["daily_trades"] += 1
    _trade_record["range_setup_ids"].add(setup_id)
    _trade_record["setup_ids"].add(setup_id)
    _trade_record["symbol_setups"][f"{symbol}_{direction}"] = time.time()

    if pl != 0.0:
        _trade_record["daily_pl"] += pl
        _trade_record["weekly_pl"] += pl

    if won is not None:
        if not won:
            _trade_record["daily_losses"] += 1
            _trade_record["consecutive_losses"] += 1
        else:
            _trade_record["consecutive_losses"] = 0

    return setup_id


def calculate_position_size(
    entry: float,
    sl: float,
    account: Dict[str, Any],
    risk_percent: float,
    is_m1: bool = False,
) -> float:
    """
    Calculate position size for Fallback 4.
    
    Uses separate risk percentages for M5 and M1.
    The actual lot calculation is delegated to mt5_connector.calculate_volume_for_risk.
    Returns the risk amount for the volume calculator.
    """
    if is_m1:
        risk_pct = config.RISK_PERCENT_M1
    else:
        risk_pct = config.RISK_PERCENT_M5

    balance = _to_float(account.get("balance", 0.0))
    if balance <= 0:
        return 0.0

    risk_amount = balance * (risk_pct / 100.0)
    return risk_amount


def calculate_sl_tp(
    entry_price: float,
    direction: str,
    sweep_extreme: float,
    range_data: Any,
    atr_value: float,
    point: float,
    spread: float = 0.0,
) -> Tuple[float, float, float, float, float, float, List[dict]]:
    """
    Calculate stop loss and take profit levels.
    
    For bullish: SL below sweep extreme + buffer.
    For bearish: SL above sweep extreme + buffer.
    
    Targets: range-based levels (25%, 50%, 75%, 100%).
    
    Returns:
        (sl_price, risk_distance, tp1, tp2, tp3, final_tp, targets_list)
    """
    spread_buffer = max(spread, point * 2)
    atr_buffer = atr_value * 0.3

    if direction == "buy":
        # SL below sweep extreme
        sl_price = min(sweep_extreme, entry_price - atr_buffer) - spread_buffer
        risk = entry_price - sl_price

        # Targets toward range high
        range_low = range_data.range_low
        range_high = range_data.range_high
        range_width = range_data.range_width

        tp1 = range_low + range_width * 0.25
        tp2 = range_low + range_width * 0.50  # Midpoint
        tp3 = range_low + range_width * 0.75
        final_tp = range_high
    else:
        sl_price = max(sweep_extreme, entry_price + atr_buffer) + spread_buffer
        risk = sl_price - entry_price

        range_low = range_data.range_low
        range_high = range_data.range_high
        range_width = range_data.range_width

        tp1 = range_high - range_width * 0.25
        tp2 = range_high - range_width * 0.50  # Midpoint
        tp3 = range_high - range_width * 0.75
        final_tp = range_low

    # Normalize to tick size
    tick_size = max(point, 1e-10)
    sl_price = round(sl_price / tick_size) * tick_size
    tp1 = round(tp1 / tick_size) * tick_size
    tp2 = round(tp2 / tick_size) * tick_size
    tp3 = round(tp3 / tick_size) * tick_size
    final_tp = round(final_tp / tick_size) * tick_size
    risk = max(risk, tick_size)

    targets = [
        {"level": tp1, "label": "tp1", "allocation": config.TP1_ALLOC},
        {"level": tp2, "label": "tp2", "allocation": config.TP2_ALLOC},
        {"level": tp3, "label": "tp3", "allocation": config.TP3_ALLOC},
        {"level": final_tp, "label": "final", "allocation": config.TP4_ALLOC},
    ]

    return sl_price, risk, tp1, tp2, tp3, final_tp, targets


def _build_range_setup_id(
    symbol: str,
    direction: str,
    range_high: float,
    range_low: float,
    sweep_side: str,
) -> str:
    """Build a unique setup identifier for range-based trade."""
    return f"{symbol}|{direction}|{range_high:.5f}|{range_low:.5f}|{sweep_side}|fb4"


def check_spread_allowed(spread: float, is_m1: bool = False) -> Tuple[bool, str]:
    """Check if spread is within acceptable limits."""
    max_spread = config.MAX_SPREAD_POINTS_M1 if is_m1 else config.MAX_SPREAD_POINTS_M5
    if spread > max_spread:
        return False, f"spread_{spread:.0f}_pts_exceeds_max_{max_spread}"
    return True, "spread_ok"
