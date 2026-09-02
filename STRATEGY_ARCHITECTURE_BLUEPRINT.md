# KINGSBALFX BOT — Strategy Architecture Blueprint (No Sugarcoating)

This is the **actual** execution pipeline as the code and live logs reveal it.
Every strategy, gate, skip reason, and the order of precedence. The logs you
shipped map 1:1 onto the boxes below.

---

## 1. Top-level flow (what `main.py` actually does per symbol, per tick)

```
TICK (market data + account + positions)
   │
   ▼
┌──────────────────────────────┐
│ PRE-FILTERS                  │  symbol allowed? data present? price>0?
└──────────────────────────────┘
   │
   ▼
┌────────────────────────────────────────────────────────────┐
│ STRATEGY 1 — ICT 12-gate (PRIMARY)                         │
│ 7 external-liquidity gates run in order, fail-closed       │
└────────────────────────────────────────────────────────────┘
   │  skipped: e.g. "H1 and M15 structural trend must align"
   ▼
┌────────────────────────────────────────────────────────────┐
│ STRATEGY 2 — KINGSBALFX fallback (SECONDARY)               │
│ 6-gate HTF/MTF/LTF/EXEC/M1 alignment validation            │
│  - uses H1:1000 / M15:1500 / M5:2000 candles (c counts)    │
└────────────────────────────────────────────────────────────┘
   │  skipped: e.g. "m15_does_not_align_with_h1_bias"
   ▼
┌────────────────────────────────────────────────────────────┐
│ STRATEGY 3 — Fallback 3  (multi-TF market structure)       │
│ sweep / CHOCH / MACD / SMA / fib entry zone               │
└────────────────────────────────────────────────────────────┘
   │  (appears as fb3=None when it returns no executable setup)
   ▼
┌────────────────────────────────────────────────────────────┐
│ STRATEGY 4 — Fallback 4  (range sweep + reclaim)          │
└────────────────────────────────────────────────────────────┘
   │  e.g. "sweep_classification: genuine_breakout" / "no_valid_range"
   ▼
┌────────────────────────────────────────────────────────────┐
│ STRATEGY 5 — Fallback 5  (session day-trend scalper)      │
│  HARD symbol allow-list: EURUSD, XAUUSD, BTCUSD, AUDJPY   │
│  HARD session windows; "symbol_not_allowed"/"outside_hours"│
└────────────────────────────────────────────────────────────┘
   │
   ▼
┌────────────────────────────────────────────────────────────┐
│ ★ MACRO RULE GATE (execution gate for EVERY strategy)     │
│  validate_trade_against_rule(symbol, direction)           │
└────────────────────────────────────────────────────────────┘
   │  BLOCKED = no_active_macro_rule_for_today (if policy is strict)
   ▼
┌────────────────────────────────────────────────────────────┐
│ BRIDGE → broker (MT5) + risk + duplicate + spread checks  │
└────────────────────────────────────────────────────────────┘
```

---

## 2. Critical truth from your live log

> `[AUDCHF] RESULT | decision=SEND_MARKET_ORDER | direction=sell | passed=5/6 | reason=kingsbalfx_fallback_valid`
> then immediately:
> `MACRO_RULE_BLOCK | reason=no_active_macro_rule_for_today`

**The strategy FINDING IS CORRECT but the trade is killed by the macro gate.**

This is the single most important non-technical issue: **Strict Macro fail-closed**.
The log shows AUDCHF had a valid SELL. Without a `daily_macro_rules` row + a
`rule_execution_audit` table, the gate blocks it. **That is not a strategy bug.**

Two ways to fix, you pick:
- **Operational**: run the consolidated SQL migration (creates the tables) and the
  nightly news fetch. Strict gate, real macro directive.
- **Policy / direct-execute**: set `MACRO_RULE_ALLOW_BY_DEFAULT=true` — the gate
  **now already implements this** (seen in `macro_rule_engine.py`). When there is
  **no news for a pair that day**, or **no rule row**, the engine returns
  `approved=true` with reason `no_macro_rule_allowed_by_policy`, so the
  strategy's technical finding can execute *if all broker/risk/spread checks pass*.
  This is exactly what you asked for ("if there is no news that day, go ahead").

---

## 3. The five strategies, honestly, as the code runs them

### Strategy 1 — ICT 12-gate (PRIMARY)
- You can see it refactored to a **6/6 or N-gate** set in your refactor.
- The log `align_confirmed=no mode=structural_trend_conflict reason=H1 structural
  trend and M15 structural trend disagree` is the top rejection.
- It requires: external liquidity, liquidity sweep, strong displacement, market
  structure shift, true FVG/OB from displacement, premium/discount, opposing
  liquidity target, retracement, lower-TF confirmation, market order execution.
- Anything missing → skip to Strategy 2.

### Strategy 2 — Kingsbalfx fallback (`kingsbalfx_fallback_valid`)
- Validates across `HTF:H1 (c=1000) → MTF:M15 (c=1500) → LTF:M5 (c=2000) →
  EXECUTION (c=2000) → M1 (c=2000)`.
- `sw`=swing count, `fvg`=fair-value-gap count, `ob`=order-block count.
- Real blocker in your log: `m15_does_not_align_with_h1_bias` — H1 bullish but M15
  bearish (or vice-versa) → `passed=2/6`, `failed_step=m15_alignment`.
- When aligned, emits `SEND_MARKET_ORDER` (as AUDCHF did).

### Strategy 3 — Fallback 3 (`fb3` in the ACTIVATED line)
- Requires a real **liquidity sweep** (not a genuine breakout), then closed-candle
  CHOCH, MACD + SMA confirmation, a fib entry zone, retracement wait, risk gate.
