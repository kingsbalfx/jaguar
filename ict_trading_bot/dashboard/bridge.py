import os
import time
import logging
from datetime import datetime, timedelta
from typing import Any, Dict
from uuid import UUID

from supabase import create_client

logger = logging.getLogger(__name__)


_SUPABASE_CLIENT = None
_BOT_LOGS_HAS_CREATED_AT = True
_BOT_SIGNALS_HAS_CREATED_AT = True
_BOT_LOGS_HAS_EVENT = True
_BOT_LOGS_INSERT_DISABLED = False
_BOT_SIGNALS_INSERT_DISABLED = False
_SIGNAL_LIMIT_CHECK_DISABLED = False
_BOT_SIGNALS_HAS_BOT_ID = True

_BOT_LIMIT_UNLIMITED = 1000000
_BOT_TIER_LIMITS = {
    "free": {"signals": 3, "trades": 0, "quality": "standard"},
    "premium": {"signals": 15, "trades": 5, "quality": "premium"},
    "vip": {"signals": 30, "trades": 10, "quality": "vip"},
    "pro": {"signals": _BOT_LIMIT_UNLIMITED, "trades": 20, "quality": "pro"},
    "lifetime": {"signals": _BOT_LIMIT_UNLIMITED, "trades": _BOT_LIMIT_UNLIMITED, "quality": "pro"},
}


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def _int_limit(value: Any, fallback: int = 0) -> int:
    if str(value).strip().lower() == "unlimited":
        return _BOT_LIMIT_UNLIMITED
    try:
        numeric = int(float(value))
        return max(0, numeric)
    except Exception:
        return fallback


def _utc_day_window():
    now = datetime.utcnow()
    start = datetime(now.year, now.month, now.day)
    end = start + timedelta(days=1)
    return start.isoformat(), end.isoformat()


def _normalize_uuid(value: Any, allow_text: bool = False):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return str(UUID(raw))
    except Exception:
        return raw if allow_text else None


def _get_supabase_client():
    global _SUPABASE_CLIENT
    if _SUPABASE_CLIENT:
        return _SUPABASE_CLIENT

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        logger.warning("Supabase URL or KEY not set; persistence disabled")
        return None

    try:
        _SUPABASE_CLIENT = create_client(url, key)
        return _SUPABASE_CLIENT
    except Exception as e:
        logger.exception("Failed to create Supabase client: %s", e)
        return None


def _with_retries(func, max_attempts=3, base_delay=0.5, *args, **kwargs):
    attempt = 0
    while attempt < max_attempts:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            attempt += 1
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning("Supabase write failed (attempt %d/%d): %s — retrying in %.2fs",
                           attempt, max_attempts, e, delay)
            time.sleep(delay)
    logger.error("Supabase write failed after %d attempts", max_attempts)
    return None


def _fetch_user_bot_limits(client, user_uuid: str) -> Dict[str, Any]:
    response = (
        client.table("profiles")
        .select("bot_tier,bot_max_signals_per_day,bot_max_concurrent_trades,bot_signal_quality")
        .eq("id", user_uuid)
        .limit(1)
        .execute()
    )
    rows = getattr(response, "data", None) or []
    profile = rows[0] if rows else {}
    tier = str(profile.get("bot_tier") or "free").lower()
    defaults = _BOT_TIER_LIMITS.get(tier, _BOT_TIER_LIMITS["free"])
    return {
        "tier": tier,
        "max_signals_per_day": _int_limit(profile.get("bot_max_signals_per_day"), defaults["signals"]),
        "max_concurrent_trades": _int_limit(profile.get("bot_max_concurrent_trades"), defaults["trades"]),
        "signal_quality": str(profile.get("bot_signal_quality") or defaults["quality"]).lower(),
    }


def _count_user_signals(client, table: str, user_uuid: str, start: str, end: str) -> int:
    response = (
        client.table(table)
        .select("id")
        .eq("user_id", user_uuid)
        .gte("created_at", start)
        .lt("created_at", end)
        .execute()
    )
    return len(getattr(response, "data", None) or [])


