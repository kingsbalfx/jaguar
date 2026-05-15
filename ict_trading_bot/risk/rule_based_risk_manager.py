# =====================================================
# PURE RULE-BASED POSITION SIZING & RISK MANAGEMENT
# =====================================================
"""
Simple, deterministic position sizing based on:
1. Account balance
2. Risk per trade (fixed %)
3. Stop loss distance (pips)
4. Asset class rules
5. Correlation limits

NO intelligent lot sizing
NO dynamic adjustments based on ML/history
NO market analysis scoring
"""

import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RuleBasedRiskParams:
    """Immutable risk parameters."""
    
    # Account-based rules
    RISK_PER_TRADE_PERCENT = 2.0  # Risk only 2% of account per trade
    MAX_CONCURRENT_TRADES = 5
    MAX_DAILY_LOSS_PERCENT = 5.0  # Max daily loss before stopping
    
    # Asset class rules
    FOREX_MIN_STOP_PIPS = 20  # Minimum SL for forex
    FOREX_MAX_STOP_PIPS = 200  # Maximum SL for forex
    FOREX_MIN_RR = 1.5  # Minimum 1.5:1 risk/reward
    
    METALS_MIN_STOP_PIPS = 50
    METALS_MAX_STOP_PIPS = 300
    METALS_MIN_RR = 2.0
    
    CRYPTO_MIN_STOP_PIPS = 100
    CRYPTO_MAX_STOP_PIPS = 500
    CRYPTO_MIN_RR = 1.5
    
    # Correlation protection
    MAX_SAME_CURRENCY_EXPOSURE = 0.06  # 6% max in one currency pair
    MAX_TOTAL_CORRELATION = 0.8  # Max correlation coefficient
    
    # Trading session rules
    LONDON_SESSION_MULTIPLIER = 1.0  # Normal risk during liquid hours
    NY_SESSION_MULTIPLIER = 1.0
    ASIA_SESSION_MULTIPLIER = 0.7  # Reduced risk (lower liquidity)
    OFF_HOURS_MULTIPLIER = 0.5  # Minimal risk outside major sessions
    
    # News impact rules
    HIGH_IMPACT_NEWS_DISABLED = True  # No trades during high-impact news
    MEDIUM_IMPACT_NEWS_MULTIPLIER = 0.5
    
    # Volatility rules
    MIN_ATR_PERCENT = 0.05  # Minimum 0.05% ATR (avoid dead markets)
    MAX_ATR_PERCENT = 3.0  # Maximum 3% ATR (avoid crazy volatility)


