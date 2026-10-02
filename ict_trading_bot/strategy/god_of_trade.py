"""God of Trade - holistic pre-trade inspector and advisory.

The God of Trade sits *above* every individual strategy (ICT 12-gate,
Kingsbalfx, Fallback 3/4/5) and inspects the whole picture before a trade is
sent to the broker. It aggregates checks that were previously scattered across
modules and adds portfolio-level intelligence that no single strategy owns:

    * Finnhub + Gemini news alignment (macro bias vs the trade)
    * daily macro-rule status
    * trading-session / entry windows
    * reward:risk sanity
    * correlated-symbol exposure (avoid stacking the same bet N times)
    * recent symbol + strategy performance (closed-deal history / loss streaks)

It returns one structured verdict::

    ALLOW   -> every check passed
    CAUTION -> soft warnings (the trade may still proceed)
    VETO    -> a hard check failed

Modes (``GOD_OF_TRADE_MODE``):
    advisory (default) -> the verdict is logged and attached to the signal, but
                          the trade still executes. Safe to enable anywhere.
    enforce            -> a VETO blocks the trade (main.py skips execution).

Environment
-----------
    GOD_OF_TRADE_ENABLED         true|false (default true)
    GOD_OF_TRADE_MODE            advisory|enforce (default advisory)
    GOD_OF_TRADE_MIN_RR          minimum reward:risk (default 1.0)
    GOD_OF_TRADE_VETO_SCORE      score below which the verdict is a VETO (45)
    GOD_OF_TRADE_MAX_CORRELATED  max same-direction correlated positions (2)
    GOD_OF_TRADE_LOSS_STREAK     consecutive losses before cooldown (3)
    GOD_OF_TRADE_LOSS_COOLDOWN   cooldown seconds after a loss streak (3600)
    GOD_OF_TRADE_LOOKBACK_DAYS   closed-deal history window (7)
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils.persistent_json import load_json_file, save_json_file
from utils.symbol_profile import canonical_symbol

logger = logging.getLogger(__name__)


def _truthy(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _float_env(name: str, default: float) -> float:
    try:
        return float(str(os.getenv(name, default)).strip())
    except (TypeError, ValueError):
        return default


def enabled() -> bool:
    return _truthy("GOD_OF_TRADE_ENABLED", True)


def mode() -> str:
    value = str(os.getenv("GOD_OF_TRADE_MODE", "advisory")).strip().lower()
    return value if value in ("advisory", "enforce") else "advisory"


def _state_file() -> Path:
    configured = os.getenv("GOD_OF_TRADE_STATE_PATH")
    base = Path(__file__).resolve().parent.parent / "data"
    return Path(configured) if configured else base / "god_of_trade_state.json"


def _load_state() -> Dict[str, Any]:
    return load_json_file(
        _state_file(),
        {"opened": {}, "outcomes": {}, "loss_streaks": {}, "updated_at": 0.0},
    )


def _save_state(state: Dict[str, Any]) -> None:
    state["updated_at"] = time.time()
    save_json_file(_state_file(), state)


def register_trade_open(symbol: str, strategy: str, direction: str = "") -> None:
    """Record that a trade was opened (feeds the performance ledger)."""
    try:
        state = _load_state()
        key = canonical_symbol(symbol)
        opened = state.setdefault("opened", {}).setdefault(key, [])
        opened.append(
            {
                "strategy": str(strategy or "unknown"),
                "direction": str(direction or "").lower(),
                "at": time.time(),
            }
        )
        state["opened"][key] = opened[-50:]
        _save_state(state)
    except Exception as exc:  # pragma: no cover - advisory must never break trading
        logger.debug("god_of_trade: register_trade_open failed: %s", exc)


def register_trade_outcome(symbol: str, strategy: str, won: bool) -> None:
    """Record a closed trade's outcome and maintain the loss-streak counter."""
    try:
        state = _load_state()
        key = canonical_symbol(symbol)
        bucket = state.setdefault("outcomes", {}).setdefault(
            key, {"wins": 0, "losses": 0, "strategies": {}}
        )
        bucket["wins" if won else "losses"] = int(bucket.get("wins" if won else "losses", 0)) + 1
        strat = str(strategy or "unknown")
        strat_bucket = bucket.setdefault("strategies", {}).setdefault(
            strat, {"wins": 0, "losses": 0}
        )
        strat_bucket["wins" if won else "losses"] = int(
            strat_bucket.get("wins" if won else "losses", 0)
        ) + 1
        streaks = state.setdefault("loss_streaks", {})
        if won:
            streaks[key] = 0
        else:
            streaks[key] = int(streaks.get(key, 0)) + 1
        _save_state(state)
    except Exception as exc:  # pragma: no cover
        logger.debug("god_of_trade: register_trade_outcome failed: %s", exc)


