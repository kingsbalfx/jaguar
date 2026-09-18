from flask import Flask, jsonify, request
import threading
import json
import time
from datetime import datetime
import os
import secrets
from bot_state import get_state, set_running, request_restart
from utils.logger import bot_log
from risk.mirror_trading import register_mirror_api

app = Flask("bot_api")

# Register mirror trading API endpoints
register_mirror_api(app)

# Global storage for webhook signals
webhook_signals = []
MAX_WEBHOOK_SIGNALS = 100  # Prevent memory issues


def _authorized():
    allowed = [
        os.getenv("BOT_API_TOKEN", "").strip(),
        os.getenv("BOT_SIGNAL_SECRET", "").strip(),
        os.getenv("ADMIN_API_KEY", "").strip(),
    ]
    allowed = [value for value in allowed if value]
    if not allowed:
        return False
    supplied = (
        request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        or request.headers.get("x-bot-api-token", "").strip()
        or request.headers.get("x-bot-signal-secret", "").strip()
        or request.args.get("token", "").strip()
    )
    return bool(supplied) and any(secrets.compare_digest(supplied, expected) for expected in allowed)


def _require_auth():
    if not _authorized():
        return jsonify({"error": "unauthorized"}), 401
    return None

def add_webhook_signal(signal_data):
    """Add a webhook signal to the queue"""
    global webhook_signals

    # Add timestamp and ID
    signal_data["received_at"] = datetime.now().isoformat()
    signal_data["signal_id"] = f"webhook_{int(time.time() * 1000)}"

    # Add to queue
    webhook_signals.append(signal_data)

    # Maintain max size
    if len(webhook_signals) > MAX_WEBHOOK_SIGNALS:
        webhook_signals.pop(0)  # Remove oldest

    bot_log(
        "webhook_signal_received",
        f"Received TradingView signal: {signal_data.get('symbol', 'unknown')} {signal_data.get('direction', 'unknown')}",
        signal_data,
        persist=True,
    )

def get_webhook_signals():
    """Get all queued webhook signals"""
    return webhook_signals.copy()

def clear_webhook_signals():
    """Clear all webhook signals"""
    global webhook_signals
    webhook_signals.clear()

@app.route("/webhook/tradingview", methods=["POST"])
def tradingview_webhook():
    """
    TradingView webhook endpoint for external signals

    Expected JSON format:
    {
        "symbol": "EURUSD",
        "direction": "BUY" or "SELL",
        "strategy": "optional strategy name",
        "price": optional entry price,
        "comment": "optional comment",
        "timestamp": optional timestamp
    }
    """
    try:
        denied = _require_auth()
        if denied:
            return denied
        data = request.get_json()

        if not data:
            return jsonify({"error": "No JSON data received"}), 400

        # Validate required fields
        symbol = data.get("symbol")
        direction = data.get("direction")

        if not symbol or not direction:
            return jsonify({"error": "Missing required fields: symbol and direction"}), 400

        # Validate direction
        direction = direction.upper()
        if direction not in ["BUY", "SELL"]:
            return jsonify({"error": "Direction must be BUY or SELL"}), 400

        # Add to signal queue
        add_webhook_signal(data)

        return jsonify({
            "status": "received",
            "signal_id": data.get("signal_id"),
            "message": f"Signal queued for {symbol} {direction}"
        }), 200

    except Exception as e:
        bot_log("webhook_error", f"Webhook processing error: {e}", {"error": str(e)}, persist=True)
        return jsonify({"error": str(e)}), 500

@app.route("/webhook/signals", methods=["GET"])
def get_signals():
    """Get queued webhook signals"""
    denied = _require_auth()
    if denied:
        return denied
    return jsonify({
        "signals": get_webhook_signals(),
        "count": len(webhook_signals)
    })

@app.route("/webhook/signals", methods=["DELETE"])
def clear_signals():
    """Clear all webhook signals"""
    denied = _require_auth()
    if denied:
        return denied
    clear_webhook_signals()
    return jsonify({"message": "Signals cleared"}), 200

@app.route("/health", methods=["GET"])
def health():
    state = get_state()
    return jsonify({
        "status": "ok",
        "running": state["running"],
        "connected": state.get("connected", False),
        "last_heartbeat": state.get("last_heartbeat"),
    })


@app.route("/status", methods=["GET"])
def status():
    denied = _require_auth()
    if denied:
        return denied
    return jsonify(get_state())


