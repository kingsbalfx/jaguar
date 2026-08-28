"""
FALLBACK STRATEGY 5 — State Machine
======================================
Full state machine for the session-based day-trend continuation scalper.

State progression:
F5_DISABLED → F5_SESSION_CLOSED → F5_RISK_GATE → F5_SYMBOL_GATE → F5_DATA_CHECK →
F5_TREND_ANALYSIS → F5_TREND_CONFIRMED → F5_SETUP_SCAN → F5_PULLBACK_TRACKING →
F5_CONFIRMATION_PENDING → F5_ENTRY_READY → F5_ORDER_APPROVAL → F5_ORDER_PENDING →
F5_TRADE_ACTIVE → F5_EXIT_PENDING → F5_TRADE_CLOSED → F5_COOLDOWN →
F5_REENTRY_SCAN → (F5_TREND_CONFIRMED / F5_SESSION_CLOSED / F5_SYMBOL_PAUSED / F5_DAY_LOCKED)
"""

from typing import List, Optional, Dict, Any

from . import config
from .fb5_logging import log_state_transition
from .session import is_session_open, is_in_sleep, is_entry_cutoff


# State names
F5_DISABLED = "F5_DISABLED"
F5_SESSION_CLOSED = "F5_SESSION_CLOSED"
F5_RISK_GATE = "F5_RISK_GATE"
F5_SYMBOL_GATE = "F5_SYMBOL_GATE"
F5_DATA_CHECK = "F5_DATA_CHECK"
F5_TREND_ANALYSIS = "F5_TREND_ANALYSIS"
F5_TREND_CONFIRMED = "F5_TREND_CONFIRMED"
F5_SETUP_SCAN = "F5_SETUP_SCAN"
F5_PULLBACK_TRACKING = "F5_PULLBACK_TRACKING"
F5_CONFIRMATION_PENDING = "F5_CONFIRMATION_PENDING"
F5_ENTRY_READY = "F5_ENTRY_READY"
F5_ORDER_APPROVAL = "F5_ORDER_APPROVAL"
F5_ORDER_PENDING = "F5_ORDER_PENDING"
F5_TRADE_ACTIVE = "F5_TRADE_ACTIVE"
F5_EXIT_PENDING = "F5_EXIT_PENDING"
F5_TRADE_CLOSED = "F5_TRADE_CLOSED"
F5_COOLDOWN = "F5_COOLDOWN"
F5_REENTRY_SCAN = "F5_REENTRY_SCAN"
F5_SYMBOL_PAUSED = "F5_SYMBOL_PAUSED"
F5_DAY_LOCKED = "F5_DAY_LOCKED"
F5_SLEEP = "F5_SLEEP"


# Full progression sequence
PROGRESSION = [
    F5_DISABLED,
    F5_SESSION_CLOSED,
    F5_RISK_GATE,
    F5_SYMBOL_GATE,
    F5_DATA_CHECK,
    F5_TREND_ANALYSIS,
    F5_TREND_CONFIRMED,
    F5_SETUP_SCAN,
    F5_PULLBACK_TRACKING,
    F5_CONFIRMATION_PENDING,
    F5_ENTRY_READY,
    F5_ORDER_APPROVAL,
    F5_ORDER_PENDING,
    F5_TRADE_ACTIVE,
    F5_EXIT_PENDING,
    F5_TRADE_CLOSED,
    F5_COOLDOWN,
    F5_REENTRY_SCAN,
    F5_SYMBOL_PAUSED,
    F5_DAY_LOCKED,
    F5_SLEEP,
]


class Fallback5StateResult:
    """Result of a state machine evaluation."""

    def __init__(self):
        self.states: List[dict] = []
        self.current_state: str = F5_DISABLED
        self.executable: bool = False
        self.rejection_reason: str = ""
        self.failed_stage: str = ""
        self.score: int = 0
        self.score_components: dict = {}
        self.direction: Optional[str] = None
        self.setup_id: str = ""
        self.model: str = ""
        self.entry_price: Optional[float] = None
        self.stop_loss: Optional[float] = None
        self.take_profit: Optional[float] = None
        self.position_size: float = 0.0
        self.risk_reward: float = 0.0
        self.evidence: dict = {}
        self.session_state: str = ""
        self.trend_direction: Optional[str] = None
        self.trend_strength: str = ""

    def add_state(self, name: str, confirmed: bool, reason: str = "", evidence: dict = None) -> None:
        """Add a state to the progression log."""
        self.states.append({
            "name": name,
            "confirmed": confirmed,
            "reason": reason,
            "evidence": evidence or {},
        })
        self.current_state = name
        if not confirmed:
            self.failed_stage = name
            self.rejection_reason = reason


