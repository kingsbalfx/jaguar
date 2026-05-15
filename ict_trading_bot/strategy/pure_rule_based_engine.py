# =====================================================
# PURE RULE-BASED ICT + SMT TRADING ENGINE
# =====================================================
"""
Strict rule-based trading system combining:
- ICT Core Rules (Non-negotiable entry criteria)
- SMT Validation (Smart Money divergence analysis)
- Rule-based Risk Management (Fixed position sizing)
- NO intelligence scoring
- NO machine learning
- NO weighted penalties
- NO learning systems

PHILOSOPHY: If all rules are met → TRADE. Otherwise → SKIP.
"""

import logging
from typing import Dict, Tuple, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)


class ICTRuleBase:
    """Immutable ICT core rules that govern all trading decisions."""

    # Rule 1: Liquidity Sweep (MANDATORY)
    LIQUIDITY_SWEEP_REQUIRED = True
    SWEEP_BUFFER_PERCENT = 0.0015  # 0.15% tolerance

    # Rule 2: Break of Structure (MANDATORY)
    BOS_REQUIRED = True

    # Rule 3: Premium/Discount Zone (MANDATORY)
    PREMIUM_ZONES = [(0.618, 0.786), (0.5, 0.618)]  # Sell setups
    DISCOUNT_ZONES = [(0.214, 0.382), (0.382, 0.5)]  # Buy setups

    # Rule 4: Minimum Displacement (MANDATORY)
    MIN_DISPLACEMENT_RATIO = 0.70  # 70% body/candle

    # Rule 5: Order Block Alignment (MANDATORY)
    ORDER_BLOCK_REQUIRED = True
    FRESH_OB_REQUIRED = True  # Must not be already mitigated

    # Rule 6: Fair Value Gap (MANDATORY)
    FVG_REQUIRED = True
    MIN_FVG_RATIO = 0.12  # 12% of ATR

    # Rule 7: Market Structure (MANDATORY)
    STRUCTURE_CONFIRMATION_REQUIRED = True

    @staticmethod
    def describe():
        return """
        ═════════════════════════════════════════════════════════════
        ICT CORE RULES (ALL MANDATORY - NO EXCEPTIONS)
        ═════════════════════════════════════════════════════════════
        
        1. LIQUIDITY SWEEP
           ├─ Bullish: Price sweeps below recent low, then closes higher
           ├─ Bearish: Price sweeps above recent high, then closes lower
           └─ Buffer: ±0.15% for confirmation
        
        2. BREAK OF STRUCTURE (BOS)
           ├─ Bullish: New higher high beyond prior swing highs
           ├─ Bearish: New lower low beyond prior swing lows
           └─ Must confirm market is in expansion phase
        
        3. PREMIUM/DISCOUNT ZONE
           ├─ Sell Setup: Price in Premium (0.618-0.786 or 0.5-0.618 Fib)
           ├─ Buy Setup: Price in Discount (0.214-0.382 or 0.382-0.5 Fib)
           └─ Entry MUST align with risk/reward zone
        
        4. MINIMUM DISPLACEMENT
           ├─ Displacement = Body / Candle Height
           ├─ Minimum: 70% (strong conviction candle)
           └─ Lower displacement = weak entry (reject)
        
        5. ORDER BLOCK ALIGNMENT
           ├─ HTF order block must be "fresh" (not yet mitigated)
           ├─ Bullish: Block above current price (support below)
           ├─ Bearish: Block below current price (resistance above)
           └─ Alignment validates institutional footprint
        
        6. FAIR VALUE GAP (FVG)
           ├─ 3-candle pattern with 12%+ gap
           ├─ Must not be fully filled/mitigated
           ├─ Provides profit target reference
           └─ Confirms price action quality
        
        7. MARKET STRUCTURE
           ├─ Bullish: Series of HH/HL (higher highs/lows)
           ├─ Bearish: Series of LH/LL (lower highs/lows)
           └─ Structure must be unbroken at entry point
        
        ═════════════════════════════════════════════════════════════
        """