@app.route("/control", methods=["POST"])
def control():
    denied = _require_auth()
    if denied:
        return denied
    data = request.get_json() or {}
    action = data.get("action")
    if action == "stop":
        set_running(False)
        return jsonify({"result": "stopping"})
    if action == "start":
        set_running(True)
        return jsonify({"result": "started"})
    if action == "restart":
        request_restart()
        return jsonify({"result": "restart requested"})
    return jsonify({"error": "unknown action"}), 400


@app.route("/restart", methods=["POST"])
def restart():
    denied = _require_auth()
    if denied:
        return denied
    request_restart()
    return jsonify({"result": "restart requested"})


# ============================================================================
# ADMIN: credentials + integrations (locally insert / save / test)
# ============================================================================
@app.route("/admin/credentials", methods=["GET"])
def admin_credentials_status():
    """Masked status of every credential the bot resolves at runtime."""
    denied = _require_auth()
    if denied:
        return denied

    payload = {"supabase": {}, "news_feed": {}, "mt5_universe": {}, "mirror": {}}
    try:
        from config.supabase_credentials import credential_status

        payload["supabase"] = credential_status()
    except Exception as exc:
        payload["supabase"] = {"error": str(exc)}

    try:
        from fundamentals.news_feed import news_feed_status

        payload["news_feed"] = news_feed_status()
    except Exception as exc:
        payload["news_feed"] = {"error": str(exc)}

    try:
        from config.mt5_universe import universe_snapshot

        payload["mt5_universe"] = universe_snapshot()
    except Exception as exc:
        payload["mt5_universe"] = {"error": str(exc)}

    try:
        import risk.mirror_trading as mirror

        payload["mirror"] = {
            "enabled": mirror.MIRROR_ENABLED,
            "auto_open": mirror.MIRROR_AUTO_OPEN,
            "risk_percent": mirror.MIRROR_RISK_PERCENT,
            "supabase_table": mirror.MIRROR_SUPABASE_TABLE,
        }
    except Exception as exc:
        payload["mirror"] = {"error": str(exc)}

    return jsonify(payload)


@app.route("/admin/credentials/test", methods=["POST"])
def admin_credentials_test():
    """Test Supabase connectivity with supplied or already stored credentials."""
    denied = _require_auth()
    if denied:
        return denied

    data = request.get_json(silent=True) or {}
    try:
        from config.supabase_credentials import test_supabase_connection

        result = test_supabase_connection(
            url=data.get("supabase_url"),
            key=data.get("supabase_key") or data.get("supabase_service_key"),
        )
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify(result), (200 if result.get("ok") else 400)


@app.route("/admin/credentials", methods=["POST"])
def admin_credentials_save():
    """Insert/save credentials locally (Supabase, MT5, mirror settings).

    Body (any subset)::

        {
          "supabase_url": "https://xyz.supabase.co",
          "supabase_key": "service-or-anon-key",
          "supabase_service_key": "service-role-key",
          "test": true,
          "apply_mt5_env": true,
          "mt5": {"login": "123456", "password": "...", "server": "Broker-Demo", "path": "C:\\...\\terminal64.exe"},
          "mirror": {"enabled": true, "risk_percent": 1.0}
        }
    """
    denied = _require_auth()
    if denied:
        return denied

    data = request.get_json(silent=True) or {}
    url = str(data.get("supabase_url") or "").strip()
    key = str(data.get("supabase_key") or "").strip()
    service_key = str(data.get("supabase_service_key") or "").strip()
    if not url or not (key or service_key):
        return jsonify({"error": "supabase_url and supabase_key are required"}), 400

    extra = {}
    mt5 = data.get("mt5") or {}
    if isinstance(mt5, dict):
        for field, store_key in (
            ("login", "mt5_login"),
            ("password", "mt5_password"),
            ("server", "mt5_server"),
            ("path", "mt5_path"),
        ):
            if str(mt5.get(field) or "").strip():
                extra[store_key] = str(mt5[field]).strip()

    mirror = data.get("mirror") or {}
    if isinstance(mirror, dict):
        if "enabled" in mirror:
            extra["mirror_enabled"] = bool(mirror.get("enabled"))
        if mirror.get("risk_percent") is not None:
            extra["mirror_risk_percent"] = float(mirror["risk_percent"])

    response = {}
    try:
        from config.supabase_credentials import save_supabase_credentials

        response["supabase"] = save_supabase_credentials(
            url, key or service_key, service_key or key, extra=extra
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"failed to save credentials: {exc}"}), 500

    if extra and data.get("apply_mt5_env", True):
        if extra.get("mt5_login"):
            os.environ["MT5_ACCOUNT_LOGIN"] = extra["mt5_login"]
        if extra.get("mt5_password"):
            os.environ["MT5_ACCOUNT_PASSWORD"] = extra["mt5_password"]
        if extra.get("mt5_server"):
            os.environ["MT5_ACCOUNT_SERVER"] = extra["mt5_server"]
        if extra.get("mt5_path"):
            os.environ["MT5_PATH"] = extra["mt5_path"]

    if data.get("test"):
        try:
            from config.supabase_credentials import test_supabase_connection

            response["test"] = test_supabase_connection()
        except Exception as exc:
            response["test"] = {"ok": False, "error": str(exc)}

    response["restart_required"] = True
    bot_log(
        "credentials_saved_locally",
        "Supabase/MT5 credentials inserted from the admin API and saved locally",
        {"url": url, "mt5_fields": sorted(extra.keys())},
        persist=False,
    )
    return jsonify(response), 200


