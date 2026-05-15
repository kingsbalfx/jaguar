# =====================================================
# PURE RULE-BASED ICT TRADING SYSTEM
# =====================================================
"""
Complete rule-based implementation following strict ICT and SMT principles.
NO intelligence scoring, NO ML components, NO learning systems.

Decision Flow:
Market Data → ICT Rules Check → SMT Validation → Risk Rules → Execute/Skip
"""

from typing import Dict, Tuple, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class RuleBasedICTTrader:
    """
    Pure rule-based ICT trading system with strict SMT validation.
    """

    def __init__(self):
        self.core_rules = {
            "liquidity_sweep": self._check_liquidity_sweep,
            "break_of_structure": self._check_bos,
            "premium_discount_zone": self._check_premium_discount_zone,
            "displacement": self._check_displacement,
            "smt_divergence": self._check_smt_divergence,
            "order_block_alignment": self._check_order_block_alignment,
            "fvg_confirmation": self._check_fvg_confirmation
        }

    def evaluate_trade_signal(self, analysis: Dict, symbol: str, direction: str) -> Tuple[bool, str]:
        """
        Evaluate trade signal using strict rule-based logic.
        Returns: (should_trade, reason)
        """
        # RULE 1: Liquidity Sweep (MANDATORY)
        if not self._check_liquidity_sweep(analysis, direction):
            return False, "ICT Rule Violation: No liquidity sweep detected"

        # RULE 2: Break of Structure (MANDATORY)
        if not self._check_bos(analysis, direction):
            return False, "ICT Rule Violation: No break of structure"

        # RULE 3: Premium/Discount Zone (MANDATORY)
        if not self._check_premium_discount_zone(analysis, direction):
            return False, "ICT Rule Violation: Not in valid premium/discount zone"

        # RULE 4: Displacement (MANDATORY)
        if not self._check_displacement(analysis, direction):
            return False, "ICT Rule Violation: Insufficient displacement"

        # RULE 5: SMT Divergence (MANDATORY)
        if not self._check_smt_divergence(analysis, symbol, direction):
            return False, "SMT Rule Violation: No smart money divergence"

        # RULE 6: Order Block Alignment (MANDATORY)
        if not self._check_order_block_alignment(analysis, direction):
            return False, "ICT Rule Violation: Order block not aligned"

        # RULE 7: FVG Confirmation (MANDATORY)
        if not self._check_fvg_confirmation(analysis, direction):
            return False, "ICT Rule Violation: FVG not confirmed"

        return True, "All ICT and SMT rules satisfied"

    def _check_liquidity_sweep(self, analysis: Dict, direction: str) -> bool:
        """MANDATORY: Check for liquidity sweep before trade entry."""
        try:
            liquidity_data = analysis.get("liquidity_sweep", {})

            if direction == "buy":
                # Bullish: Price must sweep below recent low then recover
                sweep_detected = liquidity_data.get("bullish_sweep", False)
                recovery_confirmed = liquidity_data.get("bullish_recovery", False)
                return sweep_detected and recovery_confirmed

            elif direction == "sell":
                # Bearish: Price must sweep above recent high then recover
                sweep_detected = liquidity_data.get("bearish_sweep", False)
                recovery_confirmed = liquidity_data.get("bearish_recovery", False)
                return sweep_detected and recovery_confirmed

            return False

        except Exception as e:
            logger.error(f"Liquidity sweep check failed: {e}")
            return False

    def _check_bos(self, analysis: Dict, direction: str) -> bool:
        """MANDATORY: Check for break of structure."""
        try:
            bos_data = analysis.get("break_of_structure", {})

            if direction == "buy":
                return bos_data.get("bullish_bos", False)
            elif direction == "sell":
                return bos_data.get("bearish_bos", False)

            return False

        except Exception as e:
            logger.error(f"BOS check failed: {e}")
            return False

    def _check_premium_discount_zone(self, analysis: Dict, direction: str) -> bool:
        """MANDATORY: Check if entry is in valid premium/discount zone."""
        try:
            fib_data = analysis.get("fibonacci_zones", {})
            current_price = analysis.get("current_price", 0)

            if direction == "buy":
                # Buy in discount zone (0.214-0.382 or 0.382-0.5)
                discount_zones = fib_data.get("discount_zones", [])
                return any(zone["low"] <= current_price <= zone["high"] for zone in discount_zones)

            elif direction == "sell":
                # Sell in premium zone (0.618-0.786 or 0.5-0.618)
                premium_zones = fib_data.get("premium_zones", [])
                return any(zone["low"] <= current_price <= zone["high"] for zone in premium_zones)

            return False

        except Exception as e:
            logger.error(f"Premium/discount zone check failed: {e}")
            return False

    def _check_displacement(self, analysis: Dict, direction: str) -> bool:
        """MANDATORY: Check for sufficient displacement (body/candle ratio >= 0.7)."""
        try:
            displacement_data = analysis.get("displacement", {})
            displacement_ratio = displacement_data.get("ratio", 0)

            # ICT Rule: Displacement must be >= 70%
            return displacement_ratio >= 0.7

        except Exception as e:
            logger.error(f"Displacement check failed: {e}")
            return False

    def _check_smt_divergence(self, analysis: Dict, symbol: str, direction: str) -> bool:
        """MANDATORY: Check for Smart Money divergence with correlated pairs."""
        try:
            smt_data = analysis.get("smt_divergence", {})

            # Define correlated pairs for SMT analysis
            correlated_pairs = {
                "EURUSD": "GBPUSD",
                "GBPUSD": "EURUSD",
                "AUDUSD": "NZDUSD",
                "NZDUSD": "AUDUSD",
                "XAUUSD": "XAGUSD",
                "BTCUSD": "ETHUSD"
            }

            correlated_symbol = correlated_pairs.get(symbol)
            if not correlated_symbol:
                # No correlated pair available, skip SMT check
                return True

            divergence_data = smt_data.get(correlated_symbol, {})

            if direction == "buy":
                # BUY: Symbol makes Lower Low, correlated pair fails to make LL
                return divergence_data.get("bullish_divergence", False)

            elif direction == "sell":
                # SELL: Symbol makes Higher High, correlated pair fails to make HH
                return divergence_data.get("bearish_divergence", False)

            return False

        except Exception as e:
            logger.error(f"SMT divergence check failed: {e}")
            return False

    def _check_order_block_alignment(self, analysis: Dict, direction: str) -> bool:
        """MANDATORY: Check order block alignment with trend."""
        try:
            ob_data = analysis.get("order_blocks", {})

            if direction == "buy":
                # Bullish: Must have fresh bullish order block
                return ob_data.get("bullish_fresh_ob", False)

            elif direction == "sell":
                # Bearish: Must have fresh bearish order block
                return ob_data.get("bearish_fresh_ob", False)

            return False

        except Exception as e:
            logger.error(f"Order block alignment check failed: {e}")
            return False

    def _check_fvg_confirmation(self, analysis: Dict, direction: str) -> bool:
        """MANDATORY: Check Fair Value Gap confirmation."""
        try:
            fvg_data = analysis.get("fair_value_gaps", {})

            if direction == "buy":
                # Bullish: FVG below current price, not filled
                return fvg_data.get("bullish_fvg_active", False)

            elif direction == "sell":
                # Bearish: FVG above current price, not filled
                return fvg_data.get("bearish_fvg_active", False)

            return False

        except Exception as e:
            logger.error(f"FVG confirmation check failed: {e}")
            return False

# Global instance for use across the system
rule_based_trader = RuleBasedICTTrader()</content>
<parameter name="filePath">c:\Users\kingsbal\Documents\GitHub\jaguar\ict_trading_bot\strategy\rule_based_ict_trader.py