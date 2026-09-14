"""
Unified Finnhub + Gemini news feed (attached to every strategy)
==============================================================

One news accessor for the whole bot:

* **Finnhub** supplies the live headlines / summaries (forex, crypto, metals,
  general market).
* **Google Gemini** turns those headlines into a strict directional read
  (``BUY`` / ``SELL`` / ``NO_TRADE`` + confidence + short breakdown).

Both are called over plain REST so the feed works even when the optional
``finnhub`` / ``google-genai`` SDKs are not installed in the virtualenv. When
those SDKs *are* available, the root :mod:`finnhub` module is used so the bot
keeps a single news pipeline.

Design rules (must not break trading when data is missing):

* **News exists for the pair and the setup opposes it** -> the trade is BLOCKED
  (even when the technical setup is perfect). This is the default policy.
* News exists and agrees with the setup (or is non-directional) -> allowed.
* **No news for the pair** (strict per-pair matching) -> allowed; the technical
  setup executes directly.
* Feed/network errors -> fail open, so a broken API can never freeze the bot.

The hard, authoritative second gate remains ``macro_rule_engine``.

Environment
-----------
    FINNHUB_API_KEY, GEMINI_API_KEY, GEMINI_MODEL
    NEWS_FEED_ENABLED           (default true)
    NEWS_FEED_MODE              block | advisory  (default block)
    NEWS_FEED_MIN_CONFIDENCE    (default 0.50; 0.0 blocks on any directional read)
    NEWS_FEED_STRICT_MATCH      (default true: only pair-relevant news counts)
    NEWS_FEED_MAX_HEADLINES     (default 6)
    NEWS_FEED_GLOBAL_TTL        (default 300s: shared Finnhub market-feed cache)
    NEWS_FEED_TIMEOUT           (default 12 seconds)
    NEWS_FEED_CACHE_TTL         (default 300 seconds)
    NEWS_FEED_CALENDAR_BLOCK    (default true: block around high-impact calendar events)
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

FINNHUB_BASE_URL = "https://finnhub.io/api/v1"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

_CACHE: Dict[str, Dict[str, Any]] = {}
_CACHE_LOCK = threading.Lock()

_CURRENCY_WORDS = {
    "USD": ("USD", "DOLLAR", "FED", "FOMC", "FEDERAL RESERVE"),
    "EUR": ("EUR", "EURO", "ECB", "EUROZONE"),
    "GBP": ("GBP", "POUND", "STERLING", "BOE", "BANK OF ENGLAND"),
    "JPY": ("JPY", "YEN", "BOJ", "BANK OF JAPAN"),
    "CHF": ("CHF", "FRANC", "SNB"),
    "AUD": ("AUD", "AUSSIE", "RBA"),
    "NZD": ("NZD", "KIWI", "RBNZ"),
    "CAD": ("CAD", "LOONIE", "BOC", "BANK OF CANADA"),
    "CNH": ("CNH", "YUAN", "CHINA", "PBOC"),
    "MXN": ("MXN", "PESO", "BANXICO"),
    "ZAR": ("ZAR", "RAND"),
    "NOK": ("NOK", "KRONE", "NORGES"),
    "SEK": ("SEK", "KRONA", "RIKSBANK"),
    "SGD": ("SGD", "SINGAPORE"),
    "DKK": ("DKK", "KRONE", "DANMARKS"),
    "HKD": ("HKD", "HONG KONG"),
}


def _truthy(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _env(name: str, default: str = "") -> str:
    return str(os.getenv(name, default) or "").strip()


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name) or default)
    except ValueError:
        return default


def enabled() -> bool:
    return _truthy("NEWS_FEED_ENABLED", True)



# ---------------------------------------------------------------------------
# Symbol helpers
# ---------------------------------------------------------------------------
def symbol_keywords(symbol: str) -> Tuple[str, str, List[str]]:
    """Return (base_currency, quote_currency, keyword list) for filtering news."""
    clean = re.sub(r"[^A-Z]", "", str(symbol or "").upper())
    base = clean[:3]
    quote = clean[3:6] if len(clean) >= 6 else ""
    keywords: List[str] = []
    for code in (base, quote):
        for word in _CURRENCY_WORDS.get(code, (code,)):
            if word not in keywords:
                keywords.append(word)
    if not keywords and clean:
        keywords.append(clean)
    return base, quote, keywords


def _headline_matches(headline: str, summary: str, keywords: List[str]) -> bool:
    haystack = f"{headline or ''} {summary or ''}".upper()
    return any(word and word in haystack for word in keywords)


# ---------------------------------------------------------------------------
# Finnhub (REST)
# ---------------------------------------------------------------------------
def _finnhub_key() -> str:
    return _env("FINNHUB_API_KEY")


def _finnhub_request(path: str, params: Dict[str, Any]) -> Any:
    key = _finnhub_key()
    if not key:
        return None
    try:
        import requests
    except ImportError:  # pragma: no cover
        return None
    query = dict(params)
    query["token"] = key
    try:
        response = requests.get(
            f"{FINNHUB_BASE_URL}{path}",
            params=query,
            timeout=_env_float("NEWS_FEED_TIMEOUT", 12.0),
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        logger.debug("news_feed: Finnhub %s failed: %s", path, exc)
        return None


def mode() -> str:
    """``block`` (default) = news that opposes a setup blocks the trade."""
    value = _env("NEWS_FEED_MODE", "block").lower()
    return value if value in ("advisory", "block") else "block"


def min_confidence() -> float:
    """Minimum Gemini confidence required before news can block a setup.

    Set ``NEWS_FEED_MIN_CONFIDENCE=0`` to block on *any* directional news read.
    """
    return max(0.0, min(1.0, _env_float("NEWS_FEED_MIN_CONFIDENCE", 0.50)))


def strict_match() -> bool:
    """When true, only news that actually mentions the pair's currencies counts."""
    return _truthy("NEWS_FEED_STRICT_MATCH", True)


