"""
Regression tests for the reported production errors
===================================================

Covers:
  1. Supabase credentials must never resolve to a placeholder
     (the ``SUPABASE_URL=...`` line in .env caused "Invalid URL" and
     ``supabase_unavailable`` macro-rule blocks).
  2. The MT5 symbol universe registry (bot only trades broker symbols).
  3. Fallback 5 symbol gate driven by the MT5 universe instead of a hard-coded
     four-symbol allowlist (which produced ``symbol_not_allowed`` for every pair).
  4. The unified Finnhub + Gemini news feed fails open and can optionally block.
"""

import pytest

from config import mt5_universe, supabase_credentials
from fundamentals import news_feed
from strategy.fallback_strategy5 import config as fb5_config
from strategy.fallback_strategy5 import symbol_gate


# ---------------------------------------------------------------------------
# 1. Supabase credential resolution
# ---------------------------------------------------------------------------
def test_placeholder_values_are_rejected():
    assert supabase_credentials.is_valid_supabase_url("...") is False
    assert supabase_credentials.is_valid_supabase_url("") is False
    assert supabase_credentials.is_valid_supabase_url("http://x.supabase.co") is False
    assert supabase_credentials.is_valid_supabase_key("...") is False
    assert supabase_credentials.is_valid_supabase_key("short") is False

    assert supabase_credentials.is_valid_supabase_url("https://demo.supabase.co") is True
    assert supabase_credentials.is_valid_supabase_key("k" * 40) is True


def test_env_file_has_no_placeholder_supabase_values():
    """The duplicate placeholder that broke production must not come back."""
    parsed = supabase_credentials._parse_env_file(supabase_credentials.ENV_FILE)
    if not parsed:
        pytest.skip(".env not present in this checkout")
    assert "SUPABASE_URL" in parsed
    assert parsed["SUPABASE_URL"].startswith("https://")


def test_resolver_prefers_valid_value_over_placeholders(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "...")
    monkeypatch.setenv("SUPABASE_KEY", "...")
    resolved = supabase_credentials.resolve_supabase_credentials(force=True)
    if not resolved["usable"]:
        pytest.skip("no valid credentials available in this environment")
    assert resolved["url"].startswith("https://")
    assert resolved["url"] != "..."


def test_apply_env_purges_placeholder(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "...")
    monkeypatch.setenv("SUPABASE_KEY", "...")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "...")
    supabase_credentials.resolve_supabase_credentials(force=True)
    removed = supabase_credentials.purge_placeholder_env()
    assert "SUPABASE_URL" in removed
    assert "SUPABASE_SERVICE_KEY" in removed


# ---------------------------------------------------------------------------
# 2. MT5 symbol universe
# ---------------------------------------------------------------------------
@pytest.fixture
def clean_universe(monkeypatch, tmp_path):
    monkeypatch.setattr(mt5_universe, "STORE_FILE", tmp_path / "universe.json", raising=False)
    mt5_universe._loaded = True
    mt5_universe._symbols = []
    mt5_universe._index = set()
    mt5_universe._meta = {"source": "unknown", "updated_at": None, "account": None, "count": 0}
    yield mt5_universe


def test_universe_sync_and_availability(clean_universe):
    snapshot = clean_universe.sync_universe(
        ["EURUSD", "AUDCAD", "XAUUSD.a", "AAPL"], source="mt5", persist=False
    )
    assert snapshot["count"] == 4
    assert clean_universe.is_available("AUDCAD") is True
    assert clean_universe.is_available("XAUUSD") is True          # alias aware
    assert clean_universe.is_available("ZZZXXX") is False
    assert clean_universe.resolve_tradable("XAUUSD") == "XAUUSD.a"


def test_universe_keeps_previous_on_empty_sync(clean_universe):
    clean_universe.sync_universe(["EURUSD", "GBPUSD"], source="mt5", persist=False)
    clean_universe.sync_universe([], source="mt5", persist=False)
    assert clean_universe.universe_size() == 2



# ---------------------------------------------------------------------------
# 3. Fallback 5 symbol gate
# ---------------------------------------------------------------------------
def test_fb5_gate_allows_mt5_universe_symbols(clean_universe, monkeypatch):
    monkeypatch.setattr(fb5_config, "FALLBACK5_SYMBOL_SOURCE", "mt5", raising=False)
    clean_universe.sync_universe(["EURUSD", "AUDCAD", "NAS100"], source="mt5", persist=False)

    assert symbol_gate.resolve_symbol("AUDCAD") == "AUDCAD"
    assert symbol_gate.symbol_gate_reason("AUDCAD") == ""
    # Not part of the synchronized universe -> rejected with a clear reason.
    assert symbol_gate.resolve_symbol("GBPNZD") == ""
    assert symbol_gate.symbol_gate_reason("GBPNZD") == "symbol_not_available_in_mt5"


