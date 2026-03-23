# Windows Bot Runbook

This file explains what to run, what each command does, and how the full setup works.

## 1. What runs where

- `Vercel` hosts the website and admin panel.
- `Windows MT5 machine or VPS` runs:
  - MetaTrader 5 desktop terminal
  - Python bot in `ict_trading_bot`
- `Supabase` stores MT5 credentials, signals, and bot-related data.

Live MT5 trading does **not** happen on Vercel. It happens on the Windows machine where MT5 is open.

## 2. Start the bot manually

Open PowerShell and run:

```powershell
cd C:\Users\kingsbal\Documents\GitHub\jaguar\ict_trading_bot
.\.venv\Scripts\python.exe main.py
```

What this does:

- moves into the bot folder
- runs the bot using the virtualenv Python
- loads `.env`
- fetches MT5 credentials from Supabase
- connects to MetaTrader 5
- starts the bot API on port `8000`
- scans symbols for trading opportunities

## 3. Test MT5 only

Use this if you want to test the MT5 connection without starting the full bot:

```powershell
cd C:\Users\kingsbal\Documents\GitHub\jaguar\ict_trading_bot
.\.venv\Scripts\python.exe check_mt5.py
```

## 4. Bot API checks

Open these in a browser on the Windows machine:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/status`

What they mean:

- `/health` shows if the bot API is alive
- `/status` shows richer bot state like MT5 connection, account info, floating P/L, symbols, and recent events

## 5. Admin panel flow

In `/admin/settings`:

1. Save MT5 credentials
2. Restart the bot
3. Watch the **Bot Monitor**

The bot now auto-syncs credentials from Supabase, so manual local activation is no longer the normal workflow.

## 6. Important environment values

### Windows bot `.env`

```env
BOT_ENABLED=true
RISK_PER_TRADE=1.0
MAX_OPEN_TRADES=5
MT5_FALLBACK_API_ONLY=true
MT5_PATH=C:\Program Files\MetaTrader 5\terminal64.exe
MT5_TIMEOUT=60000
MT5_PORTABLE=false
MT5_AUTO_SYNC_INTERVAL=15
SUPABASE_URL=https://<your-project>.supabase.co
SUPABASE_KEY=<your-service-role-key>
LOG_LEVEL=INFO
LOG_FILE=bot.log
API_PORT=8000
API_HOST=0.0.0.0
```

### Vercel env

```env
BOT_API_URL=https://bot.yourdomain.com
BOT_API_INTERNAL=https://bot.yourdomain.com
```

Do **not** use:

- `127.0.0.1`
- `192.168.x.x`
- your website domain
- `/api/bot`

Your Vercel app must point to the Windows bot’s **public** URL.

## 7. Twilio env names

The app now accepts these variants:

- `TWILIO_ACCOUNT_SID` or `TWILIO_SID`
- `TWILIO_API_KEY_SID` or `TWILIO_API_KEY`
- `TWILIO_API_KEY_SECRET` or `TWILIO_API_SECRET`
- `TWILIO_PHONE` or `TWILIO_FROM_NUMBER`
- `TWILIO_AUTH_TOKEN` for SMS sending endpoints

## 8. Auto-start on Windows

The bot has already been configured to auto-start using a Scheduled Task:

- task name: `KingsbalMT5Bot`

Useful commands:

```powershell
Get-ScheduledTask -TaskName KingsbalMT5Bot | Get-ScheduledTaskInfo
Start-ScheduledTask -TaskName KingsbalMT5Bot
Unregister-ScheduledTask -TaskName KingsbalMT5Bot -Confirm:$false
```

## 9. What “online” really means

If you want algorithmic trading without manually opening PowerShell every time:

- keep the Windows machine or VPS running
- keep MT5 installed there
- keep the scheduled task enabled
- keep the bot reachable from Vercel using a public bot URL

That is the proper always-on setup.
