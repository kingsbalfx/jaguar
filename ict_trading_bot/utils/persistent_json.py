import json
import os
import time
from pathlib import Path
from typing import Any, Callable


def _clone_default(default):
    if isinstance(default, dict):
        return dict(default)
    if isinstance(default, list):
        return list(default)
    return default


def load_json_file(path, default=None):
    """Load JSON from disk and fall back to a caller-provided default."""
    target = Path(path)
    fallback = _clone_default({} if default is None else default)
    if not target.exists():
        return fallback

    try:
        with open(target, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return _clone_default(fallback)

def _write_json_atomic(path, data, *, retries=5, retry_delay=0.05):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2)
    last_error = None

    for attempt in range(retries):
        temp_path = target.with_name(f"{target.name}.{os.getpid()}.{attempt}.tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, target)
            return
        except Exception as exc:
            last_error = exc
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except Exception:
                pass
            time.sleep(retry_delay * (attempt + 1))

    if last_error is not None:
        raise last_error


def _lock_path(target: Path) -> Path:
    return target.with_name(f"{target.name}.lock")


def _acquire_lock(target: Path, *, timeout=10.0, stale_after=30.0) -> Path:
    lock_path = _lock_path(target)
    start = time.monotonic()
    attempt = 0

    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(str(os.getpid()))
            return lock_path
        except FileExistsError:
            try:
                age = time.time() - lock_path.stat().st_mtime
                if age > stale_after:
                    lock_path.unlink()
                    continue
            except FileNotFoundError:
                continue

            if time.monotonic() - start > timeout:
                raise TimeoutError(f"Timed out waiting for JSON lock: {lock_path}")

            attempt += 1
            time.sleep(min(retry_delay := 0.05 * max(1, attempt), 0.25))


def _release_lock(lock_path: Path):
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass


def save_json_file(path, data, *, retries=5, retry_delay=0.05):
    """
    Atomically write JSON to disk with a process lock.

    Multiple bot processes can update the same intelligence files, so we guard
    the full write/replace cycle with a lightweight lock file.
    """
    target = Path(path)
    lock_path = _acquire_lock(target)
    try:
        _write_json_atomic(target, data, retries=retries, retry_delay=retry_delay)
    finally:
        _release_lock(lock_path)


def update_json_file(path, updater: Callable[[Any], Any], default=None, *, retries=5, retry_delay=0.05):
    """
    Read-modify-write JSON safely across multiple bot processes.

    The updater receives the current decoded JSON payload and may mutate it in
    place or return a replacement object.
    """
    target = Path(path)
    lock_path = _acquire_lock(target)
    try:
        current = load_json_file(target, default)
        updated = updater(current)
        if updated is None:
            updated = current
        _write_json_atomic(target, updated, retries=retries, retry_delay=retry_delay)
        return updated
    finally:
        _release_lock(lock_path)
