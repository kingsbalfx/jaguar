"""
RUNTIME STRATEGY TOGGLES
========================
Turn any strategy ON / OFF **without restarting the bot**, from two places:

  * locally      -> ``data/strategy_toggles.json``
                    (or ``POST /admin/strategies`` on the bot's own API)
  * admin panel  -> Supabase table ``bot_strategy_settings``
                    (what the web dashboard writes)

Precedence (highest first):
  1. local file   - the machine you are standing in front of always wins
  2. Supabase     - the admin panel / remote control
  3. .env default - shipped default (``ICT_ENABLED``, ``FALLBACK5_ENABLED``, ...)

The remote side is cached for ``STRATEGY_TOGGLE_TTL_SECONDS`` (default 30s), so
flipping a switch in the admin panel takes effect within ~30 seconds without a
restart. Everything fails *open* (strategy stays enabled) if Supabase is
unreachable, so a network outage can never silently disable trading.

Usage
-----
    from strategy.toggles import is_enabled, snapshot, set_enabled

    if not is_enabled("fallback5"):
        ...  # skip that strategy entirely
"""

import json
import logging
import os
import threading
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Strategy catalogue (single source of truth for bot + admin panel)
# ---------------------------------------------------------------------------
STRATEGY_CATALOG: "OrderedDict[str, Dict[str, Any]]" = OrderedDict([
    ("ict", {
        "label": "Strategy 1 - ICT 12-gate state machine",
        "env": "ICT_ENABLED",
        "default": True,
    }),
    ("kingsbalfx", {
        "label": "Strategy 2 - Kingsbalfx fallback",
        "env": "KINGSBALFX_ENABLED",
        "default": True,
    }),
    ("fallback3", {
        "label": "Fallback 3 - sweep + CHoCH + MACD",
        "env": "FALLBACK3_ENABLED",
        "default": True,
    }),
    ("fallback4", {
        "label": "Fallback 4 - range + displacement",
        "env": "FALLBACK4_ENABLED",
        "default": True,
    }),
    ("fallback5", {
        "label": "Fallback 5 - session day-trend scalper",
        "env": "FALLBACK5_ENABLED",
        "default": True,
    }),
    ("mirror", {
        "label": "Mirror trading (broadcast + auto-open)",
        "env": "MIRROR_TRADING_ENABLED",
        "default": True,
    }),
])

STRATEGY_NAMES = tuple(STRATEGY_CATALOG)

_LOCAL_FILE_ENV = "STRATEGY_TOGGLE_STORE"
_REMOTE_TABLE_ENV = "STRATEGY_TOGGLE_TABLE"
_TTL_ENV = "STRATEGY_TOGGLE_TTL_SECONDS"
_REMOTE_ENV = "STRATEGY_TOGGLE_REMOTE"
_DEFAULT_LOCAL = "data/strategy_toggles.json"
_DEFAULT_TABLE = "bot_strategy_settings"
_DEFAULT_TTL = 30.0

_lock = threading.Lock()
_cache: Dict[str, Any] = {"at": 0.0, "local": {}, "remote": {}}
_last_logged: Dict[str, bool] = {}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _truthy(value: Any, default: bool = True) -> bool:
    if value is None or value == "":
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _env_default(name: str) -> bool:
    meta = STRATEGY_CATALOG.get(name)
    if not meta:
        return True
    return _truthy(os.getenv(meta["env"]), bool(meta["default"]))


def local_store_path() -> Path:
    raw = os.getenv(_LOCAL_FILE_ENV, _DEFAULT_LOCAL).strip() or _DEFAULT_LOCAL
    path = Path(raw)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent.parent / raw
    return path

def _read_local() -> Dict[str, bool]:
    """Local override file. Missing/corrupt file -> no overrides."""
    path = local_store_path()
    try:
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("[TOGGLES] local store unreadable (%s): %s", path, exc)
        return {}

    raw = data.get("strategies") if isinstance(data, dict) else None
    if not isinstance(raw, dict):
        return {}
    return {name: _truthy(value, True) for name, value in raw.items() if name in STRATEGY_CATALOG}


def _read_remote() -> Dict[str, bool]:
    """Admin-panel overrides from Supabase ``bot_strategy_settings``."""
    if not _truthy(os.getenv(_REMOTE_ENV, "true"), True):
        return {}
    try:
        from config.supabase_credentials import apply_supabase_env, resolve_supabase_credentials

        apply_supabase_env()
        resolved = resolve_supabase_credentials()
        url = resolved["url"]
        key = resolved["service_key"] or resolved["key"]
    except Exception as exc:  # pragma: no cover - optional coupling
        logger.debug("[TOGGLES] Supabase resolver unavailable: %s", exc)
        return {}

    if not url or not key:
        return {}

    try:
        from supabase import create_client

        client = create_client(url, key)
        table = os.getenv(_REMOTE_TABLE_ENV, _DEFAULT_TABLE)
        response = client.table(table).select("strategy,enabled").execute()
    except Exception as exc:
        # Missing table / RLS / offline: behave as "no remote override".
        logger.debug("[TOGGLES] remote toggles unavailable: %s", exc)
        return {}

    rows = getattr(response, "data", None)
    if not isinstance(rows, list):
        return {}

    overrides: Dict[str, bool] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("strategy") or "").strip().lower()
        if name in STRATEGY_CATALOG:
            overrides[name] = _truthy(row.get("enabled"), True)
    return overrides


