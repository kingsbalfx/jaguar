# OPTIMIZATION STRATEGY FOR NEW H1→M15→M5→M1 SYSTEM

**Status:** Quick Reference for Performance Tuning  
**Based on:** 2 weeks of projected test data from first 100 trades  
**Goal:** Push win rate from 62-68% → 72-78% range

---

## PHASE 1: DATA VALIDATION (Week 1)

### 1.1 Validate H1 Brief Context Effectiveness
```
Track: After H1 scan, how often does M15 confirm the bias?
  Expected: 70-80% confirmation rate
  Target:   85%+ (H1 bias is correct)

Track: H1 scan time - should be ~2 minutes
  Expected: Each scan < 2 minutes
  Target:   < 90 seconds (just a glance)
  
If taking > 5 minutes on H1: You're over-analyzing.
Remember: H1 is just "what's the general trend?" Not a deep dive.
```

**Action Items:**
- Time yourself on H1 scans (should be fast)
- Note if H1 bias matches M15 findings
- Don't over-analyze H1 (it's a quick check, not research)
- Focus your energy on M15 analysis (where the work is)

### 1.2 Validate Timeframe Cascade
```
Track: How many bars H1→M15→M5→M1 each takes?
  Expected: H1 (1-3 hours) → M15 (15-45 min) → M5 (5-20 min) → M1 (1-5 min)

Track: What % of setups complete all 4 timeframes?
  Expected: 60-70% of signals reach M1 execution
  Target:   75%+ conversion through all timeframes
```

**Action Items:**
- Measure time from signal to execution
- Identify bottlenecks (e.g., M5 rarely confirms)
- Adjust confirmation weights if timeframes misaligned
- Note which symbols have fastest/slowest cascades

### 1.3 Validate Win Rate by Setup Type
```
Track: Liquidity vs BOS vs Price Action performance
  Expected baseline: Each ~60% win rate
  
Track: Which setup type performs BEST with previous day levels?
  Expected: One setup type gets +10-15% boost from daily S/R
```

**Action Items:**
- Tag every trade with setup type used
- Calculate win rate per setup type
- Identify winning combination (e.g., Liquidity + BOS)
- Phase out lowest-performing setup for this system

---

## PHASE 2: QUICK WINS (Week 2-3)

### 2.1 Adjust Previous Day "Sweet Zone"
**Current:** 50% (middle half of daily range)

**Optimization:** Test different zone sizes
```
Test 1: 40% sweet zone (wider entries)
  - More entries but potentially lower quality
  - Test for 30 trades, measure win rate impact
  
Test 2: 60% sweet zone (tighter entries)
  - Fewer entries but probably higher quality
  - Test for 30 trades, measure win rate impact
  
Test 3: Dynamic zone (based on ATR)
  - High volatility → wider zone
  - Low volatility → tighter zone
  - Adjusts automatically per symbol session

Decision: Choose zone that gives best Profit Factor (total wins/total losses)
```

### 2.2 Time-of-Day Filter
**Observation:** Certain sessions perform better with new system

**Optimization:**
```
Test by Session (UTC times):
  
London Window (8-16 UTC):
  - Expected: Best for FX pairs (GBPJPY, EURUSD, etc)
  - Check: 65-70% win rate
  
US Window (13-21 UTC):
  - Expected: Better for gold (XAGUSD)
  - Check: 65-70% win rate
  
Overlap Window (13-16 UTC):
  - Expected: Best liquidity, fastest execution
  - Check: 70-75% win rate expected

Off-Hours (21-8 UTC):
  - Consider: Skip trading or reduce position size
  - Expected: Slower entries, wider stops, lower win rate
```

**Action:** Implement time-based position size adjustments
```python
if 13 <= current_hour < 16:  # Peak overlap
    position_size = 1.0x  # Full size
elif 8 <= current_hour < 21:  # Secondary windows
    position_size = 0.75x  # 75% size
else:  # Off hours
    position_size = 0.5x   # Half size (or skip)
```

### 2.3 Previous Day Level Proximity Boost
**Idea:** Give extra confidence when entry is VERY close to previous day level

