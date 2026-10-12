"""Unified strategy contract for the bot's five trading strategies.

Every strategy (ICT, Kingsbalfx, Fallback 3, Fallback 4, Fallback 5) is wrapped
in a :class:`BaseStrategy` adapter so that ``main.py`` no longer has to know the
shape of each individual return value.  The framework guarantees three things
that the previous inline orchestration did not:

1. **No shared mutable state.**  Each strategy receives a context whose prior
   ``setup`` dictionaries are deep-copied before they are threaded forward, so
   one strategy can never mutate another's evidence/plan (the root cause of the
   "signal bleeding" where a Fallback-3 rejection leaked into a Fallback-4 plan).
2. **Fault isolation.**  A strategy raising an exception is recorded as a
   first-class *skip*, never a crash that aborts the symbol scan or silently
   falls through to a lower-quality strategy.
3. **A single normalised signal object.**  :class:`Signal` is the only thing a
   strategy may return when it wants a trade; ``Signal.to_request()`` produces
   the exact ``trade_request`` dictionary the executor already consumes, so the
   execution path in ``main.py`` is unchanged.

The module is deliberately dependency-free (stdlib only) so it can be imported
from ``main.py`` without creating an import cycle.
"""

from __future__ import annotations

import copy
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple

LOGGER = logging.getLogger("strategy.framework")

# ---------------------------------------------------------------------------
# Canonical strategy identifiers.
#
# These MUST match ``strategy.toggles.STRATEGY_CATALOG`` so the runtime
# ON/OFF switch and the framework agree on naming.
# ---------------------------------------------------------------------------
ICT = "ict"
KINGSBALFX = "kingsbalfx"
FALLBACK3 = "fallback3"
FALLBACK4 = "fallback4"
FALLBACK5 = "fallback5"
MIRROR = "mirror"

#: Evaluation order of the trade-generating strategies (mirror is not a
#: signal generator, it only replicates an already open trade).
STRATEGY_ORDER: Tuple[str, ...] = (ICT, KINGSBALFX, FALLBACK3, FALLBACK4, FALLBACK5)

#: Strategies the fallback chain runs after the primary (ICT) has skipped.
FALLBACK_ORDER: Tuple[str, ...] = (KINGSBALFX, FALLBACK3, FALLBACK4, FALLBACK5)

