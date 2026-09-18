"""
Tests for account synchronisation (local <-> Supabase) and mirror peer liveness
==============================================================================

Covers the requirement that an account submitted EITHER locally (env / config /
local store / admin API) OR through the web (Supabase) is:
  * accepted by the bot,
  * pushed UP to Supabase so the web + other machines see it,
  * reflected in mirror trading (which must only target accounts that are
    actually running - no more "Connection refused" to dead logins).
"""

import json

import pytest

from multi_account_runner import (
    load_accounts,
    read_active_accounts,
    sync_accounts_to_server,
    write_active_accounts,
)


@pytest.fixture
def isolated_store(monkeypatch, tmp_path):
    monkeypatch.setattr("multi_account_runner.LOCAL_STORE_PATH", tmp_path / "accounts_local.json", raising=False)
    monkeypatch.setattr("multi_account_runner.ACTIVE_REGISTRY_PATH", tmp_path / "active_accounts.json", raising=False)
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
    yield tmp_path


class _StubTable:
    def __init__(self, sink, fail_logins=()):
        self.sink = sink
        self.fail_logins = set(fail_logins)
        self._record = None

    def upsert(self, record, on_conflict=None):
        self._record = record
        return self

    def execute(self):
        login = str((self._record or {}).get("login"))
        if login in self.fail_logins:
            raise RuntimeError("boom")
        self.sink.append(dict(self._record or {}))
        return type("R", (), {"data": [self._record]})()


class _StubClient:
    def __init__(self, sink, fail_logins=()):
        self.sink = sink
        self.fail_logins = fail_logins

    def table(self, name):
        return _StubTable(self.sink, self.fail_logins)


def _stub_supabase_client(monkeypatch, client):
    import sys
    import types

    fake_supabase = types.ModuleType("supabase")
    fake_supabase.create_client = lambda url, key: client
    monkeypatch.setitem(sys.modules, "supabase", fake_supabase)

    from config import supabase_credentials

    monkeypatch.setattr(
        supabase_credentials,
        "resolve_supabase_credentials",
        lambda force=False: {
            "url": "https://demo.supabase.co",
            "key": "k" * 40,
            "service_key": "k" * 40,
            "usable": True,
            "source": {},
            "ignored": [],
        },
    )
    monkeypatch.setattr(supabase_credentials, "apply_supabase_env", lambda force=False, quiet=False: True)


def _stub_supabase(monkeypatch, sink, fail_logins=()):
    _stub_supabase_client(monkeypatch, _StubClient(sink, fail_logins))


class _NoConstraintQuery:
    """Fake Supabase query builder for a table WITHOUT a unique(login) index."""

    def __init__(self, client):
        self.client = client
        self.op = None
        self.payload = None
        self.login = None

    def upsert(self, record, on_conflict=None):
        self.op, self.payload = "upsert", record
        return self

    def insert(self, record):
        self.op, self.payload = "insert", record
        return self

    def update(self, record):
        self.op, self.payload = "update", record
        return self

    def select(self, columns):
        self.op = "select"
        return self

    def eq(self, column, value):
        self.login = value
        return self

    def limit(self, count):
        return self

    def execute(self):
        client = self.client
        if self.op == "upsert":
            # Exactly what Supabase returns when unique(login) is missing.
            raise RuntimeError(
                "{'message': 'there is no unique or exclusion constraint matching the "
                "ON CONFLICT specification', 'code': '42P10', 'hint': None, 'details': None}"
            )
        if self.op == "select":
            return type("R", (), {"data": [{"login": login} for login in client.rows if login == self.login]})()
        if self.op == "update":
            client.writes.append(("update", self.login, dict(self.payload)))
            client.rows[self.login] = dict(self.payload)
            return type("R", (), {"data": [self.payload]})()
        client.writes.append(("insert", self.payload.get("login"), dict(self.payload)))
        if client.reject_columns and (set(self.payload) & client.reject_columns):
            raise RuntimeError("column does not exist")
        client.rows[self.payload["login"]] = dict(self.payload)
        return type("R", (), {"data": [self.payload]})()


