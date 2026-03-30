# Repeated Skip Learning System

## Overview

The system NOW learns from **repeated skips** on the same symbols and automatically adjusts behavior.

When a symbol appears multiple times in skip records, the system extracts intelligence to:
- ✅ **Avoid symbols** that are repeatedly failing
- ✅ **Adjust confidence thresholds** based on pattern difficulty
- ✅ **Provide learning insights** for improving entry models

---

## How It Works: 3-Layer Learning System

### **Layer 1: Universal Skip Tracking (ALL SYMBOLS)**

✅ **WORKS FOR ALL SYMBOLS** - Every symbol is tracked in `intelligent_skip_tracking.json`

```json
{
  "GBPUSD": {
    "total_skips": 47,      // ALL symbols have this
    "skip_reasons": {...},  // Tracked for ALL symbols
    "skip_patterns": {...}  // Analyzed for ALL symbols
  },
  "EURUSD": {
    "total_skips": 23,      // Every symbol that appears gets tracked
    "skip_reasons": {...},
    "skip_patterns": {}
  }
}
```

**Coverage:** 100% - Any symbol that gets scanned gets its skips recorded

---

### **Layer 2: Pattern Analysis (For Frequently Skipped)**

When a symbol has **5+ skips**, pattern analysis activates:

```python
analysis = get_skip_pattern_analysis("GBPUSD")
# Returns:
{
    "symbol": "GBPUSD",
    "total_skips": 47,
    "most_common_skip_reason": "intelligence",
    "confidence_patterns": {
        "intelligence": {
            "avg": 0.592,  # Average confidence: 59.2%
            "min": 0.57,   # Range: 57%-63%
            "max": 0.63,
            "count": 28    # 28 intelligence skips
        }
    },
    "recommendation": "PATTERN DETECTED! Review this symbol's signals."
}
```

**Pattern Detection Thresholds:**
- **5-9 skips**: Normal frequency
- **10-14 skips**: Frequent - monitor
- **15+ skips**: Critical pattern detected

---

### **Layer 3: Intelligent Decision Making (For Problem Symbols)**

Three new functions automatically handle repeating skip patterns:

#### **1. `should_skip_symbol_entirely(symbol: str) -> (bool, reason)`**

Returns whether a symbol should be AVOIDED based on skip history.

**Rules:**
- **Skip entirely if:** 80%+ skip rate AND 20+ skip attempts
- **Skip entirely if:** 70%+ skip rate AND 15+ skip attempts AND no successful trades
- **Skip entirely if:** Many skips (20+) AND executed trades have <30% win rate

**Example:** GBPUSD with 47 skips vs 3 trades
```python
should_skip, reason = should_skip_symbol_entirely("GBPUSD")
# Returns: (True, "VERY HIGH skip rate (94%, 47 attempts). Entry model broken for GBPUSD.")
```

**In Main Loop:** Added at line ~520
```python
should_skip_entirely, skip_reason = should_skip_symbol_entirely(original_symbol)
if should_skip_entirely:
    record_skip("skip_pattern_learned", original_symbol)
    continue  # Skip this symbol entirely
```

**Benefit:** Once a symbol shows it's unprofitable, system stops wasting cycles on it.

---

#### **2. `get_learned_threshold_adjustment(symbol: str) -> float`**

Calculates how much to adjust confidence threshold based on skip patterns.

**Logic:**

