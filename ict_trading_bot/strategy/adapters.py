"""Concrete :class:`~strategy.base.BaseStrategy` adapters for the five strategies.

Each adapter is a thin, *stateless* translation layer:

    strategy module output  ->  Signal + setup + safety

so that ``main.py`` only ever deals with :class:`~strategy.base.StrategyResult`.
The adapters never keep module-level mutable state, and every prior setup they
read is already a private copy supplied by the registry
(:meth:`~strategy.base.StrategyContext.prior_setup`), which is what stops one
strategy's evidence/plan from leaking into another's.

The few helpers that historically lived in ``main.py`` (the dashboard
*validation snapshot* builder, the risk-percent reader and the disabled-strategy
stub) are injected — see :func:`register_default_strategies` — so this module
imports nothing from ``main`` and therefore cannot create an import cycle.
"""

from __future__ import annotations

import copy
import logging
import os
from typing import Any, Callable, Dict, Mapping, Optional

from strategy.base import (
    FALLBACK3,
    FALLBACK4,
    FALLBACK5,
    ICT,
    KINGSBALFX,
    BaseStrategy,
    Signal,
    StrategyContext,
    StrategyError,
    StrategyOutcome,
    StrategyResult,
)

LOGGER = logging.getLogger("strategy.adapters")

#: Number of mandatory gates each strategy exposes to the dashboard.
ICT_STEPS = 12
KINGSBALFX_STEPS = 6


# ---------------------------------------------------------------------------
# shared helpers
# ---------------------------------------------------------------------------
def _default_risk_percent() -> float:
    """Per-trade risk, clamped exactly like ``main._risk_percent``."""
    try:
        raw = float(os.getenv("RISK_PER_TRADE", "1.0"))
    except (TypeError, ValueError):
        raw = 1.0
    return max(0.05, min(raw, 2.0))


def _minimal_validation_snapshot(symbol: str, analysis: Mapping[str, Any], setup: Mapping[str, Any]) -> Dict[str, Any]:
    """Stand-in for ``main._build_validation_snapshot`` when none is injected.

    Produces just enough structure for the dashboard to render a fallback
    strategy that has no ICT states (Kingsbalfx/F3/F4/F5).
    """
    states = list(setup.get("states") or [])
    failed = next((s for s in states if not s.get("confirmed")), None)
    return {
        "symbol": symbol,
        "strategy": setup.get("strategy") or "unknown",
        "price": analysis.get("price"),
        "rules_reached": [s.get("name") for s in states],
        "rules_passed": sum(1 for s in states if s.get("confirmed")),
        "rules_total": int(setup.get("total_steps") or len(states) or 0),
        "first_failed_step": setup.get("failed_step") or (failed or {}).get("name"),
        "first_failed_reason": setup.get("reason") or (failed or {}).get("reason"),
        "blocked_steps": [],
    }


def _signal_from_request(
    request: Mapping[str, Any],
    strategy: str,
    symbol: str,
) -> Optional[Signal]:
    """Translate a legacy ``trade_request`` dict into a :class:`Signal`."""
    if not isinstance(request, Mapping):
        return None
    try:
        entry = float(request["entry"])
        sl = float(request["sl"])
        tp = float(request["tp"])
        lot = float(request["lot"])
    except (KeyError, TypeError, ValueError) as exc:
        LOGGER.warning("[%s] malformed trade request (%s); discarding signal", strategy, exc)
        return None
    direction = str(request.get("direction") or "").lower()
    if direction not in ("buy", "sell"):
        LOGGER.warning("[%s] trade request without a valid direction; discarding", strategy)
        return None
    identity_context = request.get("identity_context") or {}
    if not isinstance(identity_context, Mapping):
        identity_context = {}
    reserved = {
        "symbol", "direction", "entry", "sl", "tp", "lot", "order_type",
        "strategy", "identity", "identity_context", "confidence",
    }
    extras = {k: v for k, v in request.items() if k not in reserved}
    confidence = request.get("confidence")
    try:
        confidence = float(confidence) if confidence is not None else None
    except (TypeError, ValueError):
        confidence = None
    return Signal(
        symbol=str(request.get("symbol") or symbol),
        direction=direction,
        entry=entry,
        sl=sl,
        tp=tp,
        lot=lot,
        strategy=strategy,
        order_type=str(request.get("order_type") or "market"),
        identity=request.get("identity"),
        identity_context=identity_context,
        confidence=confidence,
        extras=extras,
    )


