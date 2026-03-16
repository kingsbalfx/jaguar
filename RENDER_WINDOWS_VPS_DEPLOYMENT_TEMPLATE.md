# Render + Windows VPS Deployment Template (ICT Bot + Jaguar Web)

This template is copy-paste ready for your production setup where:
- Web/Admin app is hosted on Render/Vercel
- Live MT5 execution bot runs on Windows VPS (MT5 required)

> Why: `MetaTrader5` runtime is Windows/MT5-terminal dependent in this codebase.

## 1) What runs where

- **Render (Linux):** web app, admin APIs, Supabase-connected backend
- **Windows VPS:** `ict_trading_bot/main.py` + MT5 terminal
- **Supabase:** shared data (`mt5_credentials`, `bot_signals`, `bot_logs`)

<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
=======
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
### Important success condition

- A Render deployment can be **green/successful** while still not doing live MT5 trading.
- For **live trading enabled**, `python main.py` must run on Windows VPS with MT5 terminal logged in.
- Render should host web/admin and call the Windows bot API via `BOT_API_URL`.

<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
## 2) Required downloads (official links)

### Windows VPS essentials
- Python 3.11: https://www.python.org/downloads/release/python-3110/
- MetaTrader 5 Terminal: https://www.metatrader5.com/en/download
- Git for Windows: https://git-scm.com/download/win
- NSSM (optional service wrapper): https://nssm.cc/download

### Local tools (optional)
- Postman: https://www.postman.com/downloads/
- cURL for Windows docs: https://curl.se/windows/

## 3) Render service settings (Web/Admin)

Set env vars in your web service:

```env
NEXT_PUBLIC_SITE_URL=https://kingsbalfx.name.ng
NEXT_PUBLIC_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=YOUR_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVICE_ROLE_KEY

# Required so /api/admin/restart-bot can control Windows bot
BOT_API_URL=https://BOT_PUBLIC_DOMAIN_OR_IP:8000

# Optional internal endpoint override for bot-control API
BOT_API_INTERNAL=https://BOT_PUBLIC_DOMAIN_OR_IP:8000

ADMIN_API_KEY=GENERATE_A_STRONG_RANDOM_SECRET
```

## 4) Windows VPS bot setup (copy/paste)

```powershell
# 1) Clone repo
git clone https://github.com/<your-org>/<your-repo>.git
cd <your-repo>\ict_trading_bot

# 2) Create venv
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3) Install deps
pip install --upgrade pip
pip install -r requirements.txt

# 4) Create env
copy .env.example .env
notepad .env
```

Paste this in `.env`:

```env
BOT_ENABLED=true
RISK_PER_TRADE=1.0
MAX_OPEN_TRADES=5

SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_KEY=YOUR_SUPABASE_SERVICE_ROLE_KEY

API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO
LOG_FILE=bot.log

# Optional: keep bot process alive if MT5 is unavailable.
# Useful on Linux/Render; does NOT execute live MT5 trades.
MT5_FALLBACK_API_ONLY=true
```

Then run:

```powershell
python main.py
```

## 5) MT5 connection steps

1. Open MT5 terminal on VPS and login broker account.
2. In Jaguar Admin: `/admin/settings`, save MT5 login/password/server.
3. Click **Restart Bot** in admin or call bot `/restart`.

## 6) Firewall + networking

### Windows Firewall
Open inbound TCP 8000 (if direct exposure):

```powershell
New-NetFirewallRule -DisplayName "ICT Bot API 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

### Cloud firewall / provider SG
- Allow inbound TCP 8000 from trusted IPs (prefer web server egress IP only)
- Do not expose broadly if avoidable

## 7) Reverse proxy (recommended)

Use Caddy/Nginx in front of Flask for TLS and domain routing.

### Caddy example (`Caddyfile`)

```txt
bot.yourdomain.com {
  reverse_proxy 127.0.0.1:8000
}
```

Then set:

```env
BOT_API_URL=https://bot.yourdomain.com
BOT_API_INTERNAL=https://bot.yourdomain.com
```

## 8) Health checks

```bash
curl https://bot.yourdomain.com/health
curl https://bot.yourdomain.com/status
```

Expected health response shape:

```json
{"status":"ok","running":true}
```

## 9) If deploying bot to Render anyway (non-trading mode)

If you still run bot container on Render Linux, prevent MT5 crash:

```env
MT5_DISABLED=1
```

This allows process up but **does not run live MT5 trading**.

## 10) Troubleshooting quick map

If bot is hosted on Linux (Render), set one of these:

```env
MT5_DISABLED=1
# or
MT5_FALLBACK_API_ONLY=true
```

This prevents startup crashes when MT5 runtime is not present.

- `MetaTrader5 package not available on this platform`
  - You are running on Linux; move trading runtime to Windows VPS or set `MT5_DISABLED=1`.
- `No MT5 credentials found in Supabase`
  - Save credentials via `/admin/settings` and restart bot.
- `/api/admin/restart-bot` returns error
  - Verify `BOT_API_URL` and bot host reachability.
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
=======
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
- `column mt5_credentials.active does not exist`
  - Use latest code (it supports both schemas).
  - Optional SQL fix to add column:
    ```sql
    alter table public.mt5_credentials
      add column if not exists active boolean not null default true;

    update public.mt5_credentials
      set active = true
      where active is null;
    ```
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
<<<<<<< ours
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
=======
>>>>>>> theirs
