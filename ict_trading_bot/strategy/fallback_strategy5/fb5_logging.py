"""
FALLBACK STRATEGY 5 — Structured Logging
===========================================
Detailed logging for every analysis step, trade event, and state transition.

NOTE: This module was renamed from ``logging.py`` to ``fb5_logging.py`` because a
package-local ``logging.py`` shadowed the Python standard-library ``logging``
module (``import logging`` resolved to this file, breaking ``logging.getLogger``).
Keeping the stdlib name clear lets every other module use ``import logging`` safely.
"""

import logging
from typing import Any, Dict, Optional

from .session import get_session_timestamps, classify_session, current_session_name

LOGGER = logging.getLogger("fallback5")


def log_activation(symbol: str, higher_results: dict) -> None:
    """Log when Fallback 5 becomes eligible for analysis."""
    timestamps = get_session_timestamps()
    session_state = classify_session()
    session_name = current_session_name()
    LOGGER.info(
        "FALLBACK5 | ACTIVATED | symbol=%s session=%s session_state=%s "
        "utc=%s broker=%s strategy_tz=%s "
        "ict=%s kingsbalfx=%s fb3=%s fb4=%s",
        symbol,
        session_name,
        session_state,
        timestamps["utc"],
        timestamps["broker"],
        timestamps["strategy"],
        higher_results.get("ict", "skip"),
        higher_results.get("kingsbalfx", "skip"),
        higher_results.get("fallback3", "skip"),
        higher_results.get("fallback4", "skip"),
    )


def log_skip(symbol: str, reason: str, evidence: Optional[Dict[str, Any]] = None) -> None:
    """Log a skip decision with full context."""
    timestamps = get_session_timestamps()
    ctx = ""
    if evidence:
        parts = [f"{k}={v}" for k, v in evidence.items() if not isinstance(v, (dict, list))]
        ctx = " | " + " ".join(parts)
    LOGGER.info(
        "FALLBACK5 | SKIP | symbol=%s reason=%s utc=%s%s",
        symbol, reason, timestamps["utc"], ctx,
    )


def log_trend_analysis(symbol: str, trend: str, strength: str, adx: float, ema_alignment: str) -> None:
    """Log trend classification result."""
    LOGGER.info(
        "FALLBACK5 | TREND | symbol=%s trend=%s strength=%s adx=%.1f ema=%s",
        symbol, trend, strength, adx, ema_alignment,
    )


def log_setup_scan(symbol: str, model: str, passed: bool, reason: str, score: int = 0) -> None:
    """Log setup model scan result."""
    status = "PASS" if passed else "FAIL"
    LOGGER.info(
        "FALLBACK5 | SETUP | symbol=%s model=%s status=%s score=%d reason=%s",
        symbol, model, status, score, reason,
    )


def log_trade_open(
    symbol: str,
    direction: str,
    model: str,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    lot: float,
    rr: float,
    score: int,
    setup_id: str,
    base_risk: float,
    active_risk: float,
    session_r: float,
) -> None:
    """Log a trade opening with full details."""
    timestamps = get_session_timestamps()
    LOGGER.info(
        "FALLBACK5 | TRADE OPEN | symbol=%s direction=%s model=%s "
        "entry=%.5f sl=%.5f tp=%.5f lot=%.4f rr=%.2f score=%d setup_id=%s "
        "base_risk=%.2f%% active_risk=%.2f%% session_r=%.2f utc=%s",
        symbol, direction.upper(), model,
        entry_price, stop_loss, take_profit, lot, rr, score, setup_id,
        base_risk, active_risk, session_r, timestamps["utc"],
    )


def log_trade_close(
    symbol: str,
    direction: str,
    exit_reason: str,
    exit_price: float,
    realised_r: float,
    holding_candles: int,
    setup_id: str,
) -> None:
    """Log a trade closure."""
    timestamps = get_session_timestamps()
    LOGGER.info(
        "FALLBACK5 | TRADE CLOSE | symbol=%s direction=%s exit=%s exit_price=%.5f "
        "realised_r=%.2f holding=%d candles setup_id=%s utc=%s",
        symbol, direction.upper(), exit_reason, exit_price,
        realised_r, holding_candles, setup_id, timestamps["utc"],
    )


def log_state_transition(
    symbol: str,
    state_name: str,
    passed: bool,
    reason: str = "",
    evidence: Optional[Dict[str, Any]] = None,
) -> None:
    """Log a state machine transition."""
    status = "PASS" if passed else "FAIL"
    extra = ""
    if evidence:
        parts = [f"{k}={v}" for k, v in evidence.items() if not isinstance(v, (dict, list))]
        extra = " | " + " ".join(parts)
    LOGGER.info("FALLBACK5 | %s | %s | %s%s", status, state_name, reason, extra)


def log_session_event(symbol: str, event: str, details: Optional[Dict[str, Any]] = None) -> None:
    """Log a session-level event (sleep, close, day reset, etc.)."""
    timestamps = get_session_timestamps()
    detail_str = ""
    if details:
        detail_str = " | " + " ".join(f"{k}={v}" for k, v in details.items() if not isinstance(v, (dict, list)))
    LOGGER.info(
        "FALLBACK5 | SESSION | symbol=%s event=%s utc=%s%s",
        symbol, event, timestamps["utc"], detail_str,
    )


def log_exception(symbol: str, context: str, exc: Exception) -> None:
    """Log an exception with traceback."""
    LOGGER.error(
        "FALLBACK5 | ERROR | symbol=%s context=%s error=%s",
        symbol, context, exc, exc_info=True,
    )


def log_entry_event(symbol: str, event: str, details: dict) -> None:
    """Detailed entry event log."""
    detail_str = " ".join(f"{k}={v}" for k, v in details.items())
    LOGGER.info("FALLBACK5 | ENTRY | symbol=%s event=%s %s", symbol, event, detail_str)


def log_management_action(symbol: str, ticket: int, action: str, details: dict) -> None:
    """Log position management action."""
    detail_str = " ".join(f"{k}={v}" for k, v in details.items())
    LOGGER.info("FALLBACK5 | MGMT | symbol=%s ticket=%d action=%s %s", symbol, ticket, action, detail_str)
