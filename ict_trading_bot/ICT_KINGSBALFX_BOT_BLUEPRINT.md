# ICT And Kingsbalfx Bot Blueprint

Generated from the current project code on 2026-06-28.

This document is an audit blueprint of how the bot actually works now. It is based on:

- Recursive import map from `main.py`.
- Recursive import map from `backtest/strategy_runner.py`.
- Direct review of the strategy, ICT concept, Kingsbalfx, execution, risk, session, symbol, Supabase, and test files.
- Validation commands listed at the end of this file.

## 1. Current Live Trading Flow

The live bot starts in:

```text
main.py
```

The live trading loop works like this:

```text
main.py
  -> starts Flask API thread
  -> connects to MT5
  -> builds symbol universe
  -> loops while bot_state says running
  -> gets account and open positions
  -> manages existing open trades
  -> closes non-crypto trades on Friday close rule
  -> filters symbols by market open and Friday entry rule
  -> scans symbols in batches
  -> for each symbol:
       get tick
       analyze top-down market context
       run strict ICT 12-state machine
       if ICT skips, run Kingsbalfx fallback
       validate broker safety
       execute market order if approved
       persist signal/trade to Supabase
```

The strict ICT strategy runs first. Kingsbalfx is only a secondary fallback after ICT returns skip.

## 2. Live Files Imported From `main.py`

These files are reachable from the current live `main.py` import graph:

```text
bot_api.py
bot_state.py
config/smt_correlations.py
config/symbol_mappings.py
config/trading_pairs.py
dashboard/bridge.py
execution/mt5_connector.py
execution/pre_trade_validator.py
execution/trade_executor.py
fundamentals/news_api.py
fundamentals/news_filter.py
fundamentals/news_manual.py
ict_concepts/fib.py
ict_concepts/fib_visual.py
ict_concepts/fvg.py
ict_concepts/judas_swing.py
ict_concepts/liquidity.py
ict_concepts/liquidity_analysis.py
ict_concepts/market_structure.py
ict_concepts/order_blocks.py
ict_concepts/smt.py
ict_concepts/sweet_zone.py
kingsbalfx_concept.py
main.py
market_structure/structure.py
multi_account_runner.py
risk/market_condition.py
risk/protection.py
risk/trade_management.py
strategy/liquidity_filter.py
strategy/pre_trade_analysis.py
strategy/setup_confirmations.py
strategy/unified_strategy.py
utils/logger.py
utils/mt5_credentials.py
utils/persistent_json.py
utils/sessions.py
utils/symbol_profile.py
utils/user_profiles.py
```

These are the files that matter for live trading behavior unless a separate script is run manually.

## 3. Backtest Strategy Files

`backtest/strategy_runner.py` imports the same strict strategy function:

```text
strategy/unified_strategy.py -> evaluate_unified_setup()
```

Backtest reachable files:

```text
backtest/metrics.py
backtest/strategy_runner.py
config/symbol_mappings.py
ict_concepts/fib.py
ict_concepts/fib_visual.py
ict_concepts/fvg.py
ict_concepts/judas_swing.py
ict_concepts/liquidity.py
ict_concepts/liquidity_analysis.py
ict_concepts/market_structure.py
ict_concepts/order_blocks.py
ict_concepts/sweet_zone.py
market_structure/structure.py
strategy/liquidity_filter.py
strategy/pre_trade_analysis.py
strategy/setup_confirmations.py
strategy/unified_strategy.py
utils/sessions.py
utils/symbol_profile.py
```

Meaning: the main backtest runner does not use a separate probability strategy. It builds analysis from historical MT5 candles, then calls the same strict ICT state machine.

## 4. Current Timeframe Model

The active lower-timeframe schedule is configured in `.env.example`:

```text
DAILY_TIMEFRAME=D1
DAILY_CONTEXT_FALLBACK_TIMEFRAME=H4
HTF_TIMEFRAME=H1
MTF_TIMEFRAME=M15
LTF_TIMEFRAME=M5
EXECUTION_TIMEFRAME=M5
```

Current meaning:

```text
D1  = previous daily candle background context only
H4  = background fallback only when D1 is unavailable or has no actionable background clue
H1  = highest active trading timeframe and trend/narrative
M15 = alignment and setup refinement against H1
M5  = execution structure and final trigger
M1  = extra lower-timeframe confirmation candles fetched for ICT confirmation support
```

