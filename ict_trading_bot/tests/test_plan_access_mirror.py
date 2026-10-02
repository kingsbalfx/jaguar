"""
Plan-aware signal delivery + mirror routing
===========================================

The website already gates *email / in-app* signal delivery by the subscriber's
plan (``jaguar-main/lib/signal-delivery.js``) but the MT5 mirror used to fan
every leader trade out to every account it could reach - including accounts
whose owner never bought bot/mirror access.

``utils/plan_access.py`` mirrors the web plan catalogue and these tests pin the
behaviour:

  * plan resolution (subscription > role > bot_tier > free) matches the web,
  * web-submitted accounts must resolve to a mirror-target plan,
  * local / owner accounts are never plan gated,
  * Supabase failures follow ``MIRROR_PLAN_FAIL_OPEN``,
  * a mirror signal that arrives by another route is still refused by the
    follower-side gate.

No network access: the Supabase client is faked.
"""

import json

import pytest

from utils import plan_access as plans


# ---------------------------------------------------------------------------
# Fake Supabase (select / eq / ilike / limit / execute)
# ---------------------------------------------------------------------------
class _Response:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.filters = []

    def select(self, columns):
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def ilike(self, column, value):
        self.filters.append((column, value))
        return self

    def limit(self, count):
        return self

    def execute(self):
        rows = [dict(row) for row in (self.client.rows.get(self.table) or [])]
        for column, value in self.filters:
            wanted = str(value or "").strip().lower()
            rows = [
                row
                for row in rows
                if str(row.get(column) or "").strip().lower() == wanted
            ]
        return _Response(rows)


class _Client:
    def __init__(self, rows=None):
        self.rows = rows or {}

    def table(self, name):
        return _Query(self, name)


def _seed(state, email, plan, *, user_id=None, role="user", status="active", ended_at=None, bot_tier=""):
    """Add a profile (+ subscription) row to the fake Supabase state."""
    state["profiles"].append(
        {
            "id": user_id or f"uuid-{email.split('@')[0]}",
            "email": email,
            "role": role,
            "bot_tier": bot_tier,
        }
    )
    if plan:
        state["subscriptions"].append(
            {"email": email, "plan": plan, "status": status, "ended_at": ended_at}
        )
    return user_id or f"uuid-{email.split('@')[0]}"


@pytest.fixture
def lookup(monkeypatch):
    """Fake Supabase state backing ``utils.plan_access`` lookups."""
    state = {"profiles": [], "subscriptions": [], "fail": False}

    def _client():
        if state["fail"]:
            raise RuntimeError("supabase unreachable")
        return _Client({"profiles": state["profiles"], "subscriptions": state["subscriptions"]})

    monkeypatch.setattr(plans, "_supabase_client", _client, raising=False)
    return state