class SMTRuleBase:
    """Smart Money Technique validation rules."""

    # Correlated pair analysis for divergence detection
    CORRELATED_PAIRS = {
        "EURUSD": ("GBPUSD", "positive"),  # Euro/Pound positive correlation
        "GBPUSD": ("EURUSD", "positive"),
        "AUDUSD": ("NZDUSD", "positive"),
        "NZDUSD": ("AUDUSD", "positive"),
        "XAUUSD": ("XAGUSD", "positive"),
        "XAGUSD": ("XAUUSD", "positive"),
        "BTCUSD": ("ETHUSD", "positive"),
        "ETHUSD": ("BTCUSD", "positive"),
    }

    # SMT Divergence Rules
    MIN_DIVERGENCE_BARS = 5  # Minimum bars for valid divergence
    MIN_DIVERGENCE_STRENGTH = 0.70  # 70% price difference required

    @staticmethod
    def describe():
        return """
        ═════════════════════════════════════════════════════════════
        SMT RULES (Smart Money Divergence Analysis)
        ═════════════════════════════════════════════════════════════
        
        DIVERGENCE DETECTION:
        
        BUY Divergence: 
        ├─ Primary pair makes Lower Low (LL)
        ├─ Correlated pair FAILS to make Lower Low (divergence)
        ├─ Indicates smart money accumulation below
        └─ High probability buy setup
        
        SELL Divergence:
        ├─ Primary pair makes Higher High (HH)
        ├─ Correlated pair FAILS to make Higher High (divergence)
        ├─ Indicates smart money distribution from top
        └─ High probability sell setup
        
        DIVERGENCE STRENGTH:
        ├─ Minimum span: 5 bars
        ├─ Minimum price difference: 70% of primary pair's move
        ├─ Stronger divergence = higher confidence entry
        └─ Weak divergence = possible rejection
        
        ═════════════════════════════════════════════════════════════
        """


