"""Tests for the guaranteed signal fan-out layer
=============================================

The bug this pins down: ``main._deliver_signal_to_website`` reports
``accepted=True`` for *any* ``2xx``, so a website response of
``{"emailed": 0, "notified": 0}`` used to be treated as a successful broadcast.
Nothing was persisted, nothing was queued for retry, and every registered
subscriber silently received nothing.

``utils.signal_dispatch`` now verifies the recipient acknowledgement before
reporting success and guarantees a retry (Supabase persist + durable outbox +
ops log) whenever users were not reached.
"""

import pytest


@pytest.fixture
def dispatch_env(monkeypatch):
    """Deterministic delivery knobs: verification on, plans strict off."""
    monkeypatch.setenv("BOT_SIGNAL_VERIFY_ACK", "true")
    monkeypatch.setenv("BOT_SIGNAL_MIN_RECIPIENTS", "1")
    monkeypatch.setenv("BOT_SIGNAL_STRICT_PLANS", "false")

    import utils.signal_dispatch as dispatch_module

    return dispatch_module


def _payload():
    return {"symbol": "EURUSD", "direction": "buy", "entryPrice": 1.1, "botId": "test"}


def _recorder(sink, key):
    def _record(*args, **kwargs):
        sink.append((key, args))
        return True

    return _record


# ---------------------------------------------------------------------------
# verify()
# ---------------------------------------------------------------------------
def test_verify_accepts_a_real_acknowledgement(dispatch_env):
    verdict = dispatch_env.verify(
        {"accepted": True, "response": {"emailed": 3, "notified": 0}}, ["premium"]
    )
    assert verdict["delivered"] is True
    assert verdict["emailed"] == 3
    assert verdict["reason"] is None


def test_verify_flags_zero_recipients(dispatch_env):
    verdict = dispatch_env.verify(
        {"accepted": True, "response": {"emailed": 0, "notified": 0}}, ["premium"]
    )
    assert verdict["delivered"] is False
    assert verdict["reason"] == "zero_recipients"


def test_verify_reports_a_missing_plan_audience(dispatch_env):
    verdict = dispatch_env.verify(
        {"accepted": True, "response": {"emailed": 2, "audienceByPlan": {"premium": 2}}},
        ["premium", "vip"],
    )
    # Default (non-strict) behaviour: delivered, but the gap is reported.
    assert verdict["delivered"] is True
    assert verdict["missing_plans"] == ["vip"]


def test_verify_can_be_made_strict_about_plans(dispatch_env, monkeypatch):
    monkeypatch.setenv("BOT_SIGNAL_STRICT_PLANS", "true")
    verdict = dispatch_env.verify(
        {"accepted": True, "response": {"emailed": 2, "audienceByPlan": {"premium": 2}}},
        ["premium", "vip"],
    )
    assert verdict["delivered"] is False
    assert verdict["reason"] == "missing_plan_audience"


def test_verify_restores_legacy_behaviour_when_disabled(dispatch_env, monkeypatch):
    monkeypatch.setenv("BOT_SIGNAL_VERIFY_ACK", "false")
    verdict = dispatch_env.verify(
        {"accepted": True, "response": {"emailed": 0, "notified": 0}}, ["premium"]
    )
    assert verdict["delivered"] is True


# ---------------------------------------------------------------------------
# dispatch()
# ---------------------------------------------------------------------------
def test_dispatch_is_a_no_op_when_users_were_reached(dispatch_env):
    calls = []
    result = dispatch_env.dispatch(
        _payload(),
        transport=lambda payload: {"accepted": True, "response": {"emailed": 4, "notified": 1}},
        expected_plans=["premium"],
        enqueue=_recorder(calls, "enqueue"),
        persist=_recorder(calls, "persist"),
        notify=_recorder(calls, "notify"),
    )
    assert result["delivered"] is True
    assert result["emailed"] == 4
    assert calls == []


def test_dispatch_enqueues_when_the_website_reached_nobody(dispatch_env):
    """The regression: 2xx + ``emailed=0`` must still queue a retry."""
    calls = []
    result = dispatch_env.dispatch(
        _payload(),
        transport=lambda payload: {"accepted": True, "response": {"emailed": 0, "notified": 0}},
        expected_plans=["premium", "vip"],
        enqueue=_recorder(calls, "enqueue"),
        persist=_recorder(calls, "persist"),
        notify=_recorder(calls, "notify"),
    )

    assert result["accepted"] is True
    assert result["delivered"] is False
    assert result["verified"] is False
    assert result["reason"] == "zero_recipients"
    assert [key for key, _ in calls] == ["persist", "enqueue", "notify"]
    # The outbox entry is keyed on the payload and carries the failure reason.
    enqueue_args = next(args for key, args in calls if key == "enqueue")
    assert enqueue_args[0] == _payload()
    assert enqueue_args[1] == "zero_recipients"


def test_dispatch_enqueues_when_the_transport_rejects(dispatch_env):
    calls = []
    result = dispatch_env.dispatch(
        _payload(),
        transport=lambda payload: {"accepted": False, "reason": "token_missing"},
        enqueue=_recorder(calls, "enqueue"),
        persist=_recorder(calls, "persist"),
        notify=_recorder(calls, "notify"),
    )
    assert result["delivered"] is False
    assert result["reason"] == "token_missing"
    assert [key for key, _ in calls] == ["persist", "enqueue", "notify"]


def test_dispatch_survives_a_transport_exception(dispatch_env):
    calls = []

    def _boom(payload):
        raise RuntimeError("network down")

    result = dispatch_env.dispatch(
        _payload(),
        transport=_boom,
        enqueue=_recorder(calls, "enqueue"),
        persist=_recorder(calls, "persist"),
        notify=_recorder(calls, "notify"),
    )
    assert result["delivered"] is False
    assert result["reason"].startswith("transport_exception")
    assert [key for key, _ in calls] == ["persist", "enqueue", "notify"]


def test_dispatch_never_raises_when_the_failure_hooks_are_broken(dispatch_env):
    def _boom(*args, **kwargs):
        raise RuntimeError("supabase down")

    result = dispatch_env.dispatch(
        _payload(),
        transport=lambda payload: {"accepted": True, "response": {"emailed": 0}},
        enqueue=_boom,
        persist=_boom,
        notify=_boom,
    )
    assert result["delivered"] is False


# ---------------------------------------------------------------------------
# outbox integration (main._verified_delivery_transport)
# ---------------------------------------------------------------------------
def test_outbox_retry_keeps_an_unverified_acceptance_queued(dispatch_env, monkeypatch):
    """``signal_outbox.flush`` must not drop a 2xx-with-no-recipients entry."""
    main = pytest.importorskip("main")

    monkeypatch.setattr(
        main,
        "_deliver_signal_to_website",
        lambda signal: {"accepted": True, "response": {"emailed": 0, "notified": 0}},
    )
    downgraded = main._verified_delivery_transport(_payload())
    assert downgraded["accepted"] is False
    assert downgraded["reason"] == "zero_recipients"

    monkeypatch.setattr(
        main,
        "_deliver_signal_to_website",
        lambda signal: {"accepted": True, "response": {"emailed": 2, "notified": 0}},
    )
    assert main._verified_delivery_transport(_payload())["accepted"] is True
