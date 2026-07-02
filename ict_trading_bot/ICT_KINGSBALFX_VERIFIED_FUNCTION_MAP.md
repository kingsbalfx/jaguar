# Verified ICT + Kingsbalfx Function Map

Verified date: 2026-06-30

This report is based on static AST import reachability from `main.py`, `strategy/unified_strategy.py`, `kingsbalfx_concept.py`, `strategy/pre_trade_analysis.py`, and `backtest/strategy_runner.py`, plus compile/import/test validation.

## Validation

- Whole project Python compile: PASS
- Strategy module import check: PASS, 26 strategy modules imported
- Test suite: PASS, 31 tests passed
- Diff whitespace check: PASS
- Live import graph from `main.py`: 39 Python modules reachable
- Strict ICT core import graph: 8 Python modules reachable
- Kingsbalfx direct import graph: 2 Python modules reachable, with input supplied by live `main.py` analysis

## Live Trading Flow

1. `main.py` starts API, connects MT5, extracts symbols, scans batches.
2. `main.py::_evaluate_symbol()` gets tick and calls `strategy/pre_trade_analysis.py::analyze_market_top_down()`.
3. `main.py::_smt_snapshot()` builds SMT advisory data where a correlation exists.
4. `main.py` calls `strategy/unified_strategy.py::evaluate_strategy()`.
5. ICT either confirms all 12 gates or returns SKIP at the first failed gate.
6. If ICT skips, `main.py::_evaluate_kingsbalfx_fallback()` calls `kingsbalfx_concept.py::evaluate()`.
7. If ICT or Kingsbalfx returns an executable setup, `execution/pre_trade_validator.py::validate_execution_safety()` checks broker safety.
8. `execution/mt5_connector.py::calculate_volume_for_risk()` sizes risk using broker specs.
9. `execution/trade_executor.py::execute_trade()` sends order.
10. `risk/trade_management.py::manage_trade()` manages open trades.

## Strict ICT 12 Gates

| Gate | State | Main Function/File | Required Result |
|---|---|---|---|
| 1 | Higher timeframe narrative | `strategy/unified_strategy.py::_narrative()` | H1 structural trend agrees with M15 structural trend; current-H1 M15 candle bias is only evidence/fallback when structure is incomplete |
| 2 | External liquidity | `strategy/unified_strategy.py::_external_liquidity()`, `ict_concepts/liquidity.py::rank_liquidity_zones()` | Entry-side external liquidity exists |
| 3 | Liquidity sweep | `strategy/setup_confirmations.py::liquidity_sweep_or_swing()` | Sweep and close back inside external liquidity |
| 4 | Strong displacement | `strategy/unified_strategy.py::evaluate_strategy()` | Post-sweep candle body >= 60% and range >= ATR |
| 5 | MSS/BOS | `strategy/unified_strategy.py::_market_structure_shift()`, `market_structure/structure.py` | Opposing swing break or supplied/local structure confirms |
| 6 | Displacement FVG or OB | `ict_concepts/fvg.py::detect_displacement_fvg()`, `ict_concepts/order_blocks.py::find_true_order_block()` | Either a three-candle displacement FVG or final opposing OB exists |
| 7 | True FVG or OB | `strategy/unified_strategy.py::evaluate_strategy()` | At least one accepted true model exists; FVG and OB are not both required |
| 8 | Premium/discount | `strategy/unified_strategy.py`, `ict_concepts/fib.py`, `ict_concepts/fib_visual.py` | FVG or OB is in correct half by H1 Fib or live Visual Fib |
| 9 | Opposing liquidity target | `ict_concepts/liquidity.py::rank_liquidity_zones()` | Target liquidity gives at least 1.5R |
| 10 | Retracement | `strategy/unified_strategy.py::_retracement_zone()` and `_ote_retracement_zone()` | Price touches FVG, OB, or OTE zone |
| 11 | LTF confirmation | `strategy/setup_confirmations.py::price_action_setup()` | M1/M5 rejection, engulfing, or momentum confirmation |
| 12 | Market execution plan | `strategy/unified_strategy.py::evaluate_strategy()` | Market order plan with entry, SL, TP |