Important: D1 and fallback H4 do not choose the trade direction by themselves. H1/M15 alignment chooses the active direction.

## 5. Configuration Files And Environment Inputs

### `.env.example`

Defines runtime controls:

- MT5 symbol extraction: `AUTO_EXTRACT_MT5_SYMBOLS`, `MT5_SYMBOL_GROUPS`, filters, allowlist, blocklist.
- Risk: `RISK_PER_TRADE`, `MAX_DAILY_LOSS_PERCENT`.
- Execution safety: `MAX_TICK_AGE_SECONDS`, `MAX_SPREAD_POINTS`, `SETUP_COOLDOWN_SECONDS`.
- Scanning: `SCAN_INTERVAL_SECONDS`, `SCAN_BATCH_SIZE`, `SCAN_BATCH_PAUSE_SECONDS`, `SCAN_WORKERS`.
- Logging: `STATE_LOG_MODE`, `SYMBOL_EVALUATION_LOGS`, `SYMBOL_SKIP_LOGS`.
- Timeframes: `DAILY_TIMEFRAME`, `DAILY_CONTEXT_FALLBACK_TIMEFRAME`, `HTF_TIMEFRAME`, `MTF_TIMEFRAME`, `LTF_TIMEFRAME`, `EXECUTION_TIMEFRAME`.
- Candle windows: `CANDLE_FETCH_PER_TIMEFRAME`, `HTF_CONTEXT_CANDLES`, `EXTERNAL_LIQUIDITY_CANDLES`, `STRUCTURE_CANDLES`, `TRUE_FVG_OB_CONTEXT_CANDLES`, `SMT_CANDLES`, `SWEEP_CANDLES`, `DISPLACEMENT_CANDLES`, `EXECUTION_CONFIRMATION_CANDLES`.
- Multi-account: `MULTI_ACCOUNT_ENABLED`, `ACCOUNT_1_LOGIN`, `ACCOUNT_2_LOGIN`, and account overrides.

### `config/trading_pairs.py`

Provides static configured symbols when MT5 auto extraction is off:

- Forex majors, minors, exotics.
- Metals.
- Crypto.
- Indices.
- Commodities.

### `config/symbol_mappings.py`

Maps broker-specific symbol alternatives:

- Crypto aliases like `BTCUSD`, `BTCUSDT`, `XBTUSD`, suffix variants.
- Metal aliases like `XAUUSD`, `GOLD`, `XAU/USD`.
- DXY aliases.
- Broker suffixes such as `.m`, `.raw`, `.pro`, `.ecn`, etc.

Used by:

- `main.py::_resolve_symbol()`
- `backtest/strategy_runner.py::_fetch_rates()`
- `utils/symbol_profile.py`

### `config/smt_correlations.py`

Defines SMT correlation pairs:

- Positive examples: `EURUSD/GBPUSD`, `XAUUSD/XAGUSD`, `BTCUSD/ETHUSD`, `NAS100/US500`.
- Inverse examples: `DXY/USDJPY`, `DXY/USDCHF`.

Used by `main.py::_smt_snapshot()`.

## 6. Symbol Universe Construction

Owned by:

```text
main.py::_build_symbol_universe()
execution/mt5_connector.py::get_broker_symbols()
utils/symbol_profile.py::infer_asset_class()
```

If `AUTO_EXTRACT_MT5_SYMBOLS=true`, the bot gets all broker symbols directly from MT5 using `mt5.symbols_get()`.

Then it filters:

- Unresolved symbols.
- Asset class if `MT5_SYMBOL_ASSET_CLASSES` is set.
- Allowlist.
- Blocklist.
- Duplicates.

If `AUTO_EXTRACT_MT5_SYMBOLS=false`, it uses either `SYMBOLS` from env or `TradingPairs.get_trading_pairs()`.

## 7. Market Data And Analysis Builder

Owned by:

```text
strategy/pre_trade_analysis.py
```

Main function:

```python
analyze_market_top_down(symbol, price, htf=None, mtf=None, ltf=None)
```

It fetches and builds analysis for:

- D1 background.
- H4 background fallback.
- H1 active HTF.
- M15 MTF alignment.
- M5 LTF/execution.
- M1 confirmation candles.

Each timeframe state includes:

- `trend`
- `fib`
- `discount`
- `premium`
- `fvgs`
- `order_blocks`
- `liquidity`
- `swings`
- `recent_candles`
- concept candle windows
- ATR
- volume boost
- SMA alignment
- live visual Fib context
- live Sweet Zone context
- live Judas Swing context

