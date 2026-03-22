import logging
import os

from supabase import create_client

logger = logging.getLogger(__name__)


def _is_missing_column_error(exc, column_name):
    message = str(exc).lower()
    return (
        f"mt5_credentials.{column_name}" in message
        or ("column" in message and column_name in message)
    )


def _select_fields(has_updated_at):
    return "login,password,server,updated_at" if has_updated_at else "login,password,server"


def fetch_mt5_credentials():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY are required to load MT5 credentials")

    client = create_client(url, key)

    def _query(has_active, has_updated_at):
        query = client.table("mt5_credentials").select(_select_fields(has_updated_at))

        if has_active:
            query = query.eq("active", True)

        if has_updated_at:
            query = query.order("updated_at", desc=True)

        return query.limit(1).execute()

    has_active = True
    has_updated_at = True

    res = None
    for _ in range(4):
        try:
            res = _query(has_active, has_updated_at)
            break
        except Exception as exc:
            if has_active and _is_missing_column_error(exc, "active"):
                has_active = False
                logger.warning("mt5_credentials.active column missing; falling back without active filter")
                continue
            if has_updated_at and _is_missing_column_error(exc, "updated_at"):
                has_updated_at = False
                logger.warning("mt5_credentials.updated_at column missing; falling back without updated_at ordering")
                continue
            raise RuntimeError(f"Failed to fetch MT5 credentials from Supabase: {exc}") from exc

    if res is None:
        raise RuntimeError("Failed to resolve mt5_credentials schema")

    data = getattr(res, "data", None) or []
    if not data:
        raise RuntimeError("No MT5 credentials found in Supabase (mt5_credentials)")

    row = data[0]
    return {
        "login": row.get("login"),
        "password": row.get("password"),
        "server": row.get("server"),
    }