class Fallback5StateMachine:
    """State machine for Fallback 5."""

    def process(
        self,
        symbol: str,
        analysis: dict,
        tick: dict,
        account: dict,
        positions: list,
        is_enabled: bool,
        risk_gate_passed: bool,
        risk_gate_reason: str,
        allowed_symbol: bool,
        direction: Optional[str],
        trend_direction: Optional[str],
        trend_strength: str,
        setup_model: str,
        setup_score: int,
        model_result: dict,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        rr: float,
        lot: float,
        identity: str,
        stats_summary: dict,
    ) -> Fallback5StateResult:
        """Run the full state machine with all pre-computed data."""
        result = Fallback5StateResult()
        result.session_state = "open" if is_session_open() else "closed"
        result.trend_direction = trend_direction
        result.trend_strength = trend_strength

        # F5_DISABLED
        if not is_enabled:
            result.add_state(F5_DISABLED, False, "fallback5_disabled")
            return result
        result.add_state(F5_DISABLED, True, "enabled")

        # F5_SESSION_CLOSED
        if is_in_sleep():
            result.add_state(F5_SLEEP, False, "sleep_window_12_14")
            return result
        if is_entry_cutoff():
            result.add_state(F5_SESSION_CLOSED, False, "entry_cutoff_period")
            return result
        if not is_session_open():
            result.add_state(F5_SESSION_CLOSED, False, "outside_trading_hours")
            return result
        result.add_state(F5_SESSION_CLOSED, True, f"session_open:{result.session_state}")

        # F5_RISK_GATE
        if not risk_gate_passed:
            result.add_state(F5_RISK_GATE, False, risk_gate_reason, {"risk_gate": risk_gate_reason})
            return result
        result.add_state(F5_RISK_GATE, True, "passed", {"risk_gate": "all_checks_ok"})

        # F5_SYMBOL_GATE
        if not allowed_symbol:
            result.add_state(F5_SYMBOL_GATE, False, f"symbol_not_allowed:{symbol}")
            return result
        result.add_state(F5_SYMBOL_GATE, True, f"symbol_allowed:{symbol}")

        # F5_DATA_CHECK
        min_candles = max(config.EMA_MEDIUM, 30)
        htf = (analysis.get("HTF") or {}).get("recent_candles", [])
        mtf = (analysis.get("MTF") or {}).get("recent_candles", [])
        exec_candles = (analysis.get("M1") or {}).get("recent_candles", [])

        data_ok = (
            len(htf) >= 20
            and len(mtf) >= min_candles
            and len(exec_candles) >= 20
        )
        if not data_ok:
            result.add_state(F5_DATA_CHECK, False, "insufficient_candles", {
                "htf": len(htf), "mtf": len(mtf), "exec": len(exec_candles),
            })
            return result
        result.add_state(F5_DATA_CHECK, True, "data_ok", {
            "htf": len(htf), "mtf": len(mtf), "exec": len(exec_candles),
        })

        # F5_TREND_ANALYSIS
        if not trend_direction:
            result.add_state(F5_TREND_ANALYSIS, False, "no_trend_detected")
            return result
        result.add_state(F5_TREND_ANALYSIS, True, f"trend={trend_direction}/{trend_strength}")

        # F5_TREND_CONFIRMED
        if trend_direction in ("neutral", "conflicting", "transitioning"):
            result.add_state(F5_TREND_CONFIRMED, False, f"trend_not_actionable:{trend_direction}")
            return result
        result.add_state(F5_TREND_CONFIRMED, True, f"trend_confirmed:{trend_direction}")

        # F5_SETUP_SCAN
        if not setup_model:
            result.add_state(F5_SETUP_SCAN, False, "no_valid_setup", {"models_tried": model_result.get("models_tried", [])})
            return result
        result.add_state(F5_SETUP_SCAN, True, f"model={setup_model}_score={setup_score}")

        # F5_PULLBACK_TRACKING
        if not model_result.get("pullback_detected") and not model_result.get("consolidation_detected") and not model_result.get("sweep_detected"):
            result.add_state(F5_PULLBACK_TRACKING, False, "no_pullback_or_consolidation_or_sweep")
            return result
        result.add_state(F5_PULLBACK_TRACKING, True, "setup_structure_ok")

        # F5_CONFIRMATION_PENDING
        if entry_price <= 0:
            result.add_state(F5_CONFIRMATION_PENDING, False, "no_entry_price")
            return result
        result.add_state(F5_CONFIRMATION_PENDING, True, f"entry={entry_price:.5f}")

        # F5_ENTRY_READY
        if stop_loss <= 0 or take_profit <= 0:
            result.add_state(F5_ENTRY_READY, False, "no_sl_or_tp")
            return result
        result.add_state(F5_ENTRY_READY, True, f"sl={stop_loss:.5f}_tp={take_profit:.5f}")

        # F5_ORDER_APPROVAL
        order_approved = rr >= config.MIN_RR and lot > 0 and entry_price > 0
        if not order_approved:
            fail_reason = f"rr_{rr:.2f}<{config.MIN_RR}_or_lot_{lot}_or_price_{entry_price}"
            result.add_state(F5_ORDER_APPROVAL, False, fail_reason)
            return result
        result.add_state(F5_ORDER_APPROVAL, True, f"approved_rr={rr:.2f}_lot={lot:.4f}")

        # F5_ORDER_PENDING
        result.add_state(F5_ORDER_PENDING, True, "order_ready")

        # Populate final result
        result.executable = True
        result.score = setup_score
        result.direction = direction
        result.model = setup_model
        result.entry_price = entry_price
        result.stop_loss = stop_loss
        result.take_profit = take_profit
        result.position_size = lot
        result.risk_reward = rr
        result.setup_id = identity
        result.evidence = {
            "model_result": model_result,
            "trend_evidence": {},
            "stats": stats_summary,
        }

        return result