class RuleBasedRiskManager:
    """
    Deterministic position sizing using only rules.
    """
    
    def __init__(self):
        self.params = RuleBasedRiskParams()
        self.violations = []

    def calculate_position_size(
        self,
        symbol: str,
        direction: str,  # 'buy' or 'sell'
        account_balance: float,
        current_price: float,
        stop_loss_price: float,
        asset_class: str,  # 'forex', 'metals', 'crypto'
        atr: float,
        session: str = "other",
        news_impact: str = "none",
        open_positions: int = 0,
        correlation_risk: float = 0.0,
    ) -> Tuple[float, str, Dict]:
        """
        Calculate position size using ONLY rule-based logic.
        
        Returns:
            (lot_size, reason, breakdown)
        """
        self.violations = []
        
        # ============================================================
        # GATE 1: PRE-QUALIFICATION CHECKS
        # ============================================================
        
        # Check: Account balance valid
        if account_balance <= 0:
            return 0.0, "Account balance invalid", {"error": "invalid_balance"}
        
        # Check: Max concurrent trades
        if open_positions >= self.params.MAX_CONCURRENT_TRADES:
            return 0.0, f"Max concurrent trades reached ({open_positions}/{self.params.MAX_CONCURRENT_TRADES})", {
                "gate": "max_trades",
                "open": open_positions,
                "max": self.params.MAX_CONCURRENT_TRADES,
            }
        
        # Check: News impact
        if news_impact == "high" and self.params.HIGH_IMPACT_NEWS_DISABLED:
            return 0.0, "High-impact news active - no trades", {
                "gate": "news_impact",
                "news": news_impact,
            }
        
        # Check: Stop loss distance
        stop_pips = abs(current_price - stop_loss_price)
        min_stop, max_stop = self._get_asset_stop_limits(asset_class)
        
        if stop_pips < min_stop:
            return 0.0, f"Stop loss too tight: {stop_pips:.0f} pips < {min_stop:.0f} (minimum)", {
                "gate": "stop_too_tight",
                "stop_pips": stop_pips,
                "min_pips": min_stop,
            }
        
        if stop_pips > max_stop:
            return 0.0, f"Stop loss too wide: {stop_pips:.0f} pips > {max_stop:.0f} (maximum)", {
                "gate": "stop_too_wide",
                "stop_pips": stop_pips,
                "max_pips": max_stop,
            }
        
        # Check: Risk/reward ratio
        min_rr = self._get_asset_min_rr(asset_class)
        risk_in_pips = stop_pips
        # Assume profit target is at least min_rr * risk
        reward_in_pips = risk_in_pips * min_rr
        
        # Check: Volatility ranges
        atr_percent = (atr / current_price * 100.0) if current_price > 0 else 0.0
        if atr_percent < self.params.MIN_ATR_PERCENT:
            return 0.0, f"Market too quiet: {atr_percent:.2f}% ATR < {self.params.MIN_ATR_PERCENT}% minimum", {
                "gate": "low_volatility",
                "atr_percent": atr_percent,
                "min_atr_percent": self.params.MIN_ATR_PERCENT,
            }
        
        if atr_percent > self.params.MAX_ATR_PERCENT:
            return 0.0, f"Market too volatile: {atr_percent:.2f}% ATR > {self.params.MAX_ATR_PERCENT}% maximum", {
                "gate": "high_volatility",
                "atr_percent": atr_percent,
                "max_atr_percent": self.params.MAX_ATR_PERCENT,
            }
        
        # Check: Correlation risk
        if correlation_risk > self.params.MAX_TOTAL_CORRELATION:
            return 0.0, f"Correlation risk too high: {correlation_risk:.2f} > {self.params.MAX_TOTAL_CORRELATION}", {
                "gate": "correlation",
                "risk": correlation_risk,
                "max": self.params.MAX_TOTAL_CORRELATION,
            }
        
        # ============================================================
        # GATE 2: CALCULATE BASE POSITION SIZE
        # ============================================================
        
        # Base risk: 2% of account per trade
        base_risk_amount = account_balance * (self.params.RISK_PER_TRADE_PERCENT / 100.0)
        
        # Adjust for session (liquidity)
        session_multiplier = self._get_session_multiplier(session)
        risk_amount = base_risk_amount * session_multiplier
        
        # Adjust for news impact
        if news_impact == "medium":
            risk_amount *= self.params.MEDIUM_IMPACT_NEWS_MULTIPLIER
        
        # Calculate lots based on stop loss distance
        pip_value = self._calculate_pip_value(symbol, asset_class, current_price)
        if pip_value <= 0:
            return 0.0, "Cannot calculate pip value", {
                "error": "invalid_pip_value",
                "symbol": symbol,
            }
        
        stop_loss_amount = risk_in_pips * pip_value
        if stop_loss_amount <= 0:
            return 0.0, "Stop loss amount invalid", {
                "error": "invalid_sl_amount",
                "stop_loss_amount": stop_loss_amount,
            }
        
        lot_size = risk_amount / stop_loss_amount
        
        # Round to standard lot sizes (0.01 per lot)
        lot_size = round(lot_size, 2)
        
        if lot_size < 0.01:
            return 0.0, "Calculated lot size too small (< 0.01)", {
                "calculated_lot": lot_size,
                "account": account_balance,
                "risk_amount": risk_amount,
                "sl_amount": stop_loss_amount,
            }
        
        # ============================================================
        # GATE 3: POSITION SIZE LIMITS
        # ============================================================
        
        # Check: Max position per currency pair
        max_per_pair = account_balance * (self.params.MAX_SAME_CURRENCY_EXPOSURE / 100.0) / pip_value
        if lot_size > max_per_pair:
            lot_size = max_per_pair
            self.violations.append(f"Position capped at pair limit: {lot_size:.2f} lots")
        
        # ============================================================
        # CALCULATE PROFIT TARGET (using min R/R)
        # ============================================================
        
        tp_pips = risk_in_pips * min_rr
        tp_price = (current_price + (tp_pips * self._get_pip_size(symbol, asset_class))
                    if direction == "buy" else
                    current_price - (tp_pips * self._get_pip_size(symbol, asset_class)))
        
        # ============================================================
        # RESULT BREAKDOWN
        # ============================================================
        
        breakdown = {
            "gate_passed": True,
            "asset_class": asset_class,
            "account_balance": account_balance,
            "session": session,
            "session_multiplier": session_multiplier,
            "news_impact": news_impact,
            "correlation_risk": correlation_risk,
            "base_risk_percent": self.params.RISK_PER_TRADE_PERCENT,
            "adjusted_risk_percent": self.params.RISK_PER_TRADE_PERCENT * session_multiplier * (
                self.params.MEDIUM_IMPACT_NEWS_MULTIPLIER if news_impact == "medium" else 1.0
            ),
            "base_risk_amount": base_risk_amount,
            "adjusted_risk_amount": risk_amount,
            "stop_loss_distance_pips": round(risk_in_pips, 2),
            "stop_loss_price": stop_loss_price,
            "take_profit_distance_pips": round(tp_pips, 2),
            "take_profit_price": round(tp_price, int(self._get_precision(symbol, asset_class))),
            "min_rr_ratio": min_rr,
            "pip_value": pip_value,
            "calculated_lot": round(lot_size, 2),
            "open_positions": open_positions,
            "max_concurrent": self.params.MAX_CONCURRENT_TRADES,
            "violations": self.violations,
        }
        
        reason = (
            f"Position sized: {lot_size:.2f} lots | Risk: {risk_amount:.2f} "
            f"({self.params.RISK_PER_TRADE_PERCENT * session_multiplier:.1f}% of {account_balance:.0f}) "
            f"| SL: {stop_loss_price} ({risk_in_pips:.0f}p) "
            f"| TP: {tp_price:.5f} ({tp_pips:.0f}p, {min_rr}:1 RR) "
            f"| Session: {session} ({session_multiplier}x)"
        )
        
        return lot_size, reason, breakdown

    # ============================================================
    # HELPER METHODS (Pure Rule-Based Lookup Tables)
    # ============================================================

    def _get_asset_stop_limits(self, asset_class: str) -> Tuple[float, float]:
        """Get min/max stop loss pips based on asset class."""
        limits = {
            "forex": (self.params.FOREX_MIN_STOP_PIPS, self.params.FOREX_MAX_STOP_PIPS),
            "metals": (self.params.METALS_MIN_STOP_PIPS, self.params.METALS_MAX_STOP_PIPS),
            "crypto": (self.params.CRYPTO_MIN_STOP_PIPS, self.params.CRYPTO_MAX_STOP_PIPS),
        }
        return limits.get(asset_class, (20, 200))

    def _get_asset_min_rr(self, asset_class: str) -> float:
        """Get minimum risk/reward ratio based on asset class."""
        ratios = {
            "forex": self.params.FOREX_MIN_RR,
            "metals": self.params.METALS_MIN_RR,
            "crypto": self.params.CRYPTO_MIN_RR,
        }
        return ratios.get(asset_class, 1.5)

    def _get_session_multiplier(self, session: str) -> float:
        """Get position size multiplier based on trading session."""
        multipliers = {
            "london": self.params.LONDON_SESSION_MULTIPLIER,
            "newyork": self.params.NY_SESSION_MULTIPLIER,
            "asia": self.params.ASIA_SESSION_MULTIPLIER,
            "other": self.params.OFF_HOURS_MULTIPLIER,
        }
        return multipliers.get(session.lower(), self.params.OFF_HOURS_MULTIPLIER)

    def _calculate_pip_value(self, symbol: str, asset_class: str, current_price: float) -> float:
        """Calculate value per pip based on symbol type and price."""
        # This is a simplified calculation - adjust for your broker
        try:
            if "JPY" in symbol.upper():
                pip_size = 0.01
                if asset_class == "crypto":
                    return 1.0  # 1 pip = $1 for crypto
                return 100.0  # 1 pip = $100 for majors vs JPY
            else:
                pip_size = 0.0001
                if asset_class == "crypto":
                    return 10.0  # 1 pip = $10 for crypto
                elif current_price > 0:
                    return 100.0 / current_price  # Scales with price
                return 100.0
        except Exception as e:
            logger.error(f"Pip value calculation failed: {e}")
            return 0.0

    def _get_pip_size(self, symbol: str, asset_class: str) -> float:
        """Get pip size (smallest unit) for symbol."""
        if "JPY" in symbol.upper():
            return 0.01
        elif asset_class == "crypto":
            return 0.00001
        else:
            return 0.0001

    def _get_precision(self, symbol: str, asset_class: str) -> int:
        """Get decimal precision for price display."""
        if "JPY" in symbol.upper():
            return 2
        elif asset_class == "crypto":
            return 5
        else:
            return 5


# Global instance
rule_based_risk_manager = RuleBasedRiskManager()
