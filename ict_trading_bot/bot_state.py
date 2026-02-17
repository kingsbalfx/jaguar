import threading
from datetime import datetime


_lock = threading.Lock()
_state = {
    "running": True,
    "restart_requested": False,
    "last_restart": None,
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


def consume_restart_request():
    with _lock:
        if _state["restart_requested"]:
            _state["restart_requested"] = False
            _state["last_restart"] = datetime.utcnow().isoformat() + "Z"
            return True
    return False