### Candle Windows

Configured by `_concept_candle_windows()`:

```text
fetch_per_timeframe          default 500
htf_context                  default 120
external_liquidity           default 200
structure                    default 80
true_fvg_ob_context          default 100
smt                          default 20
sweep                        default 20
displacement                 default 10
execution_confirmation       default 50
```

The bot fetches the larger history first, then each concept uses its own recent slice.

## 8. Background Context

Owned by:

```text
strategy/pre_trade_analysis.py::_previous_day_context()
strategy/pre_trade_analysis.py::_select_background_context()
```

D1 checks the previous daily candle as background first. If D1 has no candles, or if D1 has no actionable background clue, the bot falls back to H4 with the same context structure.

It records:

- Whether the selected background source is available.
- Selected source timeframe: `D1` or fallback `H4`.
- Whether fallback was used.
- Previous completed background candle direction.
- Previous completed background candle close.
- Whether that close is inside a true FVG.
- Whether that close is inside an order block.
- Whether that candle swept buy-side liquidity.
- Whether that candle swept sell-side liquidity.
- Whether that candle is chasing liquidity.
- Whether that candle is continuing the selected background trend.
- Whether that candle is reversing after a sweep.

Fallback to H4 happens when D1 has no candles or D1 has none of these actionable clues:

- FVG touch.
- OB touch.
- Buy-side or sell-side sweep.
- Liquidity chase.
- Trend continuation.
- Reversal after sweep.

This context is passed into ICT and Kingsbalfx evidence, but it does not replace H1/M15 direction.

## 9. Live Visual Concepts

Owned by:

```text
strategy/pre_trade_analysis.py::_visual_live_concepts()
ict_concepts/fib_visual.py
ict_concepts/sweet_zone.py
ict_concepts/judas_swing.py
```

The visual concepts now run in the active analysis path, not only in the parked direct-execution module.

They are calculated from:

```text
H1
M15
M5
```

Visual Fib:

- Uses the current active timeframe candles.
- Labels zones with the actual timeframe, such as `H1`, `M15`, or `M5`.
- Builds visual premium/discount from recent swing high/low and equilibrium.
- Uses the selected background D1/H4 candle for PDH/PDL-style references, avoiding live D1 leakage in backtest.
- Feeds strict ICT premium/discount evidence.

Sweet Zone:

- Detects clean continuation conditions.
- Requires strong same-direction candle behavior.
- Can allow Kingsbalfx continuation mode without waiting for a deep OB/FVG retracement.

Judas Swing:

- Detects purge of old highs/lows or selected background reference levels.
- Requires immediate reversal strength.
- Can allow Kingsbalfx reversal mode after a purge.

These concepts are exposed in:

```text
analysis["visual_concepts"]
analysis["HTF"]["visual_fib"]
analysis["HTF"]["sweet_zone"]
analysis["HTF"]["judas_swing"]
```

The same shape is produced by the live scanner and the backtest runner.

## 10. H1 And M15 Alignment

Owned by:

```text
strategy/pre_trade_analysis.py::_h1_m15_candle_alignment()
```

Rule:

```text
H1 is the highest trading timeframe.
H1 structural trend must align with M15 structural trend.
Current-H1 M15 candle bias is evidence/fallback only when structure is incomplete.
```

Implementation:

- Uses the last 3 H1 candles for H1 bias.
- Uses the M15 candles inside the current H1 parent candle, fallback to last 4 M15 candles.
- Confirms only if:
  - H1 bias is bullish or bearish.
  - M15 current-H1 bias equals H1 bias.
  - H1 trend equals that same bias.

Output direction:

```text
bullish -> buy
bearish -> sell
otherwise -> no direction
```

## 11. Strict ICT State Machine

Owned by:

```text
strategy/unified_strategy.py
```

Main function:

```python
evaluate_strategy(symbol, price, analysis, *, smt=None, killzone_active=False)
```

Wrapper:

```python
evaluate_unified_setup()
```

The ICT sequence is fixed:

```text
1. higher_timeframe_narrative
2. external_liquidity
3. liquidity_sweep
4. strong_displacement
5. market_structure_shift
6. displacement_fvg_or_order_block
7. true_fvg_or_order_block
8. premium_discount
9. opposing_liquidity_target
10. fvg_or_order_block_retracement
11. lower_timeframe_confirmation
12. market_order_execution
```

