"""
Live Financial News Collector
==============================
Real-time macro / fundamental news engine built on:

    * Finnhub  -> live market, forex, crypto, company news
    * Google Gemini (google-genai) -> AI financial breakdown + direction signal

This module is the **single news source** for the bot's MacroRuleEngine and for
the directional-bias feed that every strategy (ICT, Kingsbalfx, FB3, FB4, FB5)
consults via `get_market_direction_signal()`.

Key design decision (per user requirement):
    * If there is NO news for a currency/pair on a given day, and the technical
      strategies all fire correctly, the bot must NOT fail-closed on the macro
      gate. It returns a neutral/allow directive so the technical setup can
      execute. News is an *enrichment*, not a hard wall when absent.

Environment variables:
    FINNHUB_API_KEY   (required for news fetch)
    GEMINI_API_KEY    (required for Gemini breakdown/direction)
    MACRO_TOOL        ("finnhub" | "web" | "hybrid") — source selection
"""

import json
import os
from typing import Any, Dict, List, Optional, Tuple

import finnhub

# Google Generative AI (genai) SDK
from google import genai
from google.genai import types as genai_types

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Cache to avoid re-fetching every scan.
_NEWS_CACHE: Dict[str, Dict[str, Any]] = {}
_NEWS_CACHE_TTL = int(os.getenv("MACRO_NEWS_CACHE_TTL", "300"))


def _finnhub_client() -> Optional[finnhub.Client]:
    key = (os.getenv("FINNHUB_API_KEY") or "").strip()
    if not key:
        return None
    try:
        return finnhub.Client(api_key=key)
    except Exception:
        return None


def _gemini_client() -> Optional["genai.Client"]:
    key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not key:
        return None
    try:
        return genai.Client(api_key=key)
    except Exception:
        return None


# ----------------------------------------------------------------------------
# 1. Live news pull (Finnhub)
# ----------------------------------------------------------------------------
def get_finnhub_news(category: str = "general", max_items: int = 5) -> List[Dict[str, str]]:
    """Fetch live headlines + summaries from Finnhub. Empty list on any failure."""
    client = _finnhub_client()
    if client is None:
        return []
    try:
        items = client.general_news(category, min_id=0)
        out = []
        for item in items or []:
            headline = (item or {}).get("headline") or ""
            if headline:
                out.append({
                    "headline": headline,
                    "summary": (item or {}).get("summary") or "",
                    "url": (item or {}).get("url") or "",
                    "datetime": (item or {}).get("datetime"),
                })
            if len(out) >= max_items:
                break
        return out
    except Exception:
        # No FINNHUB_API_KEY / network error => treat as "no news available".
        return []


def fetch_market_news(symbol: str) -> List[Dict[str, str]]:
    """Best-effort news fetch tailored to a symbol's asset class.

    Returns [] when there is no usable news for the symbol today (the caller
    decides how to handle the empty case — the macro gate fails OPEN).
    """
    asset_class = _infer_asset_class(symbol)
    if asset_class == "crypto":
        return get_finnhub_news(category="crypto")
    if asset_class in ("forex", "indices", "stocks", "metals"):
        # General news often carries the relevant macro headlines.
        return get_finnhub_news(category="general")
    return get_finnhub_news(category="general")


def _infer_asset_class(symbol: str) -> str:
    upper = (symbol or "").upper()
    if upper.startswith(("XAU", "XAG", "XPT", "XPD")):
        return "metals"
    if any(c in upper for c in ("BTC", "ETH", "SOL", "XRP", "DOGE", "LTC", "ADA", "LINK")):
        return "crypto"
    if any(c in upper for c in ("NAS100", "US500", "US30", "US100", "SPX", "NDX")):
        return "indices"
    if len(upper) == 6 and upper.isalpha():
        return "forex"
    return "general"


# ----------------------------------------------------------------------------
# 2. Gemini AI breakdown + strict direction signal
# ----------------------------------------------------------------------------
_CONFIDENCE_SCHEMA = genai_types.Schema(
    type="OBJECT",
    properties={
        "market_direction": genai_types.Schema(
            type="STRING",
            enum=["BUY", "SELL", "NO_TRADE"],
        ),
        "confidence": genai_types.Schema(type="NUMBER"),
        "key_sentiment": genai_types.Schema(type="STRING"),
        "executive_breakdown": genai_types.Schema(type="STRING"),
        "impact_analysis": genai_types.Schema(type="STRING"),
    },
    required=["market_direction", "confidence", "key_sentiment"],
)


_ANALYSIS_PROMPT = """You are an AI financial breakdown engine.

Asset/symbol: {symbol}
Analyze the following live market news items pulled from Finnhub:
{news}

Provide a breakdown containing:
1. market_direction  - one of BUY, SELL, or NO_TRADE (NO_TRADE when news is
   mixed, insignificant, contradictory, or has no clear directional catalyst).
2. confidence        - a number from 0.0 to 1.0.
3. key_sentiment     - Bullish / Bearish / Neutral.
4. executive_breakdown - brief plain-language summary of the events.
5. impact_analysis   - likely market impact.

Output ONLY a JSON object matching the response schema.
"""