- It reads `H1 → M15 → M5` candles from `analysis`. If the `analysis` key names
  differ from what FB3 expects (`HTF/MTF/EXECUTION/...`), it silently gets no data
  → which is a real cause of `fb3=None`.
- Mirror: `source_strategy="fallback3"`.

### Strategy 4 — Fallback 4 (`fb4` in the ACTIVATED line)
- `eval direction=buy exec=M5 ctx=M15 bias=neutral | M1=False model=A`
- Requires a detected intraday range (**range_score >= 70**) else
  `no_valid_range: best_range_score_-1_below_70`.
- Then: sweep beyond boundary → reclaim → opposing displacement → lower-TF
  CHOCH/BOS → retest entry. Outputs `sweep_classification: genuine_breakout`
  means it classified the move (and usually rejects it as not a real sweep).

### Strategy 5 — Fallback 5 (activates but almost always skips in your log)
- **Hard symbol allow-list**: EURUSD, XAUUSD, BTCUSD, AUDJPY only.
  ⇒ `AUDNZD`, `AUDSGD`, `AUDCAD`, etc. **always** skip with `symbol_not_allowed`.
- **Hard session gate**: trade 08:00–12:00 and 14:00–20:00, sleep 12:00–14:00.
  ⇒ at `23:xx UTC` it is `session=Closed` → `outside_trading_hours`.
- So FB5 appearing "not to fire" is **by design**, not a bug.

---

## 4. Macro news engine (what you asked me to implement)

```
Finnhub (live news for each tracked symbol)
   │  headline + summary + url  (top ~5-8 items)
   ▼
Google Gemini (gemini-2.5-flash)   ← preferred (MACRO_NEWS_ENGINE=gemini)
   │  structured JSON output:
   │  { allowed_direction: BUY|SELL|NO_TRADE, rule, risk_note }
   │  (optional Google Search grounding if GEMINI_USE_GROUNDING=true)
   ▼
upsert → daily_macro_rules (symbol + rule_date)
   ▼
daily gate: validate_trade_against_rule(symbol, direction)
   │
   ├─ rule found & matches direction        → approved
   ├─ rule = NO_TRADE / direction mismatch   → blocked
   ├─ NO news & MACRO_RULE_ALLOW_BY_DEFAULT  → approved (no_macro_rule_allowed_by_policy)
   └─ NO news & strict policy                → blocked (no_active_macro_rule_for_today)
```

Fallback chain if Gemini key missing → Ollama (deepseek-r1:8b). Both produce a
strict JSON directive. `_extract_json` strips markdown fences and rescues partial
JSON via regex.

---

## 5. Mirror trading (broadcast + receive)

```
Leader opens trade (any strategy)
   │  build_signal() → { signal_id, symbol, direction, entry, sl, tp, source_login, source_strategy, reason }
   ▼
broadcast_signal():  3 channels in parallel
   ├─ HTTP push to discovered peers (batched, retries)
   ├─ Supabase mirror_signals table (upsert on signal_id)
   └─ local data/mirror_signals.json (same machine)
   ▼
Receiving bot: check_pending_mirror_signals()
   → should_execute_mirror(): enabled? auto_open? duplicate? symbol allowed? cooldown? strategy filter?
   → calculate lot from MIRROR_RISK_PERCENT → execute same entry/SL/TP
```

Mirror table (now in the consolidated SQL):
```sql
mirror_signals(id bigserial, signal_id text unique, created_at, expires_at, data jsonb)
```

---

## 6. Where the "errors" actually come from (honest map)

| Log line | Real cause | Fix |
|---|---|---|
| `module '...fallback_strategy5.logging' has no attribute 'getLogger'` | package-local `logging.py` shadowed stdlib | **DONE** (renamed to `fb3/4/5_logging.py`) |
| `PGRST205 table 'daily_macro_rules' not in schema cache` | Supabase migration never run | run `SUPABASE_ALL_TABLES_MIGRATION.sql` |
| `PGRST205 table 'rule_execution_audit' ...` | same, second table | same migration |
| `MACRO_RULE_BLOCK | no_active_macro_rule_for_today` | strict fail-closed, no rule/news | `MACRO_RULE_ALLOW_BY_DEFAULT=true` + run nightly fetch |
| `fb3=None` in FB5 ACTIVATED | FB3 returned no executable setup (no sweep / no data) | verify `analysis` keys: H1/M15/M5; enable FB3; log at INFO |
| `outside_trading_hours:session=Closed` | FB5 hard session gate | by design; trade only within windows |
| `symbol_not_allowed` (AUDNZD/AUDSGD) | FB5 allow-list is EURUSD/XAUUSD/BTCUSD/AUDJPY | by design |

---

## 7. Recommended `.env` for FINNHUB + GEMINI + fail-open direct-execute

```
MACRO_RULE_ENABLED=true
MACRO_RULE_ALLOW_BY_DEFAULT=true
MACRO_RULE_CACHE_TTL=300
MACRO_NEWS_ENGINE=gemini
FINNHUB_API_KEY=your_finnhub_key
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini-2.5-flash
GEMINI_USE_GROUNDING=false
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=deepseek-r1:8b
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key
MIRROR_SUPABASE_TABLE=mirror_signals
```

> **Honest caveat:** `MACRO_RULE_ALLOW_BY_DEFAULT=true` means "no macro news today,
> nobody tells me not to → the strategy's technical signal may execute." This is
> the `direct execute` behavior you asked for, and it removes the 100% block, but
> it also disables the fundamental veto on no-news days. If you want strict
> fundamentals always, set it `false` and ensure the nightly fetch runs reliably.