def _count_user_open_signals(client, table: str, user_uuid: str) -> int:
    response = (
        client.table(table)
        .select("id")
        .eq("user_id", user_uuid)
        .in_("status", ["pending", "executed", "open"])
        .execute()
    )
    return len(getattr(response, "data", None) or [])


def _user_signal_quota_allows(client, table: str, user_uuid: str, signal: Dict[str, Any]):
    if not _env_bool("ENFORCE_USER_SIGNAL_LIMITS", True):
        return True, {}, "disabled"
    if not user_uuid:
        return True, {}, "no_user"

    limits = _fetch_user_bot_limits(client, user_uuid)
    if limits["signal_quality"] == "none":
        return False, limits, "signal_quality_none"
    if limits["max_concurrent_trades"] <= 0:
        return False, limits, "bot_execution_disabled"
    if limits["max_signals_per_day"] <= 0:
        return False, limits, "daily_signal_limit_zero"

    start, end = _utc_day_window()
    today_count = _count_user_signals(client, table, user_uuid, start, end)
    if today_count >= limits["max_signals_per_day"]:
        return False, {**limits, "today_signals": today_count}, "daily_signal_limit_reached"

    open_count = _count_user_open_signals(client, table, user_uuid)
    if open_count >= limits["max_concurrent_trades"]:
        return False, {**limits, "open_signals": open_count}, "concurrent_trade_limit_reached"

    return True, {**limits, "today_signals": today_count, "open_signals": open_count}, "allowed"


def push_trade(trade: Dict[str, Any]):
    """Persist trade record for admin inspection. Best-effort with retries."""
    try:
        persist_log_to_supabase("trade", trade)
    except Exception:
        logger.exception("push_trade: unexpected error while persisting trade")


def persist_account_snapshot_to_supabase(snapshot: Dict[str, Any]):
    """Persist account floating PnL/equity snapshot for admin and user dashboards."""
    try:
        persist_log_to_supabase("account_snapshot", snapshot or {})
    except Exception:
        logger.exception("persist_account_snapshot_to_supabase: unexpected error")


def persist_log_to_supabase(event_type: str, payload: Dict[str, Any]):
    """Persist a simple log record to Supabase `bot_logs` table."""
    global _BOT_LOGS_HAS_CREATED_AT, _BOT_LOGS_HAS_EVENT, _BOT_LOGS_INSERT_DISABLED
    client = _get_supabase_client()
    if not client:
        return
    if _BOT_LOGS_INSERT_DISABLED:
        return

    payload_value = payload or {}
    record = {
        "payload": payload_value,
    }
    if _BOT_LOGS_HAS_EVENT:
        record["event"] = event_type
    if _BOT_LOGS_HAS_CREATED_AT:
        record["created_at"] = datetime.utcnow().isoformat()

    def _insert():
        return client.table(os.getenv("BOT_LOGS_TABLE", "bot_logs")).insert(record).execute()

    res = _with_retries(_insert)
    if res is None and _BOT_LOGS_HAS_CREATED_AT:
        _BOT_LOGS_HAS_CREATED_AT = False
        record.pop("created_at", None)
        res = _with_retries(_insert)
    if res is None and _BOT_LOGS_HAS_EVENT:
        _BOT_LOGS_HAS_EVENT = False
        record.pop("event", None)
        if not record.get("payload"):
            record["payload"] = {"message": str(event_type), **payload_value}
        res = _with_retries(_insert)
    if res is None:
        _BOT_LOGS_INSERT_DISABLED = True
        logger.error("persist_log_to_supabase: failed to insert log: %s", record)
    else:
        logger.debug("persist_log_to_supabase: inserted log: %s", event_type)


