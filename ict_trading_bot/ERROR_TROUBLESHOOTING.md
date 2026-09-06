# ICT TRADING BOT - ERROR TROUBLESHOOTING GUIDE

## Overview

This guide explains the errors you might see when running the bot and how to fix them.

## Most Common Errors

### 1. "Failed to create Supabase client: Invalid URL"

**What it means**: The bot tried to connect to Supabase but the URL or API key is invalid.

**Why it happens**:
- `.env` file has invalid/expired Supabase credentials
- SUPABASE_URL or SUPABASE_KEY is missing or malformed
- Network connection issue

**How to fix it**:

**Option A: Disable Supabase** (Recommended if you don't need cloud features)
```powershell
# Edit .env and comment out these lines:
# SUPABASE_URL=https://...
# SUPABASE_KEY=...
```

**Option B: Update credentials**
```powershell
# Run the credential configurator
python configure_credentials.py

# Select option 1 to configure Supabase
# Enter your verified Supabase URL and API key
```

**Option C: Use local storage**
If you've already configured credentials once:
```powershell
# Credentials are stored in:
# C:\Users\[username]\.ict_trading_bot\credentials.json

# They'll be loaded automatically next time you start the bot
python main.py
```

**Result**: The message "⚠️ Supabase credentials not configured. Running in local-only mode." is normal and expected if you don't need cloud features.

---

### 2. "IPC initialize failed, Pipe server didn't answer in 60 sec"

**What it means**: MetaTrader 5 didn't respond to the bot's connection request.

**Why it happens**:
- MT5 is not running
- MT5 is busy initializing
- Firewall or network issue
- MT5 process crashed
- System resources (RAM, CPU) exhausted

**How to fix it**:

**Step 1**: Verify MT5 is running
```powershell
# Check if MT5 process is alive
Get-Process terminal64 -ErrorAction SilentlyContinue

# If not running, start MT5 manually
C:\Program Files\MetaTrader 5\terminal64.exe
```

**Step 2**: Check firewall and antivirus
- Ensure MT5 has firewall permission
- Add project folder to antivirus whitelist
- Disable Real-Time Protection temporarily to test

**Step 3**: Check system resources
- Open Task Manager (Ctrl+Shift+Esc)
- Check if RAM usage is > 90%
- Check if CPU usage is consistently > 80%
- If yes, close other applications

**Step 4**: Restart MT5
```powershell
# Kill MT5 process
Stop-Process -Name terminal64 -Force

# Wait for cleanup
Start-Sleep -Seconds 3

# Restart MT5
C:\Program Files\MetaTrader 5\terminal64.exe

# Wait for MT5 to fully initialize (30-60 seconds)
Start-Sleep -Seconds 60

# Start the bot
python main.py
```

**Step 5**: Check MT5 logs
- Open MT5
- View → Experts → Journal
- Look for connection or initialization errors

**What to expect**: After MT5 is fully running, the bot should connect within 10-30 seconds.

---

### 3. "Unable to connect to MT5"

**What it means**: Even after retries, the bot couldn't establish a connection to MetaTrader 5.

**Why it happens**:
- MT5 wasn't running when bot started
- MT5 crashed after initial connection attempt
- Invalid MT5 credentials (login/password/server)
- Your MT5 account is locked or disabled

**How to fix it**:

**Step 1**: Verify MT5 account credentials
```powershell
# In MT5, check:
# File → Account Settings
# Verify:
#   - Login number
#   - Server name
#   - Account status is "Active"
```

**Step 2**: Check MT5 environment variables
```powershell
# Edit .env and verify these are correct:
MT5_ACCOUNT_LOGIN=your_login_number
MT5_ACCOUNT_PASSWORD=your_password
MT5_ACCOUNT_SERVER=server_name

# Or set them for this session only:
$env:MT5_ACCOUNT_LOGIN = "12345"
$env:MT5_ACCOUNT_PASSWORD = "password"
$env:MT5_ACCOUNT_SERVER = "Headway-Demo"
python main.py
```

**Step 3**: Test connection manually
```powershell
python -c "
import MetaTrader5 as mt5
print(f'MT5 version: {mt5.version()}')
if mt5.initialize():
    print('✅ MT5 initialized')
    if mt5.login(12345, 'password', 'Headway-Demo'):
        print('✅ Login successful')
    else:
        print(f'❌ Login failed: {mt5.last_error()}')
else:
    print(f'❌ Initialization failed: {mt5.last_error()}')
"
```

**Step 4**: Contact broker support
If all above steps pass but bot still can't connect:
- Account may be temporarily locked
- Server may have connection restrictions
- Broker may need additional verification

---

### 4. "SCAN SUMMARY | ... errors=X"

**What it means**: The bot encountered errors while scanning symbols for trading opportunities.

**Why it happens**:
- Symbol data unavailable from broker
- Network connectivity issue
- MT5 data feed is lagging
- Temporary broker server issue

**Severity levels**:
- `errors=0`: Normal, no issues
- `errors=1-5`: Minor issues, bot continues
- `errors=10+`: Significant problems, monitor carefully

**How to fix it**:

**For occasional errors (1-5)**:
- Usually temporary, bot recovers on next scan
- Check network connection
- Verify symbols are tradable on your account

**For frequent errors (10+)**:
1. Check MT5 connection
2. Verify all symbols in your config are available
3. Reduce number of symbols to scan
4. Contact broker support

---

### 5. "Symbol ... marked as untradable"

**What it means**: A symbol in your config is not available for trading on your account.

**Why it happens**:
- You don't have permission to trade this symbol
- Symbol is not available in your broker's market
- Symbol name is incorrect or has been renamed
- Account tier doesn't include this symbol

**How to fix it**:

**Option 1: Update symbol list**
```powershell
# Check available symbols in MT5:
python -c "
import MetaTrader5 as mt5
mt5.initialize()
mt5.login(your_login, 'password', 'server')

# Get all tradable symbols
symbols = mt5.symbols_get()
for s in symbols:
    if 'EUR' in s.name and s.select:
        print(s.name)
"
```

**Option 2: Use AUTO_EXTRACT_MT5_SYMBOLS**
```powershell
# In .env, set:
AUTO_EXTRACT_MT5_SYMBOLS=true

# This auto-discovers available symbols on your account
```

**Option 3: Filter symbols**
```powershell
# In .env, use:
MT5_SYMBOL_ALLOWLIST=EURUSD,GBPUSD,XAUUSD
# Or:
MT5_SYMBOL_BLOCKLIST=USDJPY,NZDUSD
```

---

### 6. "Failed to validate Supabase connection"

**What it means**: The bot attempted to validate Supabase credentials during startup but failed.

**Why it happens**:
- Invalid credentials
- Network unreachable
- Supabase server is down
- Regional restriction

**How to fix it**:

**Step 1**: Test internet connection
```powershell
Test-NetConnection -ComputerName app.supabase.com -Port 443
```

**Step 2**: Verify Supabase URL format
```
Should be: https://xxxxx.supabase.co
Should NOT be: https://xxxxx.supabase.co/
```

**Step 3**: Get new credentials
- Go to: https://app.supabase.com
- Navigate to: Project > Settings > API
- Copy the "Project URL" and "anon public" key
- Run: `python configure_credentials.py`

**Step 4**: Fallback to local mode
```powershell
# Set empty credentials in .env:
SUPABASE_URL=
SUPABASE_KEY=

# Bot will run in local-only mode
python main.py
```

---

### 7. "Mirror trading not working"

**What it means**: The bot is not coordinating trades across multiple accounts.

**Why it happens**:
- Mirror trading disabled (MIRROR_TRADING_ENABLED=false)
- Supabase credentials not configured
- Accounts not in same coordination group
- Network issues between accounts

**How to fix it**:

**Step 1**: Enable mirror trading
```powershell
# In .env, set:
MIRROR_TRADING_ENABLED=true
MIRROR_AUTO_OPEN=true

# Then run:
python main.py
```

**Step 2**: Configure Supabase** (optional, uses local file fallback if not available)
```powershell
python configure_credentials.py
# Select option 3: Configure mirror trading
```

**Step 3**: Check multi-account setup**
```powershell
# Edit accounts.json:
[
  {
    "login": "12345",
    "password": "pass",
    "server": "Headway-Demo"
  },
  {
    "login": "67890",
    "password": "pass",
    "server": "Headway-Demo"
  }
]

# Then run:
python main.py
```

**Fallback mode**: If Supabase is not available, mirror trading will use local file-based coordination. This works perfectly for accounts on the same machine but won't coordinate across different machines.

---

## Error Message Categories

### 🔴 Critical Errors (Bot Won't Start)
- "Python 3.9+ required"
- "Unable to connect to MT5"
- "MetaTrader 5 not installed"

**Action**: Fix the issue and restart

### 🟡 Warning Messages (Bot Continues)
- "Failed to create Supabase client"
- "Symbol marked as untradable"
- "IPC initialize retry"

**Action**: Monitor, may self-recover

### ℹ️ Informational Messages (Normal Operation)
- "Running in local-only mode"
- "SCAN COMPLETE | sleeping=60s"
- "Waiting for next account"

**Action**: No action needed

---

## Debug Mode

Enable detailed logging to see exactly what's happening:

```powershell
# In .env:
LOG_LEVEL=DEBUG
VALIDATION_LOGS=true

# Then run:
python main.py
```

This will show:
- Credential loading process
- Every symbol evaluation
- All API calls and responses
- Detailed error traces

---

## Quick Diagnostics

Run these commands to diagnose issues:

```powershell
# 1. Health check
python check_bot_health.py

# 2. MT5 connection test
python -c "
import MetaTrader5 as mt5
print(f'MT5 version: {mt5.version()}')
mt5.initialize()
print('✅ MT5 initialized')
"

# 3. Supabase connection test
python -c "
from config.credentials import get_supabase_credentials
from supabase import create_client
url, key = get_supabase_credentials()
if url and key:
    client = create_client(url, key)
    print('✅ Supabase connected')
else:
    print('⚠️ No Supabase credentials')
"

# 4. View recent logs
Get-Content bot.log -Tail 50

# 5. Check CPU/Memory usage
Get-Process terminal64 | Select-Object Name, CPU, Memory
```

---

## Getting Help

If you can't resolve the issue:

1. **Enable debug logging** (see above)
2. **Run health check**: `python check_bot_health.py`
3. **Collect logs**: Save the last 100 lines from `bot.log`
4. **Note the exact error message**
5. **Include your OS version and Python version**

---

## Version Info

- **Updated**: 2026-09-06
- **Bot Version**: ICT State Machine v2.0
- **Supabase Support**: Optional (local-only mode available)
- **Python Required**: 3.9+
- **OS Support**: Windows, Linux, macOS

---

## Related Documentation

- [SETUP_CREDENTIALS_GUIDE.md](SETUP_CREDENTIALS_GUIDE.md) - Credential configuration
- [README.md](README.md) - General bot documentation
- [BOT_FLOW_DIAGRAM.md](BOT_FLOW_DIAGRAM.md) - Architecture overview