class _NoConstraintClient:
    def __init__(self, existing_logins=(), reject_columns=()):
        self.rows = {login: {"login": login} for login in existing_logins}
        self.writes = []
        self.reject_columns = set(reject_columns)

    def table(self, name):
        return _NoConstraintQuery(self)


def test_disabled_account_leaves_rotation_and_reappears_after_resubmit(isolated_store, monkeypatch):
    """An account with repeatedly rejected MT5 credentials must stop being spawned."""
    from multi_account_runner import (
        disable_account,
        disabled_accounts,
        enable_account,
        save_local_account,
    )

    monkeypatch.setattr("multi_account_runner.DISABLED_STORE_PATH", isolated_store / "disabled_accounts.json", raising=False)
    monkeypatch.setenv("ACCOUNT_1_ENABLED", "true")
    monkeypatch.setenv("ACCOUNT_1_LOGIN", "555")
    monkeypatch.setenv("ACCOUNT_1_PASSWORD", "pw")
    monkeypatch.setenv("ACCOUNT_1_SERVER", "Headway-Demo")

    assert [a["login"] for a in load_accounts(strict=False)] == ["555"]

    assert disable_account("555", "mt5_authorization_failed") is True
    assert disabled_accounts()["555"]["reason"] == "mt5_authorization_failed"
    assert load_accounts(strict=False) == []

    # Re-submitting the account through the admin API re-enables it.
    save_local_account({"login": "555", "password": "fixed", "server": "Headway-Demo"})
    assert disabled_accounts() == {}
    logins = sorted(a["login"] for a in load_accounts(strict=False))
    assert logins == ["555"]
    assert enable_account("555") is False  # nothing left to enable


def test_sync_falls_back_when_table_has_no_unique_login(isolated_store, monkeypatch):
    client = _NoConstraintClient(existing_logins=["5941466"])
    _stub_supabase_client(monkeypatch, client)

    result = sync_accounts_to_server(
        [
            {"login": "5941466", "password": "pw", "server": "Headway-Demo"},
            {"login": "5941472", "password": "pw", "server": "Headway-Demo"},
        ]
    )
    assert sorted(result["synced"]) == ["5941466", "5941472"]
    assert result["failed"] == []
    assert result["methods"] == {"5941466": "updated", "5941472": "inserted"}
    assert [write[0] for write in client.writes] == ["update", "insert"]


def test_sync_retries_insert_with_minimal_columns(isolated_store, monkeypatch):
    client = _NoConstraintClient(reject_columns={"user_id", "email"})
    _stub_supabase_client(monkeypatch, client)

    result = sync_accounts_to_server(
        [{"login": "5941472", "password": "pw", "server": "S", "user_id": "u", "email": "a@b.c"}]
    )
    assert result["synced"] == ["5941472"]
    assert result["methods"]["5941472"] == "inserted_minimal"


def test_sync_uses_plain_upsert_when_constraint_exists(isolated_store, monkeypatch):
    sink = []
    _stub_supabase(monkeypatch, sink)
    result = sync_accounts_to_server([{"login": "5941466", "password": "pw", "server": "S"}])
    assert result["methods"] == {"5941466": "upsert"}


def test_local_accounts_are_synced_up_to_supabase(isolated_store, monkeypatch):
    sink = []
    _stub_supabase(monkeypatch, sink)

    accounts = [
        {"login": "5941451", "password": "pw1", "server": "Headway-Demo", "enabled": True},
        {"login": "5941466", "password": "pw2", "server": "Headway-Demo", "enabled": True, "user_id": "u-1", "email": "a@b.c"},
        {"login": "9999999", "server": "Headway-Demo"},  # no password -> skipped
    ]
    result = sync_accounts_to_server(accounts)
    assert sorted(result["synced"]) == ["5941451", "5941466"]
    assert result["skipped"] == ["9999999"]
    assert result["failed"] == []

    rows = {row["login"]: row for row in sink}
    assert rows["5941451"]["password"] == "pw1"
    assert rows["5941451"]["server"] == "Headway-Demo"
    assert rows["5941451"]["active"] is True
    assert rows["5941466"]["user_id"] == "u-1"
    assert rows["5941466"]["email"] == "a@b.c"