## Kingsbalfx Fallback Flow

`kingsbalfx_concept.py::evaluate()` runs only after ICT SKIP from `main.py`.

| Step | Function/File | Required Result |
|---|---|---|
| Context load | `_build_analysis_context()` | Uses `previous_day_context`, H1, M15, M5, EXECUTION states |
| Bias | `_h1_m15_alignment()`, `_bias_from_state()` | H1 and M15 agree, or direction is recoverable from state |
| H1 targets | `_liquidity_targets()`, `_fvg_zones()`, `_ob_zones()`, `_ote_zone()` | Liquidity/FVG/OB/OTE target or zone exists |
| M15 refinement | `_continuation_signal()`, `_reversal_signal()`, live Sweet Zone/Judas checks | Continuation, reversal, Sweet Zone, or Judas mode is live |
| M5 trigger | `_two_consecutive_directional()` or `_large_engulfing_or_breakout()` | Two strong candles or one large confirming candle |
| Risk | `_last_swing_stop()`, `_select_target()` | Structural SL and target >= 1.5R |
| Broker sizing | `mt5_connector.calculate_volume_for_risk()` | Lot size from broker tick/volume specs |
| Return | `KingsbalfxDecision` via `_decision_dict()` | `confirmed/executable` and request for `main.py` |

## LIVE Files Reached From `main.py`

- `main.py`: live orchestrator, scanning, ICT first, Kingsbalfx fallback, execution dispatch.
- `bot_api.py`: Flask API thread for bot state/dashboard control.
- `bot_state.py`: running/restart/metrics state.
- `config/smt_correlations.py`: correlated symbols for SMT advisory.
- `config/symbol_mappings.py`: broker symbol aliases.
- `config/trading_pairs.py`: configured fallback symbol groups.
- `dashboard/bridge.py`: Supabase signal/trade/account persistence.
- `execution/mt5_connector.py`: MT5 connection, symbol extraction, symbol info, tick, positions, broker-aware sizing.
- `execution/pre_trade_validator.py`: spread, stop distance, margin, duplicate/correlation/account safety.
- `execution/trade_executor.py`: order send, modify, close.
- `fundamentals/news_api.py`, `fundamentals/news_filter.py`, `fundamentals/news_manual.py`: news/manual block support.
- `ict_concepts/fib.py`: Fib dealing range using only 0, 0.25, 0.5, 0.75, and 1 levels.
- `ict_concepts/fib_visual.py`: visual Fib zones, PDH/PDL, premium/discount zones.
- `ict_concepts/fvg.py`: FVG detection and qualification.
- `ict_concepts/judas_swing.py`: Judas sweep/reversal detection.
- `ict_concepts/liquidity.py`: equal highs/lows, sweep confirmation, target ranking.
- `ict_concepts/liquidity_analysis.py`: liquidity zone validation and premium/discount helper.
- `ict_concepts/market_structure.py`: MT5 structure wrapper.
- `ict_concepts/order_blocks.py`: true order block detection.
- `ict_concepts/smt.py`: SMT divergence detection.
- `ict_concepts/sweet_zone.py`: trend continuation Sweet Zone detection.
- `kingsbalfx_concept.py`: secondary fallback strategy after ICT skip.
- `market_structure/structure.py`: BOS/MSS/CHOCH structure engine.
- `multi_account_runner.py`: multi-account child process launch.
- `risk/market_condition.py`: market condition support.
- `risk/protection.py`: cooldown/duplicate setup protection.
- `risk/trade_management.py`: partials, breakeven, trailing management.
- `strategy/liquidity_filter.py`: session/sweep/displacement liquidity validation for pre-trade analysis.
- `strategy/pre_trade_analysis.py`: builds all timeframe analysis for ICT and Kingsbalfx.
- `strategy/setup_confirmations.py`: liquidity sweep, BOS/CHOCH, M1/M5 confirmation.
- `strategy/unified_strategy.py`: strict ICT 12-gate state machine.
- `utils/logger.py`: bot logging.
- `utils/mt5_credentials.py`: MT5 credential loading.
- `utils/persistent_json.py`: safe persistent JSON updates.
- `utils/sessions.py`: trading sessions, killzones, Friday rules.
- `utils/symbol_profile.py`: symbol class/profile/inference.
- `utils/user_profiles.py`: max trades/profile settings.