```python
proximity = abs(entry_price - previous_day_high)
proximity_ratio = proximity / daily_range

if proximity_ratio < 0.02:  # Within 2% of daily level
    confidence += 20  # STRONG signal alignment
elif proximity_ratio < 0.05:  # Within 5% of daily level
    confidence += 10  # Good alignment
# else: standard scoring
```

**Expected impact:** +5-10% win rate on trades entering near S/R

---

## PHASE 3: MEDIUM-TERM IMPROVEMENTS (Week 4+)

### 3.1 Multi-Day Confluence
**Idea:** Use last 3 days of levels, score confluence

```
Single breakout (1 day):     50 points base
Double breakout (2 days):    +10 points bonus  
Triple breakout (3 days):    +25 points bonus (very strong)

Example:
  Yesterday broke RESISTANCE
  2-days-ago also broke RESISTANCE
  3-days-ago also broke RESISTANCE
  = Triple confluence → +100 total confidence
  = Probability near 75%+
```

**Implementation:**
```python
def get_multi_day_levels(symbol, days=3):
    levels = []
    for d in range(days):
        prev_day = get_previous_day_levels(symbol, days_back=d)
        if prev_day and 'broken_level' in prev_day:
            levels.append(prev_day)
    return calculate_confluence_score(levels)
```

### 3.2 Asset Class Specific Tuning
**Observation:** Forex, metals, crypto behave differently

**Optimization:**
```
FOREX (GBPJPY, EURUSD, etc):
  - Sweet zone: 50% (works best)
  - Time filter: London window (+10% WR)
  - Min bars held: 10 (M1 bars)
  - Daily range avg: 100-200 pips

METALS (XAGUSD, XAUUSD):
  - Sweet zone: 45% (can be tighter)
  - Time filter: All sessions equal
  - Min bars held: 5 (faster moves)
  - Daily range avg: 50-100 pips

CRYPTO (BTCUSD, DOGEUSD):
  - Sweet zone: 60% (need wider)
  - Time filter: None (24/5)
  - Min bars held: 20 (volatile)
  - Daily range avg: 200-500 pips
```

Create per-asset-class configuration:
```python
ASSET_CLASS_CONFIG = {
    "forex": {
        "sweet_zone_ratio": 0.50,
        "preferred_session": "london",
        "position_size_multiplier": 1.0,
    },
    "metals": {
        "sweet_zone_ratio": 0.45,
        "preferred_session": "all",
        "position_size_multiplier": 0.8,
    },
    "crypto": {
        "sweet_zone_ratio": 0.60,
        "preferred_session": "all",
        "position_size_multiplier": 0.6,  # Higher volatility
    }
}
```

### 3.3 Session-Based "Previous Day"
**Idea:** Different opening times = different "day"

```
For Asia Traders:
  - "Previous day" = from Tokyo open to Tokyo close
  - Use those levels for morning London session

For London Traders:
  - "Previous day" = from London open to London close
  - Use those levels for afternoon US session

For US Traders:
  - "Previous day" = from US open to US close
  - Use those levels for next morning
```

### 3.4 Smart Stop Placement
**Current:** Fixed below/above entry  
**Optimized:** Protect based on previous day range

```python
daily_range = previous_day_high - previous_day_low

# Breakout entry example:
if direction == "buy":
    entry = previous_day_high + buffer
    # Stop = farthest low in last 3 days
    stop = get_lowest_low(symbol, bars=1440*3)  # 3 days of M1 bars
    tp = entry + (daily_range * 1.5)  # 1.5x daily range as target
else:
    entry = previous_day_low - buffer
    stop = get_highest_high(symbol, bars=1440*3)  
    tp = entry - (daily_range * 1.5)
```

**Expected Impact:** Better RR ratios (2.5:1 → 3:1 avg)

---

## PHASE 4: ADVANCED (Week 5+)

### 4.1 Liquidity Level Detection
**Track:** Where were stops likely placed yesterday?

