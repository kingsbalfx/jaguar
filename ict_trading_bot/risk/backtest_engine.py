import random
from datetime import datetime
from typing import Dict, List, Tuple

from utils.sessions import in_london_session, in_newyork_session


def _pip_size(symbol: str = "") -> float:
    return 0.01 if "JPY" in str(symbol or "").upper() else 0.0001


def _session_allowed(dt: datetime, allowed_sessions: List[str]) -> bool:
    allowed = {str(item).lower() for item in (allowed_sessions or [])}
    if in_london_session(dt) and "london" in allowed:
        return True
    if in_newyork_session(dt) and "newyork" in allowed:
        return True
    return False


def _simulate_single_trade_outcome(
    symbol: str,
    entry_price: float,
    sl_price: float,
    tp_price: float,
    direction: str,
    spread_pips: float,
    slippage_pips: float,
    partial_fill_chance: float,
    displacement_score: float = 0.70
) -> Tuple[str, float]:
    pip_size = _pip_size(symbol)
    spread_cost = spread_pips * pip_size
    slippage_cost = random.uniform(0.0, slippage_pips) * pip_size

    if str(direction or "").lower() == "buy":
        effective_entry = entry_price + spread_cost + slippage_cost
        risk = abs(effective_entry - sl_price)
        reward = abs(tp_price - effective_entry)
    else:
        effective_entry = entry_price - spread_cost - slippage_cost
        risk = abs(sl_price - effective_entry)
        reward = abs(effective_entry - tp_price)

    if risk <= 0 or reward <= 0:
        return "loss", 0.0

    win_probability = 0.50
    # Realistic win probability: Base 48% + bonus for strong displacement
    # This accounts for the friction of spread and slippage on win rates
    win_probability = 0.48 + (max(0, displacement_score - 0.70) * 0.2)
    
    outcome = "win" if random.random() < win_probability else "loss"
    pnl = reward if outcome == "win" else -risk

    if random.random() < partial_fill_chance and outcome == "win":
        pnl *= random.uniform(0.65, 0.9)

    return outcome, pnl


def generate_setup_occurrence_report(
    symbol: str,
    setup_signature: Dict,
    historical_data: List[Dict],
    strategy_params: Dict,
    backtest_config: Dict,
) -> Dict:
    spread_pips = float(backtest_config.get("spread_pips", 1.0))
    slippage_pips = float(backtest_config.get("slippage_pips", 0.2))
    partial_fill_chance = float(backtest_config.get("partial_fill_chance", 0.15))
    session_filter_enabled = bool(backtest_config.get("session_filter_enabled", True))
    allowed_sessions = backtest_config.get("allowed_sessions", ["london", "newyork"])
    displacement_val = float(setup_signature.get("displacement_score", 0.70))

    total_trades = 0
    total_wins = 0
    total_losses = 0
    total_pnl = 0.0
    current_equity = 0.0
    peak_equity = 0.0
    max_drawdown = 0.0

    for occurrence in historical_data or []:
        trade_time = occurrence.get("timestamp", datetime.utcnow())
        if session_filter_enabled and not _session_allowed(trade_time, allowed_sessions):
            continue

        entry_price = occurrence.get("entry_price")
        sl_price = occurrence.get("sl_price")
        tp_price = occurrence.get("tp_price")
        direction = occurrence.get("direction")
        if not all([entry_price, sl_price, tp_price, direction]):
            continue

        outcome, pnl = _simulate_single_trade_outcome(
            symbol=symbol,
            entry_price=float(entry_price),
            sl_price=float(sl_price),
            tp_price=float(tp_price),
            direction=str(direction),
            spread_pips=spread_pips,
            slippage_pips=slippage_pips,
            partial_fill_chance=partial_fill_chance,
            displacement_score=displacement_val
        )

        total_trades += 1
        total_pnl += pnl
        current_equity += pnl
        peak_equity = max(peak_equity, current_equity)
        max_drawdown = min(max_drawdown, current_equity - peak_equity)

        if outcome == "win":
            total_wins += 1
        else:
            total_losses += 1

    win_rate = total_wins / total_trades if total_trades else 0.0
    gross_profit = max(total_pnl, 0.0)
    gross_loss = abs(min(total_pnl, 0.0))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (gross_profit if gross_profit > 0 else 0.0)
    expectancy = total_pnl / total_trades if total_trades else 0.0

    return {
        "metrics": {
            "trades": total_trades,
            "wins": total_wins,
            "losses": total_losses,
            "win_rate": round(win_rate, 4),
            "profit_factor": round(profit_factor, 2),
            "max_drawdown": round(abs(max_drawdown), 2),
            "expectancy": round(expectancy, 4),
            "total_pnl": round(total_pnl, 2),
            "spread_pips_applied": spread_pips,
            "slippage_pips_applied": slippage_pips,
            "partial_fill_chance_applied": partial_fill_chance,
            "session_filter_enabled": session_filter_enabled,
            "allowed_sessions": allowed_sessions,
        },
        "setup_signature": setup_signature,
        "strategy_params": strategy_params,
        "generated_at": datetime.utcnow().isoformat(),
    }
