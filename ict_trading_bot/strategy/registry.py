"""Strategy registry — ordered, toggle-aware, fault-isolated evaluation.

The registry replaces the long ``if strategy_enabled(...)`` / ``try/except``
ladder that used to live inside ``main.py:_evaluate_symbol``.  It owns:

* **ordering** (ICT → Kingsbalfx → Fallback 3 → Fallback 4 → Fallback 5),
* **toggle enforcement** via ``strategy.toggles.is_enabled``,
* **fault isolation** — a strategy that raises is recorded as a skip and the
  chain continues instead of aborting the symbol or silently mis-falling-through,
* **state containment** — each strategy is handed a fresh
  :class:`~strategy.base.StrategyContext` built with
  :meth:`~strategy.base.StrategyContext.with_prior`, so a lower-priority
  strategy can never mutate a higher-priority setup.
"""

from __future__ import annotations

import logging
import traceback
from collections import OrderedDict
from typing import Dict, Iterable, Iterator, List, Optional, Sequence

from strategy.base import (
    FALLBACK_ORDER,
    BaseStrategy,
    StrategyContext,
    StrategyError,
    StrategyResult,
)

LOGGER = logging.getLogger("strategy.registry")


class DuplicateStrategyError(ValueError):
    """Registering two strategies under the same name without ``replace=True``."""


class StrategyRegistry:
    """An ordered collection of :class:`BaseStrategy` adapters."""

    def __init__(self, strategies: Optional[Iterable[BaseStrategy]] = None) -> None:
        self._strategies: "OrderedDict[str, BaseStrategy]" = OrderedDict()
        for strategy in strategies or ():
            self.register(strategy)

    # -- container protocol ---------------------------------------------------
    def __len__(self) -> int:
        return len(self._strategies)

    def __iter__(self) -> Iterator[BaseStrategy]:
        return iter(self._strategies.values())

    def __contains__(self, name: object) -> bool:
        return str(name) in self._strategies

    # -- registration ---------------------------------------------------------
    def register(self, strategy: BaseStrategy, *, replace: bool = False) -> None:
        if not isinstance(strategy, BaseStrategy):
            raise TypeError(f"{strategy!r} is not a BaseStrategy")
        name = str(strategy.name or "").strip().lower()
        if not name:
            raise ValueError("strategy.name must be a non-empty string")
        if name in self._strategies and not replace:
            raise DuplicateStrategyError(f"strategy '{name}' is already registered")
        strategy.name = name
        self._strategies[name] = strategy

    def get(self, name: str) -> Optional[BaseStrategy]:
        return self._strategies.get(str(name or "").strip().lower())

    def require(self, name: str) -> BaseStrategy:
        strategy = self.get(name)
        if strategy is None:
            raise KeyError(f"strategy '{name}' is not registered")
        return strategy

    def names(self) -> List[str]:
        return list(self._strategies.keys())

    # -- evaluation -----------------------------------------------------------
    def run(
        self,
        ctx: StrategyContext,
        *,
        order: Optional[Sequence[str]] = None,
        skip: Sequence[str] = (),
        on_result=None,
    ) -> StrategyResult:
        """Evaluate strategies in ``order`` and return the first executable one.

        Returns the *last* skip result when nothing executes, which preserves the
        legacy behaviour of surfacing the lowest-priority fallback's reason.
        ``on_result(name, result)`` is called for every evaluated strategy so
        callers can collect the full audit trail.
        """
        sequence = list(order) if order is not None else self.names()
        skip_set = {str(item).strip().lower() for item in skip}
        last: Optional[StrategyResult] = None
        working = ctx

        for name in sequence:
            key = str(name).strip().lower()
            if key in skip_set:
                continue
            strategy = self._strategies.get(key)
            if strategy is None:
                LOGGER.debug("strategy '%s' not registered; skipping", key)
                continue
            result = self._evaluate_one(strategy, working)
            if on_result is not None:
                try:
                    on_result(key, result)
                except Exception as exc:  # pragma: no cover - observer must not break trading
                    LOGGER.debug("on_result(%s) failed: %s", key, exc)
            if result.executable:
                return result
            last = result
            # A strategy may explicitly forbid the rest of the chain from running
            # (e.g. ICT Gate-1 failed with no direction at all, so F3/F4/F5 have
            # nothing to work with).  ``halt_chain`` keeps that legacy shortcut.
            if result.setup.get("halt_chain"):
                LOGGER.info("strategy '%s' halted the chain: %s", key, result.setup.get("reason"))
                return result
            # Thread this strategy's setup forward *without* mutation.
            working = working.with_prior(key, result.setup)

        if last is not None:
            return last
        return StrategyResult(
            strategy="none",
            setup={
                "strategy": "none",
                "executable": False,
                "reason": "no_strategies_registered",
                "states": [],
            },
            safety={"reason": "no_strategies_registered"},
            skipped=True,
        )

    def evaluate_one(self, name: str, ctx: StrategyContext) -> StrategyResult:
        """Public, toggle-aware, fault-isolated evaluation of a single strategy."""
        strategy = self._strategies.get(str(name or "").strip().lower())
        if strategy is None:
            raise KeyError(f"strategy '{name}' is not registered")
        return self._evaluate_one(strategy, ctx)

    def _evaluate_one(self, strategy: BaseStrategy, ctx: StrategyContext) -> StrategyResult:
        """Run one strategy with toggle + exception isolation."""
        if not strategy.enabled():
            LOGGER.info("[%s] DISABLED by strategy toggle", strategy.name.upper())
            return strategy.disabled(ctx, f"{strategy.name}_disabled_by_toggle")
        try:
            result = strategy.evaluate(ctx)
        except StrategyError as exc:
            LOGGER.warning("[%s] strategy error: %s", strategy.name.upper(), exc)
            return strategy.skipped(ctx, f"strategy_error:{exc}")
        except Exception as exc:  # noqa: BLE001 - one bad strategy must not stop the scan
            LOGGER.warning(
                "[%s] unexpected error: %s", strategy.name.upper(), exc, exc_info=True
            )
            LOGGER.debug(traceback.format_exc())
            return strategy.skipped(ctx, f"strategy_exception:{type(exc).__name__}:{exc}")
        if result is None:  # defensive: adapters always return a result
            return strategy.skipped(ctx, "strategy_returned_none")
        return result

    # -- diagnostics ----------------------------------------------------------
    def describe(self) -> List[Dict[str, object]]:
        return [
            {"name": s.name, "label": s.label, "total_steps": s.total_steps}
            for s in self._strategies.values()
        ]


__all__ = ["StrategyRegistry", "DuplicateStrategyError", "FALLBACK_ORDER"]
