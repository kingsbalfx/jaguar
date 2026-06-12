"""Fixed-rule broker-aware position sizing."""

import os
from dataclasses import dataclass
from typing import Dict, Tuple

from execution.mt5_connector import calculate_volume_for_risk, get_symbol_spec


@dataclass(frozen=True)
class RuleBasedRiskParams:
    risk_per_trade_percent: float = float(os.getenv("RISK_PER_TRADE", "1.0"))
    max_risk_per_trade_percent: float = float(os.getenv("MAX_RISK_PER_TRADE", "2.0"))
    max_concurrent_trades: int = int(os.getenv("MAX_CONCURRENT_TRADES", "5"))
    minimum_rr: float = float(os.getenv("MIN_RISK_REWARD", "1.5"))


class RuleBasedRiskManager:
    def __init__(self, params: RuleBasedRiskParams = None):
        self.params = params or RuleBasedRiskParams()

    def validate_geometry(self, direction: str, entry: float, stop_loss: float, take_profit: float) -> Tuple[bool, Dict]:
        side = str(direction or "").lower()
        entry, stop_loss, take_profit = float(entry), float(stop_loss), float(take_profit)
        geometry = stop_loss < entry < take_profit if side == "buy" else take_profit < entry < stop_loss if side == "sell" else False
        risk = abs(entry - stop_loss)
        reward = abs(take_profit - entry)
        rr = reward / risk if risk else 0.0
        return geometry and rr >= self.params.minimum_rr, {
            "geometry_valid": geometry,
            "rr": rr,
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
        **_ignored,
    ) -> Tuple[float, str, Dict]:
        del direction, asset_class, atr, session
        if account_balance <= 0:
            return 0.0, "invalid_account_balance", {"approved": False}
        if open_positions >= self.params.max_concurrent_trades:
            return 0.0, "max_concurrent_trades", {"approved": False}
        if str(news_impact).lower() in ("medium", "high"):
            return 0.0, "news_blackout", {"approved": False}
        if correlation_risk > 0:
            return 0.0, "correlation_conflict", {"approved": False}
        risk_percent = min(self.params.risk_per_trade_percent, self.params.max_risk_per_trade_percent)
        risk_amount = float(account_balance) * risk_percent / 100.0
        volume = calculate_volume_for_risk(symbol, current_price, stop_loss_price, risk_amount)
        spec = get_symbol_spec(symbol)
        approved = volume >= spec["volume_min"]
        return volume if approved else 0.0, "broker_aware_risk_size" if approved else "below_broker_minimum", {
            "approved": approved,
            "risk_percent": risk_percent,
            "risk_amount": risk_amount,
            "volume": volume,
            "broker_spec": spec,
        }
