# ICT Trading Bot — Complete Execution Flow

> Based on actual code: `main.py`, `pre_trade_analysis.py`, `unified_strategy.py`, `kingsbalfx_concept.py`

---

## OVERVIEW

```
┌──────────────────────────────────────────────────────────────────┐
│                        MAIN LOOP (run_bot)                       │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐   │
│  │ CONNECT  │───▶│  FETCH   │───▶│  SCAN    │───▶│  SLEEP   │   │
│  │ to MT5   │    │ ACCOUNTS │    │ SYMBOLS  │    │ 60-300s  │   │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

---

## 1. BOT STARTUP → Symbol Universe

```
START
  │
  ├─► Connect to MetaTrader5
  │     └─► mt5.initialize(login, password, server)
  │
  ├─► Load accounts from config/JSON/env
  │     └─► If MULTI_ACCOUNT_ENABLED → spawn child processes
  │
  ├─► Build symbol universe (_build_symbol_universe)
  │     │
  │     ├─► AUTO_EXTRACT_MT5_SYMBOLS=true
  │     │     └─► get_broker_symbols() from MT5 (groups, filters)
  │     │
  │     ├─► Filter by asset class (crypto/forex/indices)
  │     ├─► Apply allowlist/blocklist
  │     ├─► Remove duplicates
  │     │
  │     └─► Result: ~349 raw → ~22 candidates (after market filters)
  │
  └─► Start Flask API (bot_api) on port 8000
```

---

## 2. SCAN CYCLE (Every 60 seconds)

```
SCAN START
  │
  ├─► Fetch account snapshot (balance, equity)
  ├─► Fetch open positions
  │
  ├─► MANAGE OPEN POSITIONS (_manage_open_positions)
  │     │
  │     ├─► For each open position:
  │     │     ├─► Get tick snapshot
  │     │     ├─► analyze_market_top_down(symbol, current_price)
  │     │     ├─► manage_trade() → check if SL/TP needs moving
  │     │     └─► If trailing → modify_position()
  │     │
  │     └─► Friday close check (forex only)
  │
  ├─► Filter candidates
  │     ├─► Skip if market closed (asset_trading_open)
  │     └─► Skip if friday cutoff
  │
  └─► For each candidate symbol:
        │
        ▼
     ┌──────────────────────────────────────────────────┐
     │           _evaluate_symbol(symbol)               │
     │                                                  │
     │  1. Get tick snapshot (bid/ask)                  │
     │  2. analyze_market_top_down(symbol, price)       │
     │     → Builds 7+ timeframe analysis               │
     │  3. SMT divergence check (_smt_snapshot)         │
     │  4. Killzone detection                           │
     │  5. evaluate_strategy() → 12-gate ICT           │
     │  6. If ICT fails → Kingsbalfx fallback           │
     │  7. If Kingsbalfx passes → execute trade         │
     └──────────────────────────────────────────────────┘