def test_fb5_gate_core_mode_keeps_original_allowlist(monkeypatch):
    monkeypatch.setattr(fb5_config, "FALLBACK5_SYMBOL_SOURCE", "core", raising=False)
    assert symbol_gate.resolve_symbol("EURUSD") == "EURUSD"
    assert symbol_gate.resolve_symbol("AUDCAD") == ""
    assert symbol_gate.symbol_gate_reason("AUDCAD") == "symbol_not_allowed"


def test_fb5_gate_custom_mode(monkeypatch):
    monkeypatch.setattr(fb5_config, "FALLBACK5_SYMBOL_SOURCE", "custom", raising=False)
    monkeypatch.setattr(fb5_config, "ALLOWED_SYMBOLS", ("GBPUSD", "USDCAD"), raising=False)
    assert symbol_gate.resolve_symbol("GBPUSD") == "GBPUSD"
    assert symbol_gate.resolve_symbol("EURUSD") == ""


def test_fb5_profile_falls_back_to_default(clean_universe, monkeypatch):
    monkeypatch.setattr(fb5_config, "FALLBACK5_SYMBOL_SOURCE", "mt5", raising=False)
    clean_universe.sync_universe(["AUDCAD"], source="mt5", persist=False)
    profile = symbol_gate.get_symbol_profile("AUDCAD")
    assert profile["default_risk_percent"] == fb5_config.DEFAULT_SYMBOL_PROFILE["default_risk_percent"]


# ---------------------------------------------------------------------------
# 4. Finnhub + Gemini news feed
# ---------------------------------------------------------------------------
def test_news_feed_fails_open_without_news(monkeypatch):
    monkeypatch.setenv("NEWS_FEED_ENABLED", "true")
    monkeypatch.setenv("NEWS_FEED_CALENDAR_BLOCK", "false")
    monkeypatch.setattr(news_feed, "fetch_headlines", lambda symbol, max_items=None, force=False: [])
    allowed, reason, brief = news_feed.news_allows_direction("EURUSD", "BUY")
    assert allowed is True
    assert reason == "no_news_available"
    assert brief["has_news"] is False


def test_news_gate_blocks_setup_against_news(monkeypatch):
    """Requirement: news exists + setup opposes it -> block the accurate setup."""
    monkeypatch.setenv("NEWS_FEED_MODE", "block")
    monkeypatch.setenv("NEWS_FEED_MIN_CONFIDENCE", "0.5")
    monkeypatch.setenv("NEWS_FEED_CALENDAR_BLOCK", "false")
    monkeypatch.setattr(news_feed, "get_news_brief", _stub_brief("SELL", 0.9))

    gate = news_feed.news_gate("EURUSD", "BUY")
    assert gate["allowed"] is False
    assert gate["has_news"] is True
    assert "news_direction_conflict" in gate["reason"]
    assert gate["news_direction"] == "SELL"
    assert gate["proposed_direction"] == "BUY"


def test_news_gate_allows_setup_with_news_if_aligned(monkeypatch):
    monkeypatch.setenv("NEWS_FEED_MODE", "block")
    monkeypatch.setenv("NEWS_FEED_CALENDAR_BLOCK", "false")
    monkeypatch.setattr(news_feed, "get_news_brief", _stub_brief("BUY", 0.8))
    gate = news_feed.news_gate("EURUSD", "BUY")
    assert gate["allowed"] is True
    assert "news_aligned" in gate["reason"]


def test_news_gate_allows_when_no_news_for_the_pair(monkeypatch):
    """Requirement: no news for the pair -> execute directly."""
    monkeypatch.setenv("NEWS_FEED_MODE", "block")
    monkeypatch.setenv("NEWS_FEED_CALENDAR_BLOCK", "false")
    monkeypatch.setattr(
        news_feed,
        "get_news_brief",
        lambda symbol, force=False: {
            "symbol": symbol,
            "enabled": True,
            "has_news": False,
            "market_direction": "NO_TRADE",
            "confidence": 0.0,
            "headlines": [],
            "sources": [],
            "engine": "none",
            "reason": "no_news_available",
        },
    )
    gate = news_feed.news_gate("AUDNZD", "BUY")
    assert gate["allowed"] is True
    assert gate["reason"] == "no_news_available"


def test_news_gate_allows_neutral_news(monkeypatch):
    monkeypatch.setenv("NEWS_FEED_MODE", "block")
    monkeypatch.setenv("NEWS_FEED_CALENDAR_BLOCK", "false")
    monkeypatch.setattr(news_feed, "get_news_brief", _stub_brief("NO_TRADE", 0.9))
    gate = news_feed.news_gate("EURUSD", "BUY")
    assert gate["allowed"] is True
    assert "news_available_neutral" in gate["reason"]


def test_news_gate_below_confidence_threshold(monkeypatch):
    monkeypatch.setenv("NEWS_FEED_MODE", "block")
    monkeypatch.setenv("NEWS_FEED_MIN_CONFIDENCE", "0.80")
    monkeypatch.setenv("NEWS_FEED_CALENDAR_BLOCK", "false")
    monkeypatch.setattr(news_feed, "get_news_brief", _stub_brief("SELL", 0.55))
    gate = news_feed.news_gate("EURUSD", "BUY")
    assert gate["allowed"] is True
    assert "below_threshold" in gate["reason"]


