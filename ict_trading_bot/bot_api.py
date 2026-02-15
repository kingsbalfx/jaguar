from flask import Flask, jsonify, request
import threading

app = Flask("bot_api")

state = {
    "running": True,
    "last_ping": None
}


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "running": state["running"]})


@app.route("/status", methods=["GET"])
def status():
    return jsonify(state)


@app.route("/control", methods=["POST"])
def control():
    data = request.get_json() or {}
    action = data.get("action")
    if action == "stop":
        state["running"] = False
        return jsonify({"result": "stopping"})
    if action == "start":
        state["running"] = True
        return jsonify({"result": "started"})
    return jsonify({"error": "unknown action"}), 400


def run_api(host="0.0.0.0", port=8000):
    # Run Flask without blocking (use threaded server for dev)
    app.run(host=host, port=port, threaded=True)


def start_in_thread():
    t = threading.Thread(target=run_api, daemon=True)
    t.start()