def persist_signal_to_supabase(signal: Dict[str, Any]):
    """Persist a generated trading signal to Supabase `bot_signals` table with retries and logging."""
    global _BOT_SIGNALS_HAS_CREATED_AT, _BOT_SIGNALS_INSERT_DISABLED, _SIGNAL_LIMIT_CHECK_DISABLED, _BOT_SIGNALS_HAS_BOT_ID
    client = _get_supabase_client()
    if not client:
        return True
    if _BOT_SIGNALS_INSERT_DISABLED:
        return True

    table = os.getenv("BOT_SIGNALS_TABLE", "bot_signals")
    allow_text_bot_id = _env_bool("BOT_SIGNAL_TEXT_BOT_ID", False)
    bot_uuid = (
        _normalize_uuid(signal.get("bot_id"), allow_text=allow_text_bot_id)
        or _normalize_uuid(os.getenv("BOT_INSTANCE_ID"), allow_text=allow_text_bot_id)
        or _normalize_uuid(os.getenv("BOT_ID"), allow_text=allow_text_bot_id)
    )
    user_uuid = (
        _normalize_uuid(signal.get("user_id"))
        or _normalize_uuid(os.getenv("BOT_USER_ID"))
        or _normalize_uuid(os.getenv("SIGNAL_USER_ID"))
    )
    quota_profile = {}
    if user_uuid and not _SIGNAL_LIMIT_CHECK_DISABLED:
        try:
            allowed, quota_profile, quota_reason = _user_signal_quota_allows(client, table, user_uuid, signal)
            if not allowed:
                payload = {
                    "user_id": user_uuid,
                    "symbol": signal.get("symbol"),
                    "direction": signal.get("direction"),
                    "reason": quota_reason,
                    "limits": quota_profile,
                }
                persist_log_to_supabase("signal_quota_blocked", payload)
                logger.info("persist_signal_to_supabase: blocked signal by quota: %s", payload)
                return False
        except Exception as quota_error:
            if _env_bool("STRICT_USER_SIGNAL_LIMITS", False):
                persist_log_to_supabase(
                    "signal_quota_error",
                    {
                        "user_id": user_uuid,
                        "symbol": signal.get("symbol"),
                        "error": str(quota_error),
                    },
                )
                return False
            logger.warning("Signal quota check failed open: %s", quota_error)
            _SIGNAL_LIMIT_CHECK_DISABLED = True

    record = {
        "symbol": signal.get("symbol"),
        "direction": signal.get("direction"),
        "entry_price": signal.get("entry") or signal.get("entry_price"),
        "stop_loss": signal.get("sl") or signal.get("stop_loss"),
        "take_profit": signal.get("tp") or signal.get("take_profit"),
        "signal_quality": (
            signal.get("signal_quality")
            or signal.get("quality")
            or quota_profile.get("signal_quality")
            or "unknown"
        ),
        "confidence": signal.get("ml_probability") or signal.get("confidence"),
        "reason": signal.get("reason") or {},
        "status": signal.get("status") or "pending",
    }
    if bot_uuid and _BOT_SIGNALS_HAS_BOT_ID:
        record["bot_id"] = bot_uuid
    if user_uuid:
        record["user_id"] = user_uuid
    if _BOT_SIGNALS_HAS_CREATED_AT:
        record["created_at"] = datetime.utcnow().isoformat()

    def _insert_signal():
        return client.table(table).insert(record).execute()

    res = _with_retries(_insert_signal)
    if res is None and record.get("bot_id"):
        _BOT_SIGNALS_HAS_BOT_ID = False
        record.pop("bot_id", None)
        res = _with_retries(_insert_signal)
    if res is None and _BOT_SIGNALS_HAS_CREATED_AT:
        _BOT_SIGNALS_HAS_CREATED_AT = False
        record.pop("created_at", None)
        res = _with_retries(_insert_signal)
    if res is None:
        _BOT_SIGNALS_INSERT_DISABLED = True
        logger.error("persist_signal_to_supabase: failed to insert signal: %s", record)
        return True
    else:
        logger.debug("persist_signal_to_supabase: inserted signal for %s", record.get("symbol"))
        return True
