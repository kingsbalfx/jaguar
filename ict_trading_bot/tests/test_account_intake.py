"""
Tests for MT5 account intake (local OR submitted through the web)
=================================================================

Verifies that the bot accepts accounts from every source:
  * ``ACCOUNT_n_*`` env vars            (local, highest priority)
  * ``data/accounts_local.json``         (saved locally / POST /admin/accounts)
  * Supabase ``mt5_credentials``         (submitted through the web)
  * ``accounts.example.json``            (local config file)
and that the supervisor spawns accounts submitted *after* startup.
"""

import json

import pytest

from multi_account_runner import (
    account_signature,
    delete_local_account,
    describe_accounts,
    load_accounts,
    plan_supervision,
    save_local_account,
    set_local_account_enabled,
    web_accounts_enabled,
)


@pytest.fixture
def isolated_store(monkeypatch, tmp_path):
    store = tmp_path / "accounts_local.json"
    monkeypatch.setattr("multi_account_runner.LOCAL_STORE_PATH", store, raising=False)
    # No env/web accounts unless a test asks for them.
    for index in range(1, 6):
        for suffix in ("ENABLED", "LOGIN", "PASSWORD", "SERVER", "MT5_PATH", "API_PORT"):
            monkeypatch.delenv(f"ACCOUNT_{index}_{suffix}", raising=False)
    monkeypatch.delenv("MULTI_ACCOUNT_ACCOUNTS_JSON", raising=False)
    monkeypatch.setenv("MULTI_ACCOUNT_LOAD_CONFIG", "false")
    monkeypatch.setenv("MULTI_ACCOUNT_LOAD_LOCAL_STORE", "true")
    monkeypatch.setenv("MULTI_ACCOUNT_ACCEPT_WEB", "true")
    monkeypatch.setenv("MULTI_ACCOUNT_LOAD_SERVER", "false")
    monkeypatch.setenv("MULTI_ACCOUNT_REQUIRE_ACCOUNTS", "false")
    monkeypatch.setattr("multi_account_runner.fetch_all_mt5_credentials", lambda: [], raising=False)
    yield store


def test_local_store_accepts_submitted_account(isolated_store):
    save_local_account(
        {
            "login": "4485839",
            "password": "pw",
            "server": "Headway-Demo",
            "api_port": 8001,
            "bot_id": "bot_acc_2",
            "source": "web",
        }
    )
    accounts = load_accounts(strict=False)
    assert len(accounts) == 1
    account = accounts[0]
    assert account["login"] == "4485839"
    assert account["server"] == "Headway-Demo"
    assert account["api_port"] == 8001
    assert account["source"] == "web"


def test_local_store_upsert_updates_existing_login(isolated_store):
    save_local_account({"login": "111", "password": "old", "server": "A"})
    save_local_account({"login": "111", "password": "new", "server": "B"})
    payload = json.loads(isolated_store.read_text(encoding="utf-8"))
    rows = [row for row in payload["accounts"] if row["login"] == "111"]
    assert len(rows) == 1
    assert rows[0]["password"] == "new"
    assert rows[0]["server"] == "B"


def test_env_account_wins_over_local_store_and_web(isolated_store, monkeypatch):
    save_local_account({"login": "777", "password": "local-pw", "server": "Local"})
    monkeypatch.setattr(
        "multi_account_runner.fetch_all_mt5_credentials",
        lambda: [{"login": "777", "password": "web-pw", "server": "Web"}],
        raising=False,
    )
    monkeypatch.setenv("MULTI_ACCOUNT_LOAD_SERVER", "true")
    monkeypatch.setenv("ACCOUNT_1_ENABLED", "true")
    monkeypatch.setenv("ACCOUNT_1_LOGIN", "777")
    monkeypatch.setenv("ACCOUNT_1_PASSWORD", "env-pw")
    monkeypatch.setenv("ACCOUNT_1_SERVER", "Env")

    accounts = load_accounts(strict=False)
    assert len(accounts) == 1
    assert accounts[0]["password"] == "env-pw"
    assert accounts[0]["server"] == "Env"


def test_web_supabase_account_wins_over_local_store(isolated_store, monkeypatch):
    save_local_account({"login": "888", "password": "stale", "server": "Local"})
    monkeypatch.setattr(
        "multi_account_runner.fetch_all_mt5_credentials",
        lambda: [{"login": "888", "password": "fresh", "server": "Web", "user_id": "u1"}],
        raising=False,
    )
    monkeypatch.setenv("MULTI_ACCOUNT_LOAD_SERVER", "true")

    accounts = load_accounts(strict=False)
    assert len(accounts) == 1
    assert accounts[0]["password"] == "fresh"
    assert accounts[0]["source"] == "web"
    assert accounts[0]["user_id"] == "u1"


def test_web_disabled_ignores_supabase_rows(isolated_store, monkeypatch):
    monkeypatch.setenv("MULTI_ACCOUNT_LOAD_SERVER", "false")
    monkeypatch.setenv("MULTI_ACCOUNT_ACCEPT_WEB", "false")
    assert web_accounts_enabled() is False
    monkeypatch.setattr(
        "multi_account_runner.fetch_all_mt5_credentials",
        lambda: [{"login": "999", "password": "pw", "server": "Web"}],
        raising=False,
    )
    assert load_accounts(strict=False) == []



