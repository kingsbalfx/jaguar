# Render + Windows VPS Deployment Template (ICT Bot + Jaguar Web)

This guide explains how the Linux web/admin stack runs on Render while live MT5 trading executes on a Windows VPS. Everything here assumes the `ict_trading_bot` folder speaks to Supabase for configuration and the Windows MT5 terminal handles the live positions.

## 1) What runs where
- **Render (Linux)** – Jaguar web app, admin APIs, Supabase-connected functions, pricing sync endpoints, and bot control endpoints (`/api/admin/*`).
- **Windows VPS** – `ict_trading_bot/main.py`, MT5 terminal, scheduled task for auto-start, and `bot_api` server that Render calls through `BOT_API_URL`.
- **Supabase** – shared data tables such as `mt5_credentials` (admin only), `bot_signals`, `bot_logs`, pricing tables, and user/subscription metadata.

## 2) Success conditions to verify
- Render service reports healthy (`/health` returns `{"status":"ok"}`).
- Windows host is running `main.py` with MT5 logged in, and `curl http://localhost:8000/health` returns a running bot status.
- Render can reach the Windows bot via the env var `BOT_API_URL`; test `/restart` or `/status` from Render after each Windows restart.
- Supabase `mt5_credentials` contains at least one row marked `active=true` (or latest row if you are using older schema).

## 3) Required downloads for Windows
- Python 3.11 installer: https://www.python.org/downloads/release/python-3110/
- MetaTrader 5 terminal: https://www.metatrader5.com/en/download
- Git for Windows: https://git-scm.com/download/win
- NSSM (optional service wrapper): https://nssm.cc/download
- Optional monitoring tools: Postman, curl (https://curl.se/windows/)

## 4) Render service settings (env configuration)
Set these values in Render’s environment variables for the web/admin service. Replace placeholders with your own:
```env
NEXT_PUBLIC_SITE_URL=https://your-production-domain
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=anon-key
SUPABASE_SERVICE_ROLE_KEY=service-role-key

BOT_API_URL=https://windows-bot-host:8000
BOT_API_INTERNAL=https://windows-bot-host:8000

ADMIN_API_KEY=32+ char random secret
PAYSTACK_PUBLIC_KEY=pk_live_...
PAYSTACK_SECRET_KEY=sk_live_...

# Optional: keep bot API up even when MT5 is down
MT5_FALLBACK_API_ONLY=true
```
Render needs `BOT_API_URL` so the admin UI can restart the Windows bot or query its health.

## 5) Windows VPS bot setup
1. Clone the repo and switch to the bot folder:
   ```powershell
   git clone https://github.com/<your-org>/<your-repo>.git
   cd <your-repo>\ict_trading_bot
   ```
2. Run the reusable setup script:
   ```powershell
   .\setup_windows.ps1
   ```
   - Creates `.venv`, upgrades pip, installs requirements, and copies `.env.example`.
3. Update `.env`:
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
   Do not point `SUPABASE_URL` to a `postgresql://` string; it must be the HTTP project URL or the Supabase REST endpoint.
4. Optional but recommended: create the scheduled task to run the bot at logon:
   ```powershell
   .\setup_autostart.ps1
   ```
5. Start the bot manually once to confirm:
   ```powershell
   .\.venv\Scripts\python.exe main.py
   ```

## 6) MT5 credential workflow (Supabase table)
- The bot reads admin-managed MT5 credentials from `public.mt5_credentials`.
- Table schema (created by `migrations/003_add_mt5_credentials.sql`):
  ```sql
  CREATE TABLE IF NOT EXISTS mt5_credentials (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    login text NOT NULL,
    password text NOT NULL,
    server text NOT NULL,
    active boolean NOT NULL DEFAULT true,
    created_at timestamp DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp DEFAULT CURRENT_TIMESTAMP
  );
  ```
- If your project is missing the `active` column, run:
  ```sql
  ALTER TABLE public.mt5_credentials
    ADD COLUMN IF NOT EXISTS active boolean NOT NULL DEFAULT true;

  UPDATE public.mt5_credentials
    SET active = true
    WHERE active IS NULL;
  ```
- Admins insert or rotate credentials through Supabase SQL or the Admin panel. Always keep just one row flagged `active=true`. The code first queries `active=true` and falls back to the latest row if the column was missing.
- RLS policy:
  ```sql
  CREATE POLICY "service_role_mt5_credentials" ON mt5_credentials
    FOR ALL USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');
  ```

## 7) Activation, monitoring, and automation
- **Activation**: Open MT5, log into your broker, then hit the Admin panel (`/admin/settings`) to store the credentials (writes into `mt5_credentials`). Restart the bot via `/api/admin/restart-bot` or the Render admin UI once credentials are saved.
- **Health**: `curl http://localhost:8000/health` on Windows and `https://your-production-domain/health` from Render should both return `{"status":"ok"}` or similar.
- **Auto commit & push**: Add a lightweight PowerShell script such as `scripts/auto_commit_push.ps1`:
  ```powershell
  param($message = 'autosave')

  cd C:\path\to\repo
  git add -A
  git commit -m $message
  git push origin main
  ```
  Schedule this script in Task Scheduler (trigger: hourly or on specific working hours) to keep documentation, SQL migrations, and config changes version-controlled. Make sure you review diffs before pushing and never commit secrets.
- **Log streaming**: Render can fetch bot logs via the `/api/admin/bot-logs` endpoint, and Windows writes `bot_logs` rows that the web UI surfaces for auditing.

## 8) Firewall + networking
- Allow inbound TCP 8000 on Windows Firewall if Render must reach it directly:
  ```powershell
  New-NetFirewallRule -DisplayName "ICT Bot API 8000" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
  ```
- Limit reach to Render’s egress IP or your admin station. Avoid exposing the bot API publicly without a reverse proxy.
- Use a reverse proxy (Caddy, Nginx) or tunneling (e.g., Cloudflare Tunnel) if you want TLS termination in front of the Windows bot API.

## 9) Troubleshooting checklist
- `MT5_DISABLED=1` lets you run the Flask API on Render or Linux without trying to connect to MT5. Keep `MT5_FALLBACK_API_ONLY=true` when you only need API responsiveness.
- If Supabase returns `column mt5_credentials.active does not exist`, apply the SQL from section 6 and rerun the deployment script.
- Verify `SUPABASE_URL`/`SUPABASE_KEY` in `.env`. They must point to the Supabase REST endpoint and service-role key (not the internal Postgres connection string).
- Combine Render health checks with Windows Task Scheduler logs to confirm the bot restarts automatically.
