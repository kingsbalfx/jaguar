# =====================================================
# ICT BINARY RULE EVALUATOR (2024-2026 MENTORSHIP LOGIC)
# =====================================================
"""
Reads the actual output of liquidity_sweep_or_swing() and bos_setup()
and makes a deterministic GO / NOâ€‘GO decision.

Required core rules (must be true):
1. Liquidity Sweep OR confirmed swing structure
2. Break of Structure (MTF or LTF)
3. Displacement (body â‰¥ 55% of range, or flag from liquidity state)
4. Price in discount (for buy) or premium (for sell)
5. (Advisory) FVG or Order Block present â€“ if both missing, still OK
   if the first 4 are clean.
6. (Advisory) SMT divergence â€“ if present, even stronger.
7. Kill Zone â€“ not required, but increases confidence (via separate sizing).

If the first 4 rules pass â†’ TRADE.
"""

import logging

logger = logging.getLogger(__name__)


class ICTBinaryEvaluator:
    def __init__(self):
        self.reasons = []

    def evaluate(self, symbol, direction, analysis):
        """
        analysis must contain:
        - liquidity_sweep (dict from liquidity_sweep_or_swing)
        - break_of_structure (dict from bos_setup)
        - current_price
        - fibonacci
        - order_blocks (bool/dict)
        - fair_value_gaps (bool/dict)
        - market_structure (not used strictly)
        - smt (optional)
        """
        self.reasons = []
        liq = analysis.get("liquidity_sweep", {})
        bos = analysis.get("break_of_structure", {})
        price = analysis.get("current_price", 0)
        fib = analysis.get("fibonacci", {})
        ob = analysis.get("order_blocks")
        fvg = analysis.get("fair_value_gaps")
        smt_ok = analysis.get("smt_confirmed", False)

        # 1. Liquidity Sweep
        sweep_ok = False
        if isinstance(liq, dict):
            # Accept confirmed sweep OR swing structure with displacement
            if liq.get("confirmed") or liq.get("liquidity_sweep"):
                sweep_ok = True
            elif liq.get("mtf_swing") and liq.get("ltf_swing") and liq.get("displacement_score", 0) >= 0.55:
                sweep_ok = True
        if not sweep_ok:
            return False, "No valid liquidity sweep or swing structure"

        # 2. Break of Structure
        bos_ok = False
        if isinstance(bos, dict):
            if bos.get("confirmed") or bos.get("mtf_bos") or bos.get("ltf_bos"):
                bos_ok = True
        if not bos_ok:
            return False, "No BOS"

        # 3. Displacement (from liquidity dict or separate)
        disp = liq.get("displacement_score", 0) if isinstance(liq, dict) else 0
        disp_flag = liq.get("displacement", False) if isinstance(liq, dict) else False
        if not (disp >= 0.55 or disp_flag):
            return False, f"Insufficient displacement ({disp:.1%})"

        # 4. Premium/Discount Zone
        zone_ok = False
        if fib:
            if direction == "buy":
                # discount: 0.0 - 0.5
                f0 = fib.get("0.0")
                f05 = fib.get("0.5")
                if f0 is not None and f05 is not None and f0 <= price <= f05:
                    zone_ok = True
            else:
                f05 = fib.get("0.5")
                f1 = fib.get("1.0")
                if f05 is not None and f1 is not None and f05 <= price <= f1:
                    zone_ok = True
        if not zone_ok:
            return False, "Price not in valid fib zone"

        # 5. OB / FVG (advisory)
        if isinstance(ob, bool) and ob:
            self.reasons.append("Fresh OB present")
        elif isinstance(ob, dict) and (ob.get("bullish_fresh_ob") or ob.get("bearish_fresh_ob")):
            self.reasons.append("Fresh OB present")
        if isinstance(fvg, bool) and fvg:
            self.reasons.append("Active FVG present")
        elif isinstance(fvg, dict) and (fvg.get("bullish_fvg_active") or fvg.get("bearish_fvg_active")):
            self.reasons.append("Active FVG present")

        # 6. SMT (advisory)
        if smt_ok:
            self.reasons.append("SMT divergence confirmed â€“ extra confidence")

        return True, "ICT core rules satisfied"


class PureRuleBasedEngine:
    """Compatibility facade around the deterministic ICT binary evaluator."""

    def __init__(self):
        self.evaluator = ICTBinaryEvaluator()

    def evaluate(self, symbol, direction, analysis):
        confirmed, reason = self.evaluator.evaluate(symbol, direction, analysis or {})
        return {
            "confirmed": confirmed,
            "executable": confirmed,
            "decision": "EXECUTE" if confirmed else "SKIP",
            "reason": reason,
            "reasons": list(self.evaluator.reasons),
        }

    def should_trade(self, symbol, direction, analysis):
        result = self.evaluate(symbol, direction, analysis)
        return bool(result["confirmed"]), result["reason"]
