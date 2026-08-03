"""
FALLBACK STRATEGY 5 — Daily & Session Statistics
===================================================
Tracks trades, PnL in R, consecutive wins/losses, and session-level limits.
Resets on session change and new trading day.
"""

import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from . import config
from .session import get_day_id, classify_session, SESSION_1, SESSION_2, SLEEP


class DailyStatsTracker:
    """
    Tracks all Fallback 5 statistics for the current trading session and day.
    Thread-safe via single-threaded design (or use locks in multi-threaded context).
    """

    def __init__(self):
        self._reset_all()

    def _reset_all(self):
        """Full reset for a new trading day."""
        self._day_id: str = ""
        self._trades: List[dict] = []
        self._session_r: float = 0.0
        self._daily_r: float = 0.0
        self._consecutive_wins: int = 0
        self._consecutive_losses: int = 0
        self._session_active_setup: Optional[dict] = None
        self._day_started: bool = False
        self._current_session: str = ""
        self._setups_log: List[dict] = []

    def check_day_reset(self) -> bool:
        """
        Check if a new trading day has started and reset if so.
        Returns True if a reset occurred.
        """
        today = get_day_id()
        if today != self._day_id:
            was = self._day_id
            self._reset_all()
            self._day_id = today
            self._day_started = True
            return True
        return False

    def check_session_reset(self) -> bool:
        """
        Check if we've changed session (especially the sleep window).
        Returns True if a session-level reset occurred.
        """
        session = classify_session()
        if session == SLEEP:
            # Reset session-level counters during sleep
            self._session_r = 0.0
            self._session_active_setup = None
            self._current_session = SLEEP
            return True
        return False

    def register_setup_scanned(
        self,
        symbol: str,
        model: str,
        direction: str,
        passed: bool,
        score: int,
        reason: str = "",
    ) -> None:
        """Log a setup scan event."""
        self._setups_log.append({
            "symbol": symbol,
            "model": model,
            "direction": direction,
            "passed": passed,
            "score": score,
            "reason": reason,
            "timestamp": time.time(),
        })

    def register_trade_open(
        self,
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
        setup_data: dict = None,
    ) -> None:
        """Register a new trade opening."""
        trade = {
            "symbol": symbol,
            "direction": direction,
            "model": model,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "lot": lot,
            "rr": rr,
            "score": score,
            "setup_id": setup_id,
            "setup_data": setup_data or {},
            "open_time": time.time(),
            "close_time": None,
            "exit_reason": None,
            "realised_r": 0.0,
            "holding_candles": 0,
        }
        self._trades.append(trade)
        self._session_active_setup = trade

    def register_trade_close(
        self,
        setup_id: str,
        exit_price: float,
        exit_reason: str,
        holding_candles: int,
    ) -> Optional[dict]:
        """
        Register a trade closing and update statistics.
        Returns the trade dict or None if not found.
        """
        trade = None
        for t in self._trades:
            if t.get("setup_id") == setup_id and t.get("close_time") is None:
                trade = t
                break

        if trade is None:
            return None

        # Calculate realised R
        entry = trade.get("entry_price", 0)
        stop = trade.get("stop_loss", 0)
        if exit_price and entry and stop:
            risk_distance = abs(entry - stop)
            if risk_distance > 0:
                if trade.get("direction") == "buy":
                    realised_r = (exit_price - entry) / risk_distance
                else:
                    realised_r = (entry - exit_price) / risk_distance
            else:
                realised_r = 0.0
        else:
            realised_r = 0.0

        trade["close_time"] = time.time()
        trade["exit_price"] = exit_price
        trade["exit_reason"] = exit_reason
        trade["realised_r"] = round(realised_r, 2)
        trade["holding_candles"] = holding_candles

        # Update statistics
        self._session_r += realised_r
        self._daily_r += realised_r

        if realised_r > 0:
            self._consecutive_wins += 1
            self._consecutive_losses = 0
        else:
            self._consecutive_losses += 1
            self._consecutive_wins = 0

        self._session_active_setup = None
        return trade

    def set_active_setup(self, setup: dict) -> None:
        """Set the currently active setup."""
        self._session_active_setup = setup

    def get_active_setup(self, symbol: str) -> Optional[dict]:
        """Get active setup for a symbol, if any."""
        if self._session_active_setup and self._session_active_setup.get("symbol") == symbol:
            return self._session_active_setup
        return None

    def clear_active_setup(self) -> None:
        """Clear the active setup reference."""
        self._session_active_setup = None

    def get_session_trade_count(self) -> int:
        """Get number of trades opened this session."""
        return len([t for t in self._trades if t.get("close_time") is None])

    def get_daily_trade_count(self) -> int:
        """Get number of trades opened today."""
        return len(self._trades)

    def get_symbol_trades(self, symbol: str) -> int:
        """Get number of active + closed trades for this symbol."""
        return len([t for t in self._trades if t.get("symbol") == symbol])

    def get_session_r(self) -> float:
        """Get current session realised PnL in R."""
        return round(self._session_r, 2)

    def get_daily_r(self) -> float:
        """Get current daily realised PnL in R."""
        return round(self._daily_r, 2)

    def get_consecutive_wins(self) -> int:
        """Get consecutive wins count."""
        return self._consecutive_wins

    def get_consecutive_losses(self) -> int:
        """Get consecutive losses count."""
        return self._consecutive_losses

    def get_recent_setups(self, symbol: str, limit: int = 3) -> List[dict]:
        """Get recent setups for duplicate check."""
        relevant = [
            s for s in self._setups_log
            if s.get("symbol") == symbol and s.get("passed")
        ]
        return relevant[-limit:]

    def get_trades(self) -> List[dict]:
        """Get all trades registered this session/day."""
        return list(self._trades)

    def get_summary(self) -> dict:
        """Get a summary dict of current stats."""
        return {
            "day_id": self._day_id,
            "session_trades": self.get_session_trade_count(),
            "daily_trades": self.get_daily_trade_count(),
            "session_r": self._session_r,
            "daily_r": self._daily_r,
            "consecutive_wins": self._consecutive_wins,
            "consecutive_losses": self._consecutive_losses,
            "active_setup": self._session_active_setup is not None,
        }

    def get_active_trades(self) -> List[dict]:
        """Get all currently active (open) trades."""
        return [t for t in self._trades if t.get("close_time") is None]


# Singleton instance
_stats = DailyStatsTracker()


def get_stats() -> DailyStatsTracker:
    """Get the global stats tracker instance."""
    return _stats


def reset_stats() -> None:
    """Reset the global stats tracker."""
    _stats._reset_all()