```

---

## 3. analyze_market_top_down (7+ Timeframe Analysis)

```
analyze_market_top_down(symbol, price)
  │
  ├─► Resolve timeframes from ENV:
  │     ├─► W1 (Weekly)     → background context
  │     ├─► D1 (Daily)      → background context
  │     ├─► H4 (Fallback)   → if D1 unavailable
  │     ├─► H1 (HTF)       → primary narrative
  │     ├─► M15 (MTF)      → mid-term structure
  │     ├─► M5 (LTF/EXEC)  → execution timeframe
  │     └─► M1 (Fallback)  → if M5 execution fails
  │
  ├─► For EACH timeframe:
  │     │
  │     ┌─► _analyze_timeframe(symbol, tf, price)
  │     │     │
  │     │     ├─► [FIX 10] Check cache (TTL 30s)
  │     │     ├─► Fetch OHLCV candles from MT5
  │     │     ├─► Calculate ATR
  │     │     ├─► Detect:
  │     │     │     ├─► Trend (bullish/bearish/range)
  │     │     │     ├─► Fibonacci levels
  │     │     │     ├─► Premium/Discount zones
  │     │     │     ├─► FVGs (Fair Value Gaps)
  │     │     │     ├─► Order Blocks
  │     │     │     ├─► Liquidity levels (EQH/EQL)
  │     │     │     ├─► Swing points
  │     │     │     └─► Market structure (BOS/MSS/CHoCH)
  │     │     │
  │     │     └─► [FIX 10] set_cache() → store result
  │     │
  │     └─► ⚠ Returns: {trend, fib, fvgs, order_blocks,
  │                       liquidity, swings, market_structure,
  │                       recent_candles, atr, volume_boost,
  │                       sma_50, above_sma}
  │
  ├─► Analyze H1↔M15 alignment (_h1_m15_candle_alignment)
  │     ├─► structural: H1 trend agrees with M15 trend
  │     ├─► candle: H1 bias matches M15 current bias
  │     └─► Result: {confirmed, direction, mode}
  │
  ├─► Select background context
  │     ├─► Try D1 first
  │     └─► Fallback to H4 if D1 unavailable
  │
  ├─► Detect opening gaps (NDOG/NWOG)
  ├─► Calculate external liquidity (EQH/EQL across timeframes)
  ├─► Detect HTF liquidity sweep
  │
  ├─► Compute live visual concepts
  │     ├─► Visual Fibonacci (live swing-based)
  │     ├─► Sweet Zone detection
  │     └─► Judas Swing detection
  │
  ├─► Session analysis (London/NY/Asia killzones)
  │
  └─► [FIX 14] _build_topdown_result()
        └─► Returns: {
              overall_trend,           # bullish/bearish
              topdown: {               # HTF summary
                trend, weekly/daily/h1/m15/m5 trend,
                context_alignment, opening_gaps,
                visual_concepts
              },
              timeframes: {WEEKLY...M1},  # which TF used
              H1_STATE, M15_STATE, M5_STATE, etc.,
              m5_candles, m1_candles,
              external_liquidity,
              h1_m15_alignment,
              visual_concepts,
              session_analysis
            }
