#!/usr/bin/env python3
"""
Post-fix diagnostics for the reported production errors
=======================================================

Run::

    .\\.venv\\Scripts\\python.exe check_fixes.py

Verifies, against the real environment:

1. Supabase credentials resolve to a valid https:// URL (never the ``...``
   placeholder that produced "Invalid URL" and blocked every trade with
   ``supabase_unavailable``).
2. The Supabase client actually builds (bridge + macro rule engine + mirror).
3. The daily macro rule gate no longer answers ``supabase_unavailable``.
4. The MT5 symbol universe registry accepts broker symbols and rejects symbols
   the broker does not expose (Fallback 5 no longer says
   ``symbol_not_allowed`` for every pair).
5. The Finnhub + Gemini news feed answers (or degrades gracefully) for a symbol.
"""

import json
import os
import sys

from dotenv import load_dotenv

PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"

results = []


def record(name, status, detail=""):
    results.append((name, status, detail))
    print(f"[{status}] {name}{(' | ' + detail) if detail else ''}")


def check_supabase_credentials():
    from config.supabase_credentials import credential_status, resolve_supabase_credentials

    resolved = resolve_supabase_credentials(force=True)
    status = credential_status()
    print("   url_source=%s key_source=%s ignored=%s" % (
        status.get("url_source"), status.get("key_source"), status.get("ignored_placeholders")))
    if resolved["usable"] and str(resolved["url"]).startswith("https://"):
        record("Supabase credentials", PASS, f"url={status.get('url')}")
    else:
        record("Supabase credentials", FAIL, "no valid https:// URL / key resolved")


def check_supabase_clients():
    from dashboard.bridge import _get_supabase_client
    from macro_rule_engine import _get_supabase_client as macro_client
    import risk.mirror_trading as mirror

    bridge_ok = _get_supabase_client() is not None
    macro_ok = macro_client() is not None
    mirror_ok = mirror._supabase_client() is not None
    record(
        "Supabase clients (bridge/macro/mirror)",
        PASS if (bridge_ok and macro_ok and mirror_ok) else FAIL,
        f"bridge={bridge_ok} macro={macro_ok} mirror={mirror_ok}",
    )


def check_macro_rule_gate():
    from macro_rule_engine import get_rule_engine

    check = get_rule_engine().validate_trade_against_rule("AUDCAD", "SELL")
    reason = check.get("reason")
    if reason == "supabase_unavailable":
        record("Macro rule gate", FAIL, "still returning supabase_unavailable -> trades blocked")
    else:
        record("Macro rule gate", PASS, f"approved={check.get('approved')} reason={reason}")


def check_mt5_universe():
    from config import mt5_universe

    sample = ["EURUSD", "AUDCAD", "XAUUSD.a", "NAS100"]
    mt5_universe.sync_universe(sample, source="mt5", account_id="diagnostic", persist=False, reason="diagnostic")
    ok = (
        mt5_universe.is_available("AUDCAD")
        and mt5_universe.is_available("XAUUSD")
        and not mt5_universe.is_available("ZZZXXX")
        and mt5_universe.resolve_tradable("XAUUSD") == "XAUUSD.a"
    )
    record("MT5 universe registry", PASS if ok else FAIL, json.dumps(mt5_universe.universe_snapshot()))

    from strategy.fallback_strategy5 import symbol_gate

    allowed = symbol_gate.resolve_symbol("AUDCAD")
    reason = symbol_gate.symbol_gate_reason("AUDCAD")
    record(
        "Fallback 5 symbol gate (MT5 driven)",
        PASS if allowed == "AUDCAD" else FAIL,
        f"canonical={allowed or '<rejected>'} reason={reason or 'ok'}",
    )


def check_news_feed():
    from fundamentals import news_feed

    status = news_feed.news_feed_status()
    print("   feed_status=%s" % json.dumps(status))
    try:
        brief = news_feed.get_news_brief("EURUSD", force=True)
    except Exception as exc:  # pragma: no cover
        record("Finnhub + Gemini news feed", FAIL, f"exception: {exc}")
        return

    if brief.get("has_news"):
        record("Finnhub + Gemini news feed", PASS,
               f"headlines={len(brief.get('headlines') or [])} direction={brief.get('market_direction')} "
               f"engine={brief.get('engine')}")
    else:
        detail = "no headlines returned (network/API key) -> feed fails open (allowed)"
        record("Finnhub + Gemini news feed", WARN, detail)


def check_news_policy():
    """Requirement: opposing news blocks; no news lets the setup execute."""
    from fundamentals import news_feed

    original = news_feed.get_news_brief
    os.environ["NEWS_FEED_MODE"] = "block"
    os.environ["NEWS_FEED_CALENDAR_BLOCK"] = "false"

    def _brief(direction, confidence, has_news=True):
        def _fake(symbol, force=False):
            return {
                "symbol": symbol,
                "enabled": True,
                "has_news": has_news,
                "market_direction": direction,
                "confidence": confidence,
                "key_sentiment": "n/a",
                "executive_breakdown": "",
                "headlines": ["diagnostic headline"] if has_news else [],
                "sources": ["diagnostic"] if has_news else [],
                "engine": "diagnostic",
                "reason": "ok" if has_news else "no_news_available",
            }

        return _fake

    try:
        news_feed.get_news_brief = _brief("SELL", 0.90)
        opposing = news_feed.news_gate("EURUSD", "BUY")

        news_feed.get_news_brief = _brief("BUY", 0.90)
        aligned = news_feed.news_gate("EURUSD", "BUY")

        news_feed.get_news_brief = _brief("NO_TRADE", 0.0, has_news=False)
        no_news = news_feed.news_gate("AUDNZD", "BUY")
    finally:
        news_feed.get_news_brief = original

    ok = (not opposing["allowed"]) and aligned["allowed"] and no_news["allowed"]
    record(
        "News policy (opposing blocks / no news executes)",
        PASS if ok else FAIL,
        f"opposing={opposing['reason']} | aligned=allowed | no_news={no_news['reason']}",
    )


def main() -> int:
    load_dotenv()
    os.environ.setdefault("NEWS_FEED_TIMEOUT", "8")

    print("=" * 72)
    print(" POST-FIX DIAGNOSTICS")
    print("=" * 72)

    for check in (
        check_supabase_credentials,
        check_supabase_clients,
        check_macro_rule_gate,
        check_mt5_universe,
        check_news_feed,
        check_news_policy,
    ):
        try:
            check()
        except Exception as exc:
            record(check.__name__, FAIL, f"{type(exc).__name__}: {exc}")

    print("-" * 72)
    failed = [name for name, status, _ in results if status == FAIL]
    print(f" {len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
