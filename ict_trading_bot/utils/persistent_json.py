import json
import os
import time
from pathlib import Path


def load_json_file(path, default=None):
    """Load JSON from disk and fall back to a caller-provided default."""
    target = Path(path)
    fallback = {} if default is None else default
    if not target.exists():
        return dict(fallback) if isinstance(fallback, dict) else fallback

    try:
        with open(target, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return dict(fallback) if isinstance(fallback, dict) else fallback


def save_json_file(path, data, *, retries=5, retry_delay=0.05):
    """
    Atomically write JSON to disk with a few retries for concurrent writers.

    Multiple bot processes can update the same intelligence files, so we write to
    a temp file first and then replace the target in one step.
    """
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
