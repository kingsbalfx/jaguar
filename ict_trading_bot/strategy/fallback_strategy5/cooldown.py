"""
FALLBACK STRATEGY 5 — Cooldown Logic
======================================
Multi-level cooldown after each trade exit.
Cooldown duration depends on exit reason.
"""

import time
from typing import Dict, Optional, Tuple

from . import config
from .daily_stats import DailyStatsTracker, get_stats


# In-memory cooldown state
_cooldowns: Dict[str, float] = {}  # setup_id -> cooldown_until


def set_cooldown(
    setup_id: str,
    exit_reason: str,
    stats: Optional[DailyStatsTracker] = None,
) -> None:
    """
    Set cooldown based on exit reason.
    Cooldown is measured in M1 candle closes.
    """
    if not setup_id:
        return

    if exit_reason == "take_profit":
        duration = config.COOLDOWN_TP
    elif exit_reason == "break_even":
        duration = config.COOLDOWN_BREAK_EVEN
    elif exit_reason == "stop_loss":
        duration = config.COOLDOWN_SL
    elif exit_reason in ("manual", "risk_management"):
        duration = config.COOLDOWN_MANUAL
    else:
        duration = config.COOLDOWN_SL

    # Increase cooldown if consecutive losses
    if stats:
        consecutive_losses = stats.get_consecutive_losses()
        if consecutive_losses >= 2:
            duration = config.COOLDOWN_2LOSS

    # Each M1 candle = 1 minute
    cooldown_seconds = duration * 60
    _cooldowns[setup_id] = time.time() + cooldown_seconds


def check_cooldown(setup_id: str) -> Tuple[bool, int]:
    """
    Check if a setup is still in cooldown.
    Returns (in_cooldown, seconds_remaining).
    """
    cooldown_until = _cooldowns.get(setup_id)
    if cooldown_until is None:
        return False, 0

    remaining = int(cooldown_until - time.time())
    if remaining <= 0:
        _cooldowns.pop(setup_id, None)
        return False, 0

    return True, remaining


def clear_cooldown(setup_id: str) -> None:
    """Clear cooldown for a setup."""
    _cooldowns.pop(setup_id, None)


def clear_all_cooldowns() -> None:
    """Clear all cooldowns (session reset)."""
    _cooldowns.clear()
