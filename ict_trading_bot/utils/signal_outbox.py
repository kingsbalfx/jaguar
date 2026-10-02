"""Durable outbox for signals the website delivery API rejected or missed.

When the bot cannot hand a signal to the website (401 token mismatch, 5xx,
network error) the signal used to be persisted to Supabase only - and the
subscriber email/in-app fan-out lives behind the website API, so subscribers saw
nothing. This module keeps a JSON-lines outbox of undelivered signals and
retries them on every scan cycle, dropping only when they are delivered or
expire. Nothing extra is required to use it: the queue lives next to the other
runtime data files.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List

logger = logging.getLogger(__name__)


def _outbox_path() -> Path:
    configured = os.getenv("SIGNAL_OUTBOX_PATH")
    base = Path(__file__).resolve().parent.parent / "data"
    return Path(configured) if configured else base / "signal_outbox.jsonl"


def _env_int(name: str, default: int) -> int:
    try:
        return int(float(str(os.getenv(name, default)).strip()))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(str(os.getenv(name, default)).strip())
    except (TypeError, ValueError):
        return default


def _read_entries() -> List[Dict[str, Any]]:
    path = _outbox_path()
    if not path.exists():
        return []
    entries: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict) and isinstance(item.get("payload"), dict):
                entries.append(item)
    except Exception as exc:  # pragma: no cover - never break a scan
        logger.debug("signal_outbox: read failed: %s", exc)
    return entries


def _write_entries(entries: List[Dict[str, Any]]) -> None:
    path = _outbox_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not entries:
            if path.exists():
                path.unlink()
            return
        body = "\n".join(json.dumps(item, default=str) for item in entries)
        path.write_text(body + "\n", encoding="utf-8")
    except Exception as exc:  # pragma: no cover
        logger.warning("signal_outbox: write failed: %s", exc)


def enqueue(payload: Dict[str, Any], reason: str = "") -> bool:
    """Queue an undelivered signal. Idempotent per (symbol, direction, key)."""
    if not isinstance(payload, dict) or os.getenv("SIGNAL_OUTBOX_ENABLED", "true").lower() not in ("1", "true", "yes", "on"):
        return False
    key = "|".join(
        str(payload.get(part) or "")
        for part in ("symbol", "direction", "entryPrice", "stopLoss", "botId")
    )
    entries = _read_entries()
    for item in entries:
        if item.get("key") == key:
            return False
    entries.append(
        {
            "key": key,
            "payload": payload,
            "reason": str(reason or ""),
            "attempts": 0,
            "created_at": time.time(),
            "last_attempt": None,
            "last_status": None,
        }
    )
    limit = _env_int("SIGNAL_OUTBOX_MAX_ENTRIES", 500)
    if len(entries) > limit:
        entries = entries[-limit:]
    _write_entries(entries)
    logger.info("signal_outbox: queued undelivered signal for %s %s", payload.get("symbol"), payload.get("direction"))
    return True


def pending() -> List[Dict[str, Any]]:
    return _read_entries()


def stats() -> Dict[str, Any]:
    entries = _read_entries()
    now = time.time()
    return {
        "enabled": os.getenv("SIGNAL_OUTBOX_ENABLED", "true").lower() in ("1", "true", "yes", "on"),
        "pending": len(entries),
        "oldest_age_seconds": round(now - min((e.get("created_at", now) for e in entries), default=now), 1),
        "total_attempts": sum(int(e.get("attempts", 0)) for e in entries),
        "path": str(_outbox_path()),
    }


def flush(deliver: Callable[[Dict[str, Any]], Dict[str, Any]]) -> Dict[str, Any]:
    """Retry queued signals via ``deliver`` and drop delivered/expired entries."""
    entries = _read_entries()
    if not entries:
        return {"retried": 0, "delivered": 0, "dropped": 0, "remaining": 0}

    max_attempts = _env_int("SIGNAL_OUTBOX_MAX_ATTEMPTS", 20)
    max_age = _env_float("SIGNAL_OUTBOX_MAX_AGE_HOURS", 24.0) * 3600.0
    now = time.time()
    remaining: List[Dict[str, Any]] = []
    delivered = dropped = retried = 0

    for entry in entries:
        age = now - float(entry.get("created_at", now) or now)
        if age > max_age or int(entry.get("attempts", 0)) >= max_attempts:
            dropped += 1
            continue
        entry["attempts"] = int(entry.get("attempts", 0)) + 1
        entry["last_attempt"] = now
        retried += 1
        try:
            result = deliver(entry.get("payload") or {}) or {}
        except Exception as exc:  # pragma: no cover
            entry["last_status"] = f"error:{exc}"[:200]
            remaining.append(entry)
            continue
        entry["last_status"] = "accepted" if result.get("accepted") else str(result.get("reason") or result.get("status_code") or "rejected")
        if result.get("accepted"):
            delivered += 1
            continue
        remaining.append(entry)

    _write_entries(remaining)
    if retried:
        logger.info(
            "signal_outbox: retried=%s delivered=%s dropped=%s remaining=%s",
            retried, delivered, dropped, len(remaining),
        )
    return {"retried": retried, "delivered": delivered, "dropped": dropped, "remaining": len(remaining)}
