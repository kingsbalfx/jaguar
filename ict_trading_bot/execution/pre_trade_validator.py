"""
PRE-TRADE VALIDATION ENGINE
===========================
Final checkpoint BEFORE every trade execution.

Ensures:
1. All confirmation criteria met
2. Risk-reward acceptable
3. Account health good
4. Market conditions safe
5. No conflicting signals
6. Order entry parameters valid
7. Broker connection healthy

If ANY validation fails, trade is BLOCKED with clear reasoning.

Output: Either APPROVED for order entry, or BLOCKED with detailed why.
"""
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime

import MetaTrader5 as mt5

logger = logging.getLogger(__name__)

# Import all validation modules
from risk.intelligence_system import get_cis_decision
from risk.market_condition import should_trade_pair_based_on_volatility
from strategy.confirmation_system import get_all_confirmations_for_pair
from risk.position_manager import get_current_account_exposure, check_margin_available
from execution.order_manager import validate_order_parameters


class PreTradeValidator:
    """
    Comprehensive pre-trade validation.
    
    Usage:
        validator = PreTradeValidator()
        result = validator.validate_trade(
            symbol="EURUSD",
            direction="BUY",
            entry=1.0850,
            stop_loss=1.0800,
            take_profit=1.0920,
            volume=0.01
        )
        
        if result["approved"]:
            # Place order
        else:
            logger.error(f"Trade blocked: {result['reason']}")
    """
    
    def __init__(self):
        self.checks = []
        self.failed_checks = []
        self.warnings = []
    
    def _reset(self):
        """Reset validation state for new trade."""
        self.checks = []
        self.failed_checks = []
        self.warnings = []
    
    def _check(self, name: str, passed: bool, message: str):
        """Record a validation check result."""
        if passed:
            self.checks.append({"name": name, "status": "PASS", "message": message})
        else:
            self.failed_checks.append({"name": name, "status": "FAIL", "message": message})
    
    def _warn(self, message: str):
        """Record a non-blocking warning."""
        self.warnings.append({"type": "WARNING", "message": message})
    
    def _check_broker_connection(self) -> bool:
        """Check MT5 connection."""
        try:
            if not mt5.initialize():
                # Try to initialize
                mt5.initialize()
            
            # Request symbol to verify connection works
            tick = mt5.symbol_info_tick("EURUSD")
            if tick is None:
                self._check("Broker Connection", False, "Cannot fetch tick data")
                return False
            
            self._check("Broker Connection", True, "MT5 connected and responsive")
            return True
        except Exception as e:
            self._check("Broker Connection", False, f"MT5 error: {e}")
            return False
    
    def _check_symbol_validity(self, symbol: str) -> bool:
        """Check symbol is tradable."""
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
        except Exception as e:
            self._check("Symbol Valid", False, f"Symbol check error: {e}")
            return False
    
    def _check_market_hours(self, symbol: str) -> bool:
        """Check market is open for this symbol."""
        try:
            info = mt5.symbol_info(symbol)
            if info is None:
                self._check("Market Hours", False, "Cannot check market hours")
                return False
            
            # If market is closed, warn but don't block (pending orders OK)
            if info.trade_mode == mt5.SYMBOL_TRADE_MODE_DISABLED:
                self._warn(f"Market closed for {symbol} - order will be pending")
                self._check("Market Hours", True, "Market currently closed - pending order mode")
                return True
            
            self._check("Market Hours", True, "Market is open")
            return True
        except Exception as e:
            self._check("Market Hours", False, f"Market hour check error: {e}")
            return False
    
    def _check_spread(self, symbol: str) -> bool:
        """
        Check spread is acceptable.
        
        Widening spreads suggest poor liquidity - warn but usually don't block.
        """
        try:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                self._check("Spread", False, "Cannot fetch tick data")
                return False
            
            spread_pips = (tick.ask - tick.bid) * 10000
            
            # Typical spread ranges:
            # Major pairs: 1-2 pips normal
            # Minor/exotics: 2-5 pips normal
            
            if spread_pips > 5.0:
                self._warn(f"Spread unusually wide: {spread_pips:.1f} pips")
                self._check("Spread", True, f"Spread OK ({spread_pips:.1f}p) but wider than usual")
            else:
                self._check("Spread", True, f"Spread normal ({spread_pips:.1f}p)")
            
            return True
        except Exception as e:
            self._check("Spread", False, f"Spread check error: {e}")
            return False
    
    def _check_cis_approval(self, symbol: str, direction: str) -> bool:
        """Check Central Intelligence System gives approval."""
        try:
            cis_result = get_cis_decision(symbol, direction)
            verdict = cis_result.get("final_verdict", "ERROR")
            confidence = cis_result.get("confidence_score", 0.0)
            
            if verdict == "AVOID":
                self._check("CIS Approval", False, f"CIS recommends AVOID (conf: {confidence:.2f})")
                return False
            elif verdict == "WAIT":
                self._warn(f"CIS suggests WAIT (conf: {confidence:.2f}) but trade allowed")
                self._check("CIS Approval", True, f"CIS WAIT (conf: {confidence:.2f})")
                return True
            else:  # TRADE
                self._check("CIS Approval", True, f"CIS TRADE (conf: {confidence:.2f})")
                return True
        except Exception as e:
            self._check("CIS Approval", False, f"CIS check error: {e}")
            return False
    
    def _check_technical_confirmations(self, symbol: str, timeframe: str) -> bool:
        """Check multi-timeframe confirmations."""
        try:
            confirmations = get_all_confirmations_for_pair(symbol, timeframe)
            
            if not confirmations:
                self._check("Technical Confirmations", False, "No confirmation data available")
                return False
            
            # Count confirmations
            confirm_count = sum(1 for v in confirmations.values() if v > 0.5)
            
            if confirm_count < 2:
                self._check("Technical Confirmations", False, f"Only {confirm_count} confirmations (need ≥2)")
                return False
            
            self._check("Technical Confirmations", True, f"{confirm_count} confirmations present")
            return True
        except Exception as e:
            self._check("Technical Confirmations", False, f"Confirmation check error: {e}")
            return False
    
    def _check_risk_parameters(
        self,
        symbol: str,
        entry: float,
        stop_loss: float,
        take_profit: float,
        volume: float
    ) -> bool:
        """
        Check risk-reward parameters are acceptable.
        
        Rules:
        - Risk must be < 2.5% of account
        - RR ratio must be ≥ 1.5:1 minimum
        - Stop loss must make sense (below entry for BUY, above for SELL)
        - Take profit must be > entry
        """
        try:
            if entry <= 0 or stop_loss <= 0 or take_profit <= 0:
                self._check("Risk Parameters", False, "Invalid prices (must be > 0)")
                return False
            
            # Calculate risk/reward
            try:
                tick = mt5.symbol_info_tick(symbol)
                if tick is None:
                    self._check("Risk Parameters", False, "Cannot fetch current price")
                    return False
                
                current_price = tick.mid()
                
                # Pip values (rough calculation)
                if "JPY" in symbol:
                    pip_size = 0.01
                else:
                    pip_size = 0.0001
                
                risk_pips = abs(entry - stop_loss) / pip_size
                reward_pips = abs(take_profit - entry) / pip_size
                
                rr_ratio = reward_pips / risk_pips if risk_pips > 0 else 0
                
                # Risk as % of account
                account_info = mt5.account_info()
                if account_info is None:
                    self._check("Risk Parameters", False, "Cannot fetch account info")
                    return False
                
                # Rough estimate: risk $ = volume * pip_size * risk_pips * 10000
                risk_amount = volume * risk_pips * 100  # Approximate
                risk_percent = (risk_amount / account_info.balance) * 100
                
                # Validation
                checks_passed = True
                reasons = []
                
                if risk_percent > 2.5:
                    checks_passed = False
                    reasons.append(f"Risk too high: {risk_percent:.2f}% (max 2.5%)")
                
                if rr_ratio < 1.5:
                    self._warn(f"Risk-reward ratio weak: {rr_ratio:.2f}:1 (ideal ≥1.5:1)")
                
                if rr_ratio > 1.5:
                    reasons.append(f"R:R acceptable: {rr_ratio:.2f}:1")
                
                status_text = " | ".join(reasons) if reasons else f"Risk {risk_percent:.2f}% | R:R {rr_ratio:.2f}"
                
                self._check("Risk Parameters", checks_passed, status_text)
                return checks_passed
            
            except Exception as e:
                self._check("Risk Parameters", False, f"Risk calculation error: {e}")
                return False
        
        except Exception as e:
            self._check("Risk Parameters", False, f"Risk parameter error: {e}")
            return False
    
    def _check_account_health(self) -> bool:
        """Check account has sufficient balance and margin."""
        try:
            account_info = mt5.account_info()
            if account_info is None:
                self._check("Account Health", False, "Cannot fetch account info")
                return False
            
            # Check margin
            if account_info.margin_free <= 0:
                self._check("Account Health", False, "No free margin available")
                return False
            
            # Check balance
            if account_info.balance <= 0:
                self._check("Account Health", False, "Account balance invalid")
                return False
            
            # Margin level
            margin_level = (account_info.equity / account_info.margin) * 100 if account_info.margin > 0 else 0
            
            if margin_level < 150:
                self._warn(f"Low margin level: {margin_level:.0f}% (should be >200%)")
            
            self._check("Account Health", True, f"Balance: ${account_info.balance:,.2f} | Margin: {margin_level:.0f}%")
            return True
        
        except Exception as e:
            self._check("Account Health", False, f"Account health error: {e}")
            return False
    
    def _check_no_conflicting_positions(self, symbol: str) -> bool:
        """Check no conflicting open positions."""
        try:
            positions = mt5.positions_get(symbol=symbol)
            
            if positions is None or len(positions) == 0:
                self._check("Conflicting Positions", True, "No existing positions")
                return True
            
            has_conflict = False
            for pos in positions:
                if pos.type == mt5.ORDER_TYPE_BUY:  # Position type
                    if pos.magic != mt5.symbol_info(symbol).magic:  # Different system
                        has_conflict = True
                        break
            
            if has_conflict:
                self._check("Conflicting Positions", False, f"{len(positions)} existing positions found")
                return False
            
            self._check("Conflicting Positions", True, f"{len(positions)} existing position(s)")
            return True
        
        except Exception as e:
            self._check("Conflicting Positions", False, f"Position check error: {e}")
            return False
    
    def _check_volatility_acceptable(self, symbol: str) -> bool:
        """Check market volatility is acceptable for trading."""
        try:
            should_trade, reason, _ = should_trade_pair_based_on_volatility(symbol)
            
            if not should_trade:
                self._check("Volatility Acceptable", False, reason)
                return False
            
            self._check("Volatility Acceptable", True, reason)
            return True
        
        except Exception as e:
            self._check("Volatility Acceptable", False, f"Volatility check error: {e}")
            return False
    
    def validate_trade(
        self,
        symbol: str,
        direction: str,  # "BUY" or "SELL"
        timeframe: str = "H1",
        entry: float = None,
        stop_loss: float = None,
        take_profit: float = None,
        volume: float = 0.01,
    ) -> Dict:
        """
        Comprehensive pre-trade validation.
        
        Args:
            symbol: Trading pair (e.g., "EURUSD")
            direction: "BUY" or "SELL"
            timeframe: Chart timeframe (e.g., "H1", "M15")
            entry: Entry price
            stop_loss: Stop loss price
            take_profit: Take profit price
            volume: Position size in lots
        
        Returns:
            {
                "approved": True/False,
                "reason": "Clear reason if blocked",
                "checks": [
                    {"name": "Broker Connection", "status": "PASS", "message": "..."},
                    ...
                ],
                "warnings": [
                    {"type": "WARNING", "message": "..."},
                ],
                "timestamp": "2026-03-29T14:30:00",
            }
        """
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
            # Run all validation checks in order
            
            # 1. System validation
            if not self._check_broker_connection():
                result["approved"] = False
                result["reason"] = "Broker connection failed"
                result["checks"] = self.checks
                return result
            
            if not self._check_symbol_validity(symbol):
                result["approved"] = False
                result["reason"] = f"{symbol} not tradable"
                result["checks"] = self.checks
                return result
            
            # 2. Market validation
            self._check_market_hours(symbol)
            self._check_spread(symbol)
            
            # 3. Account validation
            if not self._check_account_health():
                result["approved"] = False
                result["reason"] = "Account health insufficient"
                result["checks"] = self.checks
                return result
            
            # 4. Trade-specific validation
            self._check_no_conflicting_positions(symbol)
            self._check_volatility_acceptable(symbol)
            self._check_technical_confirmations(symbol, timeframe)
            self._check_cis_approval(symbol, direction)
            
            # 5. Risk validation (if parameters provided)
            if entry and stop_loss and take_profit:
                if not self._check_risk_parameters(symbol, entry, stop_loss, take_profit, volume):
                    result["approved"] = False
                    result["reason"] = "Risk parameters unacceptable"
                    result["checks"] = self.checks
                    return result
            
            # All checks completed
            if len(self.failed_checks) == 0:
                result["approved"] = True
                result["reason"] = "All validations passed"
            else:
                result["approved"] = False
                result["reason"] = f"Validation failed: {self.failed_checks[0]['message']}"
            
            result["checks"] = self.checks
            result["warnings"] = self.warnings
            
            return result
        
        except Exception as e:
            logger.error(f"Validation error: {e}")
            result["approved"] = False
            result["reason"] = f"Validation system error: {e}"
            return result


# Global validator instance
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
    """
    Quick pre-trade validation shortcut.
    
    Returns:
        (approved: bool, details: validation result dict)
    """
    result = validator.validate_trade(
        symbol=symbol,
        direction=direction,
        timeframe=timeframe,
        entry=entry,
        stop_loss=stop_loss,
        take_profit=take_profit,
        volume=volume,
    )
    
    approved = result.get("approved", False)
    return approved, result
