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

## Keeping the bot alive (why signal delivery stops)

Signal emails only leave the building when the bot opens a trade, so a stopped bot looks
exactly like "the bot stopped sending signals to my subscribers". Two safeguards make
that visible now:

1. **Auto-restart supervisor** — start the bot with `.\run_bot_forever.ps1` instead of
   `python main.py`. It restarts the bot whenever the process exits, writes each run to
   `logs\bot_<timestamp>.log` and each restart to `logs\bot_supervisor.log`, and backs
   off (15s → 300s) when the bot keeps dying immediately. Create `STOP_BOT.flag` to stop
   cleanly without a restart.
   `.\setup_autostart.ps1` now registers the scheduled task against this supervisor
   (use `.\setup_autostart.ps1 -NoSupervisor` for the old single-run behaviour).
2. **Heartbeat** — the bot writes `bot_started` on boot and `bot_heartbeat` every
   `BOT_HEARTBEAT_SECONDS` (default 300, `0` disables) to Supabase `bot_logs`, so a dead
   bot is detectable from the website.

## Diagnosing "no signals" from the website

Open **Admin → Signal Health** (`/admin/signals`). It shows, in one screen:

- whether the bot API is reachable and how long ago the last master signal was produced;
- the exact audience for the current target plans and **why each skipped subscriber was
  skipped** (`plan_not_targeted`, `admin_without_paid_plan`, `plan_has_no_signals`,
  `daily_limit_zero`, ...);
- the signal pause switch (the same one the bot respects) and SMTP status;
- a **Deliver now** button that sends a real signal through the production pipeline.

Related environment variables (website):

| Variable | Purpose |
| --- | --- |
| `BOT_API_URL` / `BOT_API_INTERNAL` | Bot API base URL used by `/admin/accounts` and `/admin/signals`. |
| `BOT_API_TOKEN` | Token the website sends to the bot API (must match the bot's `BOT_API_TOKEN`). |
| `BOT_SIGNAL_SECRET` | Token the bot sends to `/api/bot/signals` (must match the website value). |
| `BOT_SIGNAL_TARGET_PLANS` | Default audience when the bot omits `targetPlans`. |
| `BOT_SIGNAL_ROLE_FALLBACK` | `true` (default) lets a paid `profiles.role`/`bot_tier` receive signals without an active subscription row. |
| `BOT_SIGNAL_QUOTA_FALLBACK` | `true` (default) uses the plan quota when a paid profile has `bot_max_signals_per_day = 0`. |
| `BOT_SIGNAL_INCLUDE_ADMIN` | `true` adds admins to the audience. |

Plan aliases such as `Academy`, `Academy Student`, `Mentorship` and `Student` are
resolved to the `premium` tier, so `BOT_SIGNAL_TARGET_PLANS=premium,vip,pro,lifetime,Academy`
no longer drops Academy subscribers.

## MT5 account inventory and student challenges

- **Admin → MT5 Accounts** (`/admin/accounts`) lists every login the bot knows about —
  environment variables, `accounts.example.json`, `data/accounts_local.json`, Supabase
  `mt5_credentials`/`mt5_submissions` — with its source, live/running status, API port and
  terminal resolution. Accounts can be added, synced, disabled or removed from the page.
- **Admin → Student Challenges** (`/admin/challenges`) approves student demo-challenge
  requests and manages the demo pool (MT5 demo logins or TradingView invite links).
  Students request a challenge from `/dashboard/challenge`; approval assigns a pool
  account and reveals the credentials only to that student. Challenge length, platforms
  and monthly allowance come from the subscription plan
  (`challengeAccess`, `challengeDays`, `challengePlatforms`, `challengesPerMonth`,
  `challengeMaxConcurrent` in `lib/pricing-config.js`).
- Run `jaguar-main/sql/2026-09-28_student_challenges.sql` in Supabase before using
  challenges (it also adds the optional `profiles.bot_signals_muted` flag).

