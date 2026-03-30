# Intelligence System - Quick Start

## 5-Minute Setup

### 1. Import the Engine
```python
from intelligence_system_integration import TradeDecisionEngine

engine = TradeDecisionEngine()
```

### 2. Analyze Market Conditions
```python
# At start of trading session
engine.analyze_market_conditions()
```

### 3. Evaluate Any Trade
```python
# When you find a potential trade
decision = engine.evaluate_trade(
    symbol="EURUSD",
    direction="BUY",
    entry=1.0850,
    stop_loss=1.0800,
    take_profit=1.0920,
)

print(decision.summary())
# Output: "EURUSD BUY: ✓ APPROVED | CIS: TRADE (0.82) | Size: 0.01L"
```

### 4. Execute if Approved
```python
if decision.should_trade:
    order = engine.execute_trade(
        symbol="EURUSD",
        direction="BUY",
        entry=1.0850,
        stop_loss=1.0800,
        take_profit=1.0920,
        decision=decision
    )
    print(f"Order placed: {order['order_id']}")
else:
    print(f"Trade blocked: {decision.block_reason}")
```

---

## What's Being Analyzed?

The intelligence system scores each trade on 4 factors:

```
Setup Quality (0-1)      ← Is the technical setup good?
Market Condition (0-1)   ← Is the pair's environment favorable?
Risk Profile (0-1)       ← Is the account safe?
Timing (0-1)             ← Is it the right time to trade?

Average Score → Final Decision
  > 0.75 = TRADE
  0.50-0.75 = WAIT
  < 0.50 = AVOID
```

---

## Decision Details

After evaluation, decision object contains:

```python
decision.should_trade          # bool: Can we trade?
decision.block_reason          # str: Why blocked (if blocked)

decision.cis_verdict           # "TRADE", "WAIT", or "AVOID"
decision.cis_confidence        # 0.0-1.0 confidence score

decision.component_scores      # Dict of 4 component scores
decision.position_size         # 0.01 lots (or adapted size)

decision.cis_reasoning         # List of reasons supporting decision
decision.cis_red_flags         # List of concerns

decision.checks                # List of validation checks (PASS/FAIL)
decision.warnings              # Non-blocking warnings
```

---

## Common Usage Patterns

### Pattern 1: Quick Decision
```python
decision = engine.evaluate_trade("EURUSD", "BUY")
print(decision.summary())
```

### Pattern 2: Full Trade Workflow
```python
decision = engine.evaluate_trade(
    "EURUSD", "BUY",
    entry=1.0850, stop_loss=1.0800, take_profit=1.0920
)

if decision.should_trade:
    order = engine.execute_trade("EURUSD", "BUY", 1.0850, 1.0800, 1.0920, decision)
```

### Pattern 3: Detailed Logging
```python
decision = engine.evaluate_trade("EURUSD", "BUY")

print(f"Verdict: {decision.cis_verdict}")
print(f"Confidence: {decision.cis_confidence:.2f}")

print("\nReasons:")
for reason in decision.cis_reasoning:
    print(f"  ✓ {reason}")

print("\nRed Flags:")
for flag in decision.cis_red_flags:
    print(f"  ⚠️  {flag}")

print("\nValidation Checks:")
for check in decision.checks:
    status = "✓" if check['status'] == "PASS" else "✗"
    print(f"  {status} {check['name']}: {check['message']}")
```

### Pattern 4: Monitor Market Status
```python
# Get summary of current market conditions
print(engine.get_status_report())
# Output: [ENGINE] Setup: 0.85 Market: 0.75 Risk: 0.80 Timing: 0.85 | EURUSD: STABLE (0.32) ...
```

---

## Error Handling

The system handles errors gracefully:

```python
try:
    decision = engine.evaluate_trade("EURUSD", "BUY")
    
    if decision.should_trade:
        order = engine.execute_trade("EURUSD", "BUY", 1.0850, 1.0800, 1.0920)
except Exception as e:
    logger.error(f"Trading error: {e}")
```