def loss_streak(symbol: str) -> int:
    try:
        return int((_load_state().get("loss_streaks") or {}).get(canonical_symbol(symbol), 0))
    except Exception:
        return 0


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


_DEALS_CACHE: Dict[str, Any] = {"fetched_at": 0.0, "summary": {}}


def _closed_deals_summary(lookback_days: float) -> Dict[str, Any]:
    """Best-effort win/loss summary from MT5 closed-deal history.

    Never raises: when the terminal/history is unavailable an empty summary is
    returned and the caller falls back to the in-process ledger.
    """
    now = time.time()
    ttl = _float_env("GOD_OF_TRADE_HISTORY_TTL", 300.0)
    cached = _DEALS_CACHE.get("summary") or {}
    if cached and (now - float(_DEALS_CACHE.get("fetched_at", 0.0) or 0.0)) < ttl:
        return cached

    summary: Dict[str, Any] = {
        "overall": {"wins": 0, "losses": 0},
        "by_symbol": {},
        "deals": 0,
    }
    try:
        import datetime as _dt

        import MetaTrader5 as mt5

        to_dt = _dt.datetime.now(_dt.timezone.utc)
        from_dt = to_dt - _dt.timedelta(days=max(1.0, float(lookback_days)))
        deals = mt5.history_deals_get(from_dt, to_dt) or []
        entry_out = int(getattr(mt5, "DEAL_ENTRY_OUT", 1))
        for deal in deals:
            try:
                if int(getattr(deal, "entry", -1)) != entry_out:
                    continue
                profit = (
                    float(getattr(deal, "profit", 0.0) or 0.0)
                    + float(getattr(deal, "swap", 0.0) or 0.0)
                    + float(getattr(deal, "commission", 0.0) or 0.0)
                )
                sym = canonical_symbol(getattr(deal, "symbol", "") or "")
                if not sym:
                    continue
                summary["deals"] += 1
                bucket = summary["by_symbol"].setdefault(
                    sym, {"wins": 0, "losses": 0, "net": 0.0}
                )
                bucket["net"] = round(bucket["net"] + profit, 2)
                if profit > 0:
                    bucket["wins"] += 1
                    summary["overall"]["wins"] += 1
                elif profit < 0:
                    bucket["losses"] += 1
                    summary["overall"]["losses"] += 1
            except Exception:
                continue
    except Exception as exc:  # pragma: no cover - history is optional
        logger.debug("god_of_trade: closed-deal history unavailable: %s", exc)

    _DEALS_CACHE.update(fetched_at=now, summary=summary)
    return summary


def recent_performance(
    symbol: Optional[str] = None, strategy: Optional[str] = None
) -> Dict[str, Any]:
    """Merge MT5 closed-deal history with the in-process outcome ledger."""
    key = canonical_symbol(symbol) if symbol else ""
    outcomes = (_load_state().get("outcomes") or {}).get(key, {})
    closed = _closed_deals_summary(_float_env("GOD_OF_TRADE_LOOKBACK_DAYS", 7.0))
    closed_symbol = (closed.get("by_symbol") or {}).get(key, {})

    wins = int(closed_symbol.get("wins", 0)) + int(outcomes.get("wins", 0))
    losses = int(closed_symbol.get("losses", 0)) + int(outcomes.get("losses", 0))

    strategy_stats = None
    if strategy:
        strategy_stats = ((outcomes.get("strategies") or {}).get(strategy)) or None

    total = wins + losses
    return {
        "symbol": key,
        "strategy": strategy,
        "wins": wins,
        "losses": losses,
        "trades": total,
        "win_rate": round(wins / total, 3) if total else None,
        "strategy_stats": strategy_stats,
        "loss_streak": loss_streak(symbol) if symbol else 0,
        "history_deals": int(closed.get("deals", 0)),
        "overall": closed.get("overall", {}),
    }