_GLOBAL_NEWS: Dict[str, Any] = {"fetched_at": 0.0, "items": []}


def global_news(force: bool = False) -> List[Any]:
    """Fetch the market-wide Finnhub feeds ONCE per TTL and share them.

    Scanning 300+ symbols must not produce 1,000+ Finnhub calls per cycle, so the
    general/forex/crypto feeds are cached globally and filtered per symbol.
    """
    ttl = _env_float("NEWS_FEED_GLOBAL_TTL", 300.0)
    now = time.time()
    if not force and _GLOBAL_NEWS["items"] and (now - _GLOBAL_NEWS["fetched_at"]) < ttl:
        return list(_GLOBAL_NEWS["items"])

    items: List[Any] = []
    for category in ("forex", "crypto", "general"):
        payload = _finnhub_request("/news", {"category": category})
        if isinstance(payload, list):
            items.extend(payload)

    _GLOBAL_NEWS["fetched_at"] = now
    _GLOBAL_NEWS["items"] = items
    return list(items)


def _asset_class(symbol: str) -> str:
    try:
        from utils.symbol_profile import infer_asset_class

        return infer_asset_class(symbol)
    except Exception:
        return "other"


def fetch_headlines(
    symbol: str,
    max_items: Optional[int] = None,
    force: bool = False,
) -> List[Dict[str, str]]:
    """Return only the Finnhub headlines that are RELEVANT to ``symbol``.

    An empty list means "no news for this pair" — the caller then lets the
    technical setup execute directly.
    """
    if not _finnhub_key():
        return []

    limit = int(max_items or _env_float("NEWS_FEED_MAX_HEADLINES", 6))
    _, _, keywords = symbol_keywords(symbol)

    items: List[Any] = list(global_news(force=force))

    # Per-company news is useful for equities only; FX/metals/crypto are covered
    # by the shared macro feeds above (and this keeps the API call count low).
    if _asset_class(symbol) in ("stocks", "other") and _truthy("NEWS_FEED_COMPANY_NEWS", True):
        company_symbol = re.sub(r"[^A-Za-z]", "", str(symbol or ""))[:12]
        payload = _finnhub_request("/company-news", {"symbol": company_symbol})
        if isinstance(payload, list):
            items.extend(payload)

    relevant: List[Dict[str, str]] = []
    fallback: List[Dict[str, str]] = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        headline = str(item.get("headline") or "").strip()
        if not headline:
            continue
        dedupe_key = headline.lower()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        record = {
            "headline": headline,
            "summary": str(item.get("summary") or "").strip(),
            "url": str(item.get("url") or "").strip(),
            "source": str(item.get("source") or "").strip(),
        }
        if _headline_matches(record["headline"], record["summary"], keywords):
            relevant.append(record)
            if len(relevant) >= limit:
                break
        elif not strict_match() and len(fallback) < limit:
            fallback.append(record)

    return relevant or fallback


