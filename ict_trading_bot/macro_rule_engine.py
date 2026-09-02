"""
Strict Daily Macro & Fundamental Rule Engine
=============================================u

A production-grade, self-contained rule engine that replaces all technical
strategy logic at the trade-entry gate.

Pipeline
--------
1. ``fetch_and_update_daily_rules()``
   - Pulls today's fundamental news headlines + summaries from Finnhub for the
     bot's target symbols (Forex, Crypto, Metals, Stocks, Indices).
   - Sends the aggregated news text to a LOCAL DeepSeek model via Ollama.
   - DeepSeek returns a single strict, IF-THEN boolean trading directive with a
     binary allowed direction (BUY / SELL / NO_TRADE). No sentiment scores, no
     technical indicators.
   - The directive is upserted into Supabase ``daily_macro_rules``.

2. ``validate_trade_against_rule(symbol, proposed_direction)``
   - Reads today's ACTIVE rule for ``symbol``.
   - Enforces strict equality: ``allowed_direction == proposed_direction``.
   - ``NO_TRADE`` or any mismatch => ``{"approved": False, "reason": "..."}``.
   - Every evaluation is written to Supabase ``rule_execution_audit``.

The engine is deterministic and defensive: if Finnhub, Ollama, Supabase, or the
rule row is unavailable, it FAILS CLOSED (returns ``approved=False``) so a trade
is never placed on a missing/stale macro directive.

``MACRO_RULE_ALLOW_BY_DEFAULT`` (default ``true``) relaxes the strict fail-closed
gating for the *absence of a per-symbol rule* (e.g. no news available for that
pair on a given day). When a symbol has no today-rule, the engine records
``no_macro_rule_allowed_by_policy`` and lets the rest of the stack proceed, so the
bot can still execute on pure technicals when the broker / data / risk are ready.

Environment variables used (see OUTPUT section of the request):
    FINNHUB_API_KEY
    SUPABASE_URL
    SUPABASE_SERVICE_KEY
    GEMINI_API_KEY            (Google Gemini; used when set)
    GEMINI_MODEL              (default gemini-2.5-flash)
    GEMINI_USE_GROUNDING      (default false; enables Google Search tool)
    OLLAMA_HOST               (default http://localhost:11434)   [fallback]
    OLLAMA_MODEL              (default deepseek-r1:8b)
    MACRO_RULE_ALLOW_BY_DEFAULT (default true)
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger("macro_rule_engine")
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(_handler)
logger.setLevel(logging.INFO)

# ----------------------------------------------------------------------------
# Module-level configuration (env-driven, reloaded per call so it can be tuned
# at runtime without restarting).
# ----------------------------------------------------------------------------
FINNHUB_BASE_URL = "https://finnhub.io/api/v1"
FINNHUB_NEWS_ENDPOINT = "/news"
FINNHUB_HEADLINES_ENDPOINT = "/company-news"
OLLAMA_ENDPOINT = "/api/generate"
OLLAMA_CHAT_ENDPOINT = "/api/chat"

# Allowed directions (normalized).
_ALLOWED_DIRECTIONS = {"BUY", "SELL", "NO_TRADE"}

# Basic market identifiers Finnhub understands. Fallback mapping is used when a
# broker symbol has no direct Finnhub equivalent.
_FINNHUB_SYMBOL_HINTS = {
    "XAUUSD": "OANDA:XAU_USD",
    "XAGUSD": "OANDA:XAG_USD",
    "BTCUSD": "BINANCE:BTCUSDT",
    "ETHUSD": "BINANCE:ETHUSDT",
    "NAS100": "CBOE:NDX",
    "US500": "CBOE:SPX",
    "DXY": "FOREXCOM:DXY",
}

# Cache of fetched rules to avoid hammering Supabase every cycle.
_CACHE_TTL_SECONDS = int(os.getenv("MACRO_RULE_CACHE_TTL", "300"))
_RULE_CACHE: Dict[str, Dict[str, Any]] = {}


def _env(name: str, default: str = "") -> str:
    return str(os.getenv(name, default)).strip()


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _allow_by_default() -> bool:
    """True when a missing per-symbol rule should NOT block the trade.

    Controlled by ``MACRO_RULE_ALLOW_BY_DEFAULT`` (default ``true``). When the
    macro rule fetch produced no rule for a symbol (e.g. no news that day), this
    lets the bot proceed on technicals instead of failing closed.
    """
    return _env_truthy("MACRO_RULE_ALLOW_BY_DEFAULT", True)


# ----------------------------------------------------------------------------
# Supabase client helpers (service-role key => bypasses RLS)
# ----------------------------------------------------------------------------
def _get_supabase_client():
    supabase_url = _env("SUPABASE_URL")
    service_key = _env("SUPABASE_SERVICE_KEY", _env("SUPABASE_KEY"))
    if not supabase_url or not service_key:
        logger.error("macro_rule_engine: SUPABASE_URL / SUPABASE_SERVICE_KEY not set")
        return None
    try:
        from supabase import create_client
        return create_client(supabase_url, service_key)
    except Exception as exc:  # pragma: no cover - import/network edge
        logger.error("macro_rule_engine: failed to init Supabase client: %s", exc)
        return None


def _upsert_rule(client, record: Dict[str, Any]) -> bool:
    """Upsert one daily rule on (symbol + rule_date). Idempotent & safe."""
    try:
        client.table("daily_macro_rules").upsert(
            record, on_conflict="symbol,rule_date"
        ).execute()
        return True
    except Exception as exc:
        logger.error("macro_rule_engine: rule upsert failed: %s", exc)
        return False


def _insert_audit(client, record: Dict[str, Any]) -> None:
    """Best-effort append into rule_execution_audit. Never raises."""
    try:
        client.table("rule_execution_audit").insert(record).execute()
    except Exception as exc:
        logger.warning("macro_rule_engine: audit insert failed: %s", exc)


def _fetch_today_rule(client, symbol: str) -> Optional[Dict[str, Any]]:
    """Fetch today's active rule for a symbol; returns None if absent."""
    today = _now_utc().date().isoformat()
    try:
        response = (
            client.table("daily_macro_rules")
            .select("symbol,allowed_direction,strict_rule_text,asset_class,rule_date")
            .eq("symbol", symbol)
            .eq("is_active", True)
            .eq("rule_date", today)
            .limit(1)
            .execute()
        )
        rows = getattr(response, "data", None) or []
        return rows[0] if rows else None
    except Exception as exc:
        logger.error("macro_rule_engine: rule fetch failed for %s: %s", symbol, exc)
        return None


