"""Transparent broker-aware risk rules."""

import os
from dataclasses import dataclass
from typing import Dict, Tuple

from execution.mt5_connector import calculate_volume_for_risk, get_symbol_spec


@dataclass(frozen=True)
class RuleBasedRiskParams:
    risk_per_trade_percent: float = float(os.getenv("RISK_PER_TRADE", "1.0"))
    max_risk_per_trade_percent: float = float(os.getenv("MAX_RISK_PER_TRADE", "2.0"))
    max_concurrent_trades: int = int(os.getenv("MAX_CONCURRENT_TRADES", "5"))
    max_daily_loss_percent: float = float(os.getenv("MAX_DAILY_LOSS_PERCENT", "5.0"))
    minimum_rr: float = float(os.getenv("MIN_RISK_REWARD", "1.5"))
    medium_news_multiplier: float = float(os.getenv("MEDIUM_NEWS_RISK_MULTIPLIER", "0.5"))
    high_news_multiplier: float = float(os.getenv("HIGH_NEWS_RISK_MULTIPLIER", "0.25"))
    correlation_multiplier: float = float(os.getenv("CORRELATED_RISK_MULTIPLIER", "0.5"))


class RuleBasedRiskManager:
    """Size orders from broker loss calculations and explicit risk modifiers."""

    def __init__(self, params: RuleBasedRiskParams = None):
        self.params = params or RuleBasedRiskParams()

    def risk_multiplier(self, *, session_active: bool, news_impact: str, correlated: bool, setup_score: float = 100.0) -> float:
        multiplier = max(0.0, min(float(setup_score) / 100.0, 1.0))
        if not session_active:
            multiplier *= 0.7
        impact = str(news_impact or "none").lower()
        if impact == "medium":
            multiplier *= self.params.medium_news_multiplier
        elif impact == "high":
            multiplier *= self.params.high_news_multiplier
        if correlated:
            multiplier *= self.params.correlation_multiplier
        return round(multiplier, 4)

    def validate_geometry(self, direction: str, entry: float, stop_loss: float, take_profit: float) -> Tuple[bool, Dict]:
        direction = str(direction or "").lower()
        entry = float(entry)
        stop_loss = float(stop_loss)
        take_profit = float(take_profit)
        if direction == "buy":
            valid = stop_loss < entry < take_profit
        elif direction == "sell":
            valid = take_profit < entry < stop_loss
        else:
            return False, {"reason": "invalid_direction"}
        risk = abs(entry - stop_loss)
        reward = abs(take_profit - entry)
        rr = reward / risk if risk > 0 else 0.0
        return valid and rr >= self.params.minimum_rr, {
            "geometry_valid": valid,
            "risk_distance": risk,
            "reward_distance": reward,
            "rr": round(rr, 3),
            "minimum_rr": self.params.minimum_rr,
        }

    def calculate_position_size(
        self,
        symbol: str,
        direction: str,
        account_balance: float,
        current_price: float,
        stop_loss_price: float,
        asset_class: str = "",
        atr: float = 0.0,
        session: str = "other",
        news_impact: str = "none",
        open_positions: int = 0,
        correlation_risk: float = 0.0,
        setup_score: float = 100.0,
    ) -> Tuple[float, str, Dict]:
        del direction, asset_class, atr
        if float(account_balance) <= 0:
            return 0.0, "invalid_account_balance", {"approved": False}
        if int(open_positions) >= self.params.max_concurrent_trades:
            return 0.0, "max_concurrent_trades", {"approved": False, "open_positions": open_positions}

        risk_percent = min(self.params.risk_per_trade_percent, self.params.max_risk_per_trade_percent)
        multiplier = self.risk_multiplier(
            session_active=str(session or "").lower() in ("london", "newyork", "new_york"),
            news_impact=news_impact,
            correlated=float(correlation_risk) > 0.0,
            setup_score=setup_score,
        )
        risk_amount = float(account_balance) * (risk_percent / 100.0) * multiplier
        if risk_amount <= 0:
            return 0.0, "risk_reduced_to_zero", {"approved": False, "multiplier": multiplier}

        volume = calculate_volume_for_risk(symbol, float(current_price), float(stop_loss_price), risk_amount)
        spec = get_symbol_spec(symbol)
        approved = float(volume) >= float(spec["volume_min"])
        breakdown = {
            "approved": approved,
            "symbol": symbol,
            "risk_percent": risk_percent,
            "risk_multiplier": multiplier,
            "risk_amount": round(risk_amount, 2),
            "entry": float(current_price),
            "stop_loss": float(stop_loss_price),
            "volume": float(volume),
            "broker_spec": spec,
        }
        return float(volume) if approved else 0.0, "broker_aware_risk_size" if approved else "below_broker_minimum", breakdown

    def calculate_with_target(
        self,
        symbol: str,
        direction: str,
        account_balance: float,
        entry: float,
        stop_loss: float,
        take_profit: float,
        **kwargs,
    ) -> Tuple[float, str, Dict]:
        geometry_ok, geometry = self.validate_geometry(direction, entry, stop_loss, take_profit)
        if not geometry_ok:
            return 0.0, "invalid_trade_geometry", {"approved": False, **geometry}
        volume, reason, breakdown = self.calculate_position_size(
            symbol,
            direction,
            account_balance,
            entry,
            stop_loss,
            **kwargs,
        )
        breakdown["geometry"] = geometry
        return volume, reason, breakdown
