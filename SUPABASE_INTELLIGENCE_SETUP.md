# Intelligence System - Supabase SQL Setup

## ✅ STATUS

**INTELLIGENCE SYSTEM READY** ✓
**SQL TABLES READY** ✓
**READY FOR SUPABASE** ✓

---

## 🚀 How to Run SQL in Supabase

### Step 1: Go to Supabase Dashboard
1. Open https://supabase.com/
2. Sign in to your project (KingsBalfx)
3. Click **"SQL Editor"** in the left sidebar

### Step 2: Copy the SQL
```
File: INTELLIGENCE_SYSTEM_SUPABASE.sql
Location: c:\Users\kingsbal\Documents\GitHub\jaguar\
```

**Copy the ENTIRE contents of this file**

### Step 3: Paste & Run in Supabase
1. Click **"+ New Query"** in SQL Editor
2. Paste the entire SQL script
3. Click **"Run"** button (⌘ Enter or Ctrl+Enter)
4. **Wait for confirmation**: "Success" message

### Step 4: Verify Tables Created
In Supabase left sidebar:
- [ ] Click "Table Editor"
- [ ] You should see 6 new tables:
  - `market_conditions`
  - `cis_decisions`
  - `trade_executions`
  - `strategy_performance`
  - `component_effectiveness`
  - `validation_checks`

---

## 📊 What Each Table Stores

### 1. **market_conditions**
Stores volatility analysis for each pair

```
Example row:
symbol: "EURUSD"
volatility_index: 0.65
market_condition: "stable"
atr_percent: 0.041
position_size_adjustment: 1.0
```

### 2. **cis_decisions**
Every trading decision made by the intelligence system

```
Example row:
symbol: "EURUSD"
direction: "BUY"
final_verdict: "TRADE"
confidence_score: 0.82
setup_quality_score: 0.85
market_condition_score: 0.75
risk_profile_score: 0.80
timing_score: 0.85
```

### 3. **trade_executions**
Tracks actual trades that were executed

```
Example row:
symbol: "EURUSD"
entry_price: 1.0850
exit_price: 1.0895
profit_loss: 450.00
win: true
duration_minutes: 120
```

### 4. **strategy_performance**
Daily/hourly performance metrics

```
Example row:
period_date: "2026-03-29"
symbol: "EURUSD"
total_trades: 5
winning_trades: 3
win_rate: 60.00
net_pnl: 1250.00
```

### 5. **component_effectiveness**
Tracks which factors are most predictive

```
Learns over time:
"setup_quality" with score 0.80-1.00 has 70% win rate
"market_condition" with score 0.70-1.00 has 65% win rate
```

### 6. **validation_checks**
Debug/audit trail of validation checks

```
cis_decision_id: UUID
check_name: "broker_connection"
check_result: true
message: "MT5 connected"
```

---

## 🔗 How to Connect Python Bot to Supabase

### Option 1: Using Python Supabase Client

```python
from supabase import create_client, Client

# Initialize Supabase
url = "https://your-project.supabase.co"
key = "your-anon-key"
supabase: Client = create_client(url, key)

# Save a CIS decision
cis_data = {
    "symbol": "EURUSD",
    "direction": "BUY",
    "final_verdict": "TRADE",
    "confidence_score": 0.82,
    "setup_quality_score": 0.85,
    # ... etc
}

result = supabase.table("cis_decisions").insert(cis_data).execute()

# Query decisions
decisions = supabase.table("cis_decisions")\
    .select("*")\
    .eq("symbol", "EURUSD")\
    .order("created_at", desc=True)\
    .limit(100)\
    .execute()

for decision in decisions.data:
    print(f"{decision['symbol']} - {decision['final_verdict']}")
```

### Option 2: Using REST API

```python
import requests
import json

SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_KEY = "your-anon-key"

# Add a CIS decision
payload = {
    "symbol": "EURUSD",
    "direction": "BUY",
    "final_verdict": "TRADE",
    "confidence_score": 0.82
}

response = requests.post(
    f"{SUPABASE_URL}/rest/v1/cis_decisions",
    headers={
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json"
    },
    json=payload
)

print(response.json())
```

---

## 📝 Integration Checklist

**Before Running Bot:**
- [ ] Run SQL script in Supabase
- [ ] Verify 6 tables created
- [ ] Get Supabase URL and API key
- [ ] Install Python client: `pip install supabase`
- [ ] Add Supabase credentials to bot config

**During Bot Operation:**
- [ ] Each CIS decision auto-saves to `cis_decisions` table
- [ ] Market conditions auto-save to `market_conditions` table
- [ ] Trades auto-save to `trade_executions` table
- [ ] Stats auto-calculate to `strategy_performance` table

**For Analytics:**
- [ ] Query `strategy_performance` for daily reports
- [ ] Query `trade_executions` for win rate
- [ ] Query `component_effectiveness` for optimization insights

---

## 🔐 Security Notes

**RLS Policies Enabled:**
- ✅ Users see only their own decisions
- ✅ Market data is public (all see same volatility)
- ✅ Admin can see all data

**Credentials:**
- `url`: Found in Supabase project settings
- `key`: Use **Anon Public Key** (not service role)
- Store in `.env` file, NOT in code

---

## 📋 SQL Migration Files

Two files available:

### 1. **migrations/005_intelligence_system_tables.sql**
- Full migration with comments
- Use with migration tools
- More detailed

### 2. **INTELLIGENCE_SYSTEM_SUPABASE.sql**
- Direct copy-paste format
- No extra comments
- Faster setup

**Use #2 for direct Supabase setup** ✓

---

## ✨ What's Next

After SQL tables are created:

1. **Integrate with Bot**
   - Import `intelligence_system_integration.py`
   - Connect to Supabase
   - Auto-save decisions

2. **Track Performance**
   - Query `strategy_performance` daily
   - Monitor win rates
   - Adjust thresholds

3. **Optimize System**
   - Use `component_effectiveness` data
   - Learn which factors matter most
   - Adjust weights over time

---

## 🆘 Troubleshooting

### "ERROR: relation does not exist"
→ SQL wasn't run successfully
→ Check for error messages in Supabase editor
→ Try running line by line

### "ERROR: Unique constraint violated"
→ Table already exists from previous run
→ This is OK, script handles it with `IF NOT EXISTS`

### "Tables created but no data showing"
→ They're empty (normal)
→ Run bot, it will populate them
→ Or insert test data manually

### "Can't connect from Python"
→ Check URL and Key are correct
→ Verify `pip install supabase`
→ Test credentials in Supabase dashboard first

---

## 📞 Quick Links

- **Supabase Dashboard**: https://supabase.com/
- **Python Client**: `pip install supabase`
- **SQL File**: `INTELLIGENCE_SYSTEM_SUPABASE.sql`
- **Bot Code**: `intelligence_system_integration.py`

---

**Ready to set up!** 🚀

Just copy/paste the SQL into Supabase SQL Editor and click Run.
