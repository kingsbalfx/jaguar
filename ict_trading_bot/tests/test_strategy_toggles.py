"""
Tests for the runtime strategy switches
=======================================

A strategy must be switchable ON/OFF from three places, with this precedence:

    1. local file   data/strategy_toggles.json   (the machine itself)
    2. admin panel  Supabase bot_strategy_settings
    3. .env default ICT_ENABLED / FALLBACK5_ENABLED / ...

and everything must fail *open* (never silently disable trading).
"""

import json

import pytest


@pytest.fixture
def toggles_env(monkeypatch, tmp_path):
    """Isolate the toggle store and disable the Supabase (admin panel) read."""
    store = tmp_path / "strategy_toggles.json"
    monkeypatch.setenv("STRATEGY_TOGGLE_STORE", str(store))
    monkeypatch.setenv("STRATEGY_TOGGLE_REMOTE", "false")
    monkeypatch.setenv("STRATEGY_TOGGLE_TTL_SECONDS", "0")
    for key in (
        "ICT_ENABLED",
        "KINGSBALFX_ENABLED",
        "FALLBACK3_ENABLED",
        "FALLBACK4_ENABLED",
        "FALLBACK5_ENABLED",
        "MIRROR_TRADING_ENABLED",
    ):
        monkeypatch.delenv(key, raising=False)

    import strategy.toggles as toggles

    toggles._last_logged.clear()
    toggles._cache.update({"at": 0.0, "local": {}, "remote": {}})
    return toggles, store


def _write_store(store, mapping):
    store.write_text(json.dumps({"strategies": mapping}), encoding="utf-8")


def test_env_defaults_enable_every_strategy(toggles_env):
    toggles, _ = toggles_env
    for name in toggles.STRATEGY_NAMES:
        assert toggles.is_enabled(name) is True


def test_env_can_switch_a_strategy_off(toggles_env, monkeypatch):
    toggles, _ = toggles_env
    monkeypatch.setenv("FALLBACK5_ENABLED", "false")
    assert toggles.is_enabled("fallback5") is False
    assert toggles.is_enabled("fallback4") is True


def test_local_store_overrides_env(toggles_env, monkeypatch):
    toggles, store = toggles_env
    monkeypatch.setenv("FALLBACK3_ENABLED", "true")
    _write_store(store, {"fallback3": False})

    assert toggles.is_enabled("fallback3") is False
    assert toggles.snapshot()["fallback3"]["source"] == "local"


def test_admin_panel_override_is_used(toggles_env, monkeypatch):
    toggles, _ = toggles_env
    monkeypatch.setattr(toggles, "_read_remote", lambda: {"fallback4": False})

    assert toggles.is_enabled("fallback4") is False
    assert toggles.snapshot()["fallback4"]["source"] == "admin_panel"


def test_local_store_beats_admin_panel(toggles_env, monkeypatch):
    toggles, store = toggles_env
    monkeypatch.setattr(toggles, "_read_remote", lambda: {"fallback5": True})
    _write_store(store, {"fallback5": False})

    assert toggles.is_enabled("fallback5") is False
    assert toggles.snapshot()["fallback5"]["source"] == "local"


def test_set_enabled_writes_the_local_store(toggles_env):
    toggles, store = toggles_env

    result = toggles.set_enabled("kingsbalfx", False, persist_remote=False)
    assert result["saved_locally"] is True
    assert json.loads(store.read_text(encoding="utf-8"))["strategies"]["kingsbalfx"] is False
    assert toggles.is_enabled("kingsbalfx") is False

    toggles.set_enabled("kingsbalfx", True, persist_remote=False)
    assert toggles.is_enabled("kingsbalfx") is True


def test_clear_local_override_falls_back_to_env(toggles_env):
    toggles, store = toggles_env
    toggles.set_enabled("ict", False, persist_remote=False)
    assert toggles.is_enabled("ict") is False

    assert toggles.clear_local_override("ict") is True
    assert toggles.is_enabled("ict") is True


def test_unknown_strategy_is_rejected_on_write_but_fails_open_on_read(toggles_env):
    toggles, _ = toggles_env
    with pytest.raises(ValueError):
        toggles.set_enabled("does_not_exist", False, persist_remote=False)
    # Reading an unknown name must never block trading.
    assert toggles.is_enabled("does_not_exist") is True


def test_snapshot_covers_every_strategy(toggles_env):
    toggles, _ = toggles_env
    snap = toggles.snapshot()
    assert set(snap) == set(toggles.STRATEGY_NAMES)
    assert snap["ict"]["env_key"] == "ICT_ENABLED"
    assert snap["mirror"]["env_key"] == "MIRROR_TRADING_ENABLED"
    assert snap["ict"]["enabled"] is True


def test_remote_read_is_skipped_when_disabled(toggles_env, monkeypatch):
    """STRATEGY_TOGGLE_REMOTE=false must return no overrides (and touch no network)."""
    toggles, _ = toggles_env
    monkeypatch.setenv("STRATEGY_TOGGLE_REMOTE", "false")
    assert toggles._read_remote() == {}


def test_main_py_wires_every_strategy_toggle():
    """main.py must consult the toggle for all five strategies (plus mirror)."""
    source = open("main.py", encoding="utf-8").read()
    assert "from strategy.toggles import is_enabled as strategy_enabled" in source
    for name in ("ict", "kingsbalfx", "fallback3", "fallback4", "fallback5", "mirror"):
        assert 'strategy_enabled("%s")' % name in source, name
    # Disabling a strategy must degrade gracefully, not crash.
    assert "def _disabled_strategy_setup(" in source
    for helper in ("_run_fallback3", "_run_fallback4", "_run_fallback5"):
        assert "def %s(" % helper in source


def test_bot_api_exposes_strategy_endpoints():
    source = open("bot_api.py", encoding="utf-8").read()
    assert '@app.route("/admin/strategies", methods=["GET"])' in source
    assert '@app.route("/admin/strategies", methods=["POST"])' in source