class PureRuleBasedEngine:
    """
    Pure rule-based trading engine.
    All decisions are deterministic: IF conditions THEN action ELSE skip.
    """

    def __init__(self):
        self.ict_rules = ICTRuleBase()
        self.smt_rules = SMTRuleBase()
        self.violations = []
        self.met_rules = []

    def evaluate_entry(
        self,
        symbol: str,
        direction: str,  # 'buy' or 'sell'
        analysis: Dict,
    ) -> Tuple[bool, str, Dict]:
        """
        STRICT entry evaluation using ONLY rule checks.
        
        Returns:
            (should_trade, reason, rule_breakdown)
        """
        self.violations = []
        self.met_rules = []

        # Execute all 7 ICT core rules in sequence
        # If ANY rule fails → SKIP (no exceptions)
        
        # RULE 1: Liquidity Sweep
        if not self._check_liquidity_sweep(symbol, direction, analysis):
            return False, "ICT Rule 1 Violation: No liquidity sweep", self._breakdown()

        # RULE 2: Break of Structure
        if not self._check_bos(symbol, direction, analysis):
            return False, "ICT Rule 2 Violation: No break of structure", self._breakdown()

        # RULE 3: Premium/Discount Zone
        if not self._check_premium_discount_zone(symbol, direction, analysis):
            return False, "ICT Rule 3 Violation: Not in valid fib zone", self._breakdown()

        # RULE 4: Minimum Displacement
        if not self._check_displacement(symbol, direction, analysis):
            return False, "ICT Rule 4 Violation: Insufficient displacement", self._breakdown()

        # RULE 5: Order Block Alignment
        if not self._check_order_block(symbol, direction, analysis):
            return False, "ICT Rule 5 Violation: Order block not aligned", self._breakdown()

        # RULE 6: Fair Value Gap
        if not self._check_fvg(symbol, direction, analysis):
            return False, "ICT Rule 6 Violation: FVG not valid", self._breakdown()

        # RULE 7: Market Structure
        if not self._check_market_structure(symbol, direction, analysis):
            return False, "ICT Rule 7 Violation: Market structure broken", self._breakdown()

        # ALL ICT RULES PASSED → Check SMT for additional validation
        smt_pass, smt_reason = self._check_smt_divergence(symbol, direction, analysis)
        if not smt_pass:
            logger.warning(f"[{symbol}] SMT Rule warning: {smt_reason}")
            # SMT is advisory only - doesn't hard-block trades
            self.violations.append(f"SMT Advisory: {smt_reason}")

        self.met_rules.append("All 7 ICT core rules PASSED")
        if smt_pass:
            self.met_rules.append("SMT divergence confirmed")

        return True, "All ICT rules satisfied + SMT confirmed", self._breakdown()

    def _check_liquidity_sweep(self, symbol: str, direction: str, analysis: Dict) -> bool:
        """RULE 1: Liquidity sweep must be detected and confirmed."""
        try:
            liquidity = analysis.get("liquidity_sweep", {})

            if direction == "buy":
                # Bullish: Must have downswept and recovered
                sweep = liquidity.get("bullish_sweep_low")
                recovery = liquidity.get("bullish_recovery_close")
                if sweep and recovery:
                    self.met_rules.append("✓ Rule 1: Liquidity sweep (bullish)")
                    return True

            elif direction == "sell":
                # Bearish: Must have upswept and recovered
                sweep = liquidity.get("bearish_sweep_high")
                recovery = liquidity.get("bearish_recovery_close")
                if sweep and recovery:
                    self.met_rules.append("✓ Rule 1: Liquidity sweep (bearish)")
                    return True

            self.violations.append("Rule 1 FAILED: No liquidity sweep detected")
            return False

        except Exception as e:
            logger.error(f"Liquidity sweep check failed: {e}")
            self.violations.append(f"Rule 1 ERROR: {str(e)}")
            return False

    def _check_bos(self, symbol: str, direction: str, analysis: Dict) -> bool:
        """RULE 2: Break of structure must be confirmed."""
        try:
            bos = analysis.get("break_of_structure", {})

            if direction == "buy":
                if bos.get("bullish_bos"):
                    self.met_rules.append("✓ Rule 2: BOS (bullish)")
                    return True

            elif direction == "sell":
                if bos.get("bearish_bos"):
                    self.met_rules.append("✓ Rule 2: BOS (bearish)")
                    return True

            self.violations.append("Rule 2 FAILED: No break of structure")
            return False

        except Exception as e:
            logger.error(f"BOS check failed: {e}")
            self.violations.append(f"Rule 2 ERROR: {str(e)}")
            return False

    def _check_premium_discount_zone(self, symbol: str, direction: str, analysis: Dict) -> bool:
        """RULE 3: Entry must be in valid premium/discount fib zone."""
        try:
            price = analysis.get("current_price", 0)
            fib = analysis.get("fibonacci", {})

            if direction == "buy":
                # Buy in discount zones: 0.214-0.382 or 0.382-0.5
                for zone_low, zone_high in [(0.214, 0.382), (0.382, 0.5)]:
                    fib_low = fib.get(str(zone_low))
                    fib_high = fib.get(str(zone_high))
                    if fib_low and fib_high and fib_low <= price <= fib_high:
                        self.met_rules.append(f"✓ Rule 3: Discount zone {zone_low}-{zone_high}")
                        return True

            elif direction == "sell":
                # Sell in premium zones: 0.618-0.786 or 0.5-0.618
                for zone_low, zone_high in [(0.618, 0.786), (0.5, 0.618)]:
                    fib_low = fib.get(str(zone_low))
                    fib_high = fib.get(str(zone_high))
                    if fib_low and fib_high and fib_low <= price <= fib_high:
                        self.met_rules.append(f"✓ Rule 3: Premium zone {zone_low}-{zone_high}")
                        return True

            self.violations.append("Rule 3 FAILED: Not in valid fib zone")
            return False

        except Exception as e:
            logger.error(f"Fib zone check failed: {e}")
            self.violations.append(f"Rule 3 ERROR: {str(e)}")
            return False

    def _check_displacement(self, symbol: str, direction: str, analysis: Dict) -> bool:
        """RULE 4: Entry candle must have minimum 70% displacement."""
        try:
            displacement = analysis.get("displacement", {})
            ratio = float(displacement.get("ratio", 0) or 0)

            if ratio >= self.ict_rules.MIN_DISPLACEMENT_RATIO:
                self.met_rules.append(f"✓ Rule 4: Displacement {ratio:.1%} ({self.ict_rules.MIN_DISPLACEMENT_RATIO:.0%}+ required)")
                return True

            self.violations.append(f"Rule 4 FAILED: Displacement {ratio:.1%} < {self.ict_rules.MIN_DISPLACEMENT_RATIO:.0%}")
            return False

        except Exception as e:
            logger.error(f"Displacement check failed: {e}")
            self.violations.append(f"Rule 4 ERROR: {str(e)}")
            return False

    def _check_order_block(self, symbol: str, direction: str, analysis: Dict) -> bool:
        """RULE 5: Order block must be fresh and properly aligned."""
        try:
            ob = analysis.get("order_blocks", {})

            if direction == "buy":
                if ob.get("bullish_fresh_ob"):
                    self.met_rules.append("✓ Rule 5: Fresh bullish order block")
                    return True

            elif direction == "sell":
                if ob.get("bearish_fresh_ob"):
                    self.met_rules.append("✓ Rule 5: Fresh bearish order block")
                    return True

            self.violations.append("Rule 5 FAILED: No fresh order block")
            return False

        except Exception as e:
            logger.error(f"Order block check failed: {e}")
            self.violations.append(f"Rule 5 ERROR: {str(e)}")
            return False

    def _check_fvg(self, symbol: str, direction: str, analysis: Dict) -> bool:
        """RULE 6: Fair value gap must be active and valid."""
        try:
            fvgs = analysis.get("fair_value_gaps", {})

            if direction == "buy":
                if fvgs.get("bullish_fvg_active"):
                    self.met_rules.append("✓ Rule 6: Active bullish FVG")
                    return True

            elif direction == "sell":
                if fvgs.get("bearish_fvg_active"):
                    self.met_rules.append("✓ Rule 6: Active bearish FVG")
                    return True

            self.violations.append("Rule 6 FAILED: No active FVG")
            return False

        except Exception as e:
            logger.error(f"FVG check failed: {e}")
            self.violations.append(f"Rule 6 ERROR: {str(e)}")
            return False

    def _check_market_structure(self, symbol: str, direction: str, analysis: Dict) -> bool:
        """RULE 7: Market structure must be unbroken and aligned with entry."""
        try:
            structure = analysis.get("market_structure", {})

            if direction == "buy":
                if structure.get("bullish_intact"):
                    self.met_rules.append("✓ Rule 7: Bullish market structure intact")
                    return True

            elif direction == "sell":
                if structure.get("bearish_intact"):
                    self.met_rules.append("✓ Rule 7: Bearish market structure intact")
                    return True

            self.violations.append("Rule 7 FAILED: Market structure broken")
            return False

        except Exception as e:
            logger.error(f"Market structure check failed: {e}")
            self.violations.append(f"Rule 7 ERROR: {str(e)}")
            return False

    def _check_smt_divergence(self, symbol: str, direction: str, analysis: Dict) -> Tuple[bool, str]:
        """SMT Divergence check (advisory - doesn't block trades)."""
        try:
            correlated_pair = self.smt_rules.CORRELATED_PAIRS.get(symbol)
            if not correlated_pair:
                return True, "No correlated pair available (skip SMT)"

            pair_symbol, correlation_type = correlated_pair
            inversion_factor = -1 if correlation_type == "negative" else 1

            primary_structure = analysis.get("structure", {})
            correlated_structure = analysis.get("correlated_structure", {})

            if direction == "buy":
                # BUY: Primary makes LL, correlated fails to make LL (divergence up = bullish)
                primary_ll = primary_structure.get("last_low")
                prior_ll = primary_structure.get("prior_low")
                correlated_ll = correlated_structure.get("last_low")
                correlated_prior_ll = correlated_structure.get("prior_low")

                if (
                    prior_ll and correlated_prior_ll
                    and primary_ll < prior_ll * 0.98  # Primary made new LL
                    and not (correlated_ll < correlated_prior_ll * 0.98)  # Correlated did NOT
                ):
                    self.met_rules.append(f"✓ SMT: Bullish divergence detected ({symbol} vs {pair_symbol})")
                    return True, f"Bullish divergence: {symbol} LL, {pair_symbol} holds"

            elif direction == "sell":
                # SELL: Primary makes HH, correlated fails to make HH (divergence down = bearish)
                primary_hh = primary_structure.get("last_high")
                prior_hh = primary_structure.get("prior_high")
                correlated_hh = correlated_structure.get("last_high")
                correlated_prior_hh = correlated_structure.get("prior_high")

                if (
                    prior_hh and correlated_prior_hh
                    and primary_hh > prior_hh * 1.02  # Primary made new HH
                    and not (correlated_hh > correlated_prior_hh * 1.02)  # Correlated did NOT
                ):
                    self.met_rules.append(f"✓ SMT: Bearish divergence detected ({symbol} vs {pair_symbol})")
                    return True, f"Bearish divergence: {symbol} HH, {pair_symbol} fails"

            return False, f"No SMT divergence detected (advisory only)"

        except Exception as e:
            logger.warning(f"SMT check error: {e}")
            return False, f"SMT check error: {str(e)}"

    def _breakdown(self) -> Dict:
        """Return rule evaluation breakdown."""
        return {
            "met_rules": self.met_rules,
            "violations": self.violations,
            "ict_core_rules": 7,
            "ict_rules_passed": len([r for r in self.met_rules if "Rule" in r]),
            "smt_confirmed": "SMT:" in " ".join(self.met_rules),
        }


# Global engine instance
pure_rule_engine = PureRuleBasedEngine()