#: ``(request, setup, safety)`` triple returned to ``main.py``.
StrategyOutcome = Tuple[Optional[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]


class StrategyError(RuntimeError):
    """Raised inside a strategy for a *recoverable* evaluation failure.

    The registry converts this (and any other exception) into a skip result so
    that a single misbehaving strategy cannot take down the scan loop.
    """


@dataclass(frozen=True)
class Signal:
    """Normalised trade intent produced by a strategy.

    ``entry``/``sl``/``tp``/``lot`` are broker-ready absolute prices/volumes;
    the executor re-validates them (spread, margin, SL distance) before acting.
    """

    symbol: str
    direction: str
    entry: float
    sl: float
    tp: float
    lot: float
    strategy: str
    order_type: str = "market"
    identity: Optional[str] = None
    identity_context: Mapping[str, Any] = field(default_factory=dict)
    confidence: Optional[float] = None
    #: Strategy-specific extras that must reach the executor/logs verbatim.
    extras: Mapping[str, Any] = field(default_factory=dict)

    def to_request(self) -> Dict[str, Any]:
        """Render the executor-facing ``trade_request`` dictionary."""
        request: Dict[str, Any] = {
            "symbol": self.symbol,
            "direction": self.direction,
            "entry": self.entry,
            "sl": self.sl,
            "tp": self.tp,
            "lot": self.lot,
            "order_type": self.order_type,
            "strategy": self.strategy,
        }
        if self.identity is not None:
            request["identity"] = self.identity
        if self.identity_context:
            request["identity_context"] = dict(self.identity_context)
        if self.confidence is not None:
            request["confidence"] = self.confidence
        for key, value in self.extras.items():
            request.setdefault(key, value)
        return request


@dataclass
class StrategyContext:
    """Everything a strategy is allowed to see, threaded without shared state.

    ``prior`` maps a strategy name (``"ict"``, ``"kingsbalfx"``, ...) to a
    *private deep copy* of the setup that strategy produced.  Use
    :meth:`with_prior` to extend the chain; it returns a brand new context and
    never mutates the receiver.
    """

    symbol: str
    analysis: Mapping[str, Any]
    tick: Mapping[str, Any]
    account: Mapping[str, Any]
    positions: Sequence[Mapping[str, Any]]
    mt5_connector: Any = None
    direction: Optional[str] = None
    risk_percent: float = 0.15
    minimum_rr: float = 1.0
    smt: Mapping[str, Any] = field(default_factory=dict)
    killzone_active: bool = True
    prior: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # -- convenience accessors ------------------------------------------------
    def prior_setup(self, name: str) -> Optional[Dict[str, Any]]:
        """Return a defensive copy of a prior strategy's setup, or ``None``."""
        setup = self.prior.get(name)
        return copy.deepcopy(setup) if isinstance(setup, dict) else None

    def with_prior(self, name: str, setup: Optional[Mapping[str, Any]]) -> "StrategyContext":
        """Return a *new* context carrying ``name``'s setup (deep-copied).

        The receiver is left untouched, which is what prevents state bleeding
        between strategies.
        """
        merged = dict(self.prior)
        merged[name] = copy.deepcopy(dict(setup)) if isinstance(setup, Mapping) else {}
        return replace(self, prior=merged)

    def resolved_direction(self) -> Optional[str]:
        """Best-effort direction, matching the old ``_evaluate_symbol`` logic."""
        return (
            self.direction
            or self.analysis.get("overall_trend")
            or self.analysis.get("trend")
        )


@dataclass
class StrategyResult:
    """Standardised result of a single strategy evaluation."""

    strategy: str
    signal: Optional[Signal] = None
    setup: Dict[str, Any] = field(default_factory=dict)
    safety: Dict[str, Any] = field(default_factory=dict)
    skipped: bool = False
    error: Optional[str] = None

    @property
    def executable(self) -> bool:
        return self.signal is not None

    def outcome(self) -> StrategyOutcome:
        """Convert to the ``(request, setup, safety)`` triple ``main.py`` uses."""
        request = self.signal.to_request() if self.signal else None
        return request, self.setup, self.safety


class BaseStrategy(ABC):
    """Base class every strategy adapter derives from.

    Subclasses implement :meth:`evaluate` only.  They MUST NOT mutate
    ``ctx.analysis``/``ctx.prior``; the base class hands them defensive copies
    of everything they are expected to read.
    """

    #: Canonical id (must be in :data:`STRATEGY_ORDER`).
    name: str = ""
    #: Human label used in logs / signal payloads.
    label: str = ""
    #: Total mandatory steps, surfaced to the dashboard validation snapshot.
    total_steps: int = 0

    @abstractmethod
    def evaluate(self, ctx: StrategyContext) -> StrategyResult:
        """Evaluate the market and return a :class:`StrategyResult`."""

    # -- shared helpers -------------------------------------------------------
    def enabled(self) -> bool:
        """Runtime ON/OFF switch (fails open, matching ``strategy.toggles``)."""
        try:
            from strategy.toggles import is_enabled

            return bool(is_enabled(self.name))
        except Exception as exc:  # pragma: no cover - toggles never raise, but be safe
            LOGGER.debug("[%s] toggle lookup failed (%s); treating as ENABLED", self.name, exc)
            return True

    def disabled(self, ctx: StrategyContext, reason: str) -> StrategyResult:
        """Result produced when the runtime toggle is OFF.

        Override when the dashboard expects a full strategy stub (the historical
        ``_disabled_strategy_setup`` payload) instead of a bare skip.
        """
        return self.skipped(ctx, reason, extra_setup={"disabled_by_toggle": True})

    def skipped(
        self,
        ctx: StrategyContext,
        reason: str,
        *,
        setup: Optional[Mapping[str, Any]] = None,
        direction: Optional[str] = None,
        failed_step: Optional[str] = None,
        extra_setup: Optional[Mapping[str, Any]] = None,
    ) -> StrategyResult:
        """Build a well-formed *skip* result (never emits a signal)."""
        payload: Dict[str, Any] = {
            "strategy": self.name,
            "executable": False,
            "direction": direction if direction is not None else ctx.resolved_direction(),
            "reason": reason,
            "failed_step": failed_step,
            "states": [],
            "total_steps": self.total_steps,
        }
        if setup:
            payload.update(copy.deepcopy(dict(setup)))
            payload.setdefault("strategy", self.name)
            payload["executable"] = False
        if extra_setup:
            payload.update(copy.deepcopy(dict(extra_setup)))
        return StrategyResult(
            strategy=self.name,
            signal=None,
            setup=payload,
            safety={"reason": reason},
            skipped=True,
        )

    def rejected(
        self,
        ctx: StrategyContext,
        reason: str,
        *,
        setup: Optional[Mapping[str, Any]] = None,
        direction: Optional[str] = None,
        failed_step: Optional[str] = None,
        safety: Optional[Mapping[str, Any]] = None,
    ) -> StrategyResult:
        """Like :meth:`skipped` but marks the setup as *executable-but-blocked*.

        Used when the strategy found a valid setup but a downstream gate
        (duplicate protection, spread, session) refused execution.  Keeping
        ``executable=True`` matches the historical payload so the website can
        still show "setup found, blocked by risk".
        """
        result = self.skipped(
            ctx, reason, setup=setup, direction=direction, failed_step=failed_step
        )
        result.setup["executable"] = True
        result.safety = dict(safety) if safety else {"reason": reason}
        return result


__all__ = [
    "ICT",
    "KINGSBALFX",
    "FALLBACK3",
    "FALLBACK4",
    "FALLBACK5",
    "MIRROR",
    "STRATEGY_ORDER",
    "FALLBACK_ORDER",
    "StrategyOutcome",
    "StrategyError",
    "Signal",
    "StrategyContext",
    "StrategyResult",
    "BaseStrategy",
]