There is no probability score. It stops at the first missing state.

### ICT Gate 1: Higher Timeframe Narrative

Function:

```text
strategy/unified_strategy.py::_narrative()
```

Requires:

- `h1_m15_alignment.confirmed == True`
- direction must be `buy` or `sell`

Fallback if explicit alignment is absent:

- H1 trend and M15 trend must both be bullish or both bearish.

### ICT Gate 2: External Liquidity

Function:

```text
strategy/unified_strategy.py::_external_liquidity()
strategy/pre_trade_analysis.py::_external_liquidity()
ict_concepts/liquidity.py::rank_liquidity_zones()
```

External liquidity comes from active intraday timeframes:

```text
H1, M15, M5
```

For a buy, entry-side liquidity is sell-side liquidity below price (`EQL`).

For a sell, entry-side liquidity is buy-side liquidity above price (`EQH`).

If no entry-side external liquidity exists, ICT skips.

### ICT Gate 3: Liquidity Sweep

Function:

```text
strategy/setup_confirmations.py::liquidity_sweep_or_swing()
```

With supplied external liquidity, the bot checks the execution candles for:

- Sweep of the correct liquidity side.
- Close/reclaim back inside.
- Next candle is displacement in trade direction.
- Body ratio at least 60%.
- Records swept level, swept source, swept timeframe, sweep extreme, and displacement index.

### ICT Gate 4: Strong Displacement

Function:

```text
strategy/unified_strategy.py::evaluate_strategy()
```

Requires:

- Sweep says displacement is present.
- Displacement body ratio >= 0.60.
- Displacement candle range >= ATR up to that point.

### ICT Gate 5: MSS/BOS

Function:

```text
strategy/unified_strategy.py::_market_structure_shift()
market_structure/structure.py::analyze_market_structure()
market_structure/structure.py::structure_confirms_direction()
```

Uses the completed market-structure engine plus the displacement break:

- Buy: close breaks above the last opposing swing high, or completed structure confirms bullish BOS/MSS.
- Sell: close breaks below the last opposing swing low, or completed structure confirms bearish BOS/MSS.
- Evidence includes the supplied execution-timeframe structure and a local structure analysis from execution candles.

### ICT Gate 6: True FVG

Function:

```text
ict_concepts/fvg.py::detect_displacement_fvg()
```

Requires:

- Three-candle FVG.
- FVG must be created by the displacement candle.
- Displacement body ratio >= 60%.
- Displacement range >= ATR.
- Correct direction.
- Valid low/high gap.
- Tracks fresh, active, mitigated, mitigation index.

### ICT Gate 7: True Order Block

Function:

```text
ict_concepts/order_blocks.py::find_true_order_block()
```

Requires:

- Final opposing candle before displacement.
- Displacement candle is directional.
- Displacement body ratio >= 60%.
- OB body range becomes the zone.
- Tracks fresh/mitigated state.

### ICT Gate 8: Premium/Discount

Function:

```text
strategy/unified_strategy.py::evaluate_strategy()
ict_concepts/fib.py
```

Uses H1 fib equilibrium (`0.5`):

- Buy: executable FVG or OB midpoint must be in discount.
- Sell: executable FVG or OB midpoint must be in premium.

Only one of FVG or OB needs to be in the correct half.

### ICT Gate 9: Opposing Liquidity Target

Function:

```text
ict_concepts/liquidity.py::rank_liquidity_zones()
```

Requires target liquidity in the trade direction:

- Buy targets untaken EQH above price.
- Sell targets untaken EQL below price.

Target must provide at least 1.5R from the structural stop.

### ICT Gate 10: Retracement

Functions:

```text
strategy/unified_strategy.py::_retracement_zone()
strategy/unified_strategy.py::_ote_retracement_zone()
```

Current rule:

```text
Execution can use either:
- true FVG,
- true OB,
- or H1 OTE zone.
```

It does not require FVG + OB + OTE together.

FVG and OB can be touched anywhere inside their zone. The bot labels nearest 25%, 50%, or 75% reference level. It is not midpoint-only.

OTE uses only the approved quarter Fib levels from `ict_concepts/fib.py::ote_zone()`: buy uses 0.25-0.5 and sell uses 0.5-0.75.

### ICT Gate 11: Lower Timeframe Confirmation

Function:

```text
strategy/setup_confirmations.py::price_action_setup()
```

Checks MTF, LTF, and execution candles. ICT requires execution confirmation.

Patterns:

