"""
FALLBACK STRATEGY 3 - Risk Management
======================================
Fallback-specific risk controls. Does not bypass the global risk manager.
"""

import time
from typing import Any, Dict, List, Optional, Tuple

from . import config


def _to_float(value, default=0.0) -> float:
    try:
        return float(value)
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
    "symbol_setups": {},    # symbol -> timestamp of last setup
    "setup_ids": set(),     # Unique setup IDs
}


def check_risk_gate(
    symbol: str,
    direction: str,
    account: Dict[str, Any],
    positions: List[Dict[str, Any]],
    ict_setup: Dict[str, Any],
    kingsbalfx_setup: Dict[str, Any],
) -> Tuple[bool, str]:
    """
    Check all risk gates before activating Fallback 3.
    
    Returns (passed: bool, reason: str).
    """
    # 1. Check global risk limits (via the passed ict results)
    if ict_setup and not ict_setup.get("executable"):
        # ICT skipped: good
        pass
    else:
        return False, "ICT has a valid trade"

    if kingsbalfx_setup and kingsbalfx_setup.get("valid", False):
        return False, "Kingsbalfx has a valid trade"

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
        return False, f"max_daily_fallback_trades_reached: {_trade_record['daily_trades']}/{config.MAX_TRADES_PER_DAY}"

    # 7. Max consecutive losses
    if _trade_record["consecutive_losses"] >= config.MAX_CONSECUTIVE_LOSSES:
        return False, f"max_consecutive_losses: {_trade_record['consecutive_losses']}"

    # 8. Per-symbol cooldown
    symbol_key = f"{symbol}_{direction}"
    last_setup = _trade_record["symbol_setups"].get(symbol_key, 0)
    if time.time() - last_setup < config.PER_SYMBOL_COOLDOWN:
        remaining = config.PER_SYMBOL_COOLDOWN - (time.time() - last_setup)
        return False, f"symbol_cooldown: {remaining:.0f}s remaining"

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

    # Check daily loss
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
    if peak > 0:
        dd_pct = (peak - equity) / peak * 100.0
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
    exposure_pct = total_exposure / balance * 100.0

    if exposure_pct >= config.MAX_EXPOSURE_PERCENT:
        return False, f"max_exposure: {exposure_pct:.1f}% >= {config.MAX_EXPOSURE_PERCENT:.1f}%"

    return True, "exposure_ok"


def check_duplicate_setup(symbol: str, direction: str, liquidity_level: float, choch_level: float) -> Tuple[bool, str]:
    """
    Check if this exact setup (same symbol + direction + liquidity + CHOCH) was already traded.
    """
    setup_id = _build_setup_id(symbol, direction, liquidity_level, choch_level)
    if setup_id in _trade_record["setup_ids"]:
        return False, "duplicate_setup"
    return True, "unique_setup"


def register_fallback3_trade(
    symbol: str,
    direction: str,
    liquidity_level: float,
    choch_level: float,
    won: Optional[bool] = None,
    pl: float = 0.0,
) -> str:
    """
    Register a Fallback 3 trade in the risk tracker.
    Returns the setup ID.
    """
    today = time.strftime("%Y-%m-%d", time.gmtime())
    if _trade_record["day"] != today:
        _trade_record["daily_trades"] = 0
        _trade_record["daily_losses"] = 0
        _trade_record["consecutive_losses"] = 0
        _trade_record["daily_pl"] = 0.0
        _trade_record["day"] = today

    setup_id = _build_setup_id(symbol, direction, liquidity_level, choch_level)

    _trade_record["daily_trades"] += 1
    _trade_record["setup_ids"].add(setup_id)
    _trade_record["symbol_setups"][f"{symbol}_{direction}"] = time.time()

    if pl != 0:
        _trade_record["daily_pl"] += pl
        _trade_record["weekly_pl"] += pl

    if won is not None:
        if not won:
            _trade_record["daily_losses"] += 1
            _trade_record["consecutive_losses"] += 1
        else:
            _trade_record["consecutive_losses"] = 0

    return setup_id


def calculate_sl(
    entry_price: float,
    direction: str,
    sweep_level: float,
    structure_low: float,   # For buy: swing low below entry
    structure_high: float,  # For sell: swing high above entry
    atr_value: float,
    point: float,
    spread: float = 0.0,
) -> Tuple[float, float]:
    """
    Calculate stop loss with appropriate buffers.
    
    Returns (sl_price, risk_distance).
    """
    spread_buffer = max(spread, point * 2)
    atr_buffer = atr_value * 0.5

    if direction == "buy":
        # SL below swept liquidity low, swing low, or ATR-based level
        sl_candidate = min(
            sweep_level,
            structure_low,
            entry_price - atr_buffer,
            entry_price - (point * 20),
        )
        sl_price = sl_candidate - spread_buffer
        risk = entry_price - sl_price
    else:
        sl_candidate = max(
            sweep_level,
            structure_high,
            entry_price + atr_buffer,
            entry_price + (point * 20),
        )
        sl_price = sl_candidate + spread_buffer
        risk = sl_price - entry_price

    # Normalize to tick size
    tick_size = max(point, 1e-10)
    sl_price = round(sl_price / tick_size) * tick_size
    risk = max(risk, tick_size)

    return sl_price, risk


def calculate_tp(
    entry_price: float,
    direction: str,
    targets: List[float],
    risk: float,
    min_rr: float = None,
) -> Tuple[float, float]:
    """
    Calculate take profit from nearest liquidity target.
    Returns (tp_price, reward_distance).
    """
    min_rr = min_rr if min_rr is not None else config.MIN_RR

    valid_targets = []
    for t in targets:
        if direction == "buy" and t > entry_price:
            valid_targets.append(t)
        elif direction == "sell" and t < entry_price:
            valid_targets.append(t)

    if not valid_targets:
        # Fall back to risk-based
        if risk > 0:
            tp_price = entry_price + (risk * min_rr if direction == "buy" else -risk * min_rr)
            return tp_price, abs(tp_price - entry_price)
        return entry_price, 0.0

    # Best target is the nearest one that gives at least min_rr
    for t in sorted(valid_targets, key=lambda x: abs(x - entry_price)):
        reward = abs(t - entry_price)
        if risk > 0 and reward / risk >= min_rr:
            return t, reward

    # Use nearest target even if below min_rr (risk check will catch this)
    nearest = valid_targets[0] if direction == "buy" else valid_targets[-1]
    return nearest, abs(nearest - entry_price)


def _build_setup_id(symbol: str, direction: str, liquidity_level: float, choch_level: float) -> str:
    """Build a unique setup identifier."""
    return f"{symbol}|{direction}|{liquidity_level:.5f}|{choch_level:.5f}|fb3"