# ---------------------------------------------------------------------------
# Strategy 1 — ICT 12-gate state machine
# ---------------------------------------------------------------------------
class ICTStrategy(BaseStrategy):
    """Primary 12-gate ICT state machine (``strategy.unified_strategy``).

    The adapter deliberately does **not** enrich the setup with advisories /
    validation — ``main._evaluate_symbol`` does that immediately afterwards so
    the dashboard payload stays byte-for-byte identical to the pre-refactor
    output.
    """

    name = ICT
    label = "ICT 12-gate"
    total_steps = ICT_STEPS

    def __init__(self, *, disabled_setup: Optional[Callable[[str, Mapping[str, Any]], Dict[str, Any]]] = None) -> None:
        self._disabled_setup = disabled_setup

    def evaluate(self, ctx: StrategyContext) -> StrategyResult:
        from strategy.unified_strategy import evaluate_strategy

        price = _mid_price(ctx.tick, ctx.analysis)
        if price is None:
            raise StrategyError("no tick price available for ICT evaluation")
        setup = evaluate_strategy(
            ctx.symbol,
            price,
            dict(ctx.analysis),
            smt=dict(ctx.smt or {}),
            killzone_active=bool(ctx.killzone_active),
        )
        if not isinstance(setup, dict):
            raise StrategyError("ICT state machine returned a non-dict setup")
        setup.setdefault("strategy", "ict_state_machine")
        setup.setdefault("total_steps", self.total_steps)
        signal = None
        if setup.get("executable"):
            plan = setup.get("plan") or {}
            directive = setup.get("direction") or ctx.resolved_direction()
            candidate = {
                "symbol": ctx.symbol,
                "direction": directive,
                "entry": plan.get("entry"),
                "sl": plan.get("sl"),
                "tp": plan.get("tp"),
                "lot": plan.get("lot") or plan.get("volume"),
                "identity_context": plan.get("identity_context") or setup.get("identity_context"),
                "order_type": plan.get("order_type", "market"),
            }
            signal = _signal_from_request(candidate, "ict_state_machine", ctx.symbol)
            if signal is None:
                # The state machine thought it was executable but the plan is
                # incomplete: treat it as a skip instead of crashing the scan.
                setup["executable"] = False
                setup.setdefault("reason", "ict_plan_incomplete")
        return StrategyResult(
            strategy=self.name,
            signal=signal,
            setup=setup,
            safety={"reason": None if signal else setup.get("reason")},
            skipped=signal is None,
        )

    def disabled(self, ctx: StrategyContext, reason: str) -> StrategyResult:
        """Legacy ``_disabled_strategy_setup("ict", analysis)`` payload."""
        if self._disabled_setup is not None:
            return self.skipped(
                ctx, reason, setup=self._disabled_setup(ICT, ctx.analysis),
                extra_setup={"disabled_by_toggle": True},
            )
        return super().disabled(ctx, reason)