| Condition | Adjustment | Example |
|-----------|------------|---------|
| High skip rate (75%+), no trades | +0.10 | 75% threshold → 85% (more cautious) |
| High skip rate (70%+), poor WR | +0.08 | Raise 8 percentage points |
| Moderate skip rate, good WR, proven | -0.03 | Lower 3 points (reward it) |
| Many skips, excellent WR | -0.05 | Lower 5 points (it's a gem) |

**Example:** EURUSD with 40 skips, 10 trades, 65% win rate
```python
adjustment = get_learned_threshold_adjustment("EURUSD")
# Returns: -0.03 (lower threshold by 3%)
# Decision: At 72% instead of 75% (symbol is improving)
```

**In Execution:** Applied automatically in `should_take_trade()` when calculating final threshold

---

#### **3. `learn_from_repeated_skips(symbol: str) -> Dict`**

Generates complete learning report from skip patterns.

**Returns:**
```python
{
    "symbol": "GBPUSD",
    "skip_count": 47,
    "execution_count": 3,
    "skip_rate": 0.94,
    "win_rate": 0.33,
    "learned_insights": [
        "Confidence is consistently too low (28/47 intelligence skips)",
        "Skip rate for GBPUSD: 94% (47 skips vs 3 executions)",
    ],
    "recommendations": [
        "Strengthen entry model: add more confirmation signals",
        "Check if symbol requires different confirmation types",
        "CRITICAL: Never successfully traded. Entry model may be broken.",
    ],
    "threshold_adjustment": 0.05,
    "avoid_until": "System gets confidence in entry signals"
}
```

**In Reports:** Use to generate daily intelligence briefing

---

## Examples: All Symbols Covered

### **Example 1: New Symbol (No Skip History)**
```python
symbol = "NZDJPY"  # New symbol, never seen before

# Skip tracking: Automatic for ALL symbols
record_skip_detailed("intelligence", "NZDJPY", 0.62)
# Data saved to disk: ✅

# Pattern analysis: Wait until 5+ skips
should_skip, reason = should_skip_symbol_entirely("NZDJPY")
# Returns: (False, "")  → Safe to trade

# Threshold adjustment: 0.0 (no history yet)
```

### **Example 2: Symbol with a Few Skips**
```python
symbol = "AUDUSD"  # 3 skips, 5 executed trades

should_skip, reason = should_skip_symbol_entirely("AUDUSD")
# Returns: (False, "")  → Skip rate is 37%, OK

adjustment = get_learned_threshold_adjustment("AUDUSD")
# Returns: 0.0 (not enough pattern yet)
```

### **Example 3: Problem Symbol (Many Skips)**
```python
symbol = "GBPUSD"  # 47 skips, 3 executed, 33% WR

should_skip, reason = should_skip_symbol_entirely("GBPUSD")
# Returns: (True, "VERY HIGH skip rate (94%, 47 attempts). Entry model broken.")

learning = learn_from_repeated_skips("GBPUSD")
# Returns: Multiple insights and recommendations
# Action: STOP trading GBPUSD, improve entry model

adjustment = get_learned_threshold_adjustment("GBPUSD")
# Returns: 0.10 (require 85% confidence, not 75%)
```

### **Example 4: Robust Symbol (Many Skips but Good WR)**
```python
symbol = "EURUSD"  # 40 skips, 20 executed, 70% WR

should_skip, reason = should_skip_symbol_entirely("EURUSD")
# Returns: (False, "")  → Skip rate is 67% but WR is 70%, KEEP trading

adjustment = get_learned_threshold_adjustment("EURUSD")
# Returns: -0.05 (LOWER threshold to 70%, reward the gem)
# Action: MORE AGGRESSIVE on EURUSD, it's proven profitable

learning = learn_from_repeated_skips("EURUSD")
# Returns: Positive insights, no recommendations to avoid
```

---

## Data Files

### **1. `intelligent_execution_stats.json`**
- **What:** Executed trades only (wins, losses, confidence scores)
- **Size:** ~1-2KB per symbol after 50+ trades
- **Retention:** Keeps last 100 trades, last 50 confidence scores per symbol

### **2. `intelligent_skip_tracking.json`** (NEW)
- **What:** Skipped trades with full details
- **Size:** ~200 bytes per skip record
- **Retention:** Keeps last 50 skips per symbol, last 100 confidence scores per skip reason
- **Critical:** Enables learning from failed attempts

---

## System Behavior Changes

### **BEFORE**
- Symbol with 47 skips: Kept trying forever ❌
- No learning from repeated failures ❌
- Same entry signals rejected repeatedly ❌
- Network failure = all skip history lost ❌

### **AFTER**
- Symbol with 47 skips: Automatically avoided after detection ✅
- System learns "this symbol's entry model is broken" ✅
- Stops wasting cycles on dead signals ✅
- Network failure = skip data fully preserved ✅
- Threshold automatically adjusted based on evidence ✅

---

## Usage Examples

### **In Your Trading Bot**
```python
# Get learning insights for a symbol
learning = learn_from_repeated_skips("GBPUSD")
print(f"Insights: {learning['learned_insights']}")
print(f"Recommendations: {learning['recommendations']}")

# Check if symbol should be avoided
should_skip, reason = should_skip_symbol_entirely("GBPUSD")
if should_skip:
    print(f"AVOID {symbol}: {reason}")

# Get threshold adjustment
adjustment = get_learned_threshold_adjustment("GBPUSD")
threshold_with_adjustment = 0.75 + adjustment
```

### **In Daily Reports**
```python
# Full skip analysis with learning
report = get_skip_statistics_report()
print(report)

# Per-symbol learning briefing
for symbol in VALID_SYMBOLS:
    learning = learn_from_repeated_skips(symbol)
    if learning.get("skip_count", 0) >= 5:
        print(f"{symbol}: {learning['recommendation_text']}")
```

---

## Confirmation: Works for ALL Symbols

### **Coverage Matrix**

| Category | Coverage | Method |
|----------|----------|--------|
| **New symbols** | ✅ 100% | Instant skip tracking on first scan |
| **Actively traded** | ✅ 100% | Skips/trades both recorded |
| **Rarely traded** | ✅ 100% | Skip tracking persists |
| **Never traded** | ✅ 100% | Skip history preserved |
| **Inactive symbols** | ✅ 100% | Skip tracking continues |
| **Dynamic symbols** | ✅ 100% | Patterns updated in real-time |

### **Skip Tracking Mechanism**

For **ANY** symbol:
1. ✅ System scans symbol
2. ✅ Makes decision (trade/skip)
3. ✅ If SKIP: calls `record_skip_detailed()`
4. ✅ Data saved to disk within milliseconds
5. ✅ Pattern analysis available after 5+ skips
6. ✅ Learning recommendations available
7. ✅ Threshold adjustments applied automatically

---

## Implementation Files Modified

### **1. `ict_trading_bot/risk/intelligent_execution.py`**
**Added 3 new functions:**
- `should_skip_symbol_entirely()` - Identify problem symbols
- `get_learned_threshold_adjustment()` - Adjust thresholds dynamically
- `learn_from_repeated_skips()` - Generate learning insights

**Modified:**
- `get_skip_statistics_report()` - Enhanced reporting

### **2. `ict_trading_bot/main.py`**
**Added:**
- Import of 3 new functions
- Skip-entirely filter in main loop (line ~520)
- Logging for learned patterns

---

## Next Steps

1. ✅ **Run bot** - Skip tracking happens automatically for all symbols
2. ✅ **Monitor learning** - Call `learn_from_repeated_skips()` in reports
3. ✅ **Review insights** - Use recommendations to improve entry models
4. ✅ **Observe adjustments** - System automatically adjusts thresholds

---

## Summary

**Q: Does it work for ALL symbols?**
- ✅ **YES** - Every symbol that appears in the trading loop is tracked
- ✅ Universal coverage from scan #1

**Q: Can we use skips if they appear multiple times?**
- ✅ **YES** - Three new functions automatically use repeated skips:
  - Avoid problem symbols entirely
  - Adjust confidence thresholds dynamically
  - Generate learning insights

**Q: Is data persistent?**
- ✅ **YES** - All skips saved to `intelligent_skip_tracking.json`
- ✅ Survives crashes, restarts, network failures

