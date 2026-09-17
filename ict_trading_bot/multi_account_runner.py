import json
import logging
import os
import subprocess
import sys
import time
from collections import OrderedDict
from pathlib import Path

from utils.mt5_credentials import fetch_all_mt5_credentials

logger = logging.getLogger(__name__)
_WARNED: set = set()


def _warn_once(key: str, message: str) -> None:
    """Print an account-loading warning only once per process/key."""
    marker = f"{key}:{message}"
    if marker in _WARNED:
        return
    _WARNED.add(marker)
    print(message)


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = Path(os.getenv("MULTI_ACCOUNT_CONFIG", BASE_DIR / "accounts.example.json"))
LOCAL_STORE_PATH = Path(
    os.getenv("MULTI_ACCOUNT_LOCAL_STORE", BASE_DIR / "data" / "accounts_local.json")
)
ACTIVE_REGISTRY_PATH = Path(
    os.getenv("MULTI_ACCOUNT_ACTIVE_REGISTRY", BASE_DIR / "data" / "active_accounts.json")
)
DISABLED_STORE_PATH = Path(
    os.getenv("MULTI_ACCOUNT_DISABLED_STORE", BASE_DIR / "data" / "disabled_accounts.json")
)


def _env_truthy(name, default="false"):
    return os.getenv(name, default).lower() in ("1", "true", "yes", "on")


def _split_csv(value):
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _indexed_env_accounts():
    accounts = []
    found_any = False
    base_api_port = int(os.getenv("MULTI_ACCOUNT_BASE_API_PORT", "8000"))
    # Hard cap so a machine with NO ACCOUNT_n_* variables ends the scan instead of
    # looping forever (the previous `while True` never terminated in that case).
    max_index = max(1, int(os.getenv("MULTI_ACCOUNT_MAX_INDEXED_ACCOUNTS", "64")))
    for index in range(1, max_index + 1):
        prefix = f"ACCOUNT_{index}_"
        enabled = _env_truthy(f"{prefix}ENABLED", "false")
        login = os.getenv(f"{prefix}LOGIN", "").strip()

        if not enabled and not login:
            if found_any:
                break
            continue

        found_any = True
        if not enabled:
            continue
        if not login:
            raise RuntimeError(f"{prefix}ENABLED=true but {prefix}LOGIN is missing")

        account = {
            "enabled": True,
            "login": login,
            "bot_id": os.getenv(f"{prefix}BOT_ID", f"mt5_bot_{login}"),
        }

        api_port = os.getenv(f"{prefix}API_PORT", "").strip()
        if api_port:
            account["api_port"] = int(api_port)
        else:
            account["api_port"] = base_api_port + (index - 1)

        mt5_path = os.getenv(f"{prefix}MT5_PATH", "").strip()
        if mt5_path:
            account["mt5_path"] = mt5_path

        password = os.getenv(f"{prefix}PASSWORD", "").strip()
        if password:
            account["password"] = password

        server = os.getenv(f"{prefix}SERVER", "").strip()
        if server:
            account["server"] = server

        user_id = os.getenv(f"{prefix}USER_ID", "").strip()
        if user_id:
            account["user_id"] = user_id

        email = os.getenv(f"{prefix}EMAIL", "").strip()
        if email:
            account["email"] = email

        symbols = _split_csv(os.getenv(f"{prefix}SYMBOLS", ""))
        if symbols:
            account["symbols"] = symbols

        backtest_report_path = os.getenv(f"{prefix}BACKTEST_REPORT_PATH", "").strip()
        if backtest_report_path:
            account["backtest_report_path"] = backtest_report_path
        else:
            account["backtest_report_path"] = f"backtest/latest_approval_{login}.json"

        extra_env_raw = os.getenv(f"{prefix}EXTRA_ENV_JSON", "").strip()
        if extra_env_raw:
            try:
                account["extra_env"] = json.loads(extra_env_raw)
            except Exception:
                pass

        if account["enabled"]:
            accounts.append(account)

    return accounts