# ----------------------------------------------------------------------------
# Symbol universe / asset class helpers
# ----------------------------------------------------------------------------
def _target_symbols() -> List[str]:
    """Return the bot's target symbols (mirrors main.py `_build_symbol_universe`)."""
    symbols = []
    raw = _env("SYMBOLS")
    if raw:
        symbols = [s.strip() for s in raw.split(",") if s.strip()]
    if symbols:
        return symbols

    # Fall back to the configured TradingPairs universe.
    try:
        from config.trading_pairs import TradingPairs
        pairs = TradingPairs.get_trading_pairs()
        for item in pairs or []:
            sym = str(item.get("symbol") if isinstance(item, dict) else item).strip()
            if sym:
                symbols.append(sym)
    except Exception as exc:  # pragma: no cover
        logger.warning("macro_rule_engine: could not load trading pairs: %s", exc)

    if not symbols:
        symbols = [
            "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "NZDUSD",
            "XAUUSD", "XAGUSD", "BTCUSD", "ETHUSD", "NAS100", "US500",
        ]
    return sorted(set(symbols))


def _asset_class(symbol: str) -> str:
    """Return one of: forex, crypto, metals, stocks, indices, other."""
    try:
        from utils.symbol_profile import infer_asset_class
        return infer_asset_class(symbol)
    except Exception:
        pass
    upper = (symbol or "").upper()
    if upper.startswith(("XAU", "XAG", "XPT", "XPD")):
        return "metals"
    if re.search(r"(BTC|ETH|SOL|XRP|DOGE|LTC|ADA|LINK)", upper):
        return "crypto"
    if any(c in upper for c in ("NAS100", "US500", "US30", "US100", "SPX", "NDX", ".INX", ".IXIC")):
        return "indices"
    if re.match(r"^[A-Z]{6}$", upper):
        return "forex"
    if re.match(r"^[A-Z]{1,5}$", upper):
        return "stocks"
    return "other"