def _mid_price(tick: Mapping[str, Any], analysis: Mapping[str, Any]) -> Optional[float]:
    """Mid price from a tick snapshot, falling back to ``analysis['price']``."""
    try:
        bid = float(tick["bid"])
        ask = float(tick["ask"])
        return (bid + ask) / 2.0
    except (KeyError, TypeError, ValueError):
        pass
    price = analysis.get("price")
    try:
        return float(price) if price is not None else None
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Generic adapter for strategies that already return (request, setup, safety)
# ---------------------------------------------------------------------------
class RunnerStrategy(BaseStrategy):
    """Adapter around a callable ``runner(ctx) -> (request, setup, safety)``.

    Used for the modular fallbacks whose ``evaluate_fallbackX`` already returns
    the triple; the adapter only converts the request into a :class:`Signal`.
    """

    def __init__(
        self,
        name: str,
        runner: Callable[[StrategyContext], StrategyOutcome],
        *,
        label: str = "",
        total_steps: int = 0,
    ) -> None:
        self.name = name
        self.label = label or name
        self.total_steps = total_steps
        self._runner = runner

    def evaluate(self, ctx: StrategyContext) -> StrategyResult:
        outcome = self._runner(ctx)
        request: Optional[Mapping[str, Any]] = None
        setup: Mapping[str, Any] = {}
        safety: Mapping[str, Any] = {}
        if isinstance(outcome, tuple) and len(outcome) == 3:
            request, setup, safety = outcome  # type: ignore[misc]
        if not isinstance(setup, Mapping):
            setup = {}
        if not isinstance(safety, Mapping):
            safety = {}
        signal = _signal_from_request(request or {}, self.name, ctx.symbol) if request else None
        return StrategyResult(
            strategy=self.name,
            signal=signal,
            setup=copy.deepcopy(dict(setup)),
            safety=dict(safety),
            skipped=signal is None,
        )