## Backtest-Active Files

- `backtest/strategy_runner.py`: uses `strategy/unified_strategy.py::evaluate_unified_setup()`.
- `backtest/metrics.py`: metrics for backtest engine.
- The backtest path also reaches `strategy/pre_trade_analysis.py`, `strategy/setup_confirmations.py`, `strategy/unified_strategy.py`, and the same ICT concept files used live.

## Advisory / Compatibility Strategy Files

These compile and import, but are not reached by live `main.py` or `backtest/strategy_runner.py` based on AST reachability:

- `strategy/amd_detector.py`: AMD pattern detector, available to `strategy/market_features.py`.
- `strategy/bias.py`: deterministic bias helpers, available for future shared use.
- `strategy/breakout.py`: strict breakout-retest compatibility strategy.
- `strategy/confirmation_system.py`: ratings/confirmation adapter, used by older intelligence modules.
- `strategy/entry_model.py`: lower-timeframe standalone entry adapter; not called by live `main.py`.
- `strategy/execution_planner.py`: structural execution planner adapter.
- `strategy/ict_execution_direct.py`: binary direct-execution compatibility helper.
- `strategy/ict_first_execution.py`: binary ICT-first compatibility helper.
- `strategy/ict_fvg.py`: strict ICT FVG helper strategy.
- `strategy/ict_setup_quality.py`: binary setup validation helper, test-covered.
- `strategy/market_features.py`: optional feature extractor for older/intelligence flows.
- `strategy/market_rhythm.py`: advisory rhythm/management context, not live execution gate.
- `strategy/probability_sync.py`: Supabase sync helper for audit data only.
- `strategy/probability_updater.py`: audit-only rule outcome recorder; not used for live decisions.
- `strategy/pure_rule_based_engine.py`: compatibility wrapper.
- `strategy/regime_classifier.py`: optional regime classifier.
- `strategy/rule_based_ict_trader.py`: 12-gate compatibility checker.
- `strategy/silver_bullet.py`: standalone Silver Bullet adapter through `entry_model.py`.
- `strategy/smt_filter.py`: optional SMT advisory filter.
- `strategy/strict_entry_validator.py`: backward-compatible binary entry validator.
- `strategy/turtle_soup_detector.py`: false-breakout detector, available to `market_features.py`.
- `strategy/unified_ict_engine.py`: test/compatibility re-export of unified strategy.

## Raw Execution Truth

- Live trade direction comes from H1/M15 alignment in `pre_trade_analysis.py` and `unified_strategy.py`.
- D1 is background context only; H4 is fallback background context when D1 context is missing/not actionable.
- SMT is advisory. If a pair has no SMT/correlation, live ICT is not automatically skipped.
- ICT is strict: first missing gate stops the setup.
- Kingsbalfx only runs after ICT skip.
- Kingsbalfx is not a replacement for ICT; it is a second binary fallback path.
- Broker lot sizing is from `execution/mt5_connector.py::calculate_volume_for_risk()`.
- Broker safety validation is from `execution/pre_trade_validator.py::validate_execution_safety()`.
- Execution is from `execution/trade_executor.py::execute_trade()`.
- Trade management is from `risk/trade_management.py::manage_trade()`.
