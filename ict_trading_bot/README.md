# 🤖 ICT Trading Bot - Simple Start Guide

Hi! This is a **ROBOT that trades money** for you! Like a worker bee working while you sleep! 🐝

## What Does This Bot Do?

The bot:
- 🔍 **Looks at the market** every minute
- 💡 **Decides** if it should buy or sell
- 💰 **Opens trades** when conditions are perfect
- 🛡️ **Protects your money** with stop loss
- 📊 **Sends reports** to the web dashboard

## Super Simple Explanation (Like You're 5)

Imagine you have a little robot friend:
- **You give the robot money** (your trading account)
- **You tell the robot the rules** (risk per trade, which coins to trade)
- **The robot watches the market 24/7**
- **When it sees a good opportunity, it trades**
- **You check your dashboard to see what the robot did**

That's it! 🎉

## Quick Setup (5 Minutes)

### One-Click Windows Setup (Recommended)
```powershell
# From the ict_trading_bot folder:
.\setup_windows.ps1
```
This creates a virtual environment, installs dependencies, and copies `.env.example` to `.env`.

### Auto-Start on Windows (Optional)
```powershell
# Creates a Scheduled Task that runs the bot at logon
.\setup_autostart.ps1
```

### Step 1: Install Everything
```bash
# Open your terminal and type this:
pip install -r requirements.txt

# This downloads all the robot's "parts" (libraries)
```

### Step 2: Create Your Settings File
```bash
# Copy the example:
cp .env.example .env

# Edit it with your information:
nano .env
```

**What to put in .env:**
```
BOT_ENABLED=true           # Turn robot ON
RISK_PER_TRADE=1.0        # Risk 1% of money per trade
MAX_OPEN_TRADES=5         # Only 5 trades at same time
# The bot persists signals/logs to Supabase; set SUPABASE_URL and SUPABASE_KEY
SUPABASE_URL=your_database_url
SUPABASE_KEY=your_service_role_key
```
MT5 credentials are stored in Supabase via the Admin panel, not in `.env`.

### Step 3: Start the Robot!
```bash
# Run the bot:
python main.py

# You should see:
# ✅ All settings loaded!
# 🤖 Bot started successfully
# 📡 Health check: OK
```

## Check if It's Working

### Method 1: Health Check
```bash
# In another terminal:
curl https://your-bot-host:8000/health

# Should show: {"status":"ok","running":true}
```

### Method 2: Check Status
```bash
curl https://your-bot-host:8000/status

# Should show what the bot is doing
```

### Method 3: Control the Bot
```bash
# Stop the robot:
curl -X POST https://your-bot-host:8000/control \
  -H "Content-Type: application/json" \
  -d '{"action":"stop"}'

# Start the robot:
curl -X POST https://your-bot-host:8000/control \
  -H "Content-Type: application/json" \
  -d '{"action":"start"}'

# Restart MT5 connection (reload credentials):
curl -X POST https://your-bot-host:8000/restart
```

## Files Explained (What Each Part Does)

| File | What It Does |
|------|------|
| `main.py` | The robot's brain (starts everything) |
| `bot_api.py` | The robot's phone (gets commands) |
| `config/bot_config.py` | Robot's settings (risk, symbols, etc) |
| `execution/` | Robot's hands (opens/closes trades) |
| `strategy/` | Robot's eyes (finds good trades) |
| `risk/` | Robot's safety (protects money) |
| `dashboard/` | Robot's mouth (tells web what happened) |

## What Symbols (Coins) Can It Trade?

The robot can trade:
- `EURUSD` 🇪🇺🇺🇸
- `GBPUSD` 🇬🇧🇺🇸
- `USDJPY` 🇺🇸🇯🇵
- `AUDUSD` 🇦🇺🇺🇸
- `NZDUSD` 🇳🇿🇺🇸
- `USDCAD` 🇺🇸🇨🇦
- `BTCUSD` ₿
- `XAUUSD` 🥇
- And more!

## When Does It Trade?

The robot only trades during BUSY hours (like when the market is awake):

- 🕘 **London Time**: 8 AM to 4 PM (UTC)
- 🕐 **New York Time**: 1 PM to 9 PM (UTC)

**Why?** Because the market is sleeping other times! Prices don't move much when the market is closed.

## Safety Rules (So Your Money Doesn't Disappear)

- ✅ **Only risk 1% per trade** (if you have $100, lose max $1)
- ✅ **Never open more than 5 trades** at the same time
- ✅ **Always set stop loss** (so losses are small)
- ✅ **Always set take profit** (so profits are locked)
- ✅ **Stop trading during news events** (market goes crazy!)

## Troubleshooting (What to Do if Something Breaks)

### Bot Won't Start
```
Problem: Error when running python main.py
Fix: 1. Check .env file has all values
     2. Check internet connection
     3. Check python is installed: python --version
```

### Bot Not Connecting to MT5
```
Problem: "Cannot connect to MT5"
Fix: 1. Open MT5 on your computer
     2. Update MT5 credentials in the Admin panel
     3. Restart MT5
     4. Run bot again
```

### No Trades Happening
```
Problem: "Bot running but no trades"
Check: 1. Is it trading hours? (8am-4pm London or 1pm-9pm NY)
       2. Check market is moving
       3. Look at bot logs for errors
       4. Check if BOT_ENABLED=true in .env
```

### Memory/Speed Issue
```
Problem: Bot running slowly
Fix: 1. Buy more RAM
     2. Close other programs
     3. Restart the bot
     4. Check database connection
```

## Testing Before Money (SUPER IMPORTANT!)

**NEVER** run this on real money first!

### Step 1: Use Demo Account
```
✅ Sign up for demo trading account
✅ Get fake money to practice
✅ Run the bot on demo
✅ Watch it trade for 1-2 weeks
✅ Check if it works well
```

### Step 2: Run Local Tests
```bash
# Test the bot code:
pytest tests/ -v

# Test specific parts:
pytest tests/test_validation.py -v
```

### Step 3: Check Reports
```
✅ Open dashboard at https://kingsbalfx.name.ng/admin
✅ Look at analytics section
✅ Check win rate and profit
✅ Review individual trades
```

## Next Steps

1. ✅ **Setup** - Follow steps above
2. ✅ **Test** - Run on demo account
3. ✅ **Monitor** - Watch dashboard daily
4. ✅ **Deploy** - Move to real account (carefully!)

## Get Help

- 📖 Read `ARCHITECTURE.md` - System design
- 📊 Read `TRADER_GUIDE.md` - Trading tips
- 🔒 Read `SECURITY_CHECKLIST.md` - Safety first!

## Remember!

⚠️ **IMPORTANT**: 
- Past performance ≠ Future results
- You can LOSE money with this bot
- Start with SMALL amounts
- Monitor DAILY
- Take breaks from trading

---

**Status**: ✅ Ready to trade!
**Last Updated**: Feb 10, 2026