def _json_env_accounts():
    raw = os.getenv("MULTI_ACCOUNT_ACCOUNTS_JSON", "").strip()
    if not raw:
        return []
    payload = json.loads(raw)
    accounts = payload.get("accounts") if isinstance(payload, dict) else payload
    return [account for account in (accounts or []) if account.get("enabled", True)]


def web_accounts_enabled() -> bool:
    """True when accounts submitted through the web (Supabase) are accepted."""
    return _env_truthy("MULTI_ACCOUNT_LOAD_SERVER", "true") or _env_truthy(
        "MULTI_ACCOUNT_ACCEPT_WEB", "true"
    )


def _server_accounts():
    if not web_accounts_enabled():
        return []
    try:
        credentials = fetch_all_mt5_credentials()
    except Exception as exc:
        _warn_once("web_accounts", f"[MULTI] Web/server account load skipped: {exc}")
        return []

    accounts = []
    for row in credentials:
        login = str(row.get("login") or "").strip()
        if not login:
            continue
        accounts.append(
            {
                "enabled": True,
                "login": login,
                "bot_id": f"mt5_bot_{login}",
                "password": row.get("password"),
                "server": row.get("server"),
                "user_id": row.get("user_id"),
                "email": row.get("email"),
                "source": "web",
            }
        )
    return accounts


def _config_file_accounts():
    if not _env_truthy("MULTI_ACCOUNT_LOAD_CONFIG", "true"):
        return []
    try:
        if not CONFIG_PATH.exists():
            return []
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except Exception as exc:
        print(f"[MULTI] Config accounts skipped ({CONFIG_PATH}): {exc}")
        return []
    rows = payload.get("accounts") if isinstance(payload, dict) else payload
    accounts = []
    for account in rows or []:
        if not isinstance(account, dict):
            continue
        if not account.get("enabled", True):
            continue
        accounts.append({**account, "source": account.get("source") or "config"})
    return accounts


