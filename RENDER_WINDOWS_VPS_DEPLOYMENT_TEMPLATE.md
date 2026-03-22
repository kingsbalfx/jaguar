# Render + Windows VPS Deployment Template (ICT Bot + Jaguar Web)

This guide explains how the Linux web/admin stack runs on Render or Vercel while live MT5 trading executes on a Windows VPS. The Jaguar web app manages credentials and bot controls, while the Windows MT5 terminal handles live execution.

## 1) What runs where

- **Render/Vercel (Linux):** Jaguar web app, admin APIs, Supabase-connected functions, pricing sync endpoints, and bot control endpoints (`/api/admin/*`)
- **Windows VPS:** `ict_trading_bot/main.py`, MT5 terminal, scheduled task for auto-start, and the bot API server that the web app calls through `BOT_API_URL`
- **Supabase:** shared data tables such as `mt5_credentials`, `mt5_submissions`, `bot_signals`, `bot_logs`, and user/subscription metadata

## 2) Success conditions to verify

- Web deployment is healthy and the admin pages load
- Windows VPS is running `python main.py` with MT5 logged into the broker account
- `BOT_API_URL` points to the reachable Windows bot API
- Supabase `mt5_credentials` contains one active row, or the latest row if you are still on the older schema without `active`

## 3) Required downloads for Windows

- Python 3.11 installer: https://www.python.org/downloads/release/python-3110/
- MetaTrader 5 terminal: https://www.metatrader5.com/en/download
- Git for Windows: https://git-scm.com/download/win
- NSSM (optional service wrapper): https://nssm.cc/download
- Optional tools: Postman and curl for Windows docs at https://curl.se/windows/

## 4) Web service environment variables

Set these values in your Render or Vercel project:

```env
NEXT_PUBLIC_SITE_URL=https://your-production-domain
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=anon-key
SUPABASE_SERVICE_ROLE_KEY=service-role-key

BOT_API_URL=https://windows-bot-host:8000
BOT_API_INTERNAL=https://windows-bot-host:8000

ADMIN_API_KEY=32+char-random-secret
PAYSTACK_PUBLIC_KEY=pk_live_...
PAYSTACK_SECRET_KEY=sk_live_...

# Optional if you need API-only fallback mode
MT5_FALLBACK_API_ONLY=true
```

## 5) Windows VPS bot setup

```powershell
git clone https://github.com/<your-org>/<your-repo>.git
cd <your-repo>\ict_trading_bot

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install --upgrade pip
pip install -r requirements.txt

copy .env.example .env
notepad .env
```

Use values like:

```env
BOT_ENABLED=true
RISK_PER_TRADE=1.0
MAX_OPEN_TRADES=5

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=service-role-key

API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO
LOG_FILE=bot.log
```

Then start the bot:

```powershell
python main.py
```

## 6) MT5 credential workflow

- Admins save MT5 credentials from `/admin/settings`
- The app stores the active bot credentials in `public.mt5_credentials`
- User submissions are stored in `public.mt5_submissions` and can be activated into `mt5_credentials`
- The current API supports both schemas:
  - preferred schema with `active boolean`
  - older schema that falls back to the latest row

Recommended table shape:

```sql
create table if not exists public.mt5_credentials (
  id uuid primary key default gen_random_uuid(),
  login text not null,
  password text not null,
  server text not null,
  active boolean not null default true,
  created_at timestamp default current_timestamp,
  updated_at timestamp default current_timestamp
);
```

If your project is missing the `active` column:

```sql
alter table public.mt5_credentials
  add column if not exists active boolean not null default true;

update public.mt5_credentials
  set active = true
  where active is null;
```

## 7) Activation and restart flow

1. Open MT5 on the Windows VPS and log into the broker account.
2. In Jaguar Admin at `/admin/settings`, save MT5 login, password, and server.
3. If using user submissions, activate the chosen submission from the same admin page.
4. Restart the bot from the admin UI or through the bot API so it reloads the latest credentials.

## 8) Firewall and networking

Allow inbound TCP 8000 on Windows if the web app must reach the bot directly:

```powershell
New-NetFirewallRule -DisplayName "ICT Bot API 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

Prefer restricting access to trusted IPs or using a reverse proxy such as Caddy or Nginx.

## 9) Health checks

```bash
curl https://your-production-domain/health
curl https://bot.yourdomain.com/health
curl https://bot.yourdomain.com/status
```

Expected bot health response:

```json
{"status":"ok","running":true}
```

## 10) Troubleshooting

- Render or Vercel can deploy successfully even when live MT5 trading is not running. Live trading still depends on the Windows VPS bot.
- If `MetaTrader5` is unavailable on Linux, do not expect live trading there. Keep execution on Windows VPS.
- If `/api/admin/restart-bot` fails, verify `BOT_API_URL` and Windows bot reachability.
- If MT5 credentials appear missing, save them again from `/admin/settings` and confirm the insert succeeded in Supabase.
- If you get `column mt5_credentials.active does not exist`, apply the SQL above or rely on the fallback-compatible code already in the app.