def inspect(context: Dict[str, Any]) -> Dict[str, Any]:
    """Inspect the whole trade picture and return a structured verdict.

    ``context`` keys (all optional): ``symbol``, ``direction``, ``strategy``,
    ``entry``, ``sl``, ``tp``, ``positions``. This function never raises and never
    places a trade - it only reports.
    """
    context = context or {}
    symbol = str(context.get("symbol") or "")
    direction = str(context.get("direction") or "").upper()
    strategy = str(context.get("strategy") or context.get("source_strategy") or "unknown")
    entry = _to_float(context.get("entry"))
    sl = _to_float(context.get("sl"))
    tp = _to_float(context.get("tp"))
    positions = context.get("positions") or []

    if not enabled():
        return {
            "enabled": False,
            "mode": mode(),
            "symbol": symbol,
            "direction": direction,
            "strategy": strategy,
            "verdict": "ALLOW",
            "score": 100,
            "checks": [],
            "reasons": [],
            "advisory": "god_of_trade disabled",
        }

    checks: List[Dict[str, Any]] = []
    state = {"score": 100}

    def note(name: str, status: str, detail: str = "") -> None:
        checks.append({"name": name, "status": status, "detail": detail})
        if status == "fail":
            state["score"] -= 30
        elif status == "warn":
            state["score"] -= 10

    # 1. Trading session
    try:
        from risk.trade_scheduler import current_session_name, is_trading_allowed

        if is_trading_allowed():
            note("session", "pass", current_session_name() or "open")
        else:
            note("session", "fail", "outside trading sessions")
    except Exception as exc:
        note("session", "warn", f"session check unavailable: {exc}")

    # 2. Reward:risk sanity
    min_rr = _float_env("GOD_OF_TRADE_MIN_RR", 1.0)
    if entry and sl and tp:
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        rr = reward / risk if risk > 0 else 0.0
        if rr < min_rr:
            note("risk_reward", "fail", f"R:R {rr:.2f} < {min_rr:.2f}")
        elif rr < min_rr * 1.5:
            note("risk_reward", "warn", f"thin R:R {rr:.2f}")
        else:
            note("risk_reward", "pass", f"R:R {rr:.2f}")
    else:
        note("risk_reward", "warn", "entry/sl/tp incomplete")

    # 3. Finnhub + Gemini news alignment
    if direction and _truthy("GOD_OF_TRADE_CHECK_NEWS", True):
        try:
            from fundamentals.news_feed import get_news_brief

            brief = get_news_brief(symbol)
            news_dir = str(brief.get("market_direction") or "NO_TRADE").upper()
            conf = float(brief.get("confidence") or 0.0)
            if news_dir in ("BUY", "SELL") and news_dir != direction:
                note("news", "fail", f"news {news_dir} opposes {direction} (conf {conf:.2f})")
            elif news_dir in ("BUY", "SELL"):
                note("news", "pass", f"news aligned {news_dir} (conf {conf:.2f})")
            else:
                note("news", "pass", f"neutral/absent (engine={brief.get('engine')})")
        except Exception as exc:
            note("news", "warn", f"news check unavailable: {exc}")

    # 4. Daily macro rule
    if direction:
        try:
            from macro_rule_engine import get_rule_engine

            rule = get_rule_engine().validate_trade_against_rule(symbol, direction)
            if rule.get("approved"):
                note("macro_rule", "pass", rule.get("reason") or "approved")
            else:
                note("macro_rule", "fail", rule.get("reason") or "blocked")
        except Exception as exc:
            note("macro_rule", "warn", f"rule check unavailable: {exc}")

    # 5. Correlated-symbol exposure
    try:
        from config.smt_correlations import correlated_markets

        max_corr = max(1, int(_float_env("GOD_OF_TRADE_MAX_CORRELATED", 2)))
        corr_symbols = {
            canonical_symbol(item.get("symbol")) for item in correlated_markets(symbol)
        }
        same_dir = sum(
            1
            for pos in positions
            if canonical_symbol(pos.get("symbol")) in corr_symbols
            and str(pos.get("direction") or "").lower() == direction.lower()
        )
        if same_dir >= max_corr:
            note("correlation", "warn", f"{same_dir} correlated {direction} positions open")
        else:
            note("correlation", "pass", f"{same_dir} correlated positions")
    except Exception as exc:
        note("correlation", "warn", f"correlation check unavailable: {exc}")

    # 6. Loss streak on this symbol
    streak = loss_streak(symbol)
    streak_limit = max(1, int(_float_env("GOD_OF_TRADE_LOSS_STREAK", 3)))
    if streak >= streak_limit:
        note("loss_streak", "fail", f"{streak} consecutive losses on {symbol}")
    elif streak > 0:
        note("loss_streak", "warn", f"{streak} consecutive losses on {symbol}")
    else:
        note("loss_streak", "pass", "no active loss streak")

    # 7. Recent performance (MT5 history + in-process ledger)
    perf = recent_performance(symbol=symbol, strategy=strategy)
    win_rate = perf.get("win_rate")
    if win_rate is not None and perf.get("trades", 0) >= 5 and win_rate < 0.30:
        note("performance", "warn", f"win rate {win_rate:.0%} over {perf['trades']} trades")
    else:
        shown = "n/a" if win_rate is None else f"{win_rate:.0%}"
        note("performance", "pass", f"win rate {shown} over {perf.get('trades', 0)} trades")

    score = max(0, state["score"])
    fails = [c for c in checks if c["status"] == "fail"]
    warns = [c for c in checks if c["status"] == "warn"]
    veto_score = _float_env("GOD_OF_TRADE_VETO_SCORE", 45.0)
    if fails or score < veto_score:
        verdict = "VETO"
    elif warns:
        verdict = "CAUTION"
    else:
        verdict = "ALLOW"

    reasons = [f"{c['name']}: {c['detail']}" for c in checks if c["status"] != "pass"]
    advisory = (
        f"God of Trade {verdict} (score {score}) for {symbol} {direction} [{strategy}]: "
        + ("; ".join(reasons) if reasons else "all checks passed")
    )
    return {
        "enabled": True,
        "mode": mode(),
        "symbol": symbol,
        "direction": direction,
        "strategy": strategy,
        "verdict": verdict,
        "score": score,
        "checks": checks,
        "reasons": reasons,
        "advisory": advisory,
        "performance": perf,
    }


def should_block(verdict: Dict[str, Any]) -> bool:
    """True only in enforce mode when the God of Trade issued a VETO."""
    try:
        return mode() == "enforce" and str(verdict.get("verdict") or "").upper() == "VETO"
    except Exception:
        return False


def diagnostics() -> Dict[str, Any]:
    state = _load_state()
    return {
        "enabled": enabled(),
        "mode": mode(),
        "min_rr": _float_env("GOD_OF_TRADE_MIN_RR", 1.0),
        "veto_score": _float_env("GOD_OF_TRADE_VETO_SCORE", 45.0),
        "max_correlated": int(_float_env("GOD_OF_TRADE_MAX_CORRELATED", 2)),
        "loss_streak_limit": int(_float_env("GOD_OF_TRADE_LOSS_STREAK", 3)),
        "tracked_symbols": sorted((state.get("outcomes") or {}).keys())[:50],
        "loss_streaks": {k: v for k, v in (state.get("loss_streaks") or {}).items() if v},
    }

