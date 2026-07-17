"""
FALLBACK STRATEGY 4 — Lower-timeframe range liquidity sweep, reclaim, displacement,
and opposite-range target model.

Priority: 4th (last) in the strategy hierarchy.
  - Activated only after Strategy 1 (ICT 12-gate), Strategy 2 (Kingsbalfx),
    and Fallback Strategy 3 have all returned no valid trade.

Core concept:
  1. A meaningful intraday range is objectively detected.
  2. Price sweeps beyond one boundary (liquidity raid).
  3. The breakout fails — price reclaims the boundary.
  4. Strong opposing displacement develops.
  5. Lower-timeframe CHOCH / BOS confirms structure change.
  6. Entry at retest or retracement toward the range interior.
  7. Targets: internal range levels → opposite boundary.

Mirror trading:
  Any trade opened by Fallback 4 broadcasts via the existing mirror_trading
  module with source_strategy="fallback4".
"""

from .evaluate import evaluate_fallback4

__all__ = ["evaluate_fallback4"]