@pytest.fixture
def plan_env(monkeypatch):
    """Neutral plan-gating environment (no stale cache, no leftover switches)."""
    for name in (
        "PLAN_ACCESS_ENABLED",
        "MIRROR_ENFORCE_PLAN_TARGETS",
        "MIRROR_TARGET_PLANS",
        "MIRROR_OWNER_LOGINS",
        "MIRROR_OWNER_EMAILS",
        "MIRROR_OWNER_LOCAL_LOGIN",
        "MULTI_ACCOUNT_CHILD",
        "MIRROR_PLAN_FAIL_OPEN",
        "BOT_SIGNAL_TARGET_PLANS",
        "BOT_USER_ID",
        "BOT_USER_EMAIL",
        "SIGNAL_USER_ID",
        "MT5_ACCOUNT_LOGIN",
        "MT5_ACCOUNT_EMAIL",
        "MT5_LOGIN",
        "BOT_OWNER_LOGIN",
        "BOT_OWNER_EMAIL",
        "SUPER_ADMIN_EMAIL",
        "NEXT_PUBLIC_ADMIN_EMAIL",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("PLAN_LOOKUP_TTL", "0")  # never serve a cached plan
    plans.clear_cache()
    yield plans
    plans.clear_cache()


# ---------------------------------------------------------------------------
# Plan resolution (must match resolvePlanFromSubscriptions on the website)
# ---------------------------------------------------------------------------
def test_resolve_plan_prefers_paid_subscription_over_role_and_tier(plan_env):
    resolved = plans.resolve_plan(
        role="premium",
        bot_tier="vip",
        subscriptions=[{"plan": "pro", "status": "active"}],
    )
    assert resolved["plan"] == "pro"
    assert resolved["source"] == "subscription"
    assert resolved["active"] is True


def test_resolve_plan_falls_back_to_role_then_tier_then_free(plan_env):
    assert plans.resolve_plan(role="premium")["source"] == "profile_role"
    assert plans.resolve_plan(role="premium")["plan"] == "premium"
    assert plans.resolve_plan(bot_tier="vip")["plan"] == "vip"
    assert plans.resolve_plan()["plan"] == "free"
    # A lapsed subscription must not upgrade the plan but must be reported.
    # Same rule as resolvePlanFromSubscriptions in lib/subscription-status.js:
    # "expired" means status=active with ended_at in the past.
    lapsed = plans.resolve_plan(
        role="premium",
        subscriptions=[{"plan": "lifetime", "status": "active", "ended_at": "2000-01-01T00:00:00Z"}],
    )
    assert lapsed["plan"] == "premium"
    assert lapsed["source"] == "profile_role"
    assert lapsed["expired"] is True
    # A subscription that was already cancelled/expired is simply ignored.
    cancelled = plans.resolve_plan(subscriptions=[{"plan": "pro", "status": "expired"}])
    assert cancelled["plan"] == "free"
    assert cancelled["expired"] is False


def test_ended_subscription_is_not_active(plan_env):
    assert plans.subscription_active({"plan": "pro", "status": "active", "ended_at": "2000-01-01T00:00:00Z"}) is False
    assert plans.subscription_active({"plan": "pro", "status": "active", "ended_at": "2999-01-01T00:00:00Z"}) is True
    assert plans.subscription_active({"plan": "pro", "status": "canceled"}) is False


def test_plan_aliases_match_the_web_catalogue(plan_env):
    assert plans.resolve_plan_id("academy-student") == "premium"
    assert plans.resolve_plan_id("PRO") == "pro"
    assert plans.resolve_plan_id("lifetime-academy") == "lifetime"
    assert plans.resolve_plan_id("nonsense-tier") == ""
    assert plans.plan_allows_mirror("pro") is True
    assert plans.plan_allows_mirror("vip") is False
    assert plans.plan_allows_signals("free") is True


def test_signal_and_mirror_target_plans_share_the_web_catalogue(plan_env, monkeypatch):
    # Defaults: every signal plan, mirror only on the tiers that include it.
    assert plans.signal_target_plans() == ["premium", "vip", "pro", "lifetime"]
    assert plans.mirror_target_plans() == ["pro", "lifetime"]

    # ``academy`` is canonicalised, duplicates/unknown ids are dropped.
    monkeypatch.setenv("BOT_SIGNAL_TARGET_PLANS", "academy,pro,pro,not-a-plan")
    assert plans.signal_target_plans() == ["premium", "pro"]
    # Mirror plans are filtered down to the tiers that include mirror trading.
    assert plans.mirror_target_plans() == ["pro"]

    # Every signal plan is email-only -> documented mirror default.
    monkeypatch.setenv("BOT_SIGNAL_TARGET_PLANS", "premium,vip")
    assert plans.mirror_target_plans() == ["pro", "lifetime"]

    monkeypatch.setenv("MIRROR_TARGET_PLANS", "vip, Pro ")
    assert plans.mirror_target_plans() == ["vip", "pro"]


# ---------------------------------------------------------------------------
# Supabase lookups
# ---------------------------------------------------------------------------
def test_plan_lookup_reads_profile_and_subscriptions(lookup, plan_env):
    user_id = _seed(lookup, "pro@example.com", "pro")
    resolved = plans.resolve_user_plan(user_id=user_id, email="pro@example.com")
    assert resolved["plan"] == "pro"
    assert resolved["source"] == "subscription"
    assert resolved["active"] is True


def test_plan_lookup_without_identity_is_unknown(plan_env):
    resolved = plans.resolve_user_plan()
    assert resolved["plan"] == plans.UNKNOWN_PLAN
    assert resolved["source"] == "no_identity"


def test_plan_lookup_failure_returns_unknown_sentinel(lookup, plan_env):
    lookup["fail"] = True
    resolved = plans.resolve_user_plan(user_id="uuid-x", email="boom@example.com")
    assert resolved["plan"] == plans.UNKNOWN_PLAN
    assert resolved["source"] == "lookup_failed"


def test_plan_lookup_is_cached_per_identity(lookup, plan_env, monkeypatch):
    _seed(lookup, "cached@example.com", "vip")
    monkeypatch.setenv("PLAN_LOOKUP_TTL", "300")
    plans.clear_cache()
    first = plans.resolve_user_plan(email="cached@example.com")
    lookup["profiles"].clear()  # a fresh lookup would no longer find the rows
    lookup["subscriptions"].clear()
    second = plans.resolve_user_plan(email="cached@example.com")
    assert first["plan"] == second["plan"] == "vip"
    plans.clear_cache()


# ---------------------------------------------------------------------------
# Mirror decisions (mirror_trading feeds these into peer discovery)
# ---------------------------------------------------------------------------
def test_mirror_decision_allows_local_accounts_and_owners(plan_env, monkeypatch):
    # Local account: no web owner on record -> never plan gated.
    local = plans.account_mirror_decision(login="11112222")
    assert local["allowed"] is True
    assert local["plan_source"] == "local_account"

    # Owner logins / emails bypass the gate.
    monkeypatch.setenv("MIRROR_OWNER_LOGINS", "5941466")
    monkeypatch.setenv("MIRROR_OWNER_EMAILS", "owner@example.com")
    owner = plans.account_mirror_decision(login="5941466", user_id="uuid-o", email="owner@example.com")
    assert owner["allowed"] is True
    assert owner["owner"] is True
    assert owner["plan"] == "owner"

    # The login this machine trades is the operator's own account.
    monkeypatch.setenv("MT5_ACCOUNT_LOGIN", "7777777")
    assert plans.account_mirror_decision(login="7777777")["owner"] is True


def test_mirror_decision_gates_web_accounts_by_plan(lookup, plan_env, monkeypatch):
    pro_id = _seed(lookup, "pro2@example.com", "pro")
    vip_id = _seed(lookup, "vip2@example.com", "vip")
    free_id = _seed(lookup, "free2@example.com", "free")

    pro = plans.account_mirror_decision(login="222", user_id=pro_id, email="pro2@example.com")
    assert pro["allowed"] is True
    assert pro["reason"] == ""
    assert pro["plan"] == "pro"

    free = plans.account_mirror_decision(login="444", user_id=free_id, email="free2@example.com")
    assert free["allowed"] is False
    assert free["reason"] == "plan_not_targeted"
    assert free["target_plans"] == ["pro", "lifetime"]

    vip = plans.account_mirror_decision(login="333", user_id=vip_id, email="vip2@example.com")
    assert vip["allowed"] is False
    assert vip["reason"] == "plan_not_targeted"

    # ...but a plan that IS targeted yet has no mirror feature is refused too.
    monkeypatch.setenv("MIRROR_TARGET_PLANS", "vip,lifetime")
    vip_targeted = plans.account_mirror_decision(login="333", user_id=vip_id, email="vip2@example.com")
    assert vip_targeted["allowed"] is False
    assert vip_targeted["reason"] == "plan_has_no_mirror_trading"


def test_mirror_decision_follows_fail_open_switch(lookup, plan_env, monkeypatch):
    lookup["fail"] = True
    monkeypatch.setenv("MIRROR_PLAN_FAIL_OPEN", "true")
    kept = plans.account_mirror_decision(login="555", user_id="uuid-y", email="y@example.com")
    assert kept["allowed"] is True
    assert kept["reason"] == "plan_lookup_failed_fail_open"

    plans.clear_cache()
    monkeypatch.setenv("MIRROR_PLAN_FAIL_OPEN", "false")
    dropped = plans.account_mirror_decision(login="556", user_id="uuid-z", email="z@example.com")
    assert dropped["allowed"] is False
    assert dropped["reason"] == "plan_lookup_failed"


def test_mirror_decision_respects_kill_switches(lookup, plan_env, monkeypatch):
    free_id = _seed(lookup, "free3@example.com", "free")
    monkeypatch.setenv("PLAN_ACCESS_ENABLED", "false")
    off = plans.account_mirror_decision(login="666", user_id=free_id, email="free3@example.com")
    assert off["allowed"] is True
    assert off["plan_source"] == "enforcement_off"
    assert plans.diagnostics()["mirror_enforced"] is False

    monkeypatch.setenv("PLAN_ACCESS_ENABLED", "true")
    monkeypatch.setenv("MIRROR_ENFORCE_PLAN_TARGETS", "false")
    relaxed = plans.account_mirror_decision(login="667", user_id=free_id, email="free3@example.com")
    assert relaxed["allowed"] is True
    assert relaxed["plan_source"] == "enforcement_off"


def test_signal_decision_matches_the_web_signal_gate(lookup, plan_env):
    _seed(lookup, "free4@example.com", "free")
    _seed(lookup, "vip4@example.com", "vip")
    assert plans.account_signal_decision(email="free4@example.com")["allowed"] is False
    vip = plans.account_signal_decision(email="vip4@example.com")
    assert vip["allowed"] is True
    assert vip["target_plans"] == ["premium", "vip", "pro", "lifetime"]


def test_main_signal_payload_uses_the_shared_plan_catalogue():
    """The bot must not keep a second copy of the plan ids for signal delivery."""
    main_source = open("main.py", encoding="utf-8").read()
    assert "from utils.plan_access import signal_target_plans" in main_source


def test_admin_role_bypasses_plan_targeting(lookup, plan_env):
    _seed(lookup, "boss@example.com", "", user_id="uuid-boss", role="admin")
    mirror_decision = plans.account_mirror_decision(login="999", user_id="uuid-boss", email="boss@example.com")
    assert mirror_decision["allowed"] is True
    assert mirror_decision["owner"] is True
    signal_decision = plans.account_signal_decision(email="boss@example.com")
    assert signal_decision["allowed"] is True


def test_local_login_is_owner_except_in_multi_account_children(plan_env, monkeypatch):
    monkeypatch.setenv("MT5_ACCOUNT_LOGIN", "555000")
    # Stand-alone / supervisor process: the machine trades the operator's account.
    assert plans.account_mirror_decision(login="555000")["owner"] is True
    assert plans.diagnostics()["local_login_owner"] is True

    # A child trades a delegated (usually web-submitted) account: gate it.
    monkeypatch.setenv("MULTI_ACCOUNT_CHILD", "true")
    assert plans.diagnostics()["local_login_owner"] is False
    assert plans.account_mirror_decision(login="555000")["owner"] is False

    # Explicit bypass / opt-out still win.
    monkeypatch.setenv("MIRROR_OWNER_LOCAL_LOGIN", "always")
    assert plans.account_mirror_decision(login="555000")["owner"] is True
    monkeypatch.delenv("MULTI_ACCOUNT_CHILD")
    monkeypatch.setenv("MIRROR_OWNER_LOCAL_LOGIN", "never")
    assert plans.account_mirror_decision(login="555000")["owner"] is False


# ---------------------------------------------------------------------------
# risk/mirror_trading: peer discovery + follower-side gate
# ---------------------------------------------------------------------------
@pytest.fixture
def isolated_store(monkeypatch, tmp_path):
    """Keep account stores / env empty so no real account leaks into a test."""
    import multi_account_runner as runner

    monkeypatch.setattr(runner, "LOCAL_STORE_PATH", tmp_path / "accounts_local.json", raising=False)
    monkeypatch.setattr(runner, "ACTIVE_REGISTRY_PATH", tmp_path / "active_accounts.json", raising=False)
    monkeypatch.setattr(runner, "DISABLED_STORE_PATH", tmp_path / "disabled_accounts.json", raising=False)
    for index in range(1, 6):
        for suffix in ("ENABLED", "LOGIN", "PASSWORD", "SERVER", "MT5_PATH", "API_PORT", "USER_ID", "EMAIL"):
            monkeypatch.delenv(f"ACCOUNT_{index}_{suffix}", raising=False)
    monkeypatch.delenv("MULTI_ACCOUNT_ACCOUNTS_JSON", raising=False)
    monkeypatch.setenv("MULTI_ACCOUNT_LOAD_CONFIG", "false")
    monkeypatch.setenv("MULTI_ACCOUNT_LOAD_LOCAL_STORE", "true")
    monkeypatch.setenv("MULTI_ACCOUNT_LOAD_SERVER", "false")
    monkeypatch.setenv("MULTI_ACCOUNT_REQUIRE_ACCOUNTS", "false")
    monkeypatch.setattr(runner, "fetch_all_mt5_credentials", lambda: [], raising=False)
    yield tmp_path


def _mirror_env(monkeypatch, supabase_client=None):
    """Deterministic mirror surroundings: every discovered peer looks reachable."""
    import risk.mirror_trading as mirror

    monkeypatch.setenv("MT5_ACCOUNT_LOGIN", "700000")
    monkeypatch.setenv("MIRROR_SUPABASE_DISCOVERY", "false")
    monkeypatch.setenv("MIRROR_LOGIN_OWNER_TTL", "0")
    monkeypatch.setattr(mirror, "_peer_reachable", lambda host, port, timeout=None: True, raising=False)
    monkeypatch.setattr(mirror, "_LOGIN_OWNER_CACHE", {"fetched_at": 0.0, "owners": {}}, raising=False)
    monkeypatch.setattr(mirror, "_LOCAL_IDENTITY_CACHE", {}, raising=False)
    monkeypatch.setattr(mirror, "_supabase_client", lambda: supabase_client, raising=False)
    return mirror



def test_mirror_peers_drop_unentitled_web_accounts(isolated_store, lookup, plan_env, monkeypatch):
    from multi_account_runner import write_active_accounts

    mirror = _mirror_env(monkeypatch)
    pro_id = _seed(lookup, "peer-pro@example.com", "pro")
    free_id = _seed(lookup, "peer-free@example.com", "free")
    write_active_accounts(
        [
            {"login": "700001", "api_port": 8101, "user_id": pro_id, "email": "peer-pro@example.com"},
            {"login": "700002", "api_port": 8102, "user_id": free_id, "email": "peer-free@example.com"},
            {"login": "700003", "api_port": 8103},
        ],
        host="127.0.0.1",
    )

    peers = {peer["login"]: peer for peer in mirror._get_peers()}
    assert sorted(peers) == ["700001", "700003"]  # the free-plan account was dropped
    assert peers["700001"]["plan"] == "pro"
    assert peers["700003"]["plan_source"] == "local_account"

    report = mirror.plan_gate_report()
    assert report["enforced"] is True
    assert report["target_plans"] == ["pro", "lifetime"]
    assert report["checked"] == 3
    assert report["allowed"] == 2
    skipped = {item["login"]: item for item in report["skipped"]}
    assert skipped["700002"]["reason"] == "plan_not_targeted"
    assert skipped["700002"]["email"] == "peer-free@example.com"


def test_mirror_peers_backfill_owner_from_credentials_table(isolated_store, lookup, plan_env, monkeypatch):
    from multi_account_runner import write_active_accounts

    credentials = _Client({"mt5_credentials": [{"login": "700005", "user_id": "", "email": "peer-free2@example.com"}]})
    mirror = _mirror_env(monkeypatch, supabase_client=credentials)
    _seed(lookup, "peer-free2@example.com", "free")
    write_active_accounts(
        [
            {"login": "700005", "api_port": 8105},
            {"login": "700006", "api_port": 8106},
        ],
        host="127.0.0.1",
    )

    peers = {peer["login"]: peer for peer in mirror._get_peers()}
    # 700005 has no registry owner, but mt5_credentials maps it to a free plan.
    assert sorted(peers) == ["700006"]
    skipped = {item["login"]: item for item in mirror.plan_gate_report()["skipped"]}
    assert skipped["700005"]["reason"] == "plan_not_targeted"


def test_mirror_peers_keep_everything_when_enforcement_is_off(isolated_store, lookup, plan_env, monkeypatch):
    from multi_account_runner import write_active_accounts

    mirror = _mirror_env(monkeypatch)
    monkeypatch.setenv("MIRROR_ENFORCE_PLAN_TARGETS", "false")
    free_id = _seed(lookup, "peer-free3@example.com", "free")
    write_active_accounts(
        [{"login": "700007", "api_port": 8107, "user_id": free_id, "email": "peer-free3@example.com"}],
        host="127.0.0.1",
    )

    assert [peer["login"] for peer in mirror._get_peers()] == ["700007"]
    assert mirror.plan_gate_report()["enforced"] is False



def test_should_execute_mirror_refuses_unentitled_child(lookup, plan_env, monkeypatch):
    import risk.mirror_trading as mirror

    free_id = _seed(lookup, "follower@example.com", "free")
    monkeypatch.setenv("MULTI_ACCOUNT_CHILD", "true")
    monkeypatch.setenv("MT5_ACCOUNT_LOGIN", "800001")
    monkeypatch.setenv("BOT_USER_ID", free_id)
    monkeypatch.setenv("BOT_USER_EMAIL", "follower@example.com")
    monkeypatch.setattr(mirror, "MIRROR_ENABLED", True, raising=False)
    monkeypatch.setattr(mirror, "MIRROR_AUTO_OPEN", True, raising=False)
    monkeypatch.setattr(mirror, "_toggle_enabled", lambda name: True, raising=False)
    monkeypatch.setattr(mirror, "_LOCAL_IDENTITY_CACHE", {}, raising=False)
    monkeypatch.setattr(mirror, "_last_mirror_time", {}, raising=False)

    signal = {
        "signal_id": "plan-gate-free",
        "symbol": "EURUSD",
        "direction": "BUY",
        "entry_price": 1.1000,
        "source_login": "800000",
    }
    assert mirror.should_execute_mirror(dict(signal)) == (False, "plan_not_entitled:plan_not_targeted")

    # The same child accepts the mirror once the owner holds a mirror plan.
    lookup["subscriptions"].append({"email": "follower@example.com", "plan": "pro", "status": "active"})
    plans.clear_cache()
    upgraded = dict(signal, signal_id="plan-gate-pro", symbol="GBPUSD")
    assert mirror.should_execute_mirror(upgraded) == (True, "ready_to_mirror")

