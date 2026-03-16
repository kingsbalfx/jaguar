import logging
import os

from supabase import create_client

logger = logging.getLogger(__name__)


def fetch_mt5_credentials():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY are required to load MT5 credentials")

    client = create_client(url, key)

    def _query_active():
        return (
            client.table("mt5_credentials")
            .select("login,password,server,updated_at")
            .eq("active", True)
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )

    def _query_latest():
        return (
            client.table("mt5_credentials")
            .select("login,password,server,updated_at")
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )

    try:
        res = _query_active()
    except Exception as exc:
        message = str(exc).lower()
        if "mt5_credentials.active" not in message and "column" not in message:
            raise RuntimeError(f"Failed to fetch MT5 credentials from Supabase: {exc}") from exc
        logger.warning("mt5_credentials.active column missing; falling back to latest row")
        try:
            res = _query_latest()
        except Exception as fallback_exc:
            raise RuntimeError(f"Failed to fetch MT5 credentials from Supabase: {fallback_exc}") from fallback_exc

    data = getattr(res, "data", None) or []
    if not data:
        raise RuntimeError("No MT5 credentials found in Supabase (mt5_credentials)")

    row = data[0]
    return {
        "login": row.get("login"),
        "password": row.get("password"),
        "server": row.get("server"),
    }