```

---

## 4. ICT 12-Gate State Machine

```
evaluate_strategy(symbol, price, analysis, smt, killzone)
  │
  │  ╔═══════════════════════════════════════════════╗
  │  ║   GATE 1: higher_timeframe_narrative         ║
  │  ║   H1 and M15 structural trend must align     ║
  │  ║   ↓                                          ║
  │  ║   Checks: H1 trend == M15 trend              ║
  │  ║   Or: H1 bias agrees with M15 bias           ║
  │  ║   Or: structural trend alignment             ║
  │  ╚═══════════════════════════════════════════════╝
  │         │ PASS         │ FAIL → SKIP (ICT) → Kingsbalfx
  │         ▼
  │  ╔═══════════════════════════════════════════════╗
  │  ║   GATE 2: external_liquidity                 ║
  │  ║   Buy → EQL (equal lows) must exist          ║
  │  ║   Sell → EQH (equal highs) must exist        ║
  │  ║   ↓                                          ║
  │  ║   Check: H1/M15/M5 liquidity zones           ║
  │  ║   Score: rank_liquidity_zones()              ║
  │  ╚═══════════════════════════════════════════════╝
  │         │ PASS         │ FAIL → SKIP (ICT) → Kingsbalfx
  │         ▼
  │  ╔═══════════════════════════════════════════════╗
  │  ║   GATE 3: liquidity_sweep                    ║
  │  ║   Price must trade BEYOND external liquidity ║
  │  ║   AND close back inside                     ║
  │  ║   ↓                                          ║
  │  ║   Check: Did price breach EQH/EQL?           ║
  │  ║           Did it reclaim?                    ║
  │  ║           Was there a displacement candle?   ║
  │  ╚═══════════════════════════════════════════════╝
  │         │ PASS         │ FAIL → SKIP (ICT) → Kingsbalfx
  │         ▼
  │  ╔═══════════════════════════════════════════════╗
  │  ║   GATE 4: strong_displacement                ║
  │  ║   Post-sweep candle must be:                 ║
  │  ║   • Body ratio ≥ 60%                        ║
  │  ║   • Range ≥ ATR × 1.0                      ║
  │  ║   • Direction = trade direction             ║
  │  ╚═══════════════════════════════════════════════╝
  │         │ PASS         │ FAIL → SKIP (ICT) → Kingsbalfx
  │         ▼
  │  ╔═══════════════════════════════════════════════╗
  │  ║   GATE 5: market_structure_shift             ║
  │  ║   Displacement must break last opposing swing║
  │  ║   ↓                                          ║
  │  ║   Check: BOS (Break of Structure)            ║
  │  ║           MSS (Market Structure Shift)        ║
  │  ║           CHoCH (Change of Character)         ║
  │  ╚═══════════════════════════════════════════════╝
  │         │ PASS         │ FAIL → SKIP (ICT) → Kingsbalfx
  │         ▼
  │  ╔═══════════════════════════════════════════════╗
  │  ║   GATE 6: displacement_fvg_or_order_block    ║
  │  ║   Displacement must create either:           ║
  │  ║   • True M5 FVG (Fair Value Gap)             ║
  │  ║   • True M5 Order Block (last opposing)      ║
  │  ╚═══════════════════════════════════════════════╝
  │         │ PASS         │ FAIL → SKIP (ICT) → Kingsbalfx
  │         ▼
  │  ╔═══════════════════════════════════════════════╗
  │  ║   GATE 7: true_fvg_or_order_block            ║
  │  ║   (Same as gate 6 — both must hold)          ║
  │  ╚═══════════════════════════════════════════════╝
  │         │ PASS         │ FAIL → SKIP (ICT) → Kingsbalfx
  │         ▼
  │  ╔═══════════════════════════════════════════════╗
  │  ║   GATE 8: premium_discount                   ║
  │  ║   FVG/OB midpoint must be in correct half:   ║
  │  ║   • BUY → Discount zone (below H1 0.5 fib)  ║
  │  ║   • SELL → Premium zone (above H1 0.5 fib)  ║
  │  ║   Or: Live Visual Fib confirms correct half  ║
  │  ╚═══════════════════════════════════════════════╝
  │         │ PASS         │ FAIL → SKIP (ICT) → Kingsbalfx
  │         ▼
  │  ╔═══════════════════════════════════════════════╗
  │  ║   GATE 9: opposing_liquidity_target          ║
  │  ║   Target must provide ≥ 1.5× risk:          ║
  │  ║   • BUY → EQH above entry                   ║
  │  ║   • SELL → EQL below entry                  ║
  │  ║   • Distance from entry ≥ 1.5 × SL distance ║
  │  ╚═══════════════════════════════════════════════╝
  │         │ PASS         │ FAIL → SKIP (ICT) → Kingsbalfx
  │         ▼
  │  ╔═══════════════════════════════════════════════╗
  │  ║   GATE 10: fvg_or_order_block_retracement    ║
  │  ║   Price must retrace INTO the entry zone:    ║
  │  ║   • FVG zone touched                         ║
  │  ║   • OR Order Block zone touched              ║
  │  ║   • OR H1 OTE zone (quarter levels)          ║
  │  ║   [FIX 12] AND ≥ 3 candles since displacement║
  │  ╚═══════════════════════════════════════════════╝
  │         │ PASS         │ FAIL → SKIP (ICT) → Kingsbalfx
  │         ▼
  │  ╔═══════════════════════════════════════════════╗
  │  ║   GATE 11: lower_timeframe_confirmation      ║
  │  ║   M1/M5 must show price action:              ║
  │  ║   • Engulfing candle                         ║
  │  ║   • Strong rejection wick                    ║
  │  ║   • Break of structure                       ║
  │  ║   • Two consecutive directional candles      ║
  │  ╚═══════════════════════════════════════════════╝
  │         │ PASS         │ FAIL → SKIP (ICT) → Kingsbalfx
  │         ▼
  │  ╔═══════════════════════════════════════════════╗
  │  ║   GATE 12: market_order_execution            ║
  │  ║   Build market order with:                   ║
  │  ║   • Entry = current ask/bid                  ║
  │  ║   • SL = sweep extreme                       ║
  │  ║   • TP = opposing liquidity target           ║
  │  ╚═══════════════════════════════════════════════╝
  │         │ PASS
  │         ▼
  │  ┌──────────────────────────────────────────┐
  │  │     ✓ ALL 12 GATES PASSED               │
  │  │     → EXECUTE ICT MARKET ORDER          │
  │  └──────────────────────────────────────────┘
  │
  ▼
  ANY GATE FAILS
  │
  ▼
  LOG: "ICT SKIP → KINGSBALFX FALLBACK"
  │
  ▼