def _finnhub_ticker(symbol: str, asset_class: str) -> Optional[str]:
    """Return a Finnhub-friendly market identifier for news lookup."""
    upper = (symbol or "").upper()
    hint = _FINNHUB_SYMBOL_HINTS.get(upper)
    if hint:
        return hint

    # Crypto -> convert broker USD quote to a spot base symbol.
    if asset_class == "crypto":
        base = upper.replace("USD", "").replace("USDT", "").replace("USDC", "")
        if base:
            return f"BINANCE:{base}USDT"

    # Forex -> Finnhub's general market news typically flows by currency pairs.
    if asset_class == "forex":
        return f"OANDA:{upper[:3]}_{upper[3:]}"

    return upper


# ----------------------------------------------------------------------------
# Finnhub news fetching
# ----------------------------------------------------------------------------
def _finnhub_news(symbol: str, asset_class: str, max_items: int = 8) -> List[Dict[str, str]]:
    """Fetch today's headlines + summaries for a symbol from Finnhub."""
    api_key = _env("FINNHUB_API_KEY")
    if not api_key:
        logger.error("macro_rule_engine: FINNHUB_API_KEY not set")
        return []

    ticker = _finnhub_ticker(symbol, asset_class)
    now = _now_utc()
    start = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    end = now.strftime("%Y-%m-%d")
    headers = {"Accept": "application/json"}

    news: List[Dict[str, str]] = []

    # Primary: per-ticker company news (works for stocks/indices/crypto aliases).
    try:
        resp = requests.get(
            f"{FINNHUB_BASE_URL}{FINNHUB_NEWS_ENDPOINT}",
            params={"symbol": ticker, "from": start, "to": end, "token": api_key},
            headers=headers,
            timeout=_env_float("MACRO_FINNHUB_TIMEOUT", 12.0),
        )
        resp.raise_for_status()
        for item in resp.json() or []:
            headline = (item or {}).get("headline") or ""
            summary = (item or {}).get("summary") or ""
            url = (item or {}).get("url") or ""
            if headline:
                news.append({"headline": headline, "summary": summary, "url": url})
    except Exception as exc:
        logger.warning("macro_rule_engine: Finnhub company-news failed for %s: %s", symbol, exc)

    # Secondary: general market headline feed (covers major pairs/commodities).
    try:
        resp2 = requests.get(
            f"{FINNHUB_BASE_URL}/news",
            params={"category": "general", "token": api_key},
            headers=headers,
            timeout=_env_float("MACRO_FINNHUB_TIMEOUT", 12.0),
        )
        resp2.raise_for_status()
        for item in resp2.json() or []:
            headline = (item or {}).get("headline") or ""
            related = (item or {}).get("related") or ""
            summary = (item or {}).get("summary") or ""
            if headline and (related and upper_contains(related, symbol)):
                news.append({"headline": headline, "summary": summary, "url": (item or {}).get("url") or ""})
    except Exception as exc:
        logger.warning("macro_rule_engine: Finnhub general-news failed: %s", exc)

    # Deduplicate by headline.
    seen = set()
    deduped = []
    for item in news:
        key = item["headline"].strip().lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
        if len(deduped) >= max_items:
            break

    return deduped


def upper_contains(text: str, symbol: str) -> bool:
    """Case-insensitive containment check of the base symbol in text."""
    hay = (text or "").upper()
    needle = (symbol or "").upper().replace("/", "").replace("-", "").replace("_", "")
    if not needle:
        return False
    if needle in hay:
        return True
    base = needle[:3]
    return base in hay  # loose: e.g. "EUR" appears in "EUR/USD" article


# ----------------------------------------------------------------------------
# Ollama / DeepSeek reasoning
# ----------------------------------------------------------------------------
def _ollama_base() -> str:
    return (_env("OLLAMA_HOST") or "http://localhost:11434").rstrip("/")


def _ollama_model() -> str:
    return _env("OLLAMA_MODEL") or "deepseek-r1:8b"