def _refresh(force: bool = False) -> None:
    ttl = float(os.getenv(_TTL_ENV, str(_DEFAULT_TTL)) or _DEFAULT_TTL)
    now = time.time()
    with _lock:
        fresh = (now - float(_cache.get("at") or 0.0)) < max(0.0, ttl)
        if not force and fresh:
            return

    local = _read_local()
    remote = _read_remote()
    with _lock:
        _cache.update({"at": time.time(), "local": local, "remote": remote})

# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------
def is_enabled(name: str, *, force_refresh: bool = False) -> bool:
    """Effective ON/OFF state for ``name`` (never raises)."""
    key = str(name or "").strip().lower()
    if key not in STRATEGY_CATALOG:
        return True  # unknown strategy -> never block trading

    _refresh(force=force_refresh)
    with _lock:
        local = dict(_cache.get("local") or {})
        remote = dict(_cache.get("remote") or {})

    if key in local:
        value, source = bool(local[key]), "local"
    elif key in remote:
        value, source = bool(remote[key]), "admin_panel"
    else:
        value, source = _env_default(key), "env"

    if _last_logged.get(key) != value:
        _last_logged[key] = value
        logger.info(
            "[TOGGLES] strategy=%s -> %s (source=%s)",
            key, "ENABLED" if value else "DISABLED", source,
        )
    return value


def snapshot(*, force_refresh: bool = True) -> Dict[str, Any]:
    """Full picture for the bot API / admin panel."""
    if force_refresh:
        _refresh(force=True)
    with _lock:
        local = dict(_cache.get("local") or {})
        remote = dict(_cache.get("remote") or {})

    out: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    for name, meta in STRATEGY_CATALOG.items():
        if name in local:
            effective, source = bool(local[name]), "local"
        elif name in remote:
            effective, source = bool(remote[name]), "admin_panel"
        else:
            effective, source = _env_default(name), "env"
        out[name] = {
            "label": meta["label"],
            "env_key": meta["env"],
            "enabled": effective,
            "source": source,
            "env_default": _env_default(name),
            "local_override": local.get(name),
            "admin_panel": remote.get(name),
        }
    return out


def set_enabled(
    name: str,
    enabled: bool,
    *,
    persist_local: bool = True,
    persist_remote: bool = True,
    updated_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Turn a strategy ON/OFF and persist where requested."""
    key = str(name or "").strip().lower()
    if key not in STRATEGY_CATALOG:
        raise ValueError(f"unknown strategy '{name}'; expected one of {', '.join(STRATEGY_NAMES)}")

    value = bool(enabled)
    result: Dict[str, Any] = {
        "strategy": key, "enabled": value,
        "saved_locally": False, "saved_to_server": False,
    }

    if persist_local:
        path = local_store_path()
        current = _read_local()
        current[key] = value
        payload = {
            "strategies": current,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "updated_by": updated_by or "local",
        }
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2)
            os.replace(tmp, path)
            result["saved_locally"] = True
        except OSError as exc:
            result["local_error"] = str(exc)

    if persist_remote:
        result["saved_to_server"] = _write_remote(key, value, updated_by)

    _refresh(force=True)
    return result


def _write_remote(name: str, enabled: bool, updated_by: Optional[str]) -> bool:
    if not _truthy(os.getenv(_REMOTE_ENV, "true"), True):
        return False
    try:
        from config.supabase_credentials import apply_supabase_env, resolve_supabase_credentials

        apply_supabase_env()
        resolved = resolve_supabase_credentials()
        url = resolved["url"]
        key = resolved["service_key"] or resolved["key"]
    except Exception:
        return False
    if not url or not key:
        return False

    try:
        from supabase import create_client

        client = create_client(url, key)
        table = os.getenv(_REMOTE_TABLE_ENV, _DEFAULT_TABLE)
        client.table(table).upsert(
            {
                "strategy": name,
                "enabled": bool(enabled),
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "updated_by": updated_by or "bot_api",
            },
            on_conflict="strategy",
        ).execute()
        return True
    except Exception as exc:
        logger.warning("[TOGGLES] could not persist %s to server: %s", name, exc)
        return False


def clear_local_override(name: Optional[str] = None) -> bool:
    """Remove a local override so the admin panel / .env takes over again."""
    path = local_store_path()
    current = _read_local()
    if name is None:
        current = {}
    else:
        current.pop(str(name).strip().lower(), None)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"strategies": current}, fh, indent=2)
        _refresh(force=True)
        return True
    except OSError:
        return False


