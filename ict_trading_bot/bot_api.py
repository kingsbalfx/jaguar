from flask import Flask, jsonify, request
import threading
import json
import time
from datetime import datetime
from bot_state import get_state, set_running, request_restart
from utils.logger import bot_log

app = Flask("bot_api")

# Global storage for webhook signals
webhook_signals = []
MAX_WEBHOOK_SIGNALS = 100  # Prevent memory issues

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
    return jsonify({
        "signals": get_webhook_signals(),
        "count": len(webhook_signals)
    })

@app.route("/webhook/signals", methods=["DELETE"])
def clear_signals():
    """Clear all webhook signals"""
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
    return jsonify(get_state())


@app.route("/control", methods=["POST"])
def control():
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
    request_restart()
    return jsonify({"result": "restart requested"})


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