- Engulfing.
- Rejection.
- Momentum.
- Volume confirmation.

### ICT Gate 12: Market Order Execution

Function:

```text
strategy/unified_strategy.py::evaluate_strategy()
```

Creates a market order plan only after all previous 11 gates pass:

```text
entry = current price
sl = sweep extreme
tp = opposing external liquidity target
order_type = market
```

## 11. ICT Concept Detector Files

### `ict_concepts/liquidity.py`

Detects:

- Equal highs (`EQH`).
- Equal lows (`EQL`).
- Session metadata.
- Touch count.
- Separation between swings.
- Untaken flag.

Ranks target liquidity by:

- Touch count.
- Separation.
- Distance from current price.

### `ict_concepts/market_structure.py`

Live role:

- Fetches swings from MT5 candles.
- Calls `market_structure/structure.py` for the completed structure logic.
- Returns trend and full structure state to `strategy/pre_trade_analysis.py`.

### `market_structure/structure.py`

Completed reusable structure engine.

Detects:

- Normalized swing sequence.
- Higher high (`HH`).
- Higher low (`HL`).
- Lower high (`LH`).
- Lower low (`LL`).
- Break of structure (`BOS`).
- Change of character / market structure shift (`CHOCH`/`MSS`).
- Trend: bullish, bearish, or range.
- Last directional structure event.
- Whether structure confirms a requested buy/sell direction.

Used by:

- Live analysis: every H1/M15/M5 state gets `market_structure`.
- Strict ICT Gate 5: confirms MSS/BOS after sweep and displacement.
- Kingsbalfx H1 context: can confirm H1 directional structure.
- Kingsbalfx M15 setup: can confirm reversal after sweep.
- Backtest runner: produces the same structure fields as live trading.

### `ict_concepts/fvg.py`

Detects strict three-candle displacement FVG.

### `ict_concepts/order_blocks.py`

Detects the final opposing candle before displacement.

### `ict_concepts/fib.py`

Provides:

- Dealing range.
- Premium/discount.
- OTE quarter-level zone.
- Price zone helper.

### `ict_concepts/smt.py`

Provides deterministic SMT divergence detection. In current live `main.py`, SMT is advisory evidence only; it does not hard-block the strict ICT state machine.

## 12. Kingsbalfx Fallback Strategy

Owned by:

```text
kingsbalfx_concept.py
```

Main function:

```python
evaluate(symbol, direction, mt5_connector, analysis, tick, account, risk_percent=1.0, minimum_rr=1.5)
```

Called from:

```text
main.py::_evaluate_kingsbalfx_fallback()
```

Only runs when:

```text
ICT setup executable == False
```

Kingsbalfx does not replace ICT. It is a second-chance fallback for conditions the strict ICT 12-gate sequence rejects.

### Kingsbalfx State 1: Previous Day Context

Uses the selected background context from `strategy/pre_trade_analysis.py`:

```text
D1 first
-> H4 fallback only if D1 is unavailable or has no actionable background clue
```

Tracks:

- Previous completed background candle shift.
- Background source timeframe.
- Whether H4 fallback was used.
- Background FVG count.
- Background OB count.
- Previous-day/background context from `pre_trade_analysis.py`.

This state is recorded as background and currently passes if a direction exists.

### Kingsbalfx State 2: H1 Context

Requires:

- H1 direction is clear.
- H1/M15 alignment agrees when available.
- H1 market structure can confirm direction when candle bias and structure agree.
- A primary target exists.

Targets can be:

- H1 unswept liquidity.
- M15 unswept liquidity.
- M5 visible liquidity.
- H1 true FVG target.
- H1 true OB target.

### Kingsbalfx State 3: M15 Alignment

Requires:

- M15 agrees with H1 direction.
- If H1/M15 alignment object exists, it must confirm the same direction.

### Kingsbalfx State 4: M15 Setup

Four possible modes:

```text
continuation
reversal
sweet_zone
judas_swing
```

Continuation requires:

- Price touched a valid H1/M15 zone.
- Two directional M15 candles with body ratio at least 50%.

Reversal requires:

- M15 liquidity sweep.
- Engulfing, rejection, or BOS in trade direction.
- Or M15 sweep plus completed M15 market-structure confirmation in trade direction.

Sweet Zone requires:

- Live `analysis["visual_concepts"]["sweet_zone"]`.
- Direction must match H1/M15 trade direction.
- Sweet Zone must say `enter_now == True`.
- M5 must still confirm with strong candles or a large breakout.