```
Scenario: Yesterday ended near midpoint
  → Stops likely 2-5% above/below
  → Today, target those zones for best countertrend moves

Implementation:
  1. Identify yesterday's rejection zones
  2. Calculate 68% confidence zone (1 std dev)
  3. Target that zone for reversals
  4. Place stops beyond 95% zone (2 std dev)
```

### 4.2 Volatility-Adjusted Entry Zones
**Idea:** Use ATR to adjust sweet zone and stops

```python
atr_14 = calculate_atr(symbol, period=14, timeframe="H1")
avg_atr = 50  # Symbol's normal ATR

if atr_14 > avg_atr * 1.5:  # High volatility
    sweet_zone_ratio = 0.60  # Wider zone
    position_size *= 0.75     # Smaller size
elif atr_14 < avg_atr * 0.7:  # Low volatility
    sweet_zone_ratio = 0.40   # Tighter zone
    position_size *= 1.25     # Larger size
```

### 4.3 Correlation-Based Filtering
**Idea:** Skip trades when multiple pairs are conflicting

```python
# Get correlation matrix of major pairs
# If EURUSD & GBPUSD both have signals:
#   - Same direction? → Confidence +15
#   - Opposite direction? → Skip both (conflicting)
#   - One broken, one not? → Follow the broken one

# Check DXY (dollar index) against USD pairs
# If DXY breaking down, USD pairs should break up
# If conflict → Skip that signal
```

### 4.4 Machine Learning Confidence
**Use:** Strategy memory to predict setup success

```python
# From strategy_memory.json:
setup_win_rate = memory["setup_strategies"][setup_type]["per_symbol"][symbol]

# If this EXACT setup succeeded 70% of the time on this symbol:
#   → Add +20 confidence points
# If history shows < 55% win rate:
#   → Reduce confidence or skip

# Weight recent history heavier:
#   Last 10 trades win rate: 70%
#   Last 20 trades win rate: 65%
#   All-time: 60%
#   Use: (70% × 40%) + (65% × 35%) + (60% × 25%) = 66.5% expected
```

---

## QUICK OPTIMIZATION CHECKLIST

### Week 1 (Testing Phase)
- [ ] Log 30+ trades with previous day level alignment
- [ ] Calculate sweet zone accuracy
- [ ] Measure timeframe cascade completion rates
- [ ] Calculate win rate by setup type
- [ ] Identify best performing setup+timeframe combo

### Week 2-3 (Quick Wins)
- [ ] Test 3 sweet zone sizes (40%/50%/60%)
- [ ] Implement time-of-day filters by session
- [ ] Add proximity bonus for entries near S/R
- [ ] Measure Profit Factor improvement
- [ ] Adjust best parameters based on results

### Week 4+ (Medium-Term)
- [ ] Implement multi-day confluence scoring
- [ ] Create asset-class-specific configurations
- [ ] Test session-based "previous day" concept
- [ ] Optimize stop placement strategy
- [ ] Document best practices per symbol

---

## SUCCESS METRICS

Judge optimization success by:

1. **Win Rate** ↑
   - Current target: 62-68%
   - Success: 72%+

2. **Profit Factor** ↑↑↑  
   - Current target: 1.3-1.5
   - Success: 1.8-2.0

3. **Trade Frequency** ↑
   - Current target: 15-20/week
   - Success: 20-25/week

4. **Avg Bars Held** ↓
   - Current target: 20-40 bars
   - Success: 10-25 bars

5. **Slippage** ↓
   - Current target: 0-1 pip
   - Success: <0.5 pip avg

6. **Emotional Score** ↑
   - Reduced stress
   - Clear decision rules
   - Quick feedback

---

## DON'T OPTIMIZE THESE

❌ Stop optimizing if:
- Changing core logic too much (keep timeframes H1→M15→M5→M1)
- Over-optimizing to past data (only use recent 50 trades)
- Complicating entry rules (keep simple, add filters instead)
- Chasing perfection (80% of gain comes from first 20% of changes)

✅ Perfect is the enemy of good - lock in gains and move on!

---

*Optimization Strategy Created: March 28, 2026*  
*Review & Update: Every 2 weeks during testing phase*
