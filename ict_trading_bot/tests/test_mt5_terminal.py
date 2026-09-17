"""
Tests for MT5 terminal resolution / provisioning and respawn backoff
====================================================================

Covers the production failure ``(-10003, "Process create failed
'...\\Account_594151\\terminal64.exe'")``: a configured terminal path that does
not exist must be detected immediately (not after MT5 retries), resolved to a
usable terminal when one exists, or provisioned from the master install.
"""

import os

import pytest

from multi_account_runner import next_respawn_backoff, respawn_allowed
from utils import mt5_terminal


def _touch(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("stub")


@pytest.fixture
def terminal_root(monkeypatch, tmp_path):
    root = tmp_path / "MT5_Multi"
    master_dir = tmp_path / "MetaTrader 5"
    master_exe = master_dir / "terminal64.exe"
    _touch(str(master_exe))
    _touch(str(master_dir / "Config" / "accounts.dat"))
    _touch(str(master_dir / "Bases" / "huge.dat"))
    os.makedirs(str(master_dir / "logs"), exist_ok=True)
    os.makedirs(str(master_dir / "MQL5"), exist_ok=True)

    monkeypatch.setenv("MT5_MULTI_ROOT", str(root))
    monkeypatch.setenv("MT5_PATH", str(master_exe))
    monkeypatch.delenv("MULTI_ACCOUNT_ALLOW_SHARED_TERMINAL", raising=False)
    monkeypatch.delenv("MULTI_ACCOUNT_AUTO_CREATE_TERMINAL", raising=False)
    monkeypatch.delenv("ACCOUNT_1_MT5_PATH", raising=False)
    yield {"root": root, "master": str(master_exe), "master_dir": master_dir}


def test_configured_terminal_is_used_when_it_exists(terminal_root):
    exe = terminal_root["root"] / "Account_3611136" / "terminal64.exe"
    _touch(str(exe))
    result = mt5_terminal.resolve_terminal("3611136", str(exe))
    assert result["ok"] is True
    assert result["path"] == str(exe)
    assert result["source"] == "configured"


def test_missing_configured_path_falls_back_to_login_folder(terminal_root):
    exe = terminal_root["root"] / "Account_5941451" / "terminal64.exe"
    _touch(str(exe))
    # Exactly the production typo: Account_594151 instead of Account_5941451.
    result = mt5_terminal.resolve_terminal(
        "5941451", str(terminal_root["root"] / "Account_594151" / "terminal64.exe")
    )
    assert result["ok"] is True
    assert result["path"] == str(exe)
    assert result["source"] == "login_folder"


def test_missing_terminal_reports_checked_paths(terminal_root):
    result = mt5_terminal.resolve_terminal("5941472", str(terminal_root["root"] / "Account_5941472" / "terminal64.exe"))
    assert result["ok"] is False
    assert result["source"] == "missing"
    assert "terminal not found" in result["reason"]
    assert any("Account_5941472" in item for item in result["checked"])


def test_master_terminal_used_only_when_sharing_allowed(terminal_root):
    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setenv("MULTI_ACCOUNT_ALLOW_SHARED_TERMINAL", "false")
        blocked = mt5_terminal.resolve_terminal("999", None)
        assert blocked["ok"] is False

        monkeypatch.setenv("MULTI_ACCOUNT_ALLOW_SHARED_TERMINAL", "true")
        shared = mt5_terminal.resolve_terminal("999", None)
        assert shared["ok"] is True
        assert shared["source"] == "master_shared"
        assert shared["path"] == terminal_root["master"]
    finally:
        monkeypatch.undo()


def test_provision_terminal_copies_master_and_excludes_bulky_dirs(terminal_root):
    result = mt5_terminal.provision_terminal("5941466")
    assert result["ok"] is True
    assert result["provisioned"] is True

    dest = terminal_root["root"] / "Account_5941466"
    assert (dest / "terminal64.exe").is_file()
    assert not (dest / "Bases").exists()
    assert not (dest / "logs").exists()
    # Fresh login state must not carry the previous broker credentials.
    assert not (dest / "Config" / "accounts.dat").exists()


def test_ensure_terminal_provisions_when_enabled(terminal_root, monkeypatch):
    monkeypatch.setenv("MULTI_ACCOUNT_AUTO_CREATE_TERMINAL", "false")
    disabled = mt5_terminal.ensure_terminal("5941472")
    assert disabled["ok"] is False

    monkeypatch.setenv("MULTI_ACCOUNT_AUTO_CREATE_TERMINAL", "true")
    enabled = mt5_terminal.ensure_terminal("5941472")
    assert enabled["ok"] is True
    assert enabled["source"] in ("login_folder", "configured", "provisioned")
    assert (terminal_root["root"] / "Account_5941472" / "terminal64.exe").is_file()


def test_next_respawn_backoff_grows_and_caps():
    assert next_respawn_backoff(1, base=60, cap=600) == 60
    assert next_respawn_backoff(2, base=60, cap=600) == 120
    assert next_respawn_backoff(3, base=60, cap=600) == 240
    assert next_respawn_backoff(10, base=60, cap=600) == 600


def test_respawn_allowed_until_backoff_expires_and_resets_on_config_change():
    failures = {"777": {"attempts": 1, "retry_at": 1000.0, "signature": "sig-a"}}
    assert respawn_allowed("777", "sig-a", failures, now=900.0) is False
    assert respawn_allowed("777", "sig-a", failures, now=1001.0) is True
    # Config fixed (new signature) -> retry immediately.
    assert respawn_allowed("777", "sig-b", failures, now=900.0) is True
    # Never failed -> allowed.
    assert respawn_allowed("888", "sig-a", failures, now=0.0) is True