def test_sync_reports_per_account_failures(isolated_store, monkeypatch):
    sink = []
    _stub_supabase(monkeypatch, sink, fail_logins={"5941472"})
    result = sync_accounts_to_server(
        [
            {"login": "5941466", "password": "pw", "server": "S"},
            {"login": "5941472", "password": "pw", "server": "S"},
        ]
    )
    assert result["synced"] == ["5941466"]
    assert result["failed"] == ["5941472"]


def test_sync_without_supabase_reports_reason(isolated_store, monkeypatch):
    from config import supabase_credentials

    monkeypatch.setattr(
        supabase_credentials,
        "resolve_supabase_credentials",
        lambda force=False: {"url": "", "key": "", "service_key": "", "usable": False, "source": {}, "ignored": []},
    )
    monkeypatch.setattr(supabase_credentials, "apply_supabase_env", lambda force=False, quiet=False: False)
    result = sync_accounts_to_server([{"login": "1", "password": "pw", "server": "S"}])
    assert result["synced"] == []
    assert result["reason"] == "supabase_unavailable"


def test_active_registry_roundtrip(isolated_store):
    write_active_accounts(
        [
            {"login": "5941466", "api_port": 8001, "bot_id": "bot_acc_2", "server": "Headway-Demo"},
            {"login": "5941472", "api_port": 8002},
            {"login": "", "api_port": 8009},
        ],
        host="127.0.0.1",
    )
    registry = read_active_accounts(ttl_seconds=600)
    logins = sorted(row["login"] for row in registry["accounts"])
    assert logins == ["5941466", "5941472"]
    assert registry["stale"] is False



def test_mirror_peers_only_include_live_accounts(isolated_store, monkeypatch):
    monkeypatch.setenv("MIRROR_TRADING_ENABLED", "true")
    monkeypatch.setenv("MIRROR_EXCLUDE_SAME", "true")
    monkeypatch.setenv("MT5_ACCOUNT_LOGIN", "5941466")
    monkeypatch.setenv("MIRROR_SUPABASE_DISCOVERY", "false")
    # Strict mode: only accounts in the live registry may be targeted.
    monkeypatch.setenv("MIRROR_ACCEPT_ANY_ACCOUNT", "false")
    # Reachability probing is exercised separately (test_peer_probe_*).
    monkeypatch.setenv("MIRROR_PEER_PROBE", "false")

    write_active_accounts(
        [
            {"login": "5941466", "api_port": 8001},
            {"login": "5941472", "api_port": 8002},
        ],
        host="127.0.0.1",
    )

    import risk.mirror_trading as mirror

    monkeypatch.setattr(mirror, "_supabase_client", lambda: None, raising=False)
    peers = mirror._get_peers()
    logins = sorted(peer["login"] for peer in peers)
    # Self is excluded and the dead legacy logins are gone.
    assert logins == ["5941472"]
    assert all(peer["api_port"] and peer["api_host"] for peer in peers)


def test_mirror_peers_fall_back_to_local_accounts_without_registry(isolated_store, monkeypatch):
    monkeypatch.setenv("MIRROR_TRADING_ENABLED", "true")
    monkeypatch.setenv("MIRROR_SUPABASE_DISCOVERY", "false")
    monkeypatch.setenv("MIRROR_PEER_PROBE", "false")
    monkeypatch.setenv("MT5_ACCOUNT_LOGIN", "111")
    monkeypatch.setenv(
        "MULTI_ACCOUNT_ACCOUNTS_JSON",
        json.dumps({"accounts": [
            {"enabled": True, "login": "111", "api_port": 8000},
            {"enabled": True, "login": "222", "api_port": 8001},
        ]}),
    )

    import risk.mirror_trading as mirror

    monkeypatch.setattr(mirror, "_supabase_client", lambda: None, raising=False)
    peers = mirror._get_peers()
    assert sorted(peer["login"] for peer in peers) == ["222"]


