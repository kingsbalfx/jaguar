"""Persistent duplicate-trade and daily-loss protection."""

import os
import time
from pathlib import Path

from utils.persistent_json import load_json_file, save_json_file
from utils.symbol_profile import canonical_symbol


def _memory_file() -> Path:
    configured = os.getenv("TRADE_MEMORY_STORAGE_PATH")
    return Path(configured) if configured else Path(__file__).resolve().parent.parent / "data" / "trade_memory_runtime.json"


def _load():
    return load_json_file(_memory_file(), {"setups": {}, "day": None, "day_start_equity": None, "outcomes": {}})


def _save(memory):
    save_json_file(_memory_file(), memory)


def can_trade(symbol, setup_id=None, cooldown=300, **_ignored):
    memory = _load()
    key = str(setup_id or f"{canonical_symbol(symbol)}_general")
    timestamp = (memory.get("setups") or {}).get(key)
    return timestamp is None or time.time() - float(timestamp) >= int(cooldown)


def register_trade(symbol, setup_id):
    memory = _load()
    key = str(setup_id or f"{canonical_symbol(symbol)}_general")
    memory.setdefault("setups", {})[key] = time.time()
    _save(memory)


def setup_identity(symbol, direction, retracement=None):
    zone = retracement or {}
    return "|".join(
        (
            canonical_symbol(symbol),
            str(direction or "").lower(),
            str(round(float(zone.get("low", 0.0) or 0.0), 8)),
            str(round(float(zone.get("high", 0.0) or 0.0), 8)),
            str(zone.get("kind") or "general"),
        )
    )


def daily_loss_allows_trade(account_snapshot):
    if not account_snapshot:
        return False, "account_snapshot_missing"
    today = time.strftime("%Y-%m-%d", time.gmtime())
    equity = float(account_snapshot.get("equity") or account_snapshot.get("balance") or 0.0)
    memory = _load()
    if memory.get("day") != today or not memory.get("day_start_equity"):
        memory["day"] = today
        memory["day_start_equity"] = equity
        _save(memory)
    start = float(memory.get("day_start_equity") or equity)
    loss_percent = max(0.0, (start - equity) / max(start, 1e-9) * 100.0)
    maximum = float(os.getenv("MAX_DAILY_LOSS_PERCENT", "5.0"))
    return loss_percent < maximum, f"daily_loss={loss_percent:.2f}% max={maximum:.2f}%"


def register_outcome(symbol, won):
    memory = _load()
    key = canonical_symbol(symbol)
    outcomes = memory.setdefault("outcomes", {}).setdefault(key, {"wins": 0, "losses": 0})
    outcomes["wins" if won else "losses"] += 1
    _save(memory)