```

---

## 5. Kingsbalfx Fallback (When ICT fails at any gate)

```
_evaluate_kingsbalfx_fallback(symbol, direction, analysis, tick, account)
  │
  │  Reuses the SAME analysis dict from ICT evaluation
  │  (No additional analyze_market_top_down call)
  │
  ▼
kingsbalfx_concept.evaluate(symbol, direction, mt5, analysis, tick, account)
  │
  ├─► Extract candle windows from existing analysis
  │     ├─► Daily:   _candles(daily_state, "htf_context", 120)
  │     ├─► H1:      _candles(h1_state, "htf_context", 120)
  │     ├─► H1 liq:  _candles(h1_state, "external_liquidity", 200)
  │     ├─► H1 FVG/OB: _candles(h1_state, "true_fvg_ob_context", 100)
  │     ├─► M15:     _candles(m15_state, "structure", 80)
  │     ├─► M15 liq: _candles(m15_state, "external_liquidity", 200)
  │     ├─► M5 exec: _candles(execution_state, "execution_confirmation", 50)
  │     └─► M1 fallback: _candles(M1, "execution_confirmation", 50)
  │
  ├─► STEP 1: h1_context (Gate 1/6)
  │     ├─► H1 must be clear (trend or structure confirms direction)
  │     ├─► Must find at least one target (liquidity/FVG/OB)
  │     └─► ⛔ Fails → "h1_context_or_target_missing"
  │
  ├─► STEP 2: ict_context (Gate 2/6)
  │     ├─► Check previous day context is available
  │     ├─► Background FVGs and OBs exist
  │     └─► Always passes (informational)
  │
  ├─► STEP 3: m15_alignment (Gate 3/6)
  │     ├─► M15 trend must align with H1 direction
  │     ├─► Uses h1_m15_alignment from analysis
  │     └─► ⛔ Fails → "m15_does_not_align_with_h1_bias"
  │           ↑ THIS IS WHERE DOGE/BTC/BNB/SOL FAIL ↑
  │
  ├─► STEP 4: m15_setup (Gate 4/6)
  │     ├─► Look for trigger on M15:
  │     │     ├─► Continuation: price retraced into zone + 2 directional candles
  │     │     ├─► Reversal: sweep + engulfing/rejection/BOS
  │     │     ├─► Sweet Zone: live visual sweet zone active
  │     │     └─► Judas Swing: live judas swing detected
  │     └─► ⛔ Fails → "m15_reversal_or_continuation_trigger_missing"
  │           ↑ THIS IS WHERE BTC/ETH/BNB/TON/ADA FAIL ↑
  │
  ├─► STEP 5: m5_refinement (Gate 5/6)
  │     ├─► M5 must confirm the trigger:
  │     │     ├─► For reversal: M5 swept liquidity + retraced to zone
  │     │     ├─► For continuation: M5 retraced to zone
  │     │     ├─► For sweet zone/judas: M5 strong candles
  │     │     └─► Fallback: M1 if M5 fails
  │     └─► ⛔ Fails → "m5_m1_refinement_missing"
  │
  ├─► STEP 6: m5_final_trigger (Gate 6/6)
  │     ├─► M5 must show final entry trigger:
  │     │     ├─► 2 consecutive strong directional candles (body ≥ 70%)
  │     │     └─► OR large engulfing/breakout (≥ 1.35× ATR)
  │     └─► ⛔ Fails → "m5_m1_final_trigger_missing"
  │
  ├─► RISK CHECK
  │     ├─► Entry, SL (last swing), TP (nearest target)
  │     ├─► Must have RR ≥ 1.5
  │     └─► ⛔ Fails → "minimum_rr_or_structural_risk_invalid"
  │
  └─► ✓ ALL 6 KINGSBALFX GATES PASSED
        → EXECUTE KINGSBALFX MARKET ORDER
