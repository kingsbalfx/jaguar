"""
FALLBACK STRATEGY 5 — Session-Based Day-Trend Continuation Scalper.

Priority: 5th (last) in the strategy hierarchy.
  - Activated only after Strategy 1 (ICT 12-gate), Strategy 2 (Kingsbalfx),
    Fallback Strategy 3, and Fallback Strategy 4 have all returned no valid trade.

Core concept:
  1. Hard-restricted to EURUSD, XAUUSD, BTCUSD, AUDJPY.
  2. Trade only 08:00-12:00 and 14:00-20:00 (configurable timezone).
  3. Mandatory sleep window 12:00-14:00.
  4. Trade only in the confirmed intraday trend direction.
  5. Three entry models: Trend Pullback, Micro Consolidation Breakout, Trend Liquidity Sweep.
  6. Sequential re-entry with cooldown and full setup revalidation.
  7. No martingale. No increasing risk after losses.
  8. Fixed risk or profit-step scaling.
"""

import logging

from .evaluate import evaluate_fallback5

__all__ = ["evaluate_fallback5"]


# ============================================================
# Ensure the "fallback5" logger has a handler so its diagnostics
# are actually visible in the console alongside the main bot logs.
# Unlike the "ict_state_machine" logger, fallback5 logger has no
# handlers by default, so without this it silently swallows all
# FALLBACK5 activity (which is why it appeared "not to activate").
# ============================================================
_fb5_logger = logging.getLogger("fallback5")
if not _fb5_logger.handlers:
    if logging.getLogger().handlers:
        # Reuse the root logger's handler so formatting stays consistent.
        for _h in logging.getLogger().handlers:
            _fb5_logger.addHandler(_h)
    else:
        import sys
        _sh = logging.StreamHandler(sys.stdout)
        _sh.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        _fb5_logger.addHandler(_sh)
_fb5_logger.propagate = False
_fb5_logger.setLevel(logging.INFO)
