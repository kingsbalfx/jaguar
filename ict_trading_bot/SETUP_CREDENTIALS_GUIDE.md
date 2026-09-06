# BOT ERROR FIX - Complete Implementation Guide

## Summary of Changes

The bot has been updated to gracefully handle missing Supabase credentials and provide local credential management. The following errors have been fixed:

### ✅ Fixed Issues

1. **"Failed to create Supabase client: Invalid URL"** - The bot now gracefully handles missing credentials and continues in local-only mode
2. **Supabase credential management** - Added local credential storage in `~/.ict_trading_bot/credentials.json`
3. **MT5 connection resilience** - Improved error handling and logging
4. **Mirror trading fallback** - Mirror trading now works with local file-based coordination even without Supabase

## Setup Instructions

### Step 1: Configure Credentials (Optional but Recommended)

Run this command to interactively set up your credentials:

```powershell
cd c:\Users\kingsbal\Documents\GitHub\jaguar\ict_trading_bot
.\.venv\Scripts\python.exe configure_credentials.py
```

This will guide you through:
- **Supabase Setup** (optional) - For cloud persistence, analytics, and cross-account coordination
- **MT5 Broker Credentials** (required for trading) - Already set via environment
- **Mirror Trading** (optional) - For multi-account synchronization

### Step 2: Run the Bot

Run the bot as usual. It will now:
- Load credentials from local storage (`~/.ict_trading_bot/credentials.json`)
- Fall back to environment variables (`.env` file)
- Continue in **Local-Only Mode** if neither is available

```powershell
.\.venv\Scripts\python.exe main.py
```

## How It Works

### Credential Loading Order

1. **Environment Variables** (from `.env` file) - Highest priority
   ```
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_KEY=your_anon_key
   ```

2. **Local Storage** - `~/.ict_trading_bot/credentials.json`
   - Automatically loaded if env vars not set
   - Allows credentials to persist across deployments
   - Secure file permissions (0600 on Unix/Linux)

3. **Local-Only Mode** - No Supabase needed
   - Trading works fully
   - Mirror trading uses local file coordination
   - Dashboard and analytics unavailable

### File Locations

- **Credentials**: `~/.ict_trading_bot/credentials.json`
- **Mirror signals** (local fallback): `./data/mirror_signals.json`
- **Logs**: `./bot.log`

## Troubleshooting

### Bot still shows "Invalid URL" errors

**Cause**: Supabase URL in `.env` is malformed or the API key is expired

**Solution**:
1. Remove or comment out invalid credentials from `.env`:
   ```
   # SUPABASE_URL=https://ykpcrngkndrgornidojw.supabase.co
   # SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
   ```

2. Run the credential configurator:
   ```powershell
   .\.venv\Scripts\python.exe configure_credentials.py
   ```

3. Restart the bot - it will use local credentials

### Mirror Trading Not Working

**Check**:
1. Is mirror trading enabled? 
   ```powershell
   .\.venv\Scripts\python.exe configure_credentials.py
   ```

2. Check permissions on `./data/` folder

3. Verify all accounts have network access to each other

### MT5 Connection Failures

**"IPC initialize failed, Pipe server didn't answer in 60 sec"**

This is an MT5 issue, not the bot. Try:
1. Restart MetaTrader 5
2. Check firewall permissions
3. Verify MT5 is running correctly
4. Check system resources (RAM, CPU)

## What Gets Persisted to Supabase (Optional)

If Supabase is configured, the bot records:
- Trade signals and execution logs
- Account balance snapshots
- Mirror trade coordination
- Performance analytics

**These are completely optional.** The bot functions fully without Supabase.

## Security Notes

- Credentials are stored locally with restricted permissions
- `.env` file is ignored by git (see `.gitignore`)
- Never commit credentials to version control
- Store credentials in local `~/.ict_trading_bot/` directory only

## Running Multiple Accounts

Each child process will:
1. Load shared Supabase credentials from the parent
2. Use local credentials from `~/.ict_trading_bot/credentials.json`
3. Coordinate via Supabase (if available) or local file-based mirrors

## Next Steps

1. ✅ Update bot code (already done)
2. ✅ Create credential manager CLI (already done) 
3. **Run bot**: `python main.py`
4. **Optional**: Configure credentials: `python configure_credentials.py`
5. Add bot to auto-start if needed: `setup_autostart.ps1`

## Need Help?

### Enable Debug Logging

Set in `.env`:
```
LOG_LEVEL=DEBUG
```

This will show:
- Credential loading process
- Supabase connection attempts
- Mirror signal coordination
- All trading decisions

### Check Logs

View bot logs in real-time:
```powershell
Get-Content bot.log -Tail 100 -Wait
```

## Version Info

- **Updated**: 2026-09-06
- **Changes**: Supabase error handling + local credential storage + mirror trading fallback
- **Status**: ✅ Ready for production
