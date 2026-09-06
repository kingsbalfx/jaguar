# QUICK REFERENCE - BOT ERROR FIX

## 🚀 START HERE

### First Time Setup
```powershell
# 1. Validate your setup
python check_bot_health.py

# 2. (Optional) Configure Supabase for cloud features
python configure_credentials.py

# 3. Start the bot
python main.py
# OR
python quick_start.py
```

---

## 🛠️ COMMON TASKS

### Fix Supabase Errors
```powershell
# See error about "Invalid URL"?
python configure_credentials.py
# Select option 1: Configure Supabase
# Enter your correct Supabase URL and API key
```

### View Current Configuration
```powershell
python configure_credentials.py
# See summary at top of menu
```

### Troubleshoot Issues
```powershell
# Run full diagnostic
python check_bot_health.py

# Check recent logs
Get-Content bot.log -Tail 50

# Search for errors
Select-String "ERROR" bot.log | Tail -20
```

### Enable Debug Mode
```powershell
# Edit .env and set:
LOG_LEVEL=DEBUG

# Then restart bot for detailed output
python main.py
```

---

## 📍 IMPORTANT FILES

| File | Purpose | Access |
|------|---------|--------|
| `.env` | Configuration | Text editor |
| `~/.ict_trading_bot/credentials.json` | Saved credentials | Auto-loaded |
| `bot.log` | Bot logs | `Get-Content bot.log -Tail 100` |
| `check_bot_health.py` | Validation tool | `python check_bot_health.py` |
| `configure_credentials.py` | Credential setup | `python configure_credentials.py` |
| `ERROR_TROUBLESHOOTING.md` | Error solutions | See below |

---

## 🆘 QUICK FIXES

### "Failed to create Supabase client: Invalid URL"
```
This is NORMAL if you don't have Supabase configured.
Bot works fine in local-only mode.

To use Supabase:
  python configure_credentials.py
  (Select option 1, enter valid credentials)

To suppress message:
  Edit .env and remove/comment out:
  # SUPABASE_URL=...
  # SUPABASE_KEY=...
```

### "IPC initialize failed" / MT5 Connection Error
```
1. Make sure MT5 is running
   Start → MetaTrader 5 (or click shortcut)

2. Wait 30-60 seconds for MT5 to initialize

3. Run the bot again
   python main.py
```

### Bot won't start
```
1. Quick health check:
   python check_bot_health.py

2. Install missing packages:
   pip install -r requirements.txt

3. Check bot.log for errors:
   Get-Content bot.log -Tail 100
```

### Mirror trading not working
```
1. Enable mirror trading:
   Edit .env: MIRROR_TRADING_ENABLED=true

2. Configure if using Supabase:
   python configure_credentials.py
   (Select option 3)

3. Restart bot
```

---

## 📚 DOCUMENTATION LINKS

| Document | When to Read |
|----------|--------------|
| `SETUP_CREDENTIALS_GUIDE.md` | First time setup |
| `ERROR_TROUBLESHOOTING.md` | Something doesn't work |
| `IMPLEMENTATION_SUMMARY.md` | Want to understand changes |
| `FILES_MODIFIED_AND_CREATED.md` | Need technical details |
| `README.md` | General bot info |

---

## 🎯 STARTUP COMMANDS

### Simple Start
```powershell
python main.py
```

### Safe Start (with validation)
```powershell
python quick_start.py
```

### Multi-Account Start
```powershell
# Set up accounts.json with your accounts
# Then:
python main.py
```

### Debug Start
```powershell
# Set in .env first:
# LOG_LEVEL=DEBUG

python main.py
```

---

## ✅ VERIFICATION CHECKLIST

Before running the bot, verify:

- [ ] `python check_bot_health.py` shows 8/10+ checks passing
- [ ] `~/.ict_trading_bot/credentials.json` exists (OR .env has SUPABASE_URL/KEY)
- [ ] MT5 is running and logged in
- [ ] Internet connection is active
- [ ] Firewall allows connections

---

## 🔧 MAINTENANCE

### Weekly
- Run: `python check_bot_health.py`
- Review: `bot.log` for warnings
- Check: Credential file permissions

### Monthly
- Update credentials if needed: `python configure_credentials.py`
- Review performance in logs
- Check broker account status

### After Bot Crash
1. Check `bot.log` last 100 lines
2. Run `python check_bot_health.py`
3. See `ERROR_TROUBLESHOOTING.md` for your error
4. Restart: `python quick_start.py`

---

## 📞 NEED HELP?

1. **Quick diagnostic**:
   ```powershell
   python check_bot_health.py
   ```

2. **See error solutions**:
   - Read `ERROR_TROUBLESHOOTING.md`
   - Search for your error message

3. **View detailed logs**:
   ```powershell
   Get-Content bot.log -Tail 100 -Wait
   ```

4. **Reset configuration**:
   ```powershell
   python configure_credentials.py
   # Select 4: Reset all credentials
   ```

---

## 🎊 WHAT IMPROVED

### Before
```
❌ Bot crashes on "Invalid URL" error
❌ Must use .env file for credentials
❌ No graceful fallback mode
❌ Poor error messages
❌ Hard to troubleshoot
```

### After
```
✅ Bot continues in local-only mode
✅ Credentials stored locally
✅ Automatic env var fallback
✅ Clear error messages with fixes
✅ Comprehensive troubleshooting tools
```

---

## 🚀 KEY FEATURES

- ✅ **Local-Only Mode**: Works without Supabase
- ✅ **Credential Storage**: Secure local JSON file
- ✅ **Easy Setup**: Interactive config tool
- ✅ **Health Checks**: Validate everything before running
- ✅ **Error Recovery**: Clear troubleshooting guides
- ✅ **Zero Breaking Changes**: Existing config still works
- ✅ **Mirror Trading**: Automatic fallback to local coordination
- ✅ **Multi-Account**: Full support for child processes

---

## 📊 STATUS

**Implementation**: ✅ Complete
**Testing**: ✅ Verified  
**Documentation**: ✅ Comprehensive
**Ready**: ✅ Production Ready

**Last Updated**: September 6, 2026

---

*For complete information, see IMPLEMENTATION_SUMMARY.md*