def test_disabled_and_deleted_accounts(isolated_store):
    save_local_account({"login": "222", "password": "pw", "server": "S"})
    assert set_local_account_enabled("222", False) is True
    assert load_accounts(strict=False) == []
    assert delete_local_account("222") is True
    assert load_accounts(strict=False) == []


def test_describe_accounts_masks_passwords(isolated_store):
    save_local_account({"login": "333", "password": "secret", "server": "S"})
    described = describe_accounts(load_accounts(strict=False))
    assert described[0]["has_password"] is True
    assert "password" not in described[0]


def test_account_signature_changes_when_new_account_arrives(isolated_store):
    first = account_signature(load_accounts(strict=False))
    save_local_account({"login": "444", "password": "pw", "server": "S"})
    second = account_signature(load_accounts(strict=False))
    assert first != second


def test_plan_supervision_spawns_new_and_optionally_removes():
    accounts = [
        {"login": "1", "password": "pw", "server": "S", "enabled": True},
        {"login": "2", "password": "pw", "server": "S", "enabled": True},
    ]
    plan = plan_supervision(["1"], accounts)
    assert [a["login"] for a in plan["to_spawn"]] == ["2"]
    assert plan["to_remove"] == []

    plan = plan_supervision(["1", "9"], accounts, auto_remove=True)
    assert [a["login"] for a in plan["to_spawn"]] == ["2"]
    assert plan["to_remove"] == ["9"]



def test_duplicate_api_ports_are_reassigned(monkeypatch):
    monkeypatch.setenv("MULTI_ACCOUNT_BASE_API_PORT", "8000")
    monkeypatch.setenv(
        "MULTI_ACCOUNT_ACCOUNTS_JSON",
        json.dumps(
            {
                "accounts": [
                    {"enabled": True, "login": "1", "api_port": 8000},
                    {"enabled": True, "login": "2", "api_port": 8000},
                    {"enabled": True, "login": "3", "api_port": 8003},
                ]
            }
        ),
    )
    monkeypatch.setenv("MULTI_ACCOUNT_LOAD_CONFIG", "false")
    monkeypatch.setenv("MULTI_ACCOUNT_LOAD_SERVER", "false")
    monkeypatch.setenv("MULTI_ACCOUNT_ACCEPT_WEB", "false")
    monkeypatch.setenv("MULTI_ACCOUNT_REQUIRE_ACCOUNTS", "false")
    monkeypatch.setattr("multi_account_runner.fetch_all_mt5_credentials", lambda: [], raising=False)

    accounts = load_accounts(strict=False)
    ports = [account["api_port"] for account in accounts]
    assert len(ports) == len(set(ports)), f"duplicate API ports: {ports}"
    assert 8003 in ports
    assert sorted(by_login := {a["login"]: a["api_port"] for a in accounts}) == ["1", "2", "3"]
    assert by_login["1"] == 8000
    # 8001/8002 are free, and 8003 is explicitly taken, so login 2 must not reuse 8000.
    assert by_login["2"] in (8001, 8002)


def test_admin_accounts_endpoints_registered():
    import bot_api

    rules = {rule.rule for rule in bot_api.app.url_map.iter_rules()}
    assert "/admin/accounts" in rules
    assert "/admin/accounts/<login>" in rules
    assert "/admin/accounts/sync" in rules


def test_admin_accounts_submit_saves_locally(isolated_store, monkeypatch):
    monkeypatch.setenv("BOT_API_TOKEN", "test-token")
    import bot_api

    client = bot_api.app.test_client()
    response = client.post(
        "/admin/accounts",
        json={
            "login": "555",
            "password": "pw",
            "server": "Headway-Demo",
            "api_port": 8005,
            "save_to_server": False,
        },
        headers={"x-bot-api-token": "test-token"},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["saved_locally"] is True
    assert body["account"]["password"] == "***"

    accounts = load_accounts(strict=False)
    assert len(accounts) == 1
    assert accounts[0]["login"] == "555"
    assert accounts[0]["api_port"] == 8005

    denied = client.post("/admin/accounts", json={"login": "x"})
    assert denied.status_code == 401


def test_admin_accounts_submit_validates_required_fields(isolated_store, monkeypatch):
    monkeypatch.setenv("BOT_API_TOKEN", "test-token")
    import bot_api

    client = bot_api.app.test_client()
    response = client.post(
        "/admin/accounts",
        json={"login": "1"},
        headers={"x-bot-api-token": "test-token"},
    )
    assert response.status_code == 400


def test_admin_accounts_list_and_disable(isolated_store, monkeypatch):
    monkeypatch.setenv("BOT_API_TOKEN", "test-token")
    import bot_api

    save_local_account({"login": "666", "password": "pw", "server": "S"})
    client = bot_api.app.test_client()
    headers = {"x-bot-api-token": "test-token"}

    listed = client.get("/admin/accounts", headers=headers)
    assert listed.status_code == 200
    assert listed.get_json()["count"] == 1
    assert listed.get_json()["accounts"][0]["has_password"] is True

    disabled = client.delete("/admin/accounts/666", headers=headers)
    assert disabled.status_code == 200
    assert disabled.get_json()["action"] == "disabled"
    assert load_accounts(strict=False) == []