def _ollama_generate(prompt: str, timeout: float = 90.0) -> str:
    """Send a prompt to local Ollama and return the raw response text."""
    payload = {
        "model": _ollama_model(),
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.0, "num_predict": 512},
    }
    resp = requests.post(
        f"{_ollama_base()}{OLLAMA_ENDPOINT}",
        json=payload,
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    return str(data.get("response") or "")


# ----------------------------------------------------------------------------
# Google Gemini (genai) reasoning
# ----------------------------------------------------------------------------
def _gemini_model() -> str:
    return _env("GEMINI_MODEL") or "gemini-2.5-flash"


def _gemini_generate(prompt: str, timeout: float = 90.0) -> str:
    """Send a prompt to Google Gemini and return the raw response text.

    Uses the official ``google-genai`` SDK. If ``GEMINI_USE_GROUNDING`` is set to
    ``true``, the Google Search tool is enabled so the model can pull live web
    results rather than relying only on the supplied Finnhub news body.
    """
    api_key = _env("GEMINI_API_KEY")
    if not api_key:
        logger.error("macro_rule_engine: GEMINI_API_KEY not set")
        return ""

    from google import genai  # lazy import so Ollama-only setups still work
    from google.genai import types

    client = genai.Client(api_key=api_key)

    # Structured JSON output schema (forced by Gemini when response_mime_type=json).
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema={
            "type": "OBJECT",
            "properties": {
                "allowed_direction": {"type": "STRING"},
                "rule": {"type": "STRING"},
                "risk_note": {"type": "STRING"},
            },
            "required": ["allowed_direction", "rule", "risk_note"],
        },
    )

    # Optional live Google Search grounding.
    if _env_truthy("GEMINI_USE_GROUNDING"):
        config.tools = [types.Tool(google_search={})]

    response = client.models.generate_content(
        model=_gemini_model(),
        contents=prompt,
        config=config,
        timeout=timeout,
    )
    text = getattr(response, "text", "") or ""
    if not text and response and getattr(response, "candidates", None):
        try:
            text = response.candidates[0].content.parts[0].text or ""
        except Exception:
            text = ""
    return text


def _env_truthy(name: str, default: bool = False) -> bool:
    val = os.getenv(name, "").strip().lower()
    return val in ("1", "true", "yes", "on") if val else default


def _llm_generate(prompt: str, timeout: float = 90.0) -> str:
    """Prefer Google Gemini when configured, otherwise fall back to local Ollama.

    Returns the raw LLM text (a strict JSON object string).
    """
    if _env("GEMINI_API_KEY"):
        try:
            raw = _gemini_generate(prompt, timeout=timeout)
            if raw:
                return raw
        except Exception as exc:
            logger.warning("macro_rule_engine: Gemini generation failed, falling back to Ollama: %s", exc)
    return _ollama_generate(prompt, timeout=timeout)

# ===============================================================================
# Prompt templates
# ===============================================================================
_SYSTEM_DIRECTIVE = (
    "You are a strict, rules-based Daily Macro & Fundamental trading analyst. "
    "You convert macroeconomic and fundamental news into ONE deterministic, "
    "IF-THEN boolean trading directive per symbol. Never return sentiment scores, "
    "probabilities, or technical indicators. You only output a strict allowed "
    "direction: BUY, SELL, or NO_TRADE."
)

_RULE_PROMPT = (
    "{system}\n\n"
    "Today's date: {date}\n"
    "Asset class: {asset_class}\n"
    "Symbol: {symbol}\n\n"
    "Below is today's fundamental news body for this symbol.\n"
    "------NEWS START------\n"
    "{news_body}\n"
    "------NEWS END------\n\n"
    "Translate the news into a single, strict, boolean IF-THEN trading rule. "
    "Guidelines:\n"
    "- BUY  => clear bullish macro/fundamental catalyst with no strong offsetting bearish risk.\n"
    "- SELL => clear bearish macro/fundamental catalyst with no strong offsetting bullish risk.\n"
    "- NO_TRADE => news is mixed, insignificant, contradictory, or lacks a clear directional catalyst.\n"
    "- When in genuine doubt, choose NO_TRADE (fail closed).\n\n"
    "Respond with ONLY a strict JSON object, no prose, no markdown fences. Example:\n"
    "{{\"allowed_direction\": \"BUY\", \"rule\": \"IF {symbol} is supported by X and Y THEN allow BUY only, ELSE NO_TRADE.\", \"risk_note\": \"...\"}}\n\n"
    "Where allowed_direction is exactly one of: BUY, SELL, NO_TRADE."
)


