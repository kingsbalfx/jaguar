"""
FALLBACK STRATEGY 3 — Multi-timeframe market-structure fallback.

Activation:
  - Only after Strategy 1 (ICT 12-gate) and Strategy 2 (Kingsbalfx) have both returned no valid trade.
  - Does not compete with or replace either primary strategy.

Entry pipeline:
  1. HTF bias (H1 directional structure)
  2. Significant HH/LL + liquidity mapping
  3. Liquidity interaction/sweep
  4. Sweep vs breakout classification
  5. Opposing displacement
  6. Lower-TF CHOCH (closed candle only)
  7. MACD confirmation (execution timeframe)
  8. SMA crossover confirmation (execution timeframe)
  9. Fibonacci retracement entry zone
  10. Retracement wait + entry trigger
  11. Risk approval

Mirror trading: Any trade opened by Fallback 3 broadcasts via the existing
mirror_trading module (source_strategy="fallback3").
"""

from .evaluate import evaluate_fallback3

__all__ = ["evaluate_fallback3"]
