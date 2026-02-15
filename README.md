# Monorepo: Jaguar (web) + ICT Trading Bot

This workspace combines two projects:

- `jaguar-main` — Next/Node web frontend + admin dashboard
- `ict_trading_bot` — Python trading bot and associated tooling

Quickstart (requires Docker):

1. Copy `.env.example` to `.env` and fill keys.
2. From the repo root run:

```powershell
docker-compose up --build
```

This will start the web app on your configured domain and the bot API on its configured host/port.

Next steps implemented by scaffolding:
- `docker-compose.yml` to run both services.
- Root `.env.example` merging key variables.

Planned work (tracked in TODOs): auth, payments (Paystack), admin views, APIs, Docker test scripts, and security review.
# Jaguar + ICT Trading Bot Integration

This workspace contains two projects:

- `jaguar-main` — Next.js frontend + server (already deployed to Vercel in your setup).
- `ict_trading_bot` — Python trading bot that connects to MetaTrader5 and writes signals/logs to Supabase.

This README documents how I integrated the projects, what I fixed, and how to push & deploy.

---

## Summary of changes applied

- Bot-to-web webhook removed: the trading bot now writes signals and logs directly to Supabase (`bot_signals`, `bot_logs`).
- `ict_trading_bot/dashboard/bridge.py` now persists logs/signals using the official Supabase Python client with retries and logging.
- Added `Dockerfile`, `.env.example`, `requirements.txt` and `scripts/test_webhook.py` for the bot.
- Added MT5 helper wrappers in `ict_trading_bot/ict_concepts` (fib, fvg, order_blocks, market_structure) and made them defensive when MT5 returns no data.
- Implemented `get_price` and `get_open_positions` in `ict_trading_bot/execution/mt5_connector.py` so `main.py` runs.
- Updated Premium price to ₦90,000 across UI and Paystack integration.

---

## Quick local checks

1. Frontend (Next.js)

```powershell
cd jaguar-main
npm install
npm run dev
```

Open https://kingsbalfx.name.ng to verify UI and admin endpoints.

2. Bot (Python)

```powershell
cd ict_trading_bot
python -m pip install -r requirements.txt
set SUPABASE_URL=https://your_project_id.supabase.co
set SUPABASE_KEY=your_service_role_key_here
python scripts/test_webhook.py
```

You should see the test script persist a sample log into Supabase (`bot_logs`). The web app reads signals/logs from Supabase for admin views.

---

## How to push a feature branch and open PR

```bash
git checkout -b feat/integrate-bot-webhook
git add jaguar-main/server.js ict_trading_bot/dashboard/bridge.py ict_trading_bot/requirements.txt \
  ict_trading_bot/Dockerfile ict_trading_bot/.env.example ict_trading_bot/scripts/test_webhook.py \
  ict_trading_bot/ict_concepts/*.py ict_trading_bot/execution/mt5_connector.py jaguar-main/pages/pricing.js README.md
git commit -m "Integrate bot Supabase persistence, MT5 wrappers, Dockerfile, update premium price"
git push origin feat/integrate-bot-webhook
```

Open a Pull Request from `feat/integrate-bot-webhook` → `main` at `https://github.com/kingsbalfx/jaguar.git`.

---

## Vercel (Jaguar) required environment variables

In the Vercel project settings, set the following env vars (Server & Build as appropriate):

- `NEXT_PUBLIC_SITE_URL` = `https://kingsbalfx.name.ng`
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY` (server-only)
- `PAYSTACK_SECRET_KEY`

Note: The bot writes signals directly to Supabase. Ensure service role keys remain server-side only.

---

3. Deploying the bot (recommended: Render or any Docker host)

1. Connect your GitHub repo to Render (or any Docker host) and create a new service that points to the `ict_trading_bot` directory.
2. Render will detect the `Dockerfile` and build the image.
3. Set these Environment variables in Render:
  - `SUPABASE_URL` = `https://your_project_id.supabase.co`
  - `SUPABASE_KEY` = (service role key for server-side inserts)
  - MT5 credentials are managed via the Admin panel (stored in Supabase)
4. Start the service. The bot will persist signals to Supabase and log activity there.

Alternatively, deploy as a self-hosted system using the provided `Dockerfile`.

---

## Next recommended tasks I can do for you

- Add request validation for stronger API security.
- Implement full correlated-instrument (CCS) analysis and SMT pairs — please supply which pairs to monitor.
- Add CI (GitHub Actions) to build the Docker image, run lint/tests, and optionally push to a container registry.
- Push a branch and open a PR for you.

---

If you'd like, I can continue and implement the remaining steps now (HMAC signing, correlated pairs, CI, and open a PR). Which should I do next?







# kingsbalmagixtrading