@app.route("/admin/universe/sync", methods=["POST"])
def admin_universe_sync():
    """Re-acquire the MT5 symbol universe on demand."""
    denied = _require_auth()
    if denied:
        return denied
    try:
        from config.mt5_universe import refresh_from_mt5, universe_snapshot

        refresh_from_mt5(strict=False)
        return jsonify({"ok": True, "universe": universe_snapshot()}), 200
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/admin/universe", methods=["GET"])
def admin_universe_status():
    """Show which symbols the bot considers tradable right now."""
    denied = _require_auth()
    if denied:
        return denied
    try:
        from config.mt5_universe import get_universe, universe_snapshot

        return jsonify({"universe": universe_snapshot(), "symbols": get_universe()}), 200
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ============================================================================
# ADMIN: MT5 account intake (local submission OR submitted through the web)
# ============================================================================
@app.route("/admin/accounts", methods=["GET"])
def admin_accounts_list():
    """List every accepted account (passwords masked) and where it came from."""
    denied = _require_auth()
    if denied:
        return denied

    try:
        from multi_account_runner import (
            LOCAL_STORE_PATH,
            describe_accounts,
            load_accounts,
            web_accounts_enabled,
        )

        accounts = load_accounts(strict=False)
        return jsonify(
            {
                "count": len(accounts),
                "accept_web": web_accounts_enabled(),
                "local_store": str(LOCAL_STORE_PATH),
                "sources": sorted({str(a.get("source") or "local") for a in accounts}),
                "accounts": describe_accounts(accounts),
            }
        ), 200
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/admin/accounts", methods=["POST"])
def admin_accounts_submit():
    """Accept an account submitted locally or through the web.

    Body::

        {
          "login": "4485839", "password": "...", "server": "Headway-Demo",
          "mt5_path": "C:\\\\...\\\\terminal64.exe",   # optional
          "api_port": 8001, "bot_id": "bot_acc_2",     # optional
          "user_id": "<supabase user uuid>", "email": "<subscriber>",  # optional
          "symbols": ["EURUSD", "XAUUSD"],             # optional
          "save_to_server": true,                      # also upsert to Supabase mt5_credentials
          "enabled": true
        }

    The account is saved to the local store (``data/accounts_local.json``) and,
    when ``save_to_server`` is true and Supabase is configured, upserted into
    ``mt5_credentials`` so the website / other machines see it too. The running
    supervisor picks it up within ``MULTI_ACCOUNT_DISCOVERY_SECONDS``.
    """
    denied = _require_auth()
    if denied:
        return denied

    data = request.get_json(silent=True) or {}
    login = str(data.get("login") or "").strip()
    password = str(data.get("password") or "").strip()
    server = str(data.get("server") or "").strip()
    if not login or not password or not server:
        return jsonify({"error": "login, password and server are required"}), 400

    account = {
        "login": login,
        "password": password,
        "server": server,
        "source": data.get("source") or "web",
        "enabled": bool(data.get("enabled", True)),
    }
    if data.get("mt5_path"):
        account["mt5_path"] = str(data["mt5_path"]).strip()
    if data.get("api_port") is not None:
        try:
            account["api_port"] = int(data["api_port"])
        except (TypeError, ValueError):
            return jsonify({"error": "api_port must be an integer"}), 400
    if data.get("bot_id"):
        account["bot_id"] = str(data["bot_id"]).strip()
    if data.get("user_id"):
        account["user_id"] = str(data["user_id"]).strip()
    if data.get("email"):
        account["email"] = str(data["email"]).strip()
    symbols = data.get("symbols")
    if isinstance(symbols, str):
        account["symbols"] = [item.strip() for item in symbols.split(",") if item.strip()]
    elif isinstance(symbols, list):
        account["symbols"] = [str(item).strip() for item in symbols if str(item).strip()]
    if isinstance(data.get("extra_env"), dict):
        account["extra_env"] = data["extra_env"]

    try:
        from multi_account_runner import save_local_account

        saved = save_local_account(account, enabled=account["enabled"])
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"failed to save account locally: {exc}"}), 500

    response = {
        "saved_locally": True,
        "account": {**saved, "password": "***"},
        "picked_up_within_seconds": int(os.getenv("MULTI_ACCOUNT_DISCOVERY_SECONDS", "45") or 45),
    }
    if data.get("save_to_server", True):
        try:
            from multi_account_runner import save_server_account

            response["saved_to_server"] = save_server_account(account)
        except Exception as exc:
            response["saved_to_server"] = False
            response["server_error"] = str(exc)

    bot_log(
        "account_submitted",
        f"MT5 account {login} accepted ({'web' if response.get('saved_to_server') else 'local'})",
        {"login": login, "server": server, "source": account.get("source")},
        persist=False,
    )
    return jsonify(response), 200


