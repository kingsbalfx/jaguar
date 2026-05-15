# 🎯 COMPLETE RULE-BASED TRADING ARCHITECTURE
## Professional Implementation Guide - All Systems Unified

**Created**: May 7, 2026, 10:31 PM (Lagos/UTC+1)  
**Purpose**: Single-source rule-based architecture consolidating ALL systems  
**Type**: Pure Rule Logic (IF/THEN) - No Scoring, No Penalties

---

## 📋 TABLE OF CONTENTS

1. [Executive Summary](#executive-summary)
2. [Core ICT Rules (Non-Negotiable)](#core-ict-rules)
3. [Entry Decision Tree (Rule-Based)](#entry-decision-tree)
4. [Risk Management Rules](#risk-management-rules)
5. [Session & Timing Rules](#session-timing-rules)
6. [Complete Implementation Map](#implementation-map)
7. [File-by-File Implementation](#file-implementation)
8. [Testing & Validation](#testing-validation)

---

## 🎯 EXECUTIVE SUMMARY

### System Philosophy: PURE RULE-BASED
```
NO SCORING SYSTEMS
NO PENALTY CALCULATIONS
NO WEIGHTED COMPONENTS

ONLY: IF condition THEN action ELSE alternative
```

### Decision Flow (Simplified):
```
Market Data → ICT Rules Check → Risk Rules Check → Execute/Skip
     ↓               ↓                  ↓              ↓
  7 TFs      Core 4 Rules      Portfolio Limits    Trade
            (Liq/BOS/Zone/     Max Exposure        or
             Displacement)     Correlation         Wait
```

---

## 🔴 CORE ICT RULES (NON-NEGOTIABLE)

### RULE #1: LIQUIDITY SWEEP (Mandatory)
```python
IF liquidity_sweep_detected:
    # Continue to next check
ELSE:
    # SKIP - No liquidity sweep = No trade
    REASON = "ICT Rule: Liquidity sweep required"
    RETURN SKIP

# Detection Logic:
def check_liquidity_sweep(candles, direction):
    """
    BULLISH: Price sweeps below recent low, then closes higher
    BEARISH: Price sweeps above recent high, then closes lower
    """
    recent_highs = [c['high'] for c in candles[-20:]]
    recent_lows = [c['low'] for c in candles[-20:]]
    
    IF direction == "bullish":
        swing_low = min(recent_lows)
        sweep = current_low < (swing_low - buffer)
        recovery = current_close > swing_low
        RETURN (sweep AND recovery)
    
    ELIF direction == "bearish":
        swing_high = max(recent_highs)
        sweep = current_high > (swing_high + buffer)
        recovery = current_close < swing_high
        RETURN (sweep AND recovery)
```

---

### RULE #2: BREAK OF STRUCTURE (Mandatory)
```python
IF bos_confirmed:
    # Continue to next check
ELSE:
    # SKIP - No BOS = No trade
    REASON = "ICT Rule: BOS required"
    RETURN SKIP

# Detection Logic:
def check_bos(candles, trend):
    """
    Market must be in expansion phase (breaking structure)
    """
    IF trend == "bullish":
        prior_highs = [c['high'] for c in candles[-50:-10]]
        recent_high = max(candles[-5:]['high'])
        structure_break = recent_high > max(prior_highs)
        RETURN structure_break
    
    ELIF trend == "bearish":
        prior_lows = [c['low'] for c in candles[-50:-10]]
        recent_low = min(candles[-5:]['low'])
        structure_break = recent_low < min(prior_lows)
        RETURN structure_break
```

---

### RULE #3: VALID ENTRY ZONE (Mandatory)
```python
IF (fvg_present OR order_block_present):
    # At least ONE zone required
    # Continue to next check
ELSE:
    # SKIP - No entry zone
    REASON = "ICT Rule: Entry zone (FVG or OB) required"
    RETURN SKIP

# Detection Logic:
def check_entry_zone(price, fvgs, order_blocks, trend):
    """
    Price must be in a valid ICT zone
    """
    # Check FVGs
    FOR each fvg IN fvgs:
        IF fvg['type'] == trend:
            IF fvg['low'] <= price <= fvg['high']:
                IF NOT fvg['mitigated']:
                    RETURN True  # Valid FVG found
    
    # Check Order Blocks
    FOR each ob IN order_blocks:
        IF ob['type'] == trend:
            IF ob['low'] <= price <= ob['high']:
                IF NOT ob['mitigated']:
                    IF ob['quality'] >= 0.70:
                        RETURN True  # Valid OB found
    
    RETURN False  # No valid zone
```

---

### RULE #4: DISPLACEMENT (Mandatory)
```python
IF displacement >= 0.70:
    # Strong momentum confirmed
    # Continue to next check
ELSE:
    # SKIP - Weak displacement
    REASON = "ICT Rule: Displacement >= 70% required"
    RETURN SKIP

# Detection Logic:
def check_displacement(candle):
    """
    Impulse candle must have strong body (70%+ of total range)
    """
    body = abs(candle['close'] - candle['open'])
    range = candle['high'] - candle['low']
    
    IF range == 0:
        RETURN 0.0
    
    displacement_ratio = body / range
    RETURN displacement_ratio >= 0.70
```

---

## 🌳 ENTRY DECISION TREE (RULE-BASED)

### Master Decision Logic:
```python
def should_execute_trade(data):
    """
    Pure rule-based decision engine
    Returns: (EXECUTE: bool, REASON: str, ROUTE: str)
    """
    
    # ═══════════════════════════════════════════════════
    # GATE 1: CORE ICT RULES (ALL MANDATORY)
    # ═══════════════════════════════════════════════════
    
    IF NOT check_liquidity_sweep(data):
        RETURN (False, "Missing liquidity sweep", "SKIP")
    
    IF NOT check_bos(data):
        RETURN (False, "Missing BOS", "SKIP")
    
    IF NOT check_entry_zone(data):
        RETURN (False, "No valid entry zone", "SKIP")
    
    IF NOT check_displacement(data):
        RETURN (False, "Weak displacement (<70%)", "SKIP")
    
    # ═══════════════════════════════════════════════════
    # GATE 2: TREND VALIDATION
    # ═══════════════════════════════════════════════════
    
    trend = data['trend']
    IF trend NOT IN ['bullish', 'bearish']:
        RETURN (False, "No directional trend", "SKIP")
    
    trend_strength = data['trend_strength']
    IF trend_strength < 0.50:
        RETURN (False, "Trend too weak (<50%)", "SKIP")
    
    # ═══════════════════════════════════════════════════
    # GATE 3: SESSION TIMING
    # ═══════════════════════════════════════════════════
    
    IF NOT is_trading_session_active(data['asset_class']):
        RETURN (False, "Outside trading session", "SKIP")
    
    # ═══════════════════════════════════════════════════
    # GATE 4: RISK MANAGEMENT
    # ═══════════════════════════════════════════════════
    
    IF NOT check_portfolio_limits(data['symbol']):
        RETURN (False, "Portfolio limits exceeded", "SKIP")
    
    IF NOT check_correlation_risk(data['symbol']):
        RETURN (False, "High correlation risk", "SKIP")
    
    # ═══════════════════════════════════════════════════
    # GATE 5: QUALITY TIERS (OPTIONAL FILTERS)
    # ═══════════════════════════════════════════════════
    
    # These are OPTIONAL enhancements, not mandatory
    has_price_action = check_price_action_confirmation(data)
    has_smt = check_smt_divergence(data)
    in_premium_discount = check_premium_discount_zone(data)
    
    # Determine execution route based on quality
    IF (has_price_action AND has_smt AND in_premium_discount):
        ROUTE = "ELITE"  # Perfect setup
    ELIF (has_price_action OR has_smt):
        ROUTE = "STANDARD"  # Good setup
    ELSE:
        ROUTE = "BASIC"  # Minimal setup (core rules only)
    
    # ALL CORE RULES PASSED
    RETURN (True, "All ICT rules confirmed", ROUTE)
```

---

## 🛡️ RISK MANAGEMENT RULES

### Rule 1: Maximum Account Exposure
```python
def check_portfolio_limits(symbol):
    """
    Total exposure across all trades cannot exceed 6% of account
    """
    current_exposure = sum([trade.risk for trade in active_trades])
    account_balance = get_account_balance()
    max_exposure = account_balance * 0.06  # 6% max
    
    IF current_exposure >= max_exposure:
        RETURN False  # Cannot open new trade
    
    RETURN True
```

### Rule 2: Per-Trade Risk Limits
```python
def calculate_position_size(route, account_balance):
    """
    Risk per trade based on execution route
    """
    IF route == "ELITE":
        risk_percent = 0.020  # 2.0% risk
    ELIF route == "STANDARD":
        risk_percent = 0.015  # 1.5% risk
    ELIF route == "BASIC":
        risk_percent = 0.010  # 1.0% risk
    ELSE:
        risk_percent = 0.006  # 0.6% risk (conservative)
    
    risk_amount = account_balance * risk_percent
    RETURN risk_amount
```

### Rule 3: Correlation Risk
```python
def check_correlation_risk(new_symbol):
    """
    Prevent opening highly correlated positions simultaneously
    """
    correlated_pairs = {
        "EURUSD": ["GBPUSD", "AUDUSD"],
        "GBPUSD": ["EURUSD", "GBPAUD"],
        "BTCUSD": ["ETHUSD"],
        "XAUUSD": ["XAGUSD"]
    }
    
    IF new_symbol IN correlated_pairs:
        related = correlated_pairs[new_symbol]
        
        FOR symbol IN active_trades:
            IF symbol IN related:
                RETURN False  # Correlated position already open
    
    RETURN True
```

### Rule 4: Cooldown Between Trades
```python
def check_trade_cooldown(symbol):
    """
    Minimum 5 minutes between trades on same symbol
    """
    last_trade_time = get_last_trade_time(symbol)
    current_time = now()
    
    IF (current_time - last_trade_time) < 5_minutes:
        RETURN False  # Too soon
    
    RETURN True
```

---

## ⏰ SESSION & TIMING RULES

### Rule 1: Trading Session Windows
```python
def is_trading_session_active(asset_class):
    """
    Each asset class has specific trading hours
    """
    current_hour_utc = get_current_hour_utc()
    
    IF asset_class == "FOREX":
        # London: 7-16 UTC, NY: 12-21 UTC
        IF (7 <= current_hour_utc < 16) OR (12 <= current_hour_utc < 21):
            RETURN True
    
    ELIF asset_class == "CRYPTO":
        # 24/7 trading
        RETURN True
    
    ELIF asset_class == "INDICES":
        # Based on specific index hours
        IF 7 <= current_hour_utc < 21:
            RETURN True
    
    ELIF asset_class == "METALS":
        # London + NY sessions
        IF 7 <= current_hour_utc < 21:
            RETURN True
    
    RETURN False  # Outside trading hours
```

### Rule 2: Friday Drain Protection
```python
def check_friday_drain():
    """
    Avoid trading in final hours before weekend
    """
    day_of_week = get_day_of_week()
    hour_utc = get_current_hour_utc()
    
    IF day_of_week == "Friday":
        IF hour_utc >= 16:
            RETURN False  # Friday drain period
    
    RETURN True
```

### Rule 3: High Impact News Filter
```python
def check_news_filter(symbol):
    """
    Skip trading during high-impact news events
    """
    upcoming_news = get_upcoming_news(symbol, window=30_minutes)
    
    FOR event IN upcoming_news:
        IF event['impact'] == "HIGH":
            RETURN False  # High impact news imminent
    
    RETURN True
```

---

## 🗺️ COMPLETE IMPLEMENTATION MAP

### System Architecture (Rule-Based):
```
┌─────────────────────────────────────────────────────────┐
│                    MARKET DATA INPUT                    │
│              (7 Timeframes: D1/H4/H1/M30/M15/M5/M1)    │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ↓
┌─────────────────────────────────────────────────────────┐
│              GATE 1: CORE ICT RULES (MANDATORY)         │
│  ┌────────────┬────────────┬──────────────┬──────────┐│
│  │ Liquidity  │    BOS     │  Entry Zone  │Displacement││
│  │   Sweep    │ Confirmed  │  (FVG/OB)   │  >= 70%   ││
│  │    ✓/✗     │    ✓/✗     │     ✓/✗      │   ✓/✗     ││
│  └────────────┴────────────┴──────────────┴──────────┘│
│            IF ANY  ✗ → SKIP (Log reason)                │
└───────────────────────┬─────────────────────────────────┘
                        │ ALL ✓
                        ↓
┌─────────────────────────────────────────────────────────┐
│           GATE 2: TREND VALIDATION         │
│  - Directional trend(bullish/bearish)         │
│  - Trend strength >= 50%                         │
│            IF ✗ → SKIP                              │
└───────────────────────┬─────────────────────────────────┘
                        │ ✓
                        ↓
┌─────────────────────────────────────────────────────────┐
│              GATE 3: SESSION TIMING                     │
│  - Check asset class trading hours                      │
│  - Friday drain filter                                   │
│  - News filter                                           │
│            IF ✗ → SKIP                              │
└───────────────────────┬─────────────────────────────────┘
                        │ ✓
                        ↓
┌─────────────────────────────────────────────────────────┐
│            GATE 4: RISK MANAGEMENT                      │
│  - Portfolio exposure < 6%                               │
│  - Correlation check                                     │
│  - Cooldown timer                                        │
│            IF ✗ → SKIP                              │
└───────────────────────┬─────────────────────────────────┘
                        │ ✓
                        ↓
┌─────────────────────────────────────────────────────────┐
│         GATE 5: QUALITY ROUTING (OPTIONAL)              │
│  Check optional confirmations:                           │
│  - Price action patterns                                 │
│  - SMT divergence                                        │
│  - Premium/Discount zone                                 │
│                                                          │
│  Route Assignment:                                       │
│  - ELITE: All 3 optional confirmed                      │
│  - STANDARD: 1-2 optional confirmed                     │
│  - BASIC: Core rules only                               │
└───────────────────────┬─────────────────────────────────┘
                        │
                        ↓
┌─────────────────────────────────────────────────────────┐
│                  EXECUTE TRADE                          │
│  1. Calculate position size based on route              │
│  2. Calculate SL/TP levels                              │
│  3. Send order to MT5                                   │
│  4. Register trade in portfolio                         │
│  5. Log execution details                               │
└─────────────────────────────────────────────────────────┘
```

---

## 📁 FILE-BY-FILE IMPLEMENTATION

### 1. Core ICT Rules Engine
**File**: `ict_trading_bot/strategy/ict_rules_engine.py` (NEW)

```python
"""
Pure Rule-Based ICT Decision Engine
NO scoring, NO penalties - only IF/THEN logic
"""

class ICTRulesEngine:
    """Central rule-based decision engine"""
    
    def validate_core_rules(self, data):
        """
        Check ALL mandatory ICT rules
        Returns: (pass: bool, failures: list)
        """
        failures = []
        
        # Rule 1: Liquidity Sweep
        if not self._check_liquidity_sweep(data):
            failures.append("liquidity_sweep")
        
        # Rule 2: Break of Structure
        if not self._check_bos(data):
            failures.append("bos")
        
        # Rule 3: Entry Zone
        if not self._check_entry_zone(data):
            failures.append("entry_zone")
        
        # Rule 4: Displacement
        if not self._check_displacement(data):
            failures.append("displacement")
        
        passed = len(failures) == 0
        return passed, failures
    
    def determine_route(self, data):
        """
        Determine execution quality route
        Returns: str (ELITE | STANDARD | BASIC)
        """
        optional_checks = {
            'price_action': self._check_price_action(data),
            'smt': self._check_smt_divergence(data),
            'pd_zone': self._check_premium_discount(data)
        }
        
        confirmed_count = sum(optional_checks.values())
        
        if confirmed_count >= 3:
            return "ELITE"
        elif confirmed_count >= 1:
            return "STANDARD"
        else:
            return "BASIC"
    
    def _check_liquidity_sweep(self, data):
        """Rule: Liquidity sweep required"""
        return data.get('liquidity_sweep_confirmed', False)
    
    def _check_bos(self, data):
        """Rule: BOS required"""
        return data.get('bos_confirmed', False)
    
    def _check_entry_zone(self, data):
        """Rule: FVG or OB required"""
        has_fvg = data.get('fvg_present', False)
        has_ob = data.get('ob_present', False)
        return (has_fvg or has_ob)
    
    def _check_displacement(self, data):
        """Rule: Displacement >= 70%"""
        disp = data.get('displacement', 0.0)
        return disp >= 0.70
    
    def _check_price_action(self, data):
        """Optional: Price action confirmation"""
        return data.get('price_action_confirmed', False)
    
    def _check_smt_divergence(self, data):
        """Optional: SMT divergence"""
        return data.get('smt_divergence', False)
    
    def _check_premium_discount(self, data):
        """Optional: In PD zone"""
        return data.get('in_pd_zone', False)
```

---

### 2. Risk Management Rules
**File**: `ict_trading_bot/risk/rule_based_risk.py` (NEW)

```python
"""
Rule-Based Risk Management
Clear IF/THEN logic for all risk decisions
"""

class RuleBasedRisk:
    """Enforces all risk management rules"""
    
    def __init__(self, max_account_risk=0.06):
        self.max_account_risk = max_account_risk
        self.correlation_map = {
            "EURUSD": ["GBPUSD", "AUDUSD"],
            "GBPUSD": ["EURUSD", "GBPAUD"],
            "BTCUSD": ["ETHUSD"],
            "XAUUSD": ["XAGUSD"]
        }
    
    def can_open_trade(self, symbol, active_trades):
        """
        Master risk check - ALL must pass
        Returns: (allowed: bool, reason: str)
        """
        # Check 1: Portfolio exposure
        if not self._check_portfolio_exposure(active_trades):
            return False, "Portfolio exposure limit (6%) reached"
        
        # Check 2: Correlation risk
        if not self._check_correlation(symbol, active_trades):
            return False, f"Correlated position already open"
        
        # Check 3: Cooldown
        if not self._check_cooldown(symbol):
            return False, "Trade cooldown active (5 min)"
        
        # All checks passed
        return True, "All risk checks passed"
    
    def calculate_position_size(self, route, account_balance, sl_distance):
        """
        Calculate position size based on route
        """
        # Risk per trade by route
        risk_map = {
            "ELITE": 0.020,      # 2.0%
            "STANDARD": 0.015,   # 1.5%
            "BASIC": 0.010       # 1.0%
        }
        
        risk_percent = risk_map.get(route, 0.006)
        risk_amount = account_balance * risk_percent
        
        # Position size = risk / SL distance
        position_size = risk_amount / sl_distance
        
        return position_size
    
    def _check_portfolio_exposure(self, active_trades):
        """Rule: Total exposure < 6%"""
        total_risk = sum([t['risk_percent'] for t in active_trades])
        return total_risk < self.max_account_risk
    
    def _check_correlation(self, symbol, active_trades):
        """Rule: No correlated positions"""
        if symbol in self.correlation_map:
            correlated = self.correlation_map[symbol]
            active_symbols = [t['symbol'] for t in active_trades]
            
            for s in active_symbols:
                if s in correlated:
                    return False  # Correlated position found
        
        return True
    
    def _check_cooldown(self, symbol):
        """Rule: 5 min cooldown between trades"""
        # Implementation would check last trade timestamp
        # Simplified for example
        return True
```

---

### 3. Session Rules
**File**: `ict_trading_bot/utils/session_rules.py` (NEW)

```python
"""
Session and Timing Rules
Clear trading windows per asset class
"""

from datetime import datetime

class SessionRules:
    """Manages all session-related rules"""
    
    def is_session_active(self, asset_class):
        """
        Check if trading session is active for asset class
        Returns: bool
        """
        hour_utc = datetime.utcnow().hour
        
        if asset_class == "FOREX":
            # London (7-16) OR NY (12-21)
            return (7 <= hour_utc < 16) or (12 <= hour_utc < 21)
        
        elif asset_class == "CRYPTO":
            # 24/7
            return True
        
        elif asset_class in ["INDICES", "METALS"]:
            # 7-21 UTC
            return 7 <= hour_utc < 21
        
        else:
            return False
    
    def check_friday_drain(self):
        """
        Rule: No trading Friday after 16:00 UTC
        Returns: bool (True = can trade)
        """
        now = datetime.utcnow()
        
        if now.weekday() == 4:  # Friday
            if now.hour >= 16:
                return False  # Friday drain period
        
        return True
    
    def check_news_filter(self, symbol, upcoming_news):
        """
        Rule: Avoid high-impact news
        Returns: bool (True = can trade)
        """
        for event in upcoming_news:
            if event.get('impact') == 'HIGH':
                return False
        
        return True
```

---

### 4. Main Trading Loop Integration
**File**: `ict_trading_bot/main_rule_based.py` (NEW)

```python
"""
Main trading loop using pure rule-based logic
NO scoring systems - only rule validation
"""

from strategy.ict_rules_engine import ICTRulesEngine
from risk.rule_based_risk import RuleBasedRisk
from utils.session_rules import SessionRules

def trading_loop():
    """
    Main trading loop with rule-based decisions
    """
    # Initialize engines
    ict_engine = ICTRulesEngine()
    risk_manager = RuleBasedRisk(max_account_risk=0.06)
    session_rules = SessionRules()
    
    # Get symbols to analyze
    symbols = load_trading_symbols()
    
    for symbol in symbols:
        # ═══════════════════════════════════════════
        # STEP 1: Gather Market Data
        # ═══════════════════════════════════════════
        data = analyze_market(symbol)
        
        # ═══════════════════════════════════════════
        # STEP 2: Check Core ICT Rules
        # ═══════════════════════════════════════════
        rules_passed, failures = ict_engine.validate_core_rules(data)
        
        if not rules_passed:
            log_skip(symbol, f"ICT rules failed: {failures}")
            continue  # SKIP this symbol
        
        # ═══════════════════════════════════════════
        # STEP 3: Check Trend
        # ═══════════════════════════════════════════
        if data['trend'] not in ['bullish', 'bearish']:
            log_skip(symbol, "No directional trend")
            continue
        
        if data['trend_strength'] < 0.50:
            log_skip(symbol, "Trend too weak")
            continue
        
        # ═══════════════════════════════════════════
        # STEP 4: Check Session Rules
        # ═══════════════════════════════════════════
        if not session_rules.is_session_active(data['asset_class']):
            log_skip(symbol, "Outside trading session")
            continue
        
        if not session_rules.check_friday_drain():
            log_skip(symbol, "Friday drain period")
            continue
        
        # ═══════════════════════════════════════════
        # STEP 5: Check Risk Management
        # ═══════════════════════════════════════════
        active_trades = get_active_trades()
        can_trade, risk_reason = risk_manager.can_open_trade(symbol, active_trades)
        
        if not can_trade:
            log_skip(symbol, risk_reason)
            continue
        
        # ═══════════════════════════════════════════
        # STEP 6: Determine Execution Route
        # ═══════════════════════════════════════════
        route = ict_engine.determine_route(data)
        
        # ═══════════════════════════════════════════
        # STEP 7: Execute Trade
        # ═══════════════════════════════════════════
        execute_trade(symbol, data, route, risk_manager)
        
        log_execution(symbol, route, "All rules passed")


def execute_trade(symbol, data, route, risk_manager):
    """Execute trade with calculated position size"""
    
    # Calculate position size based on route
    account_balance = get_account_balance()
    sl_distance = calculate_sl_distance(data)
    
    position_size = risk_manager.calculate_position_size(
        route, 
        account_balance, 
        sl_distance
    )
    
    # Calculate SL/TP
    entry_price = data['price']
    sl = calculate_stop_loss(data, entry_price)
    tp = calculate_take_profit(data, entry_price, sl_distance)
    
    # Send order to MT5
    order = {
        'symbol': symbol,
        'direction': data['direction'],
        'entry': entry_price,
        'sl': sl,
        'tp': tp,
        'volume': position_size,
        'route': route
    }
    
    send_order_to_mt5(order)
    register_trade(order)
    log_trade(order)
```

---

## ✅ TESTING & VALIDATION

### Test Suite 1: ICT Rules Validation
```python
def test_ict_rules():
    """Test all ICT rule checks"""
    
    # Test Case 1: All rules pass
    perfect_setup = {
        'liquidity_sweep_confirmed': True,
        'bos_confirmed': True,
        'fvg_present': True,
        'ob_present': True,
        'displacement': 0.75
    }
    assert ict_engine.validate_core_rules(perfect_setup)[0] == True
    
    # Test Case 2: Missing liquidity
    no_liq = {
        'liquidity_sweep_confirmed': False,
        'bos_confirmed': True,
        'fvg_present': True,
        'displacement': 0.75
    }
    passed, failures = ict_engine.validate_core_rules(no_liq)
    assert passed == False
    assert 'liquidity_sweep' in failures
    
    # Test Case 3: Weak displacement
    weak_disp = {
        'liquidity_sweep_confirmed': True,
        'bos_confirmed': True,
        'fvg_present': True,
        'displacement': 0.65  # Below 0.70
    }
    passed, failures = ict_engine.validate_core_rules(weak_disp)
    assert passed == False
    assert 'displacement' in failures
```

### Test Suite 2: Risk Management
```python
def test_risk_rules():
    """Test risk management rules"""
    
    # Test Case 1: Portfolio limit
    active_trades = [
        {'risk_percent': 0.02},
        {'risk_percent': 0.02},
        {'risk_percent': 0.02}  # Total = 6%
    ]
    can_trade, reason = risk_manager.can_open_trade("EURUSD", active_trades)
    assert can_trade == False  # At limit
    
    # Test Case 2: Correlation check
    active_trades = [{'symbol': 'EURUSD', 'risk_percent': 0.02}]
    can_trade, reason = risk_manager.can_open_trade("GBPUSD", active_trades)
    assert can_trade == False  # Correlated
    
    # Test Case 3: Position sizing
    position_size = risk_manager.calculate_position_size(
        route="ELITE",
        account_balance=10000,
        sl_distance=50  # pips
    )
    expected_risk = 10000 * 0.02  # 2% = $200
    expected_size = 200 / 50  # = 4 lots
    assert abs(position_size - expected_size) < 0.01
```

### Test Suite 3: Session Rules
```python
def test_session_rules():
    """Test session timing rules"""
    
    # Test Case 1: FOREX during London
    # Mock time = 10:00 UTC
    assert session_rules.is_session_active("FOREX") == True
    
    # Test Case 2: FOREX during dead zone
    # Mock time = 3:00 UTC
    assert session_rules.is_session_active("FOREX") == False
    
    # Test Case 3: CRYPTO always active
    assert session_rules.is_session_active("CRYPTO") == True
    
    # Test Case 4: Friday drain
    # Mock Friday 17:00 UTC
    assert session_rules.check_friday_drain() == False
```

---

## 📝 IMPLEMENTATION CHECKLIST

### Phase 1: Core Setup (Week 1)
- [ ] Create `ict_rules_engine.py` with all rule checks
- [ ] Create `rule_based_risk.py` with risk management
- [ ] Create `session_rules.py` with timing logic
- [ ] Write unit tests for each rule module
- [ ] Test individual rule validations

### Phase 2: Integration (Week 2)
- [ ] Create `main_rule_based.py` trading loop
- [ ] Integrate all rule engines into main loop
- [ ] Connect to MT5 for order execution
- [ ] Implement logging and monitoring
- [ ] Test end-to-end flow with paper trading

### Phase 3: Deployment (Week 3)
- [ ] Run backtest on historical data
- [ ] Validate rule logic against ICT principles
- [ ] Deploy to staging environment
- [ ] Monitor for 48 hours
- [ ] Deploy to production

### Phase 4: Optimization (Week 4)
- [ ] Analyze execution rate (should be 15-25%)
- [ ] Fine-tune optional confirmations
- [ ] Adjust risk parameters if needed
- [ ] Document performance metrics
- [ ] Create user guide

---

## 🎯 EXPECTED OUTCOMES

### Before (Scoring System):
```
✗ Complex penalty calculations
✗ Unclear why trades rejected
✗ Hard to tune thresholds
✗ Difficult to debug
```

### After (Rule-Based):
```
✓ Clear IF/THEN logic
✓ Explicit rejection reasons
✓ Easy to enable/disable rules
✓ Simple to debug and test
✓ Professional rule engine
```

---

## 📊 PERFORMANCE METRICS

### Expected Results:
- **Setup Pass Rate**: 15-25% (healthy filtering)
- **Trades Per Day**: 3-8 trades
- **Average Hold Time**: 4-12 hours
- **Win Rate Target**: 45-55%
- **Risk/Reward**: Minimum 1.5:1, target 2:1+
- **Max Drawdown**: <15% (with 6% exposure limit)

---

**Status**: 📘 COMPREHENSIVE RULE-BASED ARCHITECTURE COMPLETE  
**Implementation Time**: 3-4 weeks  
**Complexity**: Professional-grade  
**Maintainability**: Excellent (clear rules)  
**Testability**: Excellent (each rule testable)