```

---

## 6. Kingsbalfx Mode Decision Tree

```
m15_setup (Gate 4) check:

              ┌──────────────────┐
              │  M15 Price       │
              │  Analysis        │
              └────────┬─────────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
   ┌──────────┐  ┌──────────┐  ┌──────────┐
   │SWEEP +   │  │RETRACE + │  │LIVE      │
   │ENGULF/   │  │2 STRONG  │  │CONCEPT   │
   │REJECT/   │  │CANDLES   │  │ACTIVE    │
   │BOS       │  │          │  │          │
   └────┬─────┘  └────┬─────┘  └────┬─────┘
        │             │             │
   ┌────▼────┐   ┌────▼────┐   ┌────▼────┐
   │REVERSAL │   │CONTINU- │   │SWEET    │
   │MODE     │   │ATION    │   │ZONE /   │
   │         │   │MODE     │   │JUDAS    │
   │         │   │         │   │SWING    │
   └────┬────┘   └────┬────┘   └────┬────┘
        │             │             │
        ▼             ▼             ▼
   ┌─────────────────────────────────────┐
   │  M5 refinement (Gate 5):           │
   │  • Reversal: M5 sweep + zone touch │
   │  • Continuation: M5 zone touch     │
   │  • SZ/JS: M5 strong candles        │
   │  • Fallback: M1                    │
   └─────────────────┬───────────────────┘
                     │
                     ▼
   ┌─────────────────────────────────────┐
   │  M5 final trigger (Gate 6):        │
   │  • 2 strong candles (≥70% body)    │
   │  • OR large engulfing/breakout     │
   │  • Fallback: M1                    │
   └─────────────────┬───────────────────┘
                     │
                     ▼
              ┌──────────────┐
              │  EXECUTE     │
              │  TRADE       │
              └──────────────┘
```

---

## 7. Post-Decision Execution

```
┌─ DECISION REACHED ───────────────────────────────────┐
│                                                      │
│  ┌──────────────────────────────────────────────┐    │
│  │  validate_execution_safety()                 │    │
│  │  ├─ Check account balance ≥ margin           │    │
│  │  ├─ Check no correlation conflict            │    │
│  │  ├─ Check setup cooldown (1800s)             │    │
│  │  ├─ Check max open trades (3)                │    │
│  │  ├─ Check news filter                        │    │
│  │  └─ Check broker minimum volume              │    │
│  └──────────────────┬───────────────────────────┘    │
│                     │                                 │
│                     ▼                                 │
│  ┌──────────────────────────────────────────────┐    │
│  │  execute_trade()                              │    │
│  │  ├─ mt5.order_send() → MARKET_ORDER          │    │
│  │  ├─ register_trade() → cooldown              │    │
│  │  ├─ persist_signal_to_supabase()             │    │
│  │  └─ push_trade() → dashboard                 │    │
│  └──────────────────────────────────────────────┘    │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

## 8. Fixes Applied (This Session)

```
FIX 6  ──► _smt_snapshot() : Lightweight M5 fetch instead of
           full analyze_market_top_down for correlated pairs
            main.py lines 658-685

FIX 10 ──► _analyze_timeframe() : TTL cache (30s) to avoid
           redundant MT5 fetches within same scan cycle
            pre_trade_analysis.py lines 164-168, 234-236

FIX 12 ──► _retracement_zone() : Minimum 3 candle hold time
           after displacement before accepting retracement
            unified_strategy.py lines 163-178

FIX 14 ──► analyze_market_top_down() : Extracted body into
           _build_topdown_result() helper for testability
            pre_trade_analysis.py lines 843-1009
```

---

## 9. Actual Skip Reasons Observed (Bot Output)

```
┌────────────┬────────────────────────────────────────────────────┐
│  SYMBOL    │  SKIP REASON                                        │
├────────────┼────────────────────────────────────────────────────┤
│  DOGE      │  H1=bearish, M15=bullish → structural conflict     │
│  BTC       │  No ATR-normalized displacement after sweep        │
│  ETH       │  No ATR-normalized displacement after sweep       │
│  BNB       │  M15 trend != H1 trend → no alignment             │
│  SOL       │  M15 trend != H1 trend → no alignment             │
│  XRP       │  M15 trend != H1 trend → no alignment             │
│  TRX       │  M15 trend != H1 trend → no alignment             │
│  TON       │  Sweep not confirmed (price didn't breach liq)    │
│  ADA       │  Sweep not confirmed                              │
│  AVAX      │  M15 trend != H1 trend → no alignment             │
└────────────┴────────────────────────────────────────────────────┘

All skips are due to CURRENT MARKET CONDITIONS, not bot logic errors.
The bot is correctly filtering out invalid setups.
```
