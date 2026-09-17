"""
MT5 terminal (``terminal64.exe``) resolution + provisioning
===========================================================

An MT5 account is only tradable when a real ``terminal64.exe`` exists for it (and,
with ``MT5_PORTABLE=true``, it must be its own folder so several accounts never
share one terminal).

This module answers two questions for any account, local or submitted through
the web:

1. :func:`resolve_terminal` — where is the terminal? It checks, in order:
   1. the configured ``ACCOUNT_n_MT5_PATH`` / submitted ``mt5_path``,
   2. ``<MT5_MULTI_ROOT>\\Account_<login>\\terminal64.exe``,
   3. any ``Account_*<login>*`` folder under the multi root,
   4. the master install (``MT5_PATH``) when terminal sharing is allowed.
2. :func:`ensure_terminal` — if nothing exists and
   ``MULTI_ACCOUNT_AUTO_CREATE_TERMINAL=true``, copy the master install into
   ``Account_<login>`` (like ``setup_multi_account_mt5.ps1`` does) so a newly
   submitted account becomes runnable without manual steps.

Environment
-----------
    MT5_PATH                          master install (source for provisioning)
    MT5_MULTI_ROOT                    default ``%USERPROFILE%\\MT5_Multi``
    MULTI_ACCOUNT_AUTO_CREATE_TERMINAL (default false)
    MULTI_ACCOUNT_ALLOW_SHARED_TERMINAL (default false)
"""

from __future__ import annotations

import glob
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

EXE_NAME = "terminal64.exe"
# Same exclusions the PowerShell setup script uses: Bases is multi-GB symbol
# history that MT5 re-downloads, and logs/temp/Tester are per-run state.
_EXCLUDE_DIRS = ("Bases", "logs", "temp", "Tester")


def _truthy(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def is_terminal(path: Optional[str]) -> bool:
    return bool(path) and os.path.isfile(str(path))


def multi_root() -> str:
    """Root folder holding one portable terminal per account."""
    explicit = os.getenv("MT5_MULTI_ROOT", "").strip()
    if explicit:
        return explicit
    first = os.getenv("ACCOUNT_1_MT5_PATH", "").strip()
    if first and os.path.dirname(first):
        parent = os.path.dirname(first)
        if os.path.basename(parent).lower().startswith("account_"):
            return os.path.dirname(parent)
    return str(Path.home() / "MT5_Multi")


def master_terminal() -> str:
    return os.getenv("MT5_PATH", "").strip()


def candidate_paths(login: Any) -> List[str]:
    """Terminal paths to try for ``login`` (order matters)."""
    login = str(login or "").strip()
    root = multi_root()
    candidates: List[str] = []
    if login:
        candidates.append(os.path.join(root, f"Account_{login}", EXE_NAME))
        candidates.append(os.path.join(root, login, EXE_NAME))
        candidates.extend(sorted(glob.glob(os.path.join(root, f"Account_*{login}*", EXE_NAME))))
    candidates.append(os.path.join(root, EXE_NAME))

    unique: List[str] = []
    for item in candidates:
        if item not in unique:
            unique.append(item)
    return unique



def resolve_terminal(
    login: Any,
    configured: Optional[str] = None,
    allow_shared: Optional[bool] = None,
) -> Dict[str, Any]:
    """Return ``{"ok", "path", "source", "reason", "checked"}`` for an account."""
    configured = str(configured or "").strip()
    checked: List[str] = []

    if is_terminal(configured):
        return {"ok": True, "path": configured, "source": "configured", "reason": "", "checked": [configured]}

    for candidate in candidate_paths(login):
        checked.append(candidate)
        if is_terminal(candidate):
            return {
                "ok": True,
                "path": candidate,
                "source": "login_folder",
                "reason": f"configured path missing; using {candidate}",
                "checked": checked,
            }

    shared = allow_shared if allow_shared is not None else _truthy("MULTI_ACCOUNT_ALLOW_SHARED_TERMINAL", False)
    master = master_terminal()
    if master:
        checked.append(master)
        if is_terminal(master) and shared:
            return {
                "ok": True,
                "path": master,
                "source": "master_shared",
                "reason": "sharing the master terminal (MULTI_ACCOUNT_ALLOW_SHARED_TERMINAL=true)",
                "checked": checked,
            }

    if configured:
        reason = f"terminal not found at configured path: {configured}"
    elif login:
        reason = f"no terminal configured and none found for login={login}"
    else:
        reason = "no MT5 terminal path configured"
    if master and not is_terminal(master):
        reason += f"; master MT5_PATH also missing ({master})"
    return {
        "ok": False,
        "path": "",
        "source": "missing",
        "reason": reason,
        "checked": checked,
        "master": master,
        "multi_root": multi_root(),
    }



def provision_terminal(login: Any, source_exe: Optional[str] = None) -> Dict[str, Any]:
    """Create ``<MT5_MULTI_ROOT>\\Account_<login>`` from the master install."""
    login = str(login or "").strip()
    if not login:
        return {"ok": False, "reason": "login is required"}

    source_exe = str(source_exe or master_terminal()).strip()
    if not is_terminal(source_exe):
        return {"ok": False, "reason": f"source terminal not found: {source_exe or '<MT5_PATH unset>'}"}

    source_dir = Path(source_exe).parent
    dest_dir = Path(multi_root()) / f"Account_{login}"
    dest_exe = dest_dir / EXE_NAME
    if dest_exe.is_file():
        return {"ok": True, "path": str(dest_exe), "source": "existing", "provisioned": False}

    if str(dest_dir.resolve()) == str(source_dir.resolve()):
        return {"ok": True, "path": str(dest_exe), "source": "master_shared", "provisioned": False}

    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            str(source_dir),
            str(dest_dir),
            ignore=shutil.ignore_patterns(*_EXCLUDE_DIRS),
            dirs_exist_ok=True,
        )
    except Exception as exc:
        return {"ok": False, "reason": f"failed to provision terminal: {exc}"}

    # Fresh login state: drop previous broker credentials from the copy.
    for name in ("accounts.dat", "terminal.ini"):
        stale = dest_dir / "Config" / name
        try:
            if stale.exists():
                stale.unlink()
        except OSError:
            pass

    if not dest_exe.is_file():
        return {"ok": False, "reason": f"provisioned folder has no {EXE_NAME}: {dest_dir}"}

    logger.info("MT5 TERMINAL | provisioned portable terminal for login=%s at %s", login, dest_exe)
    return {"ok": True, "path": str(dest_exe), "source": "provisioned", "provisioned": True}


def ensure_terminal(
    login: Any,
    configured: Optional[str] = None,
    allow_shared: Optional[bool] = None,
) -> Dict[str, Any]:
    """Resolve a terminal for ``login``, provisioning one when allowed."""
    resolved = resolve_terminal(login, configured, allow_shared=allow_shared)
    if resolved.get("ok"):
        return resolved

    if not _truthy("MULTI_ACCOUNT_AUTO_CREATE_TERMINAL", False):
        return resolved

    provisioned = provision_terminal(login)
    if not provisioned.get("ok"):
        resolved["provision_error"] = provisioned.get("reason")
        return resolved

    return resolve_terminal(login, provisioned.get("path"), allow_shared=allow_shared)