def test_mirror_accepts_any_inserted_account(isolated_store, monkeypatch):
    """MIRROR_ACCEPT_ANY_ACCOUNT: an account inserted anywhere becomes a mirror peer.

    The live registry only knows about login 222, but 333 was inserted locally -
    it must still be a mirror target (this is the "accept any account" behaviour).
    """
    monkeypatch.setenv("MIRROR_TRADING_ENABLED", "true")
    monkeypatch.setenv("MIRROR_EXCLUDE_SAME", "true")
    monkeypatch.setenv("MIRROR_SUPABASE_DISCOVERY", "false")
    monkeypatch.setenv("MIRROR_PEER_PROBE", "false")
    monkeypatch.setenv("MIRROR_ACCEPT_ANY_ACCOUNT", "true")
    monkeypatch.setenv("MT5_ACCOUNT_LOGIN", "111")
    monkeypatch.setenv(
        "MULTI_ACCOUNT_ACCOUNTS_JSON",
        json.dumps({"accounts": [
            {"enabled": True, "login": "222", "api_port": 8001},
            {"enabled": True, "login": "333", "api_port": 8002},
        ]}),
    )
    write_active_accounts([{"login": "222", "api_port": 8001}], host="127.0.0.1")

    import risk.mirror_trading as mirror

    monkeypatch.setattr(mirror, "_supabase_client", lambda: None, raising=False)
    logins = sorted(peer["login"] for peer in mirror._get_peers())
    assert logins == ["222", "333"]


def test_load_accounts_accepts_env_web_and_local_store_together(isolated_store, monkeypatch):
    monkeypatch.setenv("ACCOUNT_1_ENABLED", "true")
    monkeypatch.setenv("ACCOUNT_1_LOGIN", "111")
    monkeypatch.setenv("ACCOUNT_1_PASSWORD", "env-pw")
    monkeypatch.setenv("ACCOUNT_1_SERVER", "EnvServer")

    from multi_account_runner import save_local_account

    save_local_account({"login": "222", "password": "pw", "server": "LocalServer"})

    monkeypatch.setenv("MULTI_ACCOUNT_LOAD_SERVER", "true")
    monkeypatch.setattr(
        "multi_account_runner.fetch_all_mt5_credentials",
        lambda: [{"login": "333", "password": "pw", "server": "WebServer"}],
        raising=False,
    )

    accounts = {str(a["login"]): a for a in load_accounts(strict=False)}
    assert sorted(accounts) == ["111", "222", "333"]
    assert accounts["333"]["source"] == "web"
    assert accounts["111"]["password"] == "env-pw"


def test_mirror_peers_drop_unreachable_apis(isolated_store, monkeypatch):
    """A peer whose API is not listening must never be targeted by the mirror."""
    import socket

    import risk.mirror_trading as mirror

    # Reserve a port and close it so nothing is listening there.
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    dead_port = probe.getsockname()[1]
    probe.close()

    monkeypatch.setenv("MIRROR_PEER_PROBE", "true")
    monkeypatch.setenv("MIRROR_PEER_PROBE_TTL_SECONDS", "0")
    mirror._PEER_PROBE_CACHE.clear()

    assert mirror._peer_reachable("127.0.0.1", dead_port) is False

    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    live_port = server.getsockname()[1]
    mirror._PEER_PROBE_CACHE.clear()
    try:
        assert mirror._peer_reachable("127.0.0.1", live_port) is True
    finally:
        server.close()

    monkeypatch.setenv("MT5_ACCOUNT_LOGIN", "111")
    monkeypatch.setenv("MIRROR_EXCLUDE_SAME", "true")
    monkeypatch.setenv("MIRROR_SUPABASE_DISCOVERY", "false")
    # Both peers point at ports nothing is listening on -> no mirror targets.
    write_active_accounts(
        [{"login": "111", "api_port": dead_port}, {"login": "222", "api_port": dead_port}],
        host="127.0.0.1",
    )
    mirror._PEER_PROBE_CACHE.clear()
    assert [peer["login"] for peer in mirror._get_peers()] == []


def test_supervisor_wires_sync_registry_and_auth_failure(isolated_store):
    """main.py must sync to the server, publish live accounts and handle auth failures."""
    main_source = open("main.py", encoding="utf-8").read()
    assert "sync_accounts_to_server" in main_source
    assert "write_active_accounts" in main_source
    assert "MULTI_ACCOUNT_SYNC_TO_SERVER" in main_source
    assert "auth_failures" in main_source
    assert "sys.exit(2)" in main_source