Judas Swing requires:

- Live `analysis["visual_concepts"]["judas_swing"]`.
- Purge must be confirmed.
- Direction must match H1/M15 trade direction.
- Judas Swing must say `enter_now == True`.
- M5 must still confirm with strong candles or a large breakout.

Entry zones can be:

- H1 true FVG.
- H1 true OB.
- H1 quarter-level OTE.
- M15 true FVG.
- M15 true OB.
- M15 quarter-level OTE.

### Kingsbalfx State 5: M5 Refinement

For reversal:

- M5 must sweep liquidity.
- Price must retrace into the M15 zone.

For continuation:

- Price must retrace into the M15 zone.

### Kingsbalfx State 6: M5 Final Trigger And Risk Execution

Final trigger:

- Two strong M5 candles in trade direction with body ratio >= 70%, or
- One large engulfing/breakout candle.

Risk:

- Entry uses current ask for buy, current bid for sell.
- SL goes beyond last swing/opposing structure.
- TP uses selected H1/M15 liquidity or FVG/OB target.
- Minimum RR is 1.5.
- Lot size uses `mt5_connector.calculate_volume_for_risk()`.

If valid, request includes:

```text
strategy = kingsbalfx
order_type = market
```

## 13. Execution And Broker Safety

### Broker Connection And Specs

Owned by:

```text
execution/mt5_connector.py
```

Important functions:

- `connect()`
- `reconnect()`
- `get_broker_symbols()`
- `get_tick_snapshot()`
- `get_symbol_info()`
- `get_symbol_spec()`
- `get_account_snapshot()`
- `get_open_positions()`
- `calculate_volume_for_risk()`

`calculate_volume_for_risk()` is broker-aware:

- Uses `mt5.order_calc_profit()` for one-lot loss when possible.
- Falls back to tick size and tick value.
- Normalizes to volume step.
- Enforces min/max volume.
- Checks free margin using `mt5.order_calc_margin()`.

### Pre-Trade Safety

Owned by:

```text
execution/pre_trade_validator.py::validate_execution_safety()
```

Hard safety checks:

- Fresh tick.
- Spread <= `MAX_SPREAD_POINTS`.
- Volume within broker min/max.
- Correct buy/sell geometry.
- Stop and TP distance satisfy broker stop level.
- Free margin exists.
- Daily loss limit allows trade.
- No duplicate same-symbol same-direction position.

### Market Order Execution

Owned by:

```text
execution/trade_executor.py::execute_trade()
```

Rules:

- Only market orders allowed.
- Normalizes lot to broker step.
- Uses broker filling modes.
- Retries retryable retcodes.
- Returns open trade payload if MT5 accepts the order.

## 14. Trade Management

Owned by:

```text
risk/trade_management.py::manage_trade()
main.py::_manage_open_positions()
execution/trade_executor.py::modify_position()
execution/trade_executor.py::close_position()
```

Management behavior:

- Partial close 50% at initial TP.
- Move SL to breakeven at 0.5R.
- Trail behind:
  - fresh unmitigated OB,
  - mitigated FVG,
  - strong swing,
  - weak swing fallback.
- Never moves SL backward.

`main.py` calls this on every scan cycle before new entries.

## 15. Duplicate Setup And Daily Loss Protection

Owned by:

```text
risk/protection.py
```

Functions:

- `setup_identity()`
- `can_trade()`
- `register_trade()`
- `daily_loss_allows_trade()`

Purpose:

- Prevent repeated entry on the same symbol/direction/zone during cooldown.
- Track daily start equity.
- Block if daily loss exceeds `MAX_DAILY_LOSS_PERCENT`.

## 16. Sessions And Friday Rules

Owned by:

```text
utils/sessions.py
```

Sessions:

- London killzone: 07:00-10:00 UTC.
- New York killzone: 12:00-15:00 UTC.
- Asia: reference session only.

`intelligence_session_open()` returns London/New York unless `TRADE_ALL_SESSIONS=true`.

Market-open rules:

- Crypto trades 7 days.
- Forex/metals/other closed Saturday, Sunday before 22:00 UTC, Friday after 22:00 UTC.
- Friday new non-crypto entries blocked after `FRIDAY_ENTRY_CUTOFF_HOUR_UTC`.

`main.py::_friday_close()` closes non-crypto open positions after `FRIDAY_CLOSE_HOUR_UTC`.

