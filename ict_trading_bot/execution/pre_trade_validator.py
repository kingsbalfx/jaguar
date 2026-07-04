"""
PRE-TRADE VALIDATION ENGINE
===========================
Final checkpoint BEFORE every trade execution.
"""
import logging
import os
from datetime import datetime
from typing import Dict, Tuple

try:
    import MetaTrader5 as mt5
except Exception as e:
    mt5 = None
    _MT5_IMPORT_ERROR = e

from risk.market_condition import should_trade_pair_based_on_volatility
from execution.mt5_connector import get_symbol_spec, get_tick_snapshot
from risk.protection import daily_loss_allows_trade

logger = logging.getLogger(__name__)


class PreTradeValidator:
    def __init__(self):
        self.checks = []
        self.failed_checks = []
        self.warnings = []
        self.latest_cis_result = {}

    def _reset(self):
        self.checks = []
        self.failed_checks = []
        self.warnings = []
        self.latest_cis_result = {}

    def _check(self, name: str, passed: bool, message: str):
        record = {"name": name, "status": "PASS" if passed else "FAIL", "message": message}
        if passed:
            self.checks.append(record)
        else:
            self.failed_checks.append(record)

    def _warn(self, message: str):
        self.warnings.append({"type": "WARNING", "message": message})

    def _check_broker_connection(self) -> bool:
        try:
            if mt5 is None:
                self._check("Broker Connection", False, "MT5 package not available")
                return False
            if not mt5.initialize():
                mt5.initialize()
            tick = mt5.symbol_info_tick("EURUSD")
            if tick is None:
                self._check("Broker Connection", False, "Cannot fetch tick data")
                return False
            self._check("Broker Connection", True, "MT5 connected and responsive")
            return True
        except Exception as exc:
            self._check("Broker Connection", False, f"MT5 error: {exc}")
            return False

    def _check_symbol_validity(self, symbol: str) -> bool:
        try:
            info = mt5.symbol_info(symbol)
            if info is None:
                self._check("Symbol Valid", False, f"{symbol} not found or not tradable")
                return False
            if not info.visible:
                self._check("Symbol Valid", False, f"{symbol} not visible/enabled")
                return False
            self._check("Symbol Valid", True, f"{symbol} is tradable")
            return True
        except Exception as exc:
            self._check("Symbol Valid", False, f"Symbol check error: {exc}")
            return False

    def _check_market_hours(self, symbol: str) -> bool:
        try:
            info = mt5.symbol_info(symbol)
            if info is None:
                self._check("Market Hours", False, "Cannot check market hours")
                return False
            if info.trade_mode == mt5.SYMBOL_TRADE_MODE_DISABLED:
                self._warn(f"Market closed for {symbol} - order would remain pending")
                self._check("Market Hours", False, "Market currently closed")
                return False
            self._check("Market Hours", True, "Market is open")
            return True
        except Exception as exc:
            self._check("Market Hours", False, f"Market hour check error: {exc}")
            return False

    def _check_spread(self, symbol: str) -> bool:
        try:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                self._check("Spread", False, "Cannot fetch tick data")
                return False
            # Use symbol digits to calculate spread pips correctly for all symbols
            info = mt5.symbol_info(symbol)
            digits = int(getattr(info, "digits", 5) or 5)
            pip_multiplier = 10 ** (digits - 1) if digits > 3 else 100
            max_spread = float(os.getenv("MAX_SPREAD_PIPS", "5") or 5.0)
            spread_pips = (tick.ask - tick.bid) * pip_multiplier
            if spread_pips > max_spread:
                self._check("Spread", False, f"Spread too wide ({spread_pips:.1f}p)")
                return False
            self._check("Spread", True, f"Spread acceptable ({spread_pips:.1f}p)")
            return True
        except Exception as exc:
            self._check("Spread", False, f"Spread check error: {exc}")
            return False

    def _check_account_health(self) -> bool:
        try:
            account_info = mt5.account_info()
            if account_info is None:
                self._check("Account Health", False, "Cannot fetch account info")
                return False
            if account_info.margin_free <= 0:
                self._check("Account Health", False, "No free margin available")
                return False
            if account_info.balance <= 0:
                self._check("Account Health", False, "Account balance invalid")
                return False
            margin_level = (account_info.equity / account_info.margin) * 100 if account_info.margin > 0 else 999.0
            self._check("Account Health", True, f"Balance ${account_info.balance:,.2f} | Margin {margin_level:.0f}%")
            return True
        except Exception as exc:
            self._check("Account Health", False, f"Account health error: {exc}")
            return False

    def _check_no_conflicting_positions(self, symbol: str, direction: str) -> bool:
        try:
            positions = mt5.positions_get(symbol=symbol)
            if positions is None or len(positions) == 0:
                self._check("Conflicting Positions", True, "No existing positions")
                return True

            desired_buy = str(direction or "").upper() == "BUY"
            for position in positions:
                if desired_buy and position.type != mt5.ORDER_TYPE_BUY:
                    self._check("Conflicting Positions", False, "Opposing position already open")
                    return False
                if not desired_buy and position.type == mt5.ORDER_TYPE_BUY:
                    self._check("Conflicting Positions", False, "Opposing position already open")
                    return False

            self._check("Conflicting Positions", True, f"{len(positions)} aligned position(s) already open")
            return True
        except Exception as exc:
            self._check("Conflicting Positions", False, f"Position check error: {exc}")
            return False

    def _check_volatility_acceptable(self, symbol: str) -> bool:
        try:
            should_trade, reason, _ = should_trade_pair_based_on_volatility(symbol)
            self._check("Volatility Acceptable", should_trade, reason)
            return should_trade
        except Exception as exc:
            self._check("Volatility Acceptable", False, f"Volatility check error: {exc}")
            return False

    def _check_cis_approval(self, symbol: str, direction: str, timeframe: str = "H1", entry_price: float = None) -> bool:
        self.latest_cis_result = {
            "symbol": symbol,
            "direction": direction,
            "timeframe": timeframe,
            "entry_price": entry_price,
            "source": "strategy.unified_strategy",
        }
        self._check("ICT State Machine", True, "Strategy approval is supplied by the unified ICT state machine")
        return True

    def _check_risk_parameters(self, symbol: str, entry: float, stop_loss: float, take_profit: float, volume: float) -> bool:
        try:
            if entry <= 0 or stop_loss <= 0 or take_profit <= 0:
                self._check("Risk Parameters", False, "Invalid prices (must be > 0)")
                return False

            pip_size = 0.01 if "JPY" in symbol else 0.0001
            risk_pips = abs(entry - stop_loss) / pip_size
            reward_pips = abs(take_profit - entry) / pip_size
            rr_ratio = reward_pips / risk_pips if risk_pips > 0 else 0.0

            account_info = mt5.account_info()
            if account_info is None:
                self._check("Risk Parameters", False, "Cannot fetch account info")
                return False

            risk_amount = volume * risk_pips * 100
            risk_percent = (risk_amount / max(account_info.balance, 1e-9)) * 100
            checks_passed = risk_percent <= 2.5 and rr_ratio >= 1.5
            message = f"Risk {risk_percent:.2f}% | R:R {rr_ratio:.2f}"
            self._check("Risk Parameters", checks_passed, message)
            return checks_passed
        except Exception as exc:
            self._check("Risk Parameters", False, f"Risk calculation error: {exc}")
            return False

    def validate_trade(
        self,
        symbol: str,
        direction: str,
        timeframe: str = "H1",
        entry: float = None,
        stop_loss: float = None,
        take_profit: float = None,
        volume: float = 0.01,
    ) -> Dict:
        self._reset()
        result = {
            "symbol": symbol,
            "direction": direction,
            "entry": entry,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "volume": volume,
            "approved": False,
            "reason": "",
            "checks": [],
            "warnings": [],
            "timestamp": datetime.utcnow().isoformat(),
        }

        try:
            checks = [
                ("Broker connection failed", lambda: self._check_broker_connection()),
                (f"{symbol} not tradable", lambda: self._check_symbol_validity(symbol)),
                ("Market is closed", lambda: self._check_market_hours(symbol)),
                ("Spread too wide", lambda: self._check_spread(symbol)),
                ("Account health insufficient", lambda: self._check_account_health()),
                ("Conflicting position exists", lambda: self._check_no_conflicting_positions(symbol, direction)),
                ("Volatility unsuitable", lambda: self._check_volatility_acceptable(symbol)),
                ("CIS sequence validation failed", lambda: self._check_cis_approval(symbol, direction, timeframe=timeframe, entry_price=entry)),
            ]

            for reason, check_fn in checks:
                if not check_fn():
                    result["reason"] = reason
                    result["checks"] = self.checks + self.failed_checks
                    result["warnings"] = self.warnings
                    return result

            if entry and stop_loss and take_profit and not self._check_risk_parameters(symbol, entry, stop_loss, take_profit, volume):
                result["reason"] = "Risk parameters unacceptable"
                result["checks"] = self.checks + self.failed_checks
                result["warnings"] = self.warnings
                return result

            result["approved"] = len(self.failed_checks) == 0
            result["reason"] = "All validations passed" if result["approved"] else self.failed_checks[0]["message"]
            result["checks"] = self.checks + self.failed_checks
            result["warnings"] = self.warnings
            result["cis"] = self.latest_cis_result
            return result
        except Exception as exc:
            logger.error(f"Validation error: {exc}")
            result["approved"] = False
            result["reason"] = f"Validation system error: {exc}"
            result["checks"] = self.checks + self.failed_checks
            result["warnings"] = self.warnings
            return result


