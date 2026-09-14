"""
MT5 symbol universe registry
============================

The bot must only ever evaluate symbols that the connected MT5 terminal
actually exposes. This module is the single registry for that universe.

Usage
-----
* ``main.py`` calls :func:`sync_universe` at startup (after MT5 connect) and
  periodically re-syncs so broker symbol changes are picked up automatically
  ("always synchronize").
* ``sync_universe`` persists the list to ``data/mt5_symbol_universe.json`` so
  child processes, the Flask API and the mirror worker can consult the same
  universe without their own MT5 round-trip.
* Strategies (Fallback 5, mirror receive path, ...) call
  :func:`is_available` / :func:`resolve_tradable` instead of maintaining their
  own hard-coded allowlists.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
STORE_FILE = BASE_DIR / "data" / "mt5_symbol_universe.json"

_lock = threading.RLock()
_loaded = False
_symbols: List[str] = []
_index: Set[str] = set()
_meta: Dict[str, Any] = {"source": "unknown", "updated_at": None, "account": None, "count": 0}


def _truthy(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def allow_when_empty() -> bool:
    """When the registry is still empty, do not block trading by default."""
    return _truthy("MT5_UNIVERSE_ALLOW_WHEN_EMPTY", True)


# ---------------------------------------------------------------------------
# Alias helpers
# ---------------------------------------------------------------------------
_SUFFIX_RE = re.compile(r"[._\-#][A-Z0-9]{1,6}$", re.IGNORECASE)


def base_symbol(symbol: str) -> str:
    """Strip broker suffixes/separators (``XAUUSD.a`` -> ``XAUUSD``)."""
    raw = str(symbol or "").strip().upper()
    for _ in range(3):
        stripped = _SUFFIX_RE.sub("", raw)
        if stripped == raw:
            break
        raw = stripped
    return re.sub(r"[^A-Z0-9]", "", raw)


def root_variants(symbol: str) -> Set[str]:
    """Return progressively trimmed roots (``EURUSDm`` -> ``EURUSD``)."""
    compact = re.sub(r"[^A-Z0-9]", "", str(symbol or "").strip().upper())
    out: Set[str] = set()
    if not compact:
        return out
    out.add(compact)
    if len(compact) > 6:
        # XAUUSD.a / EURUSDm / BTCUSDT style suffixes without a separator.
        out.add(compact[:-1])
        if len(compact) > 7:
            out.add(compact[:-2])
        if len(compact) >= 8:
            out.add(compact[:6])
    return out


def aliases_for(symbol: str) -> Set[str]:
    """Return every name variant that should match this symbol."""
    raw = str(symbol or "").strip().upper()
    out: Set[str] = set()
    if not raw:
        return out

    compact = raw.replace("/", "").replace("-", "").replace("_", "")
    out.update({raw, compact, base_symbol(raw), raw.replace("#", "")})
    out.update(root_variants(raw))

    try:
        from utils.symbol_profile import canonical_symbol

        canon = canonical_symbol(raw)
        out.add(canon)
        out.add(base_symbol(canon))
        out.update(root_variants(canon))
    except Exception:  # pragma: no cover - defensive
        pass

    try:
        from config.symbol_mappings import candidates_for

        for candidate in candidates_for(base_symbol(raw)) or []:
            text = str(candidate or "").strip().upper()
            if text:
                out.add(text)
                out.add(base_symbol(text))
                out.update(root_variants(text))
    except Exception:  # pragma: no cover - defensive
        pass

    return {item for item in out if item}



# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
def _persist() -> None:
    try:
        STORE_FILE.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "symbols": list(_symbols),
            "source": _meta.get("source"),
            "updated_at": _meta.get("updated_at"),
            "account": _meta.get("account"),
        }
        STORE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.debug("mt5_universe: could not persist universe: %s", exc)


def _load_persisted() -> None:
    global _loaded, _symbols, _index, _meta
    if _loaded:
        return
    _loaded = True
    try:
        if not STORE_FILE.exists():
            return
        data = json.loads(STORE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("mt5_universe: could not load persisted universe: %s", exc)
        return

    symbols = [str(item).strip() for item in (data.get("symbols") or []) if str(item).strip()]
    if not symbols:
        return
    _symbols = symbols
    _index = set()
    for symbol in symbols:
        _index.update(aliases_for(symbol))
    _meta = {
        "source": data.get("source") or "persisted",
        "updated_at": data.get("updated_at"),
        "account": data.get("account"),
        "count": len(symbols),
    }
    logger.info(
        "MT5 UNIVERSE | restored %s symbols from %s (source=%s, updated_at=%s)",
        len(_symbols),
        STORE_FILE.name,
        _meta.get("source"),
        _meta.get("updated_at"),
    )



# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def sync_universe(
    symbols: Iterable[str],
    source: str = "mt5",
    account_id: Optional[str] = None,
    persist: bool = True,
    reason: str = "startup",
) -> Dict[str, Any]:
    """Replace the registry with ``symbols`` (the live MT5 broker universe)."""
    global _symbols, _index, _meta, _loaded
    cleaned: List[str] = []
    seen: Set[str] = set()
    for item in symbols or []:
        name = str(item or "").strip()
        if not name:
            continue
        key = name.upper()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(name)

    with _lock:
        if not cleaned and _symbols:
            # Never wipe a good universe because of a transient MT5 hiccup.
            logger.warning("MT5 UNIVERSE | sync produced 0 symbols; keeping previous %s", len(_symbols))
            return universe_snapshot()

        index: Set[str] = set()
        for name in cleaned:
            index.update(aliases_for(name))

        _symbols = cleaned
        _index = index
        _loaded = True
        _meta = {
            "source": source,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "account": str(account_id) if account_id else None,
            "count": len(cleaned),
            "reason": reason,
        }
        if persist:
            _persist()

    logger.info(
        "MT5 UNIVERSE | synchronized | source=%s | account=%s | symbols=%s | reason=%s",
        source,
        account_id or "n/a",
        len(cleaned),
        reason,
    )
    return universe_snapshot()


def register_symbol(symbol: str) -> bool:
    """Add a single resolvable symbol (used when main.py resolves one on demand)."""
    name = str(symbol or "").strip()
    if not name:
        return False
    with _lock:
        if name.upper() in {item.upper() for item in _symbols}:
            return False
        _symbols.append(name)
        _index.update(aliases_for(name))
        _meta["count"] = len(_symbols)
        _meta["updated_at"] = datetime.now(timezone.utc).isoformat()
        if _meta.get("source") in (None, "unknown"):
            _meta["source"] = "runtime"
        _persist()
    return True


def get_universe() -> List[str]:
    """Return a copy of the live MT5 symbol universe."""
    _load_persisted()
    with _lock:
        return list(_symbols)


def universe_size() -> int:
    _load_persisted()
    with _lock:
        return len(_symbols)


def universe_snapshot() -> Dict[str, Any]:
    _load_persisted()
    with _lock:
        return {
            "count": len(_symbols),
            "source": _meta.get("source"),
            "updated_at": _meta.get("updated_at"),
            "account": _meta.get("account"),
            "reason": _meta.get("reason"),
            "store": str(STORE_FILE),
            "allow_when_empty": allow_when_empty(),
        }



def is_available(symbol: str) -> bool:
    """True when ``symbol`` exists in the MT5 universe (alias aware).

    When the universe has not been synchronized yet, ``MT5_UNIVERSE_ALLOW_WHEN_EMPTY``
    (default true) decides, so a cold start never blocks every symbol.
    """
    raw = str(symbol or "").strip()
    if not raw:
        return False

    _load_persisted()
    with _lock:
        if not _index:
            return allow_when_empty()
        candidates = aliases_for(raw)
        if not candidates:
            return allow_when_empty()
        return any(candidate in _index for candidate in candidates)


def resolve_tradable(symbol: str) -> str:
    """Return the exact broker symbol from the universe, or empty string."""
    raw = str(symbol or "").strip()
    if not raw:
        return ""

    _load_persisted()
    with _lock:
        if not _symbols:
            return raw if allow_when_empty() else ""

        for broker_symbol in _symbols:
            if broker_symbol.upper() == raw.upper():
                return broker_symbol

        wanted = aliases_for(raw)
        for broker_symbol in _symbols:
            if wanted & aliases_for(broker_symbol):
                return broker_symbol
        return ""


def refresh_from_mt5(strict: bool = True) -> Dict[str, Any]:
    """Pull the universe straight from MT5 (used for periodic re-sync)."""
    try:
        from execution.mt5_connector import get_broker_symbols
    except Exception as exc:  # pragma: no cover - Windows only dependency
        logger.debug("mt5_universe: mt5 connector unavailable: %s", exc)
        return universe_snapshot()

    try:
        symbols = get_broker_symbols(
            include_hidden=_truthy("MT5_SYMBOL_INCLUDE_HIDDEN", False),
            require_trade=_truthy("MT5_SYMBOL_REQUIRE_TRADE", True),
            require_tick=_truthy("MT5_SYMBOL_REQUIRE_TICK", False),
            group_masks=[item.strip() for item in os.getenv("MT5_SYMBOL_GROUPS", "").split(",") if item.strip()],
        )
    except Exception as exc:
        if strict:
            logger.warning("mt5_universe: MT5 re-sync failed: %s", exc)
        return universe_snapshot()

    return sync_universe(
        symbols,
        source="mt5",
        account_id=os.getenv("MT5_ACCOUNT_LOGIN") or None,
        reason="refresh",
    )
