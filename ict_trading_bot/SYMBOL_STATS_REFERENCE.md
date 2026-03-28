# Quick Reference: Per-Symbol Conditional Backtesting

## Architecture Overview

```
Main Trading Loop (main.py)
    ↓
Signal Detected → Check Execution Route
    ├─ Route 1: Weighted Confirmation (direct)
    ├─ Route 2: 4-Confirmation (direct)
    └─ Route 3: Conditional Backtest
        ├─ should_skip_backtest(symbol, score)
        │   └─ Check: symbol_stats.json
        │       ├─ win_rate >= 60%?
        │       └─ avg_confidence >= 7.0?
        │           ├─ YES → Execute (skip backtest)
        │           └─ NO → Require backtest
        │
        └─ Execute Trade
            ├─ Monitor SL/TP hits
            ├─ SL hit → record_symbol_trade(symbol, win=False)
            ├─ TP hit → record_symbol_trade(symbol, win=True)
            └─ Save to data/symbol_stats.json
```

## File Locations & Functions

### `risk/protection.py`
```python
# Check if backtest can be skipped
from risk.protection import should_skip_backtest
skip = should_skip_backtest("GBPJPY", 7.2)  # → True/False

# Update symbol confidence tracking
from risk.protection import update_symbol_confidence
update_symbol_confidence("GBPJPY", win=True, confirmation_score=7.2)

# Registration (existing)
from risk.protection import register_trade, can_trade
```

### `risk/symbol_stats.py`
```python
# Record trade outcome when it closes
from risk.symbol_stats import record_symbol_trade
record_symbol_trade("GBPJPY", win=True, confirmation_score=7.2)

# Track backtest decisions
from risk.symbol_stats import record_backtest_skip, record_backtest_required
record_backtest_skip("GBPJPY")
record_backtest_required("GBPJPY")

# Get summary for logging (compact or detailed)
from risk.symbol_stats import get_symbol_summary
compact = get_symbol_summary(compact=True)  # "GBPJPY(5-3:62%)"
detailed = get_symbol_summary(compact=False)  # Full table

# Management
from risk.symbol_stats import load_symbol_stats, save_symbol_stats, reset_symbol_stats
stats = load_symbol_stats()  # Load from disk
save_symbol_stats(stats)  # Save to disk
reset_symbol_stats()  # Clear all
reset_symbol_stats("GBPJPY")  # Clear one symbol
```

### `main.py` Integration Points

**Line ~680**: Execution route decision
```python
if should_skip_backtest(original_symbol, confirmation_score_value):
    execution_route = "symbol_confidence_high"
    # Skip backtest!
else:
    # Require backtest
```

**Line ~925**: SL/TP hit detection
```python
if sl_hit:
    record_symbol_trade(original_symbol, win=False, confirmation_score=0.0)
elif tp_hit:
    record_symbol_trade(original_symbol, win=True, confirmation_score=confirmation_score_value)
```

**Line ~450**: Heartbeat logging
```python
symbol_summary = get_symbol_summary()
heartbeat_message += f" Symbol Performance: {symbol_summary}"
```

## Configuration Parameters

In `.env`:
```bash
# Master switch
CONDITIONAL_BACKTESTING_ENABLED=true

# Thresholds (AND logic - BOTH must be true to skip)
CONFIDENCE_SCORE_FOR_BACKTEST_SKIP=7.0
SYMBOL_WIN_RATE_FOR_BACKTEST_SKIP=0.60

# Execution settings
TRADE_COOLDOWN_SECONDS=300
MAX_TRADES_PER_SYMBOL=2

# Feature flags
INDEPENDENT_SYMBOL_EXECUTION=true
TRACK_SYMBOL_CONFIDENCE=true
```

## Data Flow: Trade Lifecycle

```
SIGNAL DETECTED
├─ symbol: "GBPJPY"
├─ confirmation_score: 7.2
└─ direction: "buy"

    ↓

EXECUTION DECISION
├─ Call: should_skip_backtest("GBPJPY", 7.2)
│   ├─ Load: stats = load_symbol_stats()
│   ├─ Check: stats["GBPJPY"]["win_rate"] >= 0.60? ✓
│   ├─ Check: stats["GBPJPY"]["avg_confidence"] >= 7.0? ✓
│   └─ Result: True (skip backtest!)
│
└─ execution_route = "symbol_confidence_high"

    ↓

TRADE EXECUTES
├─ Entry: 1.3250
├─ SL: 1.3200
├─ TP: 1.3300
└─ Status: "open"

    ↓

TRADE MANAGEMENT LOOP
├─ Get: live_price = 1.3275
├─ Check: 1.3275 <= 1.3200? NO
├─ Check: 1.3275 >= 1.3300? NO
├─ Status: Still open...
│
├─ ... (time passes) ...
│
├─ Get: live_price = 1.3305
├─ Check: 1.3305 <= 1.3200? NO
├─ Check: 1.3305 >= 1.3300? YES! ← HIT TP!
└─ Status: Closing...

    ↓

TRADE CLOSED - WIN
├─ Call: record_symbol_trade("GBPJPY", win=True, confirmation_score=7.2)
│   ├─ Load: stats = load_symbol_stats()
│   ├─ Add trade: stats["GBPJPY"]["total_trades"] += 1  → 6
│   ├─ Add win: stats["GBPJPY"]["wins"] += 1  → 4
│   ├─ Append score: stats["GBPJPY"]["confidence_scores"].append(7.2)
│   ├─ Update: avg = mean(last_50_scores)  → 7.15
│   ├─ Update: win_rate = 4/6  → 0.667 (66.7%)
│   └─ Save: json.dump(stats, file)
│
├─ Log: "[trade_closed] Trade closed by TP on GBPJPY"
└─ Heartbeat will show: "GBPJPY(4-2:67%)"

    ↓

NEXT SIGNAL ON GBPJPY
├─ Call: should_skip_backtest("GBPJPY", new_confirmation_score)
│   ├─ Check: win_rate (0.667) >= 0.60? ✓ YES
│   ├─ Check: avg_confidence (7.15) >= 7.0? ✓ YES
│   └─ Result: True (skip backtest again!)
└─ Continue learning...
```

