"""Compatibility wrapper for the canonical pre-trade analysis module.

This file used to contain an old D1/H4/M30 alignment copy. It is intentionally
kept as a wrapper so any manual/path-based reference uses the live H1/M15
standard implementation from strategy.pre_trade_analysis.
"""

from strategy.pre_trade_analysis import *  # noqa: F401,F403
