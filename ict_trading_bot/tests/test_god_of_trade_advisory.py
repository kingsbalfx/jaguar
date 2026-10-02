"""Tests for the God of Trade advisory, the signal outbox, and the Gemini
global macro read introduced to fix (a) signals not reaching subscribers and
(b) Gemini quota exhaustion on a 300-symbol scan.
"""

import pytest

from fundamentals import news_feed
from strategy import god_of_trade as got
from utils import signal_outbox


# ---------------------------------------------------------------------------
# God of Trade
# ---------------------------------------------------------------------------
def _stub_news(monkeypatch, direction="NO_TRADE", confidence=0.0):
    monkeypatch.setattr(
        news_feed,
        "get_news_brief",
        lambda symbol, force=False: {
            "symbol": symbol,
            "enabled": True,
            "has_news": bool(direction in ("BUY", "SELL")),
            "market_direction": direction,
            "confidence": confidence,
            "engine": "gemini-global+finnhub",
        },
    )


class _RuleEngine:
    def __init__(self, approved=True, reason="ok"):
        self._approved = approved
        self._reason = reason

    def validate_trade_against_rule(self, symbol, direction):
        return {"approved": self._approved, "reason": self._reason}


def _stub_environment(monkeypatch, tmp_path, session_open=True, approved=True, news="NO_TRADE"):
    monkeypatch.setenv("GOD_OF_TRADE_ENABLED", "true")
    monkeypatch.setenv("GOD_OF_TRADE_MODE", "advisory")
    monkeypatch.setenv("GOD_OF_TRADE_STATE_PATH", str(tmp_path / "got.json"))
    monkeypatch.setattr("risk.trade_scheduler.is_trading_allowed", lambda minutes=None: session_open)
    monkeypatch.setattr("risk.trade_scheduler.current_session_name", lambda minutes=None: "session_1")
    monkeypatch.setattr("macro_rule_engine.get_rule_engine", lambda: _RuleEngine(approved=approved))
    _stub_news(monkeypatch, news)


def test_god_of_trade_allows_a_clean_setup(monkeypatch, tmp_path):
    _stub_environment(monkeypatch, tmp_path)
    verdict = got.inspect(
        {
            "symbol": "EURUSD",
            "direction": "BUY",
            "strategy": "kingsbalfx",
            "entry": 1.1000,
            "sl": 1.0950,
            "tp": 1.1150,
            "positions": [],
        }
    )
    assert verdict["verdict"] == "ALLOW"
    assert verdict["score"] == 100
    assert verdict["mode"] == "advisory"


def test_god_of_trade_vetoes_a_loss_streak(monkeypatch, tmp_path):
    _stub_environment(monkeypatch, tmp_path)
    for _ in range(3):
        got.register_trade_outcome("EURUSD", "kingsbalfx", won=False)
    verdict = got.inspect({"symbol": "EURUSD", "direction": "BUY", "entry": 1.1, "sl": 1.09, "tp": 1.12})
    assert verdict["verdict"] == "VETO"
    assert any(c["name"] == "loss_streak" and c["status"] == "fail" for c in verdict["checks"])
    # advisory mode must never block
    assert got.should_block(verdict) is False


def test_god_of_trade_vetoes_poor_risk_reward(monkeypatch, tmp_path):
    _stub_environment(monkeypatch, tmp_path)
    verdict = got.inspect(
        {"symbol": "GBPUSD", "direction": "SELL", "entry": 1.3000, "sl": 1.3010, "tp": 1.3004}
    )
    assert verdict["verdict"] == "VETO"
    assert any(c["name"] == "risk_reward" and c["status"] == "fail" for c in verdict["checks"])


def test_god_of_trade_blocks_only_in_enforce_mode(monkeypatch, tmp_path):
    _stub_environment(monkeypatch, tmp_path, session_open=False)
    monkeypatch.setenv("GOD_OF_TRADE_MODE", "enforce")
    verdict = got.inspect({"symbol": "USDJPY", "direction": "BUY", "entry": 150.0, "sl": 149.0, "tp": 153.0})
    assert verdict["verdict"] == "VETO"
    assert got.should_block(verdict) is True


def test_god_of_trade_disabled_always_allows(monkeypatch, tmp_path):
    _stub_environment(monkeypatch, tmp_path)
    monkeypatch.setenv("GOD_OF_TRADE_ENABLED", "false")
    verdict = got.inspect({"symbol": "AUDUSD", "direction": "BUY"})
    assert verdict["enabled"] is False
    assert verdict["verdict"] == "ALLOW"
    assert got.should_block(verdict) is False


def test_god_of_trade_news_conflict_is_veto(monkeypatch, tmp_path):
    _stub_environment(monkeypatch, tmp_path, news="SELL")
    verdict = got.inspect(
        {"symbol": "EURUSD", "direction": "BUY", "entry": 1.1, "sl": 1.095, "tp": 1.115}
    )
    assert verdict["verdict"] == "VETO"
    assert any(c["name"] == "news" and c["status"] == "fail" for c in verdict["checks"])


# ---------------------------------------------------------------------------
# Signal outbox
# ---------------------------------------------------------------------------
def _payload():
    return {
        "symbol": "EURUSD",
        "direction": "BUY",
        "entryPrice": 1.1,
        "stopLoss": 1.09,
        "botId": "bot-1",
    }