# ---------------------------------------------------------------------------
# Gemini (REST)
# ---------------------------------------------------------------------------
def _gemini_key() -> str:
    return _env("GEMINI_API_KEY")


def _gemini_model() -> str:
    return _env("GEMINI_MODEL") or "gemini-3.6-flash"


# Google retires model names regularly (e.g. gemini-2.5-flash -> 404 for new
# keys). These known-good names are tried in order when the configured model is
# unavailable, so the news feed keeps working after a model retirement.
_GEMINI_MODEL_FALLBACKS = (
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-flash-latest",
)


def gemini_model_candidates() -> List[str]:
    """Configured Gemini model first, then known-good fallbacks."""
    candidates: List[str] = []
    for model in (_gemini_model(),) + _GEMINI_MODEL_FALLBACKS:
        name = str(model or "").strip()
        if name and name not in candidates:
            candidates.append(name)
    return candidates


_GEMINI_PROMPT = (
    "You are a macro news analyst for an automated trading bot.\n"
    "Instrument: {symbol} (asset class: {asset_class}).\n"
    "Today's Finnhub headlines:\n{headlines}\n\n"
    "Decide the single directional macro bias for this instrument.\n"
    "Answer with ONLY strict JSON, no markdown, using this schema:\n"
    '{{"market_direction":"BUY|SELL|NO_TRADE","confidence":0.0,'
    '"key_sentiment":"short label","executive_breakdown":"max 40 words"}}'
)