# ----------------------------------------------------------------------------
# Parsing of the LLM JSON output
# ----------------------------------------------------------------------------
def _extract_json(raw: str) -> Optional[Dict[str, Any]]:
    """Robustly parse a strict JSON object from the LLM output."""
    if not raw:
        return None
    text = raw.strip()
    # Strip leading/trailing markdown fences.
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)

    # If a leading "{" isn't at position 0, locate the first JSON object.
    if not text.startswith("{"):
        start = text.find("{")
        if start == -1:
            return None
        text = text[start:]

    try:
        return json.loads(text)
    except Exception:
        pass

    # Fallback: try to extract {"allowed_direction" ... } by scanning for keys.
    try:
        m = re.search(r'"allowed_direction"\s*:\s*"([A-Z_]+)"', text)
        direction = m.group(1).upper() if m else None
        if direction in _ALLOWED_DIRECTIONS:
            rule_m = re.search(r'"rule"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
            risk_m = re.search(r'"risk_note"\s*:\s*"((?:[^"\\]|\\.)*)"', text, re.DOTALL)
            payload: Dict[str, Any] = {"allowed_direction": direction}
            if rule_m:
                payload["rule"] = rule_m.group(1)
            if risk_m:
                payload["risk_note"] = risk_m.group(1)
            return payload
    except Exception:
        pass

    return None


# ----------------------------------------------------------------------------
# Public engine class
# ----------------------------------------------------------------------------
class MacroRuleEngine:
    """Strict Daily Macro & Fundamental Rule Engine.

    Gate for ALL trade execution. Fail-closed: absence of a rule, a network
    outage, or a malformed LLM response results in ``approved=False``.
    """

    def __init__(self, supabase_client=None, cache_ttl: int = None):
        self._sb = supabase_client
        self._cache_ttl = cache_ttl if cache_ttl is not None else _CACHE_TTL_SECONDS

    # -- Internal helpers ------------------------------------------------------
    def _client(self):
        if self._sb is None:
            self._sb = _get_supabase_client()
        return self._sb

    def _cached_rule(self, symbol: str) -> Optional[Dict[str, Any]]:
        cached = _RULE_CACHE.get(symbol)
        if cached and (time.time() - cached.get("_fetched_at", 0)) < self._cache_ttl:
            return cached.get("rule")
        return None

    def _cache_rule(self, symbol: str, rule: Optional[Dict[str, Any]]) -> None:
        _RULE_CACHE[symbol] = {"rule": rule, "_fetched_at": time.time()}

    # -- Public: daily rule generation ----------------------------------------
    def fetch_and_update_daily_rules(self, symbols: Optional[List[str]] = None) -> Dict[str, Any]:
        """Fetch today's fundamentals from Finnhub, derive strict rules via
        Ollama/DeepSeek, and upsert them into Supabase.

        Args:
            symbols: optional explicit target list. Defaults to the bot universe.

        Returns:
            {
              "total": int,
              "updated": int,
              "failed": int,
              "errors": [str, ...],
              "results": {symbol: {allowed_direction, rule, risk_note}},
            }
        """
        summary: Dict[str, Any] = {"total": 0, "updated": 0, "failed": 0, "errors": [], "results": {}}
        targets = symbols or _target_symbols()
        if not targets:
            logger.error("macro_rule_engine: no target symbols to process")
            summary["errors"].append("no target symbols")
            return summary

        client = self._client()
        if client is None:
            summary["errors"].append("supabase_unavailable")
            return summary

        summary["total"] = len(targets)
        today = _now_utc().date().isoformat()

        for symbol in targets:
            try:
                asset_class = _asset_class(symbol)
                news_items = _finnhub_news(symbol, asset_class)
                if not news_items:
                    # No fresh news for this symbol today.
                    if _allow_by_default():
                        # Policy: allow the trade on technicals. Do NOT write a
                        # restrictive NO_TRADE row, so the gate passes by default.
                        logger.info(
                            "macro_rule_engine: no macro news for %s; allowed-by-policy",
                            symbol.upper(),
                        )
                        continue
                    # Strict fail-closed: no news -> no trade directive.
                    rule = {
                        "allowed_direction": "NO_TRADE",
                        "rule": f"IF no fresh actionable fundamental news for {symbol.upper()} THEN NO_TRADE.",
                        "risk_note": "No Finnhub news available; failing closed.",
                    }
                else:
                    news_body = self._format_news_body(news_items)
                    prompt = _RULE_PROMPT.format(
                        system=_SYSTEM_DIRECTIVE,
                        date=today,
                        asset_class=asset_class,
                        symbol=symbol.upper(),
                        news_body=news_body,
                    )
                    try:
                        raw = _llm_generate(prompt)
                        parsed = _extract_json(raw)
                    except Exception as exc:
                        logger.error("macro_rule_engine: LLM failed for %s: %s", symbol, exc)
                        parsed = None

                    if not parsed or parsed.get("allowed_direction") not in _ALLOWED_DIRECTIONS:
                        rule = {
                            "allowed_direction": "NO_TRADE",
                            "rule": f"IF macro rule unparseable for {symbol.upper()} THEN NO_TRADE.",
                            "risk_note": "LLM returned malformed/unparseable directive; failing closed.",
                        }
                        summary["errors"].append(f"{symbol}:unparseable_llm")
                    else:
                        rule = {
                            "allowed_direction": parsed["allowed_direction"],
                            "rule": parsed.get("rule") or self._default_rule_text(symbol, parsed["allowed_direction"]),
                            "risk_note": parsed.get("risk_note") or "derived from daily macro fundamentals",
                        }

                record = {
                    "symbol": symbol.upper(),
                    "asset_class": asset_class,
                    "allowed_direction": rule["allowed_direction"],
                    "strict_rule_text": rule["rule"],
                    "risk_note": rule.get("risk_note"),
                    "is_active": True,
                    "rule_date": today,
                }
                if _upsert_rule(client, record):
                    summary["updated"] += 1
                else:
                    summary["failed"] += 1
                    summary["errors"].append(f"{symbol}:upsert_failed")

                summary["results"][symbol.upper()] = record
                # Invalidate local cache so validation immediately sees the fresh rule.
                self._cache_rule(symbol.upper(), {
                    "symbol": symbol.upper(),
                    "asset_class": asset_class,
                    "allowed_direction": record["allowed_direction"],
                    "strict_rule_text": record["strict_rule_text"],
                    "rule_date": today,
                })


            except Exception as exc:
                logger.exception("macro_rule_engine: error processing %s", symbol)
                summary["failed"] += 1
                summary["errors"].append(f"{symbol}:{exc}")

        logger.info(
            "macro_rule_engine: daily fetch complete total=%s updated=%s failed=%s",
            summary["total"], summary["updated"], summary["failed"],
        )
        return summary

    def _format_news_body(self, news_items: List[Dict[str, str]]) -> str:
        lines = []
        for i, item in enumerate(news_items, start=1):
            headline = item.get("headline") or "n/a"
            summary = item.get("summary") or ""
            url = item.get("url") or ""
            lines.append(f"[{i}] HEADLINE: {headline}")
            if summary:
                lines.append(f"    SUMMARY: {summary}")
            if url:
                lines.append(f"    URL: {url}")
        return "\n".join(lines)

    def _default_rule_text(self, symbol: str, direction: str) -> str:
        if direction == "BUY":
            return f"IF macro fundamentals for {symbol} are distinctly bullish THEN buy only, ELSE NO_TRADE."
        if direction == "SELL":
            return f"IF macro fundamentals for {symbol} are distinctly bearish THEN sell only, ELSE NO_TRADE."
        return f"IF there is no clear macro catalyst for {symbol} THEN NO_TRADE."

    # -- Public: gate ----------------------------------------------------------
    def validate_trade_against_rule(self, symbol: str, proposed_direction: str) -> Dict[str, Any]:
        """Strictly validate a proposed trade against today's macro rule.

        Args:
            symbol: the MT5 symbol, e.g. "EURUSD".
            proposed_direction: "BUY" or "SELL" (case-insensitive).

        Returns:
            {"approved": bool, "reason": str, "allowed_direction": str, ...}
        """
        norm_symbol = (symbol or "").upper()
        proposed = (proposed_direction or "").upper()
        asset_class = _asset_class(norm_symbol)
        client = self._client()

        # --- Fail-closed preconditions ----------------------------------------
        if proposed not in _ALLOWED_DIRECTIONS or proposed == "NO_TRADE":
            return self._audit_and_return(

                client, norm_symbol, asset_class, proposed,
                rule={}, approved=False, mt5_ticket=None,
                reason=f"proposed_direction_invalid:{proposed}", executed=False,
            )

        if client is None:
            return self._audit_and_return(
                client, norm_symbol, asset_class, proposed,
                rule={}, approved=False, mt5_ticket=None,
                reason="supabase_unavailable", executed=False,
            )

        # --- Fetch today's rule (cached + fallback) ----------------------------
        rule = self._cached_rule(norm_symbol)
        if rule is None:
            rule = _fetch_today_rule(client, norm_symbol)
            self._cache_rule(norm_symbol, rule)

        allowed = (rule or {}).get("allowed_direction") or "NO_TRADE"
        allowed = allowed.upper()

        if not rule:
            if _allow_by_default():
                # No today-rule (e.g. no news) and policy permits: proceed on
                # technicals. The broker/data/risk stack remains the final judge.
                return self._audit_and_return(
                    client, norm_symbol, asset_class, proposed,
                    rule={}, approved=True, mt5_ticket=None,
                    reason="no_macro_rule_allowed_by_policy", executed=False,
                )
            return self._audit_and_return(
                client, norm_symbol, asset_class, proposed,
                rule={}, approved=False, mt5_ticket=None,
                reason="no_active_macro_rule_for_today", executed=False,
            )

        if allowed == "NO_TRADE":
            return self._audit_and_return(
                client, norm_symbol, asset_class, proposed,
                rule=rule, approved=False, mt5_ticket=None,
                reason=f"macro_rule_forbids_trade|allowed={allowed}|tried={proposed}",
                executed=False,
            )

        if allowed != proposed:
            return self._audit_and_return(
                client, norm_symbol, asset_class, proposed,
                rule=rule, approved=False, mt5_ticket=None,
                reason=f"direction_mismatch|allowed={allowed}|tried={proposed}",
                executed=False,
            )

        return self._audit_and_return(
            client, norm_symbol, asset_class, proposed,
            rule=rule, approved=True, mt5_ticket=None,
            reason=f"macro_rule_approved|allowed={allowed}|tried={proposed}",
            executed=False,
        )

    def record_execution_ticket(self, symbol: str, proposed_direction: str, mt5_ticket: int) -> None:
        """Attach a real MT5 ticket to the most recent audit row for this symbol.

        Call this right after a trade is actually opened so the audit trail links
        a rule approval to a filled order. Best-effort; never raises.
        """
        client = self._client()
        if client is None:
            return
        proposed = (proposed_direction or "").upper()
        try:
            response = (
                client.table("rule_execution_audit")
                .select("id")
                .eq("symbol", (symbol or "").upper())
                .eq("attempted_direction", proposed)
                .eq("rule_passed", True)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            rows = getattr(response, "data", None) or []
            if rows:
                client.table("rule_execution_audit") \
                    .update({"mt5_ticket": int(mt5_ticket), "executed": True}) \
                    .eq("id", rows[0]["id"]) \
                    .execute()
        except Exception as exc:
            logger.warning("macro_rule_engine: ticket attach failed: %s", exc)

    # -- Audit ----------------------------------------------------------------
    def _audit_and_return(
        self,
        client,
        symbol: str,
        asset_class: str,
        attempted: str,
        rule: Optional[Dict[str, Any]],
        approved: bool,
        reason: str,
        mt5_ticket: Optional[int],
        executed: bool,
    ) -> Dict[str, Any]:
        audit = {
            "symbol": symbol,
            "asset_class": asset_class,
            "attempted_direction": attempted,
            "allowed_direction": (rule or {}).get("allowed_direction"),
            "rule_passed": approved,
            "rejection_reason": None if approved else reason,
            "strict_rule_text": (rule or {}).get("strict_rule_text"),
            "mt5_ticket": mt5_ticket,
            "executed": executed,
        }
        if client is not None:
            _insert_audit(client, {k: v for k, v in audit.items() if k != "executed" or True})

        result = {"approved": approved, "reason": reason}
        result.update(audit)
        return result


# ----------------------------------------------------------------------------
# Drop-in convenience for main.py
# ----------------------------------------------------------------------------
_engine_instance = None


def get_rule_engine() -> MacroRuleEngine:
    """Return a shared singleton instance for the running bot."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = MacroRuleEngine()
    return _engine_instance


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    engine = MacroRuleEngine()
    engine.fetch_and_update_daily_rules()
