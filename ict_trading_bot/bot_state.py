import threading
from datetime import datetime


_lock = threading.Lock()
_state = {
    "running": True,
    "restart_requested": False,
    "last_restart": None,
    "connected": False,
    "last_error": None,
    "last_heartbeat": None,
    "account": {},
    "metrics": {
        "open_positions": 0,
        "floating_profit": 0.0,
        "balance": None,
        "equity": None,
        "margin_free": None,
        "symbols": [],
        "asset_scan": {"forex": 0, "metals": 0, "crypto": 0, "other": 0},
    },
    "recent_logs": [],
}


def get_state():
    with _lock:
        return dict(_state)


def is_running():
    with _lock:
        return bool(_state["running"])


def set_running(value: bool):
    with _lock:
        _state["running"] = bool(value)


def request_restart():
    with _lock:
        _state["restart_requested"] = True


def set_connection(connected: bool, last_error=None, account=None):
    with _lock:
        _state["connected"] = bool(connected)
        _state["last_error"] = last_error
        if account is not None:
            _state["account"] = account


def update_metrics(**metrics):
    with _lock:
        current = dict(_state.get("metrics") or {})
        current.update(metrics)
        _state["metrics"] = current
        _state["last_heartbeat"] = datetime.utcnow().isoformat() + "Z"


def append_log(event: str, message: str, payload=None):
    with _lock:
        logs = list(_state.get("recent_logs") or [])
        logs.insert(
            0,
            {
                "event": event,
                "message": message,
                "payload": payload or {},
                "created_at": datetime.utcnow().isoformat() + "Z",
            },
        )
        _state["recent_logs"] = logs[:50]
        _state["last_heartbeat"] = datetime.utcnow().isoformat() + "Z"


def consume_restart_request():
    with _lock:
        if _state["restart_requested"]:
            _state["restart_requested"] = False
            _state["last_restart"] = datetime.utcnow().isoformat() + "Z"
            return True
    return False
