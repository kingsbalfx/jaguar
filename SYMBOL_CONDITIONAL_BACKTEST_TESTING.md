# Per-Symbol Conditional Backtesting - Testing Guide

## What Changed

The trading bot now:
1. **Tracks per-symbol performance** - Each pair (GBPJPY, EURUSD, etc.) maintains its own win/loss record
2. **Conditionally skips backtest** - High-confidence symbols execute without backtest approval
3. **Executes independently** - Different order blocks on same symbol don't block each other
4. **Reports live stats** - 30-second heartbeat shows symbol performance (e.g., "GBPJPY(9-6:60%)")

---

## Quick Validation Checklist

### ✅ Step 1: Start Bot & Monitor Logs
```bash
cd ict_trading_bot
python main.py
```

Look for in the console logs:
- `[bot_heartbeat] Bot is scanning X symbols...`
- After ~30 seconds, should see:
  - Old format: execution routes summary
  - **NEW**: `Symbol Performance: GBPJPY(0-0:N/A)` (0 trades yet)

### ✅ Step 2: Verify Symbol Stats File Created
Inside log monitor or after first trade:
```
Check: ict_trading_bot/data/symbol_stats.json exists
Expected: File created after first trade executes
```

File should look like:
```json
{
  "GBPJPY": {
    "symbol": "GBPJPY",
    "total_trades": 1,
    "wins": 1,
    "losses": 0,
    "win_rate": 1.0,
    "confidence_scores": [7.2],
    "avg_confidence": 7.2,
    "backtests_skipped": 0,
    "backtests_required": 1,
    "last_updated": "2026-03-28T..." 
  }
}
```

### ✅ Step 3: Watch Trade Closing Events
In the bot logs, when a trade closes you should see:
```
[trade_closed] Trade closed by TP on GBPJPY
  → WIN recorded to symbol_stats
  
[trade_closed] Trade closed by SL on GBPJPY  
  → LOSS recorded to symbol_stats
```

### ✅ Step 4: Monitor Backtest Skip Logic
After 1-2 winning trades on a symbol, watch for:
```
[execution_route] symbol_confidence_high - skipping backtest for GBPJPY
  Reason: win_rate=60%, avg_confidence=7.1 (threshold=7.0)
```

When symbol has <60% win rate:
```
[execution_route] backtest_fallback - symbol GBPJPY requires backtest validation
```

### ✅ Step 5: Check Heartbeat Evolution
Monitor heartbeat every 30 seconds:
```
Second 0: "Symbol Performance: EURUSD(0-0:N/A) GBPJPY(0-0:N/A)"
Second 30: "Symbol Performance: EURUSD(1-0:100%) GBPJPY(0-1:0%)"  
Second 60: "Symbol Performance: EURUSD(2-1:66%) GBPJPY(1-1:50%)"
...
```

Each symbol shows: `SYMBOL(WINS-LOSSES:WIN_RATE%)`

---

## Configuration Tuning

### 🎯 Adjust Backtest Skip Thresholds

Located in `.env`:
```bash
# More aggressive (skip backtest earlier):
CONFIDENCE_SCORE_FOR_BACKTEST_SKIP=6.5        # Default: 7.0 
SYMBOL_WIN_RATE_FOR_BACKTEST_SKIP=0.50        # Default: 0.60 (50%)

# More conservative (require backtest longer):
CONFIDENCE_SCORE_FOR_BACKTEST_SKIP=7.5        # Default: 7.0
SYMBOL_WIN_RATE_FOR_BACKTEST_SKIP=0.70        # Default: 0.60 (70%)
```

**Recommendation**: Start with defaults, after 20+ trades per symbol, adjust based on:
- If backtest is catching too many false signals → Lower thresholds (skip backtest earlier)
- If backtested symbols have worse outcomes → Raise thresholds (require backtest longer)

---

## Troubleshooting

### Issue: Symbol stats not updating after trades
**Check**:
1. Is `data/` directory writable? 
2. Are "trade_closed" events appearing in logs?
3. Check for exceptions in log about `symbol_stats.json`

