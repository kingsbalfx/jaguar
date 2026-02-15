import os
import time
import logging
from datetime import datetime
from typing import Any, Dict

from supabase import create_client

logger = logging.getLogger(__name__)


_SUPABASE_CLIENT = None


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


def push_trade(trade: Dict[str, Any]):
    """Persist trade record for admin inspection. Best-effort with retries."""
    try:
        persist_log_to_supabase("trade", trade)
    except Exception:
        logger.exception("push_trade: unexpected error while persisting trade")


def persist_log_to_supabase(event_type: str, payload: Dict[str, Any]):
    """Persist a simple log record to Supabase `bot_logs` table."""
    client = _get_supabase_client()
    if not client:
        return

    record = {
        "event": event_type,
        "payload": payload or {},
        "created_at": datetime.utcnow().isoformat(),
    }

    def _insert():
        return client.table(os.getenv("BOT_LOGS_TABLE", "bot_logs")).insert(record).execute()

    res = _with_retries(_insert)
    if res is None:
        logger.error("persist_log_to_supabase: failed to insert log: %s", record)
    else:
        logger.debug("persist_log_to_supabase: inserted log: %s", event_type)


def persist_signal_to_supabase(signal: Dict[str, Any]):
    """Persist a generated trading signal to Supabase `bot_signals` table with retries and logging."""
    client = _get_supabase_client()
    if not client:
        return

    table = os.getenv("BOT_SIGNALS_TABLE", "bot_signals")
    record = {
        "user_id": signal.get("user_id"),
        "symbol": signal.get("symbol"),
        "direction": signal.get("direction"),
        "entry_price": signal.get("entry"),
        "stop_loss": signal.get("sl"),
        "take_profit": signal.get("tp"),
        "signal_quality": signal.get("signal_quality") or signal.get("quality") or "unknown",
        "confidence": signal.get("ml_probability") or signal.get("confidence"),
        "reason": signal.get("reason") or {},
        "status": signal.get("status") or "pending",
        "created_at": datetime.utcnow().isoformat(),
    }

    def _insert_signal():
        return client.table(table).insert(record).execute()

    res = _with_retries(_insert_signal)
    if res is None:
        logger.error("persist_signal_to_supabase: failed to insert signal: %s", record)
    else:
        logger.debug("persist_signal_to_supabase: inserted signal for %s", record.get("symbol"))