## Common Development Tasks

### Add a new threshold parameter
1. Update `.env`: `NEW_PARAM=value`
2. Update `risk/protection.py`: Read in `should_skip_backtest()`
3. Test: `python main.py`

### Modify symbol decision logic
1. Edit `risk/protection.py`, function `should_skip_backtest()`
2. Current logic: `AND` operator between win_rate and avg_confidence
3. Example change: Add `total_trades_required >= 5`

### Add new stat tracking
1. Edit `risk/symbol_stats.py`, function `record_symbol_trade()`
2. Example: Track max_consecutive_wins, max_drawdown, etc.
3. Update `get_symbol_summary()` to display new stat

### Debug a symbol's decision
```python
# In main.py or test script:
from risk.symbol_stats import load_symbol_stats
from risk.protection import should_skip_backtest

stats = load_symbol_stats()
symbol = "GBPJPY"

if symbol in stats:
    s = stats[symbol]
    print(f"Trades: {s['total_trades']}")
    print(f"Win rate: {s['win_rate']:.2%}")
    print(f"Avg confidence: {s['avg_confidence']:.2f}")
    print(f"Will skip backtest: {should_skip_backtest(symbol, 7.2)}")
else:
    print(f"No stats for {symbol} yet")
```

## Testing Strategy

### Unit Test: `should_skip_backtest()`
```python
# Test case 1: High confidence symbol → Should skip
from risk.symbol_stats import record_symbol_trade
from risk.protection import should_skip_backtest

# Simulate: 10 wins, 0 losses, avg_confidence=7.5
for i in range(10):
    record_symbol_trade("TEST_SYM", win=True, confirmation_score=7.5)

assert should_skip_backtest("TEST_SYM", 7.2) == True

# Test case 2: Low confidence symbol → Should NOT skip
for i in range(10):
    record_symbol_trade("TEST_SYM2", win=False, confirmation_score=5.0)

assert should_skip_backtest("TEST_SYM2", 6.0) == False
```

### Integration Test: Full Trade Lifecycle
```python
# 1. Detect signal
# 2. Execute (with skip decision logged)
# 3. Hit SL or TP
# 4. Verify symbol_stats.json updated
# 5. Check next signal uses updated stats
```

### Live Testing: Paper Trading
1. Run bot for 1 hour
2. Check `data/symbol_stats.json` exists and has entries
3. Monitor heartbeat for symbol performance line
4. Verify backtest skip/require in execution logs

## Performance Metrics

How to evaluate if it's working:

```
RATE METRICS:
- Backtest skip rate: (backtests_skipped / total_backtests) 
  Target: 30-50% after 50+ trades/symbol
  
- Win rate per symbol: (wins / total_trades)
  Target: >50% to qualify for backtest skip
  
- Symbol confidence avg: mean(confidence_scores)
  Target: >7.0 to qualify for backtest skip

TIME METRICS:
- Trades per minute: Should increase as backtest skipped more
- Execution latency: Direct execution < backtest verification
```

## Rollback Plan

If issues occur:

**Option 1: Disable feature entirely**
```bash
CONDITIONAL_BACKTESTING_ENABLED=false
```
→ Bot reverts to always-require-backtest behavior

**Option 2: Reset learning**
```python
from risk.symbol_stats import reset_symbol_stats
reset_symbol_stats()  # Clear data/symbol_stats.json
```
→ Start fresh symbol learning

**Option 3: Adjust thresholds conservative**
```bash
CONFIDENCE_SCORE_FOR_BACKTEST_SKIP=8.0       # Very high bar
SYMBOL_WIN_RATE_FOR_BACKTEST_SKIP=0.80       # 80% required
```
→ Rarely skip backtest, safer execution

---

## Critical Notes

⚠️ **These functions MUST be called in order:**
1. `execute_trade()` → Places trade
2. Monitor for SL/TP hit
3. `record_symbol_trade()` → Records outcome (when trade closes)
4. `record_backtest_skip()` or `record_backtest_required()` → Tracks decision

⚠️ **Symbol stats persistence:**
- All stats saved to `data/symbol_stats.json` 
- Only updated when trades close (not on entry)
- JSON is human-readable (can be edited for testing)

⚠️ **Thread safety:**
- If bot runs multi-threaded, protect JSON access with locks
- Current implementation assumes single-threaded main loop

---

Version: 1.0  
Last Updated: 2026-03-28  
Status: Production Ready ✅