def _local_store_accounts():
    """Accounts saved locally by the admin API / a previous web submission."""
    if not _env_truthy("MULTI_ACCOUNT_LOAD_LOCAL_STORE", "true"):
        return []
    try:
        if not LOCAL_STORE_PATH.exists():
            return []
        payload = json.loads(LOCAL_STORE_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[MULTI] Local account store skipped ({LOCAL_STORE_PATH}): {exc}")
        return []

    rows = payload.get("accounts") if isinstance(payload, dict) else payload
    accounts = []
    for account in rows or []:
        if not isinstance(account, dict):
            continue
        if not account.get("enabled", True):
            continue
        login = str(account.get("login") or "").strip()
        if not login:
            continue
        accounts.append({**account, "enabled": True, "source": account.get("source") or "local_store"})
    return accounts


def _read_disabled_store() -> dict:
    try:
        if not DISABLED_STORE_PATH.exists():
            return {"accounts": {}}
        payload = json.loads(DISABLED_STORE_PATH.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("accounts"), dict):
            return payload
        return {"accounts": {}}
    except Exception:
        return {"accounts": {}}


def disabled_accounts() -> dict:
    """logins -> {reason, disabled_at} that must not be spawned until re-enabled."""
    return dict(_read_disabled_store().get("accounts") or {})


def disable_account(login: str, reason: str = "") -> bool:
    """Stop spawning an account until it is re-submitted or explicitly enabled.

    Works for every source (env / config file / local store / web) unlike the
    local-store flag, which only exists for locally saved accounts.
    """
    login = str(login or "").strip()
    if not login:
        return False
    payload = _read_disabled_store()
    payload.setdefault("accounts", {})[login] = {
        "reason": str(reason or ""),
        "disabled_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    try:
        DISABLED_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        DISABLED_STORE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.debug("MULTI ACCOUNT | could not write disabled store: %s", exc)
        return False
    return True


def enable_account(login: str) -> bool:
    """Clear the disabled flag (called when an account is re-submitted)."""
    login = str(login or "").strip()
    if not login:
        return False
    payload = _read_disabled_store()
    accounts = payload.setdefault("accounts", {})
    if login not in accounts:
        return False
    accounts.pop(login, None)
    try:
        DISABLED_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        DISABLED_STORE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        return False
    return True


def _read_local_store():
    try:
        if not LOCAL_STORE_PATH.exists():
            return {"accounts": []}
        payload = json.loads(LOCAL_STORE_PATH.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            payload.setdefault("accounts", [])
            return payload
        return {"accounts": payload if isinstance(payload, list) else []}
    except Exception:
        return {"accounts": []}


def save_local_account(account: dict, enabled: bool = True) -> dict:
    """Insert/update an account in the local store (used by the admin API)."""
    login = str((account or {}).get("login") or "").strip()
    if not login:
        raise ValueError("login is required")

    payload = _read_local_store()
    rows = [row for row in payload.get("accounts", []) if isinstance(row, dict)]
    record = {k: v for k, v in (account or {}).items() if v not in (None, "")}
    record["login"] = login
    record["enabled"] = bool(enabled)
    record["source"] = record.get("source") or "local_store"
    record["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    replaced = False
    for index, row in enumerate(rows):
        if str(row.get("login") or "").strip() == login:
            rows[index] = {**row, **record}
            replaced = True
            break
    if not replaced:
        rows.append(record)

    LOCAL_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload["accounts"] = rows
    LOCAL_STORE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    enable_account(login)
    return record


def set_local_account_enabled(login: str, enabled: bool) -> bool:
    login = str(login or "").strip()
    if not login:
        return False
    payload = _read_local_store()
    changed = False
    for row in payload.get("accounts", []):
        if str(row.get("login") or "").strip() == login:
            row["enabled"] = bool(enabled)
            changed = True
    if changed:
        LOCAL_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOCAL_STORE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return changed


def delete_local_account(login: str) -> bool:
    login = str(login or "").strip()
    if not login:
        return False
    payload = _read_local_store()
    original = payload.get("accounts", [])
    rows = [row for row in original if str(row.get("login") or "").strip() != login]
    if len(rows) == len(original):
        return False
    payload["accounts"] = rows
    LOCAL_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_STORE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return True


def save_server_account(account: dict) -> bool:
    """Upsert a web-submitted account into Supabase ``mt5_credentials`` (best effort)."""
    login = str((account or {}).get("login") or "").strip()
    if not login:
        raise ValueError("login is required")
    try:
        from config.supabase_credentials import apply_supabase_env, resolve_supabase_credentials

        apply_supabase_env(quiet=True)
        resolved = resolve_supabase_credentials()
        if not resolved["usable"]:
            return False
        from supabase import create_client

        client = create_client(resolved["url"], resolved["service_key"] or resolved["key"])
    except Exception as exc:
        print(f"[MULTI] Supabase account upsert skipped: {exc}")
        return False

    table = os.getenv("MT5_CREDENTIALS_TABLE", "mt5_credentials")
    record = {
        "login": login,
        "password": account.get("password"),
        "server": account.get("server"),
        "active": True,
    }
    if account.get("user_id"):
        record["user_id"] = account["user_id"]
    if account.get("email"):
        record["email"] = account["email"]
    record = {key: value for key, value in record.items() if value not in (None, "")}

    try:
        # Same resilient writer as the local -> Supabase sync: works whether or
        # not the table has a unique(login) constraint.
        _write_server_row(client, table, login, record)
        enable_account(login)
        return True
    except Exception as exc:
        print(f"[MULTI] Supabase account upsert failed for {login}: {exc}")
        return False


def describe_accounts(accounts) -> list:
    """Password-masked view of accepted accounts (admin API / logs)."""
    described = []
    for account in accounts or []:
        if not isinstance(account, dict):
            continue
        described.append(
            {
                "login": str(account.get("login") or ""),
                "server": account.get("server"),
                "bot_id": account.get("bot_id"),
                "api_port": account.get("api_port"),
                "mt5_path": account.get("mt5_path"),
                "symbols": account.get("symbols"),
                "user_id": account.get("user_id"),
                "email": account.get("email"),
                "source": account.get("source"),
                "has_password": bool(account.get("password")),
                "terminal_ok": account.get("terminal_ok"),
                "terminal_source": account.get("terminal_source"),
                "terminal_reason": account.get("terminal_reason"),
            }
        )
    return described


def account_signature(accounts) -> str:
    """Stable signature so the supervisor can detect newly submitted accounts."""
    parts = []
    for account in accounts or []:
        if not isinstance(account, dict):
            continue
        login = str(account.get("login") or "").strip()
        if not login:
            continue
        parts.append(
            "|".join(
                [
                    login,
                    str(account.get("server") or ""),
                    str(account.get("api_port") or ""),
                    str(account.get("mt5_path") or ""),
                    str(account.get("bot_id") or ""),
                ]
            )
        )
    return ";".join(sorted(parts))


def plan_supervision(running_logins, accounts, auto_remove: bool = False) -> dict:
    """Compute which accounts to spawn/stop for the supervisor loop."""
    running = {str(login).strip() for login in (running_logins or []) if str(login).strip()}
    desired = OrderedDict()
    for account in accounts or []:
        if not isinstance(account, dict):
            continue
        login = str(account.get("login") or "").strip()
        if login and account.get("enabled", True):
            desired[login] = account
    return {
        "to_spawn": [account for login, account in desired.items() if login not in running],
        "to_remove": sorted(running - set(desired)) if auto_remove else [],
    }


def resolve_account_terminal(account: dict) -> dict:
    """Resolve (never provision) the terminal path for an account."""
    try:
        from utils.mt5_terminal import resolve_terminal

        return resolve_terminal(
            (account or {}).get("login"),
            (account or {}).get("mt5_path") or os.getenv("MT5_PATH", "").strip() or None,
            allow_shared=_env_truthy("MULTI_ACCOUNT_ALLOW_SHARED_TERMINAL", "false"),
        )
    except Exception as exc:  # pragma: no cover - defensive
        return {"ok": False, "path": "", "source": "unresolved", "reason": str(exc), "checked": []}


def ensure_account_terminal(account: dict) -> dict:
    """Resolve the terminal and provision a portable copy when allowed."""
    try:
        from utils.mt5_terminal import ensure_terminal

        return ensure_terminal(
            (account or {}).get("login"),
            (account or {}).get("mt5_path") or os.getenv("MT5_PATH", "").strip() or None,
            allow_shared=_env_truthy("MULTI_ACCOUNT_ALLOW_SHARED_TERMINAL", "false"),
        )
    except Exception as exc:  # pragma: no cover - defensive
        return {"ok": False, "path": "", "source": "unresolved", "reason": str(exc), "checked": []}


def next_respawn_backoff(attempts: int, base: float = None, cap: float = None) -> float:
    """Exponential backoff (seconds) before respawning a crashed account."""
    base = float(base if base is not None else os.getenv("MULTI_ACCOUNT_RESPAWN_BACKOFF_SECONDS", "120") or 120)
    cap = float(cap if cap is not None else os.getenv("MULTI_ACCOUNT_MAX_RESPAWN_BACKOFF_SECONDS", "900") or 900)
    attempts = max(1, int(attempts or 1))
    return min(cap, base * (2 ** (attempts - 1)))


def respawn_allowed(login: str, signature: str, failures: dict, now: float = None) -> bool:
    """True when a previously failed account may be respawned now.

    A change in the account's config signature (e.g. the terminal path was fixed
    or credentials were re-submitted) resets the backoff immediately.
    """
    state = (failures or {}).get(str(login))
    if not state:
        return True
    if state.get("signature") != signature:
        return True
    now = float(now if now is not None else time.time())
    return now >= float(state.get("retry_at") or 0)


def _write_server_row(client, table: str, login: str, record: dict) -> str:
    """Create/update one Supabase ``mt5_credentials`` row.

    Uses a true upsert when the table has a unique constraint on ``login`` and
    transparently falls back to select+insert/update when it does not (Supabase
    error 42P10), so locally submitted accounts always reach the server.
    """
    try:
        client.table(table).upsert(record, on_conflict="login").execute()
        return "upsert"
    except Exception as exc:
        message = str(exc)
        not_unique = ("42P10" in message) or ("ON CONFLICT" in message.upper()) or ("unique" in message.lower())
        if not not_unique:
            raise

    # Fallback: emulate the upsert with a lookup + write.
    existing = client.table(table).select("login").eq("login", login).limit(1).execute()
    rows = getattr(existing, "data", None) or []
    if rows:
        client.table(table).update(record).eq("login", login).execute()
        return "updated"

    try:
        client.table(table).insert(record).execute()
        return "inserted"
    except Exception as exc:
        # Some tables only have login/password/server (+active): retry minimally.
        minimal = {key: record[key] for key in ("login", "password", "server", "active") if key in record}
        if minimal == record:
            raise
        client.table(table).insert(minimal).execute()
        logger.debug("MULTI ACCOUNT | server insert for %s used minimal columns: %s", login, exc)
        return "inserted_minimal"


def sync_accounts_to_server(accounts) -> dict:
    """Push locally configured accounts UP to Supabase ``mt5_credentials``.

    This is what makes a locally submitted account (``ACCOUNT_n_*`` env vars,
    ``accounts.example.json``, ``data/accounts_local.json``) visible on the web /
    to other machines: every account with credentials is upserted so the website
    and the mirror can see it.
    """
    result = {"synced": [], "skipped": [], "failed": []}
    rows = []
    for account in accounts or []:
        if not isinstance(account, dict):
            continue
        login = str(account.get("login") or "").strip()
        password = str(account.get("password") or "").strip()
        if not login:
            continue
        if not password or not account.get("server"):
            result["skipped"].append(login)
            continue
        rows.append(account)

    if not rows:
        return result

    try:
        from config.supabase_credentials import apply_supabase_env, resolve_supabase_credentials

        apply_supabase_env(quiet=True)
        resolved = resolve_supabase_credentials()
        if not resolved["usable"]:
            result["failed"] = [str(a.get("login")) for a in rows]
            result["reason"] = "supabase_unavailable"
            return result
        from supabase import create_client

        client = create_client(resolved["url"], resolved["service_key"] or resolved["key"])
    except Exception as exc:
        result["failed"] = [str(a.get("login")) for a in rows]
        result["reason"] = str(exc)
        return result

    table = os.getenv("MT5_CREDENTIALS_TABLE", "mt5_credentials")
    for account in rows:
        login = str(account.get("login")).strip()
        record = {
            "login": login,
            "password": str(account.get("password")),
            "server": str(account.get("server")),
            "active": bool(account.get("enabled", True)),
        }
        if account.get("user_id"):
            record["user_id"] = str(account["user_id"])
        if account.get("email"):
            record["email"] = str(account["email"])
        # Publish the API endpoint too, so a mirror on another machine can reach
        # this host's child (it is de-duplicated/probed on the receiving side).
        try:
            if account.get("api_port"):
                record["api_port"] = int(account["api_port"])
        except (TypeError, ValueError):
            pass
        if account.get("api_host"):
            record["api_host"] = str(account["api_host"])
        try:
            method = _write_server_row(client, table, login, record)
            result["synced"].append(login)
            result.setdefault("methods", {})[login] = method
        except Exception as exc:
            message = str(exc)
            result["failed"].append(login)
            result.setdefault("errors", {})[login] = message
            logger.debug("MULTI ACCOUNT | server sync failed for %s: %s", login, message)

    if result["failed"] and "reason" not in result:
        first_error = (result.get("errors") or {}).get(result["failed"][0], "unknown error")
        result["reason"] = first_error
    return result


def write_active_accounts(entries, host: str = None) -> dict:
    """Record the accounts whose child processes are running right now.

    The mirror reads this registry so it only ever targets LIVE accounts instead
    of stale logins that would answer "Connection refused".
    """
    payload = {
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "host": host or os.getenv("MIRROR_CONNECT_HOST") or "127.0.0.1",
        "accounts": [
            {
                "login": str(item.get("login") or "").strip(),
                "api_port": item.get("api_port"),
                "bot_id": item.get("bot_id"),
                "server": item.get("server"),
                "source": item.get("source"),
            }
            for item in (entries or [])
            if str((item or {}).get("login") or "").strip()
        ],
    }
    try:
        ACTIVE_REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        ACTIVE_REGISTRY_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.debug("MULTI ACCOUNT | could not write active registry: %s", exc)
        return payload
    return payload


def read_active_accounts(ttl_seconds: float = None) -> dict:
    """Read the live-account registry (empty when missing or stale)."""
    ttl = float(
        ttl_seconds
        if ttl_seconds is not None
        else os.getenv("MIRROR_PEER_TTL_SECONDS", "180") or 180
    )
    try:
        if not ACTIVE_REGISTRY_PATH.exists():
            return {"accounts": [], "stale": True, "reason": "missing"}
        payload = json.loads(ACTIVE_REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"accounts": [], "stale": True, "reason": str(exc)}

    updated_at = str(payload.get("updated_at") or "")
    age = None
    try:
        from datetime import datetime, timezone

        stamp = datetime.strptime(updated_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - stamp).total_seconds()
    except Exception:
        age = None

    payload["age_seconds"] = age
    payload["stale"] = bool(age is not None and ttl > 0 and age > ttl)
    return payload


def _merge_accounts(*groups):
    merged = OrderedDict()
    for group in groups:
        for account in group:
            login = str(account.get("login") or "").strip()
            if not login:
                continue
            current = merged.get(login, {})
            merged[login] = {**current, **account}

    base_api_port = int(os.getenv("MULTI_ACCOUNT_BASE_API_PORT", "8000"))
    explicit_ports = set()
    for account in merged.values():
        try:
            explicit_ports.add(int(account.get("api_port")))
        except (TypeError, ValueError):
            continue

    used_ports = set()
    next_port = base_api_port
    for login in merged:
        account = merged[login]

        # API_PORT must be unique per account (each child runs its own Flask API),
        # otherwise two children would fight over the same port.
        try:
            port = int(account.get("api_port"))
        except (TypeError, ValueError):
            port = None
        if port is None or port in used_ports:
            while next_port in used_ports or next_port in explicit_ports:
                next_port += 1
            requested = account.get("api_port")
            port = next_port
            if requested is not None:
                _warn_once(
                    f"api_port:{login}:{requested}",
                    f"[MULTI] API_PORT {requested} already used; login={login} reassigned to {port}",
                )
            account["api_port"] = port
        used_ports.add(port)

        if not account.get("backtest_report_path"):
            account["backtest_report_path"] = f"backtest/latest_approval_{login}.json"

        # Resolve the MT5 terminal so the API/supervisor can tell whether the
        # account is runnable (resolution only - provisioning happens at spawn).
        terminal = resolve_account_terminal(account)
        account["terminal_ok"] = bool(terminal.get("ok"))
        account["terminal_source"] = terminal.get("source")
        if terminal.get("ok"):
            account["mt5_path"] = terminal.get("path")
        else:
            account["terminal_reason"] = terminal.get("reason")

    return list(merged.values())


def load_accounts(strict: bool = None):
    """Return every account the bot should run.

    Accepted sources (all merged, highest priority last):
      1. ``accounts.example.json`` / ``MULTI_ACCOUNT_CONFIG``  (local file)
      2. ``data/accounts_local.json``                          (saved locally / admin API)
      3. Supabase ``mt5_credentials``                          (submitted through the web)
      4. ``ACCOUNT_n_*`` env vars / ``MULTI_ACCOUNT_ACCOUNTS_JSON`` (local override)

    ``strict`` (default ``MULTI_ACCOUNT_REQUIRE_ACCOUNTS``) raises when nothing is
    found; the web-accepting supervisor runs with ``strict=False`` so it can wait
    for accounts submitted later.
    """
    if strict is None:
        strict = _env_truthy("MULTI_ACCOUNT_REQUIRE_ACCOUNTS", "true")

    env_accounts = _json_env_accounts()
    if not env_accounts:
        env_accounts = _indexed_env_accounts()

    server_accounts = _server_accounts()
    local_accounts = _local_store_accounts()
    config_accounts = _config_file_accounts()

    accounts = _merge_accounts(
        config_accounts,
        local_accounts,
        server_accounts,
        env_accounts,
    )

    # Accounts disabled after repeated MT5 authorization failures stay out of the
    # rotation until they are re-submitted through the admin API (or re-enabled).
    if _env_truthy("MULTI_ACCOUNT_HONOR_DISABLED", "true"):
        disabled = disabled_accounts()
        if disabled:
            kept = []
            for account in accounts:
                login = str(account.get("login") or "").strip()
                if login in disabled:
                    logger.debug(
                        "MULTI ACCOUNT | login=%s skipped (disabled: %s)",
                        login,
                        (disabled.get(login) or {}).get("reason"),
                    )
                    continue
                kept.append(account)
            accounts = kept

    if not accounts and strict:
        raise RuntimeError(
            f"No accounts configured in env, local store, server, or {CONFIG_PATH}. "
            "Submit one via POST /admin/accounts, add ACCOUNT_1_LOGIN / ACCOUNT_2_LOGIN..., "
            "or insert mt5_credentials rows."
        )
    return accounts


def build_env(account):
    env = os.environ.copy()
    env["MULTI_ACCOUNT_CHILD"] = "1"
    env["BOT_ID"] = str(account.get("bot_id") or f"mt5_bot_{account['login']}")
    env["MT5_ACCOUNT_LOGIN"] = str(account["login"])
    if account.get("password"):
        env["MT5_ACCOUNT_PASSWORD"] = str(account["password"])
    if account.get("server"):
        env["MT5_ACCOUNT_SERVER"] = str(account["server"])
    if account.get("user_id"):
        env["BOT_USER_ID"] = str(account["user_id"])
        env["SIGNAL_USER_ID"] = str(account["user_id"])
    if account.get("email"):
        env["BOT_USER_EMAIL"] = str(account["email"])
    if account.get("api_port") is not None:
        env["API_PORT"] = str(account["api_port"])
    if account.get("mt5_path"):
        env["MT5_PATH"] = str(account["mt5_path"])
    if account.get("symbols"):
        env["SYMBOLS"] = ",".join(account["symbols"])
    if account.get("backtest_report_path"):
        env["BACKTEST_REPORT_PATH"] = str(account["backtest_report_path"])
    if account.get("extra_env"):
        for key, value in account["extra_env"].items():
            env[str(key)] = str(value)
    return env


def spawn_account(account):
    env = build_env(account)
    command = [sys.executable, "main.py"]
    return subprocess.Popen(command, cwd=str(BASE_DIR), env=env)


def _terminal_key(account):
    return (account.get("mt5_path") or os.getenv("MT5_PATH") or "<default_mt5_terminal>").strip().lower()


def _stop_existing_terminal(account):
    if not _env_truthy("MULTI_ACCOUNT_KILL_EXISTING_TERMINALS", "true"):
        return

    mt5_path = str(account.get("mt5_path") or "").strip()
    if not mt5_path:
        return

    escaped_path = mt5_path.replace("'", "''")
    command = (
        "Get-CimInstance Win32_Process -Filter \"name = 'terminal64.exe'\" "
        f"| Where-Object {{ $_.ExecutablePath -eq '{escaped_path}' }} "
        "| ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            print(f"[MULTI] Cleared any existing MT5 terminal for account {account['login']}.")
    except Exception as exc:
        print(f"[MULTI] Failed to clear existing MT5 terminal for account {account['login']}: {exc}")


def main():
    accounts = load_accounts(strict=False)
    allow_shared_terminal = _env_truthy("MULTI_ACCOUNT_ALLOW_SHARED_TERMINAL", "false")
    processes = []
    restart_on_exit = _env_truthy("MULTI_ACCOUNT_RESTART_ON_EXIT", "false")
    start_delay_seconds = max(2, int(os.getenv("MULTI_ACCOUNT_START_DELAY_SECONDS", "35")))
    discovery_seconds = max(10, int(os.getenv("MULTI_ACCOUNT_DISCOVERY_SECONDS", "45")))
    auto_remove = _env_truthy("MULTI_ACCOUNT_AUTO_REMOVE", "false")
    max_accounts = max(1, int(os.getenv("MULTI_ACCOUNT_MAX_ACCOUNTS", "50")))
    used_terminals = set()

    def _spawn(account, delay=False):
        terminal_key = _terminal_key(account)
        if not allow_shared_terminal and terminal_key in used_terminals:
            print(
                f"[MULTI] Skipping account {account['login']} because it shares MT5 terminal "
                f"'{terminal_key}' with another running account."
            )
            return None
        _stop_existing_terminal(account)
        process = spawn_account(account)
        processes.append((account, process))
        used_terminals.add(terminal_key)
        print(
            f"[MULTI] Started account {account['login']} "
            f"(bot_id={account.get('bot_id')}, source={account.get('source')}, pid={process.pid})"
        )
        if delay and start_delay_seconds:
            print(f"[MULTI] Waiting {start_delay_seconds}s before starting the next account.")
            time.sleep(start_delay_seconds)
        return process

    try:
        for index, account in enumerate(accounts):
            _spawn(account, delay=index < len(accounts) - 1)

        last_discovery = time.time()
        while True:
            for account, process in list(processes):
                if process.poll() is not None:
                    processes.remove((account, process))
                    used_terminals.discard(_terminal_key(account))
                    print(f"[MULTI] Account {account['login']} exited with code {process.returncode}.")
                    if restart_on_exit:
                        restarted = _spawn(account)
                        if restarted is not None:
                            print(f"[MULTI] Restarted account {account['login']} (pid={restarted.pid})")

            # Accept accounts submitted later (local store / web-Supabase / env).
            if web_accounts_enabled() or _env_truthy("MULTI_ACCOUNT_LOAD_LOCAL_STORE", "true"):
                if time.time() - last_discovery >= discovery_seconds:
                    last_discovery = time.time()
                    try:
                        refreshed = load_accounts(strict=False)
                    except Exception as exc:
                        print(f"[MULTI] Account discovery failed: {exc}")
                        refreshed = []
                    plan = plan_supervision(
                        [str(a.get("login") or "") for a, _ in processes],
                        refreshed,
                        auto_remove=auto_remove,
                    )
                    for account in plan["to_spawn"]:
                        if len(processes) >= max_accounts:
                            print(f"[MULTI] Account limit reached ({max_accounts}); {account['login']} not started.")
                            break
                        _spawn(account)
                    for login in plan["to_remove"]:
                        for account, process in list(processes):
                            if str(account.get("login")) == login:
                                process.terminate()
                                processes.remove((account, process))
                                used_terminals.discard(_terminal_key(account))
                                print(f"[MULTI] Stopped removed/disabled account {login}.")
                                break

            if not processes and not web_accounts_enabled():
                raise RuntimeError("All multi-account bot processes have exited.")
            time.sleep(5)
    finally:
        for _, process in processes:
            if process.poll() is None:
                process.terminate()


if __name__ == "__main__":
    main()
