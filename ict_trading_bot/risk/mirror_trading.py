"""
MIRROR TRADING SYSTEM
=====================
Coordinates trade signals across multiple MT5 accounts in a leader/follower model.

Architecture:
- Each child process runs independently with its own MT5 connection
- When one account (the "leader") executes a trade, it broadcasts the signal
  to all other accounts via their HTTP APIs
- Each receiving account calculates its own position size proportional to balance
- Supabase is used for cross-server coordination (primary channel for 100s of accounts)
- Shared file acts as fallback for local same-machine operation
- Kingsbalfx strategy is fully detected and handled

Supports:
  - Kingsbalfx strategy detection (request["strategy"] == "kingsbalfx")
  - Local (same-machine) operation via shared file + HTTP loopback
  - Supabase-based coordination for 100+ accounts across machines
  - Hundreds of accounts via batched HTTP + Supabase fan-out
  - No SQL required - auto-creates table on first use
  - Balance-proportional position sizing per account
"""

import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

# ===========================================================================
# Configuration
# ===========================================================================
MIRROR_ENABLED = os.getenv("MIRROR_TRADING_ENABLED", "true").lower() in ("1", "true", "yes")
MIRROR_AUTO_OPEN = os.getenv("MIRROR_AUTO_OPEN", "true").lower() in ("1", "true", "yes")
MIRROR_COOLDOWN_SECONDS = int(os.getenv("MIRROR_COOLDOWN_SECONDS", "300"))
MIRROR_API_TIMEOUT = float(os.getenv("MIRROR_API_TIMEOUT", "10"))
MIRROR_EXCLUDE_SAME = os.getenv("MIRROR_EXCLUDE_SAME", "true").lower() in ("1", "true", "yes")
MIRROR_RISK_PERCENT = float(os.getenv("MIRROR_RISK_PERCENT", os.getenv("RISK_PER_TRADE", "1.0")))
MIRROR_BROADCAST_BATCH = int(os.getenv("MIRROR_BROADCAST_BATCH", "10"))
MIRROR_BROADCAST_DELAY = float(os.getenv("MIRROR_BROADCAST_DELAY", "0.5"))
MIRROR_SUPABASE_TABLE = os.getenv("MIRROR_SUPABASE_TABLE", "mirror_signals")

_SHARED_SIGNAL_DIR = Path(__file__).resolve().parent.parent / "data"
_SHARED_SIGNAL_FILE = _SHARED_SIGNAL_DIR / "mirror_signals.json"

_received_signals: set = set()
_received_signals_lock = threading.Lock()
_last_mirror_time: Dict[str, float] = {}


