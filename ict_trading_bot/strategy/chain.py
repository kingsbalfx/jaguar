"""The bot's strategy chain: primary ICT then the four fallbacks.

``StrategyChain`` is the single object ``main.py`` talks to.  It replaces the
``~140``-line inline ladder that used to live in ``_evaluate_symbol`` with:

* one call for the primary strategy (ICT 12-gate),
* one call for the fallback cascade (Kingsbalfx → F3 → F4 → F5),
* a per-symbol **audit trail** (``chain_attempts``) attached to the returned
  setup so the dashboard can show *why* every strategy skipped, even the ones
  that never used to be reported (F3/F4 reasons used to be ``LOGGER.debug``-only).

The chain is stateless; the registry it owns is populated once per process.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from strategy.adapters import register_default_strategies
from strategy.base import (
    FALLBACK_ORDER,
    ICT,
    BaseStrategy,
    StrategyContext,
    StrategyResult,
)
from strategy.registry import StrategyRegistry

LOGGER = logging.getLogger("strategy.chain")


class StrategyChain:
    """Ordered, fault-isolated evaluation of the five strategies."""

    def __init__(
        self,
        registry: Optional[StrategyRegistry] = None,
        *,
        fallback_order: Sequence[str] = FALLBACK_ORDER,
        primary: str = ICT,
    ) -> None:
        self.registry = registry if registry is not None else StrategyRegistry()
        self.fallback_order = tuple(fallback_order)
        self.primary_name = primary

    # -- primary --------------------------------------------------------------
    def primary(self, ctx: StrategyContext) -> StrategyResult:
        """Run the primary (ICT) strategy in isolation."""
        strategy = self.registry.get(self.primary_name)
        if strategy is None:  # pragma: no cover - registry is always populated
            return StrategyResult(
                strategy=self.primary_name,
                setup={"strategy": self.primary_name, "executable": False, "reason": "primary_not_registered", "states": []},
                safety={"reason": "primary_not_registered"},
                skipped=True,
            )
        return self.registry.evaluate_one(self.primary_name, ctx)

    # -- fallbacks ------------------------------------------------------------
    def fallbacks(self, ctx: StrategyContext) -> StrategyResult:
        """Run the fallback cascade and return the winning (or best) result.

        On total failure the **first** fallback's setup is returned, matching the
        historical ``return None, fallback_setup, fallback_safety`` behaviour, but
        every attempted strategy's reason is preserved in ``chain_attempts``.
        """
        attempts: List[Tuple[str, StrategyResult]] = []

        def _collect(name: str, result: StrategyResult) -> None:
            attempts.append((name, result))

        winner = self.registry.run(
            ctx, order=self.fallback_order, skip=(self.primary_name,), on_result=_collect
        )
        if winner.executable:
            self._attach_attempts(winner, attempts)
            return winner
        if not attempts:  # pragma: no cover - registry always has fallbacks
            return winner
        legacy = attempts[0][1]
        self._attach_attempts(legacy, attempts)
        return legacy

    @staticmethod
    def _attach_attempts(result: StrategyResult, attempts: List[Tuple[str, StrategyResult]]) -> None:
        """Record every strategy's outcome on the returned setup (non-destructive)."""
        trail = [
            {
                "strategy": name,
                "executable": item.executable,
                "skipped": item.skipped,
                "reason": (item.setup or {}).get("reason") or (item.safety or {}).get("reason"),
                "failed_step": (item.setup or {}).get("failed_step"),
            }
            for name, item in attempts
        ]
        if not trail:
            return
        result.setup.setdefault("chain_attempts", trail)
        # The *winning* strategy's own reason must not be overwritten by the trail.
        if not result.executable:
            result.setup.setdefault("fallback_exhausted", True)

    # -- combined -------------------------------------------------------------
    def run(self, ctx: StrategyContext) -> StrategyResult:
        """Primary first; on skip, thread its setup into the fallback cascade."""
        primary_result = self.primary(ctx)
        if primary_result.executable:
            return primary_result
        continuation = ctx.with_prior(self.primary_name, primary_result.setup)
        return self.fallbacks(continuation)


def build_chain(
    *,
    build_validation: Optional[Callable] = None,
    risk_percent: Optional[Callable[[], float]] = None,
    cooldown: Optional[Callable[[], int]] = None,
    disabled_setup: Optional[Callable[[str, Mapping[str, Any]], Dict[str, Any]]] = None,
    registry: Optional[StrategyRegistry] = None,
    names=None,
) -> StrategyChain:
    """Build the production chain, injecting the ``main.py`` helpers."""
    reg = registry if registry is not None else StrategyRegistry()
    register_default_strategies(
        reg,
        build_validation=build_validation,
        risk_percent=risk_percent,
        cooldown=cooldown,
        disabled_setup=disabled_setup,
        names=names,
    )
    return StrategyChain(reg)


def outcome_of(result: StrategyResult):
    """Convenience: ``StrategyResult`` -> legacy ``(request, setup, safety)``."""
    return result.outcome()


__all__ = ["StrategyChain", "build_chain", "outcome_of"]