If analysis fails, you get safe defaults:
- Volatility: 0.5 (neutral)
- Position size: 0.8x (conservative)
- Verdict: "WAIT" (don't trade if uncertain)

---

## Score Interpretation

### Setup Quality
```
0.00-0.40: Weak setup (multiple signals missing)
0.40-0.60: Moderate (acceptable for trading)
0.60-0.80: Good (strong confirmations)
0.80-1.00: Excellent (all timeframes aligned)
```

### Market Condition
```
0.00-0.40: Unfavorable (poor liquidity, wide spreads)
0.40-0.70: Neutral (normal conditions)
0.70-1.00: Favorable (good liquidity, tight spreads)
```

### Risk Profile
```
0.00-0.40: Over-exposed (account too exposed)
0.40-0.70: Moderate (acceptable risk)
0.70-1.00: Safe (plenty of margin, low exposure)
```

### Timing
```
0.00-0.40: Poor (off-hours, overtrading)
0.40-0.70: Okay (non-peak hours)
0.70-1.00: Optimal (peak liquidity session)
```

---

## Block Reasons (Why Trade Might Be Blocked)

| Block Reason | Meaning | Solution |
|---|---|---|
| "CIS recommends AVOID" | Confidence < 0.50 | Wait for better setup |
| "Broker connection failed" | MT5 not responding | Check connection |
| "Symbol not tradable" | Pair not available | Choose different pair |
| "Account risk too high" | Exposure > 10% | Close existing trades |
| "Validation failed" | One or more checks failed | Check validation details |
| "Volatility too high" | Pair very volatile | Wait for calmer conditions |
| "Low setup quality" | Technical setup weak | Look for better setup |
| "Poor trade timing" | Wrong session/overtrading | Trade at peak hours |

---

## Decision Flow Summary

```
┌─────────────────────────────┐
│  engine.evaluate_trade()    │
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│   CIS Confidence Scoring    │
│   (4 component analysis)    │
└──────────────┬──────────────┘
               ↓
         Confidence?
        ↙          ↘
    >0.75         <0.5        0.50-0.75
      ↓             ↓            ↓
    TRADE        AVOID         WAIT
      ↓             ↓            ↓
   Continue    ❌ Blocked      Continue
      ↓                          ↓
   Validate                   Validate
      ↓                          ↓
   Pass?                       Pass?
    ↙  ↖                      ↙  ↖
   ✓    ❌                    ✓    ❌
   ↓    ↓                     ↓    ↓
Execute Block               Execute Block
```

---

## Integration Checklist

- [ ] Import `TradeDecisionEngine` in your code
- [ ] Create engine instance: `engine = TradeDecisionEngine()`
- [ ] Calculate markets at session start: `engine.analyze_market_conditions()`
- [ ] Call `evaluate_trade()` before entering trades
- [ ] Check `decision.should_trade` before ordering
- [ ] Use position size from `decision.position_size`
- [ ] Log decisions for performance tracking
- [ ] Review decision summary regularly

---

## Example: Complete Bot Integration

```python
import time
import logging
from intelligence_system_integration import TradeDecisionEngine

logger = logging.getLogger(__name__)

def main():
    engine = TradeDecisionEngine([
        "EURUSD", "GBPUSD", "USDJPY", "AUDUSD",
        "NZDUSD", "EURGBP", "EURJPY", "GBPJPY"
    ])
    
    # Session start
    engine.analyze_market_conditions()
    logger.info(engine.get_status_report())
    
    # Main loop
    while True:
        try:
            # Scan for setups
            for symbol in engine.symbols:
                setup = scan_for_setup(symbol)
                
                if setup:
                    # Evaluate trade
                    decision = engine.evaluate_trade(
                        symbol=symbol,
                        direction=setup['direction'],
                        entry=setup['entry'],
                        stop_loss=setup['stop_loss'],
                        take_profit=setup['take_profit']
                    )
                    
                    logger.info(decision.summary())
                    
                    # Execute if approved
                    if decision.should_trade:
                        order = engine.execute_trade(
                            symbol, setup['direction'],
                            setup['entry'], setup['stop_loss'],
                            setup['take_profit'], decision
                        )
                        
                        if order:
                            logger.info(f"✓ Executed: {symbol}")
                    else:
                        logger.info(f"✗ Blocked: {decision.block_reason}")
            
            time.sleep(60)
        
        except Exception as e:
            logger.error(f"Error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
```

---

## Common Questions

### Q: Why was my trade blocked?
**A**: Check `decision.block_reason` and `decision.checks` for detailed reason. Most common:
- CIS confidence < 0.50 (low quality setup)
- Account risk too high (close other trades first)
- Market volatility too high (wait for calmer conditions)

### Q: Why is position size smaller than usual?
**A**: The system adapts size based on market conditions:
- Volatile market: 0.8x normal size (higher risk)
- Consolidating: 0.95x normal size
- Stable: 1.0x normal size

### Q: Can I override the system's decision?
**A**: For manual trading, yes. But recommended to respect:
- AVOID verdict (confidence < 0.50)
- Block reasons (validation failures)
- System is designed to prevent losses

### Q: How accurate are the decisions?
**A**: Depends on your setup scanner quality. System helps by:
- Filtering poor setups (blocks low confidence trades)
- Preventing risky sizing (adapts to conditions)
- Avoiding overtrading (tracks trade frequency)
- Protecting account (validates risk/reward)

### Q: What if something goes wrong?
**A**: System has multiple safety layers:
1. CIS blocks low-confidence trades
2. Validator blocks invalid trades
3. Position sizing limits risk
4. Error handling prevents crashes
5. Default to conservative if uncertain

---

## Data Files

System automatically maintains:

- `data/pair_volatility_analysis.json` - Current volatility for each pair
- `data/cis_decisions_history.json` - All decisions (last 500 per pair)

Use these for:
- Performance analysis
- Win rate calculation
- Pattern identification
- System optimization

---

## Next: Full Documentation

For more details, see:
- `INTELLIGENCE_SYSTEM_GUIDE.md` - Complete guide with examples
- `INTELLIGENCE_SYSTEM_DELIVERY.md` - Architecture & design details
- Module docstrings in source code

---

**Ready to trade with intelligence!** 🚀