## 17. SMT, News, And Correlation Status

### SMT

Owned by:

```text
main.py::_smt_snapshot()
ict_concepts/smt.py
config/smt_correlations.py
```

SMT is calculated and logged as advisory context. It does not hard-block ICT or Kingsbalfx in the current live path.

### News

Owned by:

```text
fundamentals/news_filter.py
fundamentals/news_api.py
fundamentals/news_manual.py
```

`news_allows_trade()` checks:

- Forex Factory JSON when enabled.
- Local `news_events.json` fallback if present.
- Manual `news_calendar.csv`.

In current `main.py`, news is added to `setup["advisories"]`. It is not a hard execution gate.

### Correlation Conflict

`main.py` contains `_correlation_conflict()`, but this helper is not called in the current live order path.

Meaning:

- SMT correlation is advisory.
- Hard correlation blocking is not active in the current live execution path.

## 18. API, Bot State, Supabase, And Multi-Account

### API

Owned by:

```text
bot_api.py
```

Endpoints:

- `/health`
- `/status`
- `/control`
- `/restart`
- `/webhook/tradingview`
- `/webhook/signals`

Auth:

- Uses `BOT_API_TOKEN`.

The API starts in a background thread from `main.py`.

### Bot State

Owned by:

```text
bot_state.py
```

Stores:

- running flag.
- restart request.
- connection status.
- account/metrics snapshot.
- recent logs.

### Supabase Bridge

Owned by:

```text
dashboard/bridge.py
```

Persists:

- account snapshots.
- bot logs.
- generated signals.
- trade records.

Also enforces optional user signal quota when configured.

### Multi-Account

Owned by:

```text
multi_account_runner.py
main.py::_launch_multi_account_children()
```

If `MULTI_ACCOUNT_ENABLED=true`, the main process becomes a supervisor and launches one child process per account.

Accounts can come from:

- Supabase `mt5_credentials`.
- Indexed env variables like `ACCOUNT_1_LOGIN`.
- `MULTI_ACCOUNT_ACCOUNTS_JSON`.
- `accounts.example.json`.

## 19. Backtesting And Approval

### Main Backtest Runner

Owned by:

```text
backtest/strategy_runner.py
```

It:

- Fetches MT5 historical candles.
- Builds the same analysis shape used live.
- Requires H1/M15/M5 candles for strategy evaluation.
- Uses D1 as background context and H4 as fallback if D1 is missing or has no actionable background clue.
- Calls `strategy.unified_strategy.evaluate_unified_setup()`.
- Simulates SL/TP outcome on future candles.
- Returns metrics from `backtest/metrics.py`.

This is the correct current backtest path for the strict ICT state machine.

### Setup Occurrence Reports

Owned by:

```text
backtest/setup_occurrence.py
```

It builds a setup signature and runs `run_strategy_backtest()` for the same strategy.

### Approval Profile

Owned by:

```text
backtest/approval.py::build_strategy_profile()
backtest/latest_approval.json
```

Current approval profile defaults:

```text
DAILY_TIMEFRAME default = D1
DAILY_CONTEXT_FALLBACK_TIMEFRAME default = H4
HTF_TIMEFRAME default = H1
MTF_TIMEFRAME default = M15
LTF_TIMEFRAME default = M5
```

`backtest/latest_approval.json` was regenerated with this profile:

```text
DAILY_TIMEFRAME=D1
DAILY_CONTEXT_FALLBACK_TIMEFRAME=H4
HTF_TIMEFRAME=H1
MTF_TIMEFRAME=M15
LTF_TIMEFRAME=M5
```

The regenerated file is a profile/report artifact with no symbol list. It is structurally correct for the new schedule. A real metrics-bearing approval should be regenerated inside a connected MT5 session with symbols supplied to `generate_latest_approval(symbols=...)`. If `AUTO_GENERATE_BACKTEST_APPROVAL=true` and a symbol-backed approval call sees zero occurrences, `ensure_backtest_approval()` now regenerates immediately instead of waiting for the refresh timer.

## 20. Important Non-Live Or Parked Files

These files exist but are not reachable from the current live `main.py` import graph:

```text
main_refactored.py
main.py.backup
strategy/entry_model.py
strategy/execution_planner.py
strategy/confirmation_system.py
strategy/ict_execution_direct.py
strategy/ict_first_execution.py
strategy/pure_rule_based_engine.py
strategy/rule_based_ict_trader.py
strategy/strict_entry_validator.py
strategy/probability_updater.py
strategy/probability_sync.py
strategy/pre_trade_analysis - Copy.py
risk/rule_based_risk_manager.py
risk/profitability_guard.py
risk/intelligence_system.py
risk/intelligent_execution.py
execution/order_router.py
execution/order_manager.py
ml/*
portfolio/allocator.py
dashboard/app.py
```

Some of these still contain old H4/D1 wording. Because they are not in the live `main.py` path, they do not control the current ICT/Kingsbalfx trading loop.

## 21. Current Known Gaps From The Audit

These are factual gaps from the current codebase:

1. Old historical approval JSON files in `backtest/` still contain profile data from earlier runs. The active `backtest/latest_approval.json` has been regenerated to D1/H4 background and H1/M15/M5 trading timeframes.
2. The regenerated `backtest/latest_approval.json` has no symbol metrics because it was regenerated as a profile artifact outside an initialized MT5 data session. Symbol-backed auto-generation now refreshes zero-occurrence reports when enabled.
3. SMT is advisory only in live execution.
4. News is advisory only in live execution.
5. `_correlation_conflict()` exists in `main.py` but is not currently called.
6. Several parked/non-live modules still reference old H4 logic. They are not part of the current live import path.

## 22. Validation Commands

The current validation set for this blueprint is:

```powershell
cd C:\Users\kingsbal\Documents\GitHub\jaguar\ict_trading_bot

.\.venv\Scripts\python.exe -m py_compile main.py strategy\pre_trade_analysis.py strategy\unified_strategy.py kingsbalfx_concept.py tests\test_ict_concepts.py tests\test_kingsbalfx_concept.py

.\.venv\Scripts\python.exe -m py_compile strategy\pre_trade_analysis.py strategy\unified_strategy.py kingsbalfx_concept.py backtest\strategy_runner.py backtest\approval.py

.\.venv\Scripts\python.exe -m py_compile ict_concepts\fib_visual.py ict_concepts\judas_swing.py ict_concepts\sweet_zone.py strategy\pre_trade_analysis.py strategy\unified_strategy.py kingsbalfx_concept.py backtest\strategy_runner.py main.py tests\test_ict_concepts.py tests\test_kingsbalfx_concept.py

.\.venv\Scripts\python.exe -m py_compile market_structure\structure.py ict_concepts\market_structure.py strategy\pre_trade_analysis.py strategy\unified_strategy.py kingsbalfx_concept.py backtest\strategy_runner.py tests\test_ict_concepts.py tests\test_kingsbalfx_concept.py

.\.venv\Scripts\python.exe -m pytest tests\test_ict_concepts.py tests\test_kingsbalfx_concept.py -q --tb=short

.\.venv\Scripts\python.exe -m pytest tests -q --tb=short
```

Latest validation result from this audit:

```text
py_compile: passed
patched module py_compile: passed
visual concept patched module py_compile: passed
market-structure patched module py_compile: passed
focused ICT/Kingsbalfx tests: 22 passed
full test suite: 31 passed
```

## 23. Summary Of The Actual Trading Logic

Strict ICT:

```text
D1 previous candle context, or H4 fallback background when D1 has no actionable clue
-> live Visual Fib/Sweet Zone/Judas Swing snapshot on H1/M15/M5
-> H1/M15 structural trend alignment, with current-H1 M15 candle bias as evidence/fallback only
-> H1/M15/M5 external liquidity
-> liquidity sweep and reclaim
-> displacement
-> MSS/BOS
-> displacement-created M5 FVG
-> final opposing M5 OB
-> premium/discount
-> opposing liquidity target with at least 1.5R
-> retracement into true FVG or true OB or H1 OTE
-> M1/M5 price-action confirmation
-> broker-safe market order
```

Kingsbalfx fallback:

```text
Runs only after ICT skip
-> D1 previous day background, or H4 fallback background when D1 has no actionable clue
-> live Visual Fib/Sweet Zone/Judas Swing context
-> H1 context and target
-> M15 alignment
-> M15 continuation, reversal, Sweet Zone, or Judas Swing setup
-> M5 refinement
-> M5 final trigger
-> broker-aware lot sizing
-> minimum 1.5R
-> market order with strategy='kingsbalfx'
```

Execution:

```text
Strategy approval
-> duplicate setup cooldown
-> broker safety validation
-> MT5 market order
-> Supabase/dashboard persistence
-> trade management on later scan cycles
```