def _extract_json(text: str) -> Dict[str, Any]:
    raw = str(text or "").strip()
    if not raw:
        return {}
    raw = re.sub(r"^```(?:json)?", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _normalize_direction(value: Any) -> str:
    text = str(value or "").strip().upper()
    if text in ("BUY", "BULLISH", "LONG", "UP"):
        return "BUY"
    if text in ("SELL", "BEARISH", "SHORT", "DOWN"):
        return "SELL"
    return "NO_TRADE"


def _clamp_confidence(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if number > 1.0:
        number = number / 100.0
    return max(0.0, min(1.0, number))


def gemini_breakdown(symbol: str, headlines: List[Dict[str, str]]) -> Dict[str, Any]:
    """Ask Gemini for a strict directional read of the fetched headlines."""
    key = _gemini_key()
    if not key or not headlines:
        return {}

    try:
        import requests
    except ImportError:  # pragma: no cover
        return {}

    try:
        from utils.symbol_profile import infer_asset_class

        asset_class = infer_asset_class(symbol)
    except Exception:
        asset_class = "forex"

    body = "\n".join(
        f"[{index}] {item.get('headline')} :: {item.get('summary')}"[:600]
        for index, item in enumerate(headlines, start=1)
    )
    prompt = _GEMINI_PROMPT.format(symbol=symbol, asset_class=asset_class, headlines=body)
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.0, "responseMimeType": "application/json"},
    }
    if _truthy("GEMINI_USE_GROUNDING", False):
        payload["tools"] = [{"google_search": {}}]

    try:
        response = requests.post(
            f"{GEMINI_BASE_URL}/{_gemini_model()}:generateContent",
            params={"key": key},
            json=payload,
            timeout=_env_float("NEWS_FEED_TIMEOUT", 12.0),
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        logger.debug("news_feed: Gemini call failed for %s: %s", _gemini_model(), exc)
        data = None

    if data is None:
        # Retired/renamed model or transient error: try the fallback chain.
        for model in gemini_model_candidates()[1:]:
            try:
                response = requests.post(
                    f"{GEMINI_BASE_URL}/{model}:generateContent",
                    params={"key": key},
                    json=payload,
                    timeout=_env_float("NEWS_FEED_TIMEOUT", 12.0),
                )
                response.raise_for_status()
                data = response.json()
                logger.info("news_feed: Gemini model fallback in use: %s", model)
                break
            except Exception as exc:
                logger.debug("news_feed: Gemini fallback %s failed: %s", model, exc)
                data = None

    if data is None:
        return {}

    text = ""
    try:
        candidates = data.get("candidates") or []
        if candidates:
            parts = (candidates[0].get("content") or {}).get("parts") or []
            text = "".join(str(part.get("text") or "") for part in parts)
    except Exception:
        text = ""

    parsed = _extract_json(text)
    if not parsed:
        return {}
    return {
        "market_direction": _normalize_direction(parsed.get("market_direction") or parsed.get("direction")),
        "confidence": _clamp_confidence(parsed.get("confidence")),
        "key_sentiment": str(parsed.get("key_sentiment") or "").strip() or "Neutral",
        "executive_breakdown": str(parsed.get("executive_breakdown") or "").strip(),
    }


# ---------------------------------------------------------------------------
# Public: cached brief + gate
# ---------------------------------------------------------------------------
_EMPTY_BRIEF = {
    "has_news": False,
    "market_direction": "NO_TRADE",
    "confidence": 0.0,
    "key_sentiment": "Neutral",
    "executive_breakdown": "",
    "headlines": [],
    "sources": [],
}


def get_news_brief(symbol: str, force: bool = False) -> Dict[str, Any]:
    """Return the cached Finnhub + Gemini brief for ``symbol`` (never raises)."""
    key = str(symbol or "").upper()
    if not key:
        return {**_EMPTY_BRIEF, "symbol": "", "enabled": enabled(), "reason": "missing_symbol"}

    if not enabled():
        return {**_EMPTY_BRIEF, "symbol": key, "enabled": False, "reason": "news_feed_disabled"}

    ttl = _env_float("NEWS_FEED_CACHE_TTL", 300.0)
    now = time.time()
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and not force and (now - cached["fetched_at"]) < ttl:
            return dict(cached["payload"])

    headlines = fetch_headlines(key) or []
    analysis = gemini_breakdown(key, headlines) if headlines else {}

    payload = {
        "symbol": key,
        "enabled": True,
        "has_news": bool(headlines),
        "market_direction": analysis.get("market_direction") or "NO_TRADE",
        "confidence": float(analysis.get("confidence") or 0.0),
        "key_sentiment": analysis.get("key_sentiment") or "Neutral",
        "executive_breakdown": analysis.get("executive_breakdown") or "",
        "headlines": [item.get("headline") for item in headlines][:6],
        "sources": sorted({item.get("source") for item in headlines if item.get("source")}),
        "engine": "gemini+finnhub" if analysis else ("finnhub" if headlines else "none"),
        "reason": "ok" if headlines else "no_news_available",
    }
    with _CACHE_LOCK:
        _CACHE[key] = {"fetched_at": now, "payload": payload}
    return dict(payload)


def news_gate(symbol: str, direction: Optional[str] = None) -> Dict[str, Any]:
    """Decide whether the news allows this trade.

    Policy (requirement):
      * News EXISTS for the pair and its directional bias OPPOSES the setup
        -> BLOCK, even if the technical setup is perfect.
      * News EXISTS and agrees (or is non-directional) -> allow.
      * NO news for the pair -> allow, the technical setup executes directly.

    Returns ``{"allowed": bool, "reason": str, "brief": dict, ...}``.
    """
    brief = get_news_brief(symbol)
    proposed = str(direction or "").strip().upper()
    news_direction = str(brief.get("market_direction") or "NO_TRADE").upper()
    confidence = float(brief.get("confidence") or 0.0)

    result: Dict[str, Any] = {
        "symbol": str(symbol or "").upper(),
        "allowed": True,
        "reason": "no_news_available",
        "mode": mode(),
        "has_news": bool(brief.get("has_news")),
        "news_direction": news_direction,
        "confidence": confidence,
        "proposed_direction": proposed,
        "headlines": list(brief.get("headlines") or [])[:3],
        "engine": brief.get("engine"),
        "brief": brief,
    }

    # 1) Hard blocks that apply regardless of the trading direction.
    try:
        from fundamentals.news_manual import is_manual_news_block

        clean = re.sub(r"[^A-Z]", "", str(symbol or "").upper())
        for code in (clean[:3], clean[3:6]):
            if code and is_manual_news_block(code):
                result.update(allowed=False, reason=f"manual_news_block:{code}")
                return result
    except Exception:
        pass

    if _truthy("NEWS_FEED_CALENDAR_BLOCK", True):
        try:
            from fundamentals.news_api import is_high_impact_news_soon

            clean = re.sub(r"[^A-Z]", "", str(symbol or "").upper())
            for code in (clean[:3], clean[3:6]):
                if code and is_high_impact_news_soon(code):
                    result.update(allowed=False, reason=f"high_impact_calendar_event:{code}")
                    return result
        except Exception:
            pass

    # 2) No feed configured/disabled -> never block.
    if not brief.get("enabled"):
        result["reason"] = "news_feed_disabled"
        return result

    # 3) No news for this pair -> execute directly.
    if not brief.get("has_news"):
        result["reason"] = "no_news_available"
        return result

    # 4) News exists but is not a directional macro call -> allow.
    if news_direction not in ("BUY", "SELL"):
        result["reason"] = f"news_available_neutral:{news_direction}|conf={confidence:.2f}"
        return result

    if proposed not in ("BUY", "SELL"):
        result["reason"] = f"news_available:{news_direction}|direction_unknown"
        return result

    # 5) News agrees with the setup -> allow.
    if news_direction == proposed:
        result["reason"] = f"news_aligned:{news_direction}|conf={confidence:.2f}"
        return result

    # 6) News is AGAINST the setup. Advisory mode reports only; block mode stops it.
    if mode() != "block":
        result["reason"] = (
            f"news_conflict_advisory:news={news_direction}|tried={proposed}|conf={confidence:.2f}"
        )
        return result

    threshold = min_confidence()
    if confidence < threshold:
        result["reason"] = (
            f"news_conflict_below_threshold:news={news_direction}|tried={proposed}|"
            f"conf={confidence:.2f}<{threshold:.2f}"
        )
        return result

    result.update(
        allowed=False,
        reason=(
            f"news_direction_conflict:news={news_direction}|tried={proposed}|conf={confidence:.2f}"
        ),
    )
    return result


def news_allows_direction(symbol: str, direction: Optional[str] = None) -> Tuple[bool, str, Dict[str, Any]]:
    """Backwards-compatible wrapper around :func:`news_gate`."""
    gate = news_gate(symbol, direction)
    return bool(gate.get("allowed")), str(gate.get("reason")), gate.get("brief") or {}


def attach_news_to_analysis(
    analysis: Dict[str, Any],
    symbol: str,
    direction: Optional[str] = None,
) -> Dict[str, Any]:
    """Attach the macro news context to an analysis dict for every strategy."""
    result: Dict[str, Any] = {"allowed": True, "reason": "news_feed_unavailable", "brief": {}}
    try:
        gate = news_gate(symbol, direction)
        result = {
            "allowed": bool(gate.get("allowed")),
            "reason": gate.get("reason"),
            "mode": gate.get("mode"),
            "has_news": gate.get("has_news"),
            "news_direction": gate.get("news_direction"),
            "confidence": gate.get("confidence"),
            "headlines": gate.get("headlines"),
            "engine": gate.get("engine"),
            "brief": gate.get("brief") or {},
        }
    except Exception as exc:  # pragma: no cover - never break a scan
        logger.debug("news_feed: attach failed for %s: %s", symbol, exc)

    if isinstance(analysis, dict):
        analysis["news_feed"] = result
        topdown = analysis.get("topdown")
        if isinstance(topdown, dict):
            topdown["news_feed"] = result
    return result


def news_feed_status() -> Dict[str, Any]:
    """Diagnostics for the admin API / logs."""
    return {
        "enabled": enabled(),
        "mode": mode(),
        "min_confidence": min_confidence(),
        "finnhub_configured": bool(_finnhub_key()),
        "gemini_configured": bool(_gemini_key()),
        "gemini_model": _gemini_model(),
        "cached_symbols": sorted(_CACHE.keys()),
    }
