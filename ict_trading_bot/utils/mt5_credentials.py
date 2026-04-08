import logging
import os

from supabase import create_client

logger = logging.getLogger(__name__)
_MISSING_COLUMN_WARNINGS = set()


def _env_credentials():
    login = os.getenv("MT5_ACCOUNT_LOGIN", "").strip() or os.getenv("MT5_LOGIN", "").strip()
    password = os.getenv("MT5_ACCOUNT_PASSWORD", "").strip() or os.getenv("MT5_PASSWORD", "").strip()
    server = os.getenv("MT5_ACCOUNT_SERVER", "").strip() or os.getenv("MT5_SERVER", "").strip()

    if login and password and server:
        return {
            "login": login,
            "password": password,
            "server": server,
        }

    return None


def _is_missing_column_error(exc, column_name):
    message = str(exc).lower()
    return (
        f"mt5_credentials.{column_name}" in message
        or ("column" in message and column_name in message)
    )


def _warn_once(message):
    if message in _MISSING_COLUMN_WARNINGS:
        return
    _MISSING_COLUMN_WARNINGS.add(message)
    logger.warning(message)


def _select_fields(has_updated_at, has_owner_fields):
    fields = ["login", "password", "server"]
    if has_updated_at:
        fields.append("updated_at")
    if has_owner_fields:
        fields.extend(["user_id", "email"])
    return ",".join(fields)


def _fetch_mt5_credentials_rows():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY are required to load MT5 credentials")

    client = create_client(url, key)

    account_login = os.getenv("MT5_ACCOUNT_LOGIN", "").strip()

    def _query(has_active, has_updated_at, has_owner_fields):
        query = client.table("mt5_credentials").select(_select_fields(has_updated_at, has_owner_fields))

        if has_active:
            query = query.eq("active", True)

        if account_login:
            query = query.eq("login", account_login)

        if has_updated_at:
            query = query.order("updated_at", desc=True)

        return query.execute()

    has_active = True
    has_updated_at = True
    has_owner_fields = True

    res = None
    for _ in range(6):
        try:
            res = _query(has_active, has_updated_at, has_owner_fields)
            break
        except Exception as exc:
            if has_active and _is_missing_column_error(exc, "active"):
                has_active = False
                _warn_once("mt5_credentials.active column missing; falling back without active filter")
                continue
            if has_updated_at and _is_missing_column_error(exc, "updated_at"):
                has_updated_at = False
                _warn_once("mt5_credentials.updated_at column missing; falling back without updated_at ordering")
                continue
            if has_owner_fields and (
                _is_missing_column_error(exc, "user_id") or _is_missing_column_error(exc, "email")
            ):
                has_owner_fields = False
                _warn_once("mt5_credentials user owner columns missing; floating PnL will fall back to login-only mapping")
                continue
            raise RuntimeError(f"Failed to fetch MT5 credentials from Supabase: {exc}") from exc

    if res is None:
        raise RuntimeError("Failed to resolve mt5_credentials schema")

    data = getattr(res, "data", None) or []
    if not data:
        raise RuntimeError("No MT5 credentials found in Supabase (mt5_credentials)")

    return data


def _fetch_mt5_credentials_row():
    rows = _fetch_mt5_credentials_rows()
    return rows[0]


def fetch_mt5_credentials():
    env_creds = _env_credentials()
    if env_creds:
        return env_creds
    row = _fetch_mt5_credentials_row()
    return {
        "login": row.get("login"),
        "password": row.get("password"),
        "server": row.get("server"),
    }


def fetch_mt5_credentials_signature():
    row = _env_credentials() or _fetch_mt5_credentials_row()
    return "|".join(
        [
            str(row.get("login") or ""),
            str(row.get("password") or ""),
            str(row.get("server") or ""),
        ]
    )


def fetch_all_mt5_credentials():
    rows = _fetch_mt5_credentials_rows()
    return [
        {
            "login": row.get("login"),
            "password": row.get("password"),
            "server": row.get("server"),
            "user_id": row.get("user_id"),
            "email": row.get("email"),
        }
        for row in rows
    ]