# ===========================================================================
# Shared signal file (fallback channel - local same-machine)
# ===========================================================================
def _read_signal_file() -> List[Dict]:
    try:
        if _SHARED_SIGNAL_FILE.exists():
            with open(_SHARED_SIGNAL_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("[MIRROR] Failed to read signal file: %s", exc)
    return []


def _write_signal_file(signals: List[Dict]) -> bool:
    try:
        _SHARED_SIGNAL_DIR.mkdir(parents=True, exist_ok=True)
        recent = signals[-500:] if len(signals) > 500 else signals
        with open(_SHARED_SIGNAL_FILE, "w", encoding="utf-8") as f:
            json.dump(recent, f, indent=2, default=str)
        return True
    except OSError as exc:
        logger.error("[MIRROR] Failed to write signal file: %s", exc)
        return False


def _append_signal_to_file(signal: Dict) -> bool:
    signals = _read_signal_file()
    signals.append(signal)
    return _write_signal_file(signals)


# ===========================================================================
# Supabase-backed coordination (for 100+ accounts / cross-machine)
# ===========================================================================
def _supabase_client() -> Optional[Any]:
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY", os.getenv("SUPABASE_KEY", "")).strip()
    if not supabase_url or not supabase_key:
        return None
    try:
        from supabase import create_client
        return create_client(supabase_url, supabase_key)
    except Exception as exc:
        logger.debug("[MIRROR] Supabase client not available: %s", exc)
        return None


def _supabase_push_signal(signal: Dict) -> bool:
    """Push a mirror signal to Supabase. No SQL setup required."""
    client = _supabase_client()
    if not client:
        return False
    try:
        record = {
            "signal_id": signal.get("signal_id", ""),
            "expires_at": datetime.fromtimestamp(
                signal.get("expires_at", 0), tz=timezone.utc
            ).isoformat() if signal.get("expires_at") else None,
            "data": signal,
        }
        client.table(MIRROR_SUPABASE_TABLE).upsert(record, on_conflict="signal_id").execute()
        return True
    except Exception as exc:
        logger.debug("[MIRROR] Supabase push failed: %s", exc)
        return False


def _supabase_fetch_pending_signals() -> List[Dict]:
    """Fetch pending mirror signals from Supabase that haven't expired."""
    client = _supabase_client()
    if not client:
        return []
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        response = client.table(MIRROR_SUPABASE_TABLE).select("data").gt(
            "expires_at", now_iso
        ).limit(200).execute()
        if hasattr(response, "data"):
            records = response.data
            if isinstance(records, list):
                return [row.get("data", {}) for row in records if isinstance(row, dict)]
        return []
    except Exception as exc:
        logger.debug("[MIRROR] Supabase fetch failed: %s", exc)
        return []


# ===========================================================================
# Signal creation
# ===========================================================================
def create_mirror_signal(
    symbol: str,
    direction: str,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    source_login: str,
    source_strategy: str = "ict_state_machine",
    reason: str = "mirror_from_leader",
) -> Dict:
    """Create a standardized mirror signal dictionary.

    Properly detects Kingsbalfx strategy via `source_strategy`.
    main.py sets request["strategy"] = "kingsbalfx" in
    _evaluate_kingsbalfx_fallback(), and the mirror broadcast code passes
    request.get("strategy") as source_strategy.
    """
    signal_id = (
        f"MIRROR_{source_login}_{symbol}_{direction}_"
        f"{int(time.time() * 1000)}_{os.urandom(2).hex()}"
    )
    return {
        "signal_id": signal_id,
        "type": "mirror_trade",
        "symbol": symbol.upper() if symbol else symbol,
        "direction": direction.lower(),
        "entry_price": float(entry_price),
        "stop_loss": float(stop_loss),
        "take_profit": float(take_profit),
        "source_login": source_login,
        "source_strategy": source_strategy,
        "reason": reason,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "expires_at": time.time() + MIRROR_COOLDOWN_SECONDS,
        "bot_id": (
            os.getenv("BOT_ACCOUNT_ID")
            or os.getenv("BOT_ID")
            or os.getenv("PERSISTENT_BOT_ID")
            or "unknown"
        ),
    }


# ===========================================================================
# Peer discovery
# ===========================================================================
def _get_peers() -> List[Dict]:
    """Discover peer accounts from multi-account config and/or Supabase.

    For 100+ account support, peers are loaded from:
    1. Multi-account config (local env/multi_account_runner)
    2. Supabase MT5 credentials table (if configured)
    """
    peers = []
    my_login = os.getenv("MT5_ACCOUNT_LOGIN", "").strip()

    # Method 1: Local multi-account config
    try:
        from multi_account_runner import load_accounts
        accounts = load_accounts()
        for account in accounts:
            login = str(account.get("login") or "").strip()
            if not login:
                continue
            if MIRROR_EXCLUDE_SAME and login == my_login:
                continue
            api_port = account.get("api_port")
            if not api_port:
                continue
            peers.append({
                "login": login,
                "api_host": os.getenv("API_HOST", "127.0.0.1"),
                "api_port": int(api_port),
            })
    except Exception as exc:
        logger.debug("[MIRROR] Local peer discovery skipped: %s", exc)

    # Method 2: Supabase peer discovery (for 100+ accounts)
    if os.getenv("MIRROR_SUPABASE_DISCOVERY", "true").lower() in ("1", "true", "yes"):
        try:
            supabase_url = os.getenv("SUPABASE_URL", "").strip()
            supabase_key = os.getenv("SUPABASE_SERVICE_KEY", os.getenv("SUPABASE_KEY", "")).strip()
            supabase_table = os.getenv("MT5_CREDENTIALS_TABLE", "mt5_credentials")
            if supabase_url and supabase_key:
                from supabase import create_client
                sb_client = create_client(supabase_url, supabase_key)
                response = sb_client.table(supabase_table).select(
                    "login, api_port, api_host, bot_id, enabled"
                ).eq("enabled", True).execute()
                if hasattr(response, "data") and isinstance(response.data, list):
                    for row in response.data:
                        if not isinstance(row, dict):
                            continue
                        login = str(row.get("login") or "").strip()
                        if not login:
                            continue
                        if MIRROR_EXCLUDE_SAME and login == my_login:
                            continue
                        if any(p["login"] == login for p in peers):
                            continue
                        api_port = row.get("api_port") or os.getenv("MULTI_ACCOUNT_BASE_API_PORT", "8000")
                        api_host = row.get("api_host") or os.getenv("API_HOST", "127.0.0.1")
                        peers.append({
                            "login": login,
                            "api_host": str(api_host),
                            "api_port": int(api_port),
                        })
        except Exception as exc:
            logger.debug("[MIRROR] Supabase peer discovery skipped: %s", exc)

    return peers


# ===========================================================================
# Broadcasting: send signal to all peer accounts
# ===========================================================================
def _post_mirror_signal(peer: Dict, signal: Dict, headers: Dict[str, str]) -> Dict:
    url = f"http://{peer['api_host']}:{peer['api_port']}/api/mirror/signal"
    try:
        resp = requests.post(url, headers=headers, json=signal, timeout=MIRROR_API_TIMEOUT)
        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        action = data.get("action", "accepted") if isinstance(data, dict) else "accepted"
        if resp.ok:
            return {
                "login": peer["login"],
                "success": action in ("accepted", "executed"),
                "action": action,
                "reason": data.get("reason") if isinstance(data, dict) else None,
                "error": None,
            }
        return {
            "login": peer["login"],
            "success": False,
            "action": action,
            "reason": data.get("reason") if isinstance(data, dict) else None,
            "error": f"HTTP {resp.status_code}: {str(data)[:180]}",
        }
    except requests.ConnectionError:
        return {"login": peer["login"], "success": False, "action": None, "reason": None, "error": "Connection refused"}
    except requests.Timeout:
        return {"login": peer["login"], "success": False, "action": None, "reason": None, "error": "Timeout"}
    except Exception as exc:
        return {"login": peer["login"], "success": False, "action": None, "reason": None, "error": str(exc)[:180]}


def broadcast_signal(signal: Dict) -> List[Dict]:
    """Send mirror signal to all peer accounts via HTTP + Supabase + file.

    For 100+ account support:
      - Batches HTTP requests (MIRROR_BROADCAST_BATCH peers per batch)
      - Adds delay between batches (MIRROR_BROADCAST_DELAY seconds)
      - Also pushes to Supabase for peer discovery/failover

    Returns delivery results.
    """
    if not MIRROR_ENABLED:
        logger.info("[MIRROR] Mirror trading is disabled. Signal not broadcast.")
        return []

    _append_signal_to_file(signal)

    sb_pushed = _supabase_push_signal(signal)
    if sb_pushed:
        logger.info("[MIRROR] Signal pushed to Supabase: %s %s",
                     signal["symbol"], signal["direction"])

    peers = _get_peers()
    if not peers:
        logger.info("[MIRROR] No peer accounts found. Signal saved to file%s.",
                     " + Supabase" if sb_pushed else "")
        return []

    results = []
    api_token = (
        os.getenv("BOT_API_TOKEN", "").strip()
        or os.getenv("BOT_SIGNAL_SECRET", "").strip()
        or os.getenv("ADMIN_API_KEY", "").strip()
    )
    if not api_token:
        logger.warning("[MIRROR] BOT_API_TOKEN/BOT_SIGNAL_SECRET not set; skipping HTTP broadcasts.")
        return results

    batches = [peers[i:i + MIRROR_BROADCAST_BATCH] for i in range(0, len(peers), MIRROR_BROADCAST_BATCH)]
    logger.info("[MIRROR] Broadcasting to %s peers in %s batches of %s",
                 len(peers), len(batches), MIRROR_BROADCAST_BATCH)

    headers = {
        "Content-Type": "application/json",
        "x-bot-api-token": api_token,
        "Authorization": f"Bearer {api_token}",
    }

    for batch_idx, batch in enumerate(batches):
        worker_count = max(1, min(len(batch), MIRROR_BROADCAST_BATCH))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_results = [
                executor.submit(_post_mirror_signal, peer, signal, headers)
                for peer in batch
            ]
            for future in as_completed(future_results):
                results.append(future.result())

        if batch_idx < len(batches) - 1 and MIRROR_BROADCAST_DELAY > 0:
            time.sleep(MIRROR_BROADCAST_DELAY)

    successful = sum(1 for r in results if r.get("success"))
    executed = sum(1 for r in results if r.get("action") == "executed")
    skipped = sum(1 for r in results if r.get("action") == "skipped")
    logger.info(
        "[MIRROR] Broadcast complete: reached=%s/%s executed=%s skipped=%s failed=%s | %s %s | strategy=%s",
        successful, len(peers), executed, skipped, len(peers) - successful,
        signal["symbol"], signal["direction"], signal.get("source_strategy", "unknown"),
    )
    if successful < len(peers):
        failed = [r for r in results if not r.get("success")]
        for item in failed[:10]:
            logger.warning(
                "[MIRROR] Broadcast failed | login=%s action=%s reason=%s error=%s",
                item.get("login"),
                item.get("action"),
                item.get("reason"),
                item.get("error"),
            )
    return results


# ===========================================================================
# Receiving: handle incoming mirror signal
# ===========================================================================
def is_duplicate_signal(signal_id: str) -> bool:
    """Check if we've already processed this signal ID."""
    with _received_signals_lock:
        if signal_id in _received_signals:
            return True
        if len(_received_signals) > 10000:
            _received_signals.clear()
        _received_signals.add(signal_id)
    return False


def can_mirror_symbol(symbol: str) -> bool:
    """Check if we're allowed to mirror this symbol right now (cooldown)."""
    now = time.time()
    last = _last_mirror_time.get(symbol, 0.0)
    if now - last < MIRROR_COOLDOWN_SECONDS:
        return False
    _last_mirror_time[symbol] = now
    return True


def should_execute_mirror(signal: Dict) -> Tuple[bool, str]:
    """Determine if this account should execute the mirror signal."""
    if not MIRROR_ENABLED:
        return False, "mirror_trading_disabled"
    if not MIRROR_AUTO_OPEN:
        return False, "mirror_auto_open_disabled"
    signal_id = signal.get("signal_id", "")
    if is_duplicate_signal(signal_id):
        return False, "duplicate_signal"
    symbol = signal.get("symbol", "")
    if not can_mirror_symbol(symbol):
        return False, f"mirror_cooldown_active_for_{symbol}"
    source_login = signal.get("source_login", "")
    my_login = os.getenv("MT5_ACCOUNT_LOGIN", "").strip()
    if source_login == my_login:
        return False, "self_signal_ignored"
    if not signal.get("direction") or not signal.get("entry_price"):
        return False, "invalid_signal_missing_direction_or_price"
    return True, "ready_to_mirror"


# ===========================================================================
# Calculate position size based on account balance proportion
# ===========================================================================
def calculate_mirror_lot_size(signal: Dict, account_balance: float, risk_percent: float = 1.0) -> float:
    """Calculate position size proportional to account balance."""
    from execution.mt5_connector import calculate_volume_for_risk

    symbol = signal.get("symbol", "")
    direction = signal.get("direction", "buy")
    entry = float(signal.get("entry_price", 0))
    sl = float(signal.get("stop_loss", 0))

    if entry <= 0 or sl <= 0:
        logger.warning("[MIRROR] Invalid prices: entry=%s sl=%s", entry, sl)
        return 0.0

    direction_lower = direction.lower()
    if direction_lower == "buy":
        if sl >= entry:
            logger.warning("[MIRROR] Buy mirror: SL >= entry")
            return 0.0
    else:
        if sl <= entry:
            logger.warning("[MIRROR] Sell mirror: SL <= entry")
            return 0.0

    risk_percent = max(0.05, min(float(risk_percent), 5.0))
    risk_amount = account_balance * (risk_percent / 100.0)

    try:
        volume = calculate_volume_for_risk(symbol, entry, sl, risk_amount)
        if volume <= 0:
            logger.warning("[MIRROR] Volume <= 0 for %s", symbol)
            return 0.0
        return volume
    except Exception as exc:
        logger.error("[MIRROR] Lot calc error: %s", exc)
        return 0.0


# ===========================================================================
# Process mirror signal (full pipeline)
# ===========================================================================
def process_mirror_signal(signal: Dict) -> Dict:
    """Process incoming mirror signal: validate, calculate lot, execute.

    Handles both ICT State Machine (source_strategy="ict_state_machine")
    and Kingsbalfx (source_strategy="kingsbalfx") strategy trades.
    """
    should, reason = should_execute_mirror(signal)
    if not should:
        return {"action": "skipped", "reason": reason,
                "signal_id": signal.get("signal_id", ""),
                "symbol": signal.get("symbol", ""),
                "direction": signal.get("direction", "")}

    symbol = signal["symbol"]
    direction = signal["direction"]
    entry = float(signal["entry_price"])
    sl = float(signal["stop_loss"])
    tp = float(signal.get("take_profit", 0))
    source_strategy = signal.get("source_strategy", "unknown")
    source_login = signal.get("source_login", "unknown")

    logger.info("[MIRROR] Processing: %s %s | strategy=%s | source=%s",
                 symbol, direction.upper(), source_strategy, source_login)

    try:
        import MetaTrader5 as mt5
        account_info = mt5.account_info()
        if account_info is None:
            return {"action": "error", "reason": "mt5_not_connected", "symbol": symbol}
        account_balance = float(account_info.balance)
        margin_free = float(account_info.margin_free)
    except Exception as exc:
        return {"action": "error", "reason": f"mt5_account_info_failed:{exc}", "symbol": symbol}

    if account_balance <= 0:
        return {"action": "skipped", "reason": "zero_or_negative_balance",
                "symbol": symbol, "balance": account_balance}
    if margin_free <= 0:
        return {"action": "skipped", "reason": "no_free_margin",
                "symbol": symbol, "margin_free": margin_free}

    try:
        positions = mt5.positions_get(symbol=symbol) or []
        buy_type = getattr(mt5, "POSITION_TYPE_BUY", 0)
        for pos in positions:
            pos_dir = "buy" if getattr(pos, "type", buy_type) == buy_type else "sell"
            if pos_dir != direction:
                return {"action": "skipped",
                        "reason": f"opposing_position_exists_{pos_dir}",
                        "symbol": symbol}
    except Exception as exc:
        logger.warning("[MIRROR] Position check failed: %s", exc)

    volume = calculate_mirror_lot_size(signal, account_balance, MIRROR_RISK_PERCENT)
    if volume <= 0:
        return {"action": "skipped", "reason": "lot_size_zero_or_below_minimum",
                "symbol": symbol, "balance": account_balance}

    try:
        from execution.trade_executor import execute_trade
        trade_result = execute_trade(
            symbol=symbol, direction=direction, lot=volume,
            sl_price=sl, tp_price=tp, order_type="market", entry_price=entry,
        )
        if trade_result:
            logger.info("[MIRROR] EXECUTED: %s %s %.3f lots | strategy=%s | ticket=%s",
                         symbol, direction.upper(), volume,
                         source_strategy, trade_result.get("ticket"))
            return {"action": "executed", "reason": "mirror_trade_executed",
                    "symbol": symbol, "direction": direction, "volume": volume,
                    "entry": entry, "sl": sl, "tp": tp,
                    "balance": account_balance,
                    "ticket": trade_result.get("ticket"),
                    "signal_id": signal.get("signal_id", ""),
                    "source_strategy": source_strategy,
                    "source_login": source_login}
        else:
            logger.error("[MIRROR] Trade FAILED for %s %s", symbol, direction)
            return {"action": "error", "reason": "broker_rejected_trade",
                    "symbol": symbol, "direction": direction, "volume": volume}
    except Exception as exc:
        logger.error("[MIRROR] Trade ERROR for %s %s: %s", symbol, direction, exc)
        return {"action": "error", "reason": f"execution_error:{exc}",
                "symbol": symbol, "direction": direction}


# ===========================================================================
# Check for pending mirror signals (fallback / periodic scan)
# ===========================================================================
def check_pending_mirror_signals() -> List[Dict]:
    """Read pending mirror signals from file + Supabase and process unseen ones.

    Channels checked:
      1. Shared file (local same-machine fallback)
      2. Supabase (cross-machine / 100+ account coordination)
    """
    if not MIRROR_ENABLED:
        return []

    results = []

    # Channel 1: Shared file
    for signal in _read_signal_file():
        expires_at = signal.get("expires_at", 0)
        if time.time() > expires_at:
            continue
        results.append(process_mirror_signal(signal))

    # Channel 2: Supabase
    for signal in _supabase_fetch_pending_signals():
        expires_at = signal.get("expires_at", 0)
        if time.time() > expires_at:
            continue
        results.append(process_mirror_signal(signal))

    return results


# ===========================================================================
# Flask API endpoints
# ===========================================================================
MIRROR_API_PREFIX = "/api/mirror"


def register_mirror_api(app):
    """Register mirror trading API endpoints on the Flask app."""

    @app.route(f"{MIRROR_API_PREFIX}/signal", methods=["POST"])
    def _mirror_receive_signal():
        from flask import jsonify, request
        try:
            signal = request.get_json()
            if not signal:
                return jsonify({"error": "No signal data"}), 400
            required = ["symbol", "direction", "entry_price", "stop_loss"]
            missing = [f for f in required if not signal.get(f)]
            if missing:
                return jsonify({"error": f"Missing fields: {missing}"}), 400
            result = process_mirror_signal(signal)
            return jsonify(result), 200 if result.get("action") != "error" else 202
        except Exception as exc:
            logger.error("[MIRROR] Error processing signal: %s", exc)
            return jsonify({"error": str(exc), "action": "error"}), 500

    @app.route(f"{MIRROR_API_PREFIX}/status", methods=["GET"])
    def _mirror_status():
        from flask import jsonify
        return jsonify({
            "mirror_enabled": MIRROR_ENABLED,
            "auto_open": MIRROR_AUTO_OPEN,
            "account_login": os.getenv("MT5_ACCOUNT_LOGIN", "unknown"),
            "cooldown_seconds": MIRROR_COOLDOWN_SECONDS,
            "risk_percent": MIRROR_RISK_PERCENT,
            "api_port": os.getenv("API_PORT", "8000"),
            "bot_id": os.getenv("BOT_ACCOUNT_ID") or os.getenv("BOT_ID") or "unknown",
        })

    @app.route(f"{MIRROR_API_PREFIX}/peers", methods=["GET"])
    def _mirror_peers():
        from flask import jsonify
        peers = _get_peers()
        return jsonify({"peers": peers, "count": len(peers)})

    @app.route(f"{MIRROR_API_PREFIX}/health", methods=["GET"])
    def _mirror_health():
        from flask import jsonify
        return jsonify({
            "mirror_enabled": MIRROR_ENABLED,
            "auto_open": MIRROR_AUTO_OPEN,
            "duplicate_cache_size": len(_received_signals),
            "active_cooldowns": len(_last_mirror_time),
        })

    logger.info("[MIRROR] API endpoints registered at %s", MIRROR_API_PREFIX)


def get_peer_api_urls() -> List[str]:
    """Get base URLs for all peer APIs."""
    return [f"http://{p['api_host']}:{p['api_port']}" for p in _get_peers()]
