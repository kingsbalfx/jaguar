"""
FALLBACK STRATEGY 3 - Logging
===============================
Structured logging for Fallback 3 analysis steps.
"""

import logging
from typing import Any, Dict, List, Optional

from .models import FallbackSetupResult, SweepResult, CHOCHResult, MACDResult, SMAResult, EntryZoneResult

LOGGER = logging.getLogger("fallback3")


def log_fallback3_activation(symbol: str, ict_result: str, kingsbalfx_result: str, ict_reason: str, kingsbalfx_reason: str) -> None:
    """Log when Fallback 3 is activated."""
    LOGGER.info(
        "[%s] FALLBACK3 ACTIVATED | ICT=%s (%s) | Kingsbalfx=%s (%s)",
        symbol, ict_result, ict_reason, kingsbalfx_result, kingsbalfx_reason,
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
    LOGGER.info("[%s] FALLBACK3 | %s | %s | %s%s", symbol, status, state_name, reason, extra)


def log_setup_result(symbol: str, result: FallbackSetupResult) -> None:
    """Log the complete setup result."""
    if result.executable:
        LOGGER.info(
            "[%s] FALLBACK3 TRADE | direction=%s | score=%d | sweep=%s | choch=%s | macd=%s | sma=%s | zone=%s | entry=%.5f | sl=%.5f | tp=%.5f | rr=%.2f",
            symbol,
            result.direction,
            result.score,
            result.sweep.classification,
            "yes" if result.choch.detected else "no",
            "yes" if result.macd.confirmed else "no",
            "yes" if result.sma.confirmed else "no",
            "yes" if result.entry_zone.found else "no",
            result.entry_price or 0.0,
            result.stop_loss or 0.0,
            result.take_profit or 0.0,
            result.risk_reward,
        )
    else:
        LOGGER.info(
            "[%s] FALLBACK3 SKIP | score=%d | failed_stage=%s | reason=%s",
            symbol, result.score, result.failed_stage, result.rejection_reason,
        )


def log_sweep_analysis(symbol: str, sweep: SweepResult) -> None:
    """Log sweep analysis details."""
    if not sweep.detected:
        LOGGER.debug("[%s] FALLBACK3 | No sweep interaction detected", symbol)
        return
    LOGGER.debug(
        "[%s] FALLBACK3 SWEEP | type=%s | candles=%d | penetration=%.5f | return=%s | momentum_weak=%s",
        symbol,
        sweep.classification,
        sweep.candle_count_beyond,
        sweep.penetration_distance,
        "yes" if sweep.return_inside else "no",
        "yes" if sweep.momentum_weak_beyond else "no",
    )


def log_choch_analysis(symbol: str, choch: CHOCHResult) -> None:
    """Log CHOCH analysis details."""
    if not choch.detected:
        LOGGER.debug("[%s] FALLBACK3 | CHOCH not detected", symbol)
        return
    LOGGER.debug(
        "[%s] FALLBACK3 CHOCH | direction=%s | swing=%.5f | close=%.5f | distance=%.5f | body_ratio=%.2f | invalidated=%s",
        symbol,
        choch.direction,
        choch.swing_level or 0.0,
        choch.close_level or 0.0,
        choch.close_distance_above_swing,
        choch.body_ratio,
        "yes" if choch.immediately_invalidated else "no",
    )


def log_indicator_analysis(symbol: str, macd: MACDResult, sma: SMAResult) -> None:
    """Log indicator confirmation details."""
    LOGGER.debug(
        "[%s] FALLBACK3 INDICATORS | MACD_confirmed=%s contradiction=%s cross_age=%d | SMA_confirmed=%s contradiction=%s cross_age=%d",
        symbol,
        "yes" if macd.confirmed else "no",
        "yes" if macd.contradiction else "no",
        macd.cross_age,
        "yes" if sma.confirmed else "no",
        "yes" if sma.contradiction else "no",
        sma.cross_age,
    )


def log_entry_zone(symbol: str, zone: EntryZoneResult) -> None:
    """Log entry zone details."""
    if not zone.found:
        LOGGER.debug("[%s] FALLBACK3 | Entry zone not found", symbol)
        return
    LOGGER.debug(
        "[%s] FALLBACK3 ENTRY ZONE | level=%.1f%% | low=%.5f | high=%.5f | midpoint=%.5f | price_in=%s | confluence=%s | quality=%.2f",
        symbol,
        (zone.fib_level or 0.0) * 100,
        zone.zone_low,
        zone.zone_high,
        zone.midpoint,
        "yes" if zone.price_in_zone else "no",
        ",".join(zone.confluence_types) if zone.confluence_types else "none",
        zone.quality_score,
    )