def analyze_market(symbol: str, news_data: List[Dict[str, str]]) -> Dict[str, Any]:
    """Run Gemini over provided news items; return a structured direction dict.

    Never raises. On any failure returns a NEUTRAL (NO_TRADE-direction but
    low-confidence) payload so callers can fail OPEN.
    """
    if not news_data:
        return {
            "market_direction": "NO_TRADE",
            "confidence": 0.0,
            "key_sentiment": "Neutral",
            "executive_breakdown": "No news available for this symbol today.",
            "impact_analysis": "neutral",
        }

    client = _gemini_client()
    if client is None:
        return {
            "market_direction": "NO_TRADE",
            "confidence": 0.0,
            "key_sentiment": "Neutral",
            "executive_breakdown": "GEMINI_API_KEY not configured.",
            "impact_analysis": "neutral",
        }

    prompt = _ANALYSIS_PROMPT.format(symbol=symbol, news=json.dumps(news_data, indent=2))
    try:
        config = genai_types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_CONFIDENCE_SCHEMA,
        )
        response = client.models.generate_content(model=MODEL, contents=prompt, config=config)
        raw = response.text
        parsed = json.loads(raw) if isinstance(raw, str) else raw
        direction = str(parsed.get("market_direction") or "NO_TRADE").upper()
        if direction not in ("BUY", "SELL", "NO_TRADE"):
            direction = "NO_TRADE"
        try:
            confidence = float(parsed.get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        return {
            "market_direction": direction,
            "confidence": max(0.0, min(1.0, confidence)),
            "key_sentiment": parsed.get("key_sentiment") or "Neutral",
            "executive_breakdown": parsed.get("executive_breakdown") or "",
            "impact_analysis": parsed.get("impact_analysis") or "",
        }
    except Exception:
        return {
            "market_direction": "NO_TRADE",
            "confidence": 0.0,
            "key_sentiment": "Neutral",
            "executive_breakdown": "Gemini analysis failed; no directional call.",
            "impact_analysis": "neutral",
        }


# ----------------------------------------------------------------------------
# 3. Google Search Grounding (real-time web) — optional auto-sync
# ----------------------------------------------------------------------------
def fetch_live_web_breakdown(topic: str = "Forex market news today") -> str:
    """Bypass static data; auto-search Google live in real-time via Gemini."""
    client = _gemini_client()
    if client is None:
        return "GEMINI_API_KEY not configured."
    try:
        config = genai_types.GenerateContentConfig(
            tools=[{"google_search": {}}],  # enables Google Search tool
        )
        response = client.models.generate_content(
            model=MODEL,
            contents=f"Give me a breakdown of recent developments in: {topic}",
            config=config,
        )
        return response.text or ""
    except Exception as exc:
        return f"Web search breakdown unavailable: {exc}"


# ----------------------------------------------------------------------------
# 4. Cached public API used by MacroRuleEngine and strategy direction-bias
# ----------------------------------------------------------------------------
def get_market_direction_signal(symbol: str) -> Dict[str, Any]:
    """Return the consolidated daily macro direction signal for `symbol`.

    This is the single entry point for the whole bot. It is **cached** per
    symbol for `_NEWS_CACHE_TTL` seconds and NEVER raises.

    Returns a dict of the shape::

        {
          "symbol": str,
          "market_direction": "BUY"|"SELL"|"NO_TRADE",
          "confidence": float,          # 0..1
          "key_sentiment": str,
          "executive_breakdown": str,
          "impact_analysis": str,
          "has_news": bool,             # whether any real news was available
        }
    """
    upper = (symbol or "").upper()
    now = __import__("time").time()
    cache = _NEWS_CACHE.get(upper)
    if cache and (now - cache["_fetched_at"]) < _NEWS_CACHE_TTL:
        return cache["payload"]

    news = fetch_market_news(upper)
    has_news = bool(news)
    analysis = analyze_market(upper, news)

    payload = {
        "symbol": upper,
        "market_direction": analysis.get("market_direction", "NO_TRADE"),
        "confidence": analysis.get("confidence", 0.0),
        "key_sentiment": analysis.get("key_sentiment", "Neutral"),
        "executive_breakdown": analysis.get("executive_breakdown", ""),
        "impact_analysis": analysis.get("impact_analysis", ""),
        "has_news": has_news,
        "news_sources": len(news),
        "_fetched_at": now,
    }
    _NEWS_CACHE[upper] = {"payload": {k: v for k, v in payload.items() if k != "_fetched_at"}, "_fetched_at": now}
    return payload


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    symbol = os.getenv("TEST_SYMBOL", "EURUSD")
    sig = get_market_direction_signal(symbol)
    print(json.dumps(sig, indent=2))