@app.route("/admin/accounts/<login>", methods=["DELETE"])
def admin_accounts_disable(login):
    """Disable an account (``?hard=true`` removes it from the local store)."""
    denied = _require_auth()
    if denied:
        return denied

    hard = str(request.args.get("hard", "")).lower() in ("1", "true", "yes")
    try:
        from multi_account_runner import delete_local_account, set_local_account_enabled

        if hard:
            changed = delete_local_account(login)
            action = "deleted"
        else:
            changed = set_local_account_enabled(login, False)
            action = "disabled"
        return jsonify({"login": login, "action": action, "changed": changed}), 200
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/admin/accounts/sync", methods=["POST"])
def admin_accounts_sync():
    """Re-read accounts from every source (local file, local store, web/Supabase)."""
    denied = _require_auth()
    if denied:
        return denied
    try:
        from multi_account_runner import describe_accounts, load_accounts

        accounts = load_accounts(strict=False)
        return jsonify({"count": len(accounts), "accounts": describe_accounts(accounts)}), 200
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/admin/strategies", methods=["GET"])
def admin_strategies_list():
    """List every strategy and whether it is ON (env default / local file / admin panel)."""
    denied = _require_auth()
    if denied:
        return denied
    try:
        from strategy.toggles import snapshot

        strategies = snapshot()
        return jsonify({
            "count": len(strategies),
            "enabled": [name for name, row in strategies.items() if row["enabled"]],
            "disabled": [name for name, row in strategies.items() if not row["enabled"]],
            "strategies": strategies,
        }), 200
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/admin/strategies", methods=["POST"])
def admin_strategies_set():
    """Turn one or more strategies ON/OFF at runtime (no restart needed).

    Body:
      {"strategy": "fallback5", "enabled": false}
      {"strategies": {"fallback3": false, "fallback5": true}}
    Optional: "persist_local" (default true), "persist_remote" (default true).
    """
    denied = _require_auth()
    if denied:
        return denied
    try:
        from strategy.toggles import set_enabled, snapshot

        data = request.get_json(silent=True) or {}
        persist_local = bool(data.get("persist_local", True))
        persist_remote = bool(data.get("persist_remote", True))

        changes = {}
        if data.get("strategy"):
            changes[str(data["strategy"]).strip().lower()] = bool(data.get("enabled", True))
        raw = data.get("strategies")
        if isinstance(raw, dict):
            for name, value in raw.items():
                changes[str(name).strip().lower()] = bool(value)

        if not changes:
            return jsonify({"error": "provide 'strategy' + 'enabled' or a 'strategies' object"}), 400

        results = []
        for name, value in changes.items():
            try:
                results.append(set_enabled(
                    name,
                    value,
                    persist_local=persist_local,
                    persist_remote=persist_remote,
                    updated_by="bot_api",
                ))
            except ValueError as exc:
                results.append({"strategy": name, "error": str(exc)})

        bot_log(
            "strategy_toggle",
            "Strategy toggles updated via bot API: %s" % changes,
            {"changes": changes, "persist_local": persist_local, "persist_remote": persist_remote},
            persist=False,
        )
        return jsonify({"updated": results, "strategies": snapshot()}), 200
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


def run_api(host="0.0.0.0", port=8000):
    import os

    host = os.getenv("API_HOST", host)
    try:
        port = int(os.getenv("API_PORT", str(port)))
    except Exception:
        port = port
    try:
        from waitress import serve

        serve(app, host=host, port=port, threads=8)
    except Exception:
        # Fallback to Flask dev server if waitress is not installed yet.
        app.run(host=host, port=port, threaded=True)


def start_in_thread():
    t = threading.Thread(target=run_api, daemon=True)
    t.start()