def test_signal_outbox_queues_and_dedupes(monkeypatch, tmp_path):
    monkeypatch.setenv("SIGNAL_OUTBOX_PATH", str(tmp_path / "outbox.jsonl"))
    monkeypatch.setenv("SIGNAL_OUTBOX_ENABLED", "true")
    assert signal_outbox.enqueue(_payload(), "401") is True
    assert signal_outbox.enqueue(_payload(), "401") is False  # duplicate
    pending = signal_outbox.pending()
    assert len(pending) == 1
    assert pending[0]["attempts"] == 0


def test_signal_outbox_retries_then_drops_when_delivered(monkeypatch, tmp_path):
    monkeypatch.setenv("SIGNAL_OUTBOX_PATH", str(tmp_path / "outbox.jsonl"))
    monkeypatch.setenv("SIGNAL_OUTBOX_ENABLED", "true")
    signal_outbox.enqueue(_payload(), "401")

    failing = signal_outbox.flush(lambda payload: {"accepted": False, "reason": "401"})
    assert failing["remaining"] == 1
    assert failing["delivered"] == 0
    assert signal_outbox.pending()[0]["attempts"] == 1

    delivered = signal_outbox.flush(lambda payload: {"accepted": True})
    assert delivered["delivered"] == 1
    assert delivered["remaining"] == 0
    assert signal_outbox.pending() == []


def test_signal_outbox_stats(monkeypatch, tmp_path):
    monkeypatch.setenv("SIGNAL_OUTBOX_PATH", str(tmp_path / "outbox.jsonl"))
    monkeypatch.setenv("SIGNAL_OUTBOX_ENABLED", "true")
    signal_outbox.enqueue(_payload(), "network")
    assert signal_outbox.stats()["pending"] == 1


# ---------------------------------------------------------------------------
# Finnhub + Gemini global macro read
# ---------------------------------------------------------------------------
def test_symbol_direction_from_currency_bias_map():
    macro = {"currencies": {"EUR": "BUY", "USD": "SELL", "JPY": "NEUTRAL"}}
    direction, confidence, _note = news_feed.symbol_direction_from_macro("EURUSD", macro)
    assert direction == "BUY"
    assert confidence > 0

    direction, _conf, _note = news_feed.symbol_direction_from_macro("USDJPY", macro)
    assert direction == "SELL"

    direction, _conf, _note = news_feed.symbol_direction_from_macro("EURJPY", macro)
    assert direction == "BUY"


def test_symbol_direction_for_metals_from_bias_map():
    macro = {"currencies": {"XAU": "BUY"}}
    direction, _conf, note = news_feed.symbol_direction_from_macro("XAUUSD", macro)
    assert direction == "BUY"
    assert "XAU" in note


def test_global_macro_read_is_single_call_and_tracks_coverage(monkeypatch):
    calls = {"count": 0}

    def _fake_post(prompt):
        calls["count"] += 1
        return {
            "currencies": {"EUR": "BUY", "USD": "SELL"},
            "overall": "BUY",
            "confidence": 0.7,
            "key_sentiment": "bullish",
        }

    monkeypatch.setattr(news_feed, "_post_gemini", _fake_post)
    monkeypatch.setattr(news_feed, "_MACRO_AI_CACHE", {"fetched_at": 0.0, "payload": {}})
    monkeypatch.setattr(
        news_feed,
        "global_news",
        lambda force=False: [
            {"headline": "Euro rallies as ECB holds rates", "summary": "EUR up"},
            {"headline": "Dollar slips after dovish Fed", "summary": "USD down"},
        ],
    )
    monkeypatch.setenv("NEWS_FEED_AI_TTL", "3600")

    first = news_feed.global_macro_read(force=True)
    second = news_feed.global_macro_read()  # served from cache
    assert calls["count"] == 1
    assert first["engine"] == "gemini-global+finnhub"
    assert first["fetched_total"] == 2
    assert first["sent_to_llm"] == 2
    assert second["engine"] == "gemini-global+finnhub"


def test_get_news_brief_global_mode_uses_shared_read(monkeypatch):
    monkeypatch.setenv("NEWS_FEED_AI_MODE", "global")
    monkeypatch.setattr(
        news_feed,
        "fetch_headlines",
        lambda symbol, max_items=None, force=False: [
            {"headline": "Euro rallies", "summary": "EUR up", "url": "", "source": "test"}
        ],
    )
    monkeypatch.setattr(
        news_feed,
        "global_macro_read",
        lambda force=False: {
            "currencies": {"EUR": "BUY", "USD": "SELL"},
            "engine": "gemini-global+finnhub",
            "fetched_total": 10,
            "sent_to_llm": 6,
            "truncated": 4,
            "key_sentiment": "bullish",
            "executive_breakdown": "",
        },
    )
    # Per-symbol Gemini must NOT be called in global mode.
    monkeypatch.setattr(
        news_feed,
        "gemini_breakdown",
        lambda symbol, headlines: pytest.fail("per-symbol call in global mode"),
    )
    monkeypatch.setattr(news_feed, "_CACHE", {})
    brief = news_feed.get_news_brief("EURUSD", force=True)
    assert brief["engine"] == "gemini-global+finnhub"
    assert brief["market_direction"] == "BUY"
    assert brief["ai_mode"] == "global"
    assert brief["ai_coverage"]["sent_to_llm"] == 6