def test_news_gate_advisory_mode_never_blocks(monkeypatch):
    monkeypatch.setenv("NEWS_FEED_MODE", "advisory")
    monkeypatch.setenv("NEWS_FEED_CALENDAR_BLOCK", "false")
    monkeypatch.setattr(news_feed, "get_news_brief", _stub_brief("SELL", 0.95))
    gate = news_feed.news_gate("EURUSD", "BUY")
    assert gate["allowed"] is True
    assert "news_conflict_advisory" in gate["reason"]


def test_strict_match_ignores_unrelated_headlines(monkeypatch):
    """A general market headline about another market is NOT news for the pair."""
    calls = {"count": 0}

    def _fake_finnhub_request(path, params):
        calls["count"] += 1
        return [
            {"headline": "Tech earnings beat expectations in New York", "summary": "Nasdaq rallies"},
        ]

    monkeypatch.setenv("NEWS_FEED_STRICT_MATCH", "true")
    monkeypatch.setenv("FINNHUB_API_KEY", "test-key")
    monkeypatch.setattr(news_feed, "_finnhub_request", _fake_finnhub_request)
    monkeypatch.setattr(news_feed, "_GLOBAL_NEWS", {"fetched_at": 0.0, "items": []})

    headlines = news_feed.fetch_headlines("AUDNZD")
    assert headlines == []
    assert calls["count"] == 3  # only the shared macro feeds, no company-news call


def test_global_news_cache_limits_api_calls(monkeypatch):
    """300+ symbols must not trigger 300+ Finnhub calls per scan cycle."""
    calls = {"count": 0}

    def _fake_finnhub_request(path, params):
        calls["count"] += 1
        return [{"headline": "Euro rises as ECB holds rates", "summary": "EUR bullish"}]

    monkeypatch.setenv("FINNHUB_API_KEY", "test-key")
    monkeypatch.setattr(news_feed, "_finnhub_request", _fake_finnhub_request)
    monkeypatch.setattr(news_feed, "_GLOBAL_NEWS", {"fetched_at": 0.0, "items": []})

    for symbol in ("EURUSD", "EURJPY", "EURAUD", "EURCAD"):
        news_feed.fetch_headlines(symbol)

    assert calls["count"] == 3  # one shared fetch, reused for every symbol


def _stub_brief(direction="SELL", confidence=0.9):
    def _fake(symbol, force=False):
        return {
            "symbol": symbol,
            "enabled": True,
            "has_news": True,
            "market_direction": direction,
            "confidence": confidence,
            "key_sentiment": "Bearish",
            "executive_breakdown": "",
            "headlines": ["test"],
            "sources": ["test"],
            "engine": "gemini+finnhub",
            "reason": "ok",
        }

    return _fake


def test_news_gate_blocks_via_wrapper(monkeypatch):
    """The backwards-compatible wrapper must honour the blocking policy too."""
    monkeypatch.setenv("NEWS_FEED_MODE", "block")
    monkeypatch.setenv("NEWS_FEED_MIN_CONFIDENCE", "0.6")
    monkeypatch.setenv("NEWS_FEED_CALENDAR_BLOCK", "false")
    monkeypatch.setattr(news_feed, "get_news_brief", _stub_brief("SELL", 0.9))

    allowed, reason, _brief = news_feed.news_allows_direction("EURUSD", "BUY")
    assert allowed is False
    assert "news_direction_conflict" in reason

    allowed_ok, _reason_ok, _ = news_feed.news_allows_direction("EURUSD", "SELL")
    assert allowed_ok is True


def test_attach_news_to_analysis(monkeypatch):
    monkeypatch.setenv("NEWS_FEED_MODE", "block")
    monkeypatch.setenv("NEWS_FEED_CALENDAR_BLOCK", "false")
    monkeypatch.setattr(news_feed, "get_news_brief", _stub_brief("BUY", 0.8))

    analysis = {"topdown": {}}
    news_feed.attach_news_to_analysis(analysis, "EURUSD", "BUY")
    assert analysis["news_feed"]["allowed"] is True
    assert analysis["news_feed"]["has_news"] is True
    assert analysis["news_feed"]["news_direction"] == "BUY"
    assert analysis["topdown"]["news_feed"]["news_direction"] == "BUY"


# ---------------------------------------------------------------------------
# 5. Admin hygiene: the bot API + main must import cleanly
# ---------------------------------------------------------------------------
def test_bot_api_and_main_import():
    import bot_api  # noqa: F401  (registers mirror + admin routes)
    import main  # noqa: F401

    rules = {rule.rule for rule in bot_api.app.url_map.iter_rules()}
    assert "/admin/credentials" in rules
    assert "/admin/universe" in rules