# ---------------------------------------------------------------------------
# Strategy 2 — Kingsbalfx fallback
# ---------------------------------------------------------------------------
class KingsbalfxStrategy(BaseStrategy):
    """Secondary fallback that runs when the ICT state machine has skipped.

    Reads the ICT setup from ``ctx.prior_setup(ICT)`` — never from a shared
    dict — so its ``primary_ict_skip`` evidence is always an accurate snapshot
    of *this* symbol's ICT evaluation.
    """

    name = KINGSBALFX
    label = "Kingsbalfx fallback"
    total_steps = KINGSBALFX_STEPS

    def __init__(
        self,
        *,
        build_validation: Optional[Callable[[str, Mapping[str, Any], Mapping[str, Any]], Dict[str, Any]]] = None,
        risk_percent: Optional[Callable[[], float]] = None,
        cooldown: Optional[Callable[[], int]] = None,
        disabled_setup: Optional[Callable[[str, Mapping[str, Any]], Dict[str, Any]]] = None,
        evaluate: Optional[Callable[..., Dict[str, Any]]] = None,
    ) -> None:
        self._build_validation = build_validation or _minimal_validation_snapshot
        self._risk_percent = risk_percent or _default_risk_percent
        self._cooldown = cooldown or (lambda: int(os.getenv("SETUP_COOLDOWN_SECONDS", "1800")))
        self._disabled_setup = disabled_setup
        self._evaluate = evaluate

    def _evaluator(self) -> Callable[..., Dict[str, Any]]:
        if self._evaluate is not None:
            return self._evaluate
        from kingsbalfx_concept import evaluate as _evaluate

        return _evaluate

    def disabled(self, ctx: StrategyContext, reason: str) -> StrategyResult:
        """Legacy ``_disabled_strategy_setup("kingsbalfx", analysis)`` payload."""
        if self._disabled_setup is not None:
            return self.skipped(
                ctx, reason, setup=self._disabled_setup(KINGSBALFX, ctx.analysis),
                extra_setup={"disabled_by_toggle": True},
            )
        return super().disabled(ctx, reason)

    def evaluate(self, ctx: StrategyContext) -> StrategyResult:
        ict_setup = ctx.prior_setup(ICT) or {}
        direction = ctx.resolved_direction()

        # Hard skip: Gate-1 structural conflict with no direction at all means
        # Kingsbalfx cannot possibly align either — do not waste an evaluation.
        if ict_setup.get("failed_step") == "higher_timeframe_narrative" and not direction:
            return self.skipped(
                ctx,
                "h1_narrative_unclear",
                failed_step="higher_timeframe_narrative",
                extra_setup={
                    # ``direction`` must stay null here, so it cannot be
                    # re-derived from the analysis by ``skipped()``.
                    "direction": None,
                    # Legacy behaviour: no point trying F3/F4/F5 when even the
                    # H1 narrative failed to resolve.
                    "halt_chain": True,
                    "primary_ict_skip": {
                        "failed_step": ict_setup.get("failed_step"),
                        "reason": ict_setup.get("reason"),
                    },
                },
            )

        LOGGER.info(
            "[%s] ICT SKIP -> KINGSBALFX FALLBACK | failed_step=%s | reason=%s",
            ctx.symbol,
            ict_setup.get("failed_step"),
            ict_setup.get("reason"),
        )
        result = self._evaluator()(
            ctx.symbol,
            direction,
            ctx.mt5_connector,
            analysis=dict(ctx.analysis),
            tick=dict(ctx.tick),
            account=dict(ctx.account),
            risk_percent=self._risk_percent(),
            minimum_rr=ctx.minimum_rr,
        )
        setup = self._kingsbalfx_setup(result or {})
        setup["primary_ict_skip"] = {
            "failed_step": ict_setup.get("failed_step"),
            "reason": ict_setup.get("reason"),
            "direction": ict_setup.get("direction"),
            "passed_steps": sum(1 for s in ict_setup.get("states", []) if s.get("confirmed")),
            "total_steps": ICT_STEPS,
        }
        setup.setdefault("evidence", {})["primary_ict_skip"] = setup["primary_ict_skip"]
        if ict_setup.get("validation"):
            setup["primary_ict_validation"] = copy.deepcopy(ict_setup["validation"])
            setup.setdefault("evidence", {})["primary_ict_validation"] = setup["primary_ict_validation"]
        setup["validation"] = self._build_validation(ctx.symbol, ctx.analysis, setup)
        if setup.get("primary_ict_validation"):
            setup["validation"]["primary_ict"] = setup["primary_ict_validation"]

        request = (result or {}).get("request")
        if not request:
            return self.rejected(
                ctx, (result or {}).get("reason") or "kingsbalfx_rejected", setup=setup
            )
        signal = _signal_from_request(request, "kingsbalfx", ctx.symbol)
        if signal is None:
            return self.rejected(ctx, "kingsbalfx_malformed_request", setup=setup)

        # Global duplicate / cooldown protection.
        from risk.protection import can_trade, setup_identity

        identity = setup_identity(ctx.symbol, signal.direction, signal.identity_context)
        if not can_trade(ctx.symbol, identity, cooldown=self._cooldown()):
            return self.rejected(ctx, "duplicate_setup", setup=setup)
        from dataclasses import replace as _replace

        signal = _replace(signal, identity=identity)

        # Broker-side safety validation (spread, margin, SL distance).
        from execution.pre_trade_validator import validate_execution_safety

        safe, safety = validate_execution_safety(
            ctx.symbol,
            signal.direction,
            signal.entry,
            signal.sl,
            signal.tp,
            signal.lot,
            dict(ctx.account),
            list(ctx.positions),
        )
        if not safe:
            return self.rejected(
                ctx,
                (safety or {}).get("reason") or "unsafe_execution",
                setup=setup,
                safety=safety,
            )
        return StrategyResult(strategy=self.name, signal=signal, setup=setup, safety=dict(safety or {}))

    @staticmethod
    def _kingsbalfx_setup(result: Mapping[str, Any]) -> Dict[str, Any]:
        """Normalise the Kingsbalfx decision into the shared setup shape."""
        raw_setup = result.get("setup") or {}
        evidence = raw_setup.get("evidence") or {}
        states = evidence.get("states") or []
        failed = next((s for s in states if not s.get("confirmed")), None)
        request = result.get("request") or {}
        return {
            "strategy": "kingsbalfx",
            "executable": bool(result.get("valid")),
            "direction": raw_setup.get("direction") or request.get("direction"),
            "mode": raw_setup.get("mode"),
            "reason": result.get("reason") or raw_setup.get("reason"),
            "failed_step": failed.get("name") if failed else None,
            "states": copy.deepcopy(states),
            "total_steps": KINGSBALFX_STEPS,
            "plan": {
                "entry": raw_setup.get("entry") or request.get("entry"),
                "sl": raw_setup.get("sl") or request.get("sl"),
                "tp": raw_setup.get("tp") or request.get("tp"),
                "rr": raw_setup.get("rr"),
            },
            "target": raw_setup.get("target"),
            "entry_zone": raw_setup.get("entry_zone"),
            "evidence": copy.deepcopy(evidence),
            "raw": copy.deepcopy(raw_setup),
        }