validator = PreTradeValidator()


def validate_trade_before_entry(
    symbol: str,
    direction: str,
    entry: float = None,
    stop_loss: float = None,
    take_profit: float = None,
    volume: float = 0.01,
    timeframe: str = "H1",
) -> Tuple[bool, Dict]:
    result = validator.validate_trade(
        symbol=symbol,
        direction=direction,
        timeframe=timeframe,
        entry=entry,
        stop_loss=stop_loss,
        take_profit=take_profit,
        volume=volume,
    )
    return result.get("approved", False), result


def validate_execution_safety(
    symbol: str,
    direction: str,
    entry: float,
    stop_loss: float,
    take_profit: float,
    volume: float,
    account_snapshot: Dict,
    open_positions=None,
) -> Tuple[bool, Dict]:
    """Hard gates only: reject operationally unsafe orders, never strategy opinions."""
    checks = {}
    reasons = []
    try:
        tick = get_tick_snapshot(symbol)
        spec = get_symbol_spec(symbol)
    except Exception as exc:
        return False, {"approved": False, "reasons": [f"market_data_unavailable:{exc}"], "checks": checks}

    now_seconds = datetime.utcnow().timestamp()
    tick_time = float(tick.get("time") or 0.0)
    max_age = float(os.getenv("MAX_TICK_AGE_SECONDS", "120"))
    checks["fresh_tick"] = tick_time > 0 and now_seconds - tick_time <= max_age

    max_spread_points = float(os.getenv("MAX_SPREAD_POINTS", "80"))
    checks["spread"] = float(tick.get("spread_points", 0.0)) <= max_spread_points
    checks["volume"] = spec["volume_min"] <= float(volume) <= spec["volume_max"]
    side = str(direction or "").lower()
    checks["geometry"] = (
        float(stop_loss) < float(entry) < float(take_profit)
        if side == "buy"
        else float(take_profit) < float(entry) < float(stop_loss)
    )
    min_distance = spec["stops_level"] * max(spec["point"], 1e-12)
    checks["stop_distance"] = abs(float(entry) - float(stop_loss)) >= min_distance and abs(float(take_profit) - float(entry)) >= min_distance
    checks["free_margin"] = float((account_snapshot or {}).get("margin_free") or 0.0) > 0
    checks["daily_loss"], daily_reason = daily_loss_allows_trade(account_snapshot)
    existing_same = [
        pos for pos in (open_positions or [])
        if str(pos.get("symbol") or "") == symbol and str(pos.get("direction") or "").lower() == side
    ]
    checks["duplicate_position"] = len(existing_same) == 0

    for name, passed in checks.items():
        if not passed:
            reasons.append(name)
    if not checks["daily_loss"]:
        reasons.append(daily_reason)
    return not reasons, {"approved": not reasons, "reasons": reasons, "checks": checks, "tick": tick, "spec": spec}