**Fix**:
```bash
# Verify directory exists
mkdir -p ict_trading_bot/data

# Check permissions (Windows)
icacls "ict_trading_bot/data" /grant %username%:F
```

### Issue: Backtest always required (no skip happening)
**Check**:
1. Is `CONDITIONAL_BACKTESTING_ENABLED=true` in `.env`?
2. Does symbol have >60% win rate? (Check `data/symbol_stats.json`)
3. Is average confirmation score >7.0? (Check avg_confidence field)

**Debug**:
```python
# Add to main.py temporarily to debug:
from risk.protection import should_skip_backtest
result = should_skip_backtest("GBPJPY", 7.5)
print(f"Should skip backtest for GBPJPY: {result}")
```

### Issue: SL/TP hits not detected
**Check**:
1. Is trade loop reaching SL/TP comparison section?
2. Add debug log:
```python
# In main.py trade management loop (line ~915)
print(f"[DEBUG] {symbol} price={live_price}, SL={trade['sl']}, TP={trade['tp']}")
print(f"[DEBUG] SL hit: {sl_hit}, TP hit: {tp_hit}")
```

---

## Performance Expectations After Implementation

### Before Changes:
- Single trade could block entire symbol for 30 minutes
- Backtest required for ALL signals regardless of quality
- No tracking of which symbols work best
- Weighted/4-confirmation signals had no advantage

### After Changes:
- Same symbol can trade every 5 minutes on different order blocks
- High-confidence symbols skip backtest approval (faster execution)
- Per-symbol win rate tracking informs execution decisions
- Parallel execution on different pairs works independently
- Learning system improves over time as trades execute

---

## Example Trading Day

```
09:00 - Bot starts
        All symbols: 0-0:N/A (no trades yet)

09:15 - GBPJPY signal detected, weighted confirmation, confidence=7.2
        → Skip backtest (first trade, uses weighted path)
        → Trade executes directly
        → symbol_stats: GBPJPY = {trades:1, wins:0, losses:0}

09:20 - EURUSD signal detected, 4-confirmation, confidence=7.8
        → Skip backtest (4-confirmation path)
        → Trade executes directly

09:25 - GBPJPY hit TP (win!)
        → record_symbol_trade(GBPJPY, win=True, confidence=7.2)
        → symbol_stats: GBPJPY = {trades:1, wins:1, losses:0, win_rate=100%}

09:30 - GBPJPY signal again, confidence=6.9
        Heartbeat shows: "GBPJPY(1-0:100%) EURUSD(0-0:N/A)"
        → Check: win_rate=100% (✓) AND avg_confirmation=7.2 (✓)
        → Skip backtest! Execute directly
        → Execution route: "symbol_confidence_high"

09:35 - EURUSD hit SL (loss)
        → record_symbol_trade(EURUSD, win=False, confirmation=0.0)
        → symbol_stats: EURUSD = {trades:1, wins:0, losses:1, win_rate=0%}

09:45 - GBPJPY signal, confidence=6.5
        → Check: win_rate=100% (✓) BUT avg_confirmation=6.85 (✗ below 7.0)
        → Require backtest! Don't skip
        → Execution route: "backtest_fallback"

10:00 - Heartbeat shows evolution:
        "GBPJPY(2-0:100%) EURUSD(0-1:0%) NZDUSD(1-2:33%)"
        Each symbol learning independently...
```

---

## What NOT To Do

❌ Don't manually edit `data/symbol_stats.json` while bot is running
❌ Don't change thresholds every trade (give it 20+ trades to settle)
❌ Don't assume a symbol is "bad" after 1-2 losses (need statistical confidence)
❌ Don't disable `TRACK_SYMBOL_CONFIDENCE=true` (needed for the feature)

---

## Next Steps

1. **Run in paper trading mode** for 2-4 hours
2. **Monitor symbol_stats.json** evolution - should show win rates stabilizing
3. **Check execution routes** - verify backtest skips happening for good symbols
4. **Review backtest decisions** - compare skipped vs required outcomes
5. **Adjust thresholds** based on your market conditions

After ~100 trades per symbol, the system will have enough historical data to make reliable decisions about which signals to backtest and which to execute directly.