# ---------------------------------------------------------------------------
# Fallback strategies 3 / 4 / 5
# ---------------------------------------------------------------------------
class FallbackStrategy(BaseStrategy):
    """Base for the three modular fallback strategies.

    ``module_path`` / ``entry_point`` identify the lazy import; subclasses only
    declare where they live and which prior setups they consume.
    """

    module_path = ""
    entry_point = ""
    #: Prior setups (by canonical name) this strategy wants in the call.
    consumes: tuple = ()

    def __init__(
        self,
        *,
        risk_percent: Optional[Callable[[], float]] = None,
        disabled_setup: Optional[Callable[[str, Mapping[str, Any]], Dict[str, Any]]] = None,
    ) -> None:
        self._risk_percent = risk_percent or _default_risk_percent
        self._disabled_setup = disabled_setup

    def disabled(self, ctx: StrategyContext, reason: str) -> StrategyResult:
        """Legacy ``_disabled_strategy_setup("<name>", analysis)`` payload."""
        if self._disabled_setup is not None:
            return self.skipped(
                ctx, reason, setup=self._disabled_setup(self.name, ctx.analysis),
                extra_setup={"disabled_by_toggle": True},
            )
        return super().disabled(ctx, reason)

    def _runner(self) -> Callable[..., StrategyOutcome]:
        import importlib

        module = importlib.import_module(self.module_path)
        try:
            return getattr(module, self.entry_point)
        except AttributeError as exc:  # pragma: no cover - guards a broken deploy
            raise StrategyError(f"{self.module_path}.{self.entry_point} missing") from exc

    def _call_kwargs(self, ctx: StrategyContext) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {
            "symbol": ctx.symbol,
            "direction": ctx.resolved_direction(),
            "analysis": dict(ctx.analysis),
            "tick": dict(ctx.tick),
            "account": dict(ctx.account),
            "positions": list(ctx.positions),
            "mt5_connector": ctx.mt5_connector,
            "risk_percent": self._risk_percent(),
            "minimum_rr": ctx.minimum_rr,
        }
        for source in self.consumes:
            key = "ict_setup" if source == ICT else f"{source}_setup"
            kwargs[key] = ctx.prior_setup(source) or {}
        return kwargs

    def evaluate(self, ctx: StrategyContext) -> StrategyResult:
        outcome = self._runner()(**self._call_kwargs(ctx))
        if not (isinstance(outcome, tuple) and len(outcome) == 3):
            raise StrategyError(f"{self.name} returned {type(outcome).__name__}, expected a 3-tuple")
        request, setup, safety = outcome  # type: ignore[misc]
        setup_dict = copy.deepcopy(dict(setup)) if isinstance(setup, Mapping) else {}
        setup_dict.setdefault("strategy", self.name)
        safety_dict = dict(safety) if isinstance(safety, Mapping) else {}
        signal = _signal_from_request(request, self.name, ctx.symbol) if request else None
        if signal is not None:
            LOGGER.info(
                "[%s] %s | valid trade found | %s entry=%s sl=%s tp=%s lot=%s",
                ctx.symbol, self.name.upper(), signal.direction.upper(),
                signal.entry, signal.sl, signal.tp, signal.lot,
            )
        else:
            reason = (
                setup_dict.get("reason")
                or safety_dict.get("reason")
                or ("malformed_trade_request" if request else "no_valid_setup")
            )
            LOGGER.debug("[%s] %s | skipped | %s", ctx.symbol, self.name.upper(), reason)
        return StrategyResult(
            strategy=self.name,
            signal=signal,
            setup=setup_dict,
            safety=safety_dict,
            skipped=signal is None,
        )


