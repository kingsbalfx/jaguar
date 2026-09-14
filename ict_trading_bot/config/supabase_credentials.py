"""
Canonical Supabase credential resolver
======================================

Single source of truth for every module that needs Supabase
(``dashboard/bridge.py``, ``macro_rule_engine.py``, ``risk/mirror_trading.py``,
``utils/mt5_credentials.py``, the admin API, ...).

Resolution order (first VALID value wins):

1. Environment variables (``SUPABASE_URL`` / ``SUPABASE_KEY`` /
   ``SUPABASE_SERVICE_KEY``).
2. The project ``.env`` file, parsed directly. This protects the bot from a
   duplicated/placeholder key at the bottom of ``.env`` (python-dotenv keeps the
   *last* occurrence, which previously produced ``SUPABASE_URL=...`` and
   ``Invalid URL``). Here the last *valid* value is used instead.
3. Local credential stores written by the admin API / ``configure_credentials.py``:
   - ``~/.ict_trading_bot/credentials.json``
   - ``<project>/data/local_credentials.json`` (so child processes, the mirror
     worker and other local programs can reuse credentials that were inserted
     once by an admin).

Placeholders such as ``...``, ``your-project.supabase.co``, ``changeme`` or
``<key>`` are rejected instead of being passed to ``create_client``.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"
HOME_STORE = Path(os.path.expanduser("~/.ict_trading_bot")) / "credentials.json"
PROJECT_STORE = BASE_DIR / "data" / "local_credentials.json"

_URL_ENV_NAMES = ("SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL")
_KEY_ENV_NAMES = ("SUPABASE_SERVICE_KEY", "SUPABASE_KEY", "SUPABASE_ANON_KEY")

_PLACEHOLDER_TOKENS = (
    "...",
    "<",
    ">",
    "your-",
    "your_",
    "yourproject",
    "your-project",
    "your_project",
    "changeme",
    "change_me",
    "replace",
    "placeholder",
    "example",
    "todo",
    "xxxx",
    "insert_",
    "paste_",
    "not_set",
    "none",
    "null",
)

_resolve_lock = threading.RLock()
_cached: Optional[Dict[str, Any]] = None
_logged_once = False


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------
def clean(value: Any) -> str:
    """Strip whitespace and surrounding quotes from an env/file value."""
    text = str(value or "").strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
        text = text[1:-1].strip()
    return text


def looks_like_placeholder(value: Any) -> bool:
    text = clean(value).lower()
    if not text:
        return True
    if text in ("...", "..", ".", "-", "n/a"):
        return True
    return any(token in text for token in _PLACEHOLDER_TOKENS)


def is_valid_supabase_url(value: Any) -> bool:
    url = clean(value)
    if not url or looks_like_placeholder(url):
        return False
    if not url.lower().startswith("https://"):
        return False
    host = url.split("://", 1)[1].split("/", 1)[0].strip()
    if not host or "." not in host or " " in host:
        return False
    return True


def is_valid_supabase_key(value: Any) -> bool:
    key = clean(value)
    if not key or looks_like_placeholder(key):
        return False
    return len(key) >= 20 and " " not in key


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------
def _parse_env_file(path: Path = ENV_FILE) -> Dict[str, str]:
    """Parse a .env file, keeping the last *valid* value per key.

    python-dotenv semantics (last occurrence wins) are preserved for
    non-placeholder values; placeholder entries are ignored so a duplicated
    ``SUPABASE_URL=...`` line can never poison the real credential.
    """
    values: Dict[str, str] = {}
    try:
        if not path.exists():
            return values
        for raw_line in path.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, raw_value = line.partition("=")
            name = name.strip()
            if name.startswith("export "):
                name = name[len("export "):].strip()
            if not name:
                continue
            value = clean(raw_value.split(" #", 1)[0])
            if not value or looks_like_placeholder(value):
                continue
            values[name.upper()] = value
    except OSError as exc:  # pragma: no cover - unreadable file
        logger.debug("supabase_credentials: could not read %s: %s", path, exc)
    return values


def _read_json_store(path: Path) -> Dict[str, Any]:
    try:
        if not path.exists():
            return {}
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("supabase_credentials: could not read %s: %s", path, exc)
        return {}


def _store_credentials() -> Dict[str, str]:
    """Merge the home store and the project store (project store wins)."""
    merged: Dict[str, str] = {}
    for store in (HOME_STORE, PROJECT_STORE):
        data = _read_json_store(store)
        url = clean(data.get("supabase_url"))
        key = clean(data.get("supabase_key"))
        service_key = clean(data.get("supabase_service_key"))
        if url:
            merged["url"] = url
        if key:
            merged["key"] = key
        if service_key:
            merged["service_key"] = service_key
    return merged


# ---------------------------------------------------------------------------
# Resolve / apply
# ---------------------------------------------------------------------------
def resolve_supabase_credentials(force: bool = False) -> Dict[str, Any]:
    """Resolve the effective Supabase credentials.

    Returns a dict::

        {
          "url": str, "key": str, "service_key": str,
          "source": {"url": str, "key": str, "service_key": str},
          "usable": bool,
          "ignored": [str, ...]   # placeholder values that were skipped
        }
    """
    global _cached
    with _resolve_lock:
        if _cached is not None and not force:
            return _cached

        process_env = {k.upper(): clean(v) for k, v in os.environ.items()}
        file_env = _parse_env_file()
        store = _store_credentials()

        ignored: List[str] = []
        for name in _URL_ENV_NAMES + _KEY_ENV_NAMES:
            raw = process_env.get(name)
            if raw and looks_like_placeholder(raw):
                ignored.append(name)

        url, url_source = _pick(
            _URL_ENV_NAMES,
            ("env", process_env),
            ("dotenv", file_env),
            ("store", store),
            validator=is_valid_supabase_url,
        )
        service_key, service_source = _pick(
            ("SUPABASE_SERVICE_KEY",),
            ("env", process_env),
            ("dotenv", file_env),
            ("store", store),
            validator=is_valid_supabase_key,
        )
        key, key_source = _pick(
            ("SUPABASE_KEY", "SUPABASE_ANON_KEY"),
            ("env", process_env),
            ("dotenv", file_env),
            ("store", store),
            validator=is_valid_supabase_key,
        )

        effective_key = service_key or key
        resolved = {
            "url": url,
            "key": key or service_key,
            "service_key": service_key or key,
            "source": {
                "url": url_source,
                "key": service_source or key_source,
                "service_key": service_source or key_source,
            },
            "usable": bool(url and effective_key),
            "ignored": sorted(set(ignored)),
        }
        _cached = resolved
        return resolved


def apply_supabase_env(force: bool = False, quiet: bool = False) -> bool:
    """Write the resolved credentials into ``os.environ`` for every module.

    This is what makes the bot work even when ``.env`` holds a placeholder:
    every consumer (bridge, macro engine, mirror, MT5 credential loader, admin
    API) then sees one consistent, valid credential set.
    """
    global _logged_once
    resolved = resolve_supabase_credentials(force=force)
    if not resolved["usable"]:
        purge_placeholder_env()
        if not quiet and not _logged_once:
            _logged_once = True
            logger.warning(
                "Supabase credentials unavailable (no valid SUPABASE_URL/SUPABASE_KEY). "
                "Running in local-only mode. Insert credentials via the admin API "
                "('/admin/credentials') or run 'python configure_credentials.py'."
            )
        return False

    os.environ["SUPABASE_URL"] = resolved["url"]
    os.environ["SUPABASE_KEY"] = resolved["key"]
    os.environ["SUPABASE_SERVICE_KEY"] = resolved["service_key"]
    if not quiet and not _logged_once:
        _logged_once = True
        logger.info(
            "Supabase credentials ready | url_source=%s | key_source=%s",
            resolved["source"]["url"] or "unknown",
            resolved["source"]["key"] or "unknown",
        )
    return True


def bootstrap(force: bool = False, quiet: bool = False) -> Dict[str, Any]:
    """Resolve + publish credentials. Safe to call from any entry point."""
    apply_supabase_env(force=force, quiet=quiet)
    return resolve_supabase_credentials(force=force)


# ---------------------------------------------------------------------------
# Persist locally (admin insert / configure_credentials.py)
# ---------------------------------------------------------------------------
def _write_json(path: Path, payload: Dict[str, Any]) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return True
    except OSError as exc:
        logger.error("supabase_credentials: could not write %s: %s", path, exc)
        return False


def save_supabase_credentials(
    url: str,
    key: str,
    service_key: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
    write_project_store: bool = True,
) -> Dict[str, Any]:
    """Validate and persist Supabase credentials locally.

    Raises ``ValueError`` when the URL/key are invalid so callers (admin API)
    can return a clear error instead of creating a broken client.
    """
    global _cached
    url = clean(url)
    key = clean(key)
    service_key = clean(service_key) or key

    if not is_valid_supabase_url(url):
        raise ValueError("Invalid Supabase URL: must start with https:// and not be a placeholder")
    if not is_valid_supabase_key(key):
        raise ValueError("Invalid Supabase key: value is empty, too short, or a placeholder")

    stored = False
    for store in (HOME_STORE, PROJECT_STORE if write_project_store else None):
        if store is None:
            continue
        payload = _read_json_store(store)
        payload["supabase_url"] = url
        payload["supabase_key"] = key
        payload["supabase_service_key"] = service_key
        if extra:
            for name, value in extra.items():
                if value not in (None, ""):
                    payload[name] = value
        stored = _write_json(store, payload) or stored

    os.environ["SUPABASE_URL"] = url
    os.environ["SUPABASE_KEY"] = key
    os.environ["SUPABASE_SERVICE_KEY"] = service_key
    _cached = None
    resolve_supabase_credentials(force=True)
    return {
        "saved": stored,
        "home_store": str(HOME_STORE),
        "project_store": str(PROJECT_STORE) if write_project_store else None,
    }


# ---------------------------------------------------------------------------
# Diagnostics / admin helpers
# ---------------------------------------------------------------------------
def purge_placeholder_env() -> List[str]:
    """Remove placeholder Supabase values from ``os.environ``.

    Keeps modules that read the raw env (before applying the resolver) from
    handing ``"..."`` to ``create_client`` and crashing with ``Invalid URL``.
    """
    removed: List[str] = []
    for name in _URL_ENV_NAMES + _KEY_ENV_NAMES:
        raw = clean(os.environ.get(name))
        if raw and looks_like_placeholder(raw):
            os.environ.pop(name, None)
            removed.append(name)
    return removed


def masked(value: str, keep: int = 6) -> str:
    text = clean(value)
    if not text:
        return ""
    if len(text) <= keep * 2:
        return text[:keep] + "..." if len(text) > keep else text
    return f"{text[:keep]}...{text[-4:]}"


def credential_status() -> Dict[str, Any]:
    """Masked, JSON-safe credential status for the admin API."""
    resolved = resolve_supabase_credentials()
    return {
        "usable": resolved["usable"],
        "url": resolved["url"] or None,
        "url_source": resolved["source"]["url"] or None,
        "key_masked": masked(resolved["key"]),
        "key_source": resolved["source"]["key"] or None,
        "service_key_masked": masked(resolved["service_key"]),
        "ignored_placeholders": resolved["ignored"],
        "env_file": str(ENV_FILE),
        "home_store": str(HOME_STORE),
        "project_store": str(PROJECT_STORE),
    }


def test_supabase_connection(
    url: Optional[str] = None,
    key: Optional[str] = None,
    timeout: float = 10.0,
) -> Dict[str, Any]:
    """Ping Supabase REST with the given (or resolved) credentials."""
    resolved = resolve_supabase_credentials()
    url = clean(url) or resolved["url"]
    key = clean(key) or resolved["service_key"] or resolved["key"]

    if not is_valid_supabase_url(url):
        return {"ok": False, "error": "invalid_or_missing_url"}
    if not is_valid_supabase_key(key):
        return {"ok": False, "error": "invalid_or_missing_key"}

    try:
        import requests
    except ImportError:  # pragma: no cover - requests is a hard dependency
        return {"ok": False, "error": "requests_not_installed"}

    endpoint = f"{url.rstrip('/')}/rest/v1/"
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    try:
        response = requests.get(endpoint, headers=headers, timeout=timeout)
    except Exception as exc:
        return {"ok": False, "error": f"connection_failed:{exc}"}

    status = int(getattr(response, "status_code", 0) or 0)
    if status in (401, 403):
        return {"ok": False, "status": status, "error": "unauthorized_key"}
    return {
        "ok": 200 <= status < 500,
        "status": status,
        "error": None,
        "url": url,
    }


def _pick(names: Tuple[str, ...], *sources: Dict[str, str], validator=None) -> Tuple[str, str]:
    """Return (value, source_name) for the first valid candidate found."""
    for source_name, source in sources:
        for name in names:
            value = clean(source.get(name) or source.get(name.lower()))
            if validator is not None and not validator(value):
                continue
            if value:
                return value, f"{source_name}:{name}"
    return "", ""
