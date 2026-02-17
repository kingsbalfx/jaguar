from flask import Flask, jsonify, request
import threading
from bot_state import get_state, set_running, request_restart

app = Flask("bot_api")

@app.route("/health", methods=["GET"])
def health():
    state = get_state()
    return jsonify({"status": "ok", "running": state["running"]})


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
    # Run Flask without blocking (use threaded server for dev)
    app.run(host=host, port=port, threaded=True)


def start_in_thread():
    t = threading.Thread(target=run_api, daemon=True)
    t.start()