class Fallback3Strategy(FallbackStrategy):
    """Fallback 3 — liquidity sweep + CHoCH confirmation model."""

    name = FALLBACK3
    label = "Fallback 3"
    total_steps = 6
    module_path = "strategy.fallback_strategy3"
    entry_point = "evaluate_fallback3"
    consumes = (ICT, KINGSBALFX)


class Fallback4Strategy(FallbackStrategy):
    """Fallback 4 — Asian-range sweep continuation model."""

    name = FALLBACK4
    label = "Fallback 4"
    total_steps = 6
    module_path = "strategy.fallback_strategy4"
    entry_point = "evaluate_fallback4"
    consumes = (ICT, KINGSBALFX, FALLBACK3)


class Fallback5Strategy(FallbackStrategy):
    """Fallback 5 — session/trend model with A/B/C entry models."""

    name = FALLBACK5
    label = "Fallback 5"
    total_steps = 6
    module_path = "strategy.fallback_strategy5"
    entry_point = "evaluate_fallback5"
    consumes = (ICT, KINGSBALFX, FALLBACK3, FALLBACK4)


# ---------------------------------------------------------------------------
# registration
# ---------------------------------------------------------------------------
def register_default_strategies(
    registry,
    *,
    build_validation: Optional[Callable] = None,
    risk_percent: Optional[Callable[[], float]] = None,
    cooldown: Optional[Callable[[], int]] = None,
    disabled_setup: Optional[Callable[[str, Mapping[str, Any]], Dict[str, Any]]] = None,
    names=None,
) -> None:
    """Register the five production adapters on ``registry``.

    ``build_validation``/``risk_percent``/``cooldown``/``disabled_setup`` are the
    ``main.py`` helpers that must keep living in ``main`` (they read module-level
    state); everything else is self-contained.
    """
    wanted = {str(n).strip().lower() for n in names} if names else None

    def _want(key: str) -> bool:
        return wanted is None or key in wanted

    if _want(ICT):
        registry.register(ICTStrategy(disabled_setup=disabled_setup), replace=True)
    if _want(KINGSBALFX):
        registry.register(
            KingsbalfxStrategy(
                build_validation=build_validation,
                risk_percent=risk_percent,
                cooldown=cooldown,
                disabled_setup=disabled_setup,
            ),
            replace=True,
        )
    if _want(FALLBACK3):
        registry.register(
            Fallback3Strategy(risk_percent=risk_percent, disabled_setup=disabled_setup), replace=True
        )
    if _want(FALLBACK4):
        registry.register(
            Fallback4Strategy(risk_percent=risk_percent, disabled_setup=disabled_setup), replace=True
        )
    if _want(FALLBACK5):
        registry.register(
            Fallback5Strategy(risk_percent=risk_percent, disabled_setup=disabled_setup), replace=True
        )


__all__ = [
    "ICTStrategy",
    "KingsbalfxStrategy",
    "Fallback3Strategy",
    "Fallback4Strategy",
    "Fallback5Strategy",
    "FallbackStrategy",
    "RunnerStrategy",
    "register_default_strategies",
]
