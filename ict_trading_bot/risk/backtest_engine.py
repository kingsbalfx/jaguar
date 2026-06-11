"""Deterministic setup-occurrence reporting from observed price paths."""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from utils.sessions import in_london_session, in_newyork_session


def _pip_size(symbol: str = "") -> float:
    return 0.01 if "JPY" in str(symbol or "").upper() else 0.0001


def _session_allowed(dt: datetime, allowed_sessions: List[str]) -> bool:
    allowed = {str(item).lower() for item in (allowed_sessions or [])}
    return (in_london_session(dt) and "london" in allowed) or (in_newyork_session(dt) and "newyork" in allowed)


def _observed_outcome(occurrence: Dict, direction: str, sl: float, tp: float) -> Optional[str]:
    explicit = str(occurrence.get("outcome") or "").lower()
    if explicit in ("win", "loss"):
        return explicit
    highs = occurrence.get("future_highs") or occurrence.get("highs") or []
    lows = occurrence.get("future_lows") or occurrence.get("lows") or []
    for index in range(max(len(highs), len(lows))):
        high = float(highs[index]) if index < len(highs) else float("-inf")
        low = float(lows[index]) if index < len(lows) else float("inf")
        if direction == "buy":
            if low <= sl:
                return "loss"
            if high >= tp:
                return "win"
        else:
            if high >= sl:
                return "loss"
            if low <= tp:
                return "win"
    return None


def _trade_result(
    symbol: str,
    occurrence: Dict,
    spread_pips: float,
    slippage_pips: float,
) -> Optional[Tuple[str, float]]:
    direction = str(occurrence.get("direction") or "").lower()
    if direction not in ("buy", "sell"):
        return None
    entry = float(occurrence["entry_price"])
    sl = float(occurrence["sl_price"])
    tp = float(occurrence["tp_price"])
    friction = (spread_pips + slippage_pips) * _pip_size(symbol)
    effective_entry = entry + friction if direction == "buy" else entry - friction
    risk = abs(effective_entry - sl)
    reward = abs(tp - effective_entry)
    if risk <= 0 or reward <= 0:
        return None
    outcome = _observed_outcome(occurrence, direction, sl, tp)
    if outcome is None:
        return None
    return outcome, reward if outcome == "win" else -risk


def generate_setup_occurrence_report(
    symbol: str,
    setup_signature: Dict,
    historical_data: List[Dict],
    strategy_params: Dict,
    backtest_config: Dict,
) -> Dict:
    spread_pips = float(backtest_config.get("spread_pips", 1.0))
    slippage_pips = float(backtest_config.get("slippage_pips", 0.2))
    session_filter_enabled = bool(backtest_config.get("session_filter_enabled", True))
    allowed_sessions = backtest_config.get("allowed_sessions", ["london", "newyork"])
    wins = losses = 0
    total_pnl = current_equity = peak_equity = max_drawdown = gross_profit = gross_loss = 0.0

    for occurrence in historical_data or []:
        trade_time = occurrence.get("timestamp", datetime.now(timezone.utc))
        if session_filter_enabled and not _session_allowed(trade_time, allowed_sessions):
            continue
        try:
            result = _trade_result(symbol, occurrence, spread_pips, slippage_pips)
        except (KeyError, TypeError, ValueError):
            continue
        if result is None:
            continue
        outcome, pnl = result
        total_pnl += pnl
        current_equity += pnl
        peak_equity = max(peak_equity, current_equity)
        max_drawdown = min(max_drawdown, current_equity - peak_equity)
        if outcome == "win":
            wins += 1
            gross_profit += pnl
        else:
            losses += 1
            gross_loss += abs(pnl)

    trades = wins + losses
    return {
        "metrics": {
            "trades": trades,
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / trades, 4) if trades else 0.0,
            "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss else round(gross_profit, 2),
            "max_drawdown": round(abs(max_drawdown), 2),
            "expectancy": round(total_pnl / trades, 4) if trades else 0.0,
            "total_pnl": round(total_pnl, 2),
            "spread_pips_applied": spread_pips,
            "slippage_pips_applied": slippage_pips,
            "session_filter_enabled": session_filter_enabled,
            "allowed_sessions": allowed_sessions,
            "unresolved_occurrences_skipped": len(historical_data or []) - trades,
        },
        "setup_signature": setup_signature,
        "strategy_params": strategy_params,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
