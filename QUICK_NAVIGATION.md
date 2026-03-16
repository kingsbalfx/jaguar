# Quick Navigation — ICT Trading Platform

This is the shortest path to every action you might need: docs, Supabase, MT5 credentials, Render deployment, and bot activation.

## 1. Doc Map (read in under 15 minutes)
- **START_HERE.md** – high-level summary + “what’s done” overview.
- **GUIDES_DIRECTORY.md** – directory of every guide (new quick nav entry is listed at the top now).
- **SUPABASE_INDEX.md** – fastest path into Supabase SQL editor (jump straight to the “Run code” checklist).
- **RENDER_WINDOWS_VPS_DEPLOYMENT_TEMPLATE.md** – Render + Windows bot deployment instructions (link from Render service docs).
- **ict_trading_bot/README.md** – quick, Windows-specific run instructions for the bot itself.

## 2. Supabase Quick Task List
1. Open `SUPABASE_INDEX.md` → follow the “Fastest path” checklist to reach SQL Editor.
2. If you get lost, go through `SUPABASE_NAVIGATION_GUIDE.md` for the button-by-button tour.
3. Use `SUPABASE_SQL_QUICK.md` for one-shot copy/paste SQL.
4. Verify schema by running the queries in the “Verification” section of `SUPABASE_SUMMARY.md`.
5. `mt5_credentials` table reference:
   ```sql
   -- Admin-only rows storing MT5 login info
   CREATE TABLE IF NOT EXISTS public.mt5_credentials (
     id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
     login text     NOT NULL,
     password text  NOT NULL,
     server text    NOT NULL,
     active boolean NOT NULL DEFAULT true,
     created_at timestamp DEFAULT CURRENT_TIMESTAMP,
     updated_at timestamp DEFAULT CURRENT_TIMESTAMP
   );
   ```
   Keep the `active` column. `utils/mt5_credentials.py` queries `active=true` first and falls back to latest row if the column is missing.
6. To insert new credentials:
   ```sql
   INSERT INTO mt5_credentials (login, password, server, active)
   VALUES ('12345678', 'secure-password', 'YourBrokerServer', true);
   ```
   When you rotate credentials, mark the previous row `active=false` and insert the new row with `active=true`.

## 3. MT5 Credentials — Code Perspective
- `ict_trading_bot/utils/mt5_credentials.py` requires `SUPABASE_URL` + `SUPABASE_KEY`. Those values must be the Supabase URL (`https://your-project.supabase.co`) and the service role key, not the internal Postgres connection string.
- The connector reports `mt5_credentials.active column missing` if you forget to run migration `migrations/003_add_mt5_credentials.sql`. Run the migration or manually add the column (see above) before saving credentials.
- Keep the `mt5_credentials` table RLS policy so only the service_role key can read/write it.

## 4. Render + Windows Deployment Snapshot
1. Deploy the web/app (admin APIs) to Render using the env vars in section 3 of `RENDER_WINDOWS_VPS_DEPLOYMENT_TEMPLATE.md`, especially `BOT_API_URL` pointing at your Windows host.
2. On Windows VPS:
   - Clone the repo and run `.\setup_windows.ps1`.
   - Edit `.env` per `.env.example`, fill `SUPABASE_URL` + `SUPABASE_KEY`, and optionally set `MT5_FALLBACK_API_ONLY` when no MT5 is available.
   - Run `.\setup_autostart.ps1` if you want the bot to start on logon.
   - Launch `.\.venv\Scripts\python.exe main.py` or rely on the scheduled task.
3. Use the bot control API (`/api/admin/restart-bot`, `/bot/health`) from Render’s `BOT_API_URL`.

## 5. Activation + Auto Commit/Push Notes
- **Activate the bot:** once `main.py` is running with MT5 open, confirm health via `curl http://localhost:8000/health`. Use the admin panel (Jaguar Web) to hit `/admin/settings` and store MT5 credentials (the panel writes into `mt5_credentials`).
- **Auto commit/push:** keep a trusted PowerShell script handy (you can store it in `scripts/auto_commit_push.ps1`) and run it when changes accumulate:
  ```powershell
  param($message = "autosave")
  cd C:\path\to\repo
  git add -A
  git commit -m $message
  git push origin main
  ```
  Schedule that script with Task Scheduler (set trigger to hourly or on file change) so production documentation and SQL changes are versioned automatically. Always verify before pushing to avoid secrets leakage.
- **Monitoring:** Pair the Windows bot logs (stored in `bot_logs`) with Render health checks for rapid troubleshooting.

## 6. Where to Go Next
- Close gaps by reading `PROJECT_COMPLETION_SUMMARY.md` and `IMPLEMENTATION_CHECKLIST.md` for missing items.
- When ready to ship, refer to `DEPLOYMENT_CHECKLIST.md` for the full launch runbook, `SECURITY_CHECKLIST.md` for protections, and `RENDER_WINDOWS_VPS_DEPLOYMENT_TEMPLATE.md` for Render + Windows wiring.
